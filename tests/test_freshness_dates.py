"""
Three dates, because they are three different facts.

The candidate previously showed one run date. That is fine while everything
works and actively misleading the moment it does not. During the 2026-08
provider failure the three came apart:

    records last collected   2026-08-26     collection kept running
    analysis last produced   2026-08-24     analysis stopped
    last full update         2026-08-24     no run finished end to end

A single "last updated" line would have had to pick one of those and imply the
others. Whichever it picked would have been a false claim about how current the
record is.

Two wordings are specifically forbidden and tested against:

  * anything of the form "analysis current through <date>", which asserts that
    every record up to that date was analyzed — the backlog says otherwise;
  * a fabricated substitute for a date that was never measured. Unknown prints
    as "not measured" or "not yet recorded", because that is the true state.
"""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.viewmodel import FreshnessView, PublicView, _marker_date   # noqa: E402

sys.path.insert(0, str(ROOT / "site" / "preview"))
import generate_preview as gp                                        # noqa: E402

TRACKED_DB = ROOT / "pla_watch.db"

#: The opening words of the backlog sentence, and the single anchor every test
#: that cares about it matches on.
#:
#: It lived as a class attribute on one test class while another test matched
#: the bare substring "wait" on a rendered page. The two drifted the moment the
#: state changed, which is exactly what this constant now prevents: a wording
#: change moves every test that depends on it, together.
#:
#: Matched on the opening rather than the whole sentence so a change to the
#: date or the trailing clause does not silently stop these from checking
#: anything.
BACKLOG_SENTENCE = "Analysis trails collection"


class TestTheThreeConceptsAreSeparate(unittest.TestCase):

    def test_they_are_read_from_three_different_authorities(self):
        f = PublicView(TRACKED_DB).freshness()
        self.assertIsNotNone(f.records_last_collected)
        self.assertIsNotNone(f.analysis_last_produced)
        self.assertIsNotNone(f.last_full_update)

    def test_collection_ahead_of_analysis_is_detected(self):
        f = FreshnessView("2026-08-26", "2026-08-24", "2026-08-24")
        self.assertTrue(f.analysis_is_behind_collection)
        self.assertFalse(f.last_run_completed)

    def test_a_fully_caught_up_corpus_reports_neither_flag(self):
        f = FreshnessView("2026-08-26", "2026-08-26", "2026-08-26")
        self.assertFalse(f.analysis_is_behind_collection)
        self.assertTrue(f.last_run_completed)

    def test_an_unknown_date_never_implies_a_comparison(self):
        """Missing data must not be read as "caught up"."""
        for f in (FreshnessView(None, "2026-08-24", "2026-08-24"),
                  FreshnessView("2026-08-26", None, "2026-08-24"),
                  FreshnessView("2026-08-26", "2026-08-24", None)):
            with self.subTest(f=f):
                self.assertIn(f.analysis_is_behind_collection, (True, False))
        self.assertFalse(FreshnessView(None, None, None).analysis_is_behind_collection)
        self.assertFalse(FreshnessView(None, None, None).last_run_completed)

    def test_the_marker_is_read_from_the_workflow_state_file(self):
        self.assertEqual(_marker_date(),
                         (ROOT / ".github" / "state"
                          / "last_daily_run_date.txt").read_text("utf-8").strip())

    def test_a_missing_marker_is_unmeasured_not_today(self):
        self.assertIsNone(_marker_date(ROOT / "does-not-exist.txt"))

    def test_a_junk_marker_is_refused_rather_than_displayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "m.txt"
            for junk in ("", "   ", "soon", "2026-8-2", "not a date at all"):
                bad.write_text(junk, encoding="utf-8")
                with self.subTest(junk=junk):
                    self.assertIsNone(_marker_date(bad))

    def test_no_date_is_derived_from_the_clock_or_the_repository(self):
        """
        Build time and commit time are not evidence about the corpus. A date
        taken from either would move every time the site is rebuilt.
        """
        source = (ROOT / "core" / "viewmodel.py").read_text("utf-8")
        block = source[source.index("class FreshnessView"):
                       source.index("class PublicView")]
        for forbidden in ("datetime.now", "utcnow", "today()", "time.time",
                          "git", "st_mtime"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, block)


class RenderedCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="fresh-")
        gp.build(Path(cls.tmp), gp.PUBLIC_TITLE, TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(TRACKED_DB))
        cls.root = Path(cls.tmp)
        cls.home = (cls.root / "index.html").read_text(encoding="utf-8")
        cls.method = (cls.root / "methodology.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def flat(self, html):
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


class TestTheRenderedPageShowsAllThree(RenderedCase):

    def test_every_label_appears_on_the_home_page(self):
        text = self.flat(self.home)
        for label in ("Records last collected", "Analysis last produced",
                      "Last full update"):
            with self.subTest(label=label):
                self.assertIn(label, text)

    def test_the_rendered_values_match_the_view_model(self):
        f = PublicView(TRACKED_DB).freshness()
        text = self.flat(self.home)
        for label, value in (("Records last collected", f.records_last_collected),
                             ("Analysis last produced", f.analysis_last_produced),
                             ("Last full update", f.last_full_update)):
            with self.subTest(label=label):
                self.assertRegex(text, re.escape(label) + r"\s*" + re.escape(value))

    def test_the_labels_appear_on_a_nested_page_too(self):
        record = (self.root / "record" / "1000.html").read_text(encoding="utf-8")
        self.assertIn("Records last collected", self.flat(record))

    def test_the_methodology_link_resolves_from_a_nested_page(self):
        record = (self.root / "record" / "1000.html").read_text(encoding="utf-8")
        if "methodology.html#freshness" in record:
            self.assertIn("../methodology.html#freshness", record)

    def test_the_methodology_defines_each_term(self):
        text = self.flat(self.method)
        self.assertIn("How current this is", text)
        for label in ("Records last collected", "Analysis last produced",
                      "Last full update"):
            with self.subTest(label=label):
                self.assertIn(label, text)

    def test_the_methodology_says_the_analysis_date_is_not_a_completeness_claim(self):
        text = self.flat(self.method)
        self.assertIn("does not", text.replace("&nbsp;", " "))
        self.assertIn("every record up to that date", text)


class TestForbiddenWordings(RenderedCase):

    def test_no_page_claims_analysis_is_current_through_a_date(self):
        """
        "Analysis current through X" asserts that everything up to X was
        analyzed. With a backlog of unscreened records that is false.
        """
        for page in self.root.rglob("*.html"):
            text = self.flat(page.read_text(encoding="utf-8")).lower()
            with self.subTest(page=page.name):
                self.assertNotIn("analysis current through", text)
                self.assertNotIn("analyzed through", text)
                self.assertNotIn("analysed through", text)

    def test_no_page_calls_the_three_dates_one_thing(self):
        text = self.flat(self.home).lower()
        self.assertNotIn("last updated:", text)

    def test_the_backlog_is_reported_separately_from_the_analysis_date(self):
        """
        The invariant, stated once: `analysis_last_produced` says when analysis
        last RAN, never that everything up to it was analysed. So whenever a
        backlog exists the site has to say so in its own words, and the two
        freshness facts have to stay separately represented either way.

        This assertion used to read `assertIn("wait", coverage)` unconditionally
        and it was only ever true of one state. On 2026-08-31 analysis caught up
        with collection, the site correctly stopped saying records were waiting,
        and the test failed for reporting the truth. A state-dependent contract
        written as a state-independent one.

        Both branches are asserted here, chosen by the corpus rather than by a
        date written into a test:

          behind    the backlog sentence is present, and it NAMES the analysis
                    date — reported separately, not left to be inferred from
                    two dates sitting next to each other;
          caught up the sentence is absent, because claiming records are
                    waiting when none are is the same class of false statement
                    the sentence exists to prevent.

        What holds in both: each freshness fact is present under its own label,
        with its own value. That is the half of this test the old one never
        actually checked.
        """
        f = PublicView(TRACKED_DB).freshness()
        coverage = self.flat(
            (self.root / "coverage.html").read_text(encoding="utf-8"))

        for label, value in (("Records last collected", f.records_last_collected),
                             ("Analysis last produced", f.analysis_last_produced)):
            with self.subTest(label=label):
                self.assertRegex(
                    coverage, re.escape(label) + r"\s*" + re.escape(value),
                    "%s is not represented with its own value" % label)

        if f.analysis_is_behind_collection:
            self.assertIn(BACKLOG_SENTENCE, coverage,
                          "analysis trails collection and the page does not "
                          "say so")
            self.assertIn(f.analysis_last_produced, coverage)
        else:
            self.assertNotIn(BACKLOG_SENTENCE, coverage,
                             "analysis has caught up and the page still "
                             "claims records are waiting")


class TestUnknownDatesDegradeHonestly(unittest.TestCase):
    """
    Older runs did not record any of this. A build against such a database must
    print the absence, not paper over it.
    """

    #: The freshness block is lifted straight out of `base.html` and rendered
    #: alone. Rendering the whole template would drag in a page's worth of
    #: unrelated context, and the failures would then be about that context
    #: rather than about how an unknown date is displayed. Lifting the real
    #: source keeps the test honest: if the block is edited, this follows it.
    @staticmethod
    def _fragment():
        """
        Lifted from `base.html` by its own markers, so an edit to the block
        moves this test with it rather than leaving it asserting against
        markup the site no longer renders.

        The anchors changed on 2026-08-27 when the operational strip became a
        compact freshness bar: `ul.status-facts.freshness` became `dl` inside
        `.freshness-bar`, and `.status-note` became `.behind`. The block itself
        does the same job — three named dates, and one sentence that appears
        only when collection and analysis have come apart.
        """
        base = (ROOT / "site" / "preview" / "templates"
                / "base.html").read_text(encoding="utf-8")
        # Anchored on the class NAME, not on `class="freshness-bar"` with its
        # closing quote: the home page adds a `--lead` modifier, and an anchor
        # that assumed a single class stopped finding the block at all — seven
        # errors that said nothing about the dates they exist to check.
        start = base.index("<dl>", base.index("freshness-bar"))
        end = base.index("{% endif %}", base.index('class="behind"')) + len("{% endif %}")
        return base[start:end]

    def render_with(self, freshness, page="coverage.html"):
        """
        `page` is passed through because the block's own condition reads it:
        the home page carries the backlog sentence in its own note below the
        hero, so the bar suppresses it there and prints it everywhere else.
        Leaving it undefined tested one side of that branch by accident.
        """
        from jinja2 import Environment
        env = Environment()
        return env.from_string(self._fragment()).render(freshness=freshness,
                                                        nested=False, page=page)

    def test_the_fragment_under_test_is_the_one_the_site_renders(self):
        self.assertIn("freshness.records_last_collected", self._fragment())
        self.assertIn("freshness.analysis_is_behind_collection", self._fragment())

    def test_all_three_unknown_renders_placeholders_not_blanks(self):
        html = self.render_with(FreshnessView(None, None, None))
        self.assertIn("not measured", html)
        self.assertIn("not yet recorded", html)

    def test_no_fabricated_date_appears(self):
        html = self.render_with(FreshnessView(None, None, None))
        self.assertNotRegex(html, r"last collected\s*</?b?>?\s*\d{4}-\d{2}-\d{2}")

    #: The note's opening words. Matched rather than the whole sentence so a
    #: wording change does not silently stop these two from checking anything.
    #: The wording moved on 2026-08-30: "Collection is current; analysis is
    #: behind it" claimed currency the three dates cannot support — they show
    #: only that collection ran more recently than analysis, which is equally
    #: true of a corpus last collected a month ago.
    BEHIND_NOTE = BACKLOG_SENTENCE

    def test_the_behind_note_is_suppressed_when_dates_are_unknown(self):
        html = self.render_with(FreshnessView(None, None, None))
        self.assertNotIn(self.BEHIND_NOTE, html)

    def test_the_behind_note_appears_only_when_it_is_true(self):
        behind = self.render_with(FreshnessView("2026-08-26", "2026-08-24", None))
        caught = self.render_with(FreshnessView("2026-08-26", "2026-08-26", None))
        self.assertIn(self.BEHIND_NOTE, behind)
        self.assertNotIn(self.BEHIND_NOTE, caught)

    def test_the_note_does_not_call_collection_current(self):
        """
        The claim that was removed. A date newer than another date is not a
        statement that either is recent.
        """
        behind = self.render_with(FreshnessView("2026-08-26", "2026-08-24", None))
        self.assertNotIn("Collection is current", behind)

    def test_the_note_names_the_date_after_which_records_are_unscreened(self):
        behind = self.render_with(FreshnessView("2026-08-26", "2026-08-24", None))
        self.assertIn("records after 2026-08-24 await screening",
                      " ".join(behind.split()))

    #: The two states the rendered-page test can only check one of at a time.
    #:
    #: `TestForbiddenWordings` asserts against a build of the tracked corpus, so
    #: it exercises whichever state production happens to be in — and the state
    #: it is NOT in goes unchecked. That is how the backlog wording survived
    #: with no coverage until the day it changed. These two render the real
    #: block from `base.html` against synthetic dates instead, so neither state
    #: depends on what collection did last night.

    def test_a_backlog_is_stated_on_a_non_home_page(self):
        behind = self.render_with(
            FreshnessView("2026-08-26", "2026-08-24", "2026-08-24"),
            page="coverage.html")
        flat = " ".join(behind.split())
        self.assertIn(BACKLOG_SENTENCE, flat)
        # Separately represented: the sentence names the analysis date rather
        # than leaving a reader to infer the backlog from two adjacent dates.
        self.assertIn("2026-08-24", flat)
        self.assertIn("2026-08-26", flat)

    def test_a_caught_up_corpus_states_no_backlog_but_still_shows_both_dates(self):
        # Any equal triple is the caught-up state. Deliberately NOT the date
        # production happens to be on: a fixture that quoted it would read as
        # the contract encoding today's corpus, which is the mistake being
        # fixed here.
        caught = self.render_with(
            FreshnessView("2026-08-26", "2026-08-26", "2026-08-26"),
            page="coverage.html")
        flat = " ".join(caught.split())
        self.assertNotIn(BACKLOG_SENTENCE, flat)
        self.assertNotIn("await screening", flat)
        for label in ("Records last collected", "Analysis last produced",
                      "Last full update"):
            with self.subTest(label=label):
                self.assertIn(label, flat)


if __name__ == "__main__":
    unittest.main()


class TestTheDatesAreReadableOnANarrowViewport(unittest.TestCase):
    """
    At 375px the freshness row wrapped "Last full update 2026-08-24" as
    "2026-08-" / "24". A date split across two lines is a number the reader has
    to reassemble before trusting, and this row exists precisely to be trusted.
    """

    @property
    def css(self):
        return (ROOT / "site" / "preview" / "styles.css").read_text("utf-8")

    def test_the_date_value_is_kept_on_one_line(self):
        block = self.css[self.css.index(".status-facts.freshness"):]
        block = block[:block.index("}", block.index("> li > b")) + 1]
        self.assertIn("white-space: nowrap", block)

    def test_the_rule_targets_the_value_not_the_whole_row(self):
        """
        Nowrapping the row would push it off-screen instead of wrapping between
        items. Only the date itself may be unbreakable.
        """
        rows = [l for l in self.css.splitlines()
                if l.strip().startswith(".status-facts.freshness {")]
        self.assertTrue(rows)
        self.assertNotIn("nowrap", rows[0])

    def test_the_row_can_still_wrap_between_items(self):
        base = self.css[self.css.index(".status-facts {"):]
        base = base[:base.index("}") + 1]
        self.assertIn("flex-wrap: wrap", base)
