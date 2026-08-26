"""
Desk roster contract for the release candidate.

The desk directory is the surface where this project is most able to overstate
itself: a planned desk rendered like a live one, a reference desk quietly
promoted, or an invented count under an empty desk would each be a claim the
corpus cannot support. These tests fix the roster and its states against the
data and configuration they must be derived from, and pin the legacy China
routes the transition must not break.

Nothing here collects, enables a source, or writes to the tracked database.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "site" / "preview"))
import generate_preview as gp                                    # noqa: E402
from core.desk_registry import load_registry                      # noqa: E402
from scripts.reconcile_db import _read_only                      # noqa: E402

TRACKED_DB = REPO_ROOT / "pla_watch.db"
PRODUCTION_OUT = REPO_ROOT / "output"
MANIFESTS = REPO_ROOT / "desks"


class DeskCase(unittest.TestCase):
    """Builds once into a throwaway directory."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="desk-rollout-"))
        cls.out = cls.tmp / "build"
        gp.build(cls.out, "Test Title", TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(TRACKED_DB))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def page(self, name: str) -> str:
        return (self.out / name).read_text(encoding="utf-8")

    @staticmethod
    def db():
        """
        Read the tracked database through the scratch-copy helper.

        Never `sqlite3.connect()` on the tracked file, even read-only: it is in
        WAL mode, so an open can leave a -wal/-shm beside it. That is the run-475
        defect, and `test_workflow_failure_paths` enforces the rule.
        """
        return _read_only(str(TRACKED_DB))


