#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
import shutil
import tempfile
import uuid

from content import ROOT as DBROOT, collect_rows as load_rows
from schema_contract import check_row_schema

SCHEMAS = DBROOT / "schemas"

OUTDIR = DBROOT / "dist"
DBFILE = OUTDIR / "manabi-grammar.sqlite"
JS_CLIENT_ZIP = DBROOT / "js-client" / "dist" / "js-client" / "manabi-grammar-db-client.zip"

def collect_rows() -> list[tuple[str, str, int, dict]]:
    check_row_schema()
    try:
        return load_rows(DBROOT)
    except ValueError as error:
        raise SystemExit(str(error)) from error


def create_database(rows: list[tuple[str, str, int, dict]]) -> None:
    for _, _, _, data in rows:
        if {"pattern", "compiledPattern", "authoringPattern", "analysisStatus", "analysisSuppression", "testData"} & data.keys():
            raise ValueError("Public content database cannot contain private matching fields")
    if OUTDIR.resolve() != OUTDIR or (DBFILE.exists() and DBFILE.resolve() != DBFILE):
        raise ValueError(f"Unexpected database output target: {DBFILE}")
    OUTDIR.mkdir(exist_ok=True)
    trash = Path.home() / ".Trash"
    if trash.resolve() != trash:
        raise ValueError(f"Unexpected Trash target: {trash}")
    trash.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".grammar-", suffix=".sqlite", dir=OUTDIR, delete=False) as temporary:
        staged = Path(temporary.name)
    connection = None
    built = False
    try:
        connection = sqlite3.connect(staged)
        # Distribute a complete single-file snapshot that sqlite3_deserialize can read.
        connection.execute("PRAGMA journal_mode=DELETE;")
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
        connection.execute("CREATE UNIQUE INDEX grammar_rule_id ON grammar(json_extract(data, '$.ruleID'))")
        # Additive, normalized read surfaces; legacy JSON/Swift clients still
        # read exactly the same grammar table. No duplicated authored bodies.
        connection.execute("""CREATE VIEW grammar_explanations AS
            SELECT g.targetLanguage, g.headword, g.variant,
                   json_extract(g.data, '$.ruleID') AS ruleID,
                   json_extract(g.data, '$.ruleVersion') AS ruleVersion,
                   explanation.key AS contentLocale, explanation.value AS sections
            FROM grammar AS g, json_each(g.data, '$.info') AS explanation""")
        connection.execute("""CREATE VIEW grammar_example_translations AS
            SELECT g.targetLanguage, g.headword, g.variant,
                   json_extract(g.data, '$.ruleID') AS ruleID,
                   CAST(example.key AS INTEGER) AS exampleIndex,
                   json_extract(example.value, '$.sentence') AS sentence,
                   translation.key AS contentLocale, translation.value AS translation
            FROM grammar AS g, json_each(g.data, '$.exampleSentences') AS example,
                 json_each(example.value, '$.translations') AS translation""")
        connection.execute("""CREATE VIEW grammar_reference_bindings AS
            SELECT g.targetLanguage, g.headword, g.variant,
                   json_extract(g.data, '$.ruleID') AS ruleID,
                   json_extract(binding.value, '$.ruleVersion') AS ruleVersion,
                   json_extract(binding.value, '$.readerLanguage') AS explanationLocale,
                   reference.value AS referenceID
            FROM grammar AS g, json_each(g.data, '$.referenceBindings') AS binding,
                 json_each(binding.value, '$.references') AS reference""")
        connection.commit()
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Generated grammar database failed integrity validation")
        built = True
    finally:
        if connection is not None:
            connection.close()
        if not built:
            shutil.move(str(staged), str(trash / f"manabi-failed-grammar-{uuid.uuid4()}.sqlite"))

    # Publication is a single atomic replacement. A failed build or backup leaves
    # the prior snapshot available, rather than exposing an incomplete database.
    try:
        if DBFILE.exists():
            shutil.copy2(DBFILE, trash / f"manabi-grammar-{uuid.uuid4()}.sqlite")
        staged.replace(DBFILE)
    finally:
        if staged.exists():
            shutil.move(str(staged), str(trash / f"manabi-failed-grammar-{uuid.uuid4()}.sqlite"))


def copy_schemas() -> None:
    for schema_name in ("grammar-table-row.schema.json", "grammar-yaml.schema.json", "reference-registry.schema.json"):
        source = SCHEMAS / schema_name
        target = OUTDIR / schema_name
        if target.resolve() != target:
            raise ValueError(f"Unexpected schema output target: {target}")
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def copy_js_client_bundle() -> None:
    if not JS_CLIENT_ZIP.exists():
        raise SystemExit(
            "JS client bundle was not found. Ensure 'mise run client-build' has completed successfully."
        )
    target = OUTDIR / "manabi-grammar-db-client.zip"
    if target.resolve() != target:
        raise ValueError(f"Unexpected client output target: {target}")
    shutil.copy2(JS_CLIENT_ZIP, target)


def main() -> int:
    if not JS_CLIENT_ZIP.is_file():
        raise SystemExit("JS client bundle missing. Run 'mise run client-build' before rebuilding the database.")
    rows = collect_rows()
    create_database(rows)
    copy_schemas()
    copy_js_client_bundle()
    registry = DBROOT / "references/registry.json"
    registry_target = OUTDIR / "reference-registry.json"
    if registry_target.resolve() != registry_target:
        raise ValueError(f"Unexpected registry output target: {registry_target}")
    shutil.copy2(registry, registry_target)
    print(f"Wrote {DBFILE} with {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
