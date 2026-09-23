"""
Indo-Pacific Record Briefs: the source-level foundation (DECISION_LOG 2026-09-23).

Five things are pinned here: the existing issues keep every mark of what they
were published as; records are selected by the brief's named desks; each
source-trail entry keeps its own desk and language; cross-desk claims cite each
desk they compare and never infer coordination; and issue numbers are assigned
at approval, never reassigned, and not assigned at all while No. 14's
publication status is unreconciled.

Fixtures are built, never borrowed: a scratch database made by the real
`init_db()` (schema and migrations, so the China and Singapore sources are
seeded from their manifests), with records inserted through `insert_article()`.
The tracked database is never opened. The Chinese headlines used are read
verbatim from published sidecars, so no Chinese text is composed here.
"""

from __future__ import annotations

import contextlib
import html
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import storage.db as db                                           # noqa: E402
from config import SITE_ORIGIN                                    # noqa: E402
from core import brief_contract as bc                             # noqa: E402
from core.edition_identity import (                               # noqa: E402
    BRIEF_ONLY_FIELDS, COLLECTION_NAME, ERA_CURRENT, ERA_HISTORICAL,
    LAST_HISTORICAL_ISSUE, LAST_PREDECESSOR_ISSUE, SERIES_NAME,
    IdentityError, brief_identity_fields, is_brief, resolve_identity)
from scripts import author_brief                                  # noqa: E402

POSTS = REPO_ROOT / "output" / "the-pla-watch" / "posts"
FEED = REPO_ROOT / "output" / "the-pla-watch" / "feed.xml"
ATOM = {"a": "http://www.w3.org/2005/Atom"}
CJK = re.compile(r"[㐀-鿿]")
WEEK = ("2026-09-13", "2026-09-19")

CMO_URL = "https://fixture.invalid/china-mil-online/1"
SG_URLS = ("https://fixture.invalid/mindef/1", "https://fixture.invalid/mindef/2")
SG_OUTSIDE = "https://fixture.invalid/mindef/outside"


def existing_sidecars() -> dict:
    return {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(POSTS.glob("*.json"))}


def published_chinese_entries(n: int) -> list:
    """`n` trail entries whose stored original headline is Chinese, verbatim."""
    found, urls = [], set()
    for sidecar in existing_sidecars().values():
        for entry in sidecar.get("source_trail") or []:
            url = entry.get("url")
            if CJK.search(entry.get("title_zh") or "") and url and url not in urls:
                found.append(entry)
                urls.add(url)
                if len(found) == n:
                    return found
    raise unittest.SkipTest("no published Chinese headline to reuse")


def registry(live=(), shadow=()):
    """A registry stand-in: only the attributes eligibility reads."""
    return ([SimpleNamespace(slug=s, is_collecting=True,
                             has_production_records=True) for s in live]
            + [SimpleNamespace(slug=s, is_collecting=False,
                               has_production_records=False) for s in shadow])


LIVE = registry(live=("china", "singapore"), shadow=("japan",))


# ── Brief builders for the contract tests ─────────────────────────────────────

def entry(record_id, desk, lang="en"):
    return {"record_id": record_id, "desk": desk, "lang": lang,
            "source_id": "fixture", "source": "Fixture source",
            "title_original": "Fixture title", "title": "Fixture title",
            "url": "https://fixture.invalid/%d" % record_id,
            "date": "2026-09-15", "screening": "analyzed",
            "is_significant": False}


def draft(**changes):
    sidecar = brief_identity_fields()
    sidecar.update({
        "brief_schema": bc.BRIEF_SCHEMA, "editorial_status": bc.STATUS_DRAFT,
        "issue_number": None, "desks": ["china", "singapore"],
        "week_start": "2026-09-13", "week_ending": "2026-09-19",
        "development": {"summary": "", "citations": []},
        "cross_desk_claims": [],
        "source_trail": [entry(1, "china", "zh-Hans"), entry(2, "singapore")],
    })
    sidecar.update(changes)
    return sidecar


