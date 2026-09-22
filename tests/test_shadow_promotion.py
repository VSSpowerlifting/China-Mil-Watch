"""
Recapture, holds and promotion: the three things that can put text into the
production corpus that nobody captured.

Every other correction is a function of the stored bytes. `recaptured_current_
source` is not — it replaces a captured value with text fetched from the live
page later, because the whitespace collapse destroyed continuation bytes that
no transformation can restore. That makes it the only correction that can
disagree with the capture about what the document said, so it carries its own
provenance, its own evidence tier, and a warning that travels with the value.

A hold is the opposite motion: a record that is perfectly corrected and still
unfit to promote, because the live page is a later revision of the document and
the stored text cannot be repaired. Correcting it would be a lie either way.

Promotion is where both land. It refuses an overlay it cannot verify, refuses a
holds file describing another database, refuses the tracked database outright,
and inserts nothing twice.

Offline: temporary databases, no network, no model calls.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.correct_shadow_bodies as cc                     # noqa: E402
import scripts.promote_shadow_records as pr                    # noqa: E402
from tests.test_shadow_body_corrections import Base, build_state   # noqa: E402

HELD = "https://x/c/"
RECAPTURED = "https://x/a/"

MANIFEST = {
    "desk": {"desk_id": "singapore", "display_name": "Singapore Desk"},
    "sources": [{
        "slug": "sg_mindef", "display_name": "MINDEF Singapore",
        "base_url": "https://x", "institution_id": "sg_mindef",
        "language_tag": "en", "authority_tier": "A", "enabled": False,
        "listing_endpoints": [], "article_url_patterns": [], "notes": "test",
    }],
}


def production_db(path: Path) -> Path:
    con = sqlite3.connect(path)
    con.executescript("""
        create table sources (
            id integer primary key, slug text unique, display_name text,
            base_url text, language text, is_active integer, created_at text,
            desk_id text, institution_id text, language_tag text,
            authority_tier text, enabled integer, listing_endpoints text,
            article_url_patterns text, notes text);
        create table articles (
            id integer primary key, url text unique, content_hash text,
            source_id integer references sources(id), title_original text,
            text_original text, published_date text, scraped_at text,
            processing_state text);
    """)
    con.commit()
    con.close()
    return path


def with_capture_provenance(state: Path) -> Path:
    """The real corpus always records the capture hash and the retrieval time.
    The shared fixture leaves them null, and promotion is entitled to refuse
    that — so the happy-path fixture supplies them and one test removes them
    again on purpose."""
    db = state / "shadow.db"
    con = sqlite3.connect(db)
    con.execute("update shadow_records set capture_sha256 = 'cafe' || "
                "substr(content_sha256, 5), retrieved_at = '2026-08-01T00:00:00+00:00'")
    con.commit()
    con.close()
    tip = state / "ledger" / "0001.json"
    doc = json.loads(tip.read_text(encoding="utf-8"))
    doc["state_sha256_after"] = hashlib.sha256(db.read_bytes()).hexdigest()
    tip.write_text(json.dumps(doc), encoding="utf-8")
    return state


class PromotionBase(Base):

    def setUp(self):
        super().setUp()
        with_capture_provenance(self.state)
        self.db_hash = hashlib.sha256(
            (self.state / "shadow.db").read_bytes()).hexdigest()
        self.manifest = self.tmp / "manifest.json"
        self.manifest.write_text(json.dumps(MANIFEST), encoding="utf-8")
        self.into = production_db(self.tmp / "production.db")

    def recapture_file(self, body="a wholly recaptured body", **over):
        payload = {
            "request_url": RECAPTURED,
            "retrieved_at": "2026-09-20T23:00:00+00:00",
            "http_status": 200,
            "response_bytes": 12345,
            "raw_sha256": "f" * 64,
            "declared_encoding": "utf-8",
            "encoding_source": "meta",
            "body": body,
        }
        payload.update(over)
        p = self.tmp / "recapture.json"
        p.write_text(json.dumps({RECAPTURED: payload}), encoding="utf-8")
        return p

    def emit_recapture(self, **over):
        n = len(cc.existing_corrections(self.state)) + 1
        out = cc.corrections_dir(self.state) / ("%04d-body-%s.json" % (n, cc.RECAPTURE))
        return cc.emit(self.state, "body", cc.RECAPTURE, "test", "deadbeef",
                       None, None, out, self.recapture_file(**over))

    def hold(self, url=HELD):
        return cc.declare_hold(self.state, url, "unfit", "measured")

    def full_overlay(self):
        self.emit_all()
        self.emit_recapture()
        self.hold()

    def promote(self, **kw):
        return pr.promote(self.state, None, self.manifest, self.into, **kw)


class TheRecaptureCarriesItsOwnProvenance(PromotionBase):

    def test_it_replaces_the_value_and_verifies(self):
        self.emit_all()
        doc = self.emit_recapture()
        self.assertEqual(1, doc["affected_record_count"])
        self.assertEqual(0, cc.verify(self.state))
        self.assertTrue(self.db_unchanged())

    def test_the_corrected_view_shows_the_recaptured_text(self):
        self.full_overlay()
        self.assertEqual("a wholly recaptured body",
                         cc.corrected_view(self.state)[RECAPTURED]["body"])

    def test_the_warning_travels_with_the_value(self):
        self.emit_all()
        doc = self.emit_recapture()
        self.assertEqual(cc.RECAPTURE_WARNING, doc["warning"])
        self.assertEqual(cc.RECAPTURE_WARNING, doc["transformation"]["warning"])
        self.assertEqual(cc.RECAPTURE_WARNING, doc["records"][0]["warning"])

    def test_it_is_not_claimed_to_be_equivalent_to_re_extraction(self):
        """Every other kind says what re-extraction would have produced. This
        one cannot, and must not pretend to."""
        self.emit_all()
        doc = self.emit_recapture()
        self.assertIsNone(doc["transformation"]["equivalent_to"])

    def test_missing_provenance_is_refused_at_emit(self):
        for field in cc.RECAPTURE_PROVENANCE:
            with self.subTest(missing=field):
                with self.assertRaises(SystemExit):
                    cc.load_recapture(self.recapture_file(**{field: None}))

    def test_a_non_200_recapture_is_refused(self):
        with self.assertRaises(SystemExit):
            cc.load_recapture(self.recapture_file(http_status=404))

    def test_a_tampered_replacement_fails_verification(self):
        self.emit_all()
        self.emit_recapture()
        index = len(cc.existing_corrections(self.state)) - 1
        self.tamper(index, lambda d: d["records"][0].__setitem__(
            "replacement", d["records"][0]["replacement"] + " TAMPERED"))
        self.assertEqual(1, cc.verify(self.state))

    def test_a_derived_correction_may_not_claim_the_recaptured_tier(self):
        self.emit_all()
        self.tamper(0, lambda d: d["records"][0].__setitem__("evidence", "recaptured"))
        self.assertEqual(1, cc.verify(self.state))

    def test_the_kind_is_refused_without_a_recapture_file(self):
        self.emit_all()
        with self.assertRaises(SystemExit):
            cc.emit(self.state, "body", cc.RECAPTURE, "test", "x", None, None,
                    self.tmp / "out.json", None)


class AHoldIsNotACorrection(PromotionBase):

    def test_it_lives_outside_the_corrections(self):
        self.full_overlay()
        self.assertNotIn(cc.holds_path(self.state),
                         cc.existing_corrections(self.state))
        self.assertEqual(0, cc.verify(self.state))

    def test_holding_an_unknown_record_is_refused(self):
        with self.assertRaises(SystemExit):
            cc.declare_hold(self.state, "https://x/nope/", "r", "e")

    def test_a_hold_bound_to_another_database_is_refused(self):
        self.hold()
        p = cc.holds_path(self.state)
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["binding"]["database_sha256"] = "f" * 64
        p.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(SystemExit):
            cc.load_holds(self.state)

    def test_a_miscounted_holds_file_is_refused(self):
        self.hold()
        p = cc.holds_path(self.state)
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["hold_count"] = 99
        p.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(SystemExit):
            cc.load_holds(self.state)

    def test_no_holds_file_means_no_holds_not_an_error(self):
        self.assertEqual({}, cc.load_holds(self.state))

    def test_declaring_the_same_hold_twice_does_not_duplicate_it(self):
        self.hold()
        self.hold()
        self.assertEqual(1, len(cc.load_holds(self.state)))


class PromotionRefusesBeforeItWrites(PromotionBase):

    def rows(self):
        con = sqlite3.connect(self.into)
        n = con.execute("select count(*) from articles").fetchone()[0]
        con.close()
        return n

    def test_it_refuses_when_there_is_no_overlay(self):
        with self.assertRaises(SystemExit):
            self.promote()
        self.assertEqual(0, self.rows())

    def test_it_refuses_an_overlay_that_does_not_verify(self):
        self.full_overlay()
        self.tamper(0, lambda d: d["records"][0].__setitem__(
            "value_sha256_after", "0" * 64))
        with self.assertRaises(SystemExit):
            self.promote()
        self.assertEqual(0, self.rows())

    def test_it_refuses_an_overlay_missing_a_link_in_the_chain(self):
        self.full_overlay()
        cc.existing_corrections(self.state)[2].unlink()
        with self.assertRaises(SystemExit):
            self.promote()
        self.assertEqual(0, self.rows())

    def test_it_refuses_holds_bound_elsewhere(self):
        self.full_overlay()
        p = cc.holds_path(self.state)
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["binding"]["database_sha256"] = "f" * 64
        p.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.promote()
        self.assertEqual(0, self.rows())

    def test_it_refuses_a_record_with_no_capture_provenance(self):
        """Promoting it would assert a byte stream that was never recorded."""
        con = sqlite3.connect(self.state / "shadow.db")
        con.execute("update shadow_records set capture_sha256 = null "
                    "where url = ?", (RECAPTURED,))
        con.commit()
        con.close()
        tip = self.state / "ledger" / "0001.json"
        doc = json.loads(tip.read_text(encoding="utf-8"))
        doc["state_sha256_after"] = hashlib.sha256(
            (self.state / "shadow.db").read_bytes()).hexdigest()
        tip.write_text(json.dumps(doc), encoding="utf-8")
        self.full_overlay()
        with self.assertRaises(SystemExit) as caught:
            self.promote()
        self.assertIn("capture provenance", str(caught.exception))
        self.assertEqual(0, self.rows())

    def test_it_refuses_the_tracked_database_outright(self):
        self.full_overlay()
        with self.assertRaises(SystemExit):
            pr.promote(self.state, None, self.manifest,
                       REPO_ROOT / "pla_watch.db")

    def test_it_refuses_a_packet_passed_as_the_manifest(self):
        """The corrected-view packet and the desk manifest are both JSON in
        the same workflow, and the packet's `desk` is a string. Without a
        check the mistake surfaces as a TypeError deep inside the promoter."""
        self.full_overlay()
        packet = self.tmp / "corrected_view_packet.json"
        packet.write_text(json.dumps(
            {"schema": "corrected-view-packet/3", "desk": "singapore-mindef",
             "records": []}), encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            pr.promote(self.state, None, packet, self.into)
        self.assertIn("not a desk manifest", str(caught.exception))
        self.assertEqual(0, self.rows())

    def test_it_refuses_a_manifest_that_declares_no_sources(self):
        self.full_overlay()
        bare = self.tmp / "bare.json"
        bare.write_text(json.dumps({"desk": {"desk_id": "singapore"}}),
                        encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            pr.promote(self.state, None, bare, self.into)
        self.assertIn("declares no sources", str(caught.exception))
        self.assertEqual(0, self.rows())


class PromotionIsDeterministicAndIdempotent(PromotionBase):

    def promoted(self, db=None):
        con = sqlite3.connect(db or self.into)
        rows = list(con.execute(
            "select url, title_original, text_original, content_hash, "
            "published_date from articles order by url"))
        prov = list(con.execute(
            "select url, overlay_sha256, holds_sha256, capture_content_sha256 "
            "from shadow_promotions order by url"))
        con.close()
        return rows, prov

    def test_it_promotes_the_corrected_view_minus_the_holds(self):
        self.full_overlay()
        report = self.promote()
        self.assertEqual(len(self.ROWS) - 1, report["candidates"])
        self.assertEqual(len(self.ROWS) - 1, report["inserted"])
        self.assertEqual(1, report["held_count"])
        rows, _ = self.promoted()
        self.assertNotIn(HELD, [r[0] for r in rows])

    def test_the_promoted_text_is_the_corrected_text(self):
        self.full_overlay()
        self.promote()
        rows, _ = self.promoted()
        body = {r[0]: r[2] for r in rows}[RECAPTURED]
        self.assertEqual("a wholly recaptured body", body)

    def test_every_promoted_row_names_its_capture_and_its_overlay(self):
        self.full_overlay()
        self.promote()
        rows, prov = self.promoted()
        self.assertEqual(len(rows), len(prov))
        digest = cc.overlay_digest(self.state)
        for url, overlay, holds, capture in prov:
            self.assertEqual(digest, overlay)
            self.assertEqual(cc.holds_digest(self.state), holds)
            self.assertTrue(capture)

    def test_a_second_promotion_inserts_nothing(self):
        self.full_overlay()
        self.promote()
        before = self.promoted()
        report = self.promote()
        self.assertEqual(0, report["inserted"])
        self.assertEqual(len(self.ROWS) - 1, report["already_present"])
        self.assertEqual(before, self.promoted())

    def test_two_fresh_promotions_agree(self):
        self.full_overlay()
        self.promote()
        other = production_db(self.tmp / "other.db")
        pr.promote(self.state, None, self.manifest, other)
        self.assertEqual(self.promoted(), self.promoted(other))

    def test_urls_stay_distinct(self):
        self.full_overlay()
        self.promote()
        rows, _ = self.promoted()
        urls = [r[0] for r in rows]
        self.assertEqual(len(urls), len(set(urls)))

    def test_a_dry_run_writes_nothing(self):
        self.full_overlay()
        report = self.promote(dry_run=True)
        self.assertEqual(len(self.ROWS) - 1, report["candidates"])
        self.assertEqual(0, report["inserted"])
        con = sqlite3.connect(self.into)
        self.assertEqual(0, con.execute("select count(*) from articles").fetchone()[0])
        con.close()

    def test_the_shadow_database_is_never_written(self):
        self.full_overlay()
        self.promote()
        self.assertTrue(self.db_unchanged())
        self.assertEqual(list(self.state.glob("shadow.db-*")), [])


if __name__ == "__main__":
    unittest.main()
