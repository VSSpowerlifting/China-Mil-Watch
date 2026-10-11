"""Offline synthetic records: country URL collisions cannot import or authorize."""
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import audit_country_source_url_collisions as audit
from scripts.inspect_country_admission_boundary import plan
from tests.test_country_source_admission_schema import checkpoint, create_db

AFP_SOURCE = "ph_afp_articles"
MPS_SOURCE = "vn_mps_foreign_affairs_vi"
AFP_URL = "https://www.afp.mil.ph/news/synthetic-scope-check"
MPS_URL = "https://bocongan.gov.vn/bai-viet/example-1234567890"


def candidate(source, s3, rows=None):
    if rows is None:
        if source == AFP_SOURCE:
            rows = [{"source_identity": "afp:1395", "canonical_url": AFP_URL,
                     "publisher_date": "2026-10-06"}]
        else:
            rows = [{"source_identity": "mps-vi:1234567890", "canonical_url": MPS_URL,
                     "publisher_date": "2026-10-06"}]
    return {
        "schema": audit.CANDIDATES_SCHEMA,
        "source_slug": source,
        "state_commit": s3["pinned_source_commit"],
        "checkpoint_receipt_sha256": s3["checkpoint_receipt_sha256"],
        "production_database_sha256": s3["production_database_sha256"],
        "records": rows,
    }


