#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

LANG_RE = re.compile(r"^[a-z]{2,3}$")


def validate_lang(code: str, role: str) -> str:
    if not LANG_RE.fullmatch(code):
        raise argparse.ArgumentTypeError(
            f"{role} language must be 2-3 lowercase letters (received '{code}')"
        )
    return code


def build_yaml_stub(headword: str, target_lang: str, reader_lang: str) -> str:
    return (
        f"# YAML stub for {headword} ({target_lang})\n"
        f"headword: {headword}\n"
        "jmdictId: TODO\n"
        "pattern:\n"
        "  mecab: TODO\n"
        "examples:\n"
        "  - https://example.com/example#text=TODO\n"
        "alternativeForms: []\n"
        "exampleSentences:\n"
        "  - sentence: TODO\n"
        f"    translations:\n"
        f"      {reader_lang}: TODO translation\n"
        "    sourceUrl: https://example.com/source\n"
        "testData:\n"
        "  nonMatchingSentences:\n"
        "    - TODO non-matching sentence\n"
        "variant: 1\n"
    )


def build_markdown_stub(headword: str) -> str:
    return (
        f"# {headword}\n\n"
        "## Meaning\n"
        "Provide a concise explanation of the grammar point. "
        "You may include lower-level subheadings (###) and examples here.\n\n"
        "## Guides\n"
        "- [Resource title](https://example.com/guide) - Optional description\n\n"
        "## Q&A\n"
        "- [Example discussion](https://example.com/qna)\n\n"
        "## Related\n"
        "### Related Headword\n"
        "- [Explain the difference](https://example.com/related)\n"
    )


def write_file(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists (use --force to overwrite)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Created {path.relative_to(ROOT)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a grammar entry stub.")
    parser.add_argument("--headword", required=True, help="Headword for the grammar entry.")
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files if present.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    directory = ROOT / f"grammar-{args.target_lang}"
    yaml_path = directory / f"{args.headword}.yaml"
    md_path = directory / f"{args.headword}.{args.reader_lang}.md"

    try:
        write_file(yaml_path, build_yaml_stub(args.headword, args.target_lang, args.reader_lang), args.force)
        write_file(md_path, build_markdown_stub(args.headword), args.force)
    except FileExistsError as error:
        print(error)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
