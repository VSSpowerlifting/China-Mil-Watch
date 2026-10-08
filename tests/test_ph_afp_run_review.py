"""Synthetic-only checks for AFP per-run original-API response review handoff."""
from __future__ import annotations

import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import prepare_ph_afp_run_review as review  # noqa: E402


RUN_ID = "37788547061-1"


class SyntheticState:
    """No live site or real human source judgment in these fixtures."""

    def __init__(self, new_count=5):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        db = self.repo / "state" / "shadow.db"
        db.parent.mkdir(parents=True)
        with sqlite3.connect(db) as cx:
            cx.executescript("""
                CREATE TABLE shadow_records (
                    url TEXT PRIMARY KEY, source_identity TEXT, source_slug TEXT,
                    title_original TEXT, text_original TEXT, text_status TEXT,
                    published_date TEXT, published_at_original TEXT,
                    published_at_utc TEXT, language_tag TEXT,
                    content_sha256 TEXT, source_fingerprint TEXT,
                    capture_sha256 TEXT, first_seen_run TEXT, byline TEXT);
                CREATE TABLE captures (
                    capture_id INTEGER PRIMARY KEY, source_identity TEXT,
                    run_id TEXT, payload BLOB, payload_sha256 TEXT,
                    source_fingerprint TEXT, http_status INTEGER,
                    requested_url TEXT, final_url TEXT, retrieved_at TEXT);
            """)
            for i in range(new_count):
                title = "SYNTHETIC AFP RECORD %s" % i
                slug = "synthetic-afp-story-%s" % i
                published = "2026-10-08T08:00:00+08:00"
                raw = json.dumps({
                    "id": 1400+i, "title": title, "slug": slug,
                    "intro_html": "<p>SYNTHETIC INTRO</p>",
                    "body_html": "<p>SYNTHETIC BODY %s</p>" % i,
                    "published_at": published,
                }).encode("utf-8")
                body = "SYNTHETIC BODY %s" % i
                fp = review.sha256(("SYNTHETIC FP %s" % i).encode())
                cap_hash = review.sha256(raw)
                url = "https://www.afp.mil.ph/news/" + slug
                cx.execute(
                    "INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (url, "afp:%s" % (1400+i), "ph_afp_articles", title,
                     body, "text", "2026-10-08", published,
                     "2026-10-08T00:00:00+00:00", "en",
                     review.sha256(body.encode()), fp, cap_hash,
                     RUN_ID, "pao afp"),
                )
                requested = "https://api.afp.mil.ph/articles/" + slug + "/"
                cx.execute(
                    "INSERT INTO captures VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (i+1, "afp:%s" % (1400+i), RUN_ID,
                     raw, cap_hash, fp, 200, requested,
                     requested, "2026-10-08T13:59:23+00:00"),
                )
        self.ledger = {
            "run_id": RUN_ID,
            "desk": "ph-afp",
            "rehearsal": False,
            "health": "ok", "result": "ok", "aborted": None,
            "target_date": "2026-10-08",
            "target_date_source": "schedule-slot",
            "listing_status": "ok",
            "collector_identity": "IndoPacificRecord-ShadowCollector/0.1 (SYNTHETIC TEST)",
            "inserted": new_count, "stored_total": new_count,
            "fetch_failures": 0, "extraction_failures": 0,
            "access_failures": 0, "identity_collisions": 0,
            "redirect_refusals": 0, "failure_log": [],
            "day_zero_utc": "2026-10-07T13:51:44+00:00",
            "state_sha256_after": review.sha256(db.read_bytes()),
        }
        ledger_file = self.repo / "state/ledger/SYNTHETIC.json"
        ledger_file.parent.mkdir()
        ledger_file.write_text(json.dumps(self.ledger))
        (self.repo / "state/clock.json").write_text(json.dumps({
            "day_zero_utc": "2026-10-07T13:51:44+00:00",
            "day_zero_run_id": "SYNTHETIC-DAY0",
        }))
        self.commit()

    def commit(self):
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run([
            "git", "-c", "user.name=TEST", "-c",
            "user.email=synthetic@example.invalid",
            "commit", "-qm", "SYNTHETIC AFP TEST STATE",
        ], cwd=self.repo, check=True)
        self.sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo
        ).decode().strip()

    def mutate_ledger(self, key, value):
        self.ledger[key] = value
        (self.repo / "state/ledger/SYNTHETIC.json").write_text(
            json.dumps(self.ledger))
        self.commit()

    def mutate_db(self, statement, parameters=()):
        file = self.repo / "state/shadow.db"
        with sqlite3.connect(file) as cx:
            cx.execute(statement, parameters)
        self.ledger["state_sha256_after"] = review.sha256(file.read_bytes())
        (self.repo / "state/ledger/SYNTHETIC.json").write_text(
            json.dumps(self.ledger))
        self.commit()

    def packet(self):
        return review.make_packet(review.FrozenState(self.repo, self.sha), RUN_ID)

    def close(self):
        self.temp.cleanup()


