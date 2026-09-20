"""
The correction overlay: what it may change, what it must refuse, and the
single rule it can never break — the database is not written.

A shadow state branch is hash-chained twice over: each ledger records the
SHA-256 of the whole database file, and the `content_sha256` of every record it
inserted. So a historical correction is published beside the database, never
applied to it, and a reader materialises the corrected text.

These tests hold that line, and hold the overlay to failing closed. An overlay
that quietly skips a file it does not understand is worse than no overlay,
because the packet built from it would look complete.
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

HEX = "&#x27;"
CURLY = "’"
MOJIBAKE = CURLY.encode("utf-8").decode("latin-1")
ORPHAN = chr(0xC2)


def build_state(tmp: Path, rows) -> Path:
    state = tmp / "state"
    (state / "ledger").mkdir(parents=True)
    db = state / "shadow.db"
    con = sqlite3.connect(db)
    con.execute("""create table shadow_records (
        url text primary key, source_slug text, title_original text,
        text_original text, published_date text, language_tag text,
        publication_kind text, content_sha256 text not null,
        capture_sha256 text, retrieved_at text, first_seen_run text)""")
    for url, title, body in rows:
        con.execute("insert into shadow_records values (?,?,?,?,?,?,?,?,?,?,?)",
                    (url, "sg_mindef", title, body, "2026-08-01", "en", "news",
                     hashlib.sha256(body.encode()).hexdigest(), None, None, "1"))
    con.commit()
    con.close()
    (state / "ledger" / "0001.json").write_text(json.dumps({
        "run_id": "1", "result": "ok", "state_sha256_before": "0" * 64,
        "state_sha256_after": hashlib.sha256(db.read_bytes()).hexdigest(),
        "content_hashes": []}), encoding="utf-8")
    (state / "clock.json").write_text(
        json.dumps({"day_zero_utc": "2026-08-01T00:00:00+00:00"}), encoding="utf-8")
    return state


class Base(unittest.TestCase):
    ROWS = [
        ("https://x/a/", "Plain title", "it" + HEX + "s and " + MOJIBAKE + "s"),
        ("https://x/b/", "Title&#x27;s &amp; more", "clean body"),
        ("https://x/c/", "Another", "nothing to fix"),
        ("https://x/d/", "Curly" + MOJIBAKE + "s", "spaced" + ORPHAN + " out"),
    ]

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.state = build_state(self.tmp, self.ROWS)
        self.db_hash = hashlib.sha256((self.state / "shadow.db").read_bytes()).hexdigest()

    def db_unchanged(self):
        return hashlib.sha256(
            (self.state / "shadow.db").read_bytes()).hexdigest() == self.db_hash

    def emit(self, field, kind, out=None):
        n = len(cc.existing_corrections(self.state)) + 1
        out = out or (cc.corrections_dir(self.state)
                      / ("%04d-%s-%s.json" % (n, field, kind)))
        return cc.emit(self.state, field, kind, "test", "deadbeef", None, None, out)

    def emit_all(self):
        self.emit("body", "literal_replace_all")
        self.emit("title", "html_unescape_once")
        self.emit("body", "mojibake_latin1_utf8")
        self.emit("title", "mojibake_latin1_utf8")

    def tamper(self, index, mutate):
        f = cc.existing_corrections(self.state)[index]
        doc = json.loads(f.read_text(encoding="utf-8"))
        mutate(doc)
        f.write_text(json.dumps(doc), encoding="utf-8")
        return f


class TheDatabaseIsNeverWritten(Base):

    def test_emitting_everything_leaves_it_byte_identical(self):
        self.emit_all()
        self.assertTrue(self.db_unchanged())

    def test_no_wal_or_shm_sidecar_is_created(self):
        self.emit_all()
        cc.corrected_view(self.state)
        self.assertEqual(list(self.state.glob("shadow.db-*")), [])

    def test_materialising_leaves_it_byte_identical(self):
        self.emit_all()
        cc.corrected_view(self.state)
        self.assertTrue(self.db_unchanged())

    def test_the_original_view_still_shows_the_damage(self):
        self.emit_all()
        raw = cc.original_view(self.state)
        self.assertIn(HEX, raw["https://x/a/"]["body"])
        self.assertIn(MOJIBAKE, raw["https://x/a/"]["body"])


class TheTwoViews(Base):

    def test_original_and_corrected_differ_only_where_declared(self):
        self.emit_all()
        before, after = cc.original_view(self.state), cc.corrected_view(self.state)
        changed = {u for u in before if before[u] != after[u]}
        self.assertEqual(changed, {"https://x/a/", "https://x/b/", "https://x/d/"})
        self.assertEqual(before["https://x/c/"], after["https://x/c/"])

    def test_the_corrected_view_is_actually_correct(self):
        self.emit_all()
        v = cc.corrected_view(self.state)
        self.assertEqual(v["https://x/a/"]["body"], "it's and " + CURLY + "s")
        self.assertEqual(v["https://x/b/"]["title"], "Title's & more")
        self.assertEqual(v["https://x/d/"]["title"], "Curly" + CURLY + "s")
        self.assertEqual(v["https://x/d/"]["body"], "spaced out")

    def test_corrections_compose_across_files(self):
        # https://x/a/ is corrected twice: entities, then charset. The second
        # must be described against the first's output, not raw storage.
        self.emit_all()
        v = cc.corrected_view(self.state)
        self.assertNotIn(HEX, v["https://x/a/"]["body"])
        self.assertNotIn(MOJIBAKE, v["https://x/a/"]["body"])

    def test_the_overlay_digest_names_the_whole_overlay(self):
        self.assertIsNone(cc.overlay_digest(self.state))
        self.emit_all()
        first = cc.overlay_digest(self.state)
        self.assertEqual(first, cc.overlay_digest(self.state))
        self.tamper(0, lambda d: d.update(reason="changed"))
        self.assertNotEqual(first, cc.overlay_digest(self.state))


class ItIsIdempotent(Base):

    def test_materialising_twice_is_the_same(self):
        self.emit_all()
        self.assertEqual(cc.corrected_view(self.state), cc.corrected_view(self.state))

    def test_re_emitting_an_applied_correction_finds_nothing(self):
        self.emit_all()
        again = cc.emit(self.state, "body", "literal_replace_all",
                        "probe", "p", None, None, None)
        self.assertEqual(again["affected_record_count"], 0)


class ItRefusesWhatItCannotProve(Base):

    def test_a_double_escaped_body_is_refused(self):
        state = build_state(Path(tempfile.mkdtemp()),
                            [("https://x/e/", "t", "see &amp;#x27; literal")])
        with self.assertRaises(SystemExit) as e:
            cc.emit(state, "body", "literal_replace_all", "t", "x", None, None, None)
        self.assertIn("&amp;#x27;", str(e.exception))

    def test_irreversible_mojibake_is_refused_not_guessed(self):
        # A continuation byte the whitespace collapse already ate: the original
        # character is gone and no transformation can invent it.
        broken = chr(0xE5) + " " + chr(0xAB) + " tail " + MOJIBAKE
        state = build_state(Path(tempfile.mkdtemp()), [("https://x/f/", "t", broken)])
        doc = cc.emit(state, "body", "mojibake_latin1_utf8", "t", "x", None, None, None)
        self.assertEqual(doc["affected_record_count"], 0)
        self.assertEqual(len(doc["refused"]), 1)
        self.assertIn("not recoverable", doc["refused"][0]["why"])

    def test_a_database_that_does_not_match_its_ledger_is_refused(self):
        con = sqlite3.connect(self.state / "shadow.db")
        con.execute("update shadow_records set published_date='2030-01-01'")
        con.commit()
        con.close()
        with self.assertRaises(SystemExit) as e:
            self.emit("body", "literal_replace_all")
        self.assertIn("does not hash", str(e.exception))

    def test_an_unapproved_transformation_cannot_be_emitted(self):
        with self.assertRaises(SystemExit):
            cc.emit(self.state, "body", "rot13", "t", "x", None, None, None)


class TheOverlayFailsClosed(Base):
    """Eight ways an overlay can be wrong. None of them may pass quietly."""

    def setUp(self):
        super().setUp()
        self.emit_all()

    def test_an_unknown_schema_is_refused(self):
        self.tamper(0, lambda d: d.update(schema="something-else/9"))
        self.assertEqual(cc.verify(self.state), 1)
        with self.assertRaises(SystemExit):
            cc.corrected_view(self.state)

    def test_an_unapproved_transformation_kind_is_refused(self):
        self.tamper(0, lambda d: d["transformation"].update(kind="rot13"))
        self.assertEqual(cc.verify(self.state), 1)
        with self.assertRaises(SystemExit):
            cc.corrected_view(self.state)

    def test_a_wrong_database_hash_is_refused(self):
        self.tamper(0, lambda d: d["binding"].update(database_sha256="f" * 64))
        self.assertEqual(cc.verify(self.state), 1)
        with self.assertRaises(SystemExit):
            cc.corrected_view(self.state)

    def test_a_wrong_state_commit_is_refused(self):
        self.tamper(0, lambda d: d["binding"].update(state_commit="a" * 40))
        with self.assertRaises(SystemExit):
            cc.corrected_view(self.state, self.state)

    def test_a_mismatched_original_field_hash_is_refused(self):
        self.tamper(0, lambda d: d["records"][0].update(value_sha256_before="e" * 64))
        self.assertEqual(cc.verify(self.state), 1)
        with self.assertRaises(SystemExit):
            cc.corrected_view(self.state)

    def test_a_duplicate_correction_is_refused(self):
        self.tamper(0, lambda d: d["records"].append(dict(d["records"][0])))
        self.assertEqual(cc.verify(self.state), 1)

    def test_correcting_a_record_this_database_does_not_have_is_refused(self):
        def add(d):
            r = dict(d["records"][0]); r["url"] = "https://x/nope/"
            d["records"].append(r)
        self.tamper(0, add)
        self.assertEqual(cc.verify(self.state), 1)
        with self.assertRaises(SystemExit):
            cc.corrected_view(self.state)

    def test_an_incomplete_manifest_is_refused(self):
        self.tamper(0, lambda d: d["records"].pop())
        self.assertEqual(cc.verify(self.state), 1)

    def test_unreadable_json_is_refused(self):
        cc.existing_corrections(self.state)[0].write_text("{ not json",
                                                          encoding="utf-8")
        self.assertEqual(cc.verify(self.state), 1)

    def test_a_broken_chain_link_is_refused(self):
        self.tamper(1, lambda d: d["binding"].update(prev_correction_sha256="a" * 64))
        self.assertEqual(cc.verify(self.state), 1)

    def test_a_tampered_after_hash_is_refused(self):
        self.tamper(0, lambda d: d["records"][0].update(value_sha256_after="b" * 64))
        self.assertEqual(cc.verify(self.state), 1)

    def test_a_claim_that_an_untouched_field_moved_is_refused(self):
        self.tamper(0, lambda d: d["records"][0]["unchanged"].update(
            published_date="1999-01-01"))
        self.assertEqual(cc.verify(self.state), 1)

    def test_an_unknown_evidence_tier_is_refused(self):
        self.tamper(0, lambda d: d["records"][0].update(evidence="vibes"))
        self.assertEqual(cc.verify(self.state), 1)

    def test_a_clean_overlay_still_verifies(self):
        self.assertEqual(cc.verify(self.state), 0)


class EvidenceIsRecorded(Base):

    def test_every_record_names_its_evidence_tier(self):
        self.emit_all()
        for f in cc.existing_corrections(self.state):
            doc = json.loads(f.read_text(encoding="utf-8"))
            for r in doc["records"]:
                self.assertIn(r["evidence"], cc.EVIDENCE_TIERS)

    def test_a_c1_control_is_intrinsic_evidence_without_a_live_page(self):
        doc = self.emit("body", "mojibake_latin1_utf8")
        self.assertTrue(doc["records"])
        self.assertTrue(all(r["evidence"] == "intrinsic" for r in doc["records"]))

    def test_live_confirmation_is_recorded_when_supplied(self):
        ev = self.tmp / "ev.json"
        ev.write_text(json.dumps([{"url": "https://x/a/", "body_matches_live": True}]),
                      encoding="utf-8")
        doc = cc.emit(self.state, "body", "literal_replace_all", "t", "x", ev, None, None)
        tiers = {r["url"]: r["evidence"] for r in doc["records"]}
        self.assertEqual(tiers["https://x/a/"], "live-confirmed")


class TheBindingIsComplete(Base):

    def test_it_names_the_database_ledger_and_chain(self):
        doc = self.emit("body", "literal_replace_all")
        b = doc["binding"]
        for key in ("database_sha256", "ledger_tip_file", "ledger_tip_run_id",
                    "ledger_entry_count", "state_commit", "state_tree",
                    "prev_correction_sha256"):
            self.assertIn(key, b)

    def test_each_record_names_identity_field_and_both_hashes(self):
        doc = self.emit("body", "literal_replace_all")
        for r in doc["records"]:
            for key in ("url", "field", "occurrences", "evidence",
                        "value_sha256_before", "value_sha256_after", "unchanged"):
                self.assertIn(key, r)

    def test_the_transformation_is_declarative(self):
        doc = self.emit("body", "mojibake_latin1_utf8")
        tr = doc["transformation"]
        self.assertEqual(tr["kind"], "mojibake_latin1_utf8")
        self.assertIn("steps", tr)
        self.assertTrue(tr["applies_to"].startswith("shadow_records."))


if __name__ == "__main__":
    unittest.main()