class CountrySourceCanonicalURLContracts(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / "production-copy.db"
        create_db(self.db)

    def paired(self, source=AFP_SOURCE, rows=None):
        cp = checkpoint("philippines_afp" if source == AFP_SOURCE
                        else "vietnam_three_ministry_sources")
        s3 = plan(source, cp, self.db)
        return s3, candidate(source, s3, rows)

    def test_clean_AFP_supplied_URL_is_not_approval(self):
        s3, inventory = self.paired()
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        report = audit.compare(s3, inventory, self.db)
        self.assertEqual(report["source_slug"], AFP_SOURCE)
        self.assertEqual(report["candidate_URL_outcomes"]["new_URLs"], 1)
        self.assertEqual(report["production_database_sha256"], before)
        self.assertEqual(report["candidate_records_supplied"], 1)
        self.assertEqual(report["collision_rehearsal"],
                         "supplied_URLs_no_detected_collisions_not_an_admission")
        for flag in ("entire_source_corpus_inventory_verified",
                     "AFP_numeric_id_to_public_slug_authenticated",
                     "human_original_review_authenticated",
                     "publisher_source_rights_approved", "record_promotion_authorized",
                     "private_custody_established", "public_projection_authorized",
                     "weekly_AI_authorized", "deployment_authorized"):
            self.assertIs(report[flag], False)
        self.assertEqual(report["records_imported"], 0)
        self.assertEqual(report["database_or_output_writes"], 0)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)

    def test_MPS_exact_publisher_derived_ID(self):
        s3, inventory = self.paired(MPS_SOURCE)
        result = audit.compare(s3, inventory, self.db)
        self.assertEqual(result["candidate_URL_outcomes"]["new_URLs"], 1)
        self.assertEqual(result["state_commit"], "1" * 40)
        self.assertFalse(result["human_original_review_authenticated"])

    def test_MPS_forged_numeric_ID_is_refused(self):
        s3, inv = self.paired(MPS_SOURCE)
        inv["records"][0]["source_identity"] = "mps-vi:9999999999"
        with self.assertRaisesRegex(audit.CollisionRefused, "MPS_url_derived_identity_mismatch"):
            audit.compare(s3, inv, self.db)

    def test_AFP_API_ID_public_slug_pair_not_pretended_verified(self):
        s3, inv = self.paired()
        inv["records"][0]["source_identity"] = "afp:2002"
        result = audit.compare(s3, inv, self.db)
        self.assertIs(result["AFP_numeric_id_to_public_slug_authenticated"], False)

    def test_same_source_URL_is_existing_and_requires_idempotency_review(self):
        with sqlite3.connect(self.db) as cx:
            cx.execute("INSERT INTO sources (id, slug) VALUES (1, ?)", (AFP_SOURCE,))
            cx.execute("INSERT INTO articles (source_id,url,text_original) VALUES (?,?,?)",
                       (1, AFP_URL, "SECRET SYNTHETIC ARTICLE BODY"))
        s3, inv = self.paired()
        before = self.db.read_bytes()
        result = audit.compare(s3, inv, self.db)
        self.assertEqual(result["candidate_URL_outcomes"]["already_present_same_source"], 1)
        self.assertIn("same_source_existing_URLs_require_idempotence_review", result["holds"])
        self.assertIn("source_slug_already_exists_requires_source_registration_review", result["holds"])
        self.assertEqual(before, self.db.read_bytes())
        self.assertNotIn("SECRET SYNTHETIC ARTICLE BODY", json.dumps(result))

    def test_other_source_claiming_same_URL_is_foreign_collision(self):
        with sqlite3.connect(self.db) as cx:
            cx.execute("INSERT INTO sources (id, slug) VALUES (2, ?)", ("sg_mindef",))
            cx.execute("INSERT INTO articles (source_id,url) VALUES (?,?)", (2, AFP_URL))
        s3, inv = self.paired()
        r = audit.compare(s3, inv, self.db)
        self.assertEqual(r["candidate_URL_outcomes"]["foreign_source_URL_collisions"], 1)
        self.assertIn("foreign_source_URL_collisions_require_human_resolution", r["holds"])

    def test_orphan_production_article_is_visible_as_count_only(self):
        with sqlite3.connect(self.db) as cx:
            cx.execute("INSERT INTO articles (source_id,url) VALUES (?,?)",
                       (9876543, AFP_URL))
        s3, inv = self.paired()
        r = audit.compare(s3, inv, self.db)
        self.assertEqual(r["candidate_URL_outcomes"]["orphan_source_URL_collisions"], 1)
        self.assertIn("orphan_source_URL_collisions_require_schema_repair", r["holds"])

    def test_two_distinct_candidate_URLs_are_counted_separately(self):
        s3, _ = self.paired()
        rows = [{"source_identity": "afp:1395", "canonical_url": AFP_URL,
                 "publisher_date": "2026-10-06"},
                {"source_identity": "afp:1396",
                 "canonical_url": "https://www.afp.mil.ph/news/second-synthetic",
                 "publisher_date": "2026-10-07"}]
        inv = candidate(AFP_SOURCE, s3, rows)
        r = audit.compare(s3, inv, self.db)
        self.assertEqual(r["candidate_URL_outcomes"]["new_URLs"], 2)

    def test_duplicate_identity_or_URL_refused_not_collapsed(self):
        s3, inv = self.paired()
        inv["records"] *= 2
        with self.assertRaisesRegex(audit.CollisionRefused, "duplicate_candidate_identity"):
            audit.compare(s3, inv, self.db)
        s3, inv = self.paired()
        inv["records"].append({"source_identity": "afp:2002",
                               "canonical_url": AFP_URL,
                               "publisher_date": "2026-10-06"})
        with self.assertRaisesRegex(audit.CollisionRefused, "duplicate_candidate_identity"):
            audit.compare(s3, inv, self.db)

    def test_invalid_URLs_are_rejected_without_rewriting_them(self):
        cases = [
            "https://evil.invalid/news/synthetic-scope-check",
            "http://www.afp.mil.ph/news/synthetic-scope-check",
            "https://www.afp.mil.ph/news/synthetic-scope-check?token=1",
            "https://www.afp.mil.ph:443/news/synthetic-scope-check",
            "https://www.afp.mil.ph/news/../news/synthetic-scope-check",
            "https://www.afp.mil.ph/news/synthetic%2fscope",
            "https://www.afp.mil.ph/news/Synthetic-Scope",
            "https://evil.invalid@www.afp.mil.ph/news/synthetic-scope-check",
            "https://www.afp.mil.ph/news/synthetic-scope-check#fragment",
        ]
        for url in cases:
            with self.subTest(url=url):
                s3, inv = self.paired()
                inv["records"][0]["canonical_url"] = url
                with self.assertRaisesRegex(audit.CollisionRefused, "candidate_not_in_AFP"):
                    audit.compare(s3, inv, self.db)

    def test_MPS_host_and_path_are_source_scoped(self):
        for url in [
            "https://moit.gov.vn/bai-viet/example-1234567890",
            "https://bocongan.gov.vn/tin-tuc/example-1234567890",
            "https://bocongan.gov.vn/bai-viet/example-1234567890?view=1",
        ]:
            with self.subTest(url=url):
                s3, inv = self.paired(MPS_SOURCE)
                inv["records"][0]["canonical_url"] = url
                with self.assertRaisesRegex(audit.CollisionRefused, "candidate_not_in_MPS"):
                    audit.compare(s3, inv, self.db)

    def test_input_wrong_state_commit_and_database_snapshot_refused(self):
        s3, inv = self.paired()
        inv["state_commit"] = "f" * 40
        with self.assertRaisesRegex(audit.CollisionRefused, "candidate_metadata_does_not_match"):
            audit.compare(s3, inv, self.db)
        s3, inv = self.paired()
        inv["production_database_sha256"] = "0" * 64
        with self.assertRaisesRegex(audit.CollisionRefused, "candidate_metadata_does_not_match"):
            audit.compare(s3, inv, self.db)

    def test_stale_database_even_if_schema_and_source_row_unchanged_refused(self):
        s3, inv = self.paired()
        with sqlite3.connect(self.db) as cx:
            cx.execute("INSERT INTO articles (url,text_original) VALUES (?,?)",
                       ("https://other.invalid/synthetic", "unpublished synthetic"))
        with self.assertRaisesRegex(audit.CollisionRefused, "production_snapshot_differs"):
            audit.compare(s3, inv, self.db)

    def test_fake_S3_permissions_and_preflight_counts_refused(self):
        s3, inv = self.paired()
        s3["record_promotion_authorized"] = True
        with self.assertRaisesRegex(audit.CollisionRefused, "unexpected_or_missing_S3_report_fields"):
            audit.compare(s3, inv, self.db)
        s3, inv = self.paired()
        s3["production_source_slug_collisions"] = 1
        with self.assertRaisesRegex(audit.CollisionRefused, "production_source_registration_or_schema_changed"):
            audit.compare(s3, inv, self.db)

    def test_MOIT_and_NSC_are_out_of_scope_even_if_schema_ready(self):
        for slug in ("vn_moit_energy_vi", "vn_moit_foundational_industry_vi",
                     "ph_nsc_press_releases"):
            with self.subTest(slug=slug):
                with self.assertRaisesRegex(audit.CollisionRefused, "not_in_collision_rehearsal_scope"):
                    audit.bind_s3({"schema": audit.S3_SCHEMA}, slug)

    def test_candidate_input_cannot_smuggle_body_or_publisher_notes(self):
        s3, inv = self.paired()
        inv["records"][0]["text_original"] = "SECRET PUBLISHER TEXT"
        with self.assertRaisesRegex(audit.CollisionRefused, "extra_or_missing_fields"):
            audit.compare(s3, inv, self.db)
        s3, inv = self.paired()
        inv["owner_approved"] = True
        with self.assertRaisesRegex(audit.CollisionRefused, "invalid_candidate_inventory_schema"):
            audit.compare(s3, inv, self.db)

    def test_empty_and_unbounded_inventories_refused(self):
        s3, inv = self.paired()
        inv["records"] = []
        with self.assertRaisesRegex(audit.CollisionRefused, "candidate_count_out_of_bounds"):
            audit.compare(s3, inv, self.db)
        s3, inv = self.paired()
        inv["records"] = [inv["records"][0]] * 4001
        with self.assertRaisesRegex(audit.CollisionRefused, "candidate_count_out_of_bounds"):
            audit.compare(s3, inv, self.db)

    def test_input_file_rejects_duplicate_keys_and_symlinks(self):
        bad = self.root / "dupe.json"
        bad.write_text('{"source_slug":"ph_afp_articles","source_slug":"wrong"}')
        with self.assertRaisesRegex(audit.AdmissionSchemaRefused, "duplicate_json_key"):
            audit.load_private_file(bad)
        valid = self.root / "valid.json"
        valid.write_text(json.dumps(self.paired()[1]))
        symlink = self.root / "alias.json"
        symlink.symlink_to(valid)
        with self.assertRaisesRegex(audit.CollisionRefused, "input_must_be_regular_file"):
            audit.load_private_file(symlink)

    def test_live_sidecars_refused(self):
        s3, inv = self.paired()
        for extension in ("-wal", "-shm", "-journal"):
            p = Path(str(self.db) + extension)
            p.write_bytes(b"unsettled")
            try:
                with self.assertRaisesRegex(audit.CollisionRefused, "transaction_sidecars"):
                    audit.compare(s3, inv, self.db)
            finally:
                p.unlink()

    def test_malformed_candidate_publisher_date_refused(self):
        s3, inv = self.paired()
        inv["records"][0]["publisher_date"] = "10/06/2026"
        with self.assertRaisesRegex(audit.CollisionRefused, "candidate_publisher_date_invalid"):
            audit.compare(s3, inv, self.db)

    def test_incorrect_S3_unique_index_claim_is_not_trusted(self):
        db = self.root / "no-url-index.db"
        create_db(db, unique=False)
        s3 = plan(AFP_SOURCE, checkpoint(), db)
        inv = candidate(AFP_SOURCE, s3)
        with self.assertRaisesRegex(audit.CollisionRefused, "structurally_compatible_schema"):
            audit.compare(s3, inv, db)

    def test_metadata_report_redacts_all_source_URLs_and_bodies(self):
        with sqlite3.connect(self.db) as cx:
            cx.execute("INSERT INTO articles(url,text_original) VALUES (?,?)",
                       (AFP_URL, "PRIVATE_FAKE_BODY_THAT_MUST_NOT_APPEAR"))
        s3, inv = self.paired()
        r = audit.compare(s3, inv, self.db)
        output = json.dumps(r)
        self.assertNotIn(AFP_URL, output)
        self.assertNotIn("PRIVATE_FAKE_BODY", output)
        self.assertNotIn("afp:1395", output)
        self.assertNotIn("www.afp.mil.ph", output)
        self.assertEqual(sum(r["candidate_URL_outcomes"].values()), 1)


if __name__ == "__main__":
    unittest.main()
