import copy
import unittest
from content import ROOT, YAML_SCHEMA, collect_rows, validate
from schema_contract import check_row_schema
import build_db

class PublicContentPrivacyTests(unittest.TestCase):
    def test_public_rows_and_schemas_are_content_only(self):
        check_row_schema()
        rows = collect_rows()
        self.assertEqual(len(rows), 646)
        for _, _, _, data in rows:
            self.assertTrue(data["info"])
            self.assertFalse({"pattern", "compiledPattern", "authoringPattern", "analysisStatus", "analysisSuppression", "testData"} & data.keys())
        for name in ("compile_rules.py", "source_rules.py", "rule_readiness.py"):
            self.assertFalse((ROOT / "scripts" / name).exists())
        self.assertFalse((ROOT / "source-rules").exists())

    def test_authoring_and_database_boundary_reject_matching_fields(self):
        base = {"ruleID": "grammar.ja.fixture", "ruleVersion": 1, "examples": []}
        validate(base, YAML_SCHEMA, "fixture")
        for field in ("pattern", "compiledPattern", "authoringPattern", "analysisStatus", "analysisSuppression", "testData"):
            data = {**base, field: {}}
            with self.subTest(field=field), self.assertRaises(ValueError): validate(data, YAML_SCHEMA, "fixture")
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "private matching fields"):
                build_db.create_database([("ja", "fixture", 1, data)])
