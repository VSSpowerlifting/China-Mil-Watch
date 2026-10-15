"""Synthetic dual-signed Korea metadata import, never production or originals."""
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import korea_versioned_review_admission as review
from scripts import rehearse_korea_metadata_sqlite as harness
from scripts import stage_korea_production_candidates as stage
from tests.test_korea_versioned_review_admission import (
    packet, signed, REVIEWER_KEY, OWNER_KEY, SOURCE,
)


class KoreaMetadataSQLiteRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "fake-clean-korea-source"
        self.source.mkdir(mode=0o700)
        self.private = self.root / "private-databases"
        self.private.mkdir(mode=0o700)
        self.out = self.private / "metadata.sqlite"
        self.p = packet()

    def go(self, p=None, seals=None, **more):
        p = p if p is not None else self.p
        seals = seals if seals is not None else [signed(p)]
        with patch.object(stage, "build", return_value=p):
            return harness.rehearse(
                self.source, p, seals, reviewer_key=REVIEWER_KEY,
                owner_key=OWNER_KEY, as_of_utc="2026-10-15T18:00:00Z",
                destination=self.out, **more)

    def test_verified_fictional_record_inserts_exactly_one_metadata_row(self):
        result = self.go()
        self.assertEqual(result["signed_metadata_rehearsal_rows"], 1)
        self.assertEqual(result["reviewed_source_count"], 1)
        self.assertEqual(result["real_production_rows_written"], 0)
        self.assertEqual(result["actual_public_records_created"], 0)
        self.assertFalse(result["original_body_title_or_media_exported"])
        self.assertEqual(self.out.stat().st_mode & 0o777, 0o600)
        with sqlite3.connect(self.out) as con:
            rows = con.execute(
                "SELECT * FROM korea_metadata_rehearsal").fetchall()
            self.assertEqual(len(rows), 1)
            columns = [x[1] for x in con.execute(
                "PRAGMA table_info(korea_metadata_rehearsal)")]
            for prohibited in (
                "text_original", "title_original", "body",
                "summary_english", "model_id", "image_data",
                "copyright_permission", "production_article_id",
            ):
                self.assertNotIn(prohibited, columns)
            self.assertEqual(rows[0][0], SOURCE)
            self.assertEqual(rows[0][5], stage.URL + "156799901")
            self.assertEqual(rows[0][2], self.p["source_db_sha256"])
            self.assertEqual(
                rows[0][3], self.p["records"][0]["candidate_version_sha256"])
            self.assertEqual(
                rows[0][4],
                hashlib.sha256(stage.canonical(signed(self.p))).hexdigest())
            self.assertEqual(
                rows[0][12], self.p["records"][0]["original_title_sha256"])
            for expected_column in (
                "source_db_sha256", "signed_review_sha256",
                "original_title_sha256",
            ):
                self.assertIn(expected_column, columns)
            self.assertEqual(rows[0][-1],
                             "metadata_only_rehearsal_not_production")
            self.assertEqual(con.execute("PRAGMA quick_check").fetchone()[0],
                             "ok")
        data = self.out.read_bytes()
        self.assertNotIn(b"completely fabricated original", data)
        self.assertNotIn(b"completely fabricated title", data)
        self.assertNotIn(b"-----BEGIN PRIVATE KEY-----", data)
        self.assertNotIn(b"Synthetic Independent Reviewer", data)
        self.assertNotIn(b"Synthetic Project Owner", data)

    def test_signed_hold_stages_an_empty_reviewed_database(self):
        receipt = self.go(seals=[signed(self.p, disposition=review.HOLD)])
        self.assertEqual(receipt["signed_metadata_rehearsal_rows"], 0)
        self.assertEqual(receipt["held_source_count"], 1)
        with sqlite3.connect(self.out) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM "
                                         "korea_metadata_rehearsal").fetchone()[0], 0)

    def test_duplicate_signed_review_is_refused_before_file_creation(self):
        seal = signed(self.p)
        with self.assertRaisesRegex(harness.RehearsalHold,
                                    "duplicate_or_unrecognized_review"):
            self.go(seals=[seal, seal])
        self.assertFalse(self.out.exists())

    def test_source_packet_drift_requires_new_authentic_original_replay(self):
        wrong = copy.deepcopy(self.p)
        wrong["source_git_commit"] = "f" * 40
        with patch.object(stage, "build", return_value=self.p):
            with self.assertRaises(harness.RehearsalHold):
                harness.rehearse(
                    self.source, wrong, [signed(wrong)],
                    reviewer_key=REVIEWER_KEY, owner_key=OWNER_KEY,
                    as_of_utc="2026-10-15T18:00:00Z", destination=self.out)
        self.assertFalse(self.out.exists())

    def test_missing_signatures_wrong_key_rights_or_changed_version_refused(self):
        for change in ("wrong_key", "missing_owner_signature", "wrong_version",
                       "publisher_body_permission", "model_permission"):
            seal = signed(self.p)
            k = OWNER_KEY
            if change == "wrong_key":
                k = b"wrong-synthetic-owner-key-0000000000"
            elif change == "missing_owner_signature":
                seal["owner_hmac_sha256"] = "a" * 64
            elif change == "wrong_version":
                seal["owner"]["candidate_version_sha256"] = "a" * 64
                seal = review.owner_sign(seal["review"], seal["owner"],
                                         secret=OWNER_KEY)
            elif change == "publisher_body_permission":
                seal["owner"]["source_body_redistribution_authorized"] = True
                seal = review.owner_sign(seal["review"], seal["owner"],
                                         secret=OWNER_KEY)
            else:
                seal["owner"]["model_or_email_authorized"] = True
                seal = review.owner_sign(seal["review"], seal["owner"],
                                         secret=OWNER_KEY)
            with self.subTest(change=change):
                with patch.object(stage, "build", return_value=self.p):
                    with self.assertRaises(harness.RehearsalHold):
                        harness.rehearse(
                            self.source, self.p, [seal],
                            reviewer_key=REVIEWER_KEY, owner_key=k,
                            as_of_utc="2026-10-15T18:00:00Z",
                            destination=self.out)
                self.assertFalse(self.out.exists())

    def test_bad_output_path_or_existing_db_refused(self):
        self.go()
        with self.assertRaises(stage.IntakeHold):
            self.go()
        with patch.object(stage, "build", return_value=self.p):
            with self.assertRaises(stage.IntakeHold):
                harness.rehearse(
                    self.source, self.p, [signed(self.p)],
                    reviewer_key=REVIEWER_KEY, owner_key=OWNER_KEY,
                    as_of_utc="2026-10-15T18:00:00Z",
                    destination=stage.ROOT / "pla_watch.db")

    def test_year_discrepancy_never_enters_even_scratch(self):
        p = packet("korea-policy:156785161")
        with self.assertRaises(harness.RehearsalHold):
            self.go(p=p)
        self.assertFalse(self.out.exists())

    def test_no_production_or_publication_wiring(self):
        text = (stage.ROOT / "scripts/rehearse_korea_metadata_sqlite.py").read_text()
        for token in ("UPDATE articles", "INSERT INTO articles", "smtplib",
                      "anthropic", "git push", "site/render.py",
                      "UPDATE desks", "publish_brief"):
            self.assertNotIn(token, text)
        registry = json.loads(
            (stage.ROOT / "desks/registry.json").read_text(encoding="utf-8"))
        kr = next(row for row in registry["desks"] if row["slug"] == "korea")
        self.assertEqual(kr["status"], "shadow")
        self.assertFalse(kr["has_production_records"])


if __name__ == "__main__":
    unittest.main()
