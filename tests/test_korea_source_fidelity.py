"""Korea archival fidelity gate: offline original HWPX-byte source replay."""
import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scraper.sources.kr_policy_briefing import hwpx_text
from scripts import audit_korea_source_fidelity as audit

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "tests/fixtures/indonesia_korea/korea-document-1.bin"


class KoreaSourceFidelityTests(unittest.TestCase):
    def make_record(self, root):
        state = root / "state"
        capture_dir = state / "captures"
        capture_dir.mkdir(parents=True)
        document = DOC.read_bytes()
        original = hwpx_text(document)
        html = b"<html><body>government portal release</body></html>"
        doc_digest = hashlib.sha256(document).hexdigest()
        html_digest = hashlib.sha256(html).hexdigest()
        (capture_dir / (doc_digest + ".bin")).write_bytes(document)
        (capture_dir / (html_digest + ".bin")).write_bytes(html)
        record = {
            "source_identity": "korea-policy:156784297",
            "source_slug": "kr_policy_mnd_releases",
            "url": "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784297",
            "title_original": "국방부 공식 보도자료",
            "text_original": original,
            "published_date": "2026-10-06",
            "language_tag": "ko",
            "content_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "capture_sha256": html_digest,
            "metadata": {
                "issuer": "국방부", "publisher": "대한민국 정책브리핑",
                "publication_kind": "syndicated_press_release",
                "body_scope": "published_hwpx_text",
                "attachments_collected": True,
                "document_url": "https://www.korea.kr/common/download.do?fileId=198565537&tblKey=GMN",
                "document_capture_sha256": doc_digest,
            },
        }
        return state, record

    def test_exact_original_hwpx_reextracts_and_matches_record(self):
        with tempfile.TemporaryDirectory() as root:
            state, record = self.make_record(Path(root))
            report = audit.source_compare(record, state)
            self.assertEqual(report["machine_fidelity"], "PASS", report["findings"])
            self.assertGreater(report["extracted_characters"], 0)
            self.assertEqual(report["original_language"], "ko")
            self.assertEqual(report["publisher"], "대한민국 정책브리핑")
            self.assertNotIn("text_original", report)
            self.assertNotIn(record["text_original"], json.dumps(report, ensure_ascii=False))

    def test_hash_consistent_forged_text_is_still_detected(self):
        with tempfile.TemporaryDirectory() as root:
            state, record = self.make_record(Path(root))
            record["text_original"] = "가짜 문장"
            record["content_sha256"] = hashlib.sha256(record["text_original"].encode()).hexdigest()
            out = audit.source_compare(record, state)
            self.assertEqual(out["machine_fidelity"], "FAIL")
            self.assertTrue(any("HWPX re-extracted" in s for s in out["findings"]))

    def test_reject_changed_original_document_even_when_stored_body_is_valid(self):
        with tempfile.TemporaryDirectory() as root:
            state, record = self.make_record(Path(root))
            doc_sha = record["metadata"]["document_capture_sha256"]
            (state / "captures" / (doc_sha + ".bin")).write_bytes(b"tampered")
            result = audit.source_compare(record, state)
            self.assertEqual(result["machine_fidelity"], "FAIL")
            self.assertTrue(any("bytes fail SHA-256" in x for x in result["findings"]))

    def test_refuse_different_issuer_document_host_and_identity(self):
        with tempfile.TemporaryDirectory() as root:
            state, record = self.make_record(Path(root))
            cases = [
                ("metadata", "issuer", "외교부"),
                ("metadata", "document_url", "https://www.mnd.go.kr/common/download.do?fileId=198565537&tblKey=GMN"),
                ("metadata", "document_url", "https://www.korea.kr/common/download.do?fileId=198565537&tblKey=GMN&extra=1"),
                ("record", "source_identity", "korea-policy:wrong"),
            ]
            for section, field, value in cases:
                with self.subTest(field=field, value=value):
                    r = json.loads(json.dumps(record, ensure_ascii=False))
                    (r["metadata"] if section == "metadata" else r)[field] = value
                    self.assertEqual(audit.source_compare(r, state)["machine_fidelity"], "FAIL")

    def test_forged_approval_never_inferred_from_machine_checks(self):
        with tempfile.TemporaryDirectory() as root:
            state, record = self.make_record(Path(root))
            sha = hashlib.sha256(b"db").hexdigest()
            (state / "shadow.db").write_bytes(b"db")
            ledger = [{
                "run_id": "one", "desk": "korea", "health": "ok",
                "target_date": "2026-10-06",
                "finished_utc": "2026-10-06T17:00:00+00:00",
                "state_sha256_before": None, "state_sha256_after": sha,
            }]
            formal = {"findings": [], "missing_successful_days": []}
            report, assignment = audit.make_packet(
                state, formal, [record], ledger, date(2026, 10, 6),
                "a" * 40, "b" * 40)
            self.assertEqual(report["machine_hwp_original_parity"], "PASS")
            self.assertEqual(report["scheduled_continuity"], "PASS")
            self.assertFalse(report["source_eligible_for_substantive_weekly_claims"])
            self.assertFalse(report["production_promotion_authorized"])
            self.assertEqual(report["human_source_review"], "UNMEASURED")
            self.assertEqual(assignment["human_approval_count"], 0)
            checks = assignment["source_review_assignments"][0]
            self.assertIsNone(checks["original_hwpx_visually_compared"])
            self.assertFalse(checks["source_specific_approved"])

    def test_missing_day_blocks_continuity_not_machine_source_parity(self):
        with tempfile.TemporaryDirectory() as root:
            state, record = self.make_record(Path(root))
            (state / "shadow.db").write_bytes(b"db")
            sha = hashlib.sha256(b"db").hexdigest()
            run = {"run_id": "first", "desk": "korea", "health": "ok",
                   "target_date": "2026-10-06",
                   "finished_utc": "2026-10-06T17:00:00+00:00",
                   "state_sha256_before": None, "state_sha256_after": sha}
            reviewed = {"findings": ["No successful logical-day ledger: 2026-10-07"],
                        "missing_successful_days": ["2026-10-07"]}
            report, _ = audit.make_packet(state, reviewed, [record], [run],
                                          date(2026, 10, 7), "a"*40, "b"*40)
            self.assertEqual(report["machine_hwp_original_parity"], "PASS")
            self.assertEqual(report["scheduled_continuity"], "FAIL")
            self.assertEqual(report["missing_logical_dates"], ["2026-10-07"])

    def test_fail_closed_on_broken_chain_and_duplicate_run_id(self):
        with tempfile.TemporaryDirectory() as root:
            state, _ = self.make_record(Path(root))
            (state / "shadow.db").write_bytes(b"correct")
            runs = [
                {"run_id": "same", "desk": "korea", "health": "ok",
                 "target_date": "2026-10-06", "finished_utc": "2026-10-06T17:00:00+00:00",
                 "state_sha256_before": None, "state_sha256_after": "a"*64},
                {"run_id": "same", "desk": "korea", "health": "ok",
                 "target_date": "2026-10-07", "finished_utc": "2026-10-07T17:00:00+00:00",
                 "state_sha256_before": "b"*64, "state_sha256_after": "c"*64},
            ]
            findings = audit.chain_findings(runs, state, as_of=date(2026, 10, 7))
            self.assertTrue(any("discontinuity" in f for f in findings))
            self.assertTrue(any("duplicate" in f for f in findings))
            self.assertTrue(any("current SQLite" in f for f in findings))

    def test_reject_repo_output_location_before_git_inspection(self):
        with self.assertRaises(audit.AuditRefused):
            audit.run(Path("/tmp/nonexistent"), "a"*40, date(2026, 10, 8),
                      ROOT / "internal-korea-review-packet")


if __name__ == "__main__":
    unittest.main()
