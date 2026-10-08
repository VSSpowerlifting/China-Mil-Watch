"""Regional Topic Taxonomy v2 -- backwards-compatible version selection.

All assignment tests use memory-only SQLite; none touches production or shadow.
V1 remains the implicit default; v2 is selected explicitly.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.topics import (
    RecordRef,
    TopicAssignment,
    TopicStoreError,
    TopicTaxonomyError,
    attach_topic,
    ensure_topic_store,
    load_taxonomy,
    topics_for_record,
)

ROOT = Path(__file__).resolve().parent.parent
V1_PATH = ROOT / "taxonomy" / "regional_topics.v1.json"
V2_PATH = ROOT / "taxonomy" / "regional_topics.v2.json"
HADR = "military_hadr"


class VocabularyV2(unittest.TestCase):
    def test_legacy_default_still_loads_v1(self):
        default = load_taxonomy()
        self.assertEqual(default.taxonomy_version, 1)
        self.assertEqual(len(default.topics), 19)
        self.assertNotIn(HADR, default.topic_slugs)

    def test_v2_adds_one_topic_preserving_all_v1_slug_identities(self):
        v1, v2 = load_taxonomy(version=1), load_taxonomy(version=2)
        self.assertEqual((v1.taxonomy_version, v2.taxonomy_version), (1, 2))
        self.assertEqual(len(v2.topics), 20)
        self.assertEqual(set(v2.topic_slugs) - set(v1.topic_slugs), {HADR})
        self.assertEqual(set(v1.topic_slugs) - set(v2.topic_slugs), set())
        self.assertEqual([g.slug for g in v1.groups], [g.slug for g in v2.groups])
        self.assertEqual(v2.topic(HADR).group, "operations")

    def test_v2_spelling_and_scope_are_explicit(self):
        v2 = load_taxonomy(version=2)
        self.assertIn("Disaster Response", v2.topic(HADR).display_name)
        self.assertIn("dedicated HADR training", v2.topic(HADR).scope_note)
        self.assertIn("military/security-linked", v2.topic("space_security").scope_note)
        self.assertIn("merely located", v2.topic("east_china_sea").scope_note.lower())
        self.assertIn("Generic supplier", v2.topic("critical_minerals_supply_chains").scope_note)

    def test_v1_file_never_changes_when_loading_v2(self):
        before = V1_PATH.read_bytes()
        load_taxonomy(version=2)
        self.assertEqual(V1_PATH.read_bytes(), before)

    def test_path_declared_version_must_match_explicit_selection(self):
        for path, ver in [(V2_PATH, 1), (V1_PATH, 2)]:
            with self.subTest(path=path.name, requested=ver):
                with self.assertRaisesRegex(TopicTaxonomyError, "unsupported taxonomy_version"):
                    load_taxonomy(path, version=ver)

    def test_unsupported_versions_fail_closed_without_falling_back(self):
        for version in [True, False, 0, 3, 99, "2", None]:
            with self.subTest(version=version):
                with self.assertRaisesRegex(TopicTaxonomyError, "unsupported taxonomy_version"):
                    load_taxonomy(version=version)

    def test_malformed_v2_duplicate_slug_is_rejected(self):
        raw = json.loads(V2_PATH.read_text(encoding="utf-8"))
        raw["topics"].append(dict(raw["topics"][0]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad-v2.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(TopicTaxonomyError, "duplicate topic"):
                load_taxonomy(path, version=2)

    def test_changed_group_ref_is_rejected(self):
        raw = json.loads(V2_PATH.read_text(encoding="utf-8"))
        raw["topics"][0]["group"] = "nonexistent"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad-v2.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(TopicTaxonomyError, "unknown group"):
                load_taxonomy(path, version=2)


class AssignmentV2(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.record = RecordRef(
            desk_id="philippines",
            source_slug="ph_afp",
            canonical_url="https://www.afp.mil.ph/example-response",
        )
        ensure_topic_store(self.conn)

    def tearDown(self):
        self.conn.close()

    def assignment(self, slug, version, by="editor"):
        return TopicAssignment(
            record=self.record,
            topic_slug=slug,
            assignment_method="human",
            assigned_by=by,
            assigned_at="2026-10-07T23:20:00Z",
            evidence="Temporary fixture evidence; no real-world assignment.",
            taxonomy_version=version,
        )

    def test_v2_hadr_assignment_is_valid_only_under_v2(self):
        a = self.assignment(HADR, 2)
        self.assertTrue(attach_topic(self.conn, a))
        self.assertEqual([x.topic_slug for x in topics_for_record(self.conn, self.record, taxonomy_version=2)], [HADR])
        self.assertEqual(topics_for_record(self.conn, self.record), [])
        with self.assertRaisesRegex(TopicTaxonomyError, "unknown regional topic"):
            attach_topic(self.conn, self.assignment(HADR, 1))

    def test_same_slug_coexists_at_both_versions_and_returns_only_requested_version(self):
        self.assertTrue(attach_topic(self.conn, self.assignment("military_exercises", 1)))
        self.assertTrue(attach_topic(self.conn, self.assignment("military_exercises", 2)))
        self.assertTrue(attach_topic(self.conn, self.assignment(HADR, 2)))
        self.assertEqual(
            [(a.topic_slug, a.taxonomy_version) for a in topics_for_record(self.conn, self.record)],
            [("military_exercises", 1)],
        )
        self.assertEqual(
            [(a.topic_slug, a.taxonomy_version)
             for a in topics_for_record(self.conn, self.record, taxonomy_version=2)],
            [(HADR, 2), ("military_exercises", 2)],
        )
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM record_topics").fetchone()[0], 3)

    def test_v2_conflicting_provenance_fails_closed(self):
        a = self.assignment(HADR, 2)
        self.assertTrue(attach_topic(self.conn, a))
        self.assertFalse(attach_topic(self.conn, a))
        with self.assertRaises(TopicStoreError):
            attach_topic(self.conn, self.assignment(HADR, 2, by="another-review"))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM record_topics").fetchone()[0], 1)

    def test_cross_version_taxonomy_override_does_not_bypass_validation(self):
        with self.assertRaisesRegex(TopicTaxonomyError, "assignment taxonomy version"):
            attach_topic(self.conn, self.assignment(HADR, 2), taxonomy=load_taxonomy(version=1))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM record_topics").fetchone()[0], 0)

    def test_bool_and_unknown_assignment_versions_remain_refused(self):
        for version in (True, 3, "2"):
            with self.subTest(version=version):
                with self.assertRaisesRegex(TopicTaxonomyError, "assignment taxonomy version"):
                    attach_topic(self.conn, self.assignment(HADR, version))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM record_topics").fetchone()[0], 0)

    def test_v2_does_not_implicitly_create_a_topic_store(self):
        unconfigured = sqlite3.connect(":memory:")
        try:
            with self.assertRaisesRegex(TopicStoreError, "not configured"):
                attach_topic(unconfigured, self.assignment(HADR, 2))
            self.assertFalse(unconfigured.execute(
                "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE name='record_topics')"
            ).fetchone()[0])
            self.assertEqual(
                topics_for_record(unconfigured, self.record, taxonomy_version=2), []
            )
        finally:
            unconfigured.close()

    def test_only_topic_store_is_changed_by_explicit_memory_opt_in(self):
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute("CREATE TABLE articles (id INTEGER PRIMARY KEY, title TEXT)")
            connection.execute("INSERT INTO articles VALUES (42, 'unchanged')")
            before = connection.execute("SELECT * FROM articles").fetchall()
            ensure_topic_store(connection)
            attach_topic(connection, self.assignment(HADR, 2))
            self.assertEqual(connection.execute("SELECT * FROM articles").fetchall(), before)
            self.assertFalse(connection.execute(
                "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE name='schema_migrations')"
            ).fetchone()[0])
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
