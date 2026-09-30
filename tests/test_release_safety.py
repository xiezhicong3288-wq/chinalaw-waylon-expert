import hashlib
import json
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_sources
from audit_verification import audit_verification
from release_guard import approved_files, check, tree_hash, inventory
from package_skill import build_package, verify_package


def manifest(root, names):
    (root / 'release-files.json').write_text(json.dumps({'files': ['release-files.json', *names]}), encoding='utf-8')


class ReleaseSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'skill'
        self.root.mkdir()
        (self.root / 'SKILL.md').write_text('Public generic instructions', encoding='utf-8')
        manifest(self.root, ['SKILL.md'])
        self.output = Path(self.temp.name) / 'out.zip'

    def test_unlisted_files_block_before_output(self):
        for name in ('.env', 'outputs/internal.txt', 'notes/instructions.md'):
            with self.subTest(name=name):
                path = self.root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('synthetic', encoding='utf-8')
                with self.assertRaises(SystemExit):
                    build_package(self.root, self.output)
                self.assertFalse(self.output.exists())
                path.unlink()

    def test_sensitive_path_cannot_be_whitelisted(self):
        (self.root / '.env').write_text('synthetic', encoding='utf-8')
        manifest(self.root, ['SKILL.md', '.env'])
        with self.assertRaises(ValueError):
            check(self.root)

    def test_path_aliases_and_collisions_rejected(self):
        for bad in ('../secret', '/absolute', 'a\\b', 'a/./b', 'a:b', 'skill.md'):
            manifest(self.root, ['SKILL.md', bad])
            with self.assertRaises(ValueError):
                approved_files(self.root)

    def test_sensitive_text_in_approved_file_is_blocked(self):
        samples = ['C:' + '\\Users\\' + 'example\\private',
                   'person' + '@' + 'example.com', 'gh' + 'p_' + 'X' * 25,
                   '-----BEGIN ' + 'PRIVATE KEY-----']
        for body in samples:
            (self.root / 'SKILL.md').write_text(body, encoding='utf-8')
            with self.assertRaises(ValueError):
                check(self.root)

    def test_same_filename_changed_zip_body_rejected(self):
        build_package(self.root, self.output)
        with zipfile.ZipFile(self.output) as archive:
            entries = [(info, archive.read(info)) for info in archive.infolist()]
        with zipfile.ZipFile(self.output, 'w') as archive:
            for info, body in entries:
                archive.writestr(info, b'changed' if info.filename.endswith('SKILL.md') else body)
        with self.assertRaises(SystemExit):
            verify_package(self.root, self.output)

    def test_failed_verification_preserves_previous_output(self):
        self.output.write_bytes(b'previous reviewed output')
        with patch('package_skill.verify_package', side_effect=SystemExit('reject')):
            with self.assertRaises(SystemExit):
                build_package(self.root, self.output)
        self.assertEqual(self.output.read_bytes(), b'previous reviewed output')
        self.assertFalse(list(self.output.parent.glob('.package-*')))

    def test_zip_type_tampering_is_rejected(self):
        for kind in (stat.S_IFLNK, stat.S_IFDIR):
            build_package(self.root, self.output)
            with zipfile.ZipFile(self.output) as archive:
                entries = [(info, archive.read(info)) for info in archive.infolist()]
            with zipfile.ZipFile(self.output, 'w') as archive:
                for info, body in entries:
                    if info.filename.endswith('SKILL.md'):
                        info.external_attr = (kind | 0o777) << 16
                    archive.writestr(info, body)
            with self.assertRaises(SystemExit):
                verify_package(self.root, self.output)

    def test_chinese_names_and_content_roundtrip(self):
        (self.root / '法源.md').write_text('通用来源', encoding='utf-8')
        manifest(self.root, ['SKILL.md', '法源.md'])
        build_package(self.root, self.output)
        verify_package(self.root, self.output)

    def test_state_hash_detects_body_change(self):
        before = tree_hash(inventory(self.root))
        (self.root / 'SKILL.md').write_text('Changed', encoding='utf-8')
        self.assertNotEqual(before, tree_hash(inventory(self.root)))

    def test_state_report_must_be_outside_input(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/release_state.py'
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(script), '--candidate', str(self.root),
                                 '--installed', str(self.root), '--output', str(self.root / 'report.json')], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / 'report.json').exists())


class SourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'references').mkdir()
        self.raw = self.root / 'raw'
        self.raw.mkdir()
        (self.raw / 'source.html').write_bytes(b'original official download')
        self.row = {'law': 'Synthetic law', 'file': 'source.html', 'url': 'https://www.gov.cn/test',
                    'organization': 'Synthetic authority', 'sha256': hashlib.sha256(b'original official download').hexdigest(),
                    'downloadedAt': '2024-02-29'}

    def audit(self, raw=True):
        (self.root / 'references/source-manifest.json').write_text(json.dumps([self.row]), encoding='utf-8')
        with patch.object(audit_sources, 'ROOT', self.root):
            return audit_sources.inspect(snapshot_root=self.raw if raw else None)

    def test_real_snapshot_matches(self):
        self.assertEqual(self.audit(), ([], []))

    def test_empty_manifest_cannot_claim_success(self):
        (self.root / 'references/source-manifest.json').write_text('[]', encoding='utf-8')
        with patch.object(audit_sources, 'ROOT', self.root):
            self.assertTrue(audit_sources.inspect()[0])

    def test_unread_snapshot_not_verified(self):
        errors, gaps = self.audit(raw=False)
        self.assertFalse(errors)
        self.assertTrue(gaps)

    def test_impossible_date_rejected(self):
        self.row['downloadedAt'] = '2025-02-29'
        self.assertTrue(self.audit()[0])

    def test_malformed_urls_report_instead_of_crashing(self):
        for url in ('not-a-url', 'https://[bad', 'https://www.gov.cn:wrong', 'https://www.gov.cn.evil.test/page'):
            self.row['url'] = url
            self.assertTrue(self.audit()[0])

    def test_snapshot_hash_mismatch(self):
        (self.raw / 'source.html').write_bytes(b'changed')
        self.assertTrue(self.audit()[0])

    def test_missing_or_outside_snapshot_rejected(self):
        for file in ('absent.html', '../outside.html'):
            self.row['file'] = file
            self.assertTrue(self.audit()[0])

    def test_normalized_hash_is_separate(self):
        (self.root / 'text.md').write_bytes(b'normalized text')
        self.row.update(textFile='text.md', textSha256=hashlib.sha256(b'normalized text').hexdigest())
        self.assertEqual(self.audit(), ([], []))
        self.row['textSha256'] = self.row['sha256']
        self.assertTrue(self.audit()[0])

    def test_checked_verification_requires_read_scope(self):
        value = {'status': 'checked', 'verifiedAt': '2024-02-29', 'url': 'https://www.gov.cn/test',
                 'readScope': 'Article 2', 'version': '2024', 'effectiveFrom': '2024-01-01', 'applicability': 'Synthetic reason'}
        self.assertEqual(audit_verification([{'verification': value}]), ([], []))
        value['readScope'] = '待核'
        self.assertTrue(audit_verification([{'verification': value}])[1])

    def test_legacy_verification_not_silently_promoted(self):
        self.assertEqual(audit_verification([{'id': 'L01'}]), ([], []))
        self.assertTrue(audit_verification([{'verification': {'status': 'snapshot'}}])[1])

    def test_verification_bad_types_and_date(self):
        for value in ([], {'status': []}, {'status': 'checked', 'verifiedAt': '2025-99-99', 'url': []}):
            self.assertTrue(audit_verification([{'verification': value}])[0])


if __name__ == '__main__':
    unittest.main()
