"""Standing-scope synthetic MND metadata checks. No publisher, live DB or HWPX."""
import copy
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core import korea_official_metadata_admission as admission
from core.korea_official_live_links import load_live_korea_official_links
from migrations.versions import m0008_korea_official_source_metadata as schema


def packet(ids=None):
    ids = ids or [str(156799901 + n) for n in range(5)]
    result = {
        "schema": "ipr-korea-versioned-production-candidates/1",
        "source_original_count": len(ids), "candidate_count": len(ids),
        "source_git_commit": "b" * 40, "source_db_sha256": "a" * 64,
        "production_import_enabled": False, "approved_count": 0,
        "public_body_count": 0, "model_email_or_publication_authorized": False,
        "reviewer_identity_authenticated": False, "per_source_rights_granted": False,
        "records": [],
    }
    for article_id in ids:
        identity = "korea-policy:" + article_id
        link = admission.PREFIX + article_id
        pins = {
            "original_title_sha256": "1" * 64,
            "original_text_sha256": "2" * 64,
            "publisher_html_sha256": "3" * 64,
            "original_hwpx_sha256": "4" * 64,
        }
        version = hashlib.sha256(admission.canon({
            "source_identity": identity, "source_url": link,
            "published_date": "2026-10-15",
            "original_text_sha256": pins["original_text_sha256"],
            "publisher_html_sha256": pins["publisher_html_sha256"],
            "original_hwpx_sha256": pins["original_hwpx_sha256"],
        })).hexdigest()
        result["records"].append(dict(
            source_identity=identity, canonical_source_url=link,
            publisher_posted_date="2026-10-15", source_slug="kr_policy_mnd_releases",
            institution_id="kr_mnd", publisher_institution_id="kr_policy_briefing",
            authority_tier="B", originality="syndicated", language_tag="ko",
            approved_for_production=False, approved_for_publication=False,
            approved_for_model_or_email=False,
            original_text_included=False, original_title_included=False,
            original_media_included=False, candidate_version_sha256=version,
            editorial_exception=("year_dispute" if article_id == "156785161"
                                 else None), **pins
        ))
    return result


class KoreaStandingLinkAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "scratch.sqlite"
        self.db = sqlite3.connect(self.path)
        self.addCleanup(self.db.close)
        schema.up(self.db)
        self.policy = admission.read_policy()
        self.packet = packet()
        self.stamp = "2026-10-15T20:00:00Z"

    def go(self, p=None):
        result = admission.admit(self.db, p or self.packet, self.policy,
                                 as_of_utc=self.stamp)
        self.db.commit()
        return result

    def test_owner_policy_is_limited_to_five_factual_public_fields(self):
        self.assertEqual(self.policy["public_fields"], admission.FIELDS)
        self.assertTrue(self.policy["automatic_public_official_link_only"])
        for excluded in admission.FLAGS:
            self.assertIs(self.policy[excluded], False)
        self.assertFalse(
            self.policy["independent_human_signoff_required_for_links_only"])

    def test_idempotent_new_links_in_live_metadata_not_articles(self):
        result = self.go()
        self.assertEqual(result["new_official_links_admitted"], 5)
        self.assertEqual(self.go()["unchanged_official_links"], 5)
        rows = load_live_korea_official_links(self.path)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["source_identity"], "korea-policy:156799905")
        self.assertNotIn("title_original", rows[0])
        self.assertNotIn("text_original", rows[0])
        self.assertNotIn("model_id", rows[0])
        self.assertEqual(len(load_live_korea_official_links(
            self.path, exclude={"korea-policy:156799905"})), 4)

    def test_source_version_change_is_held_without_overwrite(self):
        self.go()
        changed = copy.deepcopy(self.packet)
        changed["records"][0]["original_title_sha256"] = "5" * 64
        # Title change cannot change previous admitted source version silently:
        # compare all identity/provenance, including title pin in the live DB.
        with self.assertRaises(admission.MetadataHold):
            self.go(changed)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM korea_official_source_records"
        ).fetchone()[0], 5)

    def test_bad_official_url_and_issuer_refused_atomically(self):
        for field, bad in (("canonical_source_url", "https://bad.example/hi"),
                           ("institution_id", "kr_dapa"),
                           ("approved_for_publication", True),
                           ("original_title_included", True)):
            p = copy.deepcopy(self.packet)
            p["records"][-1][field] = bad
            with self.subTest(field=field), self.assertRaises(admission.MetadataHold):
                self.go(p)
            self.assertEqual(self.db.execute(
                "SELECT COUNT(*) FROM korea_official_source_records"
            ).fetchone()[0], 0)

    def test_false_public_policy_or_unreviewed_body_is_refused(self):
        for key in admission.FLAGS:
            policy = dict(self.policy, **{key: True})
            with self.subTest(key=key), self.assertRaises(admission.MetadataHold):
                admission.admit(self.db, self.packet, policy,
                                as_of_utc=self.stamp)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM korea_official_source_records"
        ).fetchone()[0], 0)

    def test_known_chronology_dispute_kept_off_site(self):
        p = packet(["156785161", "156799901", "156799902",
                    "156799903", "156799904"])
        result = self.go(p)
        self.assertEqual(result["explicit_exception_held"], 1)
        self.assertEqual(len(load_live_korea_official_links(self.path)), 4)
        self.assertNotIn("korea-policy:156785161", [
            x["source_identity"] for x in load_live_korea_official_links(self.path)])

    def test_duplicate_identity_and_boolean_counter_never_publish(self):
        p = copy.deepcopy(self.packet)
        p["records"][1] = p["records"][0]
        with self.assertRaises(admission.MetadataHold):
            self.go(p)
        p = copy.deepcopy(self.packet)
        p["approved_count"] = False
        with self.assertRaises(admission.MetadataHold):
            self.go(p)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM korea_official_source_records"
        ).fetchone()[0], 0)

    def test_generated_real_korea_route_reads_only_live_link_metadata(self):
        # Full site render against a disposable copy of the actual production
        # corpus. This never changes pla_watch.db or tracked output.
        import sys
        from core.korea_reference_gate import ROOT
        sys.path.insert(0, str(ROOT / "site/preview"))
        import generate_preview as gp
        copied_db = Path(self.temp.name) / "production-copy.sqlite"
        from scripts.reconcile_db import read_only
        with read_only(ROOT / "pla_watch.db") as src, sqlite3.connect(copied_db) as out:
            src.backup(out)
        with sqlite3.connect(copied_db) as con:
            schema.up(con)
            admission.admit(con, self.packet, self.policy, as_of_utc=self.stamp)
            con.commit()
        target = Path(self.temp.name) / "site"
        gp.build(target, "Korea automatic official metadata", copied_db,
                 snapshot=gp.snapshot_from_corpus(copied_db),
                 site_origin="https://indopacificrecord.org")
        page = (target / "korea.html").read_text(encoding="utf-8")
        self.assertEqual(page.count('data-korea-public-link='), 5)
        self.assertEqual(page.count('data-korea-additional-link='), 9)
        self.assertEqual(page.count('data-korea-auto-official-link='), 5)
        self.assertIn("MND official press release 156799905", page)
        self.assertIn("Portal posted:", page)
        for forbidden in ("summary_english", "text_original", "source_git_commit",
                          "original_title_sha256", "original_hwpx_sha256"):
            self.assertNotIn(forbidden, page)

    def test_existing_old_style_database_fails_publication_closed(self):
        old = Path(self.temp.name) / "legacy.sqlite"
        with sqlite3.connect(old) as conn:
            conn.execute("CREATE TABLE articles (id INTEGER)")
        self.assertEqual(load_live_korea_official_links(old), [])

if __name__ == "__main__":
    unittest.main()
