#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path
import shutil

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from validate_repo import ROOT as DBROOT, parse_markdown_sections

SCHEMAS = DBROOT / "schemas"
ROW_SCHEMA = json.loads((SCHEMAS / "grammar-table-row.schema.json").read_text(encoding="utf-8"))
ROW_VALIDATOR = Draft202012Validator(ROW_SCHEMA, format_checker=FormatChecker())

OUTDIR = DBROOT / "dist"
OUTDIR.mkdir(exist_ok=True)
DBFILE = OUTDIR / "manabi-grammar.sqlite"
JS_CLIENT_ZIP = DBROOT / "js-client" / "dist" / "js-client" / "manabi-grammar-db-client.zip"

LANG_DIR_RE = re.compile(r"^grammar-([a-z]{2,3})$")
LANG_FILE_RE = re.compile(r"^(?P<head>.+?)\.(?P<lang>[a-z]{2,3})\.md$")


def _rename_key(mapping: dict, old: str, new: str) -> None:
    if old in mapping:
        if new in mapping and mapping[new] != mapping[old]:
            raise ValueError(f"Conflicting keys '{old}' and '{new}' encountered.")
        mapping[new] = mapping.pop(old)


def _normalize_yaml_record(data: dict) -> dict:
    record = dict(data)
    _rename_key(record, "jmdict_id", "jmdictId")
    _rename_key(record, "alternative_forms", "alternativeForms")
    _rename_key(record, "example_sentences", "exampleSentences")
    _rename_key(record, "test_data", "testData")
    _rename_key(record, "level_label", "levelLabel")

    example_sentences = record.get("exampleSentences")
    if isinstance(example_sentences, list):
        normalized_sentences: list[dict] = []
        for item in example_sentences:
            if not isinstance(item, dict):
                continue
            normalized = dict(item)
            _rename_key(normalized, "source_url", "sourceUrl")
            normalized_sentences.append(normalized)
        record["exampleSentences"] = normalized_sentences

    test_data = record.get("testData")
    if isinstance(test_data, dict):
        normalized_test = dict(test_data)
        _rename_key(normalized_test, "non_matching_sentences", "nonMatchingSentences")
        record["testData"] = normalized_test

    return record


def _coerce_variant(value: object, yaml_file: Path) -> int:
    if value is None:
        return 1
    if isinstance(value, bool):
        raise ValueError(f"{yaml_file}: variant cannot be a boolean")
    if isinstance(value, int):
        if value < 1:
            raise ValueError(f"{yaml_file}: variant must be >= 1")
        return value
    if isinstance(value, str) and value.isdigit():
        parsed = int(value, 10)
        if parsed < 1:
            raise ValueError(f"{yaml_file}: variant must be >= 1")
        return parsed
    raise ValueError(f"{yaml_file}: variant must be a positive integer")


def collect_rows() -> list[tuple[str, str, int, dict]]:
    rows: list[tuple[str, str, int, dict]] = []
    seen: set[tuple[str, str, int]] = set()
    for directory in sorted(DBROOT.iterdir()):
        if not directory.is_dir() or not directory.name.startswith("grammar-"):
            continue

        match = LANG_DIR_RE.match(directory.name)
        if not match:
            continue

        target_language = match.group(1)

        markdown_map: dict[str, dict[str, object]] = {}
        for md_file in directory.glob("*.md"):
            md_match = LANG_FILE_RE.match(md_file.name)
            if not md_match:
                continue
            headword = md_match.group("head")
            reader_lang = md_match.group("lang")
            sections = parse_markdown_sections(md_file.read_text(encoding="utf-8"))
            markdown_map.setdefault(headword, {})[reader_lang] = sections

        for yaml_file in sorted(directory.glob("*.yaml")):
            headword = yaml_file.stem
            yaml_data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            if not isinstance(yaml_data, dict):
                raise SystemExit(f"{yaml_file}: YAML root must be a mapping/object.")
            yaml_data = _normalize_yaml_record(yaml_data)
            try:
                variant = _coerce_variant(yaml_data.get("variant"), yaml_file)
            except ValueError as error:
                raise SystemExit(str(error)) from error
            yaml_data.setdefault("variant", variant)
            info = markdown_map.get(headword, {})
            record = dict(yaml_data)
            record.setdefault("targetLanguage", target_language)
            record.setdefault("headword", headword)
            record["info"] = info
            ROW_VALIDATOR.validate(record)
            key = (target_language, headword, variant)
            if key in seen:
                raise SystemExit(
                    f"Duplicate grammar entry detected for {target_language}/{headword} "
                    f"variant {variant} in '{yaml_file}'."
                )
            seen.add(key)
            rows.append((target_language, headword, variant, record))
    return rows


def create_database(rows: list[tuple[str, str, int, dict]]) -> None:
    if DBFILE.exists():
        DBFILE.unlink()

    connection = sqlite3.connect(DBFILE)
    try:
        connection.execute("PRAGMA journal_mode=WAL;")
        connection.execute("PRAGMA synchronous=NORMAL;")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS grammar (
              targetLanguage TEXT NOT NULL,
              headword        TEXT NOT NULL,
              variant         INTEGER NOT NULL DEFAULT 1,
              data            TEXT NOT NULL,
              CHECK (variant >= 1),
              PRIMARY KEY (targetLanguage, headword, variant)
            ) STRICT, WITHOUT ROWID;
            """
        )
        connection.executemany(
            "INSERT INTO grammar(targetLanguage, headword, variant, data) VALUES (?, ?, ?, ?)",
            [
                (target, head, variant, json.dumps(data, ensure_ascii=False))
                for target, head, variant, data in rows
            ],
        )
        connection.commit()
    finally:
        connection.close()


def copy_schemas() -> None:
    for schema_name in ("grammar-table-row.schema.json", "grammar-yaml.schema.json"):
        source = SCHEMAS / schema_name
        target = OUTDIR / schema_name
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def copy_js_client_bundle() -> None:
    if not JS_CLIENT_ZIP.exists():
        raise SystemExit(
            "JS client bundle was not found. Ensure 'mise run client-build' has completed successfully."
        )
    target = OUTDIR / "manabi-grammar-db-client.zip"
    shutil.copy2(JS_CLIENT_ZIP, target)


def main() -> int:
    rows = collect_rows()
    create_database(rows)
    copy_schemas()
    copy_js_client_bundle()
    print(f"Wrote {DBFILE} with {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
