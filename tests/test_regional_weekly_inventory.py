"""No-network regional inventory tests; no SMTP, collector or model."""
from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from core.regional_weekly_inventory import (
    InventoryError, build_inventory, inspect,
)

SAT = "2026-10-10"
SUN = "2026-10-11"


def desk(slug, status="live", sources=("official",)):
    return NS(slug=slug, status=status, is_collecting=status == "live",
              has_production_records=status == "live",
              sources=[NS(slug=s) for s in sources])


def registry():
    return [desk("china"), desk("singapore"), desk("japan", "shadow"),
            desk("vietnam", "research", ()), desk("philippines", "planned", ())]


def row(ident, desk_name, **changes):
    value = {
        "id": ident, "desk_id": desk_name,
        "source_slug": "official", "source_name": "Official publisher",
        "url": "https://official.example/" + str(ident),
        "published_date": "2026-10-08", "title_original": "An original headline",
        "text_original": "Original reported wording " * 30,
        "text_english": "", "source_language_tag": "en",
        "analyzed_at": None, "is_significant": None,
        "passed_relevance": None,
    }
    value.update(changes)
    return value


def make(rows=None, **changes):
    values = {
        "registry": registry(), "rows": rows if rows is not None else [
            row(42, "china"), row(47, "singapore")],
        "week_ending": SAT, "as_of": SAT, "review_day": SUN, "marker": SUN,
    }
    values.update(changes)
    return build_inventory(**values)


def pending(ident="JP-W41-01", desk_name="japan"):
    return {
        "id": ident, "desk": desk_name, "source_url": "https://www.mod.go.jp/j/press/news/a.html",
        "published_date": "2026-10-08",
        "status": "unapproved-source-linked-editorial-candidate",
        "summary": "Contains content that must never appear in metadata inventory",
        "text_original": "SENSITIVE RAW TEXT MUST NOT COPY",
    }


