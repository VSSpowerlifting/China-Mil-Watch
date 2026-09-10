"""
The home page as a paired record: English title primary, original beneath.

Direction C1, as approved 2026-09-09. Three things are under contract here and
each one exists because the current snapshot cannot be trusted to stay the way
it is:

  the opening      one compressed masthead, one consolidated dateline carrying
                   every governed figure, one statement of the claim, and then
                   the record itself — not a description of it;
  the pairing      every displayed record shows its original-language title
                   directly beneath its English title when it genuinely has
                   one, with the language metadata the repository actually
                   stores rather than a hard-coded `zh-Hans`;
  the provenance   a truthful group summary is allowed only while the register
                   really is homogeneous. The lab prototype's example was six
                   records from one institution on one day; the moment a
                   source, an institution or a date differs, each affected row
                   states its own provenance.

Every paired-record and provenance case below renders a CONTROLLED FIXTURE — a
throwaway copy of the corpus whose six newest analyzed records are rewritten to
the shape under test. Asserting against the tracked snapshot alone would only
ever prove the homogeneous case, which is the defect this file exists to
prevent.

Offline. Renders into temporary directories; never `output/`, and never opens
the tracked database for writing.
"""

from __future__ import annotations

import html as html_mod
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "site" / "preview"))

import generate_preview as gp                                    # noqa: E402
from core.viewmodel import PublicView                            # noqa: E402

TRACKED_DB = REPO_ROOT / "pla_watch.db"
TEMPLATES = REPO_ROOT / "site" / "preview" / "templates"
CSS = REPO_ROOT / "site" / "preview" / "styles.css"

#: How many records the home page publishes: one lead plate plus the register.
HOME_RECORDS = 6

#: Two language tags that the desk configuration actually declares
#: (`desks/china/manifest.json` -> supported_language_tags). Chinese and a
#: Latin-script source, which is the pair the approved decision names. Nothing
#: here invents a language the repository does not already support.
ZH = "zh-Hans"
EN = "en"


#: The candidate's own record partial. Tests that render its macros directly
#: are inapplicable on a tree that does not have it — they say so rather than
#: erroring with a template-not-found, which would obscure the product change
#: they exist to detect.
RECORD_PARTIAL = TEMPLATES / "_records.html"


def require_partial(case):
    if not RECORD_PARTIAL.is_file():
        case.skipTest("_records.html is not present: this tree does not carry "
                      "the paired-record partial")


def strip_tags(fragment: str) -> str:
    """Visible text. Entities are resolved: an institution whose name holds an
    apostrophe reaches the page as `&#39;` and must still compare equal to the
    name the corpus stores."""
    return html_mod.unescape(
        re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip()


# ── Fixtures ────────────────────────────────────────────────────────────────
#
# The six newest analyzed records are rewritten in place on a COPY. They are
# given publication dates later than anything else in the corpus so that they
# remain the six the home page selects no matter what the tracked snapshot
# holds — the fixture states its own ordering rather than inheriting one.

def _newest_analyzed_ids(db: Path, count: int) -> list:
    con = sqlite3.connect(str(db))
    try:
        return [r[0] for r in con.execute(
            "SELECT id FROM articles WHERE analyzed_at IS NOT NULL "
            " ORDER BY published_date DESC, id DESC LIMIT ?", (count,))]
    finally:
        con.close()


def _source_ids_by_tag(db: Path) -> dict:
    """slug -> (source_id, language_tag, institution display name)."""
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT s.id, s.slug, s.display_name, s.language_tag, "
            "       i.display_name AS institution "
            "  FROM sources s "
            "  LEFT JOIN institutions i ON i.institution_id = s.institution_id"
        ).fetchall()
    finally:
        con.close()
    return {r["slug"]: dict(r) for r in rows}


def build_fixture(tmp: Path, rows: list, name="fixture"):
    """
    Render a home page whose six newest analyzed records are exactly `rows`.

    `rows` is newest-first. Each entry may set `title_english`,
    `title_original` (None or "" for a record that has none) and `source_slug`;
    dates are assigned descending from a base later than the whole corpus, so
    `dates=True` produces a mixed-date register and the default produces one
    date shared by all six.
    """
    db = tmp / ("%s.db" % name)
    shutil.copy2(TRACKED_DB, db)
    ids = _newest_analyzed_ids(db, len(rows))
    if len(ids) < len(rows):
        raise unittest.SkipTest("corpus holds too few analyzed records")
    sources = _source_ids_by_tag(db)

    con = sqlite3.connect(str(db))
    for position, (record_id, row) in enumerate(zip(ids, rows)):
        slug = row.get("source_slug", "pla_daily")
        con.execute(
            "UPDATE articles SET title_english = ?, title_original = ?, "
            "       published_date = ?, source_id = ? WHERE id = ?",
            (row["title_english"], row.get("title_original"),
             row.get("published_date", "2026-09-20"),
             sources[slug]["id"], record_id))
    con.commit()
    con.close()

    out = tmp / ("%s-build" % name)
    gp.build(out, gp.PUBLIC_TITLE, db, snapshot=gp.snapshot_from_corpus(db))
    home = (out / "index.html").read_text(encoding="utf-8")

    # The fixture verifies its own premise: the records it rewrote are the ones
    # the page actually selected. Without this a mis-ordered fixture would make
    # every assertion below vacuously true.
    selected = gp.load_corpus(db)["recent"][:len(rows)]
    if [r["id"] for r in selected] != ids:
        raise AssertionError("fixture did not become the newest records")
    return home, selected, out


def homogeneous_rows(count=HOME_RECORDS):
    return [{"title_english": "Record %d in English" % n,
             "title_original": "第%d号原文标题" % n,
             "source_slug": "pla_daily",
             "published_date": "2026-09-20"} for n in range(count)]


# ── The opening ─────────────────────────────────────────────────────────────

