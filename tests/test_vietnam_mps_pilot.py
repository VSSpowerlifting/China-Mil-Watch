"""Offline contract for the accelerated Vietnam MPS staging gate.

No network, no production database and no source text fixtures.
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import prepare_vietnam_mps_pilot as pilot

SOURCE = pilot.PILOT_SOURCE
IDENTITY = "mps-vi:1234567890"
URL = "https://bocongan.gov.vn/bai-viet/test-1234567890"
DIGEST = "a" * 64
CAPTURE = "b" * 64
COMMIT = "c" * 40
TREE = "d" * 40


def approval():
    return {
        "schema": pilot.SCHEMA, "source_slug": SOURCE,
        "state_commit": COMMIT, "reviewer": "Test Reviewer",
        "reviewed_at_utc": "2026-10-08T00:00:00+00:00",
        "records": [{
            "source_identity": IDENTITY, "content_sha256": DIGEST,
            "checks": {k: True for k in pilot.CHECKS},
            "reuse_approved": True,
            "rights_basis": "Explicit human approval based on a documented source-use review."
        }]
    }


def evidence():
    record = {
        "source_identity": IDENTITY, "source_slug": SOURCE, "url": URL,
        "canonical_url": URL, "published_date": "2026-10-05",
        "current_content_sha256": DIGEST,
    }
    version = {
        "source_identity": IDENTITY, "content_sha256": DIGEST,
        "body_status": "text", "title_original": "A Vietnamese ministry title",
        "text_original": "Vietnamese text as captured from the publisher",
        "first_seen_run": "run-1", "first_capture_sha256": CAPTURE,
    }
    obs = {"run_id": "run-1", "source_identity": IDENTITY,
           "content_sha256": DIGEST, "capture_sha256": CAPTURE,
           "retrieved_at": "2026-10-07T23:00:00Z", "anomalies_json": "[]"}
    return {
        "source_slug": SOURCE, "clock": {"day_zero_utc": "2026-10-07T23:00:00Z"},
        "successes": 1, "runs": [{"health": "ok"}],
        "records": [record], "versions": [version], "observations": [obs]
    }


def create_db(path):
    with sqlite3.connect(path) as con:
        con.executescript("""
            CREATE TABLE desks (
                desk_id TEXT PRIMARY KEY,display_name TEXT,jurisdiction_code TEXT,
                default_timezone TEXT,default_calendar TEXT,
                supported_language_tags TEXT,active INTEGER,public_status TEXT);
            CREATE TABLE institutions (
                institution_id TEXT PRIMARY KEY,desk_id TEXT,
                display_name TEXT,name_original TEXT,institution_type TEXT);
            CREATE TABLE sources (
                id INTEGER PRIMARY KEY,slug TEXT UNIQUE,display_name TEXT,
                base_url TEXT,language TEXT,is_active INTEGER,desk_id TEXT,
                institution_id TEXT,language_tag TEXT,authority_tier TEXT,
                enabled INTEGER,listing_endpoints TEXT,notes TEXT);
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY,url TEXT UNIQUE,content_hash TEXT,
                source_id INTEGER,title_original TEXT,text_original TEXT,
                published_date TEXT,scraped_at TEXT);
        """)


class VietnamPilotAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "approval.json"
        self.path.write_text(json.dumps(approval()), encoding="utf-8")

    def read(self, payload):
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        return pilot.read_approval(self.path, COMMIT)

    def test_correct_document_is_bound_to_exact_commit(self):
        self.assertEqual(self.read(approval())["source_slug"], SOURCE)
        with self.assertRaisesRegex(pilot.Refused, "another state commit"):
            pilot.read_approval(self.path, "f" * 40)

    def test_missing_human_review_is_refused(self):
        for field in pilot.CHECKS:
            with self.subTest(field=field):
                a = approval()
                a["records"][0]["checks"][field] = False
                with self.assertRaisesRegex(pilot.Refused, "checks"):
                    self.read(a)

    def test_rights_and_named_reviewer_are_required(self):
        a = approval()
        a["records"][0]["reuse_approved"] = False
        with self.assertRaisesRegex(pilot.Refused, "reuse"):
            self.read(a)
        a = approval()
        a["records"][0]["rights_basis"] = "ok"
        with self.assertRaisesRegex(pilot.Refused, "rights basis"):
            self.read(a)
        a = approval()
        a["reviewer"] = ""
        with self.assertRaisesRegex(pilot.Refused, "reviewer"):
            self.read(a)

    def test_duplicate_and_mass_approvals_refused(self):
        a = approval()
        a["records"].append(dict(a["records"][0]))
        with self.assertRaisesRegex(pilot.Refused, "duplicate"):
            self.read(a)
        a = approval()
        a["records"] = a["records"] * 11
        with self.assertRaisesRegex(pilot.Refused, "1–10"):
            self.read(a)

    def test_only_mps_source_is_permitted(self):
        a = approval()
        a["source_slug"] = "vn_moit_energy_vi"
        with self.assertRaisesRegex(pilot.Refused, "limited"):
            self.read(a)

    def test_current_version_and_capture_must_match(self):
        planned = pilot.candidates(evidence(), approval())
        self.assertEqual(len(planned), 1)
        e = evidence()
        e["records"][0]["current_content_sha256"] = "e" * 64
        with self.assertRaisesRegex(pilot.Refused, "no longer current"):
            pilot.candidates(e, approval())
        e = evidence()
        e["observations"][0]["capture_sha256"] = "e" * 64
        with self.assertRaisesRegex(pilot.Refused, "first capture"):
            pilot.candidates(e, approval())

    def test_anomalous_and_empty_bodies_refused(self):
        e = evidence()
        e["observations"][0]["anomalies_json"] = '["published_time_changed"]'
        with self.assertRaisesRegex(pilot.Refused, "anomaly"):
            pilot.candidates(e, approval())
        e = evidence()
        e["versions"][0]["text_original"] = "  "
        with self.assertRaisesRegex(pilot.Refused, "empty body"):
            pilot.candidates(e, approval())

    def test_copy_only_insert_is_atomic_and_idempotent(self):
        dest = self.root / "copy.db"
        create_db(dest)
        plan = pilot.candidates(evidence(), approval())
        provenance = {"state_commit": COMMIT, "state_tree": TREE}
        one = pilot.apply_to_copy(dest, plan, approval(), provenance)
        self.assertEqual(one, {"inserted": 1, "already_present": 0})
        two = pilot.apply_to_copy(dest, plan, approval(), provenance)
        self.assertEqual(two, {"inserted": 0, "already_present": 1})
        with sqlite3.connect(dest) as con:
            source = con.execute(
                "SELECT enabled,is_active,desk_id FROM sources WHERE slug=?", (SOURCE,)
            ).fetchone()
            desk = con.execute(
                "SELECT active,public_status FROM desks WHERE desk_id='vietnam'"
            ).fetchone()
            count = con.execute("SELECT count(*) FROM articles").fetchone()[0]
            audit = con.execute("SELECT count(*) FROM vietnam_pilot_imports").fetchone()[0]
        self.assertEqual(source, (0, 0, "vietnam"))
        self.assertEqual(desk, (0, "shadow"))
        self.assertEqual((count, audit), (1, 1))

    def test_existing_mismatched_url_refused_without_overwrite(self):
        dest = self.root / "copy.db"
        create_db(dest)
        plan = pilot.candidates(evidence(), approval())
        provenance = {"state_commit": COMMIT, "state_tree": TREE}
        pilot.apply_to_copy(dest, plan, approval(), provenance)
        plan[0]["version"]["text_original"] = "Later tampered text"
        with self.assertRaisesRegex(pilot.Refused, "different"):
            pilot.apply_to_copy(dest, plan, approval(), provenance)
        with sqlite3.connect(dest) as con:
            self.assertEqual(con.execute("SELECT text_original FROM articles WHERE url=?",
                                         (URL,)).fetchone()[0],
                             "Vietnamese text as captured from the publisher")

    def test_refuses_missing_or_unmigrated_destination(self):
        plan = pilot.candidates(evidence(), approval())
        provenance = {"state_commit": COMMIT, "state_tree": TREE}
        with self.assertRaisesRegex(pilot.Refused, "existing migrated"):
            pilot.apply_to_copy(self.root / "missing.db", plan, approval(), provenance)
        dest = self.root / "empty.db"
        sqlite3.connect(dest).close()
        with self.assertRaisesRegex(pilot.Refused, "not been migrated"):
            pilot.apply_to_copy(dest, plan, approval(), provenance)


if __name__ == "__main__":
    unittest.main()
