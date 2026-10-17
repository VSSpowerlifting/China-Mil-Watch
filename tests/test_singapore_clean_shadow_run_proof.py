"""Synthetic, no-source-network tests for the next genuine Singapore run receipt."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.verify_singapore_clean_shadow_run import (
    EMPTY_SHA, URL, TITLE, ShadowHold, verify,
)

RUN_ID = "39000000001"
COLLECTOR = "a" * 40
URL_2 = ("https://www.mindef.gov.sg/news-and-events/latest-releases/"
         "15oct26-nr1/")


class SingaporeScheduledProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "isolated-singapore-git"
        self.state = self.root / "state"
        (self.state / "ledger").mkdir(parents=True)
        self.db_path = self.state / "shadow.db"
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "CREATE TABLE shadow_records("
                "url TEXT PRIMARY KEY,title_original TEXT NOT NULL,"
                "text_original TEXT NOT NULL,published_date TEXT NOT NULL,"
                "content_sha256 TEXT NOT NULL,source_slug TEXT NOT NULL)"
            )
            db.executemany(
                "INSERT INTO shadow_records VALUES(?,?,?,?,?,?)", [
                    (URL, TITLE, "", "2026-09-22", EMPTY_SHA,
                     "sg_mindef_releases"),
                    (URL_2, "Synthetic test release", "SYNTHETIC body",
                     "2026-10-15",
                     hashlib.sha256(b"SYNTHETIC body").hexdigest(),
                     "sg_mindef_releases"),
                ]
            )
        self.receipt = {
            "run_id": RUN_ID,
            "collector_commit": COLLECTOR,
            "health": "ok", "result": "ok",
            "robots_status": "allowed", "listing_status": "ok",
            "selected": 2, "discovered": 2, "retrieved": 2,
            "inserted": 2, "duplicates": 0, "stored_total": 2,
            "access_failures": 0, "fetch_failures": 0,
            "extraction_failures": 0, "failure_log": [],
            "text_unavailable": 1, "media_only_urls": [URL],
            "target_date": "2026-10-15",
            "target_date_source": "schedule-slot",
        }
        self.write()

    def write(self):
        path = self.state / "ledger" / ("20261015T211000+0000-" +
                                         RUN_ID + ".json")
        path.write_text(json.dumps(self.receipt), encoding="utf-8")

    def check(self):
        return verify(self.root, run_id=RUN_ID, collector_sha=COLLECTOR)

    def test_clean_real_like_schedule_identity_and_media_only(self):
        result = self.check()
        self.assertEqual(result["status"],
                         "VERIFIED_SINGAPORE_SCHEDULED_SHADOW_SLOT")
        self.assertEqual(result["publisher_media_only_without_invented_text"], 1)
        self.assertEqual(result["new_originals"], 2)
        self.assertTrue(result["known_infographic_verified"])
        self.assertFalse(result["publication_authorized"])
        self.assertEqual(result["production_rows_admitted"], 0)

    def test_failed_old_attempt_cannot_qualify_despite_known_url(self):
        for changes in (
            {"health": "fail", "result": "extraction_failure"},
            {"extraction_failures": 1},
            {"failure_log": [{"url": URL, "stage": "extract",
                              "status": "extraction_failure"}]},
            {"retrieved": 1},
            {"selected": 0},
            {"robots_status": "disallowed"},
            {"media_only_urls": []},
            {"target_date_source": "explicit"},
            {"collector_commit": "b" * 40},
        ):
            with self.subTest(changes=changes):
                self.receipt.update(changes)
                self.write()
                with self.assertRaises(ShadowHold):
                    self.check()
                self.receipt = {
                    **self.base_receipt(), **{
                        # Recreate exact clean fields; avoid leaking mutation
                        # from the previous negative case.
                    }}
                self.write()

    def base_receipt(self):
        return dict(
            run_id=RUN_ID, collector_commit=COLLECTOR,
            health="ok", result="ok", robots_status="allowed",
            listing_status="ok", selected=2, discovered=2, retrieved=2,
            inserted=2, duplicates=0, stored_total=2, access_failures=0,
            fetch_failures=0, extraction_failures=0, failure_log=[],
            text_unavailable=1, media_only_urls=[URL],
            target_date="2026-10-15", target_date_source="schedule-slot")

    def test_missing_run_identity_and_false_old_ledger(self):
        with self.assertRaises(ShadowHold):
            verify(self.root, run_id="39000000002", collector_sha=COLLECTOR)
        with self.assertRaises(ShadowHold):
            verify(self.root, run_id=RUN_ID, collector_sha="b" * 40)

    def test_broken_original_db_and_media_only_hash_hold(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE shadow_records SET text_original=? WHERE url=?",
                       ("fake text", URL))
        with self.assertRaises(ShadowHold):
            self.check()

    def test_original_count_and_duplicate_crosschecks(self):
        self.receipt["stored_total"] = 90
        self.write()
        with self.assertRaises(ShadowHold):
            self.check()
        self.receipt["stored_total"] = 2
        self.receipt["duplicates"] = 1
        self.write()
        with self.assertRaises(ShadowHold):
            self.check()

    def test_all_duplicates_clean_slot_is_eligible(self):
        self.receipt.update(result="ok_all_duplicates", inserted=0,
                            duplicates=2)
        self.write()
        result = self.check()
        self.assertEqual(result["new_originals"], 0)
        self.assertEqual(result["duplicates"], 2)
        self.assertTrue(result["new_reliability_day_proven"])

    def test_clean_future_slot_can_omit_expired_infographic_without_fake_proof(self):
        # The Sep 22 original is eventually outside the 30-day publisher
        # lookback. Requiring it on every subsequent day would make an
        # otherwise complete production feed permanently red.
        self.receipt.update(text_unavailable=0, media_only_urls=[])
        self.write()
        receipt = self.check()
        self.assertTrue(receipt["new_reliability_day_proven"])
        self.assertFalse(receipt["known_infographic_verified"])
        self.assertEqual(receipt["publisher_media_only_without_invented_text"], 0)

    def test_workflow_authenticates_scheduled_attempt_from_actions_api(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github" /
                    "workflows" / "singapore_first_clean_scheduled_proof.yml")
        contents = workflow.read_text(encoding="utf-8")
        # Human-triggered replays must authenticate the original GitHub Actions
        # schedule/attempt/job; a self-declared run ID or ledger is insufficient.
        for needle in (
            "actions: read",
            "gh api \"repos/${GITHUB_REPOSITORY}/actions/runs/${RUN_ID_INPUT}\"",
            ".event == \"schedule\"",
            ".run_attempt == 1",
            ".head_branch == \"main\"",
            ".head_sha == $sha",
            ".name == \"shadow\"",
            ".name == \"Run shadow collection\"",
            ".total_count == (.jobs | length)",
        ):
            with self.subTest(expected_guard=needle):
                self.assertIn(needle, contents)
        self.assertNotIn("contents: write", contents)
        self.assertNotIn("pages: write", contents)

    def test_never_creates_production_sqlite_or_sidecar(self):
        self.check()
        self.assertFalse((self.root / "pla_watch.db").exists())
        self.assertFalse((self.state / "shadow.db-wal").exists())
        self.assertFalse((self.state / "shadow.db-shm").exists())


if __name__ == "__main__":
    unittest.main()