def complete(**changes):
    """A draft with everything an approval needs, still unnumbered."""
    sidecar = draft(**{name: "Fixture prose." for name in bc.REQUIRED_SECTIONS})
    sidecar.update({
        "title": "Fixture title for a brief",
        "development": {"summary": "One fixture development.",
                        "citations": [1]},
        "cross_desk_claims": [{
            "claim": "Both institutions published on the development; one "
                     "named its location and the other did not.",
            "desks": ["china", "singapore"], "citations": [1, 2],
            "basis": bc.BASIS_COMPARISON}],
    })
    sidecar.update(changes)
    return sidecar


def approve(sidecar, collection, on="2026-09-27"):
    """Approval as if No. 14 were already reconciled — simulated, not ruled."""
    return bc.approve(sidecar, collection=collection, registry=LIVE,
                      approved_by="Owner (fixture)", approved_on=on,
                      unreconciled=frozenset())


# ── The existing issues ───────────────────────────────────────────────────────

class TestExistingIssuesKeepWhatTheyWerePublishedAs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sidecars = existing_sidecars()
        if not cls.sidecars:
            raise unittest.SkipTest("no published sidecars")

    def test_the_predecessor_series_is_the_issues_that_exist(self):
        numbers = sorted(sc["issue_number"] for sc in self.sidecars.values())
        self.assertEqual(numbers, list(range(1, LAST_PREDECESSOR_ISSUE + 1)))

    def test_every_existing_issue_is_in_the_collection_as_the_pla_watch(self):
        for stem, sidecar in self.sidecars.items():
            with self.subTest(issue=stem):
                for name in ("collection",) + BRIEF_ONLY_FIELDS:
                    self.assertNotIn(name, sidecar, "a sidecar was edited")
                self.assertFalse(is_brief(sidecar))
                identity = resolve_identity(sidecar)
                self.assertEqual(identity["series_name"], SERIES_NAME)
                self.assertEqual(identity["collection"], COLLECTION_NAME)
                self.assertFalse(identity["is_brief"])
                # The published page still carries the stored title verbatim
                # and the series it was published as. (No. 2's title has no
                # series prefix; the attribution is on the page, not the key.)
                page = html.unescape((POSTS / (stem + ".html"))
                                     .read_text(encoding="utf-8"))
                self.assertIn(sidecar["title"], page)
                self.assertIn(SERIES_NAME, page)

    def test_the_publisher_boundary_is_unchanged(self):
        for stem, sidecar in self.sidecars.items():
            with self.subTest(issue=stem):
                expected = (ERA_HISTORICAL
                            if sidecar["issue_number"] <= LAST_HISTORICAL_ISSUE
                            else ERA_CURRENT)
                self.assertEqual(resolve_identity(sidecar)["era"], expected)

    def test_the_legacy_series_constant_keeps_its_name_and_value(self):
        self.assertEqual(SERIES_NAME, "The PLA Watch")

    def test_every_address_and_feed_entry_id_is_unchanged(self):
        root = ET.parse(FEED).getroot()
        ids = {e.findtext("a:id", namespaces=ATOM)
               for e in root.findall("a:entry", ATOM)}
        self.assertEqual(ids, {"%s/the-pla-watch/posts/%s.html"
                               % (SITE_ORIGIN, stem) for stem in self.sidecars})
        for stem in self.sidecars:
            self.assertTrue((POSTS / (stem + ".html")).is_file(), stem)