class HomeCase(unittest.TestCase):
    """One build of the tracked corpus, shared by the structural assertions."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="c1-home-"))
        cls.out = cls.tmp / "build"
        gp.build(cls.out, gp.PUBLIC_TITLE, TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(TRACKED_DB))
        cls.home = (cls.out / "index.html").read_text(encoding="utf-8")
        cls.data = gp.load_corpus(TRACKED_DB)
        cls.view = PublicView(TRACKED_DB)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def dateline(self) -> str:
        self.assertIn("freshness-bar--lead", self.home,
                      "the home page has no consolidated dateline")
        after = self.home.split("freshness-bar--lead", 1)[1]
        return after.split("</div>\n</div>", 1)[0]


class TestTheHomePageIdentityIsPreserved(HomeCase):
    """C1 compresses the masthead. It does not replace the identity."""

    def test_the_wordmark_is_still_the_only_h1(self):
        headings = re.findall(r"<h1[^>]*>(.*?)</h1>", self.home, re.S)
        self.assertEqual(len(headings), 1)
        self.assertIn(gp.PUBLIC_TITLE, headings[0])

    def test_the_mark_still_renders_at_the_documented_size(self):
        img = re.search(r'<img[^>]+class="brand-mark"[^>]*>', self.home)
        self.assertIsNotNone(img, "the compass mark is gone from the masthead")
        self.assertIn('width="56"', img.group(0))
        self.assertIn('height="56"', img.group(0))

    def test_the_compressed_masthead_is_a_home_page_modifier(self):
        """
        The masthead is shared by every record-site page. Compressing it for
        the home page may not silently recompose the archive, the record pages
        or the desks. The modifier is the boundary, and an interior page must
        not carry it.
        """
        self.assertRegex(self.home, r'<header class="masthead[^"]*\bmasthead--lead\b')
        for page in ("archive.html", "desks.html", "coverage.html",
                     "methodology.html", "about.html", "sources.html",
                     "analysis.html"):
            with self.subTest(page=page):
                other = (self.out / page).read_text(encoding="utf-8")
                self.assertNotIn("masthead--lead", other)

    def test_the_masthead_is_not_made_sticky(self):
        """
        The lab prototype pins its masthead to the top of the viewport.
        Production does not, and a sticky header would obstruct the record on
        every scroll. The only sticky element on this site is the record rail.
        """
        css = CSS.read_text(encoding="utf-8")
        for block in re.findall(r"\.masthead[^{]*\{[^}]*\}", css):
            with self.subTest(block=block[:48]):
                self.assertNotIn("position: sticky", block)
                self.assertNotIn("position:sticky", block)
                self.assertNotIn("position: fixed", block)

    def test_the_compact_navigation_keeps_the_collapsed_sections_disclosure(self):
        """
        C1's prototype exposes all seven links at every width. Production
        collapses them into an accessible `<details>` at compact widths, and
        that is retained: the disclosure is a real element, it is closed by
        default (no `open` attribute), and the compact link set lives inside
        it rather than beside it.
        """
        self.assertIn('<details class="nav-toggle nav-mobile">', self.home)
        self.assertIn("<summary>Sections</summary>", self.home)
        details = self.home.split('<details class="nav-toggle nav-mobile">', 1)[1]
        details = details.split("</details>", 1)[0]
        self.assertNotRegex(
            self.home, r'<details class="nav-toggle nav-mobile"[^>]*\bopen\b',
            "the compact disclosure ships expanded")
        for label in ("Record", "Desks", "Sources", "Analysis", "Coverage",
                      "Methodology", "About"):
            with self.subTest(label=label):
                self.assertIn(">%s</a>" % label, details)

    def test_the_skip_link_and_landmarks_survive(self):
        self.assertRegex(self.home, r'<a class="skip" href="#main">')
        for landmark in ("<header", "<nav", '<main id="main"', "<footer"):
            with self.subTest(landmark=landmark):
                self.assertIn(landmark, self.home)

    def test_no_heading_level_is_skipped(self):
        levels = [int(m) for m in re.findall(r"<h([1-6])[^>]*>", self.home)]
        self.assertTrue(levels)
        self.assertEqual(levels[0], 1)
        for previous, current in zip(levels, levels[1:]):
            with self.subTest(previous=previous, current=current):
                self.assertLessEqual(current - previous, 1)


class TestTheDatelineCarriesEveryGovernedFigure(HomeCase):
    """
    Consolidation is a layout change, not permission to drop a disclosure.
    Production states these facts across a five-cell freshness strip, a
    three-row hero ledger and a coverage apron; C1 states each of them once,
    in one band, and none of them may go missing on the way.
    """

    def test_the_three_freshness_labels_stay_with_their_own_values(self):
        f = self.view.freshness()
        text = strip_tags(self.dateline())
        for label, value in (
                ("Records last collected", f.records_last_collected),
                ("Analysis last produced", f.analysis_last_produced),
                ("Last full update", f.last_full_update)):
            with self.subTest(label=label):
                self.assertRegex(text, re.escape(label) + r"\s*"
                                 + re.escape(value or ""))

    def test_the_dateline_states_the_held_and_analyzed_counts_separately(self):
        text = strip_tags(self.dateline())
        held = len(self.data["corpus"])
        analyzed = self.data["totals"]["analyzed"]
        self.assertNotEqual(held, analyzed,
                            "the fixture cannot distinguish the two counts")
        self.assertRegex(text, r"Records held[^0-9]*" + "{:,}".format(held))
        self.assertRegex(text, r"analyzed[^0-9]*" + "{:,}".format(analyzed))

    def test_the_dateline_carries_time_and_corpus_state_and_nothing_else(self):
        """
        Each fact has one home. The dateline is time and corpus state: three
        dates, what is held, how much of it is analysed, and the run it came
        from. Collection TOPOLOGY — how many desks collect and how many
        sources they enable — is stated in the Desks introduction, because
        putting it here made this strip the loudest claim on the page and
        printed the desk ratio twice.
        """
        text = strip_tags(self.dateline())
        for absent in ("Collecting sources", "Collecting desks"):
            with self.subTest(fact=absent):
                self.assertNotIn(absent, text)
        labels = re.findall(r"<dt>(.*?)</dt>", self.dateline(), re.S)
        self.assertEqual([strip_tags(l) for l in labels],
                         ["Records last collected", "Analysis last produced",
                          "Last full update",
                          "Records held, %s" % self.view.desk_directory()
                          .collecting[0].name,
                          "Of those, analyzed"])

    def test_the_desks_introduction_states_the_collection_topology_once(self):
        desks = self.view.desk_directory()
        self.assertTrue(
            hasattr(desks, "collecting_source_count"),
            "DeskDirectory has no collecting_source_count: the enabled-source "
            "total is not derived in the view model")
        intro = self.home.split('<h2 id="desks">', 1)[1]
        intro = intro.split('class="cards', 1)[0]
        self.assertIn("<b>%d</b> collecting desk" % desks.collecting_count,
                      intro)
        self.assertIn("of <b>%d</b> declared" % desks.declared_count, intro)
        self.assertIn("<b>%d</b> enabled source"
                      % desks.collecting_source_count, intro)
        # One sentence, not two: the ratio is stated once on the page.
        self.assertEqual(strip_tags(self.home).count(
            "%d collecting desk" % desks.collecting_count), 1)
        # Grammatical in both directions.
        flat = strip_tags(intro)
        if desks.collecting_source_count == 1:
            self.assertIn("1 enabled source.", flat)
            self.assertNotIn("1 enabled sources", flat)
        else:
            self.assertIn("%d enabled sources." % desks.collecting_source_count,
                          flat)

    def test_the_dateline_names_the_run_and_links_coverage(self):
        run = self.data["latest_run"]
        run_id = run["id"] if isinstance(run, dict) else run
        line = self.dateline()
        self.assertIn("coverage.html", line)
        self.assertRegex(strip_tags(line), r"Run\s*%d\b" % run_id)

    def test_the_record_total_keeps_its_desk_attribution(self):
        """
        A corpus total beside a desk count invites "N records across four
        desks", which is false while one desk collects. Production's hero
        ledger attributed the figure; the dateline that replaces it must too.
        """
        desks = self.view.desk_directory()
        if desks.collecting_count != 1:
            self.skipTest("more than one desk collects; the label is generic")
        self.assertIn("Records held, %s" % desks.collecting[0].name,
                      strip_tags(self.dateline()))

    def test_no_dateline_figure_is_written_into_a_template(self):
        """
        Every number in the band is derived. A literal would keep printing
        after the corpus moved, which is the failure `DECISION_LOG`
        2026-08-28 records.
        """
        names = ["base.html", "home.html"]
        if RECORD_PARTIAL.is_file():
            names.append("_records.html")
        for name in names:
            source = (TEMPLATES / name).read_text(encoding="utf-8")
            # Jinja comments carry measurements and dates that explain the
            # markup; they render nothing. The guard is about what a reader
            # receives, so it reads the template with its commentary removed.
            markup = re.sub(r"\{#.*?#\}", " ", source, flags=re.S)
            with self.subTest(template=name):
                self.assertNotRegex(markup, r"\b\d{1,3}(,\d{3})+\b",
                                    "a comma-grouped figure is written in")
                self.assertNotRegex(
                    markup,
                    r"\b\d[\d,]{2,}\s+(records|articles|sources|desks)\b",
                    "a corpus figure is written in")

    def test_the_coverage_limitation_stays_findable(self):
        """
        Rendered against a corpus where analysis genuinely trails collection.
        The tracked snapshot is currently caught up, and skipping on that
        would leave the caveat — the page's own statement of what it does not
        yet know — with no contract at all.
        """
        tmp = Path(tempfile.mkdtemp(prefix="c1-behind-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        db = tmp / "behind.db"
        shutil.copy2(TRACKED_DB, db)
        # `records_last_collected` is MAX(scraped_at) and
        # `analysis_last_produced` is MAX(analyzed_at). Collecting one record
        # after the last analysis ran is exactly the state the caveat exists
        # for, and it is the smallest change that produces it.
        con = sqlite3.connect(str(db))
        newest = _newest_analyzed_ids(db, 1)[0]
        con.execute("UPDATE articles SET scraped_at = '2026-09-30 06:00:00' "
                    " WHERE id = ?", (newest,))
        con.commit()
        con.close()
        out = tmp / "behind-build"
        gp.build(out, gp.PUBLIC_TITLE, db, snapshot=gp.snapshot_from_corpus(db))
        home = (out / "index.html").read_text(encoding="utf-8")

        f = PublicView(db).freshness()
        self.assertTrue(f.analysis_is_behind_collection,
                        "the fixture did not put analysis behind collection")
        self.assertIn('id="freshness-note"', home)
        self.assertIn("#freshness-note", home)
        note = home.split('id="freshness-note"', 1)[1].split("</p>", 1)[0]
        self.assertIn(f.analysis_last_produced, note)
        self.assertIn("coverage.html", note)
        self.assertIn("methodology.html#freshness", note)

    def test_the_dateline_claims_no_healthy_empty_result(self):
        text = strip_tags(self.home).lower()
        for forbidden in ("all sources reporting", "all clear",
                          "collection is current", "fully collected",
                          "all desks collecting"):
            with self.subTest(phrase=forbidden):
                self.assertNotIn(forbidden, text)


class TestTheClaimIsStatedOnceAndThenTheRecord(HomeCase):

    CLAIM = ("A record of what defense institutions publish about themselves,")

    def test_the_claim_band_carries_the_statement_and_two_ways_in(self):
        self.assertIn('class="claim-band"', self.home)
        band = self.home.split('class="claim-band"', 1)[1].split("</section>", 1)[0]
        self.assertIn(self.CLAIM, strip_tags(band))
        self.assertIn("Explore the record", band)
        self.assertIn("Methodology", band)
        self.assertIn('href="archive.html"', band)
        self.assertIn('href="methodology.html"', band)

    def test_the_claim_is_stated_exactly_once(self):
        self.assertEqual(strip_tags(self.home).count(self.CLAIM), 1)

    def test_the_coverage_caveat_is_stated_once(self):
        """
        Production says "Coverage is selective" twice — once in the hero apron
        and once in the footer. The footer is governed and stays; the apron's
        copy is the duplicate C1 removes.
        """
        self.assertEqual(strip_tags(self.home).count("Coverage is selective"), 1)

    def test_the_lead_record_follows_the_claim_band_directly(self):
        for marker in ('class="claim-band"', 'class="lead-record"'):
            self.assertIn(marker, self.home)
        order = [self.home.index(marker) for marker in (
            'class="claim-band"', 'class="lead-record"')]
        self.assertEqual(order, sorted(order))
        between = self.home[order[0]:order[1]]
        self.assertNotIn("<h2", between.split("</section>", 1)[-1],
                         "another heading was inserted before the record")

    def test_the_home_page_sections_run_in_the_approved_order(self):
        """
        The governed order, asserted end to end: the claim, the lead record,
        the rest of the register, the desks that produce it, the reading of it,
        the record-versus-analysis explanation, and what failed to collect.

        C1 moves the LEAD record into the opening and changes nothing else
        about the sequence. Desks still precedes Latest analysis.
        """
        markers = ('class="claim-band"', 'class="lead-record"',
                   "Latest records", '<h2 id="desks">', "Latest analysis",
                   "Record and analysis are not the same thing",
                   "What did not collect")
        for marker in markers:
            self.assertIn(marker, self.home)
        order = [self.home.index(marker) for marker in markers]
        self.assertEqual(order, sorted(order),
                         "the home page sections are out of order")


class TestTheAircraftIsGoneFromTheHomePage(HomeCase):
    """
    Contrast method v2 measured 11 failing text cells on the home page, every
    one of them where live type crosses the photograph — `a.btn--quiet` fails
    at all four viewports, worst 2.92:1. The image is removed from the render;
    the asset, its derivative and its licence record are untouched.
    """

    def test_the_home_page_renders_no_veil_and_no_aircraft_credit(self):
        for marker in ('class="pl-veil"', "src-bracket", "src-inline",
                       "data-editorial-id", "atmosphere/", "emperornie",
                       "CC BY-SA", "Wikimedia Commons",
                       "Duotone adaptation", "chengdu-j20"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, self.home)

    def test_no_stylesheet_rule_paints_a_photograph_behind_text(self):
        """
        The stylesheet painted the aircraft, so removing the markup is not
        enough — the rule that put an image behind live text has to go too.
        Matched on the declaration, not the block: every `background-image` in
        this stylesheet other than a gradient is a raster file.
        """
        css = CSS.read_text(encoding="utf-8")
        painted = [d.strip() for d in
                   re.findall(r"background-image:\s*([^;}]+)", css)
                   if "url(" in d]
        self.assertEqual(painted, [], "an image is still painted behind text")

    def test_the_asset_and_its_licence_record_are_left_in_place(self):
        """
        "Do not render it" is not "delete it". The manifest, the source image
        and the derivative stay exactly as they are, and the build still
        publishes the provenance record.
        """
        manifest = (REPO_ROOT / "site" / "assets" / "editorial"
                    / "manifest.json")
        self.assertTrue(manifest.is_file())
        self.assertIn("chengdu-j20", manifest.read_text(encoding="utf-8"))
        self.assertIsNotNone(gp.home_atmosphere(REPO_ROOT),
                             "the atmospheric entry was removed, not unused")
        published = self.out / "atmosphere.json"
        self.assertTrue(published.is_file())
        self.assertIn("emperornie", published.read_text(encoding="utf-8"))


class TestRecordAndAnalysisStayDistinguished(HomeCase):

    def test_the_lead_record_is_labelled_as_a_stored_record(self):
        self.assertIn('class="lead-record"', self.home)
        lead = self.home.split('class="lead-record"', 1)[1]
        lead = lead.split("</section>", 1)[0]
        self.assertIn('class="evidence evidence--record">Source record', lead)

    def test_the_latest_analysis_renders_the_actual_edition(self):
        editions = gp.load_editions(REPO_ROOT)
        if not editions:
            self.skipTest("no published edition to lead with")
        lead = editions[0]
        section = self.home.split("Latest analysis", 1)[1]
        section = section.split('class="section-head', 1)[0]
        self.assertIn(lead["title"] or lead["slug"], section)
        self.assertIn(lead["url"], section)
        self.assertIn("No. %s" % lead["issue"], section)

    def test_the_pla_watch_cover_still_renders_with_its_credit(self):
        editions = gp.load_editions(REPO_ROOT)
        if not editions or not editions[0].get("cover"):
            self.skipTest("the leading edition has no cover")
        cover = editions[0]["cover"]
        self.assertIn(cover["route"], self.home)
        self.assertIn(cover["alt"], self.home)
        self.assertIn(cover["credit_note"], self.home)
        img = re.search(r'<img[^>]+%s[^>]*>' % re.escape(cover["route"]),
                        self.home)
        self.assertIsNotNone(img)
        self.assertIn('width="1200"', img.group(0))
        self.assertIn('height="630"', img.group(0))

    def test_the_analysis_section_is_still_labelled_interpretation(self):
        self.assertIn("Record and analysis are not the same thing", self.home)
        self.assertIn("labeled as interpretation", strip_tags(self.home))


# ── The pairing ─────────────────────────────────────────────────────────────

class PairedRecordCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="c1-paired-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def records(self, home: str) -> list:
        """
        Every displayed record, in document order, as
        (english, original, lang, href). Parsed from the page rather than from
        the context, so the assertion is about what a reader receives.
        """
        found = []
        for block in re.findall(
                r'<h[23][^>]*>\s*<a href="(record/\d+\.html)">(.*?)</a>\s*</h[23]>'
                r'(.*?)(?=<h[23]|</section>|</li>|</ul>)', home, re.S):
            href, english, tail = block
            original = re.search(
                r'<p class="original"([^>]*)>(.*?)</p>', tail, re.S)
            lang = None
            text = None
            if original:
                attrs, text = original.group(1), original.group(2).strip()
                match = re.search(r'lang="([^"]*)"', attrs)
                lang = match.group(1) if match else None
            found.append((html_mod.unescape(english.strip()),
                          html_mod.unescape(text) if text is not None else None,
                          lang, href))
        return found


class TestTheEnglishTitleLeadsAndTheOriginalFollows(PairedRecordCase):

    def test_all_six_records_show_their_original_title(self):
        """
        The omission C1 exists to fix: production renders the original for the
        two lead cards and leaves the register's four without it, so the page
        shows two of six originals the record actually holds.
        """
        home, selected, _ = build_fixture(
            self.tmp, homogeneous_rows(), name="all-six")
        shown = self.records(home)
        self.assertEqual(len(shown), HOME_RECORDS)
        for record, (english, original, _lang, _href) in zip(selected, shown):
            with self.subTest(record=record["id"]):
                self.assertEqual(english, record["title_english"])
                self.assertEqual(original, record["title_original"])

    def test_the_english_title_is_the_primary_linked_heading(self):
        home, selected, _ = build_fixture(
            self.tmp, homogeneous_rows(), name="primary")
        for record, (english, original, _lang, href) in zip(
                selected, self.records(home)):
            with self.subTest(record=record["id"]):
                self.assertEqual(href, "record/%d.html" % record["id"])
                self.assertEqual(english, record["title_english"])
                # The original is a sibling paragraph, never the link text.
                self.assertNotIn(record["title_original"], english)
                self.assertIsNotNone(original)

    def test_the_original_sits_immediately_beneath_its_own_english_title(self):
        rows = homogeneous_rows()
        home, selected, _ = build_fixture(self.tmp, rows, name="adjacency")
        for record in selected:
            english = html_mod.escape(record["title_english"])
            original = record["title_original"]
            with self.subTest(record=record["id"]):
                between = home.split(english, 1)[1].split(original, 1)[0]
                self.assertNotRegex(
                    between, r"<h[1-6]",
                    "no original follows this English title before the next "
                    "record's heading — the pair is not rendered")

    def test_original_text_is_escaped(self):
        rows = homogeneous_rows()
        rows[0]["title_original"] = '<script>alert("x")</script>标题 & 引号'
        rows[0]["title_english"] = 'An <b>English</b> title & a "quote"'
        home, _selected, _ = build_fixture(self.tmp, rows, name="escaping")
        self.assertNotIn("<script>alert", home)
        self.assertIn("&lt;script&gt;", home)
        self.assertIn("&amp;", home)
        self.assertNotIn("<b>English</b>", home)

    def test_a_very_long_english_title_is_not_truncated(self):
        long_title = ("A Multi-Dimensional Analysis of the Driving Forces "
                      "Behind the Evolution of Military Organizational Forms "
                      "and the Institutional Consequences Thereof, Stated at "
                      "Considerably Greater Length Than Any Record Currently "
                      "Held by the Corpus")
        rows = homogeneous_rows()
        rows[0]["title_english"] = long_title
        rows[3]["title_english"] = long_title
        home, _selected, _ = build_fixture(self.tmp, rows, name="long-en")
        shown = self.records(home)
        self.assertEqual(shown[0][0], long_title)
        self.assertEqual(shown[3][0], long_title)
        self.assertNotIn("…", home.split("</main>", 1)[0])

    def test_a_long_original_title_is_not_truncated(self):
        long_original = "武警西藏总队某支队在班排设置连心码服务卡以解决官兵急难愁盼问题" * 3
        rows = homogeneous_rows()
        rows[0]["title_original"] = long_original
        rows[4]["title_original"] = long_original
        home, _selected, _ = build_fixture(self.tmp, rows, name="long-zh")
        shown = self.records(home)
        self.assertEqual(shown[0][1], long_original)
        self.assertEqual(shown[4][1], long_original)


class TestARecordWithNoOriginalTitle(unittest.TestCase):
    """
    Two separate contracts, because the absence is handled in two places.

    The **builder** already refuses it. `record_citation()` requires the
    original title and substitutes nothing, so a stored record without one
    stops the build with a named refusal rather than publishing a record page
    that quietly cites its machine translation as the source text. That is the
    governed behaviour and this file does not relax it.

    The **home page** must still degrade cleanly, because the guard is what
    keeps an absent original from becoming an empty line or an orphaned rule.
    That half is rendered directly from the partial with a controlled record,
    which is the only way to exercise a state the builder refuses to reach.
    """

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="c1-missing-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @staticmethod
    def render_records(records, shared=None):
        if not RECORD_PARTIAL.is_file():
            raise unittest.SkipTest(
                "_records.html is not present: this tree does not carry the "
                "paired-record partial")
        """
        The home page's record partial, rendered on its own.

        Lifted as a real template rather than by string surgery: the partial is
        the unit that decides whether an original is shown, so testing it
        directly tests the decision rather than a copy of it.
        """
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                          autoescape=True, trim_blocks=True,
                          lstrip_blocks=True)
        return env.from_string(
            '{% from "_records.html" import lead_record, record_register %}'
            "{{ lead_record(records[0]) }}"
            "{{ record_register(records[1:], shared) }}"
        ).render(records=list(records), shared=shared)

    def record(self, **overrides):
        base = {"id": 1, "title_english": "An English title",
                "title_original": "原文标题", "language_tag": ZH,
                "institution": "CMC Political Work Department",
                "source_name": "PLA Daily (解放军报)",
                "source_slug": "pla_daily", "published_date": "2026-09-20"}
        base.update(overrides)
        return base

    def test_the_builder_refuses_a_record_with_no_original_title(self):
        db = self.tmp / "no-original.db"
        shutil.copy2(TRACKED_DB, db)
        target = _newest_analyzed_ids(db, 1)[0]
        con = sqlite3.connect(str(db))
        con.execute("UPDATE articles SET title_original = NULL WHERE id = ?",
                    (target,))
        con.commit()
        con.close()
        with self.assertRaises(gp.CitationDataMissing) as caught:
            gp.build(self.tmp / "no-original-build", gp.PUBLIC_TITLE, db,
                     snapshot=gp.snapshot_from_corpus(db))
        self.assertIn("original title is absent", str(caught.exception))

    def test_an_absent_original_renders_no_line_at_all(self):
        rendered = self.render_records([
            self.record(id=10),
            self.record(id=11, title_original=None),
            self.record(id=12, title_original="   "),
            self.record(id=13),
        ])
        originals = re.findall(r'<p class="original"[^>]*>(.*?)</p>',
                               rendered, re.S)
        self.assertEqual(len(originals), 2,
                         "an original was rendered for a record without one")
        for text in originals:
            with self.subTest(text=text):
                self.assertEqual(text.strip(), "原文标题")
        self.assertNotRegex(rendered, r'<p class="original"[^>]*>\s*</p>')
        self.assertNotRegex(rendered, r'<p class="original"[^>]*>\s*[·—-]\s*</p>')

    def test_no_record_borrows_a_neighbours_original(self):
        rendered = self.render_records([
            self.record(id=20, title_original="第一条原文"),
            self.record(id=21, title_original=None),
            self.record(id=22, title_original="第三条原文"),
        ])
        row = re.search(r'href="record/21\.html".*?(?=href="record/22)',
                        rendered, re.S)
        self.assertIsNotNone(row)
        self.assertNotIn("第一条原文", row.group(0))
        self.assertNotIn("第三条原文", row.group(0))

    def test_an_absent_english_title_falls_back_to_the_original(self):
        """
        The existing fallback convention, kept: a record with no machine
        translation shows its original as the heading rather than an empty
        link, and does not then repeat it beneath itself.
        """
        rendered = self.render_records([
            self.record(id=30, title_english=None,
                        title_original="只有原文标题"),
            self.record(id=31),
        ])
        self.assertIn("只有原文标题", rendered)
        self.assertEqual(rendered.count("只有原文标题"), 1)


class TestTheLanguageMetadataIsTheRepositorysOwn(PairedRecordCase):

    def test_each_original_carries_the_language_its_source_declares(self):
        """
        Two languages, both declared by `desks/china/manifest.json`:
        `pla_daily` is `zh-Hans`, `global_times_mil` is `en`. The rendered
        `lang` follows the stored source, never a page-wide assumption.
        """
        rows = homogeneous_rows()
        for index in (1, 4):
            rows[index]["source_slug"] = "global_times_mil"
            rows[index]["title_original"] = "An English-language original %d" % index
        home, selected, _ = build_fixture(self.tmp, rows, name="two-langs")
        shown = self.records(home)
        tags = {r["language_tag"] for r in selected}
        self.assertEqual(tags, {ZH, EN},
                         "the fixture did not produce two languages")
        for record, (_en, _orig, lang, _href) in zip(selected, shown):
            with self.subTest(record=record["id"]):
                self.assertEqual(lang, record["language_tag"])

    def test_the_language_tag_is_not_hardcoded_in_the_template(self):
        require_partial(self)
        sources = {name: (TEMPLATES / name).read_text(encoding="utf-8")
                   for name in ("home.html", "_records.html")}
        for name, source in sources.items():
            with self.subTest(template=name):
                self.assertNotIn('lang="zh-Hans"', source)
                self.assertNotIn("'zh'", source)
                self.assertNotIn('"zh"', source)
        self.assertIn("language_tag", sources["_records.html"])

    def test_a_source_with_no_language_code_gets_no_invented_one(self):
        """
        `sources.language_tag` is nullable. An absent code is an absent code:
        the paragraph renders without a `lang` attribute rather than being
        told it is Chinese.
        """
        db = self.tmp / "nolang.db"
        shutil.copy2(TRACKED_DB, db)
        ids = _newest_analyzed_ids(db, HOME_RECORDS)
        con = sqlite3.connect(str(db))
        for position, record_id in enumerate(ids):
            con.execute(
                "UPDATE articles SET title_english = ?, title_original = ?, "
                "       published_date = '2026-09-20' WHERE id = ?",
                ("Record %d in English" % position,
                 "第%d号原文标题" % position, record_id))
        # `sources.language` is NOT NULL and is the deprecated compatibility
        # mirror (migration m0005). Only the authoritative BCP 47 field is
        # cleared, which is the state a newly configured source can be in.
        con.execute("UPDATE sources SET language_tag = NULL")
        con.commit()
        con.close()
        out = self.tmp / "nolang-build"
        gp.build(out, gp.PUBLIC_TITLE, db, snapshot=gp.snapshot_from_corpus(db))
        home = (out / "index.html").read_text(encoding="utf-8")
        originals = re.findall(r'<p class="original"([^>]*)>', home)
        self.assertTrue(originals)
        for attrs in originals:
            with self.subTest(attrs=attrs):
                self.assertNotIn("lang=", attrs)

    def test_the_documented_original_language_treatment_is_intact(self):
        """
        `DESIGN_SYSTEM.md` §4: the original renders under the English at
        secondary colour, never italicised, never letter-spaced, and never
        below 0.8rem. The register's rows are new surface for original-language
        text, so they are held to the same rule as the lead plate.
        """
        css = CSS.read_text(encoding="utf-8")
        blocks = re.findall(r"([^}\n][^{}]*\.original[^{}]*)\{([^}]*)\}", css)
        self.assertTrue(blocks, "no rule styles the original-language line")
        secondary = ("--deep", "--graphite", "--text-muted-tinted")
        saw_colour = False
        saw_size = False
        for selector, body in blocks:
            with self.subTest(selector=selector.strip()):
                self.assertNotIn("font-style: italic", body)
                self.assertNotIn("letter-spacing", body)
                self.assertNotIn("text-transform", body)
                self.assertNotIn("var(--mono)", body)
                for size in re.findall(r"font-size:\s*([0-9.]+)rem", body):
                    saw_size = True
                    self.assertGreaterEqual(float(size), 0.8)
                # `color`, not `border-top-color`: the hairline above the
                # lead's original line is a rule, not the text tone.
                for colour in re.findall(
                        r"(?:^|[;{\s])color:\s*var\((--[a-z-]+)\)", body):
                    saw_colour = True
                    self.assertIn(colour, secondary)
        self.assertTrue(saw_colour and saw_size)

    def test_the_register_row_original_is_not_set_in_the_metadata_font(self):
        rows = homogeneous_rows()
        home, _selected, _ = build_fixture(self.tmp, rows, name="not-mono")
        self.assertIn('class="record-register"', home)
        register = home.split('class="record-register"', 1)[1]
        register = register.split("</ul>", 1)[0]
        self.assertIn('class="original"', register)
        self.assertNotRegex(register, r'class="register-meta"[^>]*>\s*第')


# ── The provenance ──────────────────────────────────────────────────────────

class TestProvenanceSurvivesAHeterogeneousRegister(PairedRecordCase):
    """
    The prototype's group summary is safe only while its premise holds. These
    cases break the premise deliberately.
    """

    def summary(self, home: str):
        match = re.search(r'<p class="register-note">(.*?)</p>', home, re.S)
        return strip_tags(match.group(1)) if match else None

    def register_rows(self, home: str) -> list:
        assert 'class="record-register"' in home, "no register was rendered"
        register = home.split('class="record-register"', 1)[1]
        register = register.split("</ul>", 1)[0]
        return re.findall(r"<li[^>]*>(.*?)</li>", register, re.S)

    def test_the_lead_record_always_states_its_own_provenance(self):
        for name, rows in (("lead-homog", homogeneous_rows()),
                           ("lead-mixed", self.mixed_source_rows()),
                           ("lead-dates", self.mixed_date_rows())):
            home, selected, _ = build_fixture(self.tmp, rows, name=name)
            with self.subTest(fixture=name):
                self.assertIn('class="lead-record"', home)
                lead = home.split('class="lead-record"', 1)[1]
                lead = lead.split("</section>", 1)[0]
                record = selected[0]
                self.assertIn(record["institution"] or record["source_name"],
                              strip_tags(lead))
                self.assertIn('datetime="%s"' % record["published_date"], lead)

    @staticmethod
    def mixed_source_rows():
        rows = homogeneous_rows()
        # `mod_china` is a different institution (cn_mnd) from `pla_daily`
        # (cn_cmc_political_work), and both are declared China-desk sources.
        rows[2]["source_slug"] = "mod_china"
        rows[3]["source_slug"] = "global_times_mil"
        rows[3]["title_original"] = "An English-language original"
        return rows

    @staticmethod
    def mixed_date_rows():
        rows = homogeneous_rows()
        for index, row in enumerate(rows):
            row["published_date"] = "2026-09-%02d" % (20 - index)
        return rows

    def test_a_homogeneous_register_may_carry_a_truthful_group_summary(self):
        home, selected, _ = build_fixture(
            self.tmp, homogeneous_rows(), name="prov-homog")
        summary = self.summary(home)
        self.assertIsNotNone(summary,
                             "a homogeneous register states its shared "
                             "provenance once")
        rest = selected[1:HOME_RECORDS]
        institution = rest[0]["institution"] or rest[0]["source_name"]
        self.assertIn(institution, summary)
        self.assertIn(rest[0]["published_date"], summary)
        self.assertRegex(summary, r"\b%d\b" % len(rest))
        # A publication date is not a collection date.
        self.assertNotRegex(summary.lower(), r"collected\s+2026")

    def test_a_mixed_source_register_exposes_each_row_s_provenance(self):
        home, selected, _ = build_fixture(
            self.tmp, self.mixed_source_rows(), name="prov-mixed-src")
        institutions = {(r["institution"] or r["source_name"])
                        for r in selected[1:HOME_RECORDS]}
        self.assertGreater(len(institutions), 1,
                           "the fixture did not produce mixed sources")
        self.assertIsNone(
            self.summary(home),
            "a group summary claimed one institution for several")
        rows = self.register_rows(home)
        self.assertEqual(len(rows), HOME_RECORDS - 1)
        for record, row in zip(selected[1:HOME_RECORDS], rows):
            with self.subTest(record=record["id"]):
                self.assertIn(record["institution"] or record["source_name"],
                              strip_tags(row))

    def test_a_mixed_date_register_exposes_each_row_s_date(self):
        home, selected, _ = build_fixture(
            self.tmp, self.mixed_date_rows(), name="prov-mixed-date")
        dates = {r["published_date"] for r in selected[1:HOME_RECORDS]}
        self.assertGreater(len(dates), 1,
                           "the fixture did not produce mixed dates")
        self.assertIsNone(self.summary(home),
                          "a group summary claimed one date for several")
        rows = self.register_rows(home)
        for record, row in zip(selected[1:HOME_RECORDS], rows):
            with self.subTest(record=record["id"]):
                self.assertIn('datetime="%s"' % record["published_date"], row)

    def test_no_record_is_shown_under_another_record_s_date(self):
        home, selected, _ = build_fixture(
            self.tmp, self.mixed_date_rows(), name="prov-no-crosstalk")
        by_date = {r["id"]: r["published_date"] for r in selected}
        for record, row in zip(selected[1:HOME_RECORDS],
                               self.register_rows(home)):
            others = set(by_date.values()) - {record["published_date"]}
            for other in others:
                with self.subTest(record=record["id"], other=other):
                    self.assertNotIn(other, row)

    def test_a_shared_institution_with_two_sources_is_not_summarised(self):
        """
        `pla_daily` and `china_mil_online` share `cn_cmc_political_work`, so
        the institution matches while the source does not. "All five from X"
        would then be true of the institution and false of the source, and
        source attribution may never be inferred across records.
        """
        rows = homogeneous_rows()
        rows[3]["source_slug"] = "china_mil_online"
        rows[3]["title_original"] = "An English-language original"
        home, selected, _ = build_fixture(
            self.tmp, rows, name="prov-same-inst")
        institutions = {(r["institution"] or r["source_name"])
                        for r in selected[1:HOME_RECORDS]}
        self.assertEqual(len(institutions), 1,
                         "the fixture did not hold the institution constant")
        slugs = {r["source_slug"] for r in selected[1:HOME_RECORDS]}
        self.assertGreater(len(slugs), 1)
        self.assertIsNone(self.summary(home))


class TestTheRegisterDegradesWithTheCorpus(PairedRecordCase):

    def test_fewer_than_six_suitable_records_render_what_exists(self):
        """
        The home page shows the six newest ANALYZED records. A corpus holding
        three renders three — a lead and two register rows — and invents
        nothing to fill the shape the current snapshot happens to have.
        """
        db = self.tmp / "short.db"
        shutil.copy2(TRACKED_DB, db)
        keep = _newest_analyzed_ids(db, 3)
        con = sqlite3.connect(str(db))
        # `is_significant` is NOT NULL, so it returns to its unassessed
        # default rather than being cleared; the state case reads `analyzed_at`.
        con.execute(
            "UPDATE articles SET analyzed_at = NULL, is_significant = 0, "
            "       model_id = NULL, prompt_version = NULL, "
            "       title_english = NULL, summary_english = NULL "
            " WHERE analyzed_at IS NOT NULL AND id NOT IN (%s)"
            % ",".join(str(i) for i in keep))
        for position, record_id in enumerate(keep):
            con.execute(
                "UPDATE articles SET title_english = ?, title_original = ?, "
                "       published_date = '2026-09-20' WHERE id = ?",
                ("Short corpus record %d" % position,
                 "短语料第%d条" % position, record_id))
        con.commit()
        con.close()
        out = self.tmp / "short-build"
        gp.build(out, gp.PUBLIC_TITLE, db, snapshot=gp.snapshot_from_corpus(db))
        home = (out / "index.html").read_text(encoding="utf-8")

        self.assertEqual(len(gp.load_corpus(db)["recent"]), len(keep))
        self.assertIn('class="lead-record"', home)
        self.assertNotRegex(home, r'<li class="register-item">\s*</li>')
        for record_id in keep:
            with self.subTest(record=record_id):
                self.assertIn("record/%d.html" % record_id, home)
        rows = re.findall(r'<li class="register-item">', home)
        self.assertEqual(len(rows), len(keep) - 1)

    def test_every_displayed_record_keeps_a_route_to_its_own_page(self):
        home, selected, out = build_fixture(
            self.tmp, homogeneous_rows(), name="routes")
        for record in selected:
            route = "record/%d.html" % record["id"]
            with self.subTest(record=record["id"]):
                self.assertIn('href="%s"' % route, home)
                self.assertTrue((out / route).is_file())

    def test_no_current_edition_leaves_the_page_coherent(self):
        """
        `lead_edition` is `None` when no sidecar exists. The analysis section
        is then absent rather than an empty frame, and nothing above or below
        it claims an edition.
        """
        source = (TEMPLATES / "home.html").read_text(encoding="utf-8")
        self.assertIn("{% if lead_edition %}", source)
        analysis = source.split("{% if lead_edition %}", 1)[1]
        self.assertIn("Latest analysis", analysis.split("{% endif %}")[0])


if __name__ == "__main__":                                  # pragma: no cover
    unittest.main()


# ── The visual contract, in a real browser ──────────────────────────────────
#
# Thresholds rather than snapshots. A screenshot proves the page looked right
# once; these say what has to remain true after the corpus, the copy and the
# viewport change. Offline: a loopback server on an ephemeral port.

class BrowserCase(unittest.TestCase):

    VIEWPORTS = (375, 768, 1280, 1920)

    @classmethod
    def corpus_for_build(cls, tmp: Path) -> Path:
        """
        The database this class renders. The default is the tracked snapshot,
        which the builder opens without writing to it; a subclass that needs a
        corpus of a particular SHAPE copies it and returns its own file, so
        the tracked database is never the thing being edited.
        """
        return TRACKED_DB

    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:                                   # pragma: no cover
            raise unittest.SkipTest("playwright not installed")
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        import functools
        import http.server
        import socketserver
        import threading

        cls.tmp = Path(tempfile.mkdtemp(prefix="c1-browser-"))
        cls.out = cls.tmp / "build"
        db = cls.corpus_for_build(cls.tmp)
        gp.build(cls.out, gp.PUBLIC_TITLE, db,
                 snapshot=gp.snapshot_from_corpus(db))

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass

        handler = functools.partial(Quiet, directory=str(cls.out))
        socketserver.TCPServer.allow_reuse_address = True
        cls.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        # `pip install playwright` does not fetch a browser, and the
        # pull-request workflow installs none. Skip cleanly there; the daily
        # workflow runs `playwright install chromium` before this suite.
        cls._pw = sync_playwright().start()
        try:
            cls.browser = cls._pw.chromium.launch()
        except Exception as exc:                              # pragma: no cover
            cls._pw.stop()
            raise unittest.SkipTest(
                "chromium not available (%s); run `playwright install chromium`"
                % type(exc).__name__)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "browser"):
            cls.browser.close()
            cls._pw.stop()
            cls.httpd.shutdown()
            cls.httpd.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def page_at(self, width, height=900, path="index.html", **kwargs):
        context = self.browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=1, **kwargs)
        page = context.new_page()
        page.goto("http://127.0.0.1:%d/%s" % (self.port, path),
                  wait_until="load")
        page.evaluate("window.scrollTo(0, 0)")
        self.assertEqual(page.evaluate("window.scrollY"), 0)
        return context, page


class TestTheRecordReachesTheFirstViewport(BrowserCase):

    #: Durable, not a snapshot of one capture. Production measures
    #: `firstRecordY` 1,023.9 at 1280 and 1,505.9 at 375, with zero readable
    #: record titles in the first 900px at any viewport.
    LEAD_START_375 = 800
    FIRST_VIEWPORT = 900

    def lead_box(self, page):
        return page.evaluate(
            "() => { const h = document.querySelector("
            "'.lead-record .record-headline'); if (!h) return null;"
            " const r = h.getBoundingClientRect();"
            " return {top: r.top + window.scrollY, bottom: r.bottom +"
            " window.scrollY, height: r.height,"
            " lineHeight: parseFloat(getComputedStyle(h).lineHeight)}; }")

    def test_a_complete_record_title_is_visible_in_the_first_viewport(self):
        context, page = self.page_at(1280, 900)
        try:
            box = self.lead_box(page)
            self.assertIsNotNone(box, "no lead record headline was rendered")
            self.assertLess(
                box["bottom"], self.FIRST_VIEWPORT,
                "no complete English record title fits in 1280x900")
        finally:
            context.close()

    def test_the_lead_headline_begins_early_on_a_phone(self):
        context, page = self.page_at(375, 900)
        try:
            box = self.lead_box(page)
            self.assertIsNotNone(box)
            self.assertLess(box["top"], self.LEAD_START_375)
            visible = min(box["bottom"], self.FIRST_VIEWPORT) - box["top"]
            self.assertGreaterEqual(
                visible, 2 * box["lineHeight"] - 1,
                "fewer than two rendered lines of the headline are visible")
        finally:
            context.close()


class TestTheHomePageHoldsItsShape(BrowserCase):

    def test_no_horizontal_overflow_from_320_to_2560(self):
        for width in (320, 375, 768, 1280, 1920, 2560):
            context, page = self.page_at(width, 900)
            try:
                overflow = page.evaluate(
                    "() => document.documentElement.scrollWidth -"
                    " document.documentElement.clientWidth")
                with self.subTest(width=width):
                    self.assertLessEqual(overflow, 0)
            finally:
                context.close()

    def test_the_page_loads_without_console_or_network_errors(self):
        context, page = self.page_at(1280, 900)
        messages, failures, bad_status = [], [], []
        page.on("console", lambda m: messages.append(m.text)
                if m.type in ("error", "warning") else None)
        page.on("requestfailed", lambda r: failures.append(r.url))
        page.on("response", lambda r: bad_status.append((r.url, r.status))
                if r.status >= 400 else None)
        try:
            page.reload(wait_until="load")
            self.assertEqual(messages, [])
            self.assertEqual(failures, [])
            self.assertEqual(bad_status, [])
        finally:
            context.close()

    def test_no_live_text_intersects_an_image_backed_region(self):
        """
        The defect the aircraft caused, stated as a property: no element that
        paints a raster background may overlap an element that carries text.
        """
        for width in self.VIEWPORTS:
            context, page = self.page_at(width, 900)
            try:
                overlaps = page.evaluate("""() => {
                  const painted = [...document.querySelectorAll('*')].filter(
                    el => {
                      const bg = getComputedStyle(el).backgroundImage;
                      return bg && bg.includes('url(');
                    });
                  const texts = [...document.querySelectorAll(
                    'p,h1,h2,h3,h4,a,span,dt,dd,time,li,summary')]
                    .filter(el => el.textContent.trim().length > 1);
                  const hit = [];
                  for (const p of painted) {
                    const a = p.getBoundingClientRect();
                    if (!a.width || !a.height) continue;
                    for (const t of texts) {
                      if (p.contains(t) || t.contains(p)) continue;
                      const b = t.getBoundingClientRect();
                      if (!b.width || !b.height) continue;
                      if (a.left < b.right && b.left < a.right &&
                          a.top < b.bottom && b.top < a.bottom) {
                        hit.push(t.textContent.trim().slice(0, 40));
                      }
                    }
                  }
                  return hit;
                }""")
                with self.subTest(width=width):
                    self.assertEqual(overlaps, [])
            finally:
                context.close()

    def test_the_identity_mark_renders_at_its_documented_size(self):
        for width, expected in ((375, 48), (1280, 56)):
            context, page = self.page_at(width, 900)
            try:
                box = page.evaluate(
                    "() => { const m = document.querySelector('.brand-mark');"
                    " const r = m.getBoundingClientRect();"
                    " return [r.width, r.height]; }")
                with self.subTest(width=width):
                    self.assertEqual([round(v) for v in box],
                                     [expected, expected])
            finally:
                context.close()

    def test_the_masthead_does_not_stick_to_the_viewport(self):
        context, page = self.page_at(1280, 900)
        try:
            self.assertEqual(
                page.evaluate("() => getComputedStyle("
                              "document.querySelector('.masthead')).position"),
                "static")
        finally:
            context.close()


class TestTheCompactDisclosureBehaves(BrowserCase):

    def control(self, page):
        return page.evaluate(
            "() => { const s = document.querySelector("
            "'.nav-mobile > summary'); const r = s.getBoundingClientRect();"
            " return {w: r.width, h: r.height,"
            "  open: s.parentElement.open,"
            "  visible: getComputedStyle(s.parentElement).display !== 'none'};"
            "}")

    def test_the_disclosure_is_present_collapsed_and_large_enough(self):
        context, page = self.page_at(375, 900)
        try:
            control = self.control(page)
            self.assertTrue(control["visible"])
            self.assertFalse(control["open"], "the disclosure ships expanded")
            self.assertGreaterEqual(control["w"], 44)
            self.assertGreaterEqual(control["h"], 44)
            # `getBoundingClientRect()` is not the test: a closed <details>
            # SKIPS its subtree rather than removing its layout boxes, so the
            # links still report a rect. Playwright's visibility check is the
            # one that answers "can a reader see this".
            links = page.locator(".nav-mobile a")
            self.assertEqual(links.count(), 7)
            self.assertEqual(
                sum(1 for i in range(links.count())
                    if links.nth(i).is_visible()), 0,
                "the compact links are exposed by default")
        finally:
            context.close()

    def test_the_disclosure_opens_from_the_keyboard_with_a_visible_focus_ring(self):
        context, page = self.page_at(375, 900)
        try:
            # Tabbed to, not focused by script: `:focus-visible` is what draws
            # the ring, and it only applies to a keyboard-initiated focus.
            for _ in range(40):
                page.keyboard.press("Tab")
                if page.evaluate("() => document.activeElement.tagName") \
                        == "SUMMARY":
                    break
            else:                                         # pragma: no cover
                self.fail("the disclosure is not reachable by keyboard")
            outline = page.evaluate(
                "() => { const c = getComputedStyle(document.activeElement);"
                " return [c.outlineStyle, parseFloat(c.outlineWidth) || 0]; }")
            self.assertNotEqual(outline[0], "none")
            self.assertGreaterEqual(outline[1], 2)
            page.keyboard.press("Enter")
            self.assertTrue(self.control(page)["open"])
            links = page.locator(".nav-mobile a")
            self.assertEqual(
                sum(1 for i in range(links.count())
                    if links.nth(i).is_visible()), 7)
        finally:
            context.close()

    def test_changed_navigation_and_button_targets_meet_44px(self):
        """
        The record site's house floor is 40px for mobile nav and buttons
        (`DESIGN_SYSTEM.md` §7). Everything this change touches is held to the
        stricter 44px figure the prototypes met, in both dimensions.
        """
        selectors = (".nav-mobile > summary", ".claim-band .btn",
                     ".freshness-bar--lead a")
        for width in (375, 768, 1280):
            context, page = self.page_at(width, 900)
            try:
                small = page.evaluate("""(sel) => {
                  const bad = [];
                  for (const s of sel) {
                    for (const el of document.querySelectorAll(s)) {
                      const r = el.getBoundingClientRect();
                      if (!r.width && !r.height) continue;
                      if (Math.min(r.width, r.height) < 44) {
                        bad.push(s + ' ' + Math.round(r.width) + 'x' +
                                 Math.round(r.height));
                      }
                    }
                  }
                  return bad;
                }""", list(selectors))
                with self.subTest(width=width):
                    self.assertEqual(small, [])
            finally:
                context.close()


class TestNothingInformationalIsHidden(BrowserCase):

    def visible_text_length(self, page):
        return page.evaluate(
            "() => document.querySelector('main').innerText.trim().length")

    def test_reduced_motion_reveals_the_same_content(self):
        normal_ctx, normal = self.page_at(1280, 900)
        normal_len = self.visible_text_length(normal)
        normal_ctx.close()
        reduced_ctx, reduced = self.page_at(1280, 900,
                                            reduced_motion="reduce")
        try:
            hidden = reduced.evaluate(
                "() => [...document.querySelectorAll('[data-reveal]')]"
                ".filter(el => parseFloat(getComputedStyle(el).opacity) < 1)"
                ".length")
            self.assertEqual(hidden, 0)
            self.assertEqual(self.visible_text_length(reduced), normal_len)
        finally:
            reduced_ctx.close()

    def test_the_page_reads_with_javascript_disabled(self):
        context = self.browser.new_context(
            viewport={"width": 1280, "height": 900}, java_script_enabled=False)
        page = context.new_page()
        try:
            page.goto("http://127.0.0.1:%d/index.html" % self.port,
                      wait_until="load")
            body = page.locator("main").inner_text()
            self.assertGreater(len(body.strip()), 1500)
            for expected in ("Latest records", "Latest analysis",
                             "What did not collect"):
                with self.subTest(expected=expected):
                    self.assertIn(expected, body)
        finally:
            context.close()

    def test_print_hides_nothing_informational(self):
        context, page = self.page_at(1280, 900)
        try:
            page.emulate_media(media="print")
            hidden = page.evaluate(
                "() => [...document.querySelectorAll("
                "'main p, main h2, main h3, main li, main dd')]"
                ".filter(el => el.textContent.trim().length > 1 &&"
                " (getComputedStyle(el).display === 'none' ||"
                "  getComputedStyle(el).visibility === 'hidden' ||"
                "  parseFloat(getComputedStyle(el).opacity) === 0))"
                ".map(el => el.textContent.trim().slice(0, 40))")
            self.assertEqual(hidden, [])
        finally:
            context.close()

    def test_every_keyboard_stop_shows_a_focus_indicator(self):
        """
        Walked with real Tab presses. `:focus-visible` cannot be queried
        through `getComputedStyle`'s pseudo-element argument — asking for it
        that way returns the unfocused style and reports every control as
        bare, which is a test that fails for the wrong reason.
        """
        context, page = self.page_at(1280, 900)
        try:
            bad, seen = [], set()
            for _ in range(120):
                page.keyboard.press("Tab")
                state = page.evaluate("""() => {
                  const el = document.activeElement;
                  if (!el || el === document.body) return null;
                  const c = getComputedStyle(el);
                  const r = el.getBoundingClientRect();
                  return {
                    key: (el.tagName + '|' + (el.getAttribute('href') || '')
                          + '|' + el.textContent.trim().slice(0, 40)),
                    style: c.outlineStyle,
                    width: parseFloat(c.outlineWidth) || 0,
                    onScreen: !!(r.width || r.height),
                  };
                }""")
                if state is None or state["key"] in seen:
                    break
                seen.add(state["key"])
                if state["onScreen"] and (state["style"] == "none"
                                          or state["width"] < 1):
                    bad.append(state["key"])
            self.assertGreater(len(seen), 5, "the tab order was not walked")
            self.assertEqual(bad, [])
        finally:
            context.close()

    def test_the_skip_link_moves_focus_to_the_main_landmark(self):
        context, page = self.page_at(1280, 900)
        try:
            page.keyboard.press("Tab")
            self.assertEqual(
                page.evaluate("() => document.activeElement.className"), "skip")
            page.keyboard.press("Enter")
            self.assertEqual(
                page.evaluate("() => location.hash"), "#main")
        finally:
            context.close()


class TestTheDatelineIsActuallyCompressed(BrowserCase):
    """
    "Compressed" is a measurement, not a description. An earlier revision of
    this candidate compressed the masthead by 21px and grew the dateline by
    47px, so the chrome above the first content got TALLER than production's
    while claiming to be smaller. These are the gates that make the claim
    checkable.
    """

    #: Top of the home page's first main-content child, by viewport.
    CHROME_CEILING = {375: 300, 768: 250, 1280: 220, 1920: 220}
    #: Top of the lead English headline.
    HEADLINE_CEILING = {375: 700, 1280: 560}

    def chrome_top(self, page):
        return page.evaluate(
            "() => { const m = document.querySelector('main');"
            " const f = m.firstElementChild;"
            " return +(f.getBoundingClientRect().top + window.scrollY)"
            "         .toFixed(1); }")

    def test_the_chrome_above_the_first_content_stays_under_its_ceiling(self):
        for width, ceiling in sorted(self.CHROME_CEILING.items()):
            height = 1080 if width == 1920 else 900
            context, page = self.page_at(width, height)
            try:
                top = self.chrome_top(page)
                with self.subTest(width=width):
                    self.assertLessEqual(top, ceiling,
                                         "chrome is %.1fpx at %d" % (top, width))
            finally:
                context.close()

    def test_the_lead_headline_starts_above_its_ceiling(self):
        for width, ceiling in sorted(self.HEADLINE_CEILING.items()):
            context, page = self.page_at(width, 900)
            try:
                top = page.evaluate(
                    "() => { const h = document.querySelector("
                    "'.lead-record .record-headline'); return h ? "
                    "+(h.getBoundingClientRect().top + window.scrollY)"
                    ".toFixed(1) : null; }")
                with self.subTest(width=width):
                    self.assertIsNotNone(
                        top, "no lead record headline is rendered")
                    self.assertLessEqual(top, ceiling)
            finally:
                context.close()

    def test_the_run_link_never_occupies_a_row_alone_on_a_wide_screen(self):
        """
        At desktop widths the run link shares the figure list's own last row.
        A link alone under a mostly empty band is the composition defect this
        replaced. At 375 the list becomes a two-column label/value grid and the
        link takes its own row deliberately — beside a grid row it lands flush
        against a value and reads as part of it.
        """
        for width in (768, 1280, 1920):
            height = 1080 if width == 1920 else 900
            context, page = self.page_at(width, height)
            try:
                shares = page.evaluate("""() => {
                  const link = document.querySelector(
                    '.freshness-bar .detail a').getBoundingClientRect();
                  const cells = [...document.querySelectorAll(
                    '.freshness-bar dl > div')].map(d => d.getBoundingClientRect());
                  return cells.some(c => link.top < c.bottom && c.top < link.bottom);
                }""")
                with self.subTest(width=width):
                    self.assertTrue(shares, "the run link is alone on its row")
            finally:
                context.close()

    def test_no_dateline_box_overlaps_another(self):
        """
        The link is 44px tall inside a band of ~14px rows, so overlap is the
        specific hazard. Checked at every viewport, including the two the
        design does not otherwise measure.
        """
        for width in (320, 375, 768, 1280, 1920, 2560):
            context, page = self.page_at(width, 900)
            try:
                overlaps = page.evaluate("""() => {
                  const link = document.querySelector(
                    '.freshness-bar .detail a');
                  if (!link) return [];
                  const lr = link.getBoundingClientRect();
                  return [...document.querySelectorAll(
                      '.freshness-bar dl dt, .freshness-bar dl dd')]
                    .filter(e => { const r = e.getBoundingClientRect();
                      return lr.left < r.right && r.left < lr.right &&
                             lr.top < r.bottom && r.top < lr.bottom; })
                    .map(e => e.textContent.trim().slice(0, 30));
                }""")
                with self.subTest(width=width):
                    self.assertEqual(overlaps, [])
            finally:
                context.close()

    def test_the_dateline_hides_nothing_and_clips_nothing(self):
        for width in (320, 375, 768, 1280):
            context, page = self.page_at(width, 900)
            try:
                bad = page.evaluate("""() => {
                  const bar = document.querySelector('.freshness-bar');
                  const cs = getComputedStyle(bar);
                  const out = [];
                  if (cs.overflow === 'hidden') out.push('bar overflow hidden');
                  for (const e of bar.querySelectorAll('dt, dd, a')) {
                    const c = getComputedStyle(e);
                    if (c.textOverflow === 'ellipsis') out.push('ellipsis');
                    if (parseFloat(c.marginTop) < 0 ||
                        parseFloat(c.marginBottom) < 0) out.push('negative margin');
                    if (c.position === 'absolute') out.push('absolute');
                    if (e.scrollWidth > e.clientWidth + 1) out.push('clipped: ' +
                      e.textContent.trim().slice(0, 24));
                  }
                  return [...new Set(out)];
                }""")
                with self.subTest(width=width):
                    self.assertEqual(bad, [])
            finally:
                context.close()

    def test_the_dateline_control_holds_44px_in_both_dimensions(self):
        for width in (375, 768, 1280, 1920):
            height = 1080 if width == 1920 else 900
            context, page = self.page_at(width, height)
            try:
                box = page.evaluate(
                    "() => { const r = document.querySelector("
                    "'.freshness-bar .detail a').getBoundingClientRect();"
                    " return [+r.width.toFixed(1), +r.height.toFixed(1)]; }")
                with self.subTest(width=width):
                    self.assertGreaterEqual(min(box), 44, "box is %s" % box)
            finally:
                context.close()

    def test_the_identity_mark_keeps_its_documented_floors(self):
        for width, expected in ((375, 48), (768, 56), (1280, 56), (1920, 56)):
            height = 1080 if width == 1920 else 900
            context, page = self.page_at(width, height)
            try:
                box = page.evaluate(
                    "() => { const r = document.querySelector('.brand-mark')"
                    ".getBoundingClientRect();"
                    " return [Math.round(r.width), Math.round(r.height)]; }")
                with self.subTest(width=width):
                    self.assertEqual(box, [expected, expected])
            finally:
                context.close()


class TestTheGroupSummaryReadsCorrectly(PairedRecordCase):
    """
    The homogeneous register's own sentence. It described five records with a
    singular label, and the period closing its date clause could arrive alone
    at the head of the next line.
    """

    def summary(self, home):
        match = re.search(r'<p class="register-note">(.*?)</p>', home, re.S)
        return match.group(1) if match else None

    def test_the_group_label_is_plural_and_the_row_label_is_singular(self):
        home, selected, _ = build_fixture(
            self.tmp, homogeneous_rows(), name="plural")
        note = self.summary(home)
        self.assertIsNotNone(note)
        self.assertIn(
            '<span class="evidence evidence--record">Source records</span>',
            note, "the group label describes several records and must be plural")
        # The lead keeps the singular: it labels exactly one record.
        lead = home.split('class="lead-record"', 1)[1].split("</article>", 1)[0]
        self.assertIn(
            '<span class="evidence evidence--record">Source record</span>',
            lead)
        self.assertNotIn("Source records", lead)

    def test_the_sentence_counts_and_reads_naturally(self):
        require_partial(self)
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                          autoescape=True, trim_blocks=True,
                          lstrip_blocks=True)

        def render(count):
            rows = [{"id": 100 + n, "title_english": "Record %d" % n,
                     "title_original": "第%d号" % n, "language_tag": ZH,
                     "institution": "CMC Political Work Department",
                     "source_name": "PLA Daily", "source_slug": "pla_daily",
                     "published_date": "2026-09-20"} for n in range(count)]
            return env.from_string(
                '{% from "_records.html" import record_register %}'
                "{{ record_register(records, shared) }}"
            ).render(records=rows,
                     shared={"source_slug": "pla_daily", "count": count,
                             "institution": "CMC Political Work Department",
                             "date": "2026-09-20"})

        for count, expected in ((5, "5 records, all published by"),
                                (2, "2 records, both published by"),
                                (1, "One record, published by")):
            flat = strip_tags(render(count))
            with self.subTest(records=count):
                self.assertIn(expected, flat)
                self.assertNotIn("records, published by", flat)
                self.assertNotIn("1 records", flat)
                # Doubled spacing is checked where it is observable — on the
                # browser's own `innerText`, in
                # `TestTheGroupSummaryHoldsItsLine`. HTML collapses runs of
                # source whitespace, so asserting on the markup here would
                # only pin the template's indentation.

    def test_the_date_keeps_a_machine_readable_datetime(self):
        home, selected, _ = build_fixture(
            self.tmp, homogeneous_rows(), name="datetime")
        note = self.summary(home)
        self.assertIsNotNone(note, "no group summary was rendered")
        date = selected[1]["published_date"]
        self.assertRegex(note, r'<time datetime="%s">%s</time>'
                         % (re.escape(date), re.escape(date)))
        self.assertRegex(date, r"^\d{4}-\d{2}-\d{2}$")

    def test_the_closing_period_travels_with_the_date(self):
        home, _selected, _ = build_fixture(
            self.tmp, homogeneous_rows(), name="period")
        note = self.summary(home)
        self.assertIsNotNone(note, "no group summary was rendered")
        # The period is inside the same inline wrapper as the date, so it can
        # never be the first glyph on a line.
        self.assertRegex(
            note,
            r'<span class="date-clause"><time [^>]*>[^<]*</time>\.</span>')
        # The period must be INSIDE the wrapper, never trailing it, which is
        # the arrangement that let it wrap onto a line of its own.
        self.assertNotRegex(note, r'</span>\s*\.')
        self.assertEqual(note.count("."), 2, "one clause period, one sentence")

    def test_mixed_provenance_still_suppresses_the_group_summary(self):
        rows = homogeneous_rows()
        rows[2]["source_slug"] = "mod_china"
        home, _selected, _ = build_fixture(
            self.tmp, rows, name="plural-mixed")
        self.assertIsNone(self.summary(home))
        self.assertNotIn("Source records", home)


class TestTheEvidenceLabelAgreesWithTheRowCount(PairedRecordCase):
    """
    The register's evidence label counts the rows it stands over.

    The sentence beneath it was already dynamic — "One record", "2 records,
    both", "5 records, all" — but the label above it was a literal
    `Source records`. On the normal five-row register that is right, and it is
    the state the design was reviewed in. It is wrong in exactly one reachable
    corpus shape: two suitable records, where the lead is lifted out and a
    single row remains. The page then read `SOURCE RECORDS` over
    "One record, published by ...".

    A label is a claim about how many things follow it, so it is derived from
    the same number the sentence counts rather than from either one's wording.
    """

    def register(self, count):
        """The register macro rendered over `count` grouped rows."""
        require_partial(self)
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                          autoescape=True, trim_blocks=True,
                          lstrip_blocks=True)
        rows = [{"id": 200 + n, "title_english": "Record %d" % n,
                 "title_original": "第%d号" % n, "language_tag": ZH,
                 "institution": "CMC Political Work Department",
                 "source_name": "PLA Daily", "source_slug": "pla_daily",
                 "published_date": "2026-09-20"} for n in range(count)]
        return env.from_string(
            '{% from "_records.html" import record_register %}'
            "{{ record_register(records, shared) }}"
        ).render(records=rows,
                 shared={"source_slug": "pla_daily", "count": count,
                         "institution": "CMC Political Work Department",
                         "date": "2026-09-20"})

    def label(self, fragment):
        match = re.search(
            r'<p class="register-note">\s*'
            r'<span class="evidence evidence--record">([^<]*)</span>',
            fragment, re.S)
        return match.group(1) if match else None

    def test_one_grouped_row_takes_the_singular_label(self):
        markup = self.register(1)
        self.assertEqual(self.label(markup), "Source record")
        flat = strip_tags(markup)
        self.assertIn("One record, published by", flat)
        # The plural must not survive anywhere in the summary.
        self.assertNotIn("Source records", markup)

    def test_two_grouped_rows_take_the_plural_label_and_both(self):
        markup = self.register(2)
        self.assertEqual(self.label(markup), "Source records")
        self.assertIn("2 records, both published by", strip_tags(markup))

    def test_five_grouped_rows_take_the_plural_label_and_all(self):
        markup = self.register(5)
        self.assertEqual(self.label(markup), "Source records")
        self.assertIn("5 records, all published by", strip_tags(markup))

    def test_the_label_counts_the_rows_it_actually_stands_over(self):
        """
        The derivation, not three worked examples: for every register size the
        home page can reach, the label's plural agrees with the row count and
        with the sentence.
        """
        for count in range(1, HOME_RECORDS):
            markup = self.register(count)
            rows = len(re.findall(r'<li class="register-item">', markup))
            with self.subTest(rows=count):
                self.assertEqual(rows, count, "fixture rendered the wrong "
                                              "number of rows")
                self.assertEqual(self.label(markup),
                                 "Source record" if count == 1
                                 else "Source records")

    def test_the_lead_plate_keeps_the_singular_whatever_the_register_holds(self):
        """The lead labels exactly one record, so its label never varies."""
        for rows in (HOME_RECORDS, 2):
            home, _selected, _out = build_fixture(
                self.tmp, homogeneous_rows(rows), name="lead-singular-%d" % rows)
            with self.subTest(records=rows):
                # Asserted before splitting: a tree with no lead plate must
                # report the missing product, not an IndexError from the
                # split that assumes it.
                self.assertIn('class="lead-record"', home,
                              "no lead record plate was rendered")
                lead = home.split('class="lead-record"', 1)[1] \
                           .split("</article>", 1)[0]
                self.assertIn(
                    '<span class="evidence evidence--record">'
                    'Source record</span>', lead)
                self.assertNotIn("Source records", lead)

    def test_mixed_provenance_keeps_every_row_label_singular(self):
        """
        With no group summary each row states its own provenance, and each of
        those labels describes one record. The plural must not appear on the
        page at all in this state — there is no object for it to describe.
        """
        rows = homogeneous_rows()
        rows[2]["source_slug"] = "mod_china"
        home, _selected, _out = build_fixture(
            self.tmp, rows, name="mixed-singular")
        self.assertIsNone(
            re.search(r'<p class="register-note">', home),
            "a mixed register must not carry a group summary")
        per_row = re.findall(
            r'<p class="register-meta">\s*'
            r'<span class="evidence evidence--record">([^<]*)</span>', home)
        self.assertTrue(per_row, "no per-row provenance labels were rendered")
        for index, text in enumerate(per_row):
            with self.subTest(row=index):
                self.assertEqual(text, "Source record")
        self.assertNotIn("Source records", home)


class TestTheOneRecordRegisterReadsCorrectly(BrowserCase):
    """
    The two-record corpus, rendered. One lead plate and one register row is
    the shape that exposed the label defect, and it is reachable: a fresh desk,
    or a screening backlog, leaves the page with very few analyzed records.
    """

    @classmethod
    def corpus_for_build(cls, tmp: Path) -> Path:
        db = tmp / "two-record.db"
        shutil.copy2(TRACKED_DB, db)
        keep = _newest_analyzed_ids(db, 2)
        if len(keep) < 2:
            raise unittest.SkipTest("corpus holds fewer than two analyzed "
                                    "records")
        con = sqlite3.connect(str(db))
        # Same de-analysis as the short-corpus case: `is_significant` is NOT
        # NULL, so it returns to its unassessed default rather than being
        # cleared, and the home page's selection reads `analyzed_at`.
        con.execute(
            "UPDATE articles SET analyzed_at = NULL, is_significant = 0, "
            "       model_id = NULL, prompt_version = NULL, "
            "       title_english = NULL, summary_english = NULL "
            " WHERE analyzed_at IS NOT NULL AND id NOT IN (%s)"
            % ",".join(str(i) for i in keep))
        for position, record_id in enumerate(keep):
            con.execute(
                "UPDATE articles SET title_english = ?, title_original = ?, "
                "       published_date = '2026-09-20' WHERE id = ?",
                ("Two record corpus %d" % position,
                 "两条语料第%d条" % position, record_id))
        con.commit()
        con.close()
        return db

    def test_the_page_really_holds_one_lead_and_one_register_row(self):
        """The premise. Without it every assertion below is vacuous."""
        home = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="lead-record"', home)
        self.assertEqual(
            len(re.findall(r'<li class="register-item">', home)), 1)

    def test_the_label_is_singular_and_the_sentence_agrees_at_every_width(self):
        for width in (320, 375, 768, 1280):
            context, page = self.page_at(width, 900)
            try:
                probe = page.evaluate("""() => {
                  const note = document.querySelector('.register-note');
                  if (!note) return null;
                  const clause = note.querySelector('.date-clause');
                  const rects = [...clause.getClientRects()];
                  return {
                    label: note.querySelector('.evidence').textContent.trim(),
                    text: note.innerText.replace(/\s+/g, ' ').trim(),
                    rows: document.querySelectorAll('.register-item').length,
                    clauseLines: rects.length,
                    overflowPx: document.documentElement.scrollWidth -
                                document.documentElement.clientWidth,
                    emptyProvenance: [...document.querySelectorAll(
                      '.register-item .register-meta')].filter(
                        p => !p.textContent.trim()).length,
                    perRowProvenance: document.querySelectorAll(
                      '.register-item .register-meta').length,
                  };
                }""")
                with self.subTest(width=width):
                    self.assertIsNotNone(probe, "no group summary rendered")
                    self.assertEqual(probe["rows"], 1)
                    # The DOM text, not the rendered case: `text-transform`
                    # uppercases the label on screen.
                    self.assertEqual(probe["label"], "Source record")
                    self.assertRegex(
                        probe["text"],
                        r"^(?i:Source record)\s+One record, published by .+ on "
                        r"\d{4}-\d{2}-\d{2}\. Each original-language title "
                        r"is shown as that institution published it\.$")
                    # A group summary replaces the per-row line; an empty one
                    # left behind would be an orphan.
                    self.assertEqual(probe["perRowProvenance"], 0)
                    self.assertEqual(probe["emptyProvenance"], 0)
                    # No orphan punctuation, and no doubled spacing.
                    self.assertNotIn("  ", probe["text"])
                    self.assertNotRegex(probe["text"], r"\s\.")
                    self.assertEqual(probe["clauseLines"], 1,
                                     "the date clause broke across lines")
                    self.assertLessEqual(probe["overflowPx"], 0)
            finally:
                context.close()


class TestTheGroupSummaryHoldsItsLine(BrowserCase):

    def test_the_period_never_starts_a_line_and_nothing_overflows(self):
        """
        Rendered, at four widths. The wrapper is the only nonbreaking
        construction in the sentence, so the sentence still wraps and the page
        cannot be widened by it — including at 320, where the shell is
        narrowest.
        """
        for width in (320, 375, 768, 1280):
            context, page = self.page_at(width, 900)
            try:
                probe = page.evaluate("""() => {
                  const note = document.querySelector('.register-note');
                  if (!note) return null;
                  const clause = note.querySelector('.date-clause');
                  const rects = [...clause.getClientRects()];
                  const time = clause.querySelector('time')
                    .getClientRects()[0];
                  return {
                    clauseLines: rects.length,
                    // The date's own box sits inside the wrapper's single
                    // box, so the period after it cannot be on another line.
                    contained: rects.length === 1 &&
                               time.left >= rects[0].left - 1 &&
                               time.right <= rects[0].right + 1,
                    overflowPx: document.documentElement.scrollWidth -
                                document.documentElement.clientWidth,
                    noteWraps: note.getClientRects().length > 1,
                    clauseWidth: +rects[0].width.toFixed(1),
                    text: note.innerText.replace(/\s+/g, ' ').trim(),
                    rows: document.querySelectorAll('.register-item').length,
                  };
                }""")
                with self.subTest(width=width):
                    self.assertIsNotNone(probe, "no group summary rendered")
                    self.assertEqual(probe["clauseLines"], 1,
                                     "the date clause broke across lines")
                    self.assertRegex(
                        probe["text"], r"\b%d records\b" % probe["rows"],
                        "the summary count disagrees with the rows")
                    self.assertTrue(probe["contained"])
                    self.assertLessEqual(probe["overflowPx"], 0)
                    self.assertLess(probe["clauseWidth"], 160)
                    # The sentence a reader actually sees: no doubled space,
                    # and the count agrees with the rows below it.
                    self.assertNotIn("  ", probe["text"])
                    # `innerText` reflects RENDERED case, and the evidence
                    # label is uppercased by `text-transform`, so the label is
                    # matched case-insensitively while the sentence is not.
                    self.assertRegex(
                        probe["text"],
                        r"^(?i:Source records)\s+(One record, published|"
                        r"\d+ records, (both|all) published) by .+ on "
                        r"\d{4}-\d{2}-\d{2}\. Each original-language title "
                        r"is shown as that institution published it\.$")
            finally:
                context.close()


class TestTheAnalysisSectionDegrades(unittest.TestCase):
    """
    Two absences the corpus can produce and the home page must survive: an
    edition with no cover, and no current edition at all. Neither can be
    reached by mutating the corpus — both live in `output/the-pla-watch/`,
    which is protected — so they are exercised where the decision is made:
    `edition_cover()` and the template's own guards.
    """

    def test_a_missing_cover_file_yields_no_cover_rather_than_a_gap(self):
        import json
        import tempfile as _tf
        editions = gp.load_editions(REPO_ROOT)
        if not editions:
            self.skipTest("no published edition to read")
        slug = editions[0]["slug"]
        sidecar = json.loads(
            (REPO_ROOT / "output" / "the-pla-watch" / "posts"
             / ("%s.json" % slug)).read_text(encoding="utf-8"))

        # A repo root whose cover directory exists but holds no cover for this
        # edition. `edition_cover` must return None, not a broken reference.
        root = Path(_tf.mkdtemp(prefix="c1-nocover-"))
        self.addCleanup(shutil.rmtree, root, True)
        (root / "output" / "the-pla-watch" / "covers").mkdir(parents=True)
        self.assertIsNone(gp.edition_cover(root, slug, sidecar))

        # And with the cover present it returns a complete record — so the
        # None above is the absence, not a broken call.
        real = gp.edition_cover(REPO_ROOT, slug, sidecar)
        if real is not None:
            for key in ("route", "alt", "credit_note", "sha256", "bytes"):
                with self.subTest(key=key):
                    self.assertTrue(real[key])

    def build_with_editions(self, editions):
        """
        A real build whose edition list is exactly `editions`.

        `load_editions` reads `output/the-pla-watch/`, which is protected, so
        the absence is injected at the seam instead of by touching the tree.
        The template, the stylesheet and the rest of the page are the real
        ones.
        """
        import tempfile as _tf
        tmp = Path(_tf.mkdtemp(prefix="c1-editions-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        original = gp.load_editions
        gp.load_editions = lambda root: list(editions)
        try:
            out = tmp / "build"
            gp.build(out, gp.PUBLIC_TITLE, TRACKED_DB,
                     snapshot=gp.snapshot_from_corpus(TRACKED_DB))
        finally:
            gp.load_editions = original
        return (out / "index.html").read_text(encoding="utf-8")

    def real_edition(self):
        """
        The edition the build actually leads with. Used rather than a
        synthetic one because the cover record carries a source path the
        publish step copies, and a hand-made dict would test the test.
        """
        editions = gp.load_editions(REPO_ROOT)
        if not editions:
            self.skipTest("no published edition to lead with")
        return dict(editions[0])

    def test_the_feature_renders_one_column_without_a_cover(self):
        edition = self.real_edition()
        self.assertIsNotNone(edition.get("cover"),
                             "the fixture needs an edition that HAS a cover")
        edition["cover"] = None
        html = self.build_with_editions([edition])
        section = html.split("Latest analysis", 1)[1]
        section = section.split('class="section-head', 1)[0]
        self.assertIn(edition["title"], section)
        self.assertIn("Read this edition", section)
        self.assertNotIn("feature-figure", section)
        self.assertNotIn("<img", section)
        self.assertNotIn("figure-credit", section)

    def test_the_cover_renders_with_its_dimensions_and_credit(self):
        edition = self.real_edition()
        if not edition.get("cover"):
            self.skipTest("the leading edition has no cover")
        html = self.build_with_editions([edition])
        section = html.split("Latest analysis", 1)[1]
        self.assertIn('src="%s"' % edition["cover"]["route"], section)
        self.assertIn(edition["cover"]["alt"], section)
        self.assertIn(edition["cover"]["credit_note"], section)
        self.assertIn('width="1200"', section)
        self.assertIn('height="630"', section)

    def test_no_current_edition_removes_the_section_without_a_claim(self):
        html = self.build_with_editions([])
        self.assertNotIn('<h2>Latest analysis</h2>', html)
        for phrase in ("Read this edition", "figure-credit",
                       "feature-figure", "legacy-note",
                       "Retrospective edition"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, html)
        # The folios close the gap rather than skipping a number.
        folios = re.findall(
            r'<p class="section-index" aria-hidden="true">(\d+)</p>', html)
        self.assertEqual(folios, sorted(folios),
                         "the folio sequence is out of order")
        # And the rest of the page is intact.
        for kept in ("Latest records", '<h2 id="desks">',
                     "What did not collect"):
            with self.subTest(kept=kept):
                self.assertIn(kept, html)


class TestNoProductionLiteralIsEmbedded(unittest.TestCase):
    """
    No count, date, source name, run number or record title from the current
    snapshot may be written into a template or the stylesheet. Checked against
    the corpus the build actually reads, so it keeps working as the corpus
    moves.
    """

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.data = gp.load_corpus(TRACKED_DB)
        cls.view = PublicView(TRACKED_DB)

    def sources(self):
        names = ["base.html", "home.html"]
        if RECORD_PARTIAL.is_file():
            names.append("_records.html")
        files = [TEMPLATES / n for n in names] + [CSS]
        return {f.name: f.read_text(encoding="utf-8") for f in files}

    def test_no_current_figure_date_run_or_title_is_written_in(self):
        corpus = self.data["corpus"]
        run = self.data["latest_run"]
        run_id = run["id"] if isinstance(run, dict) else run
        freshness = self.view.freshness()
        forbidden = {
            "corpus total": "{:,}".format(len(corpus)),
            "corpus total, bare": str(len(corpus)),
            "analyzed total": "{:,}".format(self.data["totals"]["analyzed"]),
            "run id": "Run %d" % run_id,
            "collection date": freshness.records_last_collected or "\0",
            "lead record title": (self.data["recent"][0]["title_english"]
                                  or "\0"),
            "lead original title": (self.data["recent"][0]["title_original"]
                                    or "\0"),
            "institution": (self.data["recent"][0]["institution"] or "\0"),
        }
        for name, text in self.sources().items():
            # Jinja comments explain the markup and render nothing.
            markup = re.sub(r"\{#.*?#\}", " ", text, flags=re.S)
            markup = re.sub(r"/\*.*?\*/", " ", markup, flags=re.S)
            for label, literal in forbidden.items():
                if literal == "\0" or len(literal) < 4:
                    continue
                with self.subTest(file=name, literal=label):
                    self.assertNotIn(literal, markup,
                                     "%s embeds the current %s" % (name, label))

    def test_the_stylesheet_references_no_editorial_asset(self):
        css = CSS.read_text(encoding="utf-8")
        for marker in ("atmosphere/", "chengdu", "j20", ".jpg", "emperornie"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, css)
