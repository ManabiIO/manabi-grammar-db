#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import json
from pathlib import Path


from content import ROOT, YAML_SCHEMA, entry_stem, load_yaml, validate, EXPLANATION_LOCALE_RE

LANG_RE = re.compile(r"^[a-z]{2,3}$")


def validate_lang(code: str, role: str) -> str:
    if not (EXPLANATION_LOCALE_RE if role == "reader" else LANG_RE).fullmatch(code):
        raise argparse.ArgumentTypeError(
            f"{role} language must use canonical language/script/region casing (received '{code}')"
        )
    return code


def build_yaml_stub(headword: str, target_lang: str, reader_lang: str, rule_id: str, variant: int = 1) -> str:
    # JSON scalars are valid YAML and avoid interpolation into YAML syntax.
    quoted = json.dumps(headword, ensure_ascii=False)
    return (
        f"# Author explanation content before publishing ({target_lang}).\n"
        f"headword: {quoted}\n"
        f"ruleID: {json.dumps(rule_id)}\n"
        "ruleVersion: 1\n"
        "examples: []\n"
        f"variant: {variant}\n"
    )


def build_markdown_stub(headword: str) -> str:
    return (
        f"# {headword}\n\n"
        "## Meaning\n"
        "TODO: Explain the grammar point and its context constraints.\n"
    )


def write_file(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists (use --force to overwrite)")
    if path.resolve() != path:
        raise ValueError(f"Unexpected output target: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Created {path.relative_to(ROOT)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a grammar entry stub.")
    parser.add_argument("--headword", required=True, help="Headword for the grammar entry.")
    parser.add_argument("--rule-id", required=True, help="Stable identity, e.g. grammar.ja.ga.subject.")
    parser.add_argument(
        "--target-lang",
        required=True,
        type=lambda value: validate_lang(value, "target"),
        help="Target language code (grammar-<code> directory).",
    )
    parser.add_argument(
        "--reader-lang",
        required=True,
        type=lambda value: validate_lang(value, "reader"),
        help="Reader language code for the markdown file.",
    )
    parser.add_argument("--variant", type=int, default=1, help="Positive variant; values above 1 use .vN filenames.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files if present.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stem = entry_stem(args.headword, args.variant)
    if not re.fullmatch(r"grammar\." + args.target_lang + r"\.[a-z0-9][a-z0-9.-]*", args.rule_id):
        raise ValueError("Rule ID must match the target language and schema")
    directory = ROOT / f"grammar-{args.target_lang}"
    yaml_path = directory / f"{stem}.yaml"
    md_path = directory / f"{stem}.{args.reader_lang}.md"

    stub = build_yaml_stub(args.headword, args.target_lang, args.reader_lang, args.rule_id, args.variant)
    validate(load_yaml(stub, yaml_path), YAML_SCHEMA, yaml_path)
    try:
        for path in [yaml_path, md_path]:
            if path.resolve() != path:
                raise ValueError(f"Unexpected output target: {path}")
            if path.exists() and not args.force:
                raise FileExistsError(f"{path} already exists (use --force to overwrite)")
        write_file(yaml_path, stub, args.force)
        write_file(md_path, build_markdown_stub(args.headword), args.force)
    except FileExistsError as error:
        print(error)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
