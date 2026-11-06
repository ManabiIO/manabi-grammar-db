# Local qualification and publication

Run relevant content/schema/client checks locally before integrating changes.
Pushes and pull requests must not start hosted Actions. Preserve
`.github/actions-spending-policy.json` and the local guard. Only an explicit
user request to run hosted qualification or publish authorizes manual dispatch
on `main`. Publication remains opt-in and requires the existing build gates.

Before integrating workflow edits, run
`python3 scripts/check_actions_spending.py` (requires PyYAML) and `actionlint`.
Do not reintroduce push, PR, schedule or repository-dispatch triggers.
