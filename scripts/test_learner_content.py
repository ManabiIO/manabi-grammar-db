import unittest

from content import collect_rows, parse_markdown_sections
from create_stub_entry import build_markdown_stub


class LearnerContentTests(unittest.TestCase):
    def test_reference_backed_scaffold_has_no_fake_meaning_or_published_todo(self):
        text = build_markdown_stub("猫")
        self.assertEqual(text, "# 猫\n")
        self.assertEqual(parse_markdown_sections(text, "猫"), {})

    def test_reserved_private_headings_and_visible_implementation_prose_fail(self):
        for body in [
            "### Matching scope\nReviewed forms.",
            "### Recognized parts\nObserved ending.",
            "The current detector supports this form.",
            "The **matcher** returns a context component.",
            "This matcher checks the MeCab lemma.",
            "Confidence remains unassessed.",
            "Form evidence is tentative.",
            "Its JMdict identity supplies attachment evidence.",
        ]:
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, "private matching notes"):
                parse_markdown_sections(f"# 猫\n## Meaning\n{body}\n", "猫")

    def test_genuine_usage_and_literal_fenced_examples_remain_lossless(self):
        meaning = "A detector is called 検出器. Context distinguishes a question from a statement.\n\n```md\n### Matching scope\nThis matcher uses MeCab.\n```"
        self.assertEqual(parse_markdown_sections(f"# 猫\n## Meaning\n{meaning}\n", "猫"), {"Meaning": meaning})

    def test_all_public_rows_keep_their_identities_locales_and_real_explanations(self):
        rows = collect_rows()
        self.assertEqual(len(rows), 646)
        self.assertTrue(all("en" in data["info"] for _, _, _, data in rows))
        by_rule = {data["ruleID"]: data for _, _, _, data in rows}
        self.assertNotIn("Meaning", by_rule["grammar.ja.source.takoboto.1667"]["info"]["en"])
        self.assertIn("as if", by_rule["grammar.ja.source.takoboto.1316"]["info"]["en"]["Meaning"])
        self.assertIn("Guides", by_rule["grammar.ja.ga.subject"]["info"]["en"])
