#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent
SCHEMAS = ROOT / "schemas"
YAML_SCHEMA = json.loads((SCHEMAS / "grammar-yaml.schema.json").read_text(encoding="utf-8"))

LANG_DIR_RE = re.compile(r"^grammar-([a-z]{2,3})$")
LANG_FILE_RE = re.compile(r"^(?P<head>.+?)\.(?P<lang>[a-z]{2,3})\.md$")
WARN_ALIASES = {"jp": "ja"}


def err(msg: str) -> None:
    print(f"::error::{msg}")


def warn(msg: str) -> None:
    print(f"::warning::{msg}")


def is_valid_lang(code: str) -> bool:
    return bool(re.fullmatch(r"[a-z]{2,3}", code))


def parse_markdown_sections(md_text: str) -> dict[str, object]:
    """
    Return dict(section -> structure).
    Guides/Q&A => list of {url,name,description?,recommended?}
    Related    => map of heading -> list of entries.
    Enforces: only dash lists under each H2 with optional leading ⭐ flag.
    """

    lines = md_text.splitlines()
    allowed_h2 = {"Guides", "Q&A", "Related"}
    sections: dict[str, object] = {}
    h2: str | None = None
    h3: str | None = None

    for i, line in enumerate(lines, 1):
        if line.startswith("# "):
            h2 = None
            h3 = None
            continue

        if line.startswith("## "):
            h2 = line[3:].strip()
            h3 = None
            if h2 not in allowed_h2:
                err(f"Unknown H2 '{h2}'. Allowed: {sorted(allowed_h2)}")
                raise SystemExit(1)
            sections[h2] = {} if h2 == "Related" else []
            continue

        if line.startswith("### "):
            if h2 != "Related":
                err(f"H3 only allowed under '## Related'; offending line {i}: '{line}'")
                raise SystemExit(1)
            h3 = line[4:].strip()
            if not h3:
                err(f"Empty '###' heading under Related at line {i}.")
                raise SystemExit(1)
            related_map = sections.setdefault("Related", {})
            assert isinstance(related_map, dict)
            related_map.setdefault(h3, [])
            continue

        if h2:
            stripped = line.strip()
            if not stripped:
                continue

            recommended = False
            if stripped.startswith("- ⭐ "):
                recommended = True
                item = stripped[4:]
            elif stripped.startswith("- "):
                item = stripped[2:]
            else:
                err(f"Only dash lists allowed under '## {h2}'; offending line {i}: '{line}'")
                raise SystemExit(1)

            match = re.match(
                r"\[(?P<name>[^\]]+)\]\((?P<url>https?://[^\s)]+)\)(?:\s*-\s*(?P<desc>.+))?$",
                item,
            )
            if not match:
                err(f"Invalid list item under '## {h2}': '{item}'")
                raise SystemExit(1)

            name = match.group("name")
            url = match.group("url")
            desc = match.group("desc") or ""

            entry = {"url": url, "name": name}
            if desc:
                entry["description"] = desc
            if recommended:
                entry["recommended"] = True

            if h2 == "Related":
                related_map = sections.setdefault("Related", {})
                assert isinstance(related_map, dict)
                if not h3:
                    err(
                        "Links under '## Related' must be grouped by '### <headword>' "
                        f"before the list. Offending line {i}: '{line}'"
                    )
                    raise SystemExit(1)
                related_map.setdefault(h3, [])
                related_map[h3].append(entry)
            else:
                section_list = sections[h2]
                assert isinstance(section_list, list)
                section_list.append(entry)

        elif stripped := line.strip():
            err(f"Unexpected content outside a recognised section at line {i}: '{line}'")
            raise SystemExit(1)

    return sections


def main() -> int:
    ok = True
    for directory in ROOT.iterdir():
        if not directory.is_dir() or not directory.name.startswith("grammar-"):
            continue

        match = LANG_DIR_RE.match(directory.name)
        if not match:
            err(
                f"Invalid grammar directory name '{directory.name}'. "
                "Use grammar-xx with lowercase ISO/BPC47 code."
            )
            ok = False
            continue

        target_language = match.group(1)
        if target_language in WARN_ALIASES:
            warn(
                f"Language code '{target_language}' is aliased to "
                f"'{WARN_ALIASES[target_language]}'. Prefer that code going forward."
            )

        if not is_valid_lang(target_language):
            err(f"Invalid language code '{target_language}' in directory '{directory.name}'.")
            ok = False

        for md_file in directory.glob("*.md"):
            md_match = LANG_FILE_RE.match(md_file.name)
            if not md_match:
                err(
                    f"Invalid markdown filename '{md_file.name}'. "
                    "Must be <headword>.<yy>.md with yy lowercase."
                )
                ok = False
                continue

            headword = md_match.group("head")
            yaml_path = directory / f"{headword}.yaml"
            if not yaml_path.exists():
                err(f"Markdown '{md_file.name}' has no sibling YAML '{headword}.yaml'.")
                ok = False

            text = md_file.read_text(encoding="utf-8").lstrip("\ufeff")
            if not text.startswith(f"# {headword}"):
                err(f"Markdown '{md_file.name}' must start with H1 '# {headword}'.")
                ok = False
                continue

            try:
                sections = parse_markdown_sections(text)
            except SystemExit:
                ok = False
                continue

        validator = Draft202012Validator(YAML_SCHEMA, format_checker=FormatChecker())
        for yaml_file in directory.glob("*.yaml"):
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
            for error in errors:
                err(f"{yaml_file}: {error.message}")
            if errors:
                ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
