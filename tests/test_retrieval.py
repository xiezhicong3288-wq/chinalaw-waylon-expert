"""Regression tests for observed retrieval risks; no external dependencies."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from search_law import article_text, choose_laws, file_articles, load_json


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = load_json("law-index.json")
        cls.catalog = load_json("law-catalog.json")

    def get_article(self, slug, number, suffix=None):
        item = next(x for x in self.index if x["lawSlug"] == slug and x["article"] == number and x["articleSuffix"] == suffix)
        return article_text(item["file"], item["articleCn"])

    def cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/search_law.py"), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def test_exact_civil_article(self):
        self.assertEqual(self.get_article("civil-code", 577),
                         "当事人一方不履行合同义务或者履行合同义务不符合约定的，应当承担继续履行、采取补救措施或者赔偿损失等违约责任。")

    def test_inserted_article_separate_from_base(self):
        ordinary = self.get_article("criminal-law", 133)
        inserted = self.get_article("criminal-law", 133, 1)
        self.assertNotEqual(ordinary, inserted)
        self.assertIn("追逐竞驶", inserted)
        self.assertNotIn("追逐竞驶", ordinary)

    def test_chapter_boundary_is_not_article_content(self):
        self.assertNotIn("附 则", self.get_article("criminal-law", 451))
        last = self.get_article("criminal-law", 452)
        self.assertIn("列于本法附件一", last)
        self.assertIn("列于本法附件二", last)

    def test_criminal_2024_amendment_retrievable(self):
        body = self.get_article("criminal-law", 390)
        self.assertIn("处三年以下有期徒刑或者拘役", body)
        self.assertIn("（七）将违法所得用于行贿的。", body)
        self.assertIn("可以减轻或者免除处罚", body)

    def test_competition_effective_date(self):
        self.assertEqual(self.get_article("anti-unfair-competition-law", 41),
                         "本法自2025年10月15日起施行。")

    def test_missing_law_is_rejected(self):
        self.assertNotEqual(self.cli("--article", "39").returncode, 0)

    def test_ambiguous_law_is_rejected(self):
        self.assertNotEqual(self.cli("--law", "行政", "--article", "39").returncode, 0)

    def test_unknown_law_does_not_silently_match(self):
        with self.assertRaises(SystemExit):
            choose_laws("中华人民共和国劳动合同法", self.catalog)

    def test_exact_alias(self):
        self.assertEqual(choose_laws("消保法", self.catalog), {"consumer-rights-law"})

    def test_invalid_queries_fail(self):
        for args in [("--law", "刑法", "--article", "0"),
                     ("--law", "刑法", "--article", "9999"),
                     ("--keyword", " "), ("--keyword", "证据", "--limit", "0"),
                     ("--keyword", "证据", "--suffix", "1")]:
            with self.subTest(args=args):
                self.assertNotEqual(self.cli(*args).returncode, 0)

    def test_keyword_scoping(self):
        result = self.cli("--law", "社会保险法", "--keyword", "骗取", "--limit", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("第八十七条", result.stdout)
        self.assertIn("第八十八条", result.stdout)
        self.assertNotIn("中华人民共和国刑法", result.stdout)

    def test_no_query_must_fail(self):
        self.assertNotEqual(self.cli().returncode, 0)

    def test_file_path_cannot_escape_root(self):
        with self.assertRaises(ValueError):
            file_articles("../not-in-skill.md")


if __name__ == "__main__":
    unittest.main()
