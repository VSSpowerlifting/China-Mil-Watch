"""
The correction sidecar: what it may change, and what it must never touch.

A shadow state branch is hash-chained twice over — each ledger records the
SHA-256 of the whole database file, and the `content_sha256` of every record it
inserted. So a historical correction is not applied to the database at all. It
is published beside it, append-only and chained, and a reader materialises the
corrected text. These tests hold that line: the database is byte-identical
before and after everything this tool does.
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


def build_state(tmp: Path, rows) -> Path:
    """A minimal but structurally real state directory."""
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
    after = hashlib.sha256(db.read_bytes()).hexdigest()
    (state / "ledger" / "0001.json").write_text(json.dumps({
        "run_id": "1", "result": "ok",
        "state_sha256_before": "0" * 64, "state_sha256_after": after,
        "content_hashes": []}), encoding="utf-8")
    (state / "clock.json").write_text(json.dumps({"day_zero_utc": "2026-08-01T00:00:00+00:00"}),
                                      encoding="utf-8")
    return state


class CorrectionBase(unittest.TestCase):
    ROWS = [
        ("https://x/a/", "Plain title", "it" + HEX + "s here and " + HEX),
        ("https://x/b/", "Title&#x27;s &amp; more", "clean body"),
        ("https://x/c/", "Another", "nothing to fix"),
    ]

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.state = build_state(self.tmp, self.ROWS)
        self.db_hash = hashlib.sha256((self.state / "shadow.db").read_bytes()).hexdigest()

    def db_unchanged(self):
        return hashlib.sha256((self.state / "shadow.db").read_bytes()).hexdigest() == self.db_hash

    def emit(self, field, out=None):
        n = len(cc.existing_corrections(self.state)) + 1
        out = out or (self.state / "corrections" / ("%04d-%s.json" % (n, field)))
        return cc.emit(self.state, "test", "deadbeef", field, out)


class TheDatabaseIsNeverWritten(CorrectionBase):

    def test_emit_leaves_the_database_byte_identical(self):
        self.emit("body")
        self.emit("title")
        self.assertTrue(self.db_unchanged())

    def test_emit_creates_no_wal_or_shm_sidecar(self):
        self.emit("body")
        self.assertEqual(list(self.state.glob("shadow.db-*")), [])

    def test_materializing_leaves_the_database_byte_identical(self):
        self.emit("body")
        cc.corrected_records(self.state)
        self.assertTrue(self.db_unchanged())

    def test_the_original_text_is_still_recoverable(self):
        self.emit("body")
        con = cc.read_only(self.state / "shadow.db")
        stored = dict(con.execute("select url, text_original from shadow_records"))
        con.close()
        self.assertIn(HEX, stored["https://x/a/"])


class WhatItCorrects(CorrectionBase):

    def test_body_correction_counts_records_and_occurrences(self):
        doc = self.emit("body")
        self.assertEqual(doc["affected_record_count"], 1)
        self.assertEqual(doc["total_occurrences"], 2)

    def test_title_correction_counts_records_and_occurrences(self):
        doc = self.emit("title")
        self.assertEqual(doc["affected_record_count"], 1)
        self.assertEqual(doc["total_occurrences"], 2)   # &#x27; and &amp;

    def test_materialized_text_is_corrected(self):
        self.emit("body")
        self.emit("title")
        out = cc.corrected_records(self.state)
        self.assertEqual(out["https://x/a/"]["body"], "it's here and '")
        self.assertEqual(out["https://x/b/"]["title"], "Title's & more")

    def test_untouched_records_are_untouched(self):
        self.emit("body")
        self.emit("title")
        out = cc.corrected_records(self.state)
        self.assertEqual(out["https://x/c/"]["body"], "nothing to fix")
        self.assertEqual(out["https://x/c/"]["title"], "Another")

    def test_a_body_correction_does_not_move_the_title(self):
        self.emit("body")
        out = cc.corrected_records(self.state)
        self.assertEqual(out["https://x/a/"]["title"], "Plain title")


class ItIsIdempotent(CorrectionBase):

    def test_materializing_twice_gives_the_same_text(self):
        self.emit("body")
        self.emit("title")
        self.assertEqual(cc.corrected_records(self.state),
                         cc.corrected_records(self.state))

    def test_re_emitting_is_deterministic(self):
        a = self.emit("body")
        b = self.emit("body")
        self.assertEqual((a["affected_record_count"], a["total_occurrences"]),
                         (b["affected_record_count"], b["total_occurrences"]))
        self.assertEqual([r["value_sha256_after"] for r in a["records"]],
                         [r["value_sha256_after"] for r in b["records"]])


class ItRefusesWhatItCannotProve(CorrectionBase):

    def test_a_double_escaped_body_is_refused(self):
        # `&amp;#x27;` is the one construction where a literal substitution and
        # a real re-extraction disagree, so the tool will not guess.
        state = build_state(Path(tempfile.mkdtemp()),
                            [("https://x/d/", "t", "see &amp;#x27; literal")])
        with self.assertRaises(SystemExit) as e:
            cc.emit(state, "test", "x", "body", None)
        self.assertIn("&amp;#x27;", str(e.exception))

    def test_a_database_that_does_not_match_its_ledger_is_refused(self):
        con = sqlite3.connect(self.state / "shadow.db")
        con.execute("update shadow_records set published_date='2030-01-01'")
        con.commit()
        con.close()
        with self.assertRaises(SystemExit) as e:
            self.emit("body")
        self.assertIn("does not hash", str(e.exception))

    def test_a_correction_for_a_different_database_is_refused(self):
        self.emit("body")
        f = cc.existing_corrections(self.state)[0]
        doc = json.loads(f.read_text(encoding="utf-8"))
        doc["records"][0]["value_sha256_before"] = "f" * 64
        doc["records"][0]["value_sha256_after"] = "e" * 64
        f.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(SystemExit) as e:
            cc.corrected_records(self.state)
        self.assertIn("neither the before nor the after", str(e.exception))


class TheChainIsVerified(CorrectionBase):

    def test_a_clean_pair_of_corrections_verifies(self):
        self.emit("body")
        self.emit("title")
        self.assertEqual(cc.verify(self.state), 0)

    def test_a_broken_link_in_the_correction_chain_fails(self):
        self.emit("body")
        self.emit("title")
        f = cc.existing_corrections(self.state)[1]
        doc = json.loads(f.read_text(encoding="utf-8"))
        doc["anchor"]["prev_correction_sha256"] = "a" * 64
        f.write_text(json.dumps(doc), encoding="utf-8")
        self.assertEqual(cc.verify(self.state), 1)

    def test_a_tampered_after_hash_fails(self):
        self.emit("body")
        f = cc.existing_corrections(self.state)[0]
        doc = json.loads(f.read_text(encoding="utf-8"))
        doc["records"][0]["value_sha256_after"] = "b" * 64
        f.write_text(json.dumps(doc), encoding="utf-8")
        self.assertEqual(cc.verify(self.state), 1)

    def test_a_correction_claiming_an_unchanged_field_that_moved_fails(self):
        self.emit("body")
        f = cc.existing_corrections(self.state)[0]
        doc = json.loads(f.read_text(encoding="utf-8"))
        doc["records"][0]["unchanged"]["published_date"] = "1999-01-01"
        f.write_text(json.dumps(doc), encoding="utf-8")
        self.assertEqual(cc.verify(self.state), 1)


if __name__ == "__main__":
    unittest.main()
