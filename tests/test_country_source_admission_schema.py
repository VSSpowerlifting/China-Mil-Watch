"""Synthetic-only source-admission schema and checkpoint boundary contracts."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.inspect_country_admission_boundary import (
    AdmissionSchemaRefused, bind_checkpoint, inspect_database, load_checkpoint,
    plan, SOURCE_CONTRACTS, SCHEMA,
)

SOURCE_SHAS = {
    "vn_mps_foreign_affairs_vi": "1" * 40,
    "vn_moit_energy_vi": "2" * 40,
    "vn_moit_foundational_industry_vi": "3" * 40,
}


def checkpoint(desk="philippines_afp", status="candidate_for_human_checkpoint"):
    common = {
        "schema": "ipr-country-desk-checkpoint-intake/1",
        "desk": desk, "as_of_utc": "2026-10-13" if desk == "philippines_afp" else "2026-10-14",
        "checkpoint": "day-07",
        "machine_status": status, "machine_holds": [],
        "external_holds": ["written_owner_source_admission_and_release_decisions",
                           "separate_source_action_rights_and_robots_review"],
        "human_checkpoint_authenticated": False,
        "complete_Actions_history_authenticated": False,
        "source_reuse_rights_approved": False,
        "private_custody_approved": False,
        "C13_satisfied": False,
        "production_eligible": False,
        "public_records_admitted": False,
        "weekly_model_eligible": False,
        "desk_activated": False,
        "deployment_authorized": False,
        "source_or_output_writes": 0,
    }
    if desk == "philippines_afp":
        common["machine_evidence"] = {
            "state_commit": "a" * 40, "window": ["2026-10-07", "2026-10-13"],
            "verified_ledger_slots": 7, "positive_Actions_matches": 7,
        }
    else:
        common["machine_evidence"] = {
            "sources": [{
                "slug": slug, "state_commit": digest,
                "checkpoint_reached_elapsed_time_only": True,
            } for slug, digest in SOURCE_SHAS.items()]
        }
    return common


def create_db(path, *, unique=True, existing=None, row=None):
    with sqlite3.connect(str(path)) as cx:
        cx.executescript("""
            CREATE TABLE sources (
                id INTEGER PRIMARY KEY, slug TEXT, display_name TEXT,
                base_url TEXT, language TEXT, desk_id TEXT, institution_id TEXT,
                language_tag TEXT, authority_tier TEXT, enabled INTEGER
            );
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY, url TEXT, content_hash TEXT,
                source_id INTEGER, title_original TEXT, text_original TEXT,
                published_date TEXT, scraped_at TEXT, processing_state TEXT
            );
        """)
        if unique:
            cx.executescript("""
                CREATE UNIQUE INDEX source_slug_unique ON sources(slug);
                CREATE UNIQUE INDEX article_url_unique ON articles(url);
            """)
        if existing:
            cx.execute("INSERT INTO sources (slug) VALUES (?)", (existing,))
        if row:
            cx.execute("INSERT INTO articles (url, text_original) VALUES (?,?)",
                       ("https://private.synthetic.invalid/secret", row))


class SchemaAdmissionContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "copy.db"
        create_db(self.db)

    def test_AFP_compatible_schema_does_not_admit_or_publish_records(self):
        before = self.db.read_bytes()
        report = plan("ph_afp_articles", checkpoint(), self.db)
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["schema_preflight"], "structure_compatible_no_admission")
        self.assertTrue(report["production_schema_checks"]["schema_compatible"])
        self.assertEqual(report["pinned_source_commit"], "a" * 40)
        self.assertEqual(report["production_source_slug_collisions"], 0)
        self.assertEqual(report["production_database_sha256"],
                         hashlib.sha256(before).hexdigest())
        self.assertFalse(report["production_write_authorized"])
        self.assertFalse(report["public_record_projection_authorized"])
        self.assertFalse(report["website_or_model_release_authorized"])
        self.assertFalse(report["human_review_authenticated"])
        self.assertEqual(report["candidate_records_imported"], 0)
        self.assertEqual(before, self.db.read_bytes())
        self.assertFalse(Path(str(self.db) + "-wal").exists())

    def test_Vietnam_MPS_uses_own_exact_sha_not_MOIT_sha(self):
        r = plan("vn_mps_foreign_affairs_vi", checkpoint("vietnam_three_ministry_sources"), self.db)
        self.assertEqual(r["pinned_source_commit"], SOURCE_SHAS["vn_mps_foreign_affairs_vi"])
        self.assertEqual(r["desk_slug"], "vietnam")

    def test_each_MOIT_family_has_irreducible_rights_hold(self):
        c = checkpoint("vietnam_three_ministry_sources")
        for source in ("vn_moit_energy_vi", "vn_moit_foundational_industry_vi"):
            with self.subTest(source=source):
                r = plan(source, c, self.db)
                self.assertEqual(r["schema_preflight"], "blocked_before_any_ingest")
                self.assertIn("MOIT_source_rights_and_robots_remain_held", r["holds"])
                self.assertFalse(r["source_rights_authorized"])

    def test_real_source_sha_drift_is_refused(self):
        c = checkpoint("vietnam_three_ministry_sources")
        c["machine_evidence"]["sources"][0]["state_commit"] = "too-short"
        with self.assertRaisesRegex(AdmissionSchemaRefused, "invalid_Vietnam_source_state"):
            plan("vn_mps_foreign_affairs_vi", c, self.db)

    def test_unreviewed_machine_checkpoint_holds_even_with_compatible_schema(self):
        c = checkpoint(status="machine_evidence_incomplete_or_held")
        c["machine_holds"] = ["missing_or_invalid_AFP_ledger_2026-10-11"]
        r = plan("ph_afp_articles", c, self.db)
        self.assertIn("source_machine_checkpoint_unreconciled_or_held", r["holds"])
        self.assertIn("source_machine_checkpoint_has_unresolved_holds", r["holds"])

    def test_future_checkpoint_cannot_be_marked_structurally_green_early(self):
        afp = checkpoint()
        afp["as_of_utc"] = "2026-10-12"
        with self.assertRaisesRegex(AdmissionSchemaRefused, "source_checkpoint_not_yet_due"):
            plan("ph_afp_articles", afp, self.db)
        vn = checkpoint("vietnam_three_ministry_sources")
        vn["as_of_utc"] = "2026-10-13"
        with self.assertRaisesRegex(AdmissionSchemaRefused, "source_checkpoint_not_yet_due"):
            plan("vn_mps_foreign_affairs_vi", vn, self.db)
        vn = checkpoint("vietnam_three_ministry_sources")
        vn["checkpoint"] = "day-30"
        with self.assertRaisesRegex(AdmissionSchemaRefused, "source_checkpoint_not_yet_due"):
            plan("vn_moit_energy_vi", vn, self.db)

    def test_wrong_desk_refused_instead_of_borrowing_AFP_clock(self):
        with self.assertRaisesRegex(AdmissionSchemaRefused, "wrong_desk_checkpoint_receipt"):
            plan("vn_mps_foreign_affairs_vi", checkpoint(), self.db)
        with self.assertRaisesRegex(AdmissionSchemaRefused, "undeclared_source_family"):
            bind_checkpoint(checkpoint(), "ph_nsc_press_releases")

    def test_authority_forgery_and_missing_release_holds_refused(self):
        c = checkpoint()
        c["production_eligible"] = True
        with self.assertRaisesRegex(AdmissionSchemaRefused, "checkpoint_authority_claim"):
            bind_checkpoint(c, "ph_afp_articles")
        c = checkpoint()
        c["external_holds"] = ["owner_signed"]
        with self.assertRaisesRegex(AdmissionSchemaRefused, "missing_external_release_holds"):
            bind_checkpoint(c, "ph_afp_articles")

    def test_missing_uniqueness_is_a_hold_not_a_green_schema(self):
        no_index = self.root / "missing-index.db"
        create_db(no_index, unique=False)
        r = plan("ph_afp_articles", checkpoint(), no_index)
        self.assertIn("production_schema_contract_not_satisfied", r["holds"])
        self.assertFalse(r["production_schema_checks"]["unique_article_canonical_url_index"])
        self.assertFalse(r["production_schema_checks"]["unique_source_slug_index"])

    def test_previously_registered_production_source_is_collision_hold(self):
        present = self.root / "registered.db"
        create_db(present, existing="ph_afp_articles")
        r = plan("ph_afp_articles", checkpoint(), present)
        self.assertEqual(r["production_source_slug_collisions"], 1)
        self.assertIn("production_source_slug_already_registered_review_collision", r["holds"])

    def test_no_body_or_url_leaks_into_report(self):
        secret = "NEVER_EMIT_REAL_ARTICLE_TEXT_AAADDH340305"
        db = self.root / "secret.db"
        create_db(db, row=secret)
        c = checkpoint()
        c["synthetic_extra_private_text"] = secret
        r = plan("ph_afp_articles", c, db)
        rendered = json.dumps(r)
        self.assertNotIn(secret, rendered)
        self.assertNotIn("https://private.synthetic.invalid/secret", rendered)
        self.assertFalse(r["record_collisions_audited"])

    def test_checkpoint_JSON_duplicate_keys_and_symlink_are_refused(self):
        dup = self.root / "duplicate.json"
        dup.write_text('{"schema":"first","schema":"second"}')
        with self.assertRaisesRegex(AdmissionSchemaRefused, "duplicate_json_key"):
            load_checkpoint(dup)
        good = self.root / "good.json"
        good.write_text(json.dumps(checkpoint()))
        symlink = self.root / "link.json"
        symlink.symlink_to(good)
        with self.assertRaisesRegex(AdmissionSchemaRefused, "invalid_checkpoint_file"):
            load_checkpoint(symlink)

    def test_database_symlink_and_WAL_sidecar_are_refused(self):
        alias = self.root / "alias.db"
        alias.symlink_to(self.db)
        with self.assertRaisesRegex(AdmissionSchemaRefused, "invalid_production_database_file"):
            plan("ph_afp_articles", checkpoint(), alias)
        wal = Path(str(self.db) + "-wal")
        wal.write_bytes(b"synthetic wal")
        with self.assertRaisesRegex(AdmissionSchemaRefused, "production_database_has_live_sidecars"):
            plan("ph_afp_articles", checkpoint(), self.db)
        wal.unlink()
        journal = Path(str(self.db) + "-journal")
        journal.write_bytes(b"synthetic pending rollback")
        with self.assertRaisesRegex(AdmissionSchemaRefused, "production_database_has_live_sidecars"):
            plan("ph_afp_articles", checkpoint(), self.db)

    def test_exact_schema_probe_does_not_change_disk(self):
        before = hashlib.sha256(self.db.read_bytes()).digest()
        s, existing = inspect_database(self.db, "ph_afp_articles")
        self.assertTrue(s["schema_compatible"])
        self.assertEqual(existing, 0)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).digest(), before)
        self.assertFalse(Path(str(self.db) + "-shm").exists())

    def test_repo_schema_probe_reads_columns_only_and_does_not_claim_approval(self):
        root = Path(__file__).resolve().parents[1]
        prod = root / "pla_watch.db"
        self.assertTrue(prod.is_file())
        schema, count = inspect_database(prod, "ph_afp_articles")
        self.assertEqual(set(schema), {
            "source_required_columns_present",
            "article_required_columns_present",
            "unique_source_slug_index",
            "unique_article_canonical_url_index", "schema_compatible",
        })
        self.assertTrue(schema["schema_compatible"], schema)
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
