#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from validate_repo import ROOT as DBROOT, parse_markdown_sections

SCHEMAS = DBROOT / "schemas"
ROW_SCHEMA = json.loads((SCHEMAS / "grammar-table-row.schema.json").read_text(encoding="utf-8"))
ROW_VALIDATOR = Draft202012Validator(ROW_SCHEMA, format_checker=FormatChecker())

OUTDIR = DBROOT / "dist"
OUTDIR.mkdir(exist_ok=True)
DBFILE = OUTDIR / "manabi-grammar.sqlite"

LANG_DIR_RE = re.compile(r"^grammar-([a-z]{2,3})$")
LANG_FILE_RE = re.compile(r"^(?P<head>.+?)\.(?P<lang>[a-z]{2,3})\.md$")
ALIAS = {"jp": "ja"}


def collect_rows() -> list[tuple[str, str, dict]]:
    rows: list[tuple[str, str, dict]] = []
    for directory in sorted(DBROOT.iterdir()):
        if not directory.is_dir() or not directory.name.startswith("grammar-"):
            continue

        match = LANG_DIR_RE.match(directory.name)
        if not match:
            continue

        target_language = ALIAS.get(match.group(1), match.group(1))

        markdown_map: dict[str, dict[str, object]] = {}
        for md_file in directory.glob("*.md"):
            md_match = LANG_FILE_RE.match(md_file.name)
            if not md_match:
                continue
            headword = md_match.group("head")
            reader_lang = md_match.group("lang")
            sections = parse_markdown_sections(md_file.read_text(encoding="utf-8"))
            markdown_map.setdefault(headword, {})[reader_lang] = sections

        for yaml_file in directory.glob("*.yaml"):
            headword = yaml_file.stem
            yaml_data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            info = markdown_map.get(headword, {})
            record = dict(yaml_data)
            record["info"] = info
            ROW_VALIDATOR.validate(record)
            rows.append((target_language, headword, record))
    return rows


def create_database(rows: list[tuple[str, str, dict]]) -> None:
    if DBFILE.exists():
        DBFILE.unlink()

    connection = sqlite3.connect(DBFILE)
    try:
        connection.execute("PRAGMA journal_mode=WAL;")
        connection.execute("PRAGMA synchronous=NORMAL;")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS grammar (
              target_language TEXT NOT NULL,
              headword        TEXT NOT NULL,
              data            TEXT NOT NULL,
              PRIMARY KEY (target_language, headword)
            ) STRICT, WITHOUT ROWID;
            """
        )
        connection.executemany(
            "INSERT INTO grammar(target_language, headword, data) VALUES (?, ?, ?)",
            [
                (target, head, json.dumps(data, ensure_ascii=False))
                for target, head, data in rows
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


def main() -> int:
    rows = collect_rows()
    create_database(rows)
    copy_schemas()
    print(f"Wrote {DBFILE} with {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
