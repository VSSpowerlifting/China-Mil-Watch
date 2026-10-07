"""Regional Topic Taxonomy v1 contracts.

The regional layer must be useful across production and shadow stores without
reinterpreting the China Desk's existing article_categories.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.topics import (  # noqa: E402
    RecordRef,
    TopicAssignment,
    TopicStoreError,
    TopicTaxonomyError,
    attach_topic,
    ensure_topic_store,
    load_taxonomy,
    topics_for_record,
)
from migrations.runner import apply_all, connect, verify  # noqa: E402
from tests.test_migrations import build_legacy_db  # noqa: E402


class TaxonomyContract(unittest.TestCase):

    def test_v1_is_cross_desk_and_contains_the_approved_core_topics(self):
        taxonomy = load_taxonomy()
        self.assertEqual(taxonomy.taxonomy_id, "ipr_regional_topics")
        self.assertEqual(taxonomy.taxonomy_version, 1)
        self.assertEqual(len(taxonomy.topics), 19)
        required = {
            "military_exercises",
            "defense_diplomacy",
            "procurement_acquisition",
            "defense_industry",
            "maritime_security",
            "taiwan_strait",
            "south_china_sea",
            "economic_security",
            "cyber_information",
            "space_security",
            "export_controls_sanctions",
            "critical_minerals_supply_chains",
        }
        self.assertTrue(required.issubset(set(taxonomy.topic_slugs)))

    def test_every_slug_and_group_is_unique(self):
        taxonomy = load_taxonomy()
        self.assertEqual(
            len(taxonomy.topic_slugs),
            len(set(taxonomy.topic_slugs)),
        )
        groups = [g.slug for g in taxonomy.groups]
        self.assertEqual(len(groups), len(set(groups)))
        self.assertTrue(all(topic.group in groups for topic in taxonomy.topics))

    def test_malformed_duplicate_topic_is_refused(self):
        raw = json.loads(
            (REPO_ROOT / "taxonomy" / "regional_topics.v1.json")
            .read_text(encoding="utf-8")
        )
        raw["topics"].append(dict(raw["topics"][0]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topics.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(TopicTaxonomyError, "duplicate topic"):
                load_taxonomy(path)

    def test_the_legacy_china_labels_remain_a_separate_unchanged_vocabulary(self):
        raw = json.loads(
            (REPO_ROOT / "desks" / "china" / "taxonomy.json")
            .read_text(encoding="utf-8")
        )
        legacy = [item["slug"] for item in raw["topical_labels"]]
        self.assertEqual(legacy, [
            "taiwan",
            "south_china_sea",
            "east_china_sea",
            "us_china_military",
            "exercises",
            "modernization",
            "doctrine",
            "personnel",
            "nuclear",
            "cyber_info",
            "internal_security",
            "coast_guard",
            "military_diplomacy",
            "political_work",
        ])
        self.assertNotIn("regional_topics", raw)


class AssignmentContract(unittest.TestCase):

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.record = RecordRef(
            desk_id="singapore",
            source_slug="sg_mindef_releases",
            canonical_url="https://www.mindef.gov.sg/news-and-events/latest-releases/example/",
        )

    def tearDown(self):
        self.conn.close()

    def assignment(self, **overrides):
        values = {
            "record": self.record,
            "topic_slug": "military_exercises",
            "assignment_method": "human",
            "assigned_by": "editorial-review",
            "assigned_at": "2026-10-07T23:15:00Z",
            "evidence": "The release describes a named bilateral exercise.",
        }
        values.update(overrides)
        return TopicAssignment(**values)

    def test_attach_is_idempotent_and_query_order_is_deterministic(self):
        self.assertTrue(attach_topic(self.conn, self.assignment()))
        self.assertFalse(attach_topic(self.conn, self.assignment()))
        self.assertTrue(attach_topic(
            self.conn,
            self.assignment(
                topic_slug="defense_diplomacy",
                evidence="The release records formal military-to-military engagement.",
            ),
        ))
        got = topics_for_record(self.conn, self.record)
        self.assertEqual(
            [assignment.topic_slug for assignment in got],
            ["defense_diplomacy", "military_exercises"],
        )

    def test_unknown_topic_fails_before_write(self):
        with self.assertRaisesRegex(TopicTaxonomyError, "unknown regional topic"):
            attach_topic(self.conn, self.assignment(topic_slug="made_up_topic"))
        ensure_topic_store(self.conn)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM record_topics").fetchone()[0],
            0,
        )

    def test_conflicting_provenance_never_silently_overwrites(self):
        attach_topic(self.conn, self.assignment())
        with self.assertRaises(TopicStoreError):
            attach_topic(
                self.conn,
                self.assignment(
                    assigned_by="different-review",
                    evidence="Different provenance must not overwrite the first row.",
                ),
            )
        row = self.conn.execute(
            "SELECT assigned_by FROM record_topics"
        ).fetchone()
        self.assertEqual(row[0], "editorial-review")

    def test_human_assignment_cannot_invent_a_confidence_score(self):
        with self.assertRaisesRegex(
                TopicTaxonomyError, "human assignments do not carry"):
            attach_topic(self.conn, self.assignment(confidence=0.9))

    def test_model_assignment_must_name_provenance_and_valid_confidence(self):
        assignment = self.assignment(
            assignment_method="model",
            assigned_by="topic-classifier:v1",
            confidence=0.82,
        )
        self.assertTrue(attach_topic(self.conn, assignment))
        stored = topics_for_record(self.conn, self.record)[0]
        self.assertAlmostEqual(stored.confidence, 0.82)

    def test_record_identity_requires_a_stable_absolute_url(self):
        bad = RecordRef("singapore", "sg_mindef_releases", "/relative")
        with self.assertRaisesRegex(TopicTaxonomyError, "absolute http"):
            attach_topic(self.conn, self.assignment(record=bad))


    def test_reading_an_unconfigured_store_is_read_only(self):
        self.assertEqual(topics_for_record(self.conn, self.record), [])
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name='record_topics'"
            ).fetchone()[0],
            0,
        )


class StorePortability(unittest.TestCase):

    def test_shadow_shaped_database_can_use_the_same_store_without_articles(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE shadow_records (canonical_url TEXT PRIMARY KEY, body TEXT)"
        )
        record = RecordRef(
            "vietnam",
            "vn_mps_foreign_affairs_vi",
            "https://bocongan.gov.vn/bai-viet/example-1234567890",
        )
        attach_topic(
            conn,
            TopicAssignment(
                record=record,
                topic_slug="defense_diplomacy",
                assignment_method="rule",
                assigned_by="fixture-rule:v1",
                assigned_at="2026-10-07T23:15:00+00:00",
                confidence=1.0,
                evidence="Fixture proves storage portability only.",
            ),
        )
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM record_topics").fetchone()[0],
            1,
        )
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name='articles'"
            ).fetchone()[0],
            0,
        )
        conn.close()

    def test_migration_adds_an_empty_store_and_preserves_every_article_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "legacy.db"
            before = build_legacy_db(db_path, articles=7)
            conn = connect(db_path)
            report = apply_all(conn)
            after_ids = [
                row[0] for row in conn.execute(
                    "SELECT id FROM articles ORDER BY id"
                ).fetchall()
            ]
            topic_count = conn.execute(
                "SELECT COUNT(*) FROM record_topics"
            ).fetchone()[0]
            verified = verify(conn)
            conn.close()

        self.assertIn("0008", report["applied"])
        self.assertEqual(after_ids, before["article_ids"])
        self.assertEqual(topic_count, 0)
        self.assertEqual(verified["counts"]["record_topics"], 0)
        self.assertTrue(verified["ok"])


    def test_partial_migration_table_is_refused_not_blessed(self):
        import migrations.versions.m0008_regional_record_topics as m8

        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE record_topics (desk_id TEXT, source_slug TEXT)"
        )
        self.assertFalse(m8.is_already_applied(conn))
        with self.assertRaisesRegex(sqlite3.IntegrityError, "partial record_topics"):
            m8.up(conn)
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(record_topics)")
        }
        self.assertEqual(columns, {"desk_id", "source_slug"})
        conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