class TestRosterMatchesConfiguration(DeskCase):

    def test_the_registry_is_the_only_desk_roster(self):
        """
        There is no second list. The renderer used to carry a `DESKS`
        presentation constant beside `desks/*/manifest.json`, and two lists of
        desks with no relationship between them is exactly the configuration
        that lets a page promote a desk no source supports.
        """
        source = (REPO_ROOT / "site" / "preview"
                  / "generate_preview.py").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"^DESKS\s*=", "a second desk roster returned")
        self.assertIn("PublicView", source)
        self.assertTrue((REPO_ROOT / "desks" / "registry.json").is_file())

    def test_china_is_the_only_collecting_desk(self):
        live = [e for e in load_registry() if e.is_collecting]
        self.assertEqual([e.slug for e in live], ["china"])

    def test_a_collecting_desk_must_have_an_enabled_source(self):
        """Derived, not declared: the count comes from the desk's manifest."""
        for entry in load_registry():
            with self.subTest(desk=entry.slug):
                if entry.is_collecting:
                    self.assertGreater(entry.enabled_source_count, 0)
                else:
                    self.assertFalse(entry.may_show_record_count)

    def test_a_non_collecting_desk_declares_no_production_records(self):
        for entry in load_registry():
            with self.subTest(desk=entry.slug):
                if not entry.is_collecting:
                    self.assertFalse(entry.has_production_records)

    def test_the_only_desk_in_the_database_is_china(self):
        with self.db() as con:
            desks = [r[0] for r in con.execute("SELECT desk_id FROM desks")]
        self.assertEqual(sorted(desks), ["china"])

    def test_every_enabled_source_belongs_to_the_china_desk(self):
        """A source enabled under any other desk would be collection this
        product has not declared."""
        with self.db() as con:
            rows = con.execute(
                "SELECT slug, desk_id, is_active FROM sources").fetchall()
        self.assertTrue(rows, "no sources configured")
        for slug, desk_id, active in rows:
            with self.subTest(source=slug):
                if active:
                    self.assertEqual(desk_id, "china")

    def test_no_japan_source_exists_or_is_enabled(self):
        with self.db() as con:
            japan = con.execute(
                "SELECT slug FROM sources WHERE desk_id = 'japan' "
                "OR slug LIKE '%japan%' OR slug LIKE '%mod_jp%'").fetchall()
        self.assertEqual(japan, [])

    def test_no_japan_manifest_is_discoverable(self):
        """The draft manifest lives under docs/ precisely so the loader cannot
        find it. If it ever lands in desks/, collection starts by accident."""
        discovered = {p.parent.name for p in MANIFESTS.glob("*/manifest.json")}
        self.assertEqual(discovered, {"china"})

    def test_the_us_is_not_a_live_desk(self):
        us = load_registry().get("us-indopacific")
        self.assertIsNotNone(us)
        self.assertEqual(us.status, "planned")
        self.assertFalse(us.is_collecting)
        self.assertEqual(us.configured_source_count, 0)
        self.assertEqual(us.enabled_source_count, 0)
        self.assertIn("nothing collected", us.status_label.lower())

    def test_singapore_is_shadow_and_is_never_promoted(self):
        """
        The shadow desk is declared, labelled by its ledger status, and
        counted nowhere. Its manifest is read for its sources — one, disabled —
        and it may not claim a record count.
        """
        sg = load_registry().get("singapore")
        self.assertIsNotNone(sg)
        self.assertEqual(sg.status, "shadow")
        self.assertFalse(sg.is_collecting)
        self.assertEqual(sg.configured_source_count, 1)
        self.assertEqual(sg.enabled_source_count, 0)
        self.assertFalse(sg.may_show_record_count)

    def test_the_shadow_manifest_stays_outside_production_discovery(self):
        """
        Pointing the registry at the shadow manifest must not make it
        discoverable. `load_all_desks()` globs `desks/*/manifest.json`; the
        shadow manifest lives elsewhere and syncing configuration must never
        write a Singapore desk into the tracked database.
        """
        sg = load_registry().get("singapore")
        self.assertEqual(sg.manifest_path, "shadow/singapore_mindef/manifest.json")
        self.assertFalse((MANIFESTS / "singapore" / "manifest.json").exists())
        discovered = {p.parent.name for p in MANIFESTS.glob("*/manifest.json")}
        self.assertEqual(discovered, {"china"})

    def test_no_shadow_day_count_reaches_a_public_surface(self):
        """
        A day counter copied out of the ledger is stale the next morning and
        reads as a promise. The page states the requirement, never the elapsed
        count.
        """
        html = self.page("singapore.html").lower()
        for counter in (r"day\s+\d+\s+of\s+30", r"\d+\s*/\s*30\s*days",
                        r"\d+\s+shadow\s+days?", r"shadow\s+day\s+\d+"):
            with self.subTest(pattern=counter):
                self.assertNotRegex(html, counter)
        # The requirement is stated; the elapsed count is not.
        self.assertIn("consecutive days required</dt><dd>30", html)
        self.assertIn("not a qualified desk", html)

    def test_no_review_verdict_is_published(self):
        html = self.page("singapore.html").lower()
        self.assertIn("no review has been completed", html)
        self.assertIn("no verdict has been reached", html)
        for premature in ("is qualified", "has qualified", "verdict:",
                          "approved for launch", "cleared for launch"):
            with self.subTest(claim=premature):
                self.assertNotIn(premature, html)

    def test_counts_are_never_hard_coded_in_a_template(self):
        """Every figure a reader sees must come from the corpus."""
        templates = (REPO_ROOT / "site" / "preview" / "templates")
        for tpl in sorted(templates.glob("*.html")):
            text = tpl.read_text(encoding="utf-8")
            with self.subTest(template=tpl.name):
                self.assertNotRegex(
                    text, r"\b\d[\d,]{2,}\s+(records|articles|sources)\b",
                    "%s hard-codes a corpus figure" % tpl.name)


