from pathlib import Path
import shutil
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import yaml

import build_db


class DatabasePublicationTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="manabi-db-publication-")).resolve()
        self.output = self.work / "dist"
        self.output.mkdir()
        self.database = self.output / "manabi-grammar.sqlite"
        self.patches = [
            patch.object(build_db, "DBROOT", self.work),
            patch.object(build_db, "OUTDIR", self.output),
            patch.object(build_db, "DBFILE", self.database),
            patch.object(Path, "home", return_value=self.work),
        ]
        for item in self.patches:
            item.start()
        self.addCleanup(self.clean_up)

    def clean_up(self):
        for item in reversed(self.patches):
            item.stop()
        trash = Path.home() / ".Trash"
        self.assertEqual(trash.resolve(), trash)
        trash.mkdir(exist_ok=True)
        shutil.move(str(self.work), str(trash / self.work.name))

    def test_failed_insert_preserves_previous_complete_snapshot(self):
        original = [("ja", "猫", 1, {"ruleID": "grammar.ja.cat"})]
        build_db.create_database(original)
        before = self.database.read_bytes()
        with self.assertRaises(sqlite3.IntegrityError):
            build_db.create_database(original + original)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(list(self.output.glob(".grammar-*.sqlite")), [])
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone(), ("ok",))
            self.assertEqual(connection.execute("SELECT headword FROM grammar").fetchall(), [("猫",)])

    def test_successful_replacement_publishes_new_rows_and_preserves_backup(self):
        build_db.create_database([("ja", "猫", 1, {})])
        before = self.database.read_bytes()
        build_db.create_database([("ja", "犬", 1, {})])
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT headword FROM grammar").fetchall(), [("犬",)])
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone(), ("delete",))
        backups = list((self.work / ".Trash").glob("manabi-grammar-*.sqlite"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), before)

    def test_output_symlink_is_rejected_without_changing_its_target(self):
        target = self.work / "unrelated.sqlite"
        target.write_bytes(b"preserve")
        self.database.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "Unexpected database output"):
            build_db.create_database([])
        self.assertEqual(target.read_bytes(), b"preserve")

    def test_backup_and_replacement_failures_preserve_previous_database(self):
        build_db.create_database([("ja", "猫", 1, {})])
        before = self.database.read_bytes()
        for fault in [patch.object(shutil, "copy2", side_effect=OSError("backup failed")),
                      patch.object(Path, "replace", side_effect=OSError("replace failed"))]:
            with fault, self.assertRaises(OSError):
                build_db.create_database([("ja", "犬", 1, {})])
            self.assertEqual(self.database.read_bytes(), before)
            self.assertEqual(list(self.output.glob(".grammar-*.sqlite")), [])

    def test_rule_ids_are_unique_and_payload_identity_matches_path(self):
        directory = self.work / "grammar-ja"
        directory.mkdir()
        record = {
            "ruleID": "grammar.ja.fixture", "ruleVersion": 1, "examples": [],
        }
        (directory / "猫.yaml").write_text(yaml.safe_dump(record), encoding="utf-8")
        self.assertEqual(build_db.collect_rows()[0][:3], ("ja", "猫", 1))
        second = directory / "犬.yaml"
        second.write_text(yaml.safe_dump(record), encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "duplicate ruleID"):
            build_db.collect_rows()
        record["ruleID"] = "grammar.ja.dog"
        record["headword"] = "鳥"
        second.write_text(yaml.safe_dump(record), encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "identity must match"):
            build_db.collect_rows()

    def test_stable_rule_lookup_is_indexed_and_duplicate_ids_cannot_publish(self):
        rows = [("ja", "猫", 1, {"ruleID": "grammar.ja.cat"})]
        build_db.create_database(rows)
        before = self.database.read_bytes()
        with sqlite3.connect(self.database) as connection:
            query = "SELECT headword FROM grammar WHERE json_extract(data, '$.ruleID') = ?"
            self.assertEqual(connection.execute(query, ("grammar.ja.cat",)).fetchall(), [("猫",)])
            plan = connection.execute("EXPLAIN QUERY PLAN " + query, ("grammar.ja.cat",)).fetchall()
            self.assertTrue(any("grammar_rule_id" in row[3] for row in plan))
        with self.assertRaises(sqlite3.IntegrityError):
            build_db.create_database(rows + [("ja", "犬", 1, {"ruleID": "grammar.ja.cat"})])
        self.assertEqual(self.database.read_bytes(), before)

    def test_multilingual_views_keep_one_grammar_identity_and_separate_actual_locales(self):
        data = {"ruleID": "grammar.ja.synthetic", "ruleVersion": 4,
            "info": {"en": {"Meaning": "Synthetic English explanation"}, "zh-Hant": {"Meaning": "合成說明"}, "ar": {"Meaning": "شرح تجريبي"}},
            "exampleSentences": [{"sentence": "猫が来る。", "translations": {"en": "Synthetic example", "pt-BR": "Exemplo sintético"}}],
            "referenceBindings": [{"ruleVersion": 4, "readerLanguage": "zh-Hant", "references": ["wiktionary:synthetic"]}]}
        build_db.create_database([("ja", "猫", 1, data)])
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM grammar").fetchone(), (1,))
            rows = connection.execute("SELECT contentLocale, sections FROM grammar_explanations WHERE ruleID = ? ORDER BY contentLocale", ("grammar.ja.synthetic",)).fetchall()
            self.assertEqual({locale: json.loads(sections) for locale, sections in rows}, data["info"])
            self.assertEqual(connection.execute("SELECT contentLocale, translation FROM grammar_example_translations ORDER BY contentLocale").fetchall(), [("en", "Synthetic example"), ("pt-BR", "Exemplo sintético")])
            self.assertEqual(connection.execute("SELECT explanationLocale, referenceID FROM grammar_reference_bindings").fetchall(), [("zh-Hant", "wiktionary:synthetic")])


if __name__ == "__main__":
    unittest.main()
