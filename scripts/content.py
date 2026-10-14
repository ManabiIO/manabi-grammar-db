"""One lossless authoring/identity/validation path for lint and SQLite builds."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from markdown_it import MarkdownIt

from schema_contract import ROOT, row_schema

SCHEMAS = ROOT / "schemas"
YAML_SCHEMA = json.loads((SCHEMAS / "grammar-yaml.schema.json").read_text(encoding="utf-8"))
ROW_SCHEMA = row_schema(YAML_SCHEMA)
REGISTRY_SCHEMA = json.loads((SCHEMAS / "reference-registry.schema.json").read_text(encoding="utf-8"))
LANG_RE = re.compile(r"^[a-z]{2,3}$")
LANG_DIR_RE = re.compile(r"^grammar-([a-z]{2,3})$")
EXPLANATION_LOCALE_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Z][a-z]{3})?(?:-(?:[A-Z]{2}|[0-9]{3}))?$")
LANG_FILE_RE = re.compile(r"^(?P<stem>.+)\.(?P<lang>[a-z]{2,3}(?:-[A-Z][a-z]{3})?(?:-(?:[A-Z]{2}|[0-9]{3}))?)\.md$")
class StrictLoader(yaml.SafeLoader):
    """PyYAML safe scalar semantics, with only true/false implicit booleans.

    This is deliberately not advertised as a complete YAML 1.2 implementation.
    Mapping keys must be strings; aliases and merge keys are not authoring syntax.
    """
    yaml_implicit_resolvers = {
        key: [(tag, expr) for tag, expr in items if tag != "tag:yaml.org,2002:bool"]
        for key, items in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            event = self.peek_event()
            raise yaml.YAMLError(f"YAML aliases are unsupported at line {event.start_mark.line + 1}")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                raise yaml.YAMLError(f"YAML merge keys are unsupported at line {key_node.start_mark.line + 1}")
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise yaml.YAMLError(f"Mapping keys must be strings at line {key_node.start_mark.line + 1}")
            if key in mapping:
                raise yaml.YAMLError(f"Duplicate key '{key}' at line {key_node.start_mark.line + 1}")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


StrictLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false|True|False|TRUE|FALSE)$"), list("tTfF")
)


def load_yaml(text, source="<yaml>"):
    try:
        data = yaml.load(text.removeprefix("\ufeff"), Loader=StrictLoader)
    except yaml.YAMLError as error:
        raise ValueError(f"{source}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"{source}: YAML root must be a mapping/object")
    return data


def source_locations(text, source):
    """Common YAML node positions for compiler/debugger diagnostics."""
    locations = {}
    def walk(node, path):
        locations[path] = node.start_mark.line + 1
        if isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                walk(value, path + "." + key.value)
        elif isinstance(node, yaml.SequenceNode):
            for index, value in enumerate(node.value):
                walk(value, path + f"[{index}]")
    walk(yaml.compose(text.removeprefix("\ufeff"), Loader=StrictLoader), source)
    return locations


def validate(data, schema, source):
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(data))
    if errors:
        details = "; ".join(f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}" for error in errors)
        raise ValueError(f"{source}: {details}")


def web_url(value):
    try:
        parsed = urlsplit(value)
        return (parsed.scheme in {"http", "https"} and bool(parsed.hostname)
                and not parsed.username and not parsed.password and parsed.port != 0
                and not re.search(r"[\s\x00-\x1f\x7f]", value))
    except (ValueError, TypeError):
        return False


def entry_identity(stem):
    """The terminal .vN suffix is reserved; legacy bare stems mean variant 1."""
    match = re.fullmatch(r"(.+)\.v([0-9]+)", stem)
    if match:
        headword, number = match.groups()
        if str(int(number)) != number or not 2 <= int(number) <= 2147483647:
            raise ValueError(f"Invalid variant suffix in '{stem}'; use .v2, .v3, ...")
        return headword, int(number)
    if not stem or re.search(r"\.v[^.]*$", stem):
        raise ValueError(f"Invalid/reserved variant suffix in '{stem}'")
    return stem, 1


def entry_stem(headword, variant=1):
    if not headword or headword in {".", ".."} or any(c in headword for c in "/\\\n\r\0"):
        raise ValueError("Headword must be a single safe filename")
    if entry_identity(headword) != (headword, 1):
        raise ValueError("Headword cannot end in the reserved .vN suffix")
    if type(variant) is not int or not 1 <= variant <= 2147483647:
        raise ValueError("Variant must be an integer from 1 through 2147483647")
    return headword if variant == 1 else f"{headword}.v{variant}"


def parse_markdown_sections(text, headword=None, source="<markdown>"):
    text = text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    # CommonMark source maps count CR/LF lines, not Unicode paragraph separators.
    lines = text.split("\n")
    if not lines or not lines[0].startswith("# "):
        raise ValueError(f"{source}: line 1 must be the document H1")
    expected = headword if headword is not None else lines[0][2:]
    if lines[0] != f"# {expected}":
        raise ValueError(f"{source}: line 1 must be exactly '# {expected}'")
    tokens = MarkdownIt("commonmark").parse(text)
    headings = [(token, tokens[index + 1].content) for index, token in enumerate(tokens)
                if token.type == "heading_open"]
    titles = [(token, name) for token, name in headings if token.tag == "h1"]
    if len(titles) != 1 or titles[0][0].level != 0 or titles[0][0].map != [0, 1]:
        raise ValueError(f"{source}: exactly one document H1 is allowed")
    structural = [(token, name) for token, name in headings if token.tag == "h2" and token.level == 0]
    if any(token.tag in {"h1", "h2"} and token.level != 0 for token, _ in headings):
        raise ValueError(f"{source}: nested H1/H2 headings are unsupported; use H3–H6 in Meaning")
    first_section = structural[0][0].map[0] if structural else len(lines)
    if any(line.strip() for line in lines[1:first_section]):
        raise ValueError(f"{source}: content must belong to a recognized H2 section")
    sections = {}
    for index, (token, name) in enumerate(structural):
        start = token.map[0]
        end = structural[index + 1][0].map[0] if index + 1 < len(structural) else len(lines)
        if name not in {"Meaning", "Guides", "Q&A", "Related"} or lines[start] != f"## {name}":
            raise ValueError(f"{source}:{start + 1}: unknown/noncanonical H2 '{name}'")
        if name in sections:
            raise ValueError(f"{source}:{start + 1}: duplicate H2 '{name}'")
        body = lines[start + 1:end]
        if name == "Meaning":
            # Trim separator lines only. Stripping characters would turn a
            # leading indented code block into prose and erase hard breaks.
            while body and not body[0].strip():
                body.pop(0)
            while body and not body[-1].strip():
                body.pop()
            meaning = "\n".join(body)
            if not meaning:
                raise ValueError(f"{source}:{start + 1}: Meaning must include descriptive text")
            sections[name] = meaning
            continue
        section = {} if name == "Related" else []
        sections[name] = section
        group = None
        for offset, line in enumerate(body, start + 2):
            stripped = line.strip()
            if not stripped:
                continue
            if name == "Related" and line.startswith("### "):
                group = line[4:].strip()
                if not group or group in section:
                    raise ValueError(f"{source}:{offset}: empty or duplicate Related group '{group}'")
                section[group] = []  # Empty groups are preserved, never silently discarded.
                continue
            match = re.fullmatch(r"- (?P<star>⭐ )?\[(?P<name>[^\]]+)\]\((?P<url>[^\s)]+)\)(?: - (?P<desc>.+))?", stripped)
            if not match or not web_url(match["url"]):
                raise ValueError(f"{source}:{offset}: expected '- [Name](https://...) - description'")
            resource = {"name": match["name"], "url": match["url"]}
            if match["star"]:
                resource["recommended"] = True
            if match["desc"]:
                resource["description"] = match["desc"]
            if name == "Related":
                if group is None:
                    raise ValueError(f"{source}:{offset}: Related links require a '### <headword>' group")
                section[group].append(resource)
            else:
                section.append(resource)
    return sections


def load_registry(path):
    # Fixture repositories with no citations need no registry. Real canonical
    # builds package the registry even when all its collections are empty.
    if not path.exists():
        if path == ROOT / "references/registry.json":
            raise ValueError(f"{path}: canonical reference registry is required")
        return {"schemaVersion": 1, "sources": [], "references": [], "bindings": []}
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{path}: duplicate JSON key '{key}'")
            result[key] = value
        return result
    registry = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_pairs)
    validate(registry, REGISTRY_SCHEMA, path)
    sources, references, bindings = {}, {}, set()
    for item in registry["sources"]:
        if item["id"] in sources:
            raise ValueError(f"{path}: duplicate source ID {item['id']}")
        if (item["id"] == "takoboto") != ("release" in item):
            raise ValueError(f"{path}: Takoboto requires one pinned release; Wiktionary uses per-page revisions")
        sources[item["id"]] = item
    for item in registry["references"]:
        if item["id"] in references or item["sourceID"] not in sources or not item["id"].startswith(item["sourceID"] + ":"):
            raise ValueError(f"{path}: duplicate/unknown source reference {item['id']}")
        if item["sourceID"] == "takoboto" and item["id"] != f"takoboto:{item['entryID']}":
            raise ValueError(f"{path}: foreign entry ID disagrees with reference ID")
        references[item["id"]] = item
    for binding in registry["bindings"]:
        key = binding["ruleID"], binding["readerLanguage"]
        if key in bindings or any(ref not in references for ref in binding["references"]):
            raise ValueError(f"{path}: duplicate binding or unresolved reference for {key}")
        bindings.add(key)
    return registry


def collect_rows(root=ROOT, registry=None):
    rows, identities, rule_ids = [], set(), set()
    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or not directory.name.startswith("grammar-"):
            continue
        match = LANG_DIR_RE.fullmatch(directory.name)
        if not match:
            raise ValueError(f"{directory}: expected grammar-<2–3 lowercase language letters>")
        target = match[1]
        markdown = {}
        for path in sorted(directory.glob("*.md")):
            match = LANG_FILE_RE.fullmatch(path.name)
            if not match:
                raise ValueError(f"{path}: expected <headword>[.vN].<canonical explanation locale>.md")
            stem, reader = match["stem"], match["lang"]
            headword, variant = entry_identity(stem)
            if not (directory / f"{stem}.yaml").is_file():
                raise ValueError(f"{path}: no sibling YAML '{stem}.yaml'")
            markdown.setdefault((headword, variant), {})[reader] = parse_markdown_sections(
                path.read_text(encoding="utf-8"), headword, path
            )
        for path in sorted(directory.glob("*.yaml")):
            headword, variant = entry_identity(path.stem)
            data = load_yaml(path.read_text(encoding="utf-8"), path)
            validate(data, YAML_SCHEMA, path)  # No lossy aliases, filtering or numeric coercion.
            data.setdefault("targetLanguage", target)
            data.setdefault("headword", headword)
            data.setdefault("variant", variant)
            if (data["targetLanguage"], data["headword"], data["variant"]) != (target, headword, variant):
                raise ValueError(f"{path}: entry identity must match its directory and filename")
            if not data["ruleID"].startswith(f"grammar.{target}."):
                raise ValueError(f"{path}: ruleID must match target language {target}")
            if data["ruleID"] in rule_ids:
                raise ValueError(f"{path}: duplicate ruleID '{data['ruleID']}'")
            key = target, headword, variant
            if key in identities:
                raise ValueError(f"{path}: duplicate grammar identity {key}")
            identities.add(key)
            rule_ids.add(data["ruleID"])
            data["info"] = markdown.get((headword, variant), {})
            rows.append((*key, data))
    registry = registry if registry is not None else load_registry(root / "references/registry.json")
    by_rule = {row[3]["ruleID"]: row[3] for row in rows}
    references = {item["id"]: item for item in registry["references"]}
    for binding in registry["bindings"]:
        data = by_rule.get(binding["ruleID"])
        if data is None or binding["ruleVersion"] != data["ruleVersion"]:
            raise ValueError(f"Stale or missing rule reference binding: {binding['ruleID']}")
        if binding["readerLanguage"] not in data["info"]:
            raise ValueError(f"Binding has no companion reader Markdown: {binding['ruleID']}/{binding['readerLanguage']}")
        if any(references[ref]["targetLanguage"] != data["targetLanguage"] for ref in binding["references"]):
            raise ValueError(f"Binding target language mismatch: {binding['ruleID']}")
        data.setdefault("referenceBindings", []).append({key: value for key, value in binding.items() if key != "ruleID"})
    for target, headword, variant, data in rows:
        validate(data, ROW_SCHEMA, f"{target}/{headword}/{variant}")
    return rows


if __name__ == "__main__":
    import sys
    if sys.argv[1:] != ["--json"]: raise SystemExit("Usage: python scripts/content.py --json")
    print(json.dumps(collect_rows(), ensure_ascii=False, separators=(",", ":")))
