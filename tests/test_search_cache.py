"""Check cache freshness, fallback, and identical public retrieval semantics."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SearchCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'references').mkdir()
        for name in ('search_law.py', 'law_search_cache.py'):
            shutil.copyfile(ROOT / 'scripts' / name, self.root / 'scripts' / name)
        self.catalog = [{'name': '测试法', 'slug': 'test-law', 'aliases': ['测试'], 'version': '合成测试'}]
        self.index = [dict(law='测试法', lawSlug='test-law', article=1, articleSuffix=None,
                           articleCn='第一条', file='references/测试法.md', chapter='总则')]
        self.save('law-catalog.json', self.catalog)
        self.save('law-index.json', self.index)
        self.source = self.root / 'references/测试法.md'
        self.source.write_text('**第一条** 电子数据与电子方式送达；印章。ASCII "NEAR" %_。\n', encoding='utf-8')
        self.db = self.root / '.cache/law-search.sqlite3'

    def save(self, name, value):
        (self.root / 'references' / name).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def cli(self, *args):
        return subprocess.run([sys.executable, '-X', 'utf8', str(self.root / 'scripts/search_law.py'), *args],
                              capture_output=True, encoding='utf-8')

    def assert_same(self, *args):
        cached = self.cli(*args)
        direct = self.cli(*args, '--no-cache')
        self.assertEqual((cached.returncode, cached.stdout, cached.stderr),
                         (direct.returncode, direct.stdout, direct.stderr))
        return cached

    def test_exact_short_long_alias_and_literal_searches_match(self):
        self.assert_same('--law', '测试', '--article', '1')
        for word in ('印', '印章', '电子数据', '电子送达', '总则', '测试法', 'ascii', '"NEAR"', '%_', '缺失词'):
            with self.subTest(word=word):
                self.assert_same('--keyword', word)

    def test_source_edit_invalidates_even_if_size_and_mtime_restored(self):
        self.assert_same('--keyword', '电子数据')
        original = self.source.stat()
        self.source.write_text(self.source.read_text(encoding='utf-8').replace('电子数据', '新鲜资料'), encoding='utf-8')
        os.utime(self.source, ns=(original.st_atime_ns, original.st_mtime_ns))
        self.assertEqual(self.assert_same('--keyword', '电子数据').returncode, 1)
        self.assertIn('新鲜资料', self.assert_same('--keyword', '新鲜资料').stdout)

    def test_index_addition_and_catalog_version_refresh(self):
        self.assert_same('--law', '测试', '--article', '1')
        self.source.write_text('**第一条** 原条文\n**第一条之一** 增补条文\n', encoding='utf-8')
        self.index.append(dict(self.index[0], articleSuffix=1, articleCn='第一条之一'))
        self.save('law-index.json', self.index)
        self.catalog[0]['version'] = '修订测试'
        self.save('law-catalog.json', self.catalog)
        output = self.assert_same('--law', '测试', '--article', '1', '--suffix', '1').stdout
        self.assertIn('增补条文', output)
        self.assertIn('修订测试', output)
        self.assertNotIn('原条文', output)

    def test_corrupt_cache_is_rebuilt(self):
        self.assert_same('--keyword', '电子数据')
        self.db.write_bytes(b'not a database')
        self.assert_same('--keyword', '电子数据')

    def test_no_cache_does_not_create_cache(self):
        self.assertEqual(self.cli('--law', '测试', '--article', '1', '--no-cache').returncode, 0)
        self.assertFalse(self.db.exists())

    def test_cache_directory_unavailable_falls_back(self):
        (self.root / '.cache').write_text('blocks cache directory', encoding='utf-8')
        result = self.cli('--law', '测试', '--article', '1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('电子数据', result.stdout)
        self.assertIn('改用原文检索', result.stderr)

    def test_missing_source_never_returns_cached_text(self):
        self.assert_same('--law', '测试', '--article', '1')
        self.source.unlink()
        result = self.cli('--law', '测试', '--article', '1')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('电子数据', result.stdout)

    def test_without_fts_uses_same_substring_semantics(self):
        self.assert_same('--keyword', '电子数据')
        with sqlite3.connect(self.db) as connection:
            connection.execute('DROP TABLE IF EXISTS article_fts')
            connection.execute("UPDATE metadata SET value = 'false' WHERE key = 'fts'")
        connection.close()
        self.assert_same('--keyword', '电子数据')

    def test_order_and_limit_follow_index(self):
        self.source.write_text('**第一条** 第一条印章\n**第二条** 第二条印章\n', encoding='utf-8')
        self.index.insert(0, dict(self.index[0], article=2, articleCn='第二条'))
        self.save('law-index.json', self.index)
        output = self.assert_same('--keyword', '印章', '--limit', '1').stdout
        self.assertIn('第二条', output)
        self.assertNotIn('第一条', output)

    def test_packaging_omits_cache(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        from package_skill import source_files
        self.assert_same('--keyword', '印章')
        (self.root / 'SKILL.md').write_text('Synthetic cache fixture', encoding='utf-8')
        names = ['SKILL.md', 'release-files.json', 'scripts/search_law.py', 'scripts/law_search_cache.py',
                 'references/law-catalog.json', 'references/law-index.json', 'references/测试法.md']
        (self.root / 'release-files.json').write_text(json.dumps({'files': names}), encoding='utf-8')
        files = source_files(self.root)
        self.assertTrue(files)
        self.assertFalse(any('.cache' in path.parts for path in files))


if __name__ == '__main__':
    unittest.main()