class PacketContract(unittest.TestCase):
    def setUp(self):
        self.fake = SyntheticState()

    def tearDown(self):
        self.fake.close()

    def test_all_five_new_record_payloads_are_included_without_judgments(self):
        packet = self.fake.packet()
        self.assertEqual(packet["machine_verified_capture_count"], 5)
        self.assertEqual(len(packet["records"]), 5)
        self.assertFalse(packet["human_review_complete"])
        self.assertFalse(packet["human_approval"])
        self.assertFalse(packet["desk_qualified"])
        self.assertEqual(packet["production_assignments"], 0)
        self.assertTrue(all(row["decision"] == "pending" for row in packet["records"]))
        self.assertTrue(all("SYNTHETIC" in row["original_api_response_utf8"]
                            for row in packet["records"]))
        self.assertTrue(all(row["first_seen_run"] == RUN_ID for row in packet["records"]))
        self.assertTrue(all(row["read_original_capture"] is False
                            for row in packet["records"]))

    def test_human_attestation_is_not_automatically_authenticated(self):
        original = self.fake.packet()
        completed = copy.deepcopy(original)
        for row in completed["records"]:
            row["decision"] = "verified"
            row["reviewer_name"] = "SYNTHETIC TEST ACTOR, NOT A PERSON"
            row["read_original_capture"] = True
            row["reviewed_at_utc"] = "2026-10-08T14:00:00Z"
            row["rationale"] = "SYNTHETIC TEST FIXTURE ONLY"
            row["checks"] = dict.fromkeys(review.CHECKS, True)
        report = review.validate_packet(completed, original, require_complete=True)
        self.assertEqual(report["decisions"]["verified"], 5)
        self.assertFalse(report["human_identity_authenticated"])
        self.assertFalse(report["reviewer_actually_read_original_verified"])
        self.assertFalse(report["editorial_approval"])
        self.assertFalse(report["qualification"])
        self.assertEqual(report["production_writes"], 0)

    def test_frozen_raw_original_cannot_be_modified_by_reviewer(self):
        original = self.fake.packet()
        for field in ("original_api_response_utf8", "first_seen_run", "byline",
                      "capture_sha256", "text_original", "title_original"):
            candidate = copy.deepcopy(original)
            candidate["records"][0][field] += "MUTATION"
            with self.subTest(field=field):
                with self.assertRaisesRegex(review.AFPReviewError, "modified|altered"):
                    review.validate_packet(candidate, original)

    def test_pending_review_does_not_count_as_completed(self):
        original = self.fake.packet()
        with self.assertRaisesRegex(review.AFPReviewError, "incomplete"):
            review.validate_packet(original, original, require_complete=True)

    def test_identity_mismatch_in_json_capture_refused(self):
        self.fake.mutate_db(
            "UPDATE captures SET payload = ? WHERE source_identity='afp:1400'",
            (b'{"id": 999, "title":"SYNTHETIC"}',)
        )
        with self.assertRaisesRegex(review.AFPReviewError, "capture mismatch"):
            self.fake.packet()

    def test_raw_json_slug_and_title_parity_is_enforced(self):
        self.fake.mutate_db(
            "UPDATE shadow_records SET title_original='MISMATCH' "
            "WHERE source_identity='afp:1400'"
        )
        with self.assertRaisesRegex(review.AFPReviewError, "title differs"):
            self.fake.packet()

    def test_original_capture_hash_changed_even_with_valid_json_fails(self):
        self.fake.mutate_db(
            "UPDATE captures SET payload_sha256='" + "0"*64 + "' "
            "WHERE source_identity='afp:1400'"
        )
        with self.assertRaisesRegex(review.AFPReviewError, "capture mismatch"):
            self.fake.packet()

    def test_insertion_count_must_match_first_seen_rows(self):
        self.fake.mutate_ledger("inserted", 999)
        with self.assertRaisesRegex(review.AFPReviewError, "insertion count"):
            self.fake.packet()

    def test_manual_or_rehearsal_returns_no_human_review_packet(self):
        for key, value in (("target_date_source", "explicit"),
                           ("rehearsal", True),
                           ("health", "partial"),
                           ("fetch_failures", 1)):
            with self.subTest(key=key):
                state = SyntheticState()
                try:
                    state.mutate_ledger(key, value)
                    with self.assertRaisesRegex(review.AFPReviewError, "provenance"):
                        state.packet()
                finally:
                    state.close()

    def test_missing_git_originals_fail_without_live_fetch(self):
        with self.assertRaisesRegex(review.AFPReviewError, "40-character"):
            review.FrozenState(self.fake.repo, "shadow/ph-afp")
        with self.assertRaisesRegex(review.AFPReviewError, "unavailable"):
            review.FrozenState(self.fake.repo, "0"*40)

    def test_multiple_ledger_rows_cannot_claim_same_run(self):
        ledger = self.fake.repo / "state/ledger/SYNTHETIC.json"
        (self.fake.repo / "state/ledger/FAKE_COPY.json").write_bytes(
            ledger.read_bytes()
        )
        self.fake.commit()
        with self.assertRaisesRegex(review.AFPReviewError, "exactly one"):
            self.fake.packet()

    def test_commit_snapshot_does_not_read_worktree_mutation(self):
        original = self.fake.packet()
        ledger = self.fake.repo / "state/ledger/SYNTHETIC.json"
        ledger.write_bytes(b"WORKTREE TAMPERING AFTER COMMIT")
        self.assertEqual(self.fake.packet(), original)

    def test_zero_new_record_success_generates_zero_unsigned_rows(self):
        state = SyntheticState(new_count=0)
        try:
            packet = state.packet()
            self.assertEqual(packet["machine_verified_capture_count"], 0)
            self.assertEqual(packet["records"], [])
            self.assertEqual(
                review.validate_packet(packet, packet)["decisions"]["pending"], 0
            )
        finally:
            state.close()

    def test_cli_can_print_frozen_packet_without_writes(self):
        run = subprocess.run(
            [sys.executable, str(ROOT / "scripts/prepare_ph_afp_run_review.py"),
             "packet", "--state-repo", str(self.fake.repo),
             "--state-commit", self.fake.sha, "--run-id", RUN_ID],
            cwd=ROOT, capture_output=True, text=True, check=False
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), self.fake.packet())

    def test_wrong_run_is_not_substituted_from_adjacent_archive(self):
        with self.assertRaisesRegex(review.AFPReviewError, "exactly one"):
            review.make_packet(
                review.FrozenState(self.fake.repo, self.fake.sha), "unrelated-run"
            )

    def test_malformed_source_record_type_is_rejected(self):
        self.fake.mutate_db(
            "UPDATE shadow_records SET text_original='MUTATED' "
            "WHERE source_identity='afp:1400'"
        )
        with self.assertRaisesRegex(review.AFPReviewError, "text hash mismatch"):
            self.fake.packet()


if __name__ == "__main__":
    unittest.main()