class RegionalInventoryTests(unittest.TestCase):
    def test_all_declared_desks_and_full_week_unabridged(self):
        r = make(rows=[row(i, "china") for i in range(1, 32)] +
                 [row(47, "singapore")])
        self.assertEqual(len(r["production_evidence"]), 32)
        self.assertEqual([c["desk"] for c in r["coverage"]],
                         ["china", "singapore", "japan", "vietnam", "philippines"])
        self.assertEqual([c["state"] for c in r["coverage"]],
                         ["reviewable", "reviewable", "awaiting_validation",
                          "awaiting_validation", "collector_unavailable"])
        self.assertEqual(r["production_preflight"],
                         "candidate_for_no_send_model_preview_not_approved")
        self.assertFalse(r["model_input_authorized"])
        self.assertFalse(r["publication_authorized"])
        self.assertFalse(r["editor_email_authorized"])
        self.assertIsNone(r["empty_editorial_slate"]["provisional_lead"])
        self.assertEqual(len(r["empty_editorial_slate"]["evidence"]), 32)

    def test_partial_week_and_missing_success_marker_remain_visible(self):
        r = make(as_of="2026-10-08", review_day="2026-10-08", marker="",
                 rows=[row(42, "china")])
        self.assertEqual(r["production_preflight"], "hold_before_model_or_email")
        self.assertIn("reporting_week_not_complete", r["unmet_production_gates"])
        coverage = {c["desk"]: c for c in r["coverage"]}
        self.assertEqual(coverage["singapore"]["state"], "awaiting_validation")
        self.assertEqual(coverage["china"]["state"], "reviewable")
        self.assertNotIn("silence", coverage["china"]["reason"].lower())

    def test_no_publications_does_not_mean_silence(self):
        r = make(rows=[row(42, "china")])
        sg = next(c for c in r["coverage"] if c["desk"] == "singapore")
        self.assertEqual(sg["state"], "no_qualifying_evidence")
        self.assertIn("not a claim", sg["reason"])
        self.assertIn("fewer_than_two_desks_with_usable_source_text",
                      r["unmet_production_gates"])

    def test_held_records_keep_exclusion_accounting(self):
        rows = [row(42, "china"), row(47, "singapore"),
                row(1, "china", passed_relevance=0),
                row(2, "china", text_original="short"),
                row(3, "china", url="http://example.com/plain"),
                row(4, "china", source_slug="unregistered"),
                row(5, "china", title_original=""),
                row(6, "china", source_language_tag="")]
        r = make(rows=rows)
        self.assertEqual(len(r["production_evidence"]), 2)
        self.assertEqual(len(r["held_production_records"]), 6)
        self.assertEqual(
            {h["reason"] for h in r["held_production_records"]},
            {"screened_not_selected", "insufficient_stored_full_text",
             "publisher_url_requires_review", "source_not_in_declared_desk_manifest",
             "missing_original_title", "missing_source_language"},
        )

    def test_distinct_numeric_identity_and_publisher_url(self):
        for rows in ([row(42, "china"), row(42, "singapore")],
                     [row(42, "china"),
                      row(47, "singapore", url="https://official.example/42")]):
            with self.subTest(rows=rows), self.assertRaises(InventoryError):
                make(rows=rows)

    def test_out_of_week_and_unregistered_desk_refuse(self):
        for val in ("2026-10-03", "2026-10-11"):
            with self.subTest(date=val), self.assertRaises(ValueError):
                make(rows=[row(42, "china", published_date=val)])
        with self.assertRaises(ValueError):
            make(rows=[row(42, "japan"), row(47, "singapore")])

    def test_private_research_never_becomes_slate_evidence(self):
        note = pending()
        r = make(research_rows=[note])
        self.assertEqual(len(r["pending_private_research"]), 1)
        self.assertEqual(r["pending_private_research"][0]["desk"], "japan")
        self.assertNotIn("JP-W41-01",
                         json.dumps(r["empty_editorial_slate"]["evidence"]))
        serial = json.dumps(r)
        self.assertNotIn("SENSITIVE RAW TEXT", serial)
        self.assertNotIn("Contains content that must never", serial)
        self.assertIn("independent_shadow_attestation", serial)

    def test_unapproved_duplicate_shadow_sources_fail_closed(self):
        note = pending()
        with self.assertRaises(InventoryError):
            make(research_rows=[note, copy.deepcopy(note)])
        with self.assertRaises(InventoryError):
            make(research_rows=[note, dict(note, id="JP-W41-02")])
        with self.assertRaises(InventoryError):
            make(research_rows=[pending(desk_name="china")])
        with self.assertRaises(InventoryError):
            make(research_rows=[dict(note, status="approved")])
        with self.assertRaises(InventoryError):
            make(research_rows=[dict(note, published_date="2026-10-11")])
        with self.assertRaises(InventoryError):
            make(research_rows=[dict(note, source_url="https://official.example/42")])

    def test_stored_body_is_digest_only_and_deterministic(self):
        r = make()
        again = make()
        self.assertEqual(r["source_metadata_digest_sha256"],
                         again["source_metadata_digest_sha256"])
        serial = json.dumps(r)
        self.assertNotIn("Original reported wording", serial)
        body = r["production_evidence"][0]
        self.assertEqual(len(body["stored_text_sha256"]), 64)
        self.assertEqual(body["role"], "new_week")
        self.assertEqual(body["topic_suggestions"], [])
        r2 = make(rows=[row(42, "china", text_original="Changed original " * 30),
                        row(47, "singapore")])
        self.assertNotEqual(r["source_metadata_digest_sha256"],
                            r2["source_metadata_digest_sha256"])

    def test_full_sqlite_scratch_copy_does_not_touch_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "source.db"
            marker = Path(tmp) / "marker.txt"
            marker.write_text(SUN, encoding="utf-8")
            with sqlite3.connect(str(db)) as conn:
                conn.executescript("""
                    CREATE TABLE sources (
                        id INTEGER PRIMARY KEY, slug TEXT, display_name TEXT,
                        desk_id TEXT, language TEXT, language_tag TEXT);
                    CREATE TABLE articles (
                        id INTEGER PRIMARY KEY, source_id INTEGER, url TEXT,
                        title_original TEXT, published_date TEXT,
                        text_original TEXT, text_english TEXT,
                        passed_relevance INTEGER, analyzed_at TEXT,
                        is_significant INTEGER);
                    INSERT INTO sources VALUES
                        (1, 'official', 'Publisher China', 'china', 'en', 'en'),
                        (2, 'official', 'Publisher SG', 'singapore', 'en', 'en');
                """)
                for ix, source_id in ((42, 1), (47, 2)):
                    conn.execute(
                        "INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (ix, source_id, "https://official.example/" + str(ix),
                         "Source title", "2026-10-08", "Original text " * 30,
                         None, None, None, None))
            original = db.read_bytes()
            result = inspect(
                database=db, marker_path=marker, week_ending=SAT,
                as_of=SAT, review_day=SUN, registry=registry())
            self.assertEqual(len(result["production_evidence"]), 2)
            self.assertEqual(db.read_bytes(), original)
            self.assertFalse(Path(str(db) + "-wal").exists())
            self.assertFalse(Path(str(db) + "-shm").exists())

    def test_malformed_external_packet_fails_before_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Loader refuses malformed supplied packet, rather than
            # accepting a fabricated or incorrectly authorized research ID.
            packet = Path(tmp) / (SAT + ".json")
            packet.write_text('{"status":"approved","items":[]}', encoding="utf-8")
            with self.assertRaises(ValueError):
                inspect(database=Path(tmp) / "nonexistent.db",
                        marker_path=Path(tmp) / "marker",
                        week_ending=SAT, as_of=SAT, review_day=SUN,
                        registry=registry(), research_directory=Path(tmp))


if __name__ == "__main__":
    unittest.main()
