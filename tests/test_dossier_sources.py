"""B1.2 private source-parity tests: entirely fabricated text and SQLite rows."""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.dossier_sources import reconcile_dossier_sources

FIXTURE = Path(__file__).parent / "fixtures/dossiers/fictional-exercise-reporting.json"
BODIES = {
    900001: "THIS IS A FABRICATED ALPHA RELEASE USED ONLY FOR TESTS. " * 8,
    900002: "THIS IS A FABRICATED BETA RELEASE USED ONLY FOR TESTS. " * 8,
}


def draft():
    sc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for src in sc["sources"]:
        src["stored_original_sha256"] = hashlib.sha256(
            BODIES[src["record_id"]].encode("utf-8")
        ).hexdigest()
    return sc


def fake_registry():
    entries = []
    for name in ("alpha", "beta"):
        entries.append(SimpleNamespace(
            slug="fixture-" + name,
            public=True, is_collecting=True, has_production_records=True,
            sources=[SimpleNamespace(
                slug=f"fixture-{name}-releases",
                institution_id=f"fixture-ministry-{name}",
                base_url="https://example.org",
                language_tag="en", enabled=True, contract_validated=True,
            )],
        ))
    return entries


def synthetic_sqlite(path):
    """Make a never-published minimal subset of the real SQL join shape."""
    with sqlite3.connect(path) as db:
        db.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE sources (
                id INTEGER PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                desk_id TEXT NOT NULL,
                institution_id TEXT NOT NULL,
                language_tag TEXT NOT NULL,
                enabled INTEGER NOT NULL
            );
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY,
                source_id INTEGER NOT NULL REFERENCES sources(id),
                title_original TEXT,
                text_original TEXT,
                published_date TEXT,
                url TEXT,
                passed_relevance INTEGER
            );
        """)
        db.executemany(
            "INSERT INTO sources VALUES(?, ?, ?, ?, ?, ?)", [
                (1, "fixture-alpha-releases", "fixture-alpha", "fixture-ministry-alpha", "en", 1),
                (2, "fixture-beta-releases", "fixture-beta", "fixture-ministry-beta", "en", 1),
            ])
        db.executemany(
            "INSERT INTO articles VALUES(?, ?, ?, ?, ?, ?, ?)", [
                (900001, 1, "Fictional first source", BODIES[900001],
                 "2026-08-12", "https://example.org/hypothetical-alpha", None),
                (900002, 2, "Fictional second source", BODIES[900002],
                 "2026-09-07", "https://example.org/hypothetical-beta", 1),
            ])
        db.commit()


def codes(result, category):
    return [x["code"] for x in result[category]]


class SourceParitySyntheticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "fake.db"
        synthetic_sqlite(self.path)
        self.doc = draft()
        self.registry = fake_registry()

    def scan(self, doc=None, registry=None, db_path=None):
        return reconcile_dossier_sources(
            self.doc if doc is None else doc,
            self.path if db_path is None else db_path,
            self.registry if registry is None else registry,
        )

    def change_db(self, sql, args=()):
        with sqlite3.connect(self.path) as db:
            db.execute(sql, args)
            db.commit()

    def test_fictional_two_source_parity_passes_but_not_publication(self):
        report = self.scan()
        self.assertTrue(report["archive_reconciled"])
        self.assertFalse(report["eligible_for_publication"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["selected_record_ids"], [900001, 900002])

    def test_reports_pending_and_analyzed_without_promotion(self):
        report = self.scan()
        self.assertEqual([x["model_screening"] for x in report["evidence"]],
                         ["pending", "selected"])
        self.assertIn("screening-pending-human-review", codes(report, "holds"))
        self.assertIn("independent-source-admission-required", codes(report, "holds"))

    def test_missing_or_forged_editorial_and_rights_refs_never_grant_permission(self):
        doc = copy.deepcopy(self.doc)
        for src in doc["sources"]:
            src["editorial_admission_ref"] = "fabricated-human-receipt"
            src["source_use_decision_ref"] = "fabricated-publisher-permission"
        report = self.scan(doc)
        self.assertTrue(report["archive_reconciled"])
        self.assertFalse(report["eligible_for_publication"])
        self.assertEqual(codes(report, "holds").count(
            "independent-source-use-decision-required"), 2)

    def test_forged_approved_sidecar_still_held(self):
        from tests.test_dossier_contract import approved
        doc = approved()
        for src in doc["sources"]:
            src["stored_original_sha256"] = hashlib.sha256(
                BODIES[src["record_id"]].encode("utf-8")
            ).hexdigest()
        from core.dossier_contract import dossier_content_digest
        doc["approval"]["content_sha256"] = dossier_content_digest(doc)
        report = self.scan(doc)
        self.assertTrue(report["archive_reconciled"])
        self.assertFalse(report["eligible_for_publication"])
        self.assertIn("independently-authenticated-editorial-approval-required",
                      codes(report, "holds"))

    def test_source_record_missing_detected(self):
        self.change_db("DELETE FROM articles WHERE id=?", (900002,))
        report = self.scan()
        self.assertFalse(report["archive_reconciled"])
        self.assertIn("source-record-missing", codes(report, "errors"))

    def test_orphan_wrong_archive_id_does_not_fallback(self):
        doc = copy.deepcopy(self.doc)
        doc["sources"][1]["record_id"] = 900099
        doc["sections"][0]["claims"][1]["source_record_ids"] = [900099]
        doc["sections"][1]["claims"][0]["source_record_ids"] = [900001, 900099]
        report = self.scan(doc)
        self.assertFalse(report["archive_reconciled"])
        self.assertIn("source-record-missing", codes(report, "errors"))

    def test_title_bytes_are_not_pinned_by_body_only_sha(self):
        first = self.scan()
        self.assertTrue(first["archive_reconciled"])
        title_holds = [h for h in first["holds"]
                       if h["code"] == "publisher-title-continuity-unpinned"]
        self.assertEqual([x["record_id"] for x in title_holds], [900001, 900002])
        # Deliberately alter the archived title without touching original body.
        # A body-only pin cannot make an integrity claim about title continuity.
        self.change_db(
            "UPDATE articles SET title_original=? WHERE id=?",
            ("Different imaginary title", 900001)
        )
        changed = self.scan()
        self.assertTrue(changed["archive_reconciled"])
        self.assertIn(
            {"code": "publisher-title-continuity-unpinned", "record_id": 900001},
            changed["holds"],
        )
        self.assertFalse(changed["eligible_for_publication"])

    def test_registered_publisher_hostname_mismatch_is_review_hold(self):
        registry = fake_registry()
        registry[0].sources[0].base_url = "https://official-fiction.example.invalid"
        review = self.scan(registry=registry)
        self.assertTrue(review["archive_reconciled"])
        self.assertIn(
            {"code": "publisher-origin-differs-from-registry", "record_id": 900001},
            review["holds"],
        )
        self.assertFalse(review["eligible_for_publication"])

    def test_lookalike_host_not_treated_as_registered_subdomain(self):
        self.change_db(
            "UPDATE articles SET url=? WHERE id=900001",
            ("https://example.org.evil.invalid/fake",)
        )
        d = copy.deepcopy(self.doc)
        d["sources"][0]["url"] = "https://example.org.evil.invalid/fake"
        review = self.scan(doc=d)
        self.assertTrue(review["archive_reconciled"])
        self.assertIn("publisher-origin-differs-from-registry", codes(review, "holds"))

    def test_missing_registered_origin_is_not_silently_verified(self):
        registry = fake_registry()
        registry[0].sources[0].base_url = None
        review = self.scan(registry=registry)
        self.assertTrue(review["archive_reconciled"])
        self.assertIn(
            {"code": "publisher-origin-unverified-human-review", "record_id": 900001},
            review["holds"],
        )

    def test_registered_publisher_subdomain_can_match_without_rights_grant(self):
        self.change_db(
            "UPDATE articles SET url=? WHERE id=900001",
            ("https://news.example.org/fake-release",)
        )
        d = copy.deepcopy(self.doc)
        d["sources"][0]["url"] = "https://news.example.org/fake-release"
        review = self.scan(doc=d)
        self.assertTrue(review["archive_reconciled"])
        self.assertNotIn(
            "publisher-origin-differs-from-registry", codes(review, "holds")
        )
        self.assertIn("independent-source-use-decision-required", codes(review, "holds"))
        self.assertFalse(review["eligible_for_publication"])

    def test_title_missing_rejected(self):
        self.change_db("UPDATE articles SET title_original='' WHERE id=900001")
        self.assertIn("source-original-title-missing", codes(self.scan(), "errors"))

    def test_missing_original_body_rejected(self):
        self.change_db("UPDATE articles SET text_original=NULL WHERE id=900001")
        self.assertIn("source-original-text-missing", codes(self.scan(), "errors"))

    def test_original_body_drift_even_if_other_metadata_unchanged(self):
        self.change_db("UPDATE articles SET text_original=? WHERE id=900001",
                       ("CHANGED BODY " * 25,))
        self.assertIn("source-original-body-drift", codes(self.scan(), "errors"))

    def test_source_publication_date_mismatch(self):
        self.change_db("UPDATE articles SET published_date=? WHERE id=900001",
                       ("2026-08-13",))
        self.assertIn("source-published-on-mismatch", codes(self.scan(), "errors"))

    def test_source_url_mismatch(self):
        self.change_db("UPDATE articles SET url=? WHERE id=900001",
                       ("https://example.org/changed",))
        self.assertIn("source-url-mismatch", codes(self.scan(), "errors"))

    def test_wrong_language_detected(self):
        self.change_db("UPDATE sources SET language_tag=? WHERE id=1", ("fr",))
        report = self.scan()
        self.assertIn("source-language-mismatch", codes(report, "errors"))
        self.assertIn("source-not-public-eligible", codes(report, "errors"))

    def test_wrong_issuer_detected(self):
        self.change_db("UPDATE sources SET institution_id=? WHERE id=1", ("elsewhere",))
        report = self.scan()
        self.assertIn("source-institution-id-mismatch", codes(report, "errors"))
        self.assertIn("source-not-public-eligible", codes(report, "errors"))

    def test_shadow_desk_rejected(self):
        registry = fake_registry()
        registry[0].public = False
        self.assertIn("source-not-public-eligible",
                      codes(self.scan(registry=registry), "errors"))

    def test_not_collecting_desk_rejected(self):
        registry = fake_registry()
        registry[0].is_collecting = False
        self.assertIn("source-not-public-eligible",
                      codes(self.scan(registry=registry), "errors"))

    def test_source_manifest_not_contract_validated(self):
        registry = fake_registry()
        registry[0].sources[0].contract_validated = False
        self.assertIn("source-not-public-eligible",
                      codes(self.scan(registry=registry), "errors"))

    def test_disabled_database_source_rejected(self):
        self.change_db("UPDATE sources SET enabled=0 WHERE id=1")
        self.assertIn("source-not-public-eligible", codes(self.scan(), "errors"))

    def test_model_not_selected_requires_human_review_not_db_rewrite(self):
        self.change_db("UPDATE articles SET passed_relevance=0 WHERE id=900001")
        report = self.scan()
        self.assertIn("screening-not-selected-human-review", codes(report, "holds"))
        self.assertTrue(report["archive_reconciled"])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT passed_relevance FROM articles WHERE id=900001"
            ).fetchone()[0], 0)

    def test_unexpected_screening_state_fails(self):
        self.change_db("UPDATE articles SET passed_relevance=6 WHERE id=900001")
        self.assertIn("invalid-screening-state", codes(self.scan(), "errors"))

    def test_no_original_bodies_returned_even_on_failure(self):
        self.change_db("UPDATE articles SET text_original=? WHERE id=900001",
                       ("SECRET_FAKE_PUBLISHER_TEXT " * 16,))
        report = self.scan()
        self.assertNotIn("SECRET_FAKE_PUBLISHER_TEXT", json.dumps(report))

    def test_original_database_digest_unchanged_and_no_sidecars(self):
        original = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.scan()
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),
                         original)
        self.assertFalse(Path(str(self.path) + "-wal").exists())
        self.assertFalse(Path(str(self.path) + "-shm").exists())

    def test_missing_or_invalid_db_fails_closed(self):
        missing = Path(self.tmp.name) / "not-found.db"
        self.assertIn("archive-unavailable",
                      codes(self.scan(db_path=missing), "errors"))
        corrupt = Path(self.tmp.name) / "corrupt.db"
        corrupt.write_text("NOT A SQLITE DATABASE", encoding="utf-8")
        self.assertIn("archive-query-failed",
                      codes(self.scan(db_path=corrupt), "errors"))

    def test_bogus_non_registry_source_not_eligible(self):
        doc = copy.deepcopy(self.doc)
        registry = fake_registry()
        registry[0].sources[0].enabled = False
        self.assertIn("source-not-public-eligible",
                      codes(self.scan(doc, registry), "errors"))


if __name__ == "__main__":
    unittest.main()