class TestJapanDeskIsPlannedNotCoverage(DeskCase):

    def test_the_japan_desk_page_exists_and_is_linked(self):
        self.assertTrue((self.out / "japan.html").is_file())
        self.assertIn('href="japan.html"', self.page("desks.html"))

    def test_the_japan_page_states_zero_records_and_zero_sources(self):
        html = self.page("japan.html")
        self.assertIn("Records</dt><dd>None collected", html)
        self.assertIn("Sources enabled</dt><dd>0", html)
        self.assertIn("No source is enabled. No collector exists.", html)

    def test_the_japan_page_shows_no_collection_statistic(self):
        """Observed publication volume describes the ministry's output, not
        ours. Nothing may read as a record count for this desk.

        The page may — and does — name the 30-day shadow gate and say that
        cadence and silence thresholds are deliberately unset. Those are the
        governing disclosures. What must never appear is a *running* shadow-day
        counter or a calibrated threshold, either of which would imply a clock
        that has started."""
        html = self.page("japan.html")
        self.assertNotRegex(
            html, r"\b\d[\d,]*\s+(records|articles)\s+collected\b")
        lower = html.lower()
        for counter in (r"day\s+\d+\s+of\s+30", r"\d+\s*/\s*30\s*days",
                        r"\d+\s+shadow\s+days?", r"shadow\s+day\s+\d+"):
            with self.subTest(pattern=counter):
                self.assertNotRegex(lower, counter)
        for raw_field in ("expected_cadence_days", "silence_threshold_days"):
            with self.subTest(field=raw_field):
                self.assertNotIn(raw_field, lower)
        self.assertIn("thresholds remain unset", lower)

    def test_the_japan_page_is_not_described_as_coverage(self):
        html = re.sub(r"\s+", " ", self.page("japan.html").lower())
        self.assertIn("it is not coverage", html)
        for claim in ("japan coverage", "covering japan", "japan corpus"):
            with self.subTest(claim=claim):
                self.assertNotIn(claim, html)

    def test_the_access_problem_is_disclosed_without_promising_a_workaround(self):
        html = self.page("japan.html")
        self.assertIn("access", html.lower())
        for evasion in ("bypass", "circumvent", "user agent", "user-agent",
                        "proxy", "captcha", "fingerprint"):
            with self.subTest(term=evasion):
                self.assertNotIn(evasion, html.lower())

    def test_no_planned_desk_is_counted_as_a_live_one(self):
        html = self.page("index.html")
        self.assertIn("1</b> collecting desk", html)
        self.assertIn("of <b>4</b> declared", html)


class TestLegacyChinaRoutesSurvive(DeskCase):

    EDITIONS = ("2026-05-09", "2026-05-16", "2026-05-23", "2026-05-30",
                "2026-06-06", "2026-06-13", "2026-06-20", "2026-06-27",
                "2026-07-04", "2026-07-11", "2026-07-18", "2026-08-01",
                "2026-08-08")

    def test_all_thirteen_editions_exist_in_production_output(self):
        for edition in self.EDITIONS:
            path = PRODUCTION_OUT / "the-pla-watch" / "posts" / (edition + ".html")
            with self.subTest(edition=edition):
                self.assertTrue(path.is_file())

    def test_the_preview_links_editions_to_the_live_site_and_copies_none(self):
        html = self.page("pla-watch.html")
        for edition in self.EDITIONS:
            with self.subTest(edition=edition):
                self.assertIn(
                    "https://chinamilwatch.org/the-pla-watch/posts/%s.html"
                    % edition, html)
                self.assertFalse(
                    (self.out / "the-pla-watch" / "posts"
                     / (edition + ".html")).exists(),
                    "an edition was copied into the prototype")

    def test_the_pla_watch_remains_a_china_desk_series(self):
        html = self.page("pla-watch.html")
        self.assertIn("China", html)
        self.assertNotIn("Japan Desk", html)

    def test_the_pla_watch_page_is_labelled_as_a_legacy_series(self):
        """
        The issues were published under the predecessor masthead. Saying so is
        the difference between preserving a record and backdating a rebrand.
        """
        html = self.page("pla-watch.html")
        self.assertIn("The PLA Watch", html)
        self.assertIn("China Mil Watch", html)
        self.assertIn("preserved as published", html.lower())
        self.assertIn("did not", html)

    def test_the_prototype_never_writes_into_the_production_namespace(self):
        for reserved in ("article", "the-pla-watch"):
            with self.subTest(namespace=reserved):
                self.assertFalse((self.out / reserved).exists())


class TestProductionArtifactsAreUntouched(unittest.TestCase):
    """The release candidate reads production; it never edits it."""

    def test_no_sidecar_sits_beside_the_tracked_database(self):
        for ext in ("-wal", "-shm"):
            with self.subTest(sidecar=ext):
                self.assertFalse(Path(str(TRACKED_DB) + ext).exists())

    def test_the_generator_opens_the_database_read_only(self):
        source = (REPO_ROOT / "site" / "preview"
                  / "generate_preview.py").read_text(encoding="utf-8")
        self.assertIn("_read_only", source)
        self.assertNotRegex(
            source, r"sqlite3\.connect\(\s*str\(db_path\)\s*\)",
            "the generator must not open the tracked database read-write")


