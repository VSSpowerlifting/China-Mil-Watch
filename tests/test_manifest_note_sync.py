"""
Registry-sync field-level tests for the mod_china manifest note.

`notes` is a registry-managed column: editing it in desks/china/manifest.json
means the next `sync_desk_config()` writes it into `sources`. Correcting a
misleading note is worth doing, but only if it demonstrably touches nothing
else — a manifest edit that silently re-pointed a base_url, changed an
authority tier or flipped `enabled` would be a production data change wearing
a documentation change's clothes.

These tests are hermetic: they build a temporary database from the legacy
schema, migrate it, and sync against temporary manifest directories. The
tracked pla_watch.db is never opened. The same proof was also run once against
a disposable copy of origin/main:pla_watch.db; see DECISION_LOG 2026-08-17.

Offline: no network, no model calls.
"""

from __future__ import annotations

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

from core.registry import sync_desk_config                       # noqa: E402
from migrations.runner import apply_all                          # noqa: E402
from tests.test_migrations import build_legacy_db                # noqa: E402

MANIFEST = REPO_ROOT / "desks" / "china" / "manifest.json"


def snapshot_sources(conn) -> tuple[list[str], dict]:
    """Every column of every source row, keyed by slug."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(sources)")]
    rows = conn.execute(
        "SELECT %s FROM sources ORDER BY slug" % ", ".join(cols)
    ).fetchall()
    idx = cols.index("slug")
    return cols, {r[idx]: dict(zip(cols, r)) for r in rows}


def field_diff(cols, before: dict, after: dict) -> list[tuple]:
    """Every (slug, column, old, new) that changed."""
    changes = []
    for slug in sorted(set(before) | set(after)):
        if slug not in before:
            changes.append((slug, "<row inserted>", None, None))
            continue
        if slug not in after:
            changes.append((slug, "<row deleted>", None, None))
            continue
        for c in cols:
            if before[slug][c] != after[slug][c]:
                changes.append((slug, c, before[slug][c], after[slug][c]))
    return changes


class TestManifestNoteSync(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

        self.db_path = self.root / "sync.db"
        build_legacy_db(self.db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.addCleanup(self.conn.close)
        apply_all(self.conn)
        sync_desk_config(self.conn)          # baseline: current manifest
        self.conn.commit()

    def _desks_dir_with_note(self, note: str) -> Path:
        """A temp desks/ tree identical to the real one but for mod_china.notes."""
        desks = self.root / "desks_variant"
        if desks.exists():
            shutil.rmtree(desks)
        shutil.copytree(REPO_ROOT / "desks", desks)
        path = desks / "china" / "manifest.json"
        data = json.loads(path.read_text())
        for src in data["sources"]:
            if src["slug"] == "mod_china":
                src["notes"] = note
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        return desks

    # ── the properties under test ────────────────────────────────────────────

    def test_resync_of_the_current_manifest_is_idempotent(self):
        cols, before = snapshot_sources(self.conn)
        sync_desk_config(self.conn)
        self.conn.commit()
        _, after = snapshot_sources(self.conn)
        self.assertEqual(field_diff(cols, before, after), [],
                         "re-syncing an unchanged manifest must change nothing")

    def test_note_only_edit_changes_only_that_note(self):
        cols, before = snapshot_sources(self.conn)
        desks = self._desks_dir_with_note("A corrected note, and nothing else.")

        sync_desk_config(self.conn, desks)
        self.conn.commit()
        _, after = snapshot_sources(self.conn)

        changes = field_diff(cols, before, after)
        self.assertEqual(
            [(slug, col) for slug, col, _, _ in changes],
            [("mod_china", "notes")],
            "a notes-only manifest edit must touch exactly one field",
        )
        self.assertEqual(after["mod_china"]["notes"],
                         "A corrected note, and nothing else.")

    def test_no_managed_fact_other_than_notes_moves(self):
        cols, before = snapshot_sources(self.conn)
        desks = self._desks_dir_with_note("Another corrected note.")
        sync_desk_config(self.conn, desks)
        self.conn.commit()
        _, after = snapshot_sources(self.conn)

        guarded = [c for c in cols if c != "notes"]
        for slug in before:
            for col in guarded:
                self.assertEqual(
                    before[slug][col], after[slug][col],
                    "sources.%s changed for %s during a notes-only edit"
                    % (col, slug),
                )

    def test_note_edit_is_idempotent_on_the_second_sync(self):
        desks = self._desks_dir_with_note("Stable corrected note.")
        sync_desk_config(self.conn, desks)
        self.conn.commit()
        cols, after_first = snapshot_sources(self.conn)

        sync_desk_config(self.conn, desks)
        self.conn.commit()
        _, after_second = snapshot_sources(self.conn)

        self.assertEqual(field_diff(cols, after_first, after_second), [],
                         "the second sync of the same note must be a no-op")

    def test_no_rows_are_inserted_or_deleted_by_a_note_edit(self):
        before_count = self.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        desks = self._desks_dir_with_note("Counting note.")
        sync_desk_config(self.conn, desks)
        self.conn.commit()
        after_count = self.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        self.assertEqual(before_count, after_count)

    def test_database_stays_consistent(self):
        desks = self._desks_dir_with_note("Integrity note.")
        sync_desk_config(self.conn, desks)
        self.conn.commit()
        self.assertEqual(
            self.conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_synced_rows_actually_match_the_manifest(self):
        """
        Before/after comparison alone cannot catch a sync that writes the same
        wrong value every time — the diff would be empty while the database
        disagreed with the manifest. So assert fidelity to the manifest
        directly, field by field, for every governed source.
        """
        manifest = json.loads(MANIFEST.read_text())
        _, rows = snapshot_sources(self.conn)

        for src in manifest["sources"]:
            row = rows[src["slug"]]
            self.assertEqual(row["base_url"], src["base_url"], src["slug"])
            self.assertEqual(row["display_name"], src["display_name"], src["slug"])
            self.assertEqual(row["authority_tier"], src["authority_tier"], src["slug"])
            self.assertEqual(row["source_type"], src["source_type"], src["slug"])
            self.assertEqual(row["originality"], src["originality"], src["slug"])
            self.assertEqual(row["language_tag"], src["language_tag"], src["slug"])
            self.assertEqual(row["access_method"], src["access_method"], src["slug"])
            self.assertEqual(row["institution_id"], src["institution_id"], src["slug"])
            self.assertEqual(
                row["expected_cadence_days"], src["expected_cadence_days"], src["slug"])
            self.assertEqual(
                row["silence_threshold_days"],
                src.get("silence_threshold_days"), src["slug"])
            self.assertEqual(bool(row["enabled"]), bool(src["enabled"]), src["slug"])
            self.assertEqual(row["notes"], src["notes"], src["slug"])

    def test_note_edit_leaves_every_other_field_matching_the_manifest(self):
        """The note-only edit must not desynchronise any other field."""
        desks = self._desks_dir_with_note("Fidelity note.")
        sync_desk_config(self.conn, desks)
        self.conn.commit()
        _, rows = snapshot_sources(self.conn)

        manifest = json.loads(MANIFEST.read_text())
        for src in manifest["sources"]:
            row = rows[src["slug"]]
            self.assertEqual(row["base_url"], src["base_url"], src["slug"])
            self.assertEqual(row["authority_tier"], src["authority_tier"], src["slug"])
            self.assertEqual(
                row["silence_threshold_days"],
                src.get("silence_threshold_days"), src["slug"])
            self.assertEqual(bool(row["enabled"]), bool(src["enabled"]), src["slug"])
        self.assertEqual(rows["mod_china"]["notes"], "Fidelity note.")

    def test_tracked_database_is_never_opened(self):
        self.assertTrue(str(self.db_path).startswith(str(self.root)))
        self.assertNotEqual(self.db_path, REPO_ROOT / "pla_watch.db")


class TestShippedNoteContent(unittest.TestCase):
    """The note we actually ship must say the true things, and not overclaim."""

    @classmethod
    def setUpClass(cls):
        data = json.loads(MANIFEST.read_text())
        cls.src = next(s for s in data["sources"] if s["slug"] == "mod_china")
        cls.note = cls.src["notes"]

    def test_source_is_still_active_tier_a_at_21_days(self):
        self.assertEqual(self.src["authority_tier"], "A")
        self.assertEqual(self.src["silence_threshold_days"], 21)
        self.assertTrue(self.src["enabled"])
        self.assertIn("21 days", self.note)
        self.assertIn("Tier A", self.note)

    def test_note_states_the_source_stayed_live(self):
        self.assertIn("stayed live", self.note)

    def test_note_names_both_causes(self):
        self.assertIn("canonical selection", self.note)
        self.assertIn("discovery", self.note)

    def test_note_does_not_claim_recovery_already_happened(self):
        lowered = self.note.lower()
        for overclaim in ("backfilled", "re-attributed", "reattributed",
                          "has been recovered", "recovery complete"):
            self.assertNotIn(overclaim, lowered,
                             "note must not claim recovery already occurred")
        self.assertIn("has not been performed", lowered)
        self.assertIn("tracked separately", lowered)

    def test_note_still_forbids_inert_classification(self):
        self.assertIn("Do not treat as inert", self.note)


if __name__ == "__main__":
    unittest.main()
