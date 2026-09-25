"""Regression tests for observed retrieval risks; no external dependencies."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from search_law import article_text, choose_laws, file_articles, load_json
from audit_sources import audit as audit_sources
from new_matter import create_workspace
from search_cases import card_text, load_catalog as load_case_catalog


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

    def case_cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/search_cases.py"), *args],
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
            choose_laws("中华人民共和国税收征收管理法", self.catalog)

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

    def test_phase_two_last_articles(self):
        expectations = {
            ("civil-procedure-law", 305): "外国国家豁免",
            ("criminal-procedure-law", 308): "中国海警局",
            ("administrative-reconsideration-law", 90): "2024年1月1日起施行",
            ("company-law", 266): "2024年7月1日起施行",
            ("labor-contract-law", 98): "2008年1月1日起施行",
            ("arbitration-law", 96): "2026年3月1日起施行",
            ("civil-evidence-provisions", 100): "2020年5月1日起施行",
        }
        for (slug, number), phrase in expectations.items():
            with self.subTest(slug=slug):
                self.assertIn(phrase, self.get_article(slug, number))

    def test_new_authority_aliases(self):
        self.assertEqual(choose_laws("民诉法", self.catalog), {"civil-procedure-law"})
        self.assertEqual(choose_laws("民事证据规定", self.catalog), {"civil-evidence-provisions"})
        self.assertEqual(choose_laws("仲裁法", self.catalog), {"arbitration-law"})

    def test_source_manifest_offline_audit(self):
        self.assertEqual(audit_sources(), [])

    def test_matter_workspace_is_structured_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "matter"
            markdown, data = create_workspace(output, "测试案件")
            self.assertIn("要件—事实—证据矩阵", markdown.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(data.read_text(encoding="utf-8"))["title"], "测试案件")
            with self.assertRaises(SystemExit):
                create_workspace(output, "覆盖")

    def test_matter_workspace_refuses_git_repo_by_default(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "public-repo"
            (repo / ".git").mkdir(parents=True)
            with self.assertRaises(SystemExit):
                create_workspace(repo / "matter", "敏感案件")
            markdown, _ = create_workspace(repo / "matter", "明确允许", allow_git_repo=True)
            self.assertTrue(markdown.is_file())

    def test_keyword_alias_finds_electronic_service(self):
        result = self.cli("--law", "民事诉讼法", "--keyword", "电子送达", "--limit", "3")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("检索扩展", result.stdout)
        self.assertIn("第九十条", result.stdout)

    def test_case_catalog_and_domain_search(self):
        catalog = load_case_catalog()
        self.assertEqual(len(catalog), 12)
        result = self.case_cli("--domain", "劳动")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("GC179", result.stdout)
        self.assertIn("GC180", result.stdout)
        self.assertIn("GC184", result.stdout)

    def test_case_search_uses_decisive_facts(self):
        result = self.case_cli("--keyword", "事故认定书", "--keyword", "因果关系")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("GC269", result.stdout)
        self.assertIn("仅用于本地检索排序", result.stdout)

    def test_case_search_rejects_missing_or_unknown_query(self):
        self.assertNotEqual(self.case_cli().returncode, 0)
        self.assertNotEqual(self.case_cli("--id", "GC999999").returncode, 0)

    def test_case_path_cannot_escape_root(self):
        with self.assertRaises(ValueError):
            card_text("../outside.md")


if __name__ == "__main__":
    unittest.main()