class TestNothingNewIsPublishedAsThePlaWatch(unittest.TestCase):

    def test_a_sidecar_cannot_declare_itself_the_pla_watch(self):
        with self.assertRaises(IdentityError):
            is_brief({"collection": SERIES_NAME})

    def test_an_issue_after_the_series_must_name_its_collection(self):
        with self.assertRaises(IdentityError):
            resolve_identity({"issue_number": LAST_PREDECESSOR_ISSUE + 1})

    def test_a_brief_shaped_sidecar_must_say_it_is_a_brief(self):
        with self.assertRaises(IdentityError):
            resolve_identity({"desks": ["china", "singapore"]})

    def test_a_brief_is_the_collection_under_the_current_publisher(self):
        identity = resolve_identity(draft())
        self.assertTrue(identity["is_brief"])
        self.assertEqual(identity["series_name"], COLLECTION_NAME)
        self.assertEqual(identity["era"], ERA_CURRENT)
        self.assertEqual(identity["publication"], "Indo-Pacific Record")

    def test_a_brief_cannot_be_published_as_the_predecessor(self):
        for publication in ("China Mil Watch", "Some Other Outlet"):
            sidecar = complete(publication=publication)
            with self.subTest(publication=publication):
                with self.assertRaises(IdentityError):
                    resolve_identity(sidecar)
                problems = bc.validate_brief(sidecar, LIVE)
                self.assertEqual(len(problems), 1, problems)
                self.assertIn(publication, problems[0])

    def test_a_brief_on_a_pre_rename_week_is_still_current(self):
        """
        No `publication` stored and a week before the rename: the date rule
        that places No. 1-13 would put this under China Mil Watch.
        """
        sidecar = complete(week_start="2026-08-16", week_ending="2026-08-22",
                           date="2026-08-22")
        del sidecar["publication"], sidecar["author_title"], sidecar["author_bio"]
        identity = resolve_identity(sidecar)
        self.assertEqual(identity["era"], ERA_CURRENT)
        self.assertEqual(identity["publication"], "Indo-Pacific Record")
        self.assertNotIn("China Mil Watch", identity["author_title"])
        self.assertNotIn("China Mil Watch", identity["author_bio"])
        self.assertEqual(bc.validate_brief(sidecar, LIVE), [])

    def test_a_brief_naming_the_current_publication_is_accepted(self):
        sidecar = complete(publication="Indo-Pacific Record")
        self.assertEqual(resolve_identity(sidecar)["publication"],
                         "Indo-Pacific Record")
        self.assertEqual(bc.validate_brief(sidecar, LIVE), [])

    def test_existing_issues_keep_their_published_publication(self):
        """The brief rule reaches no existing sidecar: each keeps its publisher."""
        for stem, sidecar in existing_sidecars().items():
            with self.subTest(issue=stem):
                identity = resolve_identity(sidecar)
                expected = ("China Mil Watch"
                            if sidecar["issue_number"] <= LAST_HISTORICAL_ISSUE
                            else "Indo-Pacific Record")
                self.assertEqual(identity["publication"], expected)
                self.assertEqual(identity["series_name"], SERIES_NAME)
                if sidecar.get("author_title"):
                    self.assertEqual(identity["author_title"],
                                     sidecar["author_title"])

    def test_brief_identity_is_explicit_and_stores_no_route_bound_links(self):
        fields = brief_identity_fields()
        self.assertEqual(fields["collection"], COLLECTION_NAME)
        self.assertNotIn("author_links", fields)

    def test_the_predecessor_generator_stops_before_reading_or_calling(self):
        import scripts.generate_pla_watch as generator
        guard = AssertionError("reached past the refusal")
        with mock.patch.object(sys, "argv", ["generate_pla_watch.py"]), \
                mock.patch.object(generator, "get_articles_for_date_range",
                                  side_effect=guard), \
                mock.patch.object(generator, "call_claude", side_effect=guard):
            with self.assertRaises(SystemExit) as stopped:
                generator.main()
        self.assertIn("No new issue is authored or published as The PLA Watch",
                      str(stopped.exception.code))


# ── Records from a scratch database ───────────────────────────────────────────

