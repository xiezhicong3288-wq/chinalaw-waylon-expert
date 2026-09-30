import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_reasoning import audit_reasoning
from audit_matter import audit
from new_matter import create_workspace


def fixture():
    return {"issues": [{"id": "I01"}], "facts": [{"id": "F01"}],
            "evidence": [{"id": "E01"}, {"id": "E02"}], "authorities": [{"id": "L01"}],
            "reasoning": [{"id": "R01", "issueId": "I01", "kind": "mixed",
                "factIds": ["F01"], "evidenceIds": ["E01"], "opposingEvidenceIds": ["E02"],
                "authorityIds": ["L01"], "burdenOn": "待核", "standard": "待核",
                "conclusionStatus": "conditional", "conclusion": "条件结论"}]}


class ReasoningAuditTests(unittest.TestCase):
    def test_legacy_file_is_compatible(self):
        self.assertEqual(audit_reasoning({}), ([], []))

    def test_valid_graph(self):
        self.assertEqual(audit_reasoning(fixture()), ([], []))

    def test_supported_with_unchecked_burden_is_gap(self):
        data = fixture()
        data['reasoning'][0]['conclusionStatus'] = 'supported'
        errors, gaps = audit_reasoning(data)
        self.assertFalse(errors)
        self.assertTrue(gaps)

    def test_workspace_audit_reports_dangling_reasoning(self):
        with tempfile.TemporaryDirectory() as directory:
            create_workspace(Path(directory), "合成关联测试", allow_git_repo=True)
            data = json.loads((Path(directory) / "matter.json").read_text(encoding="utf-8"))
            self.assertIn("reasoning", data)
            data.update(fixture())
            data["reasoning"][0]["evidenceIds"] = ["E99"]
            errors, _ = audit(data)
            self.assertTrue(any("evidenceIds引用E99无法唯一定位" in error for error in errors))

    def test_dangling_references_including_opposing_evidence(self):
        for key in ("factIds", "evidenceIds", "opposingEvidenceIds", "authorityIds"):
            with self.subTest(key=key):
                data = fixture(); data["reasoning"][0][key] = ["absent"]
                errors, _ = audit_reasoning(data)
                self.assertTrue(any(key in e and "absent" in e for e in errors))

    def test_ambiguous_authority_is_rejected(self):
        data = fixture(); data["authorities"].append({"id": "L01"})
        self.assertTrue(audit_reasoning(data)[0])

    def test_unknown_issue_is_rejected(self):
        data = fixture(); data["reasoning"][0]["issueId"] = "I99"
        self.assertTrue(audit_reasoning(data)[0])

    def test_bad_reference_types_do_not_crash(self):
        for value in (None, "E01", [{"id": "E01"}], [1], [[]]):
            data = fixture(); data["reasoning"][0]["evidenceIds"] = value
            self.assertTrue(audit_reasoning(data)[0])

    def test_supported_fact_without_evidence_is_gap(self):
        data = fixture(); row = data["reasoning"][0]
        row.update(conclusionStatus="supported", evidenceIds=[])
        errors, gaps = audit_reasoning(data)
        self.assertFalse(errors); self.assertTrue(gaps)

    def test_pure_law_needs_no_factual_evidence(self):
        data = fixture(); row = data["reasoning"][0]
        row.update(kind="law", conclusionStatus="supported", factIds=[], evidenceIds=[], opposingEvidenceIds=[])
        self.assertEqual(audit_reasoning(data), ([], []))

    def test_missing_authority_is_gap_not_merits_verdict(self):
        data = fixture(); data["reasoning"][0]["authorityIds"] = []
        errors, gaps = audit_reasoning(data)
        self.assertFalse(errors); self.assertTrue(gaps)

    def test_duplicate_records_and_references(self):
        data = fixture(); data["reasoning"].append(copy.deepcopy(data["reasoning"][0]))
        data["reasoning"][0]["evidenceIds"] = ["E01", "E01"]
        self.assertGreaterEqual(len(audit_reasoning(data)[0]), 2)

    def test_non_object_rows_and_fields(self):
        for value in (None, "text", [None], [[]], [{"id": []}]):
            data = fixture(); data["reasoning"] = value
            self.assertTrue(audit_reasoning(data)[0])


if __name__ == "__main__":
    unittest.main()
