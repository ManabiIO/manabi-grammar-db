#!/usr/bin/env python3
"""Local-only guard: agent iteration must never allocate GitHub Actions runners.

Requires PyYAML. Run this before integrating workflow changes. This command does
not call GitHub, install hooks, dispatch jobs, or change repository settings.
"""
import argparse
import json
from pathlib import Path
import re
import sys

import yaml

FORBIDDEN = {'push', 'pull_request', 'pull_request_target', 'merge_group',
             'schedule', 'repository_dispatch', 'create', 'release', 'deployment',
             'issue_comment', 'issues', 'check_run', 'check_suite', 'status'}


def branch_is_required(condition, branch):
    """Conservatively prove a positive branch check is required for a true result.

    Interpret only Boolean grouping and conjunction/disjunction. Function calls,
    comparisons and negated predicates are opaque atoms. Unknown atoms cannot
    establish admission. An OR is safe only when every arm requires the branch;
    an AND is safe if any factor requires it. No expression is executed.
    """
    condition = condition.strip()
    # Collect only top-level operators; quoted text and function arguments must
    # not be mistaken for Boolean grouping. GitHub escapes a quote as two quotes.
    depth, quoted, pairs, operators = 0, False, {}, []
    opening = []
    index = 0
    while index < len(condition):
        char = condition[index]
        if char == "'":
            if quoted and index + 1 < len(condition) and condition[index + 1] == "'":
                index += 2
                continue
            quoted = not quoted
        elif not quoted:
            if char == '(':
                opening.append(index)
                depth += 1
            elif char == ')':
                if not opening:
                    return False
                pairs[opening.pop()] = index
                depth -= 1
            elif depth == 0 and condition[index:index+2] in ('&&', '||'):
                operators.append((index, condition[index:index+2]))
                index += 1
        index += 1
    if quoted or opening:
        return False
    if condition.startswith('(') and pairs.get(0) == len(condition) - 1:
        return branch_is_required(condition[1:-1], branch)
    for operator, combine in (('||', all), ('&&', any)):
        positions = [index for index, value in operators if value == operator]
        if positions:
            parts = []
            start = 0
            for index in positions:
                parts.append(condition[start:index])
                start = index + 2
            parts.append(condition[start:])
            return combine(branch_is_required(part, branch) for part in parts)
    return condition == branch


def check(root):
    root = Path(root).resolve(strict=True)
    policy = json.loads((root / '.github/actions-spending-policy.json').read_text())
    errors = []
    if policy.get('automatic_spending') is not False:
        errors.append('automatic_spending must remain false')
    branch = "github.ref == 'refs/heads/" + policy['default_branch'] + "'"
    files = {p.relative_to(root).as_posix(): p for pattern in ('*.yml', '*.yaml')
             for p in (root / '.github/workflows').glob(pattern)}
    for relative in policy['active']:
        if relative not in files:
            errors.append(relative + ': declared active workflow is missing')
    for relative, path in sorted(files.items()):
        data = yaml.safe_load(path.read_text())
        events = data.get('on', data.get(True, {}))
        jobs = data.get('jobs', {})
        # Historical stubs intentionally retain disabled workflow IDs. A stub
        # must have exactly this constant-false guard and no reusable/auto event.
        retired = (set(events) == {'workflow_dispatch'} and bool(jobs) and all(
            j.get('if') == '${{ ' + branch + ' && false }}' for j in jobs.values()))
        if retired:
            if relative in policy['active']:
                errors.append(relative + ': active entry is a retirement stub')
            continue
        declared = policy['active'].get(relative)
        if declared is None:
            errors.append(relative + ': undeclared workflow can spend minutes')
            continue
        if not isinstance(events, dict) or set(events) != set(declared['events']):
            errors.append(relative + ': event list differs from explicit policy')
        if set(events) & FORBIDDEN or set(events) - {'workflow_dispatch', 'workflow_call', 'workflow_run'}:
            errors.append(relative + ': automatic iteration trigger is forbidden')
        if 'workflow_run' in events:
            continuation = events['workflow_run']
            if (continuation.get('branches') != [policy['default_branch']]
                    or continuation.get('types') != ['completed']
                    or continuation.get('workflows') != declared.get('after')):
                errors.append(relative + ': release continuation is not bound to its declared parent')
        inputs = (events.get('workflow_dispatch') or {}).get('inputs', {})
        for name, job in jobs.items():
            condition = ' '.join(str(job.get('if', '')).split())
            if condition.startswith('${{'):
                condition = condition[3:-2].strip()
            if not branch_is_required(condition, branch):
                errors.append(relative + '/' + name + ': missing default-branch runner admission')
            if not job.get('uses') and not isinstance(job.get('timeout-minutes'), int):
                errors.append(relative + '/' + name + ': hosted job needs an explicit timeout')
            native = 'macos' in str(job.get('runs-on')) or 'macos' in str(job.get('strategy', {}))
            if native:
                option = inputs.get('include_native', {})
                if option.get('type') != 'boolean' or option.get('default') is not False:
                    errors.append(relative + '/' + name + ': macOS must be an opt-in, default false')
                if 'matrix.' in str(job.get('runs-on')):
                    matrix = job.get('strategy', {}).get('matrix', {})
                    expected_os = "${{ inputs.include_native && fromJSON('[\"ubuntu-latest\", \"macos-15\"]') || fromJSON('[\"ubuntu-latest\"]') }}"
                    if matrix != {'os': expected_os} or job.get('runs-on') != '${{ matrix.os }}':
                        errors.append(relative + '/' + name + ': native matrix does not require opt-in')
                elif not branch_is_required(condition, 'inputs.include_native'):
                    errors.append(relative + '/' + name + ': macOS runner does not require opt-in')
    # Production publication needs a distinct human-controlled dispatch flag.
    for relative, declaration in policy['active'].items():
        if not declaration.get('publishes_server') or relative not in files:
            continue
        data = yaml.safe_load(files[relative].read_text())
        option = (data.get('on', data.get(True))['workflow_dispatch'] or {}).get('inputs', {}).get('publish_release', {})
        if option.get('type') != 'boolean' or option.get('default') is not False:
            errors.append(relative + ': production publish confirmation must default false')
        if 'inputs.publish_release == true' not in str(data['jobs']['release-route'].get('if')):
            errors.append(relative + ': production work does not require confirmation before runner allocation')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        errors = check(args.root)
    except (ValueError, KeyError, TypeError, OSError, yaml.YAMLError) as error:
        parser.exit(1, 'Invalid Actions spending policy: ' + str(error) + '\n')
    if errors:
        parser.exit(1, '\n'.join(errors) + '\n')
    print('Actions spending policy passed: no automatic push/PR/schedule runners; macOS opt-in.')


if __name__ == '__main__':
    main()