class FixtureCase(unittest.TestCase):
    """China and Singapore records around one week, in a scratch database."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="ipr-briefs-"))
        cls.db_path = cls.tmp / "fixture.db"
        cls.patcher = mock.patch.object(db, "DB_PATH", cls.db_path)
        cls.patcher.start()
        try:
            cls._build()
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def _build(cls):
        db.init_db()
        run = db.start_scrape_run()
        flagged, not_selected, outside = published_chinese_entries(3)
        cls.zh = flagged
        cls.not_selected_url = not_selected["url"]
        records = [
            # (source, url, original title, date, English title, state)
            ("pla_daily", flagged["url"], flagged["title_zh"], "2026-09-15",
             flagged.get("title"), "flagged"),
            ("pla_daily", not_selected["url"], not_selected["title_zh"],
             "2026-09-17", None, "not_selected"),
            ("pla_daily", outside["url"], outside["title_zh"], "2026-09-25",
             outside.get("title"), "analyzed"),
            ("china_mil_online", CMO_URL,
             "Fixture: an English-language China Desk record", "2026-09-16",
             "Fixture: an English-language China Desk record", "analyzed"),
            ("sg_mindef_releases", SG_URLS[0], "Fixture: MINDEF release one",
             "2026-09-14", None, "unscreened"),
            ("sg_mindef_releases", SG_URLS[1], "Fixture: MINDEF release two",
             "2026-09-18", None, "unscreened"),
            ("sg_mindef_releases", SG_OUTSIDE,
             "Fixture: MINDEF release outside the week", "2026-09-01", None,
             "unscreened"),
        ]
        for i, (source, url, title, day, english, state) in enumerate(records):
            rid = db.insert_article({
                "source_slug": source, "url": url, "content_hash": "fx%d" % i,
                "title_original": title, "text_original": "Fixture body.",
                "published_date": day}, run)
            assert rid, "fixture insert failed for %s" % url
            with db.get_conn() as conn:
                if state == "not_selected":
                    conn.execute("UPDATE articles SET passed_relevance = 0 "
                                 "WHERE id = ?", (rid,))
                elif state in ("flagged", "analyzed"):
                    conn.execute(
                        "UPDATE articles SET passed_relevance = 1, "
                        "relevance_score = 0.9, analyzed_at = '2026-09-20', "
                        "is_significant = ?, title_english = ? WHERE id = ?",
                        (1 if state == "flagged" else 0, english, rid))

    def rows(self, desks):
        return db.get_articles_for_desks(*WEEK, desks)


class TestDeskSelection(FixtureCase):

    def test_selection_is_by_the_named_desks_only(self):
        self.assertEqual({r["desk_id"] for r in self.rows(["singapore"])},
                         {"singapore"})
        self.assertEqual({r["desk_id"] for r in self.rows(["china"])},
                         {"china"})
        self.assertEqual({r["desk_id"]
                          for r in self.rows(["china", "singapore"])},
                         {"china", "singapore"})

    def test_only_the_window_is_selected(self):
        urls = {r["url"] for r in self.rows(["china", "singapore"])}
        self.assertNotIn(SG_OUTSIDE, urls)
        self.assertEqual(len(urls), 5)

    def test_unscreened_records_are_selected_not_filtered_out(self):
        singapore = self.rows(["singapore"])
        self.assertEqual({r["url"] for r in singapore}, set(SG_URLS))
        self.assertEqual({bc.screening_state(r) for r in singapore},
                         {bc.SCREENING_AWAITING})

    def test_a_selection_names_at_least_one_desk(self):
        with self.assertRaises(ValueError):
            db.get_articles_for_desks(*WEEK, [])

    def test_a_supplied_read_only_connection_is_honoured(self):
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        try:
            rows = db.get_articles_for_desks(*WEEK, ["singapore"], conn=conn)
        finally:
            conn.close()
        self.assertEqual({r["desk_id"] for r in rows}, {"singapore"})

    def scaffold(self, *argv):
        out = self.tmp / "draft.json"
        out.unlink(missing_ok=True)
        with contextlib.redirect_stderr(io.StringIO()):
            code = author_brief.main(
                ["scaffold", "--week-ending", WEEK[1], "--db",
                 str(self.db_path), "--out", str(out), *argv])
        return code, (json.loads(out.read_text(encoding="utf-8"))
                      if out.exists() else None)

    def test_the_scaffold_drafts_from_the_named_desks(self):
        code, brief = self.scaffold("--desks", "china,singapore")
        self.assertEqual(code, 0)
        self.assertEqual(brief["collection"], COLLECTION_NAME)
        self.assertIsNone(brief["issue_number"])
        self.assertEqual({e["desk"] for e in brief["source_trail"]},
                         {"china", "singapore"})
        # Screened-and-not-selected records are counted but not offered.
        offered = {e["url"] for e in brief["source_trail"]}
        self.assertNotIn(self.not_selected_url, offered)
        self.assertIn(self.zh["url"], offered)
        self.assertEqual(brief["coverage_by_desk"]["china"]["records"], 3)
        self.assertEqual(sum(e["desk"] == "china"
                             for e in brief["source_trail"]), 2)
        self.assertEqual(bc.validate_brief(brief, LIVE), [])

    def test_the_scaffold_refuses_a_desk_that_is_not_live(self):
        code, brief = self.scaffold("--desks", "china,japan")
        self.assertEqual(code, 2)
        self.assertIsNone(brief)

    def test_one_desk_needs_its_approved_exception(self):
        code, brief = self.scaffold("--desks", "singapore")
        self.assertEqual(code, 2)
        self.assertIsNone(brief)
        code, brief = self.scaffold(
            "--desks", "singapore", "--exception-approved-by", "Owner",
            "--exception-approved-on", "2026-09-23",
            "--exception-reason", "Fixture: only one ministry published.")
        self.assertEqual(code, 0)
        self.assertEqual(brief["single_desk_exception"]["approved_by"], "Owner")
        self.assertEqual(bc.validate_brief(brief, LIVE), [])

    def test_the_scaffold_never_writes_inside_output(self):
        with contextlib.redirect_stderr(io.StringIO()):
            code = author_brief.main(
                ["scaffold", "--desks", "china,singapore", "--week-ending",
                 WEEK[1], "--db", str(self.db_path), "--out",
                 str(REPO_ROOT / "output" / "brief-draft.json")])
        self.assertEqual(code, 2)
        self.assertFalse((REPO_ROOT / "output" / "brief-draft.json").exists())


class TestSourceLanguage(FixtureCase):

    def entries(self):
        return {r["url"]: bc.trail_entry(r)
                for r in self.rows(["china", "singapore"])}

    def test_each_entry_keeps_its_own_desk_and_language(self):
        entries = self.entries()
        chinese = entries[self.zh["url"]]
        self.assertEqual((chinese["desk"], chinese["lang"]),
                         ("china", "zh-Hans"))
        self.assertEqual(chinese["title_original"], self.zh["title_zh"])
        self.assertEqual((entries[CMO_URL]["desk"], entries[CMO_URL]["lang"]),
                         ("china", "en"))
        for url in SG_URLS:
            self.assertEqual((entries[url]["desk"], entries[url]["lang"]),
                             ("singapore", "en"))

    def test_no_entry_assumes_its_original_is_chinese(self):
        for url, e in self.entries().items():
            with self.subTest(url=url):
                self.assertNotIn("title_zh", e)
                self.assertEqual(bool(CJK.search(e["title_original"])),
                                 e["lang"].startswith("zh"))

    def test_english_titles_are_stored_or_the_original_never_composed(self):
        entries = self.entries()
        for url in SG_URLS:
            self.assertEqual(entries[url]["title"],
                             entries[url]["title_original"])
        row = dict(self.rows(["china"])[0])
        row.update(source_language_tag="zh-Hans", title_english=None)
        self.assertEqual(bc.trail_entry(row)["title"], "")

    def test_the_model_flag_exists_only_for_analyzed_records(self):
        entries = self.entries()
        self.assertIs(entries[self.zh["url"]]["is_significant"], True)
        for url in SG_URLS:
            self.assertIsNone(entries[url]["is_significant"])

    def test_coverage_is_per_desk_and_never_pooled(self):
        coverage = bc.coverage_by_desk(self.rows(["china", "singapore"]),
                                       ["china", "singapore"])
        self.assertEqual(set(coverage), {"china", "singapore"})
        self.assertEqual(coverage["singapore"]["records"], 2)
        self.assertEqual(coverage["singapore"]["model_flagged"], 0)
        self.assertEqual(coverage["singapore"]["by_screening"],
                         {bc.SCREENING_AWAITING: 2})
        self.assertEqual(coverage["china"]["languages"], ["en", "zh-Hans"])
        self.assertEqual(coverage["china"]["model_flagged"], 1)
        empty = bc.coverage_by_desk([], ["singapore"])
        self.assertEqual(empty["singapore"]["records"], 0)

    def test_screening_codes_are_the_ones_the_site_publishes(self):
        sys.path.insert(0, str(REPO_ROOT / "site" / "preview"))
        import generate_preview
        site_codes = {s["code"] for s in generate_preview.PROCESSING_STATES}
        self.assertEqual(site_codes, {
            bc.SCREENING_ANALYZED, bc.SCREENING_NOT_SELECTED,
            bc.SCREENING_AWAITING, bc.SCREENING_INCOMPLETE})


# ── The contract ──────────────────────────────────────────────────────────────

class TestCrossDeskEvidence(unittest.TestCase):

    def problems(self, sidecar, reg=LIVE):
        return bc.validate_brief(sidecar, reg)

    def assertProblem(self, sidecar, fragment, reg=LIVE):
        found = self.problems(sidecar, reg)
        self.assertTrue(any(fragment in p for p in found),
                        "expected %r among %r" % (fragment, found))

    def test_a_two_desk_draft_and_a_complete_brief_hold(self):
        self.assertEqual(self.problems(draft()), [])
        self.assertEqual(self.problems(complete()), [])

    def test_one_desk_needs_an_approved_exception(self):
        single = dict(desks=["china"], source_trail=[entry(1, "china")])
        self.assertProblem(draft(**single), "at least 2 live desks")
        allowed = draft(**single, single_desk_exception={
            "approved_by": "Owner", "approved_on": "2026-09-23",
            "reason": "Fixture: one ministry published."})
        self.assertEqual(self.problems(allowed), [])
        unapproved = draft(**single, single_desk_exception={"reason": "x"})
        self.assertProblem(unapproved, "at least 2 live desks")

    def test_an_exception_is_not_recorded_on_a_multi_desk_brief(self):
        self.assertProblem(
            draft(single_desk_exception={"approved_by": "Owner",
                                         "approved_on": "2026-09-23",
                                         "reason": "x"}),
            "single_desk_exception is recorded")

    def test_not_every_desk_is_required(self):
        three = registry(live=("china", "singapore", "japan"))
        self.assertEqual(self.problems(draft(), three), [])

    def test_a_desk_that_is_not_live_is_refused(self):
        self.assertProblem(
            draft(desks=["china", "japan"],
                  source_trail=[entry(1, "china"), entry(2, "japan", "ja")]),
            "'japan' is not a live desk")

    def test_every_declared_desk_contributes_evidence(self):
        self.assertProblem(draft(source_trail=[entry(1, "china")]),
                           "'singapore' is declared but no source-trail entry")

    def test_no_entry_comes_from_an_undeclared_desk(self):
        trail = [entry(1, "china"), entry(2, "singapore"), entry(3, "japan")]
        self.assertProblem(draft(source_trail=trail), "does not declare")

    def test_every_entry_records_its_language_and_none_uses_title_zh(self):
        unlabeled = entry(2, "singapore", lang="")
        self.assertProblem(draft(source_trail=[entry(1, "china"), unlabeled]),
                           "records no language tag")
        legacy_key = dict(entry(1, "china", "zh-Hans"), title_zh="x")
        self.assertProblem(
            draft(source_trail=[legacy_key, entry(2, "singapore")]),
            "uses title_zh")

    def test_a_cross_desk_claim_cites_each_desk_it_compares(self):
        claim = {"claim": "Both published on it.", "desks": ["china", "singapore"],
                 "citations": [1], "basis": bc.BASIS_COMPARISON}
        self.assertProblem(complete(cross_desk_claims=[claim]),
                           "about desk 'singapore' without citing")

    def test_coordination_is_never_inferred_from_timing(self):
        worded = {"claim": "The two ministries coordinated their releases.",
                  "desks": ["china", "singapore"], "citations": [1, 2],
                  "basis": bc.BASIS_COMPARISON}
        self.assertProblem(complete(cross_desk_claims=[worded]),
                           "never inferred from similar timing")
        stated = dict(worded, basis=bc.BASIS_STATED, stated_in=[2])
        self.assertEqual(self.problems(complete(cross_desk_claims=[stated])),
                         [])
        unnamed = dict(worded, basis=bc.BASIS_STATED, stated_in=[])
        self.assertProblem(complete(cross_desk_claims=[unnamed]),
                           "stated_in names no cited record")

    def test_an_approved_brief_is_a_comparison_that_begins_with_a_development(self):
        approved = approve(complete(), collection=[])
        self.assertEqual(self.problems(approved), [])
        self.assertProblem(dict(approved, cross_desk_claims=[]),
                           "at least one cross-desk comparison")
        self.assertProblem(dict(approved, development={"summary": "",
                                                       "citations": []}),
                           "begins with a concrete development")

    def test_no_new_brief_is_titled_as_the_pla_watch(self):
        self.assertProblem(draft(title="The PLA Watch: a fixture"),
                           "no new issue is published as The PLA Watch")

    def test_a_term_records_its_language(self):
        self.assertProblem(draft(term_to_know_term="Fixture term"),
                           "term_to_know_lang")


class TestStableNumbering(unittest.TestCase):

    def setUp(self):
        self.existing = list(existing_sidecars().values())

    def test_no_number_is_assigned_while_no_14_is_unreconciled(self):
        self.assertIn(14, bc.UNRECONCILED_ISSUES)
        with self.assertRaises(bc.NumberingBlocked):
            bc.next_issue_number(self.existing)
        with self.assertRaises(bc.NumberingBlocked):
            bc.approve(complete(), collection=self.existing, registry=LIVE,
                       approved_by="Owner", approved_on="2026-09-27")

    def test_a_draft_carries_no_number(self):
        self.assertIn("a draft carries no issue number; numbers are assigned "
                      "at approval",
                      bc.validate_brief(draft(issue_number=15), LIVE))

    def test_the_next_number_follows_approval_not_the_covered_week(self):
        first = approve(complete(week_ending="2026-09-26"), self.existing)
        highest = max(sc["issue_number"] for sc in self.existing)
        self.assertEqual(first["issue_number"], highest + 1)
        earlier_week = approve(
            complete(week_start="2026-08-23", week_ending="2026-08-29",
                     publication_timing="retrospective"),
            self.existing + [first], on="2026-09-28")
        self.assertEqual(earlier_week["issue_number"], first["issue_number"] + 1)
        by_week = 1 + sum(1 for sc in self.existing + [first]
                          if sc.get("week_ending", "") < "2026-08-29")
        self.assertNotEqual(earlier_week["issue_number"], by_week)

    def test_an_approved_number_is_never_reassigned(self):
        first = approve(complete(), self.existing)
        with self.assertRaises(bc.BriefContractError):
            approve(first, self.existing + [first])

    def test_approval_changes_no_other_issue_and_not_the_draft(self):
        pending = complete()
        before = {"existing-%d" % sc["issue_number"]: sc
                  for sc in self.existing}
        approved = approve(pending, self.existing)
        after = dict(before, new=approved)
        self.assertEqual(bc.numbers_changed(before, after), [])
        self.assertIsNone(pending["issue_number"])
        self.assertEqual(pending["editorial_status"], bc.STATUS_DRAFT)

    def test_a_number_is_never_assigned_twice(self):
        twice = [{"issue_number": 3}, {"issue_number": 3}]
        self.assertEqual(bc.check_numbering(twice),
                         ["issue number 3 is assigned twice"])
        with self.assertRaises(bc.BriefContractError):
            bc.next_issue_number(twice, unreconciled=frozenset())

    def test_a_moved_number_is_detected(self):
        self.assertEqual(len(bc.numbers_changed({"a": {"issue_number": 15}},
                                                {"a": {"issue_number": 16}})),
                         1)


if __name__ == "__main__":
    unittest.main()
