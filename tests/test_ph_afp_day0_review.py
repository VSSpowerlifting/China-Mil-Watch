"""Synthetic-only contracts for the AFP Day-0 unsigned human review queue.

No test fixture reviewer is real; no human decisions or source rights are granted.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import prepare_ph_afp_day0_review as queue  # noqa: E402


def synthetic_state():
    """Construct source-looking fake data explicitly marked SYNTHETIC."""
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "shadow.db"
        with sqlite3.connect(path) as db:
            db.executescript("""
                CREATE TABLE shadow_records (
                    url TEXT PRIMARY KEY, source_identity TEXT UNIQUE,
                    source_slug TEXT, title_original TEXT,
                    text_original TEXT, text_status TEXT,
                    published_date TEXT, published_at_original TEXT,
                    published_at_utc TEXT, language_tag TEXT,
                    content_sha256 TEXT, source_fingerprint TEXT,
                    capture_sha256 TEXT, first_seen_run TEXT);
                CREATE TABLE captures (
                    capture_id INTEGER PRIMARY KEY, source_identity TEXT,
                    run_id TEXT, payload BLOB, payload_sha256 TEXT,
                    source_fingerprint TEXT, http_status INTEGER,
                    requested_url TEXT, final_url TEXT, retrieved_at TEXT);
                CREATE TABLE revisions (
                    revision_id INTEGER PRIMARY KEY, source_identity TEXT);
            """)
            for index in range(13):
                slug = "synthetic-review-%02d" % index
                pid = "afp:%d" % (2000 + index)
                text = "SYNTHETIC AFP ORIGINAL TEXT %02d; NOT ARCHIVAL EVIDENCE" % index
                payload = json.dumps({"id": 2000 + index, "body_html": text}).encode()
                h = queue.sha256(payload)
                requested = "https://api.afp.mil.ph/articles/%s/" % slug
                stored = "https://www.afp.mil.ph/news/%s" % slug
                fingerprint = queue.sha256(("fp"+str(index)).encode())
                db.execute(
                    "INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (stored, pid, queue.SOURCE, "SYNTHETIC TITLE %02d" % index,
                     text, "text", "2026-10-06", "2026-10-06T10:00:00+08:00",
                     "2026-10-06T02:00:00+00:00", "en",
                     queue.sha256(text.encode()), fingerprint, h, queue.RUN_ID),
                )
                db.execute(
                    "INSERT INTO captures VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (index + 1, pid, queue.RUN_ID, payload, h, fingerprint,
                     200, requested, requested, "2026-10-07T13:51:00+00:00"),
                )
        blob = path.read_bytes()
    ledger = {
        "run_id": queue.RUN_ID, "rehearsal": False,
        "target_date": "2026-10-07", "target_date_source": "schedule-slot",
        "result": "ok", "health": "ok", "shadow_day": 0,
        "selected": 13, "retrieved": 13, "inserted": 13,
        "stored_with_text": 13, "stored_total": 13,
        "fetch_failures": 0, "extraction_failures": 0,
        "state_sha256_after": queue.sha256(blob),
        "finished_utc": "2026-10-07T13:51:44+00:00",
    }
    clock = {"day_zero_run_id": queue.RUN_ID,
             "day_zero_utc": ledger["finished_utc"]}
    return {
        "state/shadow.db": blob,
        queue.LEDGER_PATH: json.dumps(ledger).encode(),
        "state/clock.json": json.dumps(clock).encode(),
    }


def run_git(repo: Path, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, check=True,
    ).stdout.decode("utf-8").strip()


class AFPDayZeroReviewerContracts(unittest.TestCase):
    def setUp(self):
        self.sources = synthetic_state()
        self.packet = queue.make_queue_from_objects(self.sources)

    def test_all_thirteen_unsigned_originals_and_no_automatic_approval(self):
        p = self.packet
        self.assertEqual(p["machine_verified_capture_count"], 13)
        self.assertEqual(len(p["records"]), 13)
        self.assertEqual(
            len({r["source_identity"] for r in p["records"]}), 13
        )
        self.assertFalse(p["human_review_complete"])
        self.assertFalse(p["human_approval"])
        self.assertFalse(p["desk_qualified"])
        self.assertEqual(p["production_assignments"], 0)
        self.assertTrue(all(r["decision"] == "pending" for r in p["records"]))
        self.assertTrue(all("SYNTHETIC" in r["text_original"] for r in p["records"]))

    def test_original_capture_digest_and_identity_are_in_review_queue(self):
        for row in self.packet["records"]:
            self.assertEqual(row["body_chars"], len(row["text_original"]))
            self.assertEqual(row["text_sha256"],
                             queue.sha256(row["text_original"].encode()))
            self.assertEqual(row["capture_http_status"], 200)
            self.assertEqual(row["capture_final_url"], row["capture_request_url"])
            self.assertTrue(row["capture_sha256"])
            self.assertEqual(set(row["checks"]), set(queue.CHECKS))

    def test_review_validation_rejects_premature_completion(self):
        with self.assertRaisesRegex(queue.AFPReviewError, "incomplete"):
            queue.validate_reviews(self.packet, self.packet, require_complete=True)
        q = copy.deepcopy(self.packet)
        q["records"][0]["reviewer_name"] = "SYNTHETIC TEST USER"
        with self.assertRaisesRegex(queue.AFPReviewError, "pending"):
            queue.validate_reviews(q, self.packet)

    def test_machine_accepts_only_formally_complete_test_attestations(self):
        result = copy.deepcopy(self.packet)
        for row in result["records"]:
            row["decision"] = "verified"
            row["checks"] = {name: True for name in queue.CHECKS}
            row["reviewer_name"] = "SYNTHETIC TEST ACTOR NOT A HUMAN"
            row["read_original_capture"] = True
            row["reviewed_at_utc"] = "2026-10-08T05:00:00Z"
            row["rationale"] = "SYNTHETIC FIXTURE, NOT ACTUAL REVIEW"
        report = queue.validate_reviews(result, self.packet, require_complete=True)
        self.assertEqual(report["decisions"]["verified"], 13)
        self.assertFalse(report["human_identity_authenticated"])
        self.assertFalse(report["editorial_approval"])
        self.assertFalse(report["qualification"])
        self.assertEqual(report["production_writes"], 0)

    def test_verified_cannot_override_failed_fidelity_checks(self):
        result = copy.deepcopy(self.packet)
        row = result["records"][0]
        row.update({"decision": "verified", "reviewer_name": "SYNTHETIC TEST",
                    "read_original_capture": True,
                    "reviewed_at_utc": "2026-10-08T05:00:00Z",
                    "rationale": "SYNTHETIC NEGATIVE"})
        row["checks"] = {name: True for name in queue.CHECKS}
        row["checks"]["full_body_and_no_site_furniture"] = False
        with self.assertRaisesRegex(queue.AFPReviewError, "failed source check"):
            queue.validate_reviews(result, self.packet)

    def test_review_hold_requires_a_recorded_failing_check(self):
        result = copy.deepcopy(self.packet)
        row = result["records"][0]
        row.update({"decision": "hold", "reviewer_name": "SYNTHETIC TEST",
                    "read_original_capture": True,
                    "reviewed_at_utc": "2026-10-08T05:00:00Z",
                    "rationale": "SYNTHETIC HOLD"})
        row["checks"] = {name: True for name in queue.CHECKS}
        with self.assertRaisesRegex(queue.AFPReviewError, "documented failed"):
            queue.validate_reviews(result, self.packet)
        row["checks"]["capture_bytes_and_provenance"] = False
        self.assertEqual(
            queue.validate_reviews(result, self.packet)["decisions"]["hold"], 1
        )

    def test_preserved_identity_cannot_change_in_review(self):
        result = copy.deepcopy(self.packet)
        for field in ("source_identity", "title_original", "source_url",
                      "text_original", "capture_sha256", "published_date"):
            changed = copy.deepcopy(result)
            changed["records"][0][field] += "tampered"
            with self.subTest(field=field):
                with self.assertRaisesRegex(queue.AFPReviewError, "archived identity"):
                    queue.validate_reviews(changed, self.packet)

    def test_header_claims_cannot_be_changed(self):
        for field,value in (("human_review_complete", True),
                            ("desk_qualified", True),
                            ("production_assignments", 13)):
            changed = copy.deepcopy(self.packet)
            changed[field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(queue.AFPReviewError, "provenance"):
                    queue.validate_reviews(changed, self.packet)

    def test_corrupt_original_capture_rejected(self):
        changed = dict(self.sources)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shadow.db"
            path.write_bytes(changed["state/shadow.db"])
            with sqlite3.connect(path) as db:
                db.execute(
                    "UPDATE captures SET payload = ? WHERE capture_id=1",
                    (b"altered synthetic bytes",)
                )
            changed["state/shadow.db"] = path.read_bytes()
        ledger = json.loads(changed[queue.LEDGER_PATH])
        ledger["state_sha256_after"] = queue.sha256(changed["state/shadow.db"])
        changed[queue.LEDGER_PATH] = json.dumps(ledger).encode()
        with self.assertRaisesRegex(queue.AFPReviewError, "capture integrity"):
            queue.make_queue_from_objects(changed)

    def test_corrupt_extracted_body_hash_rejected(self):
        changed = dict(self.sources)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shadow.db"
            path.write_bytes(changed["state/shadow.db"])
            with sqlite3.connect(path) as db:
                db.execute(
                    "UPDATE shadow_records SET text_original = 'SYNTHETIC MUTATION' "
                    "WHERE source_identity = 'afp:2000'"
                )
            changed["state/shadow.db"] = path.read_bytes()
        ledger = json.loads(changed[queue.LEDGER_PATH])
        ledger["state_sha256_after"] = queue.sha256(changed["state/shadow.db"])
        changed[queue.LEDGER_PATH] = json.dumps(ledger).encode()
        with self.assertRaisesRegex(queue.AFPReviewError, "text digest mismatch"):
            queue.make_queue_from_objects(changed)

    def test_missing_original_body_or_changed_day0_status_rejected(self):
        changed = dict(self.sources)
        ledger = json.loads(changed[queue.LEDGER_PATH])
        ledger["inserted"] = 12
        changed[queue.LEDGER_PATH] = json.dumps(ledger).encode()
        with self.assertRaisesRegex(queue.AFPReviewError, "Day-0"):
            queue.make_queue_from_objects(changed)
        changed = dict(self.sources)
        changed["state/clock.json"] = b'{"day_zero_run_id":"INVENTED"}'
        with self.assertRaisesRegex(queue.AFPReviewError, "clock"):
            queue.make_queue_from_objects(changed)

    def test_missing_historical_object_no_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            run_git(repo, "init", "-q")
            with self.assertRaisesRegex(queue.AFPReviewError, "no current-state"):
                queue.git_objects(repo, "0"*40, queue.SNAPSHOT_BLOBS)

    def test_pinned_git_snapshot_matches_exact_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            run_git(repo, "init", "-q")
            for path, raw in self.sources.items():
                file = repo / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(raw)
            run_git(repo, "add", ".")
            run_git(repo, "-c", "user.name=TEST",
                    "-c", "user.email=test@example.invalid",
                    "commit", "-qm", "SYNTHETIC ONLY")
            commit = run_git(repo, "rev-parse", "HEAD")
            expected = {
                path: run_git(repo, "rev-parse", "HEAD:"+path)
                for path in queue.SNAPSHOT_BLOBS
            }
            fetched = queue.git_objects(repo, commit, expected)
            self.assertEqual(fetched, self.sources)
            expected["state/shadow.db"] = "0"*40
            with self.assertRaisesRegex(queue.AFPReviewError, "blob mismatch"):
                queue.git_objects(repo, commit, expected)

    def test_symbolic_branch_rejected_for_historical_snapshot(self):
        with self.assertRaisesRegex(queue.AFPReviewError, "full Git SHA"):
            queue.git_objects(Path("."), "main", queue.SNAPSHOT_BLOBS)


if __name__ == "__main__":
    unittest.main()