class TestPrintAndStateLegibility(unittest.TestCase):
    """
    Two rendering defects found in visual QA, pinned so they cannot return.

    Neither is cosmetic. A state marker that renders as a tofu box removes the
    at-a-glance distinction between a desk that collects and one that does not,
    and a print rule that expands every href buries the record text under its
    own plumbing on exactly the pages a reader would print.
    """

    CSS = (REPO_ROOT / "site" / "preview" / "styles.css")

    #: Glyphs measured against the live font stack (Inter, system-ui, …) in the
    #: browser. Those that resolve draw at ~11px; U+25EB and U+25E7 draw at
    #: 7.22px, the fallback width, because neither font has them.
    RENDERABLE = set("◼◻▣□■◐▪▫")
    MISSING = set("◫◧◨◩◪")

    def css(self):
        return self.CSS.read_text(encoding="utf-8")

    def test_no_desk_state_marker_uses_an_unrenderable_glyph(self):
        markers = re.findall(r'\.desk[-]{1,2}(?:state--)?[a-z_]+[^{]*::before'
                             r'\s*\{\s*content:\s*"([^"]*)"',
                             self.css())
        self.assertTrue(markers, "no desk-state markers found")
        for marker in markers:
            for ch in marker.strip():
                with self.subTest(glyph=ch):
                    self.assertNotIn(ch, self.MISSING,
                                     "U+%04X has no glyph in the font stack "
                                     "and renders as a tofu box" % ord(ch))
                    self.assertIn(ch, self.RENDERABLE)

    def test_every_desk_state_has_one_distinct_marker(self):
        """
        Grouped by STATE, not by selector: a state is legitimately styled twice
        — once for its directory entry (`.desk--scoped .desk-state`) and once
        for its own desk page (`.desk-state--scoped`), where there is no `.desk`
        wrapper to select through. Both must draw the same glyph, and no two
        states may share one.
        """
        pairs = re.findall(
            r'\.desk[-]{1,2}(?:state--)?'
            r'(live|shadow|access_blocked|research|planned|paused)'
            r'[^{]*::before\s*\{\s*content:\s*"([^"]*)"', self.css())
        self.assertTrue(pairs, "no desk-state markers found")
        by_state = {}
        for state, glyph in pairs:
            by_state.setdefault(state, set()).add(glyph.strip())
        for state, glyphs in by_state.items():
            with self.subTest(state=state):
                self.assertEqual(len(glyphs), 1,
                                 "%s draws inconsistent markers: %s"
                                 % (state, sorted(glyphs)))
        used = [next(iter(g)) for g in by_state.values()]
        self.assertEqual(len(used), len(set(used)),
                         "two desk states share a marker")
        # Every status the registry can hold has a marker, so a desk moving
        # into `paused` or `research` cannot render an unmarked state.
        from core.domain import DESK_STATUSES
        self.assertEqual(set(by_state), set(DESK_STATUSES))

    def test_print_expands_only_absolute_urls(self):
        css = self.css()
        print_block = css.split("@media print", 1)[1]
        self.assertNotRegex(
            print_block, r'(?<![\]\w"])\ba::after',
            "an unscoped a::after prints a URL beside every internal link")
        self.assertIn('a[href^="http"]::after', print_block)

    def test_print_suppresses_fragment_and_mailto_urls(self):
        block = self.css().split("@media print", 1)[1]
        for selector in ('a[href^="#"]::after', 'a[href^="mailto:"]::after'):
            with self.subTest(selector=selector):
                self.assertIn(selector, block)

    def test_print_keeps_a_record_whole_across_a_page_break(self):
        block = self.css().split("@media print", 1)[1]
        self.assertIn("break-inside: avoid", block)
        self.assertIn("article.record", block)

    def test_print_keeps_a_column_header_with_its_rows(self):
        """A `thead` stranded at the foot of a page labels nothing."""
        block = self.css().split("@media print", 1)[1]
        self.assertRegex(block, r"thead\s*\{[^}]*break-after:\s*avoid")

    def test_print_does_not_clip_a_scrolling_table(self):
        block = self.css().split("@media print", 1)[1]
        self.assertRegex(block, r"\.table-scroll\s*\{[^}]*overflow:\s*visible")


if __name__ == "__main__":
    unittest.main()
