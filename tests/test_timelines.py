"""Synthetic chronology contracts; no invented Chinese or production writes."""
import copy
import dataclasses
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from core.desk_registry import load_registry
from core import timelines as t

ROOT = Path(__file__).resolve().parent.parent
PILOT = ROOT / "timelines/maritime-cooperation-2026.json"


def synthetic_timeline():
    """Invented test prose and IDs, never an editorial source or public fixture."""
    return dict(timeline_schema=1, slug="synthetic-chronology", title="Synthetic chronology fixture",
                dek="Invented English test prose, never published.", editorial_status="draft",
                scope="Synthetic contract testing only.", methodology_note="Not source evidence.",
                updated_on="2026-10-07", reviewed_on="2026-10-07", author_name="Fixture author",
                editor_name="Fixture editor", related_briefs=["synthetic-brief"], entries=[dict(
                    id="synthetic-event", headline="Invented test event", observation="Test-only assertion.",
                    event=dict(start="2026-09-05", end="2026-09-05", precision="day",
                               date_basis="Explicit synthetic date."), event_kind="occurrence", contested=False,
                    evidence=[dict(record_id=9001, desk="singapore", source_id="sg_mindef_releases",
                                   institution_id="sg_mindef", published_on="2026-09-05",
                                   url="https://fixture.test/synthetic", basis="reported",
                                   claim="Synthetic claim only.", excerpt="Synthetic preserved evidence for testing.")])])


def approve_fixture(sc):
    sc["editorial_status"] = "approved"
    sc["approval"] = dict(approved_by=sc["editor_name"], approved_on=sc["updated_on"],
                          reference="Simulated approval for disposable test fixture only.",
                          content_sha256=t.content_digest(sc))
    return sc


def write_db(path):
    with sqlite3.connect(path) as c:
        c.executescript("""
          CREATE TABLE articles(id INTEGER, title_original TEXT, title_english TEXT,
              text_original TEXT, published_date TEXT, url TEXT, source_id INTEGER);
          CREATE TABLE sources(id INTEGER, slug TEXT, desk_id TEXT, institution_id TEXT,
              display_name TEXT, language_tag TEXT, enabled INTEGER);
          CREATE TABLE institutions(institution_id TEXT, display_name TEXT);
          INSERT INTO institutions VALUES ('sg_mindef', 'Synthetic institution fixture');
          INSERT INTO sources VALUES (1, 'sg_mindef_releases', 'singapore', 'sg_mindef',
              'Synthetic source fixture', 'en', 1);
          INSERT INTO articles VALUES (9001, '<script>Synthetic original headline</script>', '',
              'Synthetic preserved evidence for testing.', '2026-09-05',
              'https://fixture.test/synthetic', 1);
        """)


class TimelineContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "synthetic.db"
        write_db(self.db)
        self.sc = synthetic_timeline()
        self.sources = self.root / "timelines"
        self.sources.mkdir()
        self.path = self.sources / "synthetic-chronology.json"
        self.related = {"synthetic-brief": dict(slug="synthetic-brief", title="Synthetic related Brief",
                                               url="briefs/synthetic-brief.html")}

    def write(self):
        self.path.write_text(json.dumps(self.sc), encoding="utf-8")

    def test_valid_draft_is_withheld_and_explicit_review_is_unapproved(self):
        self.write()
        public, withheld = t.load_timelines(self.db, self.related, self.sources)
        self.assertEqual(public, [])
        self.assertEqual(withheld, [self.sc["slug"]])
        views, _ = t.load_timelines(self.db, self.related, self.sources, self.path)
        self.assertTrue(views[0]["is_review"])
        self.assertEqual(views[0]["editorial_status"], "draft")

    def test_approval_binds_exact_content_and_is_not_inherited(self):
        approve_fixture(self.sc)
        self.write()
        views, _ = t.load_timelines(self.db, self.related, self.sources)
        self.assertEqual(len(views), 1)
        self.sc["title"] = "Changed since approval"
        with self.assertRaisesRegex(t.TimelineError, "changed since approval"):
            t.validate_timeline(self.sc)
        self.sc = synthetic_timeline()
        self.sc["editorial_status"] = "approved"
        with self.assertRaises(t.TimelineError):
            t.validate_timeline(self.sc)

    def test_bad_dates_precision_chronology_and_future_unlabelled_events(self):
        changes = [dict(start="2026-02-30"), dict(start="2026-9-05"), dict(end="2026-09-04"),
                   dict(precision="interval"), dict(start="2026-09-06", end="2026-09-06"),
                   dict(end="2026-12-01", precision="interval")]
        for change in changes:
            with self.subTest(change=change):
                sc = copy.deepcopy(self.sc)
                sc["entries"][0]["event"].update(change)
                with self.assertRaises(t.TimelineError):
                    t.validate_timeline(sc)
        later = copy.deepcopy(self.sc["entries"][0])
        later["id"] = "another-event"
        self.sc["entries"].append(later)
        with self.assertRaisesRegex(t.TimelineError, "chronological"):
            t.validate_timeline(self.sc)

    def test_duplicate_ids_orphans_and_disagreement_references(self):
        self.sc["entries"].append(copy.deepcopy(self.sc["entries"][0]))
        with self.assertRaisesRegex(t.TimelineError, "duplicate ID"):
            t.validate_timeline(self.sc)
        self.sc = synthetic_timeline()
        self.sc["entries"][0]["evidence"][0]["record_id"] = 99999
        with self.assertRaisesRegex(t.TimelineError, "orphan record"):
            t.reconcile_sources(self.sc, self.db)
        self.sc = synthetic_timeline()
        self.sc["reconciliation"] = [dict(heading="Synthetic dispute", note="Synthetic note",
                                         entry_ids=["missing-event"])]
        with self.assertRaisesRegex(t.TimelineError, "orphan entry"):
            t.validate_timeline(self.sc)

    def test_every_identity_field_and_excerpt_must_match_preserved_record(self):
        for field, value in (("desk", "china"), ("source_id", "pla_daily"),
                             ("institution_id", "cn_mnd"), ("published_on", "2026-09-06"),
                             ("url", "https://fixture.test/other"), ("excerpt", "Not the preserved source original.")):
            with self.subTest(field=field):
                sc = copy.deepcopy(self.sc)
                sc["entries"][0]["evidence"][0][field] = value
                with self.assertRaises(t.TimelineError):
                    t.reconcile_sources(sc, self.db)

    def test_shadow_disabled_and_ambiguous_sources_are_refused(self):
        registry = load_registry()
        changed = [dataclasses.replace(d, status="shadow") if d.slug == "singapore" else d for d in registry]
        with self.assertRaisesRegex(t.TimelineError, "shadow"):
            t.reconcile_sources(self.sc, self.db, changed)
        for update in ("enabled=0", "language_tag='zh-Hans'", "institution_id='unknown'"):
            with sqlite3.connect(self.db) as c:
                c.execute("UPDATE sources SET " + update)
            with self.assertRaisesRegex(t.TimelineError, "provenance"):
                t.reconcile_sources(self.sc, self.db)

    def test_empty_evidence_unknown_fields_and_unsafe_paths(self):
        for key, value in (("timeline_schema", True), ("slug", "../escape"), ("author_name", ""),
                           ("reviewed_on", "2026-10-08"), ("reconciliation", {})):
            with self.subTest(key=key):
                sc = copy.deepcopy(self.sc)
                sc[key] = value
                with self.assertRaises(t.TimelineError):
                    t.validate_timeline(sc)
        self.sc["entries"][0]["evidence"] = []
        with self.assertRaises(t.TimelineError):
            t.validate_timeline(self.sc)
        self.sc = synthetic_timeline()
        self.write()
        symlink = self.sources / "alias.json"
        symlink.symlink_to(self.path)
        with self.assertRaises(t.TimelineError):
            t.read_timeline(symlink, self.sources)
        self.path.write_text('{"slug":"one","slug":"two"}')
        with self.assertRaisesRegex(t.TimelineError, "duplicate key"):
            t.read_timeline(self.path, self.sources)

    def test_ledger_deduplicates_records_with_multiple_attributed_claims(self):
        second = copy.deepcopy(self.sc["entries"][0])
        second["id"] = "z-second-claim"
        second["contested"] = True
        second["disagreement_note"] = "Synthetic disagreement, not a resolved date."
        self.sc["entries"].append(second)
        self.sc["reconciliation"] = [dict(heading="Synthetic comparison", note="Unresolved synthetic accounts.",
                                         entry_ids=["synthetic-event", "z-second-claim"])]
        records = t.reconcile_sources(self.sc, self.db)
        view = t.timeline_view(self.sc, records, self.related)
        self.assertEqual(view["source_count"], 1)
        self.assertEqual(len(view["entries"]), 2)

    def test_unsafe_urls_duplicate_citations_and_orphan_related_briefs(self):
        for url in ("javascript:alert(1)", "https://user:pass@fixture.test/x", "https://fixture.test/x#hidden",
                    "https://fixture.test/\\escape", "https://fixture.test/ bad"):
            sc = copy.deepcopy(self.sc)
            sc["entries"][0]["evidence"][0]["url"] = url
            with self.subTest(url=url), self.assertRaises(t.TimelineError):
                t.validate_timeline(sc)
        self.sc["entries"][0]["evidence"] *= 2
        with self.assertRaisesRegex(t.TimelineError, "duplicate citation"):
            t.validate_timeline(self.sc)
        self.sc = approve_fixture(synthetic_timeline())
        self.write()
        with self.assertRaisesRegex(t.TimelineError, "approved native Brief"):
            t.load_timelines(self.db, {}, self.sources)

    def test_contested_accounts_need_reconciliation_and_report_dates_are_distinct(self):
        self.sc["entries"][0]["contested"] = True
        self.sc["entries"][0]["disagreement_note"] = "Synthetic unresolved boundary."
        with self.assertRaisesRegex(t.TimelineError, "comparison panel"):
            t.validate_timeline(self.sc)
        self.sc = synthetic_timeline()
        self.sc["entries"][0]["event_kind"] = "report"
        self.sc["entries"][0]["event"].update(start="2026-09-04", end="2026-09-04")
        with self.assertRaisesRegex(t.TimelineError, "publication interval"):
            t.validate_timeline(self.sc)

    def test_pilot_source_parity_and_read_only_preservation(self):
        before = hashlib.sha256((ROOT / "pla_watch.db").read_bytes()).digest()
        sc = t.read_timeline(PILOT)
        records = t.reconcile_sources(sc, ROOT / "pla_watch.db")
        self.assertEqual(set(records), {4164, 3924, 4466, 4472, 4102})
        self.assertEqual(sc["editorial_status"], "draft")
        self.assertEqual(before, hashlib.sha256((ROOT / "pla_watch.db").read_bytes()).digest())
        self.assertFalse((ROOT / "pla_watch.db-wal").exists())
        self.assertFalse((ROOT / "pla_watch.db-shm").exists())
