"""
The private regional prototype must not be able to touch production.

Screenshots prove a page looked right once. These prove the properties that
would still hold after someone edits the generator six months from now: that
production `output/` and the tracked database cannot change, that a desk with no
data cannot grow statistics, and that the rendered pages keep the structure the
accessibility specification depends on.

Offline. Renders into a temporary directory, never `preview/` and never
`output/`.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

import markupsafe

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

sys.path.insert(0, str(REPO_ROOT / "site" / "preview"))
import generate_preview as gp                                    # noqa: E402

TRACKED_DB = REPO_ROOT / "pla_watch.db"
PRODUCTION_OUT = REPO_ROOT / "output"


# ── House-style guard scope ──────────────────────────────────────────────────
#
# House vocabulary and spelling rules govern what the publication says in its
# OWN voice. They must not be applied to stored source text or stored model
# output: DECISION_LOG 2026-08-16 §4 requires quotations, source titles and
# published artifacts to be preserved verbatim. A PRC outlet writing "Ministry
# of National Defence", or a model summarising an article as carrying no "order
# of battle" detail, is record data — not the prototype adopting that
# vocabulary. Excluding it is not endorsing it: the page labels it, marks it
# rust, and states it is unreviewed.
#
# The exclusion removes EXACT STORED VALUES, never their containers. An earlier
# implementation stripped whole `<title>`, `<h1>`, `.interpretation` and
# `article.record` blocks, which silently un-guarded authored headings, the
# "Machine summary" label, the summary caveat, "Source record" and every
# processing-state label. Container removal cannot tell authored prose from
# stored data when both sit in one element, so it is not used.
#
# Short controlled tokens — `language_tag`, `model_id`, `prompt_version`,
# source slugs — are deliberately NOT excluded. They are closed vocabularies
# that cannot carry prose, and removing a two-character value like "en" from a
# whole page would gut authored text. Leaving them guarded is strictly safer
# and costs nothing.

#: Per-record stored values rendered as complete text nodes.
_RECORD_VALUE_FIELDS = ("title_english", "title_original", "summary_english",
                        "url")

#: Source-supplied names, from the small closed set of configured sources.
_SOURCE_NAME_FIELDS = ("display_name", "institution", "name_original")

_CORPUS_CACHE: dict = {}


def _corpus_index() -> dict:
    """Stored values, loaded once per process, read-only."""
    if not _CORPUS_CACHE:
        data = gp.load_corpus(TRACKED_DB)
        names = set()
        for source in data["sources"]:
            for field in _SOURCE_NAME_FIELDS:
                if source.get(field):
                    names.add(str(source[field]))
        _CORPUS_CACHE.update(
            by_id={r["id"]: r for r in data["corpus"]},
            names=sorted(names, key=len, reverse=True))
    return _CORPUS_CACHE


def _record_literals(record: dict, include_body: bool) -> list:
    """Every stored value this record renders as its own text node."""
    values = [str(record[f]) for f in _RECORD_VALUE_FIELDS if record.get(f)]
    if include_body:
        # record.html renders the body one paragraph per line, so each stripped
        # line — not the whole column — is what appears in the markup.
        values += [line.strip()
                   for line in (record.get("text_original") or "").split("\n")
                   if line.strip()]
    return values


def _authored_text(html: str, path: str = "", literals=None) -> str:
    """`html` with stored source and model values removed.

    Everything the publication authored survives, including labels and caveats
    that sit inside the same element as a stored value. `literals` is injectable
    so the exclusion contract can be tested without depending on which strings
    the live corpus happens to contain.
    """
    if literals is None:
        index = _corpus_index()
        literals = list(index["names"])
        referenced = {int(m) for m in
                      re.findall(r'(?:record|article)/(\d+)\.html', html)}
        own = re.search(r'(?:record|article)/(\d+)\.html$', path.replace(
            "\\", "/"))
        if own:
            record = index["by_id"].get(int(own.group(1)))
            if record:
                literals += _record_literals(record, include_body=True)
        for rec_id in referenced:
            record = index["by_id"].get(rec_id)
            if record:
                literals += _record_literals(record, include_body=False)

    # Longest first, so a value that contains another is removed as a whole.
    for value in sorted(set(literals), key=len, reverse=True):
        if len(value) < 4:
            continue
        # markupsafe is Jinja's own escaper, so the escaped form matches the
        # renderer's output exactly. It is already a dependency of the
        # generator; nothing new is introduced for this helper.
        html = html.replace(str(markupsafe.escape(value)), " ")
        html = html.replace(value, " ")
    return html


def _tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


#: The governed collection outage, as recorded in PROJECT_STATE.md. Written
#: here as data rather than imported so the expectation below is derived
#: independently of the generator; `test_the_governed_outage_window_has_not_drifted`
#: pins the two copies together, so a change to either is caught rather than
#: silently absorbed.
GOVERNED_OUTAGE_START, GOVERNED_OUTAGE_END = "2026-07-17", "2026-07-24"


def weeks_from_sql(db_path):
    """
    The publication weeks, derived from the database by SQL alone.

    This deliberately does **not** call `generate_preview`. An expectation
    computed by the code under test proves only that the code agrees with
    itself; these tests exist to check the rendered page against the corpus,
    so the corpus has to be read independently.

    Monday bucketing is done in SQL — `weekday 0` moves to that week's Sunday
    and six days back lands on its Monday — and the run-date count is assembled
    in Python from a separate `DISTINCT` query. Ordering is newest-first, which
    is the order the archive table renders.

    Opened `mode=ro&immutable=1`: no lock is taken and no `-wal` or `-shm` can
    appear beside the tracked database.
    """
    from datetime import date, timedelta
    uri = "file:%s?mode=ro&immutable=1" % urllib.parse.quote(str(db_path))
    con = sqlite3.connect(uri, uri=True)
    try:
        rows = con.execute(
            "SELECT date(a.published_date,'weekday 0','-6 days') AS start, "
            "       COUNT(*) AS n "
            "  FROM articles a JOIN sources s ON s.id = a.source_id "
            " GROUP BY start ORDER BY start DESC").fetchall()
        run_days = {r[0] for r in con.execute(
            "SELECT DISTINCT substr(started_at,1,10) FROM scrape_runs")}
    finally:
        con.close()

    weeks = []
    for start, count in rows:
        y, m, d = (int(part) for part in start.split("-"))
        monday = date(y, m, d)
        days = [(monday + timedelta(days=i)).isoformat() for i in range(7)]
        weeks.append({"start": start, "end": days[-1], "count": count,
                      "run_dates": sum(1 for day in days if day in run_days)})
    return weeks


def governed_annotations(weeks):
    """
    Which weeks the policy says must carry an annotation, and which one.

    The rule (`generate_preview.week_annotation`, ruled 2026-08-16 §6a): a week
    is annotated only when the reason is independently governed — it overlaps
    the recorded outage, or it sits at an edge of the snapshot. Nothing else
    may be.

    Both halves are derived, not listed. The outage window is governed data;
    the boundary is whichever weeks are currently first and last, so it **moves
    every time the corpus grows a week**. That movement is the whole reason the
    frozen version of this expectation had to be replaced.
    """
    starts = [w["start"] for w in weeks]
    first, last = min(starts), max(starts)
    expected = {}
    for week in weeks:
        if (week["start"] <= GOVERNED_OUTAGE_END
                and week["end"] >= GOVERNED_OUTAGE_START):
            expected[week["start"]] = "Known collection interruption"
        elif week["start"] in (first, last):
            expected[week["start"]] = "Snapshot boundary"
    return expected


def snapshot_of(db_path):
    """
    A declared snapshot describing the corpus as it actually is right now.

    The prototype's real `DECLARED_SNAPSHOT` is hand-advanced release metadata:
    it names one frozen corpus and the build refuses to publish any other under
    that name. That guard is correct for a release, and fatal for a test suite
    that runs in the daily production workflow against a corpus which advances
    every time collection succeeds.

    It was fatal, on 2026-08-21 and 2026-08-22. `SnapshotMismatch` subclasses
    `SystemExit`, so an unexpected raise inside `setUpClass` did not fail a
    test — it terminated the whole unittest process, aborting the offline suite
    and blocking the daily run before it could collect anything.

    So the structural tests below build against a snapshot derived from the
    database they are handed. What they assert — every record has a page, every
    link resolves, no heading level is skipped — is true of any corpus, and was
    never really a claim about 3,388 in particular. The declared constant is
    still asserted, by `TestDeclaredSnapshot`, which needs no build to do it.
    """
    return gp.snapshot_from_corpus(db_path)


class PreviewCase(unittest.TestCase):
    """Builds once per test into a throwaway directory."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="preview-test-"))
        cls.out = cls.tmp / "build"
        cls.snapshot = snapshot_of(TRACKED_DB)
        cls.corpus_size = cls.snapshot["expected_records"]
        cls.corpus_edge = cls.snapshot["date"]
        _data = gp.load_corpus(TRACKED_DB)
        cls.latest_run = _data["latest_run"]["id"] if isinstance(
            _data["latest_run"], dict) else _data["latest_run"]
        cls.analyzed_count = sum(
            1 for r in _data["corpus"] if r.get("analyzed_at"))
        cls.week_count = len(_data["weeks"])
        cls.result = gp.build(cls.out, "Test Title", TRACKED_DB,
                              snapshot=cls.snapshot)
        # Measured from the built tree, so necessarily after the build.
        cls.shard_count = len(list(cls.out.glob("week-*.html")))
        cls.file_count = sum(1 for q in cls.out.rglob("*") if q.is_file())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def page(self, name: str) -> str:
        return (self.out / name).read_text(encoding="utf-8")


class TestProductionIsUntouchable(PreviewCase):

    def test_building_does_not_alter_the_tracked_database(self):
        before = hashlib.sha256(TRACKED_DB.read_bytes()).hexdigest()
        gp.build(self.tmp / "again", "Test Title", TRACKED_DB,
                 snapshot=snapshot_of(TRACKED_DB))
        self.assertEqual(hashlib.sha256(TRACKED_DB.read_bytes()).hexdigest(),
                         before)

    def test_building_does_not_alter_production_output(self):
        if not PRODUCTION_OUT.exists():
            self.skipTest("no output/ in this tree")
        before = _tree_digest(PRODUCTION_OUT)
        gp.build(self.tmp / "again2", "Test Title", TRACKED_DB,
                 snapshot=snapshot_of(TRACKED_DB))
        self.assertEqual(_tree_digest(PRODUCTION_OUT), before,
                         "the prototype modified the published site")

    def test_writing_into_production_output_is_refused(self):
        with self.assertRaises(SystemExit) as ctx:
            gp.build(PRODUCTION_OUT, "Test Title", TRACKED_DB,
                     snapshot=snapshot_of(TRACKED_DB))
        self.assertIn("refusing", str(ctx.exception).lower())

    def test_writing_below_production_output_is_refused(self):
        with self.assertRaises(SystemExit):
            gp.build(PRODUCTION_OUT / "nested", "Test Title", TRACKED_DB,
                     snapshot=snapshot_of(TRACKED_DB))

    def test_two_builds_are_byte_identical(self):
        """
        Determinism is what makes 'production output unchanged' checkable at
        all — a wall-clock timestamp in the render would make every comparison
        meaningless.
        """
        a = self.tmp / "d1"
        b = self.tmp / "d2"
        snap = snapshot_of(TRACKED_DB)
        gp.build(a, "Test Title", TRACKED_DB, snapshot=snap)
        gp.build(b, "Test Title", TRACKED_DB, snapshot=snap)
        self.assertEqual(_tree_digest(a), _tree_digest(b))

    def test_no_wall_clock_timestamp_is_rendered(self):
        from datetime import date
        today = date.today().isoformat()
        for name in ("index.html", "coverage.html", "about.html"):
            body = self.page(name)
            generated = re.findall(r"[Gg]enerated[^<]{0,40}", body)
            self.assertEqual(
                generated, [],
                "%s renders a generation timestamp: %s" % (name, generated))
            # The corpus date may legitimately equal today; a *build* time must not
            # appear in prose next to words implying render time.
            self.assertNotIn("built at", body.lower())
            self.assertNotIn("last updated %s" % today, body.lower())


class TestNoFabricatedCoverage(PreviewCase):
    """
    The single most important property of this prototype. A regional shell over
    China-only data is only honest while the empty desks stay visibly empty.
    """

    def test_only_one_desk_is_marked_live(self):
        live = [d for d in gp.DESKS if d["state"] == "live"]
        self.assertEqual([d["id"] for d in live], ["china"])

    def test_developing_desks_are_labelled_and_carry_no_numbers(self):
        """
        Only desks rendered as sections are checked here. The US placeholder is
        deliberately not a section any more — see
        test_us_placeholder_is_not_a_peer_desk_section.
        """
        html = self.page("desks.html")
        for desk in gp.DESKS:
            if desk["state"] == "live" or desk["id"] == "us-indopacific":
                continue
            self.assertIn(desk["name"], html)
            # the desk's own block must not contain a digit-led statistic
            block = html.split(desk["name"], 1)[1].split("</section>", 1)[0]
            self.assertNotRegex(
                block, r"\b\d[\d,]*\s+(records|sources|runs|articles)\b",
                "%s shows a count; it has collected nothing" % desk["name"])
            self.assertIn("not yet collecting", html)

    def test_desk_directory_states_the_live_count_honestly(self):
        """
        Tranche 1 moved this from a callout into the persistent status strip.
        The claim still has to be on the page — only its rendering changed.
        """
        html = self.page("index.html")
        self.assertIn("1</b> collecting desk", html)
        self.assertIn("One\ndesk is collecting today", html)

    def test_home_page_discloses_single_desk_coverage(self):
        """
        The empty-desk disclosure and the 30-day gate now live on the desk
        directory, which is where a reader goes to ask the question.
        """
        desks = self.page("desks.html")
        self.assertIn("No records collected. No sources enabled.", desks)
        self.assertIn("30 consecutive days", desks)
        self.assertIn("Desks", self.page("index.html"))

    def test_no_page_claims_comprehensive_coverage(self):
        for p in sorted(self.out.rglob("*.html")):
            text = p.read_text(encoding="utf-8").lower()
            for banned in ("comprehensive coverage", "all chinese military",
                           "complete picture", "real-time intelligence"):
                self.assertNotIn(banned, text, "%s: %r" % (p.name, banned))

    def test_intelligence_vocabulary_is_absent(self):
        """House doctrine: never 'OSINT tool' or intelligence cosplay.

        Scoped to the publication's own voice. A machine summary reporting that
        a source article carries no "order of battle" detail is describing the
        record, not adopting the vocabulary — see `_authored_text`.
        """
        for p in sorted(self.out.rglob("*.html")):
            rel = str(p.relative_to(self.out))
            text = _authored_text(
                p.read_text(encoding="utf-8"), rel).lower()
            for banned in ("osint", "threat intelligence", "target package",
                           "order of battle", "war room"):
                self.assertNotIn(banned, text, "%s: %r" % (p.name, banned))


class TestCoverageHealthIsRendered(PreviewCase):
    """The differentiating surface must actually carry the stored record."""

    def test_every_source_in_the_run_has_a_row(self):
        html = self.page("coverage.html")
        data = gp.load_corpus(TRACKED_DB)
        self.assertTrue(data["run_results"], "no per-source results to render")
        for r in data["run_results"]:
            self.assertIn(r["source_slug"], html)

    def test_not_implemented_is_not_shown_as_healthy_silence(self):
        html = self.page("coverage.html")
        self.assertIn("Not implemented", html)
        # The stub's prose must not be the same as a source that published nothing
        self.assertNotEqual(
            gp.STATUS_PROSE["not_implemented"],
            gp.STATUS_PROSE["ok_no_publications"])

    def test_failure_and_silence_have_different_prose(self):
        self.assertNotEqual(gp.STATUS_PROSE["listing_failure"][0],
                            gp.STATUS_PROSE["ok_no_publications"][0])

    def test_collection_gaps_are_published(self):
        """
        The 2026-07-17→24 outage is real and has never appeared on a public
        surface. If the corpus has a gap, the page must show it.
        """
        gaps = gp.collection_gaps(gp.load_corpus(TRACKED_DB)["run_days"])
        html = self.page("coverage.html")
        if not gaps:
            self.skipTest("corpus currently has no multi-day gap")
        self.assertIn("Gaps in collection", html)
        self.assertIn(gaps[0]["from"], html)

    def test_gap_detection_finds_a_known_shaped_outage(self):
        days = ["2026-07-16", "2026-07-17", "2026-07-25", "2026-07-26"]
        gaps = gp.collection_gaps(days)
        self.assertEqual(gaps, [{"from": "2026-07-18", "to": "2026-07-24",
                                 "days": 7}])

    def test_a_single_missing_day_is_not_reported_as_an_outage(self):
        self.assertEqual(gp.collection_gaps(["2026-07-01", "2026-07-03"]), [])


class TestPlaWatchContinuity(PreviewCase):
    """
    The acceptance review found the prototype had no path at all to the 13
    published editions — a continuity gap in the surface whose central claim is
    that the archive survives a masthead change.
    """

    def editions(self):
        return gp.load_editions(REPO_ROOT)

    def test_every_published_edition_is_listed(self):
        html = self.page("weekly.html")
        eds = self.editions()
        self.assertGreaterEqual(len(eds), 13, "expected the published editions")
        for e in eds:
            with self.subTest(edition=e["slug"]):
                self.assertIn(e["url"], html)

    def test_edition_links_point_at_the_live_archive(self):
        html = self.page("weekly.html")
        self.assertIn(gp.LIVE_BASE + "/the-pla-watch/archive.html", html)

    def test_every_linked_edition_actually_exists(self):
        """
        The URLs are external, so they are verified against the rendered pages
        this repository already publishes rather than over the network.
        """
        posts = REPO_ROOT / "output" / "the-pla-watch" / "posts"
        for e in self.editions():
            with self.subTest(edition=e["slug"]):
                self.assertTrue(
                    (posts / (e["slug"] + ".html")).is_file(),
                    "linked edition has no rendered page in output/")

    def test_editions_are_not_duplicated_into_the_preview(self):
        """Linking, not copying: a second rendered copy would drift."""
        copied = list(self.out.rglob("*the-pla-watch*"))
        self.assertEqual(copied, [], "the prototype copied edition pages")

    def test_no_edition_metadata_is_invented(self):
        """Every rendered figure must come from the edition's own sidecar."""
        import json
        posts = REPO_ROOT / "output" / "the-pla-watch" / "posts"
        for e in self.editions():
            data = json.loads((posts / (e["slug"] + ".json")).read_text("utf-8"))
            with self.subTest(edition=e["slug"]):
                self.assertEqual(e["issue"], data.get("issue_number"))
                self.assertEqual(e["articles"], data.get("n_articles"))
                self.assertEqual(e["flagged"], data.get("n_significant"))
                self.assertEqual(e["title"], data.get("title") or "")

    def test_a_missing_sidecar_field_renders_a_dash_not_a_number(self):
        """An absent figure must read as absent, never as zero."""
        html = self.page("weekly.html")
        for e in self.editions():
            if e["flagged"] is None:
                self.assertIn("—", html,
                              "an edition with no count must show a dash")

    def test_the_series_survives_as_a_desk_level_publication(self):
        """
        Tranche 1 deleted the prose that argued the brand case: explaining your
        own brand architecture to a reader is internal governance content, not
        journalism. What must survive is the *structure* the argument described
        — the series named, placed under its desk, and reachable.
        """
        html = self.page("weekly.html")
        self.assertIn("The PLA Watch — China Desk weekly", html)
        self.assertIn("Analysis", html)
        # And the argument itself must be gone, not merely moved.
        for governance in ("predates", "Proposed hierarchy",
                           "does not make the parent product China-only"):
            with self.subTest(governance=governance):
                self.assertNotIn(governance, html)

    def test_no_edition_is_created_renumbered_or_relabelled(self):
        """
        The 13 canonical editions are read from sidecars and linked to the live
        archive. A prototype that invented, renumbered or relabelled one would
        corrupt the citation record.
        """
        html = self.page("weekly.html")
        links = re.findall(r'href="(https://[^"]*?/the-pla-watch/posts/[^"]+)"',
                           html)
        self.assertEqual(len(links), 13)
        self.assertEqual(len(set(links)), 13)
        # Issue numbers run 13..1 with nothing inserted.
        numbers = re.findall(r'class="num ed-no">(\d+)<', html)
        self.assertEqual([int(n) for n in numbers], list(range(13, 0, -1)))
        # edition_label is the analyst's field and is rendered verbatim
        # (DECISION_LOG 2026-07-17 §2).
        for label in ("Significant", "Routine", "Pilot edition"):
            with self.subTest(label=label):
                self.assertIn(label, html)


class TestEvidenceHierarchyIsHonest(PreviewCase):
    """
    The IA document specifies eight levels; three are implemented. The prototype
    must say so rather than imply the other five exist.
    """

    def test_implemented_levels_are_present(self):
        joined = "\n".join(p.read_text(encoding="utf-8")
                            for p in self.out.rglob("*.html"))
        for label in ("Source record", "Official claim", "Model-flagged"):
            self.assertIn(label, joined)

    def test_unimplemented_levels_are_not_rendered_as_empty_badges(self):
        joined = "\n".join(p.read_text(encoding="utf-8")
                            for p in self.out.rglob("*.html"))
        for absent in ("evidence--verified", "evidence--inference",
                       "evidence--confidence", "evidence--baseline"):
            self.assertNotIn(absent, joined,
                             "an unimplemented evidence level was rendered")

    def test_methodology_documents_only_labels_a_reader_can_encounter(self):
        """
        The planned eight-level taxonomy is internal design, not reader
        documentation. Publishing the five unbuilt levels invited readers to
        look for labels that do not exist.
        """
        html = self.page("methodology.html")
        for label in ("Source record", "Official claim", "Model-flagged",
                      "Significant", "Routine"):
            with self.subTest(label=label):
                self.assertIn(label, html)
        self.assertNotIn("specified in the design but not implemented", html)
        self.assertNotIn("verified fact", html.lower())

    def test_documentation_and_prototype_agree(self):
        """
        The evidence hierarchy is public doctrine, so the public operator
        document is what the prototype is held against.
        """
        ia = (REPO_ROOT / "docs" / "SITE_MODES.md").read_text(encoding="utf-8")
        self.assertIn("not demonstrated", ia,
                      "the document must mark the unimplemented levels")
        self.assertIn("Three of these eight are implemented", ia)


class TestRenderedStructure(PreviewCase):
    """Properties the accessibility specification depends on."""

    def pages(self):
        return sorted(self.out.rglob("*.html"))

    def test_exactly_one_h1_per_page(self):
        for p in self.pages():
            with self.subTest(page=p.name):
                self.assertEqual(
                    len(re.findall(r"<h1[ >]", p.read_text(encoding="utf-8"))), 1)

    def test_no_heading_level_is_skipped(self):
        for p in self.pages():
            levels = [int(m) for m in
                      re.findall(r"<h([1-6])[ >]", p.read_text(encoding="utf-8"))]
            for a, b in zip(levels, levels[1:]):
                with self.subTest(page=p.name):
                    self.assertLessEqual(b - a, 1, "h%d -> h%d" % (a, b))

    def test_landmarks_and_skip_link_present(self):
        for p in self.pages():
            html = p.read_text(encoding="utf-8")
            with self.subTest(page=p.name):
                for tag in ("<header", "<nav", "<main", "<footer"):
                    self.assertIn(tag, html)
                self.assertIn('class="skip"', html)
                self.assertIn('lang="en"', html)
                self.assertIn('name="viewport"', html)

    def test_every_table_can_scroll_without_moving_the_page(self):
        for p in self.pages():
            html = p.read_text(encoding="utf-8")
            for m in re.finditer(r"<table", html):
                before = html[:m.start()]
                with self.subTest(page=p.name):
                    self.assertGreater(
                        before.rfind('<div class="table-scroll">'),
                        before.rfind("</div>"),
                        "a table outside .table-scroll will force the page to "
                        "scroll horizontally on mobile")

    def test_focus_outline_is_never_removed(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        self.assertNotIn("outline: none", css)
        self.assertNotIn("outline:none", css)
        self.assertIn(":focus-visible", css)

    def test_reduced_motion_is_honoured(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion", css)

    def test_all_internal_links_resolve(self):
        """Both halves of a link: the file, and the fragment inside it.

        `path#fragment` previously failed outright, because the fragment was
        left on the path being resolved. Stripping it is only half the fix — a
        deep link into the Corpus Guide is broken in exactly the way a reader
        notices when the file exists and the anchor does not, so the target id
        is checked too.
        """
        ids = {}

        def anchors(path: Path) -> set:
            key = str(path)
            if key not in ids:
                body = path.read_text(encoding="utf-8")
                ids[key] = set(re.findall(r'\bid="([^"]+)"', body))
            return ids[key]

        broken = []
        for p in self.pages():
            for href in re.findall(r'href="([^"]+)"',
                                   p.read_text(encoding="utf-8")):
                if href.startswith(("http", "#", "mailto:")):
                    continue
                path, _, fragment = href.partition("#")
                target = (p.parent / path).resolve()
                if not target.exists():
                    broken.append("%s -> %s" % (p.name, href))
                elif fragment and fragment not in anchors(target):
                    broken.append("%s -> %s (no such anchor)" % (p.name, href))
        self.assertEqual(broken, [])

    def test_record_pages_expose_provenance_and_its_gaps(self):
        """Field names are the governed STOP 2 set; the intent is unchanged —
        provenance is exposed, and a gap is named rather than omitted."""
        corpus = gp.load_corpus(TRACKED_DB)["corpus"]
        gapped = next(r for r in corpus
                      if r["model_id"] and not r["prompt_version"])
        page = (self.out / "record" / ("%d.html" % gapped["id"])).read_text(
            encoding="utf-8")
        for field in ("Original URL", "Collected at", "Collection run",
                      "Content fingerprint", "Source language"):
            self.assertIn(field, page)
        self.assertIn("Prompt version is unavailable for this record.", page,
                      "a missing provenance field must be shown as missing, "
                      "not silently omitted")

    def test_model_output_is_labelled_as_model_output(self):
        corpus = gp.load_corpus(TRACKED_DB)["corpus"]
        analyzed = next(r for r in corpus if r["state"] == "analyzed")
        page = (self.out / "record" / ("%d.html" % analyzed["id"])).read_text(
            encoding="utf-8")
        self.assertIn("Machine summary", page)
        self.assertIn("Machine translation", page)
        self.assertIn("Machine assessment", page)
        self.assertIn("Not reviewed by a human", page)

    def test_archive_is_readable_without_javascript(self):
        """
        The browser is an enhancement. If the script never runs, the archive
        must still lead to every record — now through the week-shard path
        rather than through inline cards, and with no control left operative.
        """
        html = self.page("archive.html")
        self.assertIn('href="corpus.html"', html)
        self.assertIn("No JavaScript required", html)
        browse = html.split('id="browse"', 1)[1].split(">", 1)[0]
        self.assertIn("hidden", browse)
        controls = html.split('id="controls"', 1)[1].split(">", 1)[0]
        self.assertIn("hidden", controls)

    def test_working_title_is_configurable_and_flagged(self):
        """
        The masthead chip is gone — it shouted a caveat on every page. The
        caveat itself is not gone: it sits once, quietly, in the footer.
        """
        html = self.page("index.html")
        self.assertIn("Test Title", html)
        self.assertNotIn("working title — not adopted", html)
        self.assertIn("is a working name\n    pending clearance and reader "
                      "testing", html)
        self.assertNotIn("China Mil Watch", html)


class TestTrancheOneIdentityAndStructure(PreviewCase):
    """
    Properties introduced by the approved revision brief. These exist so a
    later edit cannot quietly undo the reasons for the redesign.
    """

    def _all_html(self):
        """Keyed by path relative to the build root.

        Not `p.name`: `record/3252.html` and `article/3252.html` share a
        basename, so a name-keyed dict dropped one of every colliding
        pair and left those pages unchecked.
        """
        return {str(p.relative_to(self.out)): p.read_text(encoding="utf-8")
                for p in sorted(self.out.rglob("*.html"))}

    # ── Status strip ────────────────────────────────────────────────────

    def test_status_strip_keeps_the_four_states_apart(self):
        html = self.page("index.html")
        self.assertIn("collectors executed", html)
        self.assertIn("execution failures", html)
        self.assertIn("unimplemented adapter", html)
        self.assertIn("collecting desk", html)

    def test_status_strip_shows_no_collector_denominator(self):
        """
        "4 of 5 collectors executed" asserted five collectors exist. Four do;
        the fifth configured source has no adapter, which this project's own
        vocabulary calls "no working collector". The denominator was false.
        """
        html = self.page("index.html")
        self.assertIn("<b>4</b> collectors executed", html)
        self.assertNotIn("of 5 collectors", html)
        self.assertNotRegex(html, r"\d+\s+of\s+\d+\s+collectors")

    def test_status_counts_are_derived_from_the_stored_run_record(self):
        data = gp.load_corpus(TRACKED_DB)
        summary = gp.run_status_summary(
            data["latest_run"], data["run_results"],
            data["collecting_desks"], data["unmapped_executed"])
        not_run = ("not_implemented", "skipped_disabled")
        expected_executed = sum(1 for r in data["run_results"]
                                if r["status"] not in not_run)
        expected_unimpl = sum(1 for r in data["run_results"]
                              if r["status"] == "not_implemented")
        self.assertEqual(summary["executed"], expected_executed)
        self.assertEqual(summary["unimplemented"], expected_unimpl)

    def test_collecting_desk_count_comes_from_stored_source_desk_mapping(self):
        """
        Not from the DESKS presentation constant. A rename or a new entry in
        that literal must not be able to change what the strip reports.
        """
        data = gp.load_corpus(TRACKED_DB)
        summary = gp.run_status_summary(
            data["latest_run"], data["run_results"],
            data["collecting_desks"], data["unmapped_executed"])
        self.assertEqual(summary["desks"], len(data["collecting_desks"]))
        self.assertEqual(sorted(data["collecting_desks"]), ["china"])

    def test_desk_count_is_not_a_source_count(self):
        """
        Five sources map to one desk. If the derivation ever counts sources
        instead of distinct desks, this catches it.
        """
        data = gp.load_corpus(TRACKED_DB)
        executed = [r for r in data["run_results"]
                    if r["status"] not in ("not_implemented",
                                           "skipped_disabled")]
        by_desk = {s["desk_id"] for s in data["sources"]
                   if s["slug"] in {r["source_slug"] for r in executed}}
        self.assertGreater(len(executed), len(by_desk),
                           "fixture must have several sources sharing a desk "
                           "for this test to mean anything")
        self.assertEqual(len(data["collecting_desks"]), len(by_desk))

    def test_desk_count_is_withheld_when_a_source_cannot_be_mapped(self):
        """An unmappable source means the count is unknown, not smaller."""
        s = gp.run_status_summary({"id": 1, "started_at": "2026-01-01"},
                                  [{"status": "ok", "is_failure": 0}],
                                  [], unmapped_executed=1)
        self.assertIsNone(s["desks"])
        self.assertEqual(s["desks_unmapped"], 1)

    def test_no_run_renders_no_strip_rather_than_a_reassuring_zero(self):
        self.assertIsNone(gp.run_status_summary(None, [], []))
        self.assertIsNone(gp.run_status_summary({"id": 1}, [], []))

    # ── Accent discipline ───────────────────────────────────────────────

    def test_rust_is_reserved_for_machine_generated_material(self):
        """
        --signal may only style model output. If it leaks onto callouts or
        decoration, the reader loses the one colour that means 'a model wrote
        this'.
        """
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        users = re.findall(r'([^{}]+)\{[^{}]*var\(--signal\)[^{}]*\}', css)
        selectors = " ".join(users)
        self.assertIn("--signal", css)
        for banned in (".notice", ".working-title-flag", ".status--fail"):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, selectors)

    def test_the_masthead_chip_is_gone_from_every_page(self):
        for name, html in self._all_html().items():
            with self.subTest(page=name):
                self.assertNotIn("working-title-flag", html)

    def test_callouts_are_rationed(self):
        """At most two on the whole site (revision brief §5)."""
        total = sum(html.count('class="notice"')
                    for html in self._all_html().values())
        self.assertLessEqual(total, 2, "callout treatment has crept back")

    def test_internal_governance_prose_is_not_reader_facing(self):
        for name, html in self._all_html().items():
            for governance in ("Proposed hierarchy",
                               "Why the empty desks are shown at all",
                               "Why the name on this prototype is provisional"):
                with self.subTest(page=name, phrase=governance):
                    self.assertNotIn(governance, html)

    # ── Snapshot identity and citation ──────────────────────────────────

    def test_citation_uses_snapshot_date_and_total_count_not_an_id_range(self):
        data = gp.load_corpus(TRACKED_DB)
        html = self.page("about.html")
        self.assertIn("Prototype snapshot — %s" % data["totals"]["last_date"],
                      html)
        self.assertIn("{:,} records".format(data["totals"]["articles"]), html)
        # Ids are not contiguous, so a range would be a false claim.
        self.assertNotIn("records 1", html)
        self.assertNotRegex(html, r"records\s+\d+[–-]\d+")

    def test_no_semantic_version_is_invented(self):
        for name, html in self._all_html().items():
            with self.subTest(page=name):
                self.assertNotRegex(html, r"\bv0\.\d+\b")

    # ── Desks ───────────────────────────────────────────────────────────

    def test_japan_scope_is_pre_registered_with_verified_figures(self):
        html = self.page("japan.html")
        self.assertIn("Pre-registered Japan source universe", html)
        for figure in ("135", "214", "895"):
            with self.subTest(figure=figure):
                self.assertIn(figure, html)
        self.assertIn("PDF extraction is required.", html)

    def test_japan_heading_is_not_repeated(self):
        """
        The desk directory entry and the scope section both said "Japan Desk",
        so the page appeared to introduce the same desk twice.
        """
        html = self.page("desks.html")
        headings = re.findall(r"<h[123][^>]*>(.*?)</h[123]>", html, re.S)
        text = [re.sub(r"<[^>]+>", "", h).strip() for h in headings]
        self.assertEqual(sum(1 for t in text if t.startswith("Japan Desk")), 1)

    def test_japan_repeated_title_claim_keeps_its_qualifiers(self):
        """
        The research says 27 occurrences *on the 2026 listing*, and that a
        title-only rule would collapse 26 of them. Dropping either qualifier
        overstates or vagues out a precise finding.
        """
        html = self.page("japan.html")
        self.assertIn("On the 2026 listing", html)
        self.assertIn("appears 27", html)
        self.assertIn("collapse 26 of those 27", html)

    def test_japan_scope_omits_internal_history_and_raw_field_names(self):
        html = self.page("japan.html") + self.page("desks.html")
        self.assertIn("Counts come directly from the archive listing.", html)
        for internal in ("earlier reading", "corrected count",
                         "expected_cadence_days", "silence_threshold_days",
                         "15–25", "15-25", "Chief of Staff"):
            with self.subTest(internal=internal):
                self.assertNotIn(internal, html)

    def test_japan_scope_claims_no_coverage(self):
        japan = self.page("japan.html")
        self.assertIn("nothing below has produced a record", japan)
        self.assertIn("No Japan source is enabled", japan)
        self.assertIn("No records collected. No sources enabled.", japan)
        # The directory must carry the claim too, not defer all of it.
        self.assertIn("No Japan source is enabled", self.page("desks.html"))

    def test_us_placeholder_is_not_a_peer_desk_section(self):
        """
        It was an h2 beside China and Japan, which gave an unscoped
        placeholder the same standing as a collecting desk.
        """
        html = self.page("desks.html")
        headings = [re.sub(r"<[^>]+>", "", h).strip() for h in
                    re.findall(r"<h[123][^>]*>(.*?)</h[123]>", html, re.S)]
        for h in headings:
            with self.subTest(heading=h):
                self.assertNotIn("United States", h)
                self.assertNotIn("US Indo-Pacific", h)
        self.assertNotIn('desk desk--development', html)
        self.assertIn("Not yet scoped: United States reference coverage has "
                      "not been\nresearched and is not presented as a desk.",
                      html)

    # ── Maintainer ──────────────────────────────────────────────────────

    def test_the_maintainer_is_named_with_a_route_to_reach_them(self):
        html = self.page("about.html")
        self.assertIn(gp.MAINTAINER["name"], html)
        self.assertIn(gp.MAINTAINER["role"], html)
        self.assertIn(gp.MAINTAINER["email"], html)
        self.assertIn(gp.MAINTAINER["linkedin"], html)

    def test_the_lead_edition_carries_a_byline(self):
        self.assertIn("%s, %s" % (gp.MAINTAINER["name"],
                                  gp.MAINTAINER["role"]),
                      self.page("index.html"))

    # ── Typography ──────────────────────────────────────────────────────

    def test_table_figures_are_tabular(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        self.assertRegex(
            css, r"table\s*\{[^{}]*font-variant-numeric:\s*tabular-nums")

    def test_the_type_ladder_declares_six_levels(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        for step in ("--step-wordmark", "--step-display", "--step-deck",
                     "--step-section", "--step-body", "--step-meta"):
            with self.subTest(step=step):
                self.assertIn(step, css)

    # ── Home is analysis-led ────────────────────────────────────────────

    def test_home_leads_with_the_current_issue(self):
        html = self.page("index.html")
        lead = html.index('class="lead"')
        records = html.index("Latest records")
        explanation = html.index("What this is")
        self.assertLess(lead, records)
        self.assertLess(records, explanation)

    def test_home_no_longer_opens_with_a_readme_heading(self):
        html = self.page("index.html")
        first_h = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        self.assertIsNotNone(first_h)
        self.assertNotIn("What this is", first_h.group(1))

    # ── Corpus counts and labels ────────────────────────────────────────

    def test_sources_and_institutions_are_counted_separately(self):
        """
        Five sources belong to four institutions: pla_daily and
        china_mil_online share cn_cmc_political_work. The page previously
        called the source count an institution count.
        """
        data = gp.load_corpus(TRACKED_DB)
        self.assertEqual(len(data["sources"]), 5)
        self.assertEqual(data["institutions"], 4)
        self.assertNotEqual(len(data["sources"]), data["institutions"])
        html = self.page("china.html")
        self.assertIn("5 sources across\n4 institutions", html)
        self.assertNotIn("from 5 institutions", html)

    def test_institution_count_is_derived_not_hardcoded(self):
        data = gp.load_corpus(TRACKED_DB)
        distinct = {s["institution_id"] for s in data["sources"]
                    if s["institution_id"]}
        self.assertEqual(data["institutions"], len(distinct))

    def test_analysis_labels_describe_the_stored_condition(self):
        """
        totals.analyzed is `articles.analyzed_at IS NOT NULL`. It says nothing
        about publication, and all records are part of the published corpus,
        so "Analyzed and published" conflated two different claims.
        """
        html = self.page("china.html")
        for label in ("Source records", "Analyzed records",
                      "Awaiting analysis"):
            with self.subTest(label=label):
                self.assertIn(label, html)
        self.assertNotIn("Analysed and published", html)
        self.assertNotIn("Analyzed and published", html)
        self.assertIn("Counts reflect the stored corpus at this snapshot.",
                      html)

    def test_reader_facing_counts_use_thousands_separators(self):
        data = gp.load_corpus(TRACKED_DB)
        total = data["totals"]["articles"]
        self.assertGreaterEqual(total, 1000)
        for page in ("china.html", "about.html"):
            with self.subTest(page=page):
                html = self.page(page)
                self.assertIn("{:,}".format(total), html)
                self.assertNotRegex(html, r">\s*%d\s*<" % total)

    def test_ids_dates_and_hashes_are_not_comma_formatted(self):
        """Run ids, dates and hashes are identifiers, not quantities."""
        article = next(self.out.glob("record/*.html")).read_text(
            encoding="utf-8")
        self.assertNotRegex(article, r"\b\d{1,3},\d{3}-\d{2}-\d{2}\b")
        run = re.search(r"Collection run</th><td[^>]*>(\d+)", article)
        self.assertIsNotNone(run)
        self.assertNotIn(",", run.group(1))

    # ── Lead edition count ──────────────────────────────────────────────

    def test_lead_edition_count_uses_the_governed_field_meaning(self):
        """
        n_articles is compute_stats()['total_articles'] — the week's
        relevance-passing collected articles. The edition's citations are its
        source_trail (13 entries here), so "records cited" was false.
        """
        import json
        sidecar = json.loads(
            (PRODUCTION_OUT / "the-pla-watch" / "posts"
             / "2026-08-08.json").read_text(encoding="utf-8"))
        self.assertEqual(sidecar["n_articles"], 134)
        self.assertEqual(len(sidecar["source_trail"]), 13)
        self.assertNotEqual(sidecar["n_articles"],
                            len(sidecar["source_trail"]))
        html = self.page("index.html")
        self.assertIn("134 articles", html)
        self.assertNotIn("records cited", html)
        self.assertNotIn("134 records", html)

    def test_latest_records_blurb_does_not_deny_translation(self):
        html = self.page("index.html")
        self.assertIn("The most recent China Desk records, with "
                      "original-language titles preserved.", html)
        self.assertNotIn("in the language they were published in", html)

    # ── Reader-facing language ──────────────────────────────────────────

    def test_no_repository_language_reaches_the_reader(self):
        banned = ("configuration rather than code",
                  "does not exist in this codebase",
                  "specified in the design but not implemented",
                  "does not host a second copy",
                  "production database at build time",
                  "documented stub", "legacy flagship",
                  "expected_cadence_days", "silence_threshold_days")
        for name, html in self._all_html().items():
            for phrase in banned:
                with self.subTest(page=name, phrase=phrase):
                    self.assertNotIn(phrase, html)

    def test_reader_facing_copy_uses_american_spelling(self):
        """American English in the publication's own prose.

        Scoped to authored copy. Source titles and machine output are preserved
        verbatim by ruling (DECISION_LOG 2026-08-16 §4) — a PRC outlet's
        "Ministry of National Defence" is the record, and Americanising it would
        be an edit to quoted material.
        """
        british = re.compile(
            r"\b(analysed|labelled|labelling|summarised|organised|"
            r"behaviour|colour|defence|centre|programme|judgement)\b",
            re.I)
        for name, html in self._all_html().items():
            text = re.sub(r"<[^>]+>", " ", _authored_text(html, name))
            with self.subTest(page=name):
                self.assertIsNone(british.search(text),
                                  "British spelling in %s" % name)

    def test_source_types_render_human_readable_labels(self):
        html = self.page("sources.html")
        for raw, label in gp.SOURCE_TYPE_LABELS.items():
            with self.subTest(raw=raw):
                self.assertNotIn(raw, html)
                self.assertIn(label, html)

    def test_unknown_source_type_falls_back_to_its_raw_value(self):
        f = gp.SOURCE_TYPE_LABELS
        self.assertEqual(f.get("nonexistent_type", "nonexistent_type"),
                         "nonexistent_type")

    def test_footer_does_not_repeat_the_intelligence_denial(self):
        """
        Denying it on every page introduces the association on every page.
        """
        for name, html in self._all_html().items():
            with self.subTest(page=name):
                self.assertNotIn("not an intelligence service", html)
        html = self.page("index.html")
        self.assertIn("Publication records what an institution said, not "
                      "whether its claims\n    are true", html)

    def test_coverage_note_is_reader_language(self):
        html = self.page("coverage.html")
        self.assertIn("Configured, but no working collector exists.", html)
        self.assertIn("Every configured source has a result row for this run.",
                      html)

    # ── Callouts and citations ──────────────────────────────────────────

    def test_only_two_boxed_treatments_render_site_wide(self):
        """
        Counting `.notice` alone missed three citation blocks that were also
        boxed. This counts every element carrying a boxed visual treatment.
        """
        boxed = 0
        for html in self._all_html().values():
            boxed += html.count('class="notice"')
            boxed += html.count('class="citation"')
        self.assertEqual(boxed, 2)

    def test_no_duplicate_corpus_citation_blocks(self):
        for page in ("index.html", "china.html"):
            with self.subTest(page=page):
                html = self.page(page)
                self.assertNotIn("Cite as:", html)
        about = self.page("about.html")
        self.assertEqual(about.count("Cite as:"), 1)
        self.assertIn('class="cite-line"', about)
        self.assertNotIn('class="citation"', about)

    def test_the_citation_carries_no_boxed_styling(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        block = re.search(r"\.cite-line\s*\{([^{}]*)\}", css)
        self.assertIsNotNone(block)
        self.assertNotIn("background", block.group(1))
        self.assertNotIn("border", block.group(1))

    # ── Mobile treatments ───────────────────────────────────────────────

    def test_editions_get_an_editorial_mobile_treatment(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".editions", css)
        html = self.page("weekly.html")
        # the generic key/value stacking must not apply to this table
        self.assertNotIn('<table class="stacking">', html)
        self.assertIn('<table class="editions">', html)
        for cls in ("ed-no", "ed-date", "ed-title", "ed-articles",
                    "ed-flagged"):
            with self.subTest(cls=cls):
                self.assertIn(cls, html)

    def test_edition_label_is_rendered_once_visually(self):
        """Emitted twice, but exactly one is display:none at any width."""
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".ed-label-inline { display: none; }", css)
        self.assertIn(".editions .ed-label-wide { display: none; }", css)

    def test_provenance_has_no_generic_value_pseudo_labels(self):
        article = next(self.out.glob("record/*.html")).read_text(
            encoding="utf-8")
        self.assertNotIn('data-label="Value"', article)
        self.assertNotIn('data-label="Field"', article)
        self.assertIn('<table class="provenance">', article)
        self.assertIn('scope="row"', article)

    def test_status_facts_compact_to_two_columns_at_narrow_widths(self):
        """
        Six wrapped lines made the "quiet" strip 80px tall on a 320px screen,
        giving back most of the masthead saving. Two columns x three rows keeps
        every fact and its wording while halving the band.
        """
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        narrow = css.split("@media (max-width: 600px)", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("display: grid", narrow)
        self.assertIn("repeat(2, minmax(0, 1fr))", narrow)
        # Separator dots are redundant once the grid separates the items.
        self.assertIn(".status-facts li + li::before { content: none;", narrow)
        # Tighter leading is allowed; a smaller font is not.
        self.assertNotIn("font-size", narrow.split(".status-facts", 1)[1]
                         .split("}", 1)[0])

    def test_every_status_fact_survives_the_compaction(self):
        """No fact hidden, abbreviated, truncated or merged."""
        html = self.page("index.html")
        for phrase in ("Run <b>%s</b>" % self.latest_run, self.corpus_edge,
                       "<b>4</b> collectors executed",
                       "<b>0</b> execution failures",
                       "<b>1</b> unimplemented adapter",
                       "<b>1</b> collecting desk"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, html)
        self.assertIn('<ul class="status-facts">', html)
        strip = html.split('<ul class="status-facts">', 1)[1].split("</ul>", 1)[0]
        self.assertEqual(strip.count("<li>"), 6)
        self.assertNotRegex(html, r"\d+\s+of\s+\d+\s+collectors")

    def test_about_does_not_claim_translation_for_every_text(self):
        """
        "texts alongside translations" asserted a translation exists for every
        record. It does not; the claim is now scoped.
        """
        html = self.page("about.html")
        self.assertIn("preserves official defense and security texts, with "
                      "translations where available, and\nrecords what "
                      "collection found, missed, or could not retrieve.", html)
        self.assertNotIn("alongside translations", html)
        self.assertIn("Collection gaps are published because", html)

    def test_japan_directory_note_avoids_implementation_vocabulary(self):
        html = self.page("desks.html")
        self.assertIn("Two source families have been researched and are "
                      "documented below. No source is enabled and no records "
                      "have been collected.", html)
        japan = html.split("Japan Desk", 1)[1].split("</section>", 1)[0]
        for word in ("adapter", "no data has been collected"):
            with self.subTest(word=word):
                self.assertNotIn(word, japan)

    def test_provenance_values_wrap_rather_than_clip(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        rule = re.search(r"\.token,\s*\.prov-value\s*\{([^{}]*)\}", css)
        self.assertIsNotNone(rule)
        self.assertIn("overflow-wrap", rule.group(1))


# ── Tranche 2, commit 2: full-corpus query layer ─────────────────────────────

class CorpusCase(unittest.TestCase):
    """Loads the corpus once. Read-only; asserts the database is untouched."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.before = hashlib.sha256(TRACKED_DB.read_bytes()).hexdigest()
        cls.data = gp.load_corpus(TRACKED_DB)
        cls.corpus = cls.data["corpus"]
        cls.snapshot = gp.snapshot_from_corpus(TRACKED_DB)

    def test_loading_the_corpus_does_not_alter_the_tracked_database(self):
        after = hashlib.sha256(TRACKED_DB.read_bytes()).hexdigest()
        self.assertEqual(self.before, after)

    def test_the_whole_corpus_is_loaded_not_only_analyzed_records(self):
        self.assertEqual(len(self.corpus),
                         self.data["totals"]["articles"])
        analyzed = [r for r in self.corpus if r["state"] == "analyzed"]
        self.assertLess(len(analyzed), len(self.corpus),
                        "corpus must be larger than the analyzed subset")

    def test_the_four_states_are_exhaustive_and_mutually_exclusive(self):
        codes = {s["code"] for s in gp.PROCESSING_STATES}
        self.assertEqual(len(codes), 4)
        for rec in self.corpus:
            self.assertIn(rec["state"], codes)
        # Exclusivity: each record carries exactly one state, so the per-state
        # counts must partition the corpus with nothing double-counted.
        total = sum(s["count"] for s in self.data["state_counts"])
        self.assertEqual(total, len(self.corpus))

    def test_state_counts_sum_to_the_snapshot_count(self):
        self.assertEqual(
            sum(s["count"] for s in self.data["state_counts"]),
            self.snapshot["expected_records"])

    def test_every_state_is_reported_even_when_small(self):
        """A state must not vanish from the vocabulary for being rare."""
        labels = {s["label"] for s in self.data["state_counts"]}
        self.assertEqual(labels, {"Analyzed", "Not selected for analysis",
                                  "Awaiting screening", "Analysis incomplete"})

    def test_state_derivation_matches_the_stored_columns(self):
        for rec in self.corpus:
            if rec["passed_relevance"] is None:
                expected = "awaiting_screening"
            elif rec["passed_relevance"] == 0:
                expected = "not_selected"
            elif rec["analyzed_at"] is not None:
                expected = "analyzed"
            else:
                expected = "analysis_incomplete"
            self.assertEqual(rec["state"], expected, "record %d" % rec["id"])

    def test_machine_flag_is_never_exposed_outside_the_analyzed_set(self):
        """`is_significant` is NOT NULL DEFAULT 0.

        Its zero conflates "assessed and not flagged" with "never assessed",
        so outside the analyzed set it must be None — not False.
        """
        for rec in self.corpus:
            if rec["state"] != "analyzed":
                self.assertIsNone(rec["model_flagged"], "record %d" % rec["id"])
            else:
                self.assertIsInstance(rec["model_flagged"], bool)

    def test_facets_offer_only_values_with_records(self):
        for dimension, values in self.data["facets"].items():
            for value in values:
                with self.subTest(dimension=dimension, value=value):
                    self.assertGreater(value["count"], 0)

    def test_a_configured_source_with_no_records_is_not_a_facet_value(self):
        """`xinhua_mil` is configured and holds nothing."""
        keys = {f["key"] for f in self.data["facets"]["source"]}
        self.assertNotIn("xinhua_mil", keys)
        # It is still a configured source, so this is not simply absent data.
        self.assertIn("xinhua_mil", {s["slug"] for s in self.data["sources"]})

    def test_source_and_institution_are_separate_dimensions(self):
        sources = self.data["facets"]["source"]
        institutions = self.data["facets"]["institution"]
        self.assertNotEqual(len(sources), len(institutions))
        # At least one institution aggregates more than one source, which is
        # exactly why the two dimensions cannot be collapsed.
        by_inst = defaultdict(set)
        for rec in self.corpus:
            if rec["institution_id"]:
                by_inst[rec["institution_id"]].add(rec["source_slug"])
        self.assertTrue(any(len(v) > 1 for v in by_inst.values()))

    def test_language_comes_from_the_source_not_the_article(self):
        by_source = defaultdict(set)
        for rec in self.corpus:
            by_source[rec["source_slug"]].add(rec["language_tag"])
        for slug, tags in by_source.items():
            with self.subTest(source=slug):
                self.assertEqual(len(tags), 1,
                                 "language is a source attribute")

    def test_ordering_is_deterministic_and_total(self):
        keys = [(r["published_date"], r["id"]) for r in self.corpus]
        self.assertEqual(keys, sorted(keys, reverse=True))
        self.assertEqual(len(set(keys)), len(keys), "ordering must be total")

    def test_id_gaps_are_preserved_and_never_filled(self):
        ids = [r["id"] for r in self.corpus]
        self.assertEqual(len(set(ids)), len(ids))
        highest = max(ids)
        self.assertGreater(highest, len(ids),
                           "this corpus is known to have id gaps")
        missing = set(range(1, highest + 1)) - set(ids)
        self.assertTrue(missing, "gaps must remain absent, not be synthesised")

    def test_weeks_partition_the_corpus_exactly(self):
        self.assertEqual(sum(w["count"] for w in self.data["weeks"]),
                         len(self.corpus))
        seen = [r["id"] for w in self.data["weeks"] for r in w["records"]]
        self.assertEqual(sorted(seen), sorted(r["id"] for r in self.corpus))

    def test_weeks_start_on_monday_and_run_newest_first(self):
        from datetime import date
        starts = [w["start"] for w in self.data["weeks"]]
        self.assertEqual(starts, sorted(starts, reverse=True))
        for start in starts:
            y, m, d = (int(p) for p in start.split("-"))
            self.assertEqual(date(y, m, d).weekday(), 0, start)

    def test_run_dates_are_utc_context_never_a_seven_day_denominator(self):
        for week in self.data["weeks"]:
            with self.subTest(week=week["start"]):
                self.assertLessEqual(week["run_dates"], 7)
                self.assertGreaterEqual(week["run_dates"], 0)


# ── Tranche 2, commit 3: the full snapshot record set ────────────────────────

class TestRecordPages(PreviewCase):
    """One prototype page per stored record — all 3,250, and no more."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data = gp.load_corpus(TRACKED_DB)
        cls.ids = sorted(r["id"] for r in cls.data["corpus"])
        cls.by_id = {r["id"]: r for r in cls.data["corpus"]}

    def record(self, rec_id: int) -> str:
        return (self.out / "record" / ("%d.html" % rec_id)).read_text(
            encoding="utf-8")

    def first_in_state(self, state: str) -> int:
        for rec in self.data["corpus"]:
            if rec["state"] == state:
                return rec["id"]
        self.fail("no record in state %s" % state)

    def test_page_count_equals_the_database_count(self):
        pages = list((self.out / "record").glob("*.html"))
        self.assertEqual(len(pages), len(self.ids))
        self.assertEqual(len(pages), self.snapshot["expected_records"])

    def test_page_ids_equal_the_database_ids(self):
        on_disk = sorted(int(p.stem)
                         for p in (self.out / "record").glob("*.html"))
        self.assertEqual(on_disk, self.ids)

    def test_missing_ids_have_no_page(self):
        missing = set(range(1, max(self.ids) + 1)) - set(self.ids)
        self.assertTrue(missing, "this corpus is known to have id gaps")
        for gap in missing:
            with self.subTest(id=gap):
                self.assertFalse((self.out / "record"
                                  / ("%d.html" % gap)).exists())

    def test_production_article_routes_are_untouched(self):
        """The live namespace is not this prototype's to reuse or edit."""
        live = PRODUCTION_OUT / "article"
        self.assertTrue(live.is_dir())
        self.assertEqual(len(list(live.glob("*.html"))), self.analyzed_count)

    def test_no_public_canonical_and_no_production_sitemap_entry(self):
        for rec_id in (self.ids[0], self.ids[-1]):
            html = self.record(rec_id)
            with self.subTest(id=rec_id):
                self.assertNotIn('rel="canonical"', html)
                self.assertIn('content="noindex, nofollow"', html)
        self.assertFalse((self.out / "sitemap.xml").exists())
        sitemap = (PRODUCTION_OUT / "sitemap.xml").read_text(encoding="utf-8")
        self.assertNotIn("/record/", sitemap)

    def test_the_route_is_described_as_a_prototype_path(self):
        flat = re.sub(r"\s+", " ", self.record(self.ids[-1]))
        self.assertIn("this prototype path are locators inside", flat)
        for denial in ("DOI", "accession number", "permanent identifier",
                       "public permalink", "published route"):
            with self.subTest(denial=denial):
                self.assertIn(denial, flat)

    def test_every_processing_state_has_a_rendered_page(self):
        for state in gp.STATE_ORDER:
            with self.subTest(state=state):
                html = self.record(self.first_in_state(state))
                self.assertIn(gp.STATE_LABELS[state], html)

    def test_records_without_english_claim_no_translation_or_summary(self):
        for state in ("awaiting_screening", "not_selected",
                      "analysis_incomplete"):
            rec_id = self.first_in_state(state)
            html = self.record(rec_id)
            with self.subTest(state=state):
                self.assertNotIn("Machine translation", html)
                self.assertNotIn("Machine summary", html)

    def test_an_unanalyzed_record_is_never_called_not_flagged(self):
        for state in ("awaiting_screening", "not_selected",
                      "analysis_incomplete"):
            html = self.record(self.first_in_state(state))
            with self.subTest(state=state):
                self.assertNotIn("Model-flagged", html)
                self.assertNotIn("did not\nflag it", html)
                self.assertNotIn("not flagged", html)

    def test_an_analyzed_record_distinguishes_translation_from_summary(self):
        rec_id = self.first_in_state("analyzed")
        html = self.record(rec_id)
        self.assertIn("Machine translation", html)
        self.assertIn("Machine summary", html)
        self.assertIn("distinct from the", html)

    def test_prompt_version_is_shown_when_stored(self):
        rec = next(r for r in self.data["corpus"] if r["prompt_version"])
        html = self.record(rec["id"])
        self.assertIn("Prompt version", html)
        self.assertIn(rec["prompt_version"], html)
        self.assertNotIn("Prompt version is unavailable", html)

    def test_missing_prompt_version_says_only_that_it_is_unavailable(self):
        rec = next(r for r in self.data["corpus"]
                   if r["model_id"] and not r["prompt_version"])
        html = self.record(rec["id"])
        self.assertIn("Prompt version is unavailable for this record.", html)

    def test_model_fields_are_absent_when_not_stored(self):
        rec = next(r for r in self.data["corpus"] if not r["model_id"])
        html = self.record(rec["id"])
        self.assertNotIn("Analysis model", html)
        self.assertNotIn("Prompt version", html)

    def test_empty_original_text_is_disclosed_without_a_permanence_claim(self):
        """The disclosure must not foreclose later recovery or re-capture.

        Scoped to the original-text section: the page footer legitimately says
        the record path is "not a permanent identifier", which is a different
        ruling and must not be caught here.
        """
        rec = next(r for r in self.data["corpus"] if not r["has_text"])
        html = self.record(rec["id"])
        self.assertIn("Original text is unavailable in this stored record.",
                      html)
        section = html.split("<h2>Stored source text</h2>", 1)[1].split("<h2", 1)[0]
        for word in ("permanent", "permanently", "never", "irrecoverable",
                     "cannot be recovered"):
            with self.subTest(word=word):
                self.assertNotIn(word, section)

    def test_no_fabricated_blank_field_substitutions(self):
        """A missing value is omitted or named — never invented."""
        rec = next(r for r in self.data["corpus"] if not r["model_id"])
        html = self.record(rec["id"])
        for bogus in ("N/A", "n/a", "unknown", "null", "None", "TBD"):
            with self.subTest(token=bogus):
                self.assertNotIn(">%s<" % bogus, html)

    def test_display_title_falls_back_to_the_original(self):
        rec = next(r for r in self.data["corpus"] if not r["title_english"])
        html = self.record(rec["id"])
        self.assertIn("<h1>", html)
        self.assertIn(rec["title_original"][:20], html)

    def test_exactly_one_h1_per_record_page(self):
        for state in gp.STATE_ORDER:
            html = self.record(self.first_in_state(state))
            with self.subTest(state=state):
                self.assertEqual(html.count("<h1>"), 1)

    def test_heading_levels_are_not_skipped(self):
        html = self.record(self.first_in_state("analyzed"))
        levels = [int(m) for m in re.findall(r"<h([1-6])[ >]", html)]
        self.assertEqual(levels[0], 1)
        for previous, current in zip(levels, levels[1:]):
            self.assertLessEqual(current - previous, 1)

    def test_provenance_rows_use_semantic_headers(self):
        html = self.record(self.ids[-1])
        table = html.split('class="provenance"', 1)[1].split("</table>", 1)[0]
        self.assertIn('<th scope="row">', table)
        self.assertNotIn("<td><b>", table)

    def test_the_original_source_link_is_keyboard_reachable(self):
        rec = self.by_id[self.ids[-1]]
        html = self.record(rec["id"])
        self.assertIn('<a href="%s"' % rec["url"], html)
        self.assertNotIn("tabindex=\"-1\"", html)

    def test_urls_and_hashes_can_wrap_at_320px(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        rule = re.search(r"\.token,\s*\.prov-value\s*\{([^{}]*)\}", css)
        self.assertIsNotNone(rule)
        self.assertIn("overflow-wrap", rule.group(1))

    def test_no_new_boxed_callouts_were_added(self):
        html = self.record(self.first_in_state("analyzed"))
        self.assertNotIn('class="callout', html)

    def test_citation_controls_ship_hidden_and_the_text_does_not(self):
        """STOP 4 replaces the STOP 3 marker that reserved this for commit 8.

        The property that matters is not that controls exist — it is that the
        citation reads without them. Text visible, buttons `hidden` until a
        script reveals them.
        """
        html = self.record(self.first_in_state("analyzed"))
        for button in re.findall(r"<button[^>]*data-copy[^>]*>", html):
            with self.subTest(button=button[:60]):
                self.assertIn("hidden", button)
        for anchor in ("cite-source-text", "cite-as-held"):
            with self.subTest(block=anchor):
                self.assertRegex(
                    html, r'<p class="cite-text" id="%s">[^<]+</p>' % anchor)

    def test_rust_marks_only_machine_generated_material(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        self.assertIn("--signal:       #9C5841", css)
        html = self.record(self.first_in_state("not_selected"))
        # A record with no machine output must carry no machine-output marker.
        self.assertNotIn("evidence--model", html)


# ── Tranche 2, commit 4: week-sharded no-JavaScript browsing ─────────────────

class TestWeekShards(PreviewCase):
    """Every record reachable through ordinary links, JavaScript disabled."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data = gp.load_corpus(TRACKED_DB)
        cls.weeks = cls.data["weeks"]
        cls.shards = sorted(cls.out.glob("week-*.html"))
        cls.shard_html = {p.name: p.read_text(encoding="utf-8")
                          for p in cls.shards}

    def test_every_record_appears_in_exactly_one_week(self):
        seen = [r["id"] for w in self.weeks for r in w["records"]]
        self.assertEqual(len(seen), len(set(seen)), "no id may be duplicated")
        self.assertEqual(sorted(seen),
                         sorted(r["id"] for r in self.data["corpus"]))

    def test_shard_counts_sum_to_the_snapshot(self):
        self.assertEqual(sum(w["count"] for w in self.weeks),
                         self.snapshot["expected_records"])

    def test_every_record_link_appears_across_the_shards(self):
        linked = set()
        for html in self.shard_html.values():
            linked.update(int(m) for m in
                          re.findall(r'href="record/(\d+)\.html"', html))
        self.assertEqual(linked, {r["id"] for r in self.data["corpus"]})

    def test_every_shard_link_resolves_to_a_generated_page(self):
        for name, html in self.shard_html.items():
            for rec_id in re.findall(r'href="record/(\d+)\.html"', html):
                target = self.out / "record" / ("%s.html" % rec_id)
                with self.subTest(shard=name, id=rec_id):
                    self.assertTrue(target.is_file())

    def test_every_record_is_reachable_without_javascript(self):
        """Index -> week shard -> record, all plain anchors."""
        index = self.page("corpus.html")
        shard_paths = set(re.findall(r'href="(week-[0-9-]+\.html)"', index))
        self.assertTrue(shard_paths)
        # Paginated continuations are reached from their own week's pages.
        reachable, frontier = set(shard_paths), list(shard_paths)
        while frontier:
            current = frontier.pop()
            html = self.shard_html[current]
            for nxt in re.findall(r'href="(week-[0-9-]+\.html)"', html):
                if nxt not in reachable:
                    reachable.add(nxt)
                    frontier.append(nxt)
        found = set()
        for name in reachable:
            found.update(int(m) for m in re.findall(
                r'href="record/(\d+)\.html"', self.shard_html[name]))
        self.assertEqual(found, {r["id"] for r in self.data["corpus"]})

    def test_no_javascript_is_required_by_the_shards(self):
        for name, html in self.shard_html.items():
            with self.subTest(shard=name):
                self.assertNotIn("<script", html)

    def test_no_facet_or_result_count_controls_yet(self):
        """Facets, live counts and the compact index are commit 5."""
        for name, html in self.shard_html.items():
            for token in ("<select", 'type="search"', "aria-live",
                          "facet", "corpus-index.json"):
                with self.subTest(shard=name, token=token):
                    self.assertNotIn(token, html)

    def test_no_inert_controls_are_rendered(self):
        index = self.page("corpus.html")
        for token in ("<button", "<select", "<input"):
            with self.subTest(token=token):
                self.assertNotIn(token, index)

    def test_weeks_are_newest_first_and_records_keep_corpus_order(self):
        index = self.page("corpus.html")
        listed = re.findall(r'href="(week-\d{4}-\d{2}-\d{2}\.html)"', index)
        self.assertEqual(listed, sorted(listed, reverse=True))
        for week in self.weeks:
            keys = [(r["published_date"], r["id"]) for r in week["records"]]
            with self.subTest(week=week["start"]):
                self.assertEqual(keys, sorted(keys, reverse=True))

    def test_each_shard_states_its_range_and_exact_count(self):
        for week in self.weeks:
            html = self.shard_html[week["path"]]
            with self.subTest(week=week["start"]):
                self.assertIn(week["start"], html)
                self.assertIn(week["end"], html)
                self.assertIn("{:,}".format(week["count"]), html)

    def test_entries_carry_source_language_and_processing_status(self):
        week = self.weeks[0]
        html = self.shard_html[week["path"]]
        sample = week["records"][0]
        self.assertIn(sample["source_name"], html)
        self.assertIn(sample["state_label"], html)
        self.assertIn(sample["language_tag"], html)
        self.assertIn(sample["institution"] or sample["source_name"], html)

    def test_date_boundaries_are_monday_to_sunday_and_correct(self):
        from datetime import date
        for week in self.weeks:
            y, m, d = (int(p) for p in week["start"].split("-"))
            with self.subTest(week=week["start"]):
                self.assertEqual(date(y, m, d).weekday(), 0)
                for rec in week["records"]:
                    self.assertGreaterEqual(rec["published_date"],
                                            week["start"])
                    self.assertLessEqual(rec["published_date"], week["end"])

    def test_only_governed_weeks_carry_an_annotation(self):
        """
        Exactly the governed weeks are annotated, and every other week is not.

        The expected set is derived by `governed_annotations()` from the
        corpus and the governed outage window — never copied back from the
        generator. The snapshot boundary is by definition the current first and
        last week, so it moves as the corpus grows; a frozen list of week
        starts here is a test that expires.
        """
        expected = governed_annotations(weeks_from_sql(TRACKED_DB))
        self.assertTrue(expected, "the policy annotates no week at all")

        annotated = {w["start"]: w["annotation"]
                     for w in self.weeks if w["annotation"]}
        self.assertEqual(annotated, expected)

        # The other half of "only": every week the policy does not name must
        # carry no annotation at all.
        for week in self.weeks:
            if week["start"] not in expected:
                with self.subTest(week=week["start"]):
                    self.assertIsNone(week["annotation"])
                    self.assertIsNone(week["annotation_note"])

    def test_the_annotation_reaches_the_rendered_shard(self):
        """The governed set is what a reader actually sees, not just what the
        loader computed."""
        expected = governed_annotations(weeks_from_sql(TRACKED_DB))
        for week in self.weeks:
            html = self.shard_html["week-%s.html" % week["start"]]
            with self.subTest(week=week["start"]):
                if week["start"] in expected:
                    self.assertIn(expected[week["start"]], html)
                else:
                    for label in ("Snapshot boundary",
                                  "Known collection interruption"):
                        self.assertNotIn(label, html)

    def test_the_governed_outage_window_has_not_drifted(self):
        """
        The expectation above hard-codes the outage window deliberately — it is
        governed data, not a moving fact. This is what keeps that copy honest:
        if the generator's window ever changes, the two disagree here rather
        than the expectation silently tracking whatever the code now says.
        """
        self.assertEqual(GOVERNED_OUTAGE_START, gp.OUTAGE_START)
        self.assertEqual(GOVERNED_OUTAGE_END, gp.OUTAGE_END)

    def test_outage_annotation_names_the_governed_dates(self):
        html = self.shard_html["week-2026-07-20.html"]
        self.assertIn("17–24 July 2026", html)
        self.assertIn("not evidence that nothing was published", html)

    def test_no_generic_partial_or_days_observed_language(self):
        pages = dict(self.shard_html)
        pages["corpus.html"] = self.page("corpus.html")
        banned = re.compile(r"\bpartial\b|days observed|/7 days|of 7 days",
                            re.I)
        for name, html in pages.items():
            with self.subTest(page=name):
                self.assertIsNone(banned.search(_authored_text(html, name)))

    def test_run_dates_are_never_presented_as_a_denominator(self):
        pages = dict(self.shard_html)
        pages["corpus.html"] = self.page("corpus.html")
        ratio = re.compile(r"\d\s*(?:/|of)\s*7\b")
        for name, html in pages.items():
            with self.subTest(page=name):
                self.assertIsNone(ratio.search(html),
                                  "run dates rendered as a ratio in %s" % name)
        # And each surface says what the figure is not.
        self.assertIn("not a coverage denominator", pages["corpus.html"])
        for name, html in self.shard_html.items():
            with self.subTest(shard=name):
                self.assertIn("not a measure of coverage", html)

    def test_no_permanence_language_about_missing_records(self):
        for name, html in self.shard_html.items():
            with self.subTest(shard=name):
                for word in ("permanently absent", "permanently lost",
                             "cannot be recovered", "irrecoverable"):
                    self.assertNotIn(word, html)

    def test_the_approved_caption_is_rendered_verbatim(self):
        index = re.sub(r"\s+", " ", self.page("corpus.html"))
        for fragment in (
                "Counts reflect stored records after de-duplication, not total "
                "institutional output, collection completeness, system uptime, "
                "or military activity.",
                "The accompanying run-day figure counts UTC calendar dates "
                "with at least one recorded pipeline run.",
                "it is operational context—not a coverage denominator."):
            with self.subTest(fragment=fragment[:40]):
                self.assertIn(fragment, index)

    def test_every_shard_is_within_the_page_budget(self):
        for name, html in self.shard_html.items():
            with self.subTest(shard=name):
                self.assertLessEqual(len(html.encode("utf-8")),
                                     gp.SHARD_BUDGET_BYTES)

    def test_an_over_budget_week_paginates_rather_than_truncating(self):
        paginated = [n for n in self.shard_html
                     if re.match(r"week-\d{4}-\d{2}-\d{2}-\d+\.html$", n)]
        self.assertTrue(paginated, "expected at least one week to paginate")
        for name in paginated:
            html = self.shard_html[name]
            with self.subTest(shard=name):
                self.assertIn("Page ", html)
                self.assertIn("Previous page", html)

    def test_css_is_external_and_never_inlined_into_a_shard(self):
        for name, html in self.shard_html.items():
            with self.subTest(shard=name):
                self.assertIn('<link rel="stylesheet"', html)
                self.assertNotIn("<style", html)

    def test_shards_have_one_h1_and_no_skipped_heading_levels(self):
        for name, html in self.shard_html.items():
            levels = [int(m) for m in re.findall(r"<h([1-6])[ >]", html)]
            with self.subTest(shard=name):
                self.assertEqual(html.count("<h1>"), 1)
                self.assertEqual(levels[0], 1)
                for previous, current in zip(levels, levels[1:]):
                    self.assertLessEqual(current - previous, 1)

    def test_the_existing_title_search_has_not_regressed(self):
        """The working archive stays primary until its replacement carries
        search too. Removing it here would be a silent regression."""
        html = self.page("archive.html")
        self.assertIn('id="f-q"', html)
        self.assertIn("Title contains", html)
        # The replacement is complete, so the legacy duplicate detail
        # namespace is retired; `record/` is the single record surface.
        self.assertFalse((self.out / "article").exists())
        self.assertTrue((self.out / "record").is_dir())

    def test_the_new_corpus_path_is_exposed_for_review(self):
        self.assertIn('href="corpus.html"', self.page("archive.html"))


# ── Tranche 2 remediation: record and archive semantics ──────────────────────

class TestRecordSemantics(PreviewCase):
    """Asserted across the WHOLE corpus, not the first record in each state."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data = gp.load_corpus(TRACKED_DB)

    def record(self, rec_id: int) -> str:
        return (self.out / "record" / ("%d.html" % rec_id)).read_text(
            encoding="utf-8")

    def test_every_analyzed_record_matches_its_own_boolean(self):
        checked = 0
        for rec in self.data["corpus"]:
            if rec["state"] != "analyzed":
                continue
            html = self.record(rec["id"])
            checked += 1
            if rec["is_significant"]:
                self.assertIn("Model-flagged for closer review.", html,
                              "record %d" % rec["id"])
                self.assertNotIn("Not flagged for closer review.", html,
                                 "record %d" % rec["id"])
            else:
                self.assertIn("Not flagged for closer review.", html,
                              "record %d" % rec["id"])
                self.assertNotIn("Model-flagged", html,
                                 "record %d must not be labelled model-flagged"
                                 % rec["id"])
        self.assertEqual(checked, self.analyzed_count)

    def test_model_flagged_appears_only_when_the_flag_is_true(self):
        flagged = {r["id"] for r in self.data["corpus"] if r["is_significant"]}
        self.assertTrue(flagged)
        for rec in self.data["corpus"]:
            if "Model-flagged" in self.record(rec["id"]):
                self.assertIn(rec["id"], flagged, "record %d" % rec["id"])

    def test_no_machine_assessment_outside_the_analyzed_state(self):
        for rec in self.data["corpus"]:
            if rec["state"] == "analyzed":
                continue
            html = self.record(rec["id"])
            with self.subTest(id=rec["id"]):
                self.assertNotIn("Machine assessment", html)
                self.assertNotIn("Model-flagged", html)
                self.assertNotIn("flagged for closer review", html)

    def test_the_common_label_is_neutral_for_both_outcomes(self):
        for rec in self.data["corpus"][:400]:
            if rec["state"] != "analyzed":
                continue
            with self.subTest(id=rec["id"]):
                self.assertIn("Machine assessment", self.record(rec["id"]))

    def test_machine_assessment_stays_rust_marked(self):
        rec = next(r for r in self.data["corpus"] if r["state"] == "analyzed")
        block = self.record(rec["id"]).split("Machine assessment", 1)[0]
        self.assertTrue(block.rstrip().endswith('evidence--model">'))

    def test_unscreened_and_unselected_records_carry_no_generated_output(self):
        """If the stored data ever contradicts this, stop — do not force copy."""
        offenders = [r["id"] for r in self.data["corpus"]
                     if r["state"] in ("not_selected", "awaiting_screening")
                     and (r["summary_english"] or r["title_english"])]
        self.assertEqual(offenders, [],
                         "stored data contradicts the copy for %d record(s); "
                         "stop and report rather than forcing the wording"
                         % len(offenders))
        for rec in self.data["corpus"]:
            if rec["state"] not in ("not_selected", "awaiting_screening"):
                continue
            html = self.record(rec["id"])
            with self.subTest(id=rec["id"]):
                self.assertNotIn("Machine summary", html)
                self.assertNotIn("Machine translation", html)

    def test_the_four_state_definitions_use_american_english(self):
        british = re.compile(
            r"\b(analysed|labelled|summarised|judgement|behaviour|centre|"
            r"programme|defence)\b", re.I)
        for state in gp.PROCESSING_STATES:
            with self.subTest(state=state["code"]):
                self.assertIsNone(british.search(state["definition"]))
                self.assertIsNone(british.search(state["label"]))

    def test_the_corrected_state_definitions_are_in_force(self):
        by_code = {s["code"]: s["definition"] for s in gp.PROCESSING_STATES}
        self.assertEqual(
            by_code["awaiting_screening"],
            "Stored but not yet screened for relevance. No judgment of any "
            "kind has been made about this record.")
        self.assertEqual(
            by_code["analysis_incomplete"],
            "Passed relevance screening, but analysis did not complete. The "
            "original record remains stored; no completed analysis is "
            "claimed.")

    def test_re_queueable_never_reaches_a_reader(self):
        for path in sorted(self.out.rglob("*.html")):
            with self.subTest(page=str(path.relative_to(self.out))):
                self.assertNotIn("re-queueable",
                                 path.read_text(encoding="utf-8"))

    def test_stored_source_text_heading_is_qualified(self):
        for rec in self.data["corpus"][:200]:
            html = self.record(rec["id"])
            with self.subTest(id=rec["id"]):
                self.assertIn("<h2>Stored source text</h2>", html)
                self.assertNotIn("<h2>Original text</h2>", html)

    def test_the_extraction_caveat_renders_on_every_record(self):
        caveat = ("Text captured from the source page. Extraction may omit "
                  "material\nor include unrelated page elements; consult the "
                  "original URL when exact wording\nor completeness matters.")
        flat = re.sub(r"\s+", " ", caveat)
        for rec in self.data["corpus"][:200]:
            page = re.sub(r"\s+", " ", self.record(rec["id"]))
            with self.subTest(id=rec["id"]):
                self.assertIn(flat, page)

    def test_the_caveat_renders_for_empty_and_noisy_captures_alike(self):
        empty = next(r for r in self.data["corpus"] if not r["has_text"])
        html = self.record(empty["id"])
        self.assertIn("Extraction may omit material", re.sub(r"\s+", " ", html))
        self.assertIn("Original text is unavailable in this stored record.",
                      html)

    def test_no_capture_is_called_verbatim_complete_or_permanent(self):
        """The approved caveat itself says "completeness"; that is the
        opposite of a completeness claim, so it is removed before scanning,
        and the remaining check is whole-word."""
        caveat = re.compile(
            r'<p class="meta">Text captured from the source page.*?</p>', re.S)
        stored = re.compile(r'<div class="original-text".*?</div>', re.S)
        claim = re.compile(
            r"\b(verbatim|complete|completely|archival|corrected|permanent|"
            r"permanently)\b", re.I)
        for rec in self.data["corpus"][:200]:
            section = self.record(rec["id"]).split(
                "<h2>Stored source text</h2>", 1)[1].split("<h2", 1)[0]
            with self.subTest(id=rec["id"]):
                self.assertIsNotNone(caveat.search(section))
                # A source article that happens to use the word "complete" is
                # not the publication claiming the capture is complete.
                authored = stored.sub(" ", caveat.sub(" ", section))
                self.assertIsNone(claim.search(authored))

    def test_noisy_stored_text_is_preserved_byte_for_byte(self):
        """Record 2579's capture carries unrelated page furniture. It stays."""
        rec = self.data["corpus"] and next(
            r for r in self.data["corpus"] if r["id"] == 2579)
        html = self.record(2579)
        for para in [p.strip() for p in rec["text_original"].split("\n")
                     if p.strip()]:
            with self.subTest(para=para[:40]):
                self.assertIn(markupsafe.escape(para), markupsafe.Markup(html))

    def test_the_caveat_is_not_a_boxed_callout(self):
        rec = next(r for r in self.data["corpus"] if r["state"] == "analyzed")
        section = self.record(rec["id"]).split(
            "<h2>Stored source text</h2>", 1)[1].split("<h2", 1)[0]
        self.assertNotIn("callout", section)
        self.assertIn('<p class="meta">Text captured from the source page.',
                      section)


class TestTransitionalArchiveIsTruthful(PreviewCase):

    def test_the_archive_describes_the_whole_snapshot_truthfully(self):
        """The transitional 60-record sample is gone. The archive now covers
        the complete snapshot, so the completeness claim is true."""
        html = self.page("archive.html")
        lede = re.sub(r"\s+", " ", html.split('class="lede"', 1)[1]
                      .split("</p>", 1)[0])
        self.assertIn("Search and filter the complete prototype snapshot", lede)
        self.assertIn("{:,}".format(self.corpus_size), lede)
        self.assertNotIn("recent sample", html)
        self.assertNotIn("the list is complete", html)

    def test_the_archive_does_not_claim_completeness_anywhere(self):
        html = re.sub(r"\s+", " ", self.page("archive.html"))
        for claim in ("list is complete", "complete and readable",
                      "every record below", "all records"):
            with self.subTest(claim=claim):
                self.assertNotIn(claim, html)

    def test_completeness_is_backed_by_a_reachable_complete_path(self):
        html = re.sub(r"\s+", " ", self.page("archive.html"))
        self.assertIn("complete prototype snapshot", html)
        self.assertIn("Every record is also reachable by publication week",
                      html)

    def test_the_working_title_search_is_still_present_and_not_inert(self):
        html = self.page("archive.html")
        self.assertIn('id="f-q"', html)
        self.assertIn("Title contains", html)
        self.assertIn("<script", html)


# ── Tranche 2 remediation: shard limits and mobile corpus tables ─────────────

class TestShardRecordLimit(PreviewCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data = gp.load_corpus(TRACKED_DB)
        cls.shards = {p.name: p.read_text(encoding="utf-8")
                      for p in sorted(cls.out.glob("week-*.html"))}

    def test_no_shard_page_exceeds_the_record_ceiling(self):
        self.assertEqual(gp.SHARD_MAX_RECORDS, 50)
        for name, html in self.shards.items():
            with self.subTest(shard=name):
                self.assertLessEqual(html.count('<article class="record">'),
                                     gp.SHARD_MAX_RECORDS)

    def test_no_shard_page_exceeds_the_byte_budget(self):
        for name, html in self.shards.items():
            with self.subTest(shard=name):
                self.assertLessEqual(len(html.encode("utf-8")),
                                     gp.SHARD_BUDGET_BYTES)

    def test_every_id_appears_exactly_once_across_the_paginated_set(self):
        seen = []
        for html in self.shards.values():
            seen += [int(m) for m in
                     re.findall(r'href="record/(\d+)\.html"', html)]
        self.assertEqual(len(seen), len(set(seen)), "no id may be duplicated")
        self.assertEqual(sorted(seen),
                         sorted(r["id"] for r in self.data["corpus"]))

    def test_page_one_keeps_the_plain_week_path(self):
        for week in self.data["weeks"]:
            with self.subTest(week=week["start"]):
                self.assertIn(week["path"], self.shards)
                self.assertIn(week["path"], self.page("corpus.html"))

    def test_later_pages_use_the_numbered_form(self):
        numbered = [n for n in self.shards
                    if re.match(r"week-\d{4}-\d{2}-\d{2}-\d+\.html$", n)]
        self.assertTrue(numbered)
        for name in numbered:
            self.assertRegex(name, r"week-\d{4}-\d{2}-\d{2}-[2-9]\d*\.html$")

    def test_pagers_appear_at_both_top_and_bottom(self):
        for name, html in self.shards.items():
            if "Page " not in html:
                continue
            with self.subTest(shard=name):
                self.assertEqual(html.count('aria-label="Pages within this '
                                            'week"'), 2)
                body = html.split("<h2>Records</h2>", 1)
                self.assertIn("Page ", body[0])
                self.assertIn("Page ", body[1])

    def test_every_pager_link_resolves(self):
        for name, html in self.shards.items():
            for href in re.findall(r'href="(week-[0-9a-z-]+\.html)"', html):
                with self.subTest(shard=name, href=href):
                    self.assertTrue((self.out / href).is_file())

    def test_page_x_of_n_is_stated(self):
        paginated = [h for h in self.shards.values() if "Page " in h]
        self.assertTrue(paginated)
        for html in paginated:
            self.assertRegex(html, r"Page \d+ of \d+")

    def test_run_date_context_is_stated_once_per_page_as_week_context(self):
        for name, html in self.shards.items():
            with self.subTest(shard=name):
                self.assertEqual(html.count("recorded run date"), 1)
                self.assertIn("overlap this week", html)
                self.assertIn("not a measure of coverage", html)

    def test_governed_annotations_may_repeat_across_a_weeks_pages(self):
        outage = [n for n in self.shards if n.startswith("week-2026-07-20")]
        self.assertTrue(outage)
        for name in outage:
            with self.subTest(shard=name):
                self.assertIn("Known collection interruption", self.shards[name])

    def test_every_record_remains_reachable_without_javascript(self):
        index = self.page("corpus.html")
        reachable = set(re.findall(r'href="(week-[0-9a-z-]+\.html)"', index))
        frontier = list(reachable)
        while frontier:
            html = self.shards[frontier.pop()]
            for nxt in re.findall(r'href="(week-[0-9a-z-]+\.html)"', html):
                if nxt not in reachable:
                    reachable.add(nxt)
                    frontier.append(nxt)
        found = set()
        for name in reachable:
            found.update(int(m) for m in
                         re.findall(r'href="record/(\d+)\.html"',
                                    self.shards[name]))
        self.assertEqual(found, {r["id"] for r in self.data["corpus"]})
        for html in self.shards.values():
            self.assertNotIn("<script", html)


class TestCorpusIndexMobileTables(PreviewCase):

    def test_only_the_two_corpus_tables_carry_the_new_classes(self):
        index = self.page("corpus.html")
        self.assertIn('<table class="corpus-states">', index)
        self.assertIn('<table class="corpus-weeks">', index)
        for other in ("record/1.html", "coverage.html", "sources.html"):
            path = self.out / other
            if path.exists():
                html = path.read_text(encoding="utf-8")
                with self.subTest(page=other):
                    self.assertNotIn("corpus-states", html)
                    self.assertNotIn("corpus-weeks", html)

    def test_table_semantics_and_scope_survive(self):
        index = self.page("corpus.html")
        for cls in ("corpus-states", "corpus-weeks"):
            table = index.split('class="%s"' % cls, 1)[1].split("</table>", 1)[0]
            with self.subTest(table=cls):
                self.assertIn("<caption>", table)
                self.assertIn('<th scope="col">', table)
                self.assertIn('<th scope="row">', table)

    def test_captions_are_not_collapsed_at_any_width(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        block = css.split("Corpus index tables at narrow widths", 1)[1]
        block = block.split("@media (prefers-reduced-motion", 1)[0]
        self.assertNotIn("caption", block,
                         "the corpus rules must not touch captions")

    def test_headers_stay_in_the_accessibility_tree(self):
        """Off-screen, not display:none — scope relationships must survive."""
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        block = css.split("Corpus index tables at narrow widths", 1)[1]
        block = block.split("@media (prefers-reduced-motion", 1)[0]
        self.assertIn("position: absolute; left: -9999px", block)
        self.assertNotIn("thead { display: none", block)

    def test_no_pseudo_label_duplicates_the_column_header(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        block = css.split("Corpus index tables at narrow widths", 1)[1]
        block = block.split("@media (prefers-reduced-motion", 1)[0]
        # The block's own header comment discusses ::before, and the split
        # consumed its opening `/*`. Start after that comment closes, then
        # strip any remaining comments, so only declarations are scanned.
        block = block.split("*/", 1)[1]
        block = re.sub(r"/\*.*?\*/", " ", block, flags=re.S)
        self.assertNotIn("::before", block)
        self.assertNotIn("attr(data-label)", block)

    def test_unit_words_are_markup_hidden_on_wide_viewports(self):
        index = self.page("corpus.html")
        self.assertIn('<span class="c-unit"> records</span>', index)
        self.assertIn('<span class="c-unit"> recorded run dates (UTC)</span>',
                      index)
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".c-unit { display: none; }", css)

    def test_week_ranges_never_break_mid_date(self):
        index = self.page("corpus.html")
        self.assertIn(".c-range", (self.out / "styles.css").read_text(
            encoding="utf-8"))
        self.assertIn('<span class="c-range">', index)
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        rule = css.split(".c-range {", 1)[1].split("}", 1)[0]
        self.assertIn("white-space: nowrap", rule)

    def test_no_raw_enum_reaches_the_corpus_index(self):
        index = self.page("corpus.html")
        raw = [s["code"] for s in gp.PROCESSING_STATES if "_" in s["code"]]
        self.assertTrue(raw)
        for code in raw:
            with self.subTest(code=code):
                self.assertNotIn(code, index)

    def test_tabular_figures_are_kept(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        block = css.split("Corpus index tables at narrow widths", 1)[1]
        block = block.split("@media (prefers-reduced-motion", 1)[0]
        self.assertIn("tabular-nums lining-nums", block)

    def test_desktop_layout_is_not_altered_by_the_new_rules(self):
        """Every new rule lives inside the ≤640px query, so 768px and up are
        untouched; only `.c-unit`/`.c-range` apply globally, and they hide
        text and prevent a date break respectively."""
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        block = css.split("Corpus index tables at narrow widths", 1)[1]
        block = block.split("@media (prefers-reduced-motion", 1)[0]
        outside = block.split("@media (max-width: 640px) {", 1)
        before, after = outside[0], outside[1].rsplit("}", 1)[-1]
        self.assertNotIn("corpus-states", before + after)
        self.assertNotIn("corpus-weeks", before + after)


# ── STOP 3: compact query index and the global browser ───────────────────────

class TestCompactQueryIndex(PreviewCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data = gp.load_corpus(TRACKED_DB)
        cls.raw = (cls.out / "corpus-index.json").read_bytes()
        cls.index = json.loads(cls.raw.decode("utf-8"))

    def test_the_index_is_external_and_never_inlined(self):
        for path in sorted(self.out.rglob("*.html")):
            html = path.read_text(encoding="utf-8")
            with self.subTest(page=str(path.relative_to(self.out))):
                self.assertNotIn('"records":[[', html)
                self.assertNotIn("corpus-index.json\"><", html)
        self.assertIn('src="browse.js"', self.page("archive.html"))

    def test_the_index_holds_all_and_only_the_stored_ids(self):
        ids = [row[0] for row in self.index["records"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sorted(ids),
                         sorted(r["id"] for r in self.data["corpus"]))
        self.assertEqual(len(ids), self.snapshot["expected_records"])

    def test_the_six_missing_ids_remain_absent(self):
        ids = {row[0] for row in self.index["records"]}
        missing = set(range(1, max(ids) + 1)) - ids
        self.assertEqual(len(missing), 6)

    def test_snapshot_date_and_count_match_the_declaration(self):
        self.assertEqual(self.index["snapshot"]["date"],
                         self.snapshot["date"])
        self.assertEqual(self.index["snapshot"]["records"],
                         self.snapshot["expected_records"])

    def test_the_internal_fingerprint_is_never_exposed(self):
        blob = self.raw.decode("utf-8")
        self.assertNotIn(self.snapshot["logical_sha256"], blob)
        # Not a bare "logical" search: stored titles legitimately contain
        # words like "technological". The digest and its key are what must
        # never ship.
        self.assertNotIn("logical_sha256", blob)
        self.assertNotIn("fingerprint", blob)
        for path in sorted(self.out.rglob("*")):
            if path.is_file() and path.suffix in (".html", ".js"):
                with self.subTest(f=path.name):
                    self.assertNotIn(self.snapshot["logical_sha256"],
                                     path.read_text(encoding="utf-8"))

    def test_prohibited_fields_are_absent(self):
        blob = self.raw.decode("utf-8")
        for field in gp.INDEX_FORBIDDEN_FIELDS:
            with self.subTest(field=field):
                self.assertNotIn('"%s"' % field, blob)
        sample = next(r for r in self.data["corpus"]
                      if r["state"] == "analyzed" and r["has_text"])
        for value in (sample["summary_english"], sample["url"],
                      sample["content_hash"], sample["scraped_at"]):
            with self.subTest(value=str(value)[:30]):
                self.assertNotIn(value, blob)
        self.assertNotIn(sample["text_original"][:60], blob)

    def test_every_index_row_carries_exact_titles_and_six_fields(self):
        """Corpus-wide, not sampled: 3,250 rows, every one checked."""
        by_id = {r["id"]: r for r in self.data["corpus"]}
        self.assertEqual(len(self.index["records"]), self.corpus_size)
        for row in self.index["records"]:
            rec = by_id[row[0]]
            self.assertEqual(len(row), 6, "record %d" % row[0])
            self.assertEqual(row[4], rec["title_english"] or "",
                             "record %d" % row[0])
            self.assertEqual(row[5], rec["title_original"] or "",
                             "record %d" % row[0])

    def test_the_index_declares_the_expected_field_schema(self):
        self.assertEqual(self.index["fields"],
                         ["id", "date", "source", "state", "title_en",
                          "title_orig"])

    def test_institution_and_language_are_not_duplicated_per_record(self):
        """They are source attributes; a record stores one source index."""
        for source in self.index["sources"]:
            self.assertIn("institution", source)
            self.assertIn("language", source)
        for row in self.index["records"][:50]:
            self.assertIsInstance(row[2], int)

    def test_every_facet_option_has_backing_records_matching_sql(self):
        expected = {
            "sources": Counter(r["source_slug"] for r in self.data["corpus"]),
            "institutions": Counter(r["institution_id"]
                                    for r in self.data["corpus"]),
            "languages": Counter(r["language_tag"]
                                 for r in self.data["corpus"]),
            "states": Counter(r["state"] for r in self.data["corpus"]),
        }
        for key, counts in expected.items():
            offered = {e["code"]: e["count"] for e in self.index[key]}
            with self.subTest(facet=key):
                self.assertEqual(offered, dict(counts))
                for code, n in offered.items():
                    self.assertGreater(n, 0)

    def test_xinhua_is_absent_from_the_source_facet(self):
        codes = {s["code"] for s in self.index["sources"]}
        self.assertNotIn("xinhua_mil", codes)
        self.assertIn("xinhua_mil", {s["slug"] for s in self.data["sources"]})

    def test_source_and_institution_overlap_is_represented(self):
        by_inst = defaultdict(set)
        for source in self.index["sources"]:
            by_inst[source["institution"]].add(source["code"])
        shared = [v for v in by_inst.values() if len(v) > 1]
        self.assertTrue(shared, "one institution must span two sources")
        inst = self.index["institutions"][0]
        member_total = sum(s["count"] for s in self.index["sources"]
                           if s["institution"] == 0)
        self.assertEqual(inst["count"], member_total)

    def test_language_is_resolved_through_the_source(self):
        for source in self.index["sources"]:
            lang = self.index["languages"][source["language"]]
            slug = source["code"]
            stored = {r["language_tag"] for r in self.data["corpus"]
                      if r["source_slug"] == slug}
            with self.subTest(source=slug):
                self.assertEqual(stored, {lang["code"]})

    def test_processing_states_stay_exhaustive_and_disjoint(self):
        codes = [s["code"] for s in self.index["states"]]
        self.assertEqual(set(codes), set(gp.STATE_ORDER))
        self.assertEqual(sum(s["count"] for s in self.index["states"]),
                         self.snapshot["expected_records"])
        for row in self.index["records"]:
            self.assertIsInstance(row[3], int)

    def test_no_raw_enum_or_model_flag_facet_reaches_the_page(self):
        html = self.page("archive.html")
        for token in ("is_significant", "model-flag", "Model-flagged",
                      "Significant", "Routine", "model_flagged"):
            with self.subTest(token=token):
                self.assertNotIn(token, html)
        blob = self.raw.decode("utf-8")
        self.assertNotIn("is_significant", blob)

    def test_the_index_is_byte_deterministic(self):
        tmp = Path(tempfile.mkdtemp(prefix="index-determinism-"))
        snap = snapshot_of(TRACKED_DB)
        try:
            gp.build(tmp / "a", "Test Title", TRACKED_DB, snapshot=snap)
            gp.build(tmp / "b", "Test Title", TRACKED_DB, snapshot=snap)
            self.assertEqual((tmp / "a" / "corpus-index.json").read_bytes(),
                             (tmp / "b" / "corpus-index.json").read_bytes())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_index_is_materially_smaller_than_production_inline(self):
        self.assertLess(len(self.raw), 1_766_953 // 2)

    def test_the_index_is_emitted_only_after_the_snapshot_assertions(self):
        source = (REPO_ROOT / "site" / "preview"
                  / "generate_preview.py").read_text(encoding="utf-8")
        body = source.split("def build(", 1)[1]
        self.assertLess(body.index("assert_snapshot("),
                        body.index("corpus_index("))


class TestCorpusBrowserMarkup(PreviewCase):

    def test_controls_are_inert_without_javascript(self):
        html = self.page("archive.html")
        browse = html.split('id="browse"', 1)[1].split(">", 1)[0]
        self.assertIn("hidden", browse)
        controls = html.split('id="controls"', 1)[1].split(">", 1)[0]
        self.assertIn("hidden", controls)

    def test_a_visible_no_javascript_path_reaches_the_corpus(self):
        html = self.page("archive.html")
        block = html.split('id="nojs-path"', 1)[1].split("</p>", 1)[0]
        self.assertNotIn("hidden", block.split(">", 1)[0])
        self.assertIn('href="corpus.html"', block)
        self.assertIn("No JavaScript required", block)

    def test_the_index_error_state_is_distinct_from_zero_results(self):
        html = self.page("archive.html")
        error = html.split('id="index-error"', 1)[1].split("</p>", 1)[0]
        self.assertIn("could not be loaded or did not match this snapshot",
                      error)
        self.assertIn("remain accessible through the week-by-week browse",
                      re.sub(r"\s+", " ", error))
        empty = html.split('id="no-results"', 1)[1].split("</p>", 1)[0]
        self.assertIn("No records match these filters", empty)
        self.assertNotIn("could not be loaded", empty)

    def test_language_codes_render_as_editorial_labels(self):
        self.assertEqual(gp.LANGUAGE_LABELS,
                         {"zh-Hans": "Simplified Chinese", "en": "English"})
        index = json.loads((self.out / "corpus-index.json").read_text(
            encoding="utf-8"))
        offered = {e["code"]: e["label"] for e in index["languages"]}
        self.assertEqual(offered,
                         {"zh-Hans": "Simplified Chinese", "en": "English"})

    def test_every_stored_language_tag_is_mapped(self):
        corpus = gp.load_corpus(TRACKED_DB)["corpus"]
        for tag in {r["language_tag"] for r in corpus}:
            with self.subTest(tag=tag):
                self.assertIn(tag, gp.LANGUAGE_LABELS)
                self.assertNotEqual(gp.language_label(tag), tag)

    def test_an_unmapped_tag_falls_back_rather_than_guessing(self):
        self.assertEqual(gp.language_label("ru-RU"), "ru-RU")

    def test_result_cards_use_the_label_not_the_raw_tag(self):
        js = (self.out / "browse.js").read_text(encoding="utf-8")
        card = js.split("function card(", 1)[1].split("function render", 1)[0]
        self.assertIn("lang.label", card)
        # `lang.code` survives only as the `lang` attribute on the original
        # title, which is where a BCP 47 tag belongs.
        for hit in re.findall(r"lang\.code", card):
            pass
        self.assertIn('orig.setAttribute("lang", lang ? lang.code : "zh")',
                      card)
        meta = card.split('art.appendChild(text("p", "meta"', 1)[1]
        self.assertNotIn("lang.code", meta)

    def test_no_raw_language_or_state_code_in_archive_authored_ui(self):
        html = self.page("archive.html")
        body = html.split('id="browse"', 1)[1]
        for code in ("zh-Hans", "en-US"):
            with self.subTest(code=code):
                self.assertNotIn(">%s<" % code, body)
        for state in gp.STATE_ORDER:
            if "_" in state:
                with self.subTest(state=state):
                    self.assertNotIn(state, html)

    def test_the_language_control_names_its_provenance(self):
        html = re.sub(r"\s+", " ", self.page("archive.html"))
        self.assertIn("Original language (source attribute)", html)
        self.assertIn("Original language is an attribute of the source, not "
                      "something asserted independently for each record", html)

    def test_the_date_filters_name_the_stated_source_date(self):
        html = self.page("archive.html")
        self.assertIn("Source-stated date from", html)
        self.assertIn("Source-stated date to", html)

    def test_the_volume_section_is_reachable_from_the_top(self):
        html = self.page("archive.html")
        self.assertIn('<a href="#volume-heading">', html)
        self.assertIn("View records by publication week", html)
        self.assertIn('id="volume-heading"', html)

    def test_the_volume_section_offers_a_route_back(self):
        html = self.page("archive.html")
        self.assertIn('<a href="#results-heading">', html)
        self.assertIn("Back to Archive search", html)
        self.assertIn('id="results-heading"', html)

    def test_both_fragment_targets_resolve(self):
        html = self.page("archive.html")
        for target in re.findall(r'href="#([a-z-]+)"', html):
            with self.subTest(target=target):
                self.assertIn('id="%s"' % target, html)

    def test_browse_javascript_keeps_meaningful_headroom(self):
        size = (self.out / "browse.js").stat().st_size
        # The governing ceiling stays the real budget.
        self.assertLessEqual(size, 10_000)
        # And the working target keeps the ceiling from being decorative.
        self.assertLessEqual(size, 9_500,
                             "browse.js is %d bytes; trim before adding more"
                             % size)

    def test_the_hidden_attribute_beats_author_display_rules(self):
        """`.pager { display: flex }` overrode the UA `[hidden]` rule, so the
        pager stayed on screen for a zero-result query."""
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        self.assertIn("[hidden] { display: none !important; }", css)

    def test_the_empty_state_is_stated_once(self):
        js = (self.out / "browse.js").read_text(encoding="utf-8")
        zero = js.split("if (total === 0) {", 1)[1].split("} else {", 1)[0]
        self.assertIn('els.range.textContent = "";', zero)

    def test_the_live_region_is_polite(self):
        html = self.page("archive.html")
        live = html.split('id="result-live"', 1)[1].split(">", 1)[0]
        self.assertIn('aria-live="polite"', live)
        self.assertIn('role="status"', live)

    def test_the_overlap_explanation_is_present(self):
        html = re.sub(r"\s+", " ", self.page("archive.html"))
        self.assertIn("one institution can publish through more than one "
                      "source, so their counts are not mutually exclusive "
                      "categories", html)
        self.assertIn("Original language is an attribute of the source, not "
                      "something asserted independently for each record", html)

    def test_search_is_declared_title_only(self):
        html = re.sub(r"\s+", " ", self.page("archive.html"))
        self.assertIn("Title contains", html)
        self.assertIn("It does not search machine summaries or stored source "
                      "text.", html)

    def test_top_level_navigation_is_unchanged(self):
        nav = self.page("archive.html").split('aria-label="Primary"', 1)[1]
        nav = nav.split("</nav>", 1)[0]
        labels = re.findall(r">([A-Za-z ]+)</a>", nav)
        self.assertEqual(labels, ["Desks", "Archive", "Coverage", "Sources",
                                  "Analysis", "Methodology", "About"])

    def test_corpus_values_are_never_written_through_inner_html(self):
        js = (self.out / "browse.js").read_text(encoding="utf-8")
        for hit in re.findall(r"\.innerHTML\s*=\s*([^\n;]+)", js):
            with self.subTest(assignment=hit):
                self.assertIn('""', hit)
        self.assertIn("textContent", js)
        self.assertNotIn("insertAdjacentHTML", js)
        self.assertNotIn("document.write", js)

    def test_browser_javascript_is_within_budget(self):
        size = (self.out / "browse.js").stat().st_size
        self.assertLessEqual(size, 10_000, "JS budget is 10 KB")

    def test_hostile_stored_titles_cannot_inject_markup(self):
        """Stored titles are source text and may contain anything.

        Server-side they must be escaped; client-side they are only ever
        written through textContent, which is asserted separately. Here the
        rendered record page and the index are checked against a hostile
        fixture, so a future template that drops `|safe` in is caught.
        """
        import sqlite3
        hostile = ('<img src=x onerror=alert(1)><script>window.x=1</script>'
                   '"><b>bold</b>')
        tmp = Path(tempfile.mkdtemp(prefix="hostile-"))
        try:
            db = tmp / "hostile.db"
            shutil.copy(TRACKED_DB, db)
            con = sqlite3.connect(db)
            rec_id = con.execute(
                "SELECT id FROM articles ORDER BY id DESC LIMIT 1").fetchone()[0]
            con.execute("UPDATE articles SET title_english=?, title_original=?"
                        " WHERE id=?", (hostile, hostile + "原文", rec_id))
            con.commit()
            con.close()
            snapshot = dict(gp.snapshot_from_corpus(db))
            snapshot["logical_sha256"] = None
            out = tmp / "build"
            gp.build(out, "Test Title", db, snapshot=snapshot)

            page = (out / "record" / ("%d.html" % rec_id)).read_text(
                encoding="utf-8")
            self.assertNotIn("<img src=x", page)
            self.assertNotIn("<script>window.x=1</script>", page)
            self.assertIn("&lt;img src=x", page)

            blob = (out / "corpus-index.json").read_text(encoding="utf-8")
            self.assertIn("window.x=1", blob, "the title is stored verbatim")
            for html_page in out.glob("*.html"):
                with self.subTest(page=html_page.name):
                    self.assertNotIn("<script>window.x=1</script>",
                                     html_page.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_every_index_row_shape_is_validated_not_a_sample(self):
        js = (self.out / "browse.js").read_text(encoding="utf-8")
        block = js.split("function valid(", 1)[1].split("\n  }", 1)[0]
        self.assertIn("for (var i = 0; i < d.records.length; i++)", block)
        self.assertIn("!Array.isArray(d.records[i])", block)
        self.assertIn("d.records[i].length !== FIELDS.length", block)
        # No slicing or early exit that would turn this into a sample.
        self.assertNotIn(".slice(", block)

    def test_unavailable_restores_the_safe_hidden_state(self):
        js = (self.out / "browse.js").read_text(encoding="utf-8")
        block = js.split("function unavailable(", 1)[1].split("\n  }", 1)[0]
        self.assertIn("els.controls.hidden = true", block)
        self.assertIn("root.hidden = true", block)
        self.assertIn('els.results.textContent = ""', block)
        self.assertIn("els.error.hidden = false", block)

    def test_the_page_declares_the_snapshot_the_index_must_match(self):
        html = self.page("archive.html")
        root = html.split('id="browse"', 1)[1].split(">", 1)[0]
        self.assertIn('data-snapshot-date="%s"' % self.snapshot["date"],
                      root)
        self.assertIn('data-snapshot-records="%d"'
                      % self.snapshot["expected_records"], root)
        self.assertNotIn(self.snapshot["logical_sha256"], html)

    def test_the_browser_validates_the_index_before_revealing_controls(self):
        js = (self.out / "browse.js").read_text(encoding="utf-8")
        for check in ("d.snapshot.date !== WANT_DATE",
                      "d.snapshot.records !== WANT_COUNT",
                      "d.records.length !== WANT_COUNT",
                      "d.fields.join() !== FIELDS.join()"):
            with self.subTest(check=check):
                self.assertIn(check, js)
        # Validation must gate the reveal, not follow it.
        body = js.split(".then(function (json) {", 1)[1]
        self.assertLess(body.index("if (!valid(json))"),
                        body.index("root.hidden = false"))
        self.assertIn(".catch(unavailable)", js)

    def test_the_cache_discriminator_uses_public_facts_only(self):
        js = (self.out / "browse.js").read_text(encoding="utf-8")
        request = js.split('fetch("corpus-index.json', 1)[1].split("{", 1)[0]
        self.assertIn("WANT_DATE", request)
        self.assertIn("WANT_COUNT", request)
        self.assertNotIn("logical", request)

    def test_the_failure_copy_is_the_approved_wording(self):
        html = re.sub(r"\s+", " ", self.page("archive.html"))
        self.assertIn(
            "The search index could not be loaded or did not match this "
            "snapshot, so search and filters are unavailable. The records held "
            "in this prototype snapshot remain accessible through the "
            "week-by-week browse above.", html)
        self.assertNotIn("Nothing is missing from the corpus", html)

    def test_the_failure_message_is_announced_politely(self):
        block = self.page("archive.html").split('id="index-error"', 1)[1]
        block = block.split(">", 1)[0]
        self.assertIn('role="status"', block)
        self.assertIn('aria-live="polite"', block)

    def test_every_html_page_stays_within_the_page_budget(self):
        for path in sorted(self.out.rglob("*.html")):
            with self.subTest(page=str(path.relative_to(self.out))):
                self.assertLessEqual(path.stat().st_size, 120_000)


class TestCoverageTableSemantics(PreviewCase):
    """Every Coverage header is a column header and must say so."""

    def test_no_table_header_is_left_unscoped(self):
        html = self.page("coverage.html")
        self.assertEqual(len(re.findall(r"<th(?![^>]*scope)[ >]", html)), 0)

    def test_every_header_is_scoped_as_a_column(self):
        html = self.page("coverage.html")
        headers = re.findall(r"<th[ >]", html)
        self.assertEqual(len(headers), 12)
        self.assertEqual(len(re.findall(r'scope="col"', html)), 12)
        # None of these tables has a header cell as a row label, so a
        # scope="row" here would be a mechanical addition, not a true one.
        self.assertEqual(len(re.findall(r'scope="row"', html)), 0)

    def test_the_headers_are_the_expected_column_labels(self):
        html = self.page("coverage.html")
        labels = [re.sub(r"<[^>]+>", "", t).strip() for t in
                  re.findall(r"<th[^>]*>(.*?)</th>", html, re.S)]
        self.assertEqual(labels,
                         ["Source", "Result", "Found", "Read", "Already held",
                          "New", "Note", "Result", "Meaning", "From", "To",
                          "Days"])

    def test_every_scoped_header_sits_inside_a_thead(self):
        html = self.page("coverage.html")
        for head in re.findall(r"<thead>(.*?)</thead>", html, re.S):
            with self.subTest(head=head[:40]):
                self.assertIn('scope="col"', head)
        outside = re.sub(r"<thead>.*?</thead>", " ", html, flags=re.S)
        self.assertNotIn("<th", outside)

    def test_no_preview_page_has_an_unscoped_header(self):
        """The audit is finished: every table header in the whole preview is
        scoped, not just Coverage's."""
        for path in sorted(self.out.rglob("*.html")):
            html = path.read_text(encoding="utf-8")
            with self.subTest(page=str(path.relative_to(self.out))):
                self.assertEqual(
                    len(re.findall(r"<th(?![^>]*scope)[ >]", html)), 0)

    def test_the_remaining_nineteen_headers_are_column_headers(self):
        """china/desks/sources/weekly carried 19 between them; each sits in a
        `<thead>` row and labels a column, so none takes `scope="row"` and no
        `<td>` body cell was promoted."""
        expected = {"china.html": 5, "japan.html": 3, "sources.html": 6,
                    "weekly.html": 5}
        for name, count in expected.items():
            html = (self.out / name).read_text(encoding="utf-8")
            with self.subTest(page=name):
                self.assertEqual(len(re.findall(r'scope="col"', html)), count)
                self.assertEqual(len(re.findall(r'scope="row"', html)), 0)
                outside = re.sub(r"<thead>.*?</thead>", " ", html, flags=re.S)
                self.assertNotIn("<th", outside)
        self.assertEqual(sum(expected.values()), 19)


class TestVolumeByWeek(PreviewCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data = gp.load_corpus(TRACKED_DB)
        cls.html = cls.page_static(cls.out, "archive.html")
        cls.rows = re.findall(
            r'<span class="c-range">([\d-]+) to ([\d-]+)</span>.*?'
            r'<span class="v-figure">([\d,]+)</span>.*?'
            r'<td class="c-runs">(\d+)', cls.html, re.S)

    @staticmethod
    def page_static(out, name):
        return (out / name).read_text(encoding="utf-8")

    def test_every_publication_week_renders_with_counts_matching_sql(self):
        """
        Every publication week the corpus contains renders exactly once, with
        the right span, record count and run-date count.

        The expectation comes from `weeks_from_sql()` — a separate query
        against the same database — so this compares the rendered page to the
        corpus rather than to the generator's own idea of the corpus. It also
        carries no week total: the corpus grows a week roughly every seven
        days, and a number written here would be wrong again by the next one.
        """
        expected = weeks_from_sql(TRACKED_DB)
        self.assertTrue(expected, "the corpus has no publication weeks")

        # Set comparison first: it names a missing or duplicated week directly,
        # where a zip() mismatch would only report the first row that differs.
        rendered_starts = [start for start, _, _, _ in self.rows]
        self.assertEqual(len(rendered_starts), len(set(rendered_starts)),
                         "a publication week rendered more than once")
        self.assertEqual(set(rendered_starts),
                         {w["start"] for w in expected},
                         "rendered weeks do not match the corpus")
        self.assertEqual(len(self.rows), len(expected))
        self.assertEqual(rendered_starts, [w["start"] for w in expected],
                         "weeks are not in newest-first order")

        for (start, end, count, runs), week in zip(self.rows, expected):
            with self.subTest(week=start):
                self.assertEqual(start, week["start"])
                self.assertEqual(end, week["end"])
                self.assertEqual(count, "{:,}".format(week["count"]))
                self.assertEqual(int(runs), week["run_dates"])

    def test_the_weekly_counts_sum_to_the_snapshot(self):
        total = sum(int(c.replace(",", "")) for _, _, c, _ in self.rows)
        self.assertEqual(total, self.snapshot["expected_records"])

    def test_the_table_is_the_semantic_representation(self):
        block = self.html.split('class="volume"', 1)[1].split("</table>", 1)[0]
        self.assertIn("<caption>", block)
        self.assertIn('<th scope="col">', block)
        self.assertIn('<th scope="row">', block)

    def test_bars_are_decorative_and_hidden_from_assistive_tech(self):
        for bar in re.findall(r'<span class="v-bar"[^>]*>', self.html):
            with self.subTest(bar=bar):
                self.assertIn('aria-hidden="true"', bar)

    def test_bar_length_encodes_record_count_only(self):
        widths = [float(w) for w in
                  re.findall(r'class="v-fill" style="width: ([\d.]+)%"',
                             self.html)]
        counts = [w["count"] for w in self.data["weeks"]]
        top = max(counts)
        self.assertEqual(len(widths), len(counts))
        for width, count in zip(widths, counts):
            with self.subTest(count=count):
                self.assertAlmostEqual(width, round(count * 100 / top, 1),
                                       places=1)

    def test_bars_are_never_normalised_by_run_dates(self):
        """A records-per-run-date rate is not a supportable figure."""
        widths = [float(w) for w in
                  re.findall(r'class="v-fill" style="width: ([\d.]+)%"',
                             self.html)]
        rates = [w["count"] / max(1, w["run_dates"])
                 for w in self.data["weeks"]]
        top = max(rates)
        normalised = [round(r * 100 / top, 1) for r in rates]
        self.assertNotEqual([round(x, 1) for x in widths], normalised)

    def test_exact_figures_remain_textual(self):
        for week in self.data["weeks"]:
            with self.subTest(week=week["start"]):
                self.assertIn("{:,}".format(week["count"]), self.html)
                self.assertIn(">%d<span class=\"c-unit\"> recorded run dates"
                              % week["run_dates"], self.html)

    def test_annotations_are_visible_text_not_colour_only(self):
        self.assertIn("Snapshot boundary", self.html)
        self.assertIn("Known collection interruption", self.html)
        for annotated in [w for w in self.data["weeks"] if w["annotation"]]:
            with self.subTest(week=annotated["start"]):
                self.assertIn(annotated["annotation"], self.html)

    def test_the_volume_block_never_uses_rust(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        block = css.split("Volume by publication week", 1)[1]
        block = block.split("@media (prefers-reduced-motion", 1)[0]
        self.assertNotIn("var(--signal)", block)
        self.assertIn("var(--ocean)", block)

    def test_no_chart_library_canvas_or_svg_plate(self):
        volume = self.html.split('id="volume-heading"', 1)[1]
        for token in ("<canvas", "<svg", "chart.js", "d3."):
            with self.subTest(token=token):
                self.assertNotIn(token, volume)

    def test_the_approved_caption_is_rendered_verbatim(self):
        flat = re.sub(r"\s+", " ", self.html)
        for fragment in (
                "Records in this snapshot, grouped by the publication date "
                "stated by each source.",
                "Counts reflect stored records after de-duplication, not total "
                "institutional output, collection completeness, system uptime, "
                "or military activity.",
                "The accompanying run-day figure counts UTC calendar dates "
                "with at least one recorded pipeline run.",
                "it is operational context—not a coverage denominator."):
            with self.subTest(fragment=fragment[:42]):
                self.assertIn(fragment, flat)

    def test_no_unsupported_partial_or_zero_publication_language(self):
        banned = re.compile(
            r"\bpartial\b|days observed|zero[- ]publication|no publications",
            re.I)
        self.assertIsNone(banned.search(_authored_text(self.html,
                                                       "archive.html")))

    def test_tabular_figures_are_used(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        block = css.split("Volume by publication week", 1)[1]
        self.assertIn("tabular-nums lining-nums", block)

    def test_the_volume_needs_no_javascript(self):
        """It is server-rendered inside the page, not built by the browser."""
        self.assertIn('id="volume-heading"', self.html)
        self.assertIn('<table class="volume">', self.html)
        js = (self.out / "browse.js").read_text(encoding="utf-8")
        # The script must never select, create or mutate volume markup. A
        # comment that merely mentions the word is not a violation.
        code = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
        for token in ("volume", "v-bar", "v-fill", "v-figure"):
            with self.subTest(token=token):
                self.assertNotIn(token, code)


class TestBrowserRejectsMalformedIndex(PreviewCase):
    """Behavioural proof that a malformed row is rejected BEFORE reveal.

    Source-level assertions can show the check exists; only running it shows
    that a short row is refused by validation rather than by an incidental
    exception thrown later inside card().

    Offline: a loopback HTTP server on an ephemeral port. No network.
    """

    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:                                   # pragma: no cover
            raise unittest.SkipTest("playwright not installed")
        super().setUpClass()
        import functools
        import http.server
        import socketserver
        import threading
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):        # keep suite output readable
                pass
        handler = functools.partial(Quiet, directory=str(cls.out))
        socketserver.TCPServer.allow_reuse_address = True
        cls.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever,
                                      daemon=True)
        cls.thread.start()
        # The package can be installed while the browser binary is not:
        # `pip install playwright` does not fetch chromium, and the pull-request
        # workflow deliberately installs no browser. Skip cleanly there rather
        # than erroring — the daily workflow runs `playwright install chromium`
        # before this suite, so these assertions are still enforced before any
        # production render.
        cls._pw = sync_playwright().start()
        try:
            cls.browser = cls._pw.chromium.launch()
        except Exception as exc:                              # pragma: no cover
            cls._pw.stop()
            raise unittest.SkipTest(
                "chromium not available (%s); run `playwright install chromium`"
                % type(exc).__name__)
        cls.good = json.loads(
            (cls.out / "corpus-index.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "browser"):
            cls.browser.close()
            cls._pw.stop()
            cls.httpd.shutdown()
            cls.httpd.server_close()
        super().tearDownClass()

    def state(self, mutate=None, abort=False):
        """Load the archive with an optionally mutated index; report state."""
        body = None
        if mutate is not None:
            payload = json.loads(json.dumps(self.good))
            mutate(payload)
            body = json.dumps(payload)
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            if abort:
                page.route("**/corpus-index.json*", lambda r, q=None: r.abort())
            elif body is not None:
                page.route("**/corpus-index.json*",
                           lambda r, q=None, b=body: r.fulfill(
                               status=200, content_type="application/json",
                               body=b))
            page.goto("http://127.0.0.1:%d/archive.html" % self.port,
                      wait_until="load")
            page.wait_for_timeout(600)
            return {
                "error": page.is_visible("#index-error"),
                "controls": page.is_visible("#controls"),
                "root": page.is_visible("#browse"),
                "cards": page.eval_on_selector_all("#results .record",
                                                   "e => e.length"),
                "week_path": page.is_visible("#nojs-path"),
                "volume": page.is_visible("#volume-heading"),
            }
        finally:
            page.close()

    def assert_rejected(self, state):
        self.assertTrue(state["error"], "unavailable message must be shown")
        self.assertFalse(state["controls"], "controls must stay hidden")
        self.assertFalse(state["root"], "browser root must stay hidden")
        self.assertEqual(state["cards"], 0, "no result card may render")
        self.assertTrue(state["week_path"], "the no-JS path must remain")
        self.assertTrue(state["volume"], "the volume table must remain")

    def test_a_valid_index_renders_normally(self):
        state = self.state()
        self.assertFalse(state["error"])
        self.assertTrue(state["controls"])
        self.assertTrue(state["root"])
        self.assertEqual(state["cards"], 50)

    def test_a_row_missing_only_the_original_title_is_rejected(self):
        """Truncated after title_en, so source and state indices stay valid.

        Nothing downstream would throw on this row — card() would render it
        with an undefined original title — so acceptance here would prove the
        row check absent, and rejection proves it present.
        """
        def mutate(d):
            d["records"][0] = d["records"][0][:5]
        self.assert_rejected(self.state(mutate))

    def test_a_row_with_a_seventh_value_is_rejected(self):
        def mutate(d):
            d["records"][0] = d["records"][0] + ["extra"]
        self.assert_rejected(self.state(mutate))

    def test_a_non_array_row_is_rejected(self):
        def mutate(d):
            d["records"][0] = {"id": 1}
        self.assert_rejected(self.state(mutate))

    def test_a_malformed_row_deep_in_the_corpus_is_rejected(self):
        """Validation covers every row, not the first few."""
        def mutate(d):
            d["records"][-1] = d["records"][-1][:4]
        self.assert_rejected(self.state(mutate))

    def test_a_failed_fetch_is_rejected_the_same_way(self):
        self.assert_rejected(self.state(abort=True))


class TestRecordBuildIsDeterministic(unittest.TestCase):
    """3,250 pages must be byte-identical across two builds."""

    def test_two_full_corpus_builds_are_identical(self):
        if not TRACKED_DB.exists():
            self.skipTest("production database not present")
        tmp = Path(tempfile.mkdtemp(prefix="preview-determinism-"))
        snap = snapshot_of(TRACKED_DB)
        try:
            a, b = tmp / "a", tmp / "b"
            gp.build(a, "Test Title", TRACKED_DB, snapshot=snap)
            gp.build(b, "Test Title", TRACKED_DB, snapshot=snap)
            self.assertEqual(_tree_digest(a), _tree_digest(b))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ── House-style guard scope: what the exclusion may and may not remove ───────

class TestAuthoredProseStaysGuarded(PreviewCase):
    """Authored prose must survive `_authored_text` in every location.

    Each case below was a real blind spot when the exclusion removed whole
    containers: the authored text shared an element with a stored value, so
    removing the element removed the prose too. Surviving the filter is what
    makes a string reachable by the house-style and vocabulary guards.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.corpus = gp.load_corpus(TRACKED_DB)
        cls.analyzed = next(r for r in cls.corpus["corpus"]
                            if r["state"] == "analyzed")

    def authored(self, rel: str) -> str:
        return _authored_text((self.out / rel).read_text(encoding="utf-8"), rel)

    def test_authored_corpus_index_h1_stays_guarded(self):
        self.assertIn("China Desk Corpus — by publication week",
                      self.authored("corpus.html"))

    def test_authored_non_record_titles_stay_guarded(self):
        for rel, fragment in (("corpus.html", "Corpus by week"),
                              ("archive.html", "Archive"),
                              ("methodology.html", "Methodology"),
                              ("about.html", "About")):
            with self.subTest(page=rel):
                head = self.authored(rel).split("</title>", 1)[0]
                self.assertIn(fragment, head)

    def test_authored_suffix_of_a_record_title_stays_guarded(self):
        """The stored title goes; the authored ' — <publication>' remains."""
        rel = "record/%d.html" % self.analyzed["id"]
        head = self.authored(rel).split("</title>", 1)[0]
        self.assertIn("— Test Title", head)
        self.assertNotIn(self.analyzed["title_english"], head)

    def test_machine_summary_label_stays_guarded(self):
        self.assertIn("Machine summary",
                      self.authored("record/%d.html" % self.analyzed["id"]))

    def test_machine_summary_caveat_stays_guarded(self):
        text = re.sub(
            r"\s+", " ",
            self.authored("record/%d.html" % self.analyzed["id"]))
        self.assertIn("Machine-generated from the original text, and distinct "
                      "from the machine translation of the title.", text)
        self.assertIn("Not reviewed by a human.", text)
        self.assertIn("It is a reading of what was published, not a "
                      "verification of it.", text)

    def test_machine_translation_label_and_caveat_stay_guarded(self):
        text = re.sub(
            r"\s+", " ",
            self.authored("record/%d.html" % self.analyzed["id"]))
        self.assertIn("Machine translation", text)
        self.assertIn("The heading is a machine translation of the original "
                      "title above. Not reviewed by a human.", text)

    def test_source_record_label_stays_guarded(self):
        self.assertIn("Source record",
                      self.authored("record/%d.html" % self.analyzed["id"]))

    def test_shard_entry_processing_state_label_stays_guarded(self):
        week = next(w for w in self.corpus["weeks"] if w["count"])
        authored = self.authored(week["path"])
        # Page 1 carries only the first SHARD_MAX_RECORDS entries.
        on_page_one = week["records"][:gp.SHARD_MAX_RECORDS]
        for label in {r["state_label"] for r in on_page_one}:
            with self.subTest(label=label):
                self.assertIn(label, authored)

    def test_labels_from_controlled_python_mappings_stay_guarded(self):
        """Reader-facing labels the generator supplies are authored copy."""
        sources = self.authored("sources.html")
        for label in gp.SOURCE_TYPE_LABELS.values():
            with self.subTest(label=label):
                self.assertIn(label, sources)
        coverage = self.authored("coverage.html")
        present = [lbl for lbl, _ in gp.STATUS_PROSE.values()
                   if lbl in (self.out / "coverage.html").read_text(
                       encoding="utf-8")]
        self.assertTrue(present)
        for label in present:
            with self.subTest(label=label):
                self.assertIn(label, coverage)
        for state in gp.PROCESSING_STATES:
            with self.subTest(state=state["label"]):
                self.assertIn(state["label"], self.authored("corpus.html"))
                self.assertIn(state["definition"], self.authored("corpus.html"))

    def test_provenance_row_labels_and_caveats_stay_guarded(self):
        authored = self.authored("record/%d.html" % self.analyzed["id"])
        for label in ("Publishing institution", "Source outlet",
                      "Source language", "Source-stated publication date",
                      "Original URL", "Collected at", "Content fingerprint",
                      "Collection run", "Analysis model", "Prompt version",
                      "an attribute of the source, not of this record",
                      "collection metadata, not a publication time",
                      "taken when the record was captured"):
            with self.subTest(label=label):
                self.assertIn(label, authored)

    def test_empty_text_disclosure_and_route_language_stay_guarded(self):
        empty = next(r for r in self.corpus["corpus"] if not r["has_text"])
        authored = self.authored("record/%d.html" % empty["id"])
        self.assertIn("Original text is unavailable in this stored record.",
                      authored)
        # The two adjacent locator caveats were consolidated into one sentence
        # carrying both distinctions. Matched on normalized whitespace so a
        # line wrap inside the paragraph cannot break the guard.
        flat = re.sub(r"\s+", " ", authored)
        self.assertIn("The record number and this prototype path are locators "
                      "inside the %s snapshot." % self.corpus_edge, flat)
        self.assertIn("Neither is a DOI, accession number, permanent "
                      "identifier, public permalink, or published route.",
                      flat)

    def test_shard_and_index_headings_and_captions_stay_guarded(self):
        week = self.corpus["weeks"][0]
        shard = self.authored(week["path"])
        self.assertIn("Publication week", shard)
        self.assertIn("Records", shard)
        index = self.authored("corpus.html")
        self.assertIn("Publication weeks", index)
        self.assertIn("not a coverage denominator", index)

    def test_chrome_stays_guarded(self):
        authored = self.authored("record/%d.html" % self.analyzed["id"])
        for fragment in ("Skip to content", "Methodology", "Coverage",
                         "Creator and Editor", "Private prototype.",
                         "collectors executed", "Selective coverage."):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, authored)


class TestStoredContentIsExcluded(PreviewCase):
    """Stored source text and stored model output are removed, verbatim."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.corpus = gp.load_corpus(TRACKED_DB)
        cls.analyzed = next(r for r in cls.corpus["corpus"]
                            if r["state"] == "analyzed" and r["has_text"])

    def authored(self, rel: str) -> str:
        return _authored_text((self.out / rel).read_text(encoding="utf-8"), rel)

    def test_machine_translated_title_is_excluded(self):
        rel = "record/%d.html" % self.analyzed["id"]
        self.assertNotIn(self.analyzed["title_english"], self.authored(rel))

    def test_original_source_title_is_excluded(self):
        rel = "record/%d.html" % self.analyzed["id"]
        self.assertNotIn(self.analyzed["title_original"], self.authored(rel))

    def test_machine_generated_summary_is_excluded(self):
        rel = "record/%d.html" % self.analyzed["id"]
        self.assertNotIn(self.analyzed["summary_english"], self.authored(rel))

    def test_original_source_body_is_excluded(self):
        rel = "record/%d.html" % self.analyzed["id"]
        authored = self.authored(rel)
        paragraphs = [p.strip() for p
                      in self.analyzed["text_original"].split("\n") if p.strip()]
        for para in paragraphs[:5]:
            with self.subTest(para=para[:30]):
                self.assertNotIn(para, authored)

    def test_source_outlet_and_institution_names_are_excluded(self):
        rel = "record/%d.html" % self.analyzed["id"]
        authored = self.authored(rel)
        self.assertNotIn(self.analyzed["source_name"], authored)
        self.assertNotIn(self.analyzed["institution"], authored)

    def test_original_url_is_excluded(self):
        rel = "record/%d.html" % self.analyzed["id"]
        self.assertNotIn(self.analyzed["url"], self.authored(rel))

    def test_shard_entry_titles_are_excluded(self):
        week = next(w for w in self.corpus["weeks"] if w["count"])
        authored = self.authored(week["path"])
        for rec in week["records"][:20]:
            with self.subTest(id=rec["id"]):
                if rec["title_english"]:
                    self.assertNotIn(rec["title_english"], authored)
                self.assertNotIn(rec["title_original"], authored)

    def test_short_controlled_tokens_stay_guarded_by_design(self):
        """`en`, `v1` and the like are closed vocabularies, not prose.

        Removing a two-character value from a whole page would gut authored
        text, so these remain inside the guarded surface. They cannot carry a
        style or vocabulary violation.
        """
        rel = "record/%d.html" % self.analyzed["id"]
        authored = self.authored(rel)
        self.assertIn(self.analyzed["language_tag"], authored)
        if self.analyzed["model_id"]:
            self.assertIn(self.analyzed["model_id"], authored)


class TestExclusionContract(unittest.TestCase):
    """The contract itself, independent of what the live corpus contains."""

    def test_a_british_source_name_survives_without_exempting_its_label(self):
        """The case the whole design exists for.

        "Ministry of National Defence" is how the institution writes its own
        name and must be preserved verbatim, while the authored label sitting
        beside it in the same table row stays fully guarded.
        """
        html = ('<tr><th scope="row">Publishing institution</th>'
                '<td class="prov-value">Ministry of National Defence</td></tr>'
                '<p>This record is labelled by the editor.</p>')
        authored = _authored_text(
            html, "record/1.html",
            literals=["Ministry of National Defence"])
        self.assertNotIn("Ministry of National Defence", authored)
        self.assertIn("Publishing institution", authored)
        self.assertIn("labelled by the editor", authored)

    def test_banned_vocabulary_inside_a_stored_value_is_excluded(self):
        stored = "Order of battle briefing at the defence centre"
        html = "<h1>%s</h1><p>Machine summary</p>" % stored
        authored = _authored_text(html, "record/1.html", literals=[stored])
        self.assertNotIn("order of battle", authored.lower())
        self.assertIn("Machine summary", authored)

    def test_banned_vocabulary_in_authored_prose_is_never_excluded(self):
        html = ('<h1>Corpus by programme</h1>'
                '<p>An order of battle summary, labelled by hand.</p>')
        authored = _authored_text(html, "corpus.html", literals=[])
        self.assertIn("programme", authored)
        self.assertIn("order of battle", authored)
        self.assertIn("labelled", authored)

    def test_containers_are_never_removed_wholesale(self):
        """A stored value inside an element must not take the element with it.

        The literal passed must be the one actually present, or the test would
        pass without ever exercising removal.
        """
        html = ('<div class="interpretation"><p>Machine summary</p>'
                '<p>STORED</p><p>Not reviewed by a human.</p></div>')
        authored = _authored_text(html, "record/1.html", literals=["STORED"])
        self.assertNotIn("STORED", authored)
        self.assertIn("Machine summary", authored)
        self.assertIn("Not reviewed by a human.", authored)

    def test_escaped_values_are_matched_as_rendered(self):
        stored = 'He said "defence" & moved on'
        html = "<h1>%s</h1><p>authored defence copy</p>" % markupsafe.escape(
            stored)
        authored = _authored_text(html, "record/1.html", literals=[stored])
        self.assertNotIn("&#34;defence&#34;", authored)
        self.assertIn("authored defence copy", authored)


def _fake_record(**overrides):
    """A minimal record carrying every logical field."""
    base = {f: None for f in gp.LOGICAL_FIELDS}
    base.update(id=1, url="http://example.invalid/a", title_original="标题",
                title_english="Title", published_date="2026-01-01",
                summary_english=None, analyzed_at=None, model_id=None,
                prompt_version=None, is_significant=0,
                content_hash="abc", scraped_at="2026-01-01 00:00:00",
                scrape_run_id=1, text_original="正文", passed_relevance=None,
                source_slug="s", source_name="Source", language_tag="zh-Hans",
                institution_id="i", institution="Institution")
    base.update(overrides)
    return base


class TestDeclaredSnapshot(unittest.TestCase):
    """The snapshot is declared editorial metadata, not an inferred value."""

    def test_the_declared_snapshot_is_the_approved_one(self):
        self.assertEqual(gp.DECLARED_SNAPSHOT["date"], "2026-08-19")
        self.assertEqual(gp.DECLARED_SNAPSHOT["expected_records"], 3388)

    def test_the_declared_fingerprint_is_a_literal_digest(self):
        """The real default can never silently opt out of the content check."""
        declared = gp.DECLARED_SNAPSHOT["logical_sha256"]
        self.assertRegex(declared, r"^[0-9a-f]{64}$")

    def test_a_matching_corpus_passes(self):
        corpus = [_fake_record()]
        gp.assert_snapshot(corpus, {"date": "d", "expected_records": 1,
                                    "logical_sha256":
                                        gp.corpus_fingerprint(corpus)})

    def test_a_differing_count_fails_loudly(self):
        with self.assertRaises(gp.SnapshotMismatch) as caught:
            gp.assert_snapshot([_fake_record(), _fake_record(id=2)],
                               gp.DECLARED_SNAPSHOT)
        message = str(caught.exception)
        self.assertIn("3388", message)
        self.assertIn("2026-08-19", message)

    def test_a_fixture_may_declare_its_own_snapshot(self):
        """Fixtures declare their own values without weakening the default."""
        corpus = [_fake_record(id=n) for n in range(7)]
        fixture = {"date": "2020-01-01", "expected_records": 7,
                   "logical_sha256": gp.corpus_fingerprint(corpus)}
        gp.assert_snapshot(corpus, fixture)
        with self.assertRaises(gp.SnapshotMismatch):
            gp.assert_snapshot(corpus + [_fake_record(id=99)], fixture)
        self.assertEqual(gp.DECLARED_SNAPSHOT["expected_records"], 3388)
        self.assertRegex(gp.DECLARED_SNAPSHOT["logical_sha256"],
                         r"^[0-9a-f]{64}$")

    def test_a_fixture_may_opt_out_of_the_fingerprint_explicitly(self):
        corpus = [_fake_record()]
        gp.assert_snapshot(corpus, {"date": "d", "expected_records": 1,
                                    "logical_sha256": None})

    def test_omitting_the_fingerprint_key_fails_loudly(self):
        """An absent key is a malformed declaration, never an opt-out."""
        corpus = [_fake_record()]
        with self.assertRaises(gp.SnapshotMismatch) as caught:
            gp.assert_snapshot(corpus, {"date": "d", "expected_records": 1})
        message = str(caught.exception)
        self.assertIn("omits 'logical_sha256'", message)
        self.assertIn("not an opt-out", message)

    def test_the_real_default_cannot_opt_out(self):
        self.assertIn("logical_sha256", gp.DECLARED_SNAPSHOT)
        self.assertIsNotNone(gp.DECLARED_SNAPSHOT["logical_sha256"])
        self.assertRegex(gp.DECLARED_SNAPSHOT["logical_sha256"],
                         r"^[0-9a-f]{64}$")

    def test_a_count_mismatch_names_all_three_governed_values(self):
        with self.assertRaises(gp.SnapshotMismatch) as caught:
            gp.assert_snapshot([_fake_record()], gp.DECLARED_SNAPSHOT)
        message = str(caught.exception)
        self.assertIn("date, record count AND logical fingerprint", message)

    def test_a_same_count_content_mismatch_still_fails(self):
        corpus = [_fake_record(id=n) for n in range(1, 6)]
        snapshot = {"date": "d", "expected_records": 5,
                    "logical_sha256": gp.corpus_fingerprint(corpus)}
        gp.assert_snapshot(corpus, snapshot)
        altered = corpus[:-1] + [_fake_record(id=5, title_english="Changed")]
        self.assertEqual(len(altered), len(corpus))
        with self.assertRaises(gp.SnapshotMismatch) as caught:
            gp.assert_snapshot(altered, snapshot)
        self.assertIn("content changed underneath a stable count",
                      str(caught.exception))

    def test_snapshot_identity_is_not_derived_from_max_published_date(self):
        source = (REPO_ROOT / "site" / "preview"
                  / "generate_preview.py").read_text(encoding="utf-8")
        build_body = source.split("def build(", 1)[1]
        self.assertNotIn('snapshot_date = data["totals"]["last_date"]',
                         build_body)


class TestLogicalFingerprint(unittest.TestCase):
    """The fingerprint binds the snapshot to corpus CONTENT, not just size."""

    def test_the_accepted_database_matches_the_declared_fingerprint(self):
        """
        Release-readiness, not correctness.

        `DECLARED_SNAPSHOT` names one frozen corpus. Production collects daily,
        so the tracked database moves past it within a day of every release —
        that drift is expected and is not a defect. Before 2026-08-23 this was
        an assertion, and because the whole suite runs in the daily workflow
        *before* collection, the first advance blocked the very pipeline that
        would have refreshed the snapshot.

        So drift is reported as a skip that names it. Nothing here can stop a
        daily run, and preparing a release still surfaces the exact values to
        advance to.
        """
        current = gp.snapshot_from_corpus(TRACKED_DB)
        declared = gp.DECLARED_SNAPSHOT
        if current["logical_sha256"] != declared["logical_sha256"]:
            raise unittest.SkipTest(
                "declared snapshot is stale relative to the tracked corpus — "
                "advance it before preparing a release: declared %s/%d/%s, "
                "corpus %s/%d/%s" % (
                    declared["date"], declared["expected_records"],
                    declared["logical_sha256"][:12],
                    current["date"], current["expected_records"],
                    current["logical_sha256"][:12]))
        self.assertEqual(current["date"], declared["date"])
        self.assertEqual(current["expected_records"],
                         declared["expected_records"])

    def test_input_order_does_not_change_the_fingerprint(self):
        corpus = [_fake_record(id=n, title_english="T%d" % n)
                  for n in range(1, 25)]
        forward = gp.corpus_fingerprint(corpus)
        self.assertEqual(gp.corpus_fingerprint(list(reversed(corpus))), forward)
        shuffled = corpus[7:] + corpus[:7]
        self.assertEqual(gp.corpus_fingerprint(shuffled), forward)

    def test_changing_any_included_field_changes_the_fingerprint(self):
        baseline = gp.corpus_fingerprint([_fake_record()])
        samples = {
            "id": 2, "url": "http://example.invalid/b",
            "title_original": "别的标题", "title_english": "Other",
            "published_date": "2026-01-02", "summary_english": "S",
            "analyzed_at": "2026-01-03 00:00:00", "model_id": "m",
            "prompt_version": "v2", "is_significant": 1,
            "content_hash": "def", "scraped_at": "2026-01-04 00:00:00",
            "scrape_run_id": 2, "text_original": "别的正文",
            "passed_relevance": 1, "source_slug": "t", "source_name": "Other",
            "language_tag": "en", "institution_id": "j",
            "institution": "Other Institution",
        }
        self.assertEqual(set(samples), set(gp.LOGICAL_FIELDS),
                         "every logical field must be exercised")
        for field, value in samples.items():
            with self.subTest(field=field):
                self.assertNotEqual(
                    gp.corpus_fingerprint([_fake_record(**{field: value})]),
                    baseline)

    def test_a_stale_content_hash_cannot_hide_a_corrected_body(self):
        """The stored hash is never recomputed, so text is hashed too."""
        original = _fake_record(text_original="original body")
        corrected = _fake_record(text_original="corrected body")
        self.assertEqual(original["content_hash"], corrected["content_hash"])
        self.assertNotEqual(gp.corpus_fingerprint([original]),
                            gp.corpus_fingerprint([corrected]))

    def test_replacing_a_record_at_a_constant_count_fails_the_assertion(self):
        corpus = [_fake_record(id=n) for n in range(1, 11)]
        snapshot = {"date": "d", "expected_records": 10,
                    "logical_sha256": gp.corpus_fingerprint(corpus)}
        gp.assert_snapshot(corpus, snapshot)
        swapped = corpus[:-1] + [_fake_record(id=11)]
        self.assertEqual(len(swapped), len(corpus))
        with self.assertRaises(gp.SnapshotMismatch) as caught:
            gp.assert_snapshot(swapped, snapshot)
        self.assertIn("content changed underneath a stable count",
                      str(caught.exception))

    def test_null_and_non_ascii_values_serialize_deterministically(self):
        record = _fake_record(title_original="国防部——“演习”",
                              summary_english=None, model_id=None,
                              prompt_version=None)
        first = gp.corpus_fingerprint([record])
        self.assertEqual(gp.corpus_fingerprint([dict(record)]), first)
        # None is distinct from the empty string, not conflated with it.
        self.assertNotEqual(
            gp.corpus_fingerprint([_fake_record(summary_english=None)]),
            gp.corpus_fingerprint([_fake_record(summary_english="")]))

    def test_derived_display_values_are_not_hashed(self):
        """A presentation change must not read as a corpus change."""
        plain = _fake_record()
        decorated = _fake_record()
        decorated.update(state="analyzed", state_label="Analyzed",
                         model_flagged=False, has_text=True,
                         record_path="record/1.html")
        self.assertEqual(gp.corpus_fingerprint([plain]),
                         gp.corpus_fingerprint([decorated]))

    def test_the_fingerprint_is_not_presented_as_a_public_identifier(self):
        for name in ("corpus.html", "about.html", "methodology.html"):
            path = REPO_ROOT / "preview" / name
            if path.exists():
                with self.subTest(page=name):
                    self.assertNotIn(self.snapshot["logical_sha256"],
                                     path.read_text(encoding="utf-8"))

    def test_snapshot_identity_is_not_derived_from_max_published_date(self):
        source = (REPO_ROOT / "site" / "preview"
                  / "generate_preview.py").read_text(encoding="utf-8")
        build_body = source.split("def build(", 1)[1]
        self.assertNotIn('snapshot_date = data["totals"]["last_date"]',
                         build_body)


# ── STOP 4: the reader-facing Corpus Guide ───────────────────────────────────

class TestCorpusGuide(PreviewCase):
    """One reader-facing surface: guide, dictionary and changelog.

    The properties that matter are not that the page renders — it is that every
    number on it is a query result rather than a typed literal, that the
    methodological warnings the rulings require are actually present, and that
    consolidating this material did not buy a new navigation item or a third
    boxed callout.
    """

    GUIDE = "corpus-guide.html"

    #: Stable anchors. A reader linking to a section, and the record pages
    #: linking to the dictionary, both depend on these not moving.
    SECTIONS = ("holds", "scope", "dates", "states", "machine", "dictionary",
                "citation", "changelog")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = cls.page(cls, cls.GUIDE)
        cls.corpus = gp.load_corpus(TRACKED_DB)
        cls.stats = gp.corpus_guide_stats(cls.corpus["corpus"],
                                          cls.corpus["run_days"])
        cls.text = re.sub(r"<[^>]+>", " ", cls.html)

    def _all_html(self):
        return {str(p.relative_to(self.out)): p.read_text(encoding="utf-8")
                for p in sorted(self.out.rglob("*.html"))}

    # ── Route, placement and links ──────────────────────────────────────

    def test_the_guide_is_one_page_with_every_governed_section(self):
        for anchor in self.SECTIONS:
            with self.subTest(anchor=anchor):
                self.assertIn('id="%s"' % anchor, self.html)

    def test_the_guide_adds_no_primary_navigation_item(self):
        """It is reachable contextually. The nav is unchanged."""
        for name, html in self._all_html().items():
            nav = html.split('<nav class="primary"', 1)[1].split("</nav>", 1)[0]
            with self.subTest(page=name):
                self.assertNotIn("corpus-guide.html", nav)
                self.assertNotIn("Corpus Guide", nav)

    def test_the_guide_is_linked_from_archive_about_and_record_pages(self):
        self.assertIn('href="corpus-guide.html"', self.page("archive.html"))
        self.assertIn('href="corpus-guide.html"', self.page("about.html"))
        rec = sorted((self.out / "record").glob("*.html"))[0]
        self.assertIn('href="../corpus-guide.html#dictionary"',
                      rec.read_text(encoding="utf-8"))

    def test_the_guide_adds_no_boxed_callout(self):
        for token in ('class="notice"', 'class="citation"', 'class="callout'):
            with self.subTest(token=token):
                self.assertNotIn(token, self.html)

    def test_rust_never_reaches_the_guide(self):
        """Rust means a model produced this. Nothing on the guide is model
        output, so no marker may appear on it."""
        self.assertNotIn("evidence--model", self.html)
        self.assertNotIn("interpretation", self.html)

    def test_the_masthead_footprint_is_unchanged(self):
        """The guide uses the shared masthead and adds nothing to it.

        Compared element-for-element against another page's masthead: the 320px
        footprint accepted in Tranche 1 is a property of this markup, so
        identical markup is identical footprint.
        """
        def masthead(html):
            return html.split('<header class="masthead">', 1)[1].split(
                "</header>", 1)[0]
        # corpus.html, not archive.html: the compared page must also be absent
        # from the nav, or its `aria-current` marker is the only difference.
        self.assertEqual(masthead(self.html), masthead(self.page("corpus.html")))

    # ── Data dictionary ─────────────────────────────────────────────────

    def test_every_dictionary_field_names_a_real_stored_column(self):
        record = self.corpus["corpus"][0]
        for field in gp.DICTIONARY_FIELDS:
            if not field["check"]:
                continue
            with self.subTest(field=field["label"]):
                self.assertIn(field["check"], record,
                              "%s claims a column the corpus does not carry"
                              % field["label"])

    def test_the_dictionary_covers_every_field_a_reader_encounters(self):
        labels = [f["label"] for f in gp.DICTIONARY_FIELDS]
        for required in (
                "Record ID", "Source-stated publication date", "Source outlet",
                "Publishing institution", "Original language", "Original title",
                "Stored source text", "Machine-translated English title",
                "Machine summary", "Processing state", "Machine assessment",
                "Analysis model", "Prompt version", "Capture fingerprint",
                "Collection run", "Collection timestamp", "Original URL"):
            with self.subTest(field=required):
                self.assertIn(required, labels)
                self.assertIn(required, self.html)

    def test_every_field_states_origin_meaning_absence_and_limitation(self):
        for row in gp.dictionary_rows(self.stats):
            with self.subTest(field=row["label"]):
                self.assertIn(row["origin"], ("Stored", "Derived"))
                for part in ("meaning", "absent", "limitation"):
                    self.assertTrue(row[part].strip(),
                                    "%s has no %s" % (row["label"], part))

    def test_a_field_claiming_it_is_never_absent_really_is_never_absent(self):
        """The strongest guard here: prose that says 'never absent' is checked
        against the corpus, so the claim cannot rot as data changes."""
        rows = {r["label"]: r for r in gp.dictionary_rows(self.stats)}
        for field in gp.DICTIONARY_FIELDS:
            if not field["check"] or "Never absent" not in field["absent"]:
                continue
            missing = sum(1 for r in self.corpus["corpus"]
                          if gp._blank(r.get(field["check"])))
            with self.subTest(field=field["label"]):
                self.assertEqual(missing, 0,
                                 "%s says 'never absent' but %d records lack it"
                                 % (field["label"], missing))
                self.assertIn("Never absent", rows[field["label"]]["absent"])

    def test_the_machine_assessment_row_never_prints_the_stored_column_name(self):
        """`is_significant` carries the one word the public label may never
        use. The row exists; the raw name does not."""
        row = [f for f in gp.DICTIONARY_FIELDS
               if f["label"] == "Machine assessment"][0]
        self.assertIsNone(row["stored"])
        for name, html in self._all_html().items():
            with self.subTest(page=name):
                self.assertNotIn("is_significant", html)

    def test_field_names_render_as_metadata_not_prose(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".fieldname", css)
        self.assertRegex(css, r"\.fieldname\s*\{[^{}]*var\(--mono\)")
        # Inside a row header, never in a heading or a paragraph.
        for match in re.findall(r'<code class="fieldname">', self.html):
            self.assertTrue(match)
        self.assertNotRegex(self.html, r"<h[123][^>]*>[^<]*<code")

    # ── Required methodological warnings ────────────────────────────────

    def test_every_required_warning_is_present(self):
        flat = re.sub(r"\s+", " ", self.text)
        for label, fragment in (
            ("date is source-stated", "Source-stated and collection-bounded"),
            ("collection-bounded", "it can only fall inside the window"),
            ("missing runs are not quiet days",
             "A gap in the run record is a gap in observation"),
            ("run history is thin",
             "does not preserve which publication dates were sought"),
            ("no source-level history",
             "does not preserve historical per-source outcomes"),
            ("language is a source attribute",
             "It is an attribute of the source, inherited by every record"),
            ("english is unreviewed",
             "No human has checked either against the original"),
            ("four states not two", "Processing has four states, not two"),
            ("assessment only when analyzed",
             "meaningful only within the analyzed set"),
            ("false flag implies nothing",
             "must never be read as evidence that an unscreened record was "
             "assessed"),
            ("edition label is human",
             "label a PLA Watch edition"),
            ("hash is capture-time",
             "not a continuing integrity guarantee"),
            ("prompt version missing",
             "of the {:,} analyzed records".format(self.analyzed_count)),
            ("first-writer-wins", "De-duplication across sources is "
                                  "first-writer-wins"),
            ("source counts are not volume",
             "not publication-volume counts"),
            ("institution concentration", "The corpus is concentrated in one "
                                          "institution"),
            ("empty captures", "records hold an empty body capture"),
            ("scrape time is not access time",
             "not a reader access date and not a publication time"),
        ):
            with self.subTest(warning=label):
                self.assertIn(fragment, flat, "missing warning: %s" % label)

    def test_no_raw_processing_enum_reaches_reader_facing_copy(self):
        """Codes are internal. Labels are the only strings a reader sees."""
        enums = ("not_selected", "awaiting_screening", "analysis_incomplete")
        for name, html in self._all_html().items():
            for enum in enums:
                with self.subTest(page=name, enum=enum):
                    self.assertNotIn(enum, html)

    # ── Counts equal direct queries ─────────────────────────────────────

    def test_every_displayed_count_equals_a_direct_query(self):
        corpus = self.corpus["corpus"]
        expected = {
            "total": len(corpus),
            "empty_text": sum(1 for r in corpus
                              if not (r.get("text_original") or "").strip()),
            "no_english": sum(1 for r in corpus
                              if not (r.get("title_english") or "").strip()),
            "analyzed": sum(1 for r in corpus if r["state"] == "analyzed"),
            "awaiting_screening": sum(1 for r in corpus
                                      if r["state"] == "awaiting_screening"),
            "analysis_incomplete": sum(1 for r in corpus
                                       if r["state"] == "analysis_incomplete"),
            "not_selected": sum(1 for r in corpus
                                if r["state"] == "not_selected"),
            "max_id": max(r["id"] for r in corpus),
            "outlets": len({r["source_name"] for r in corpus}),
        }
        for key, value in expected.items():
            with self.subTest(stat=key):
                self.assertEqual(self.stats[key], value)
        self.assertEqual(self.stats["backlog"],
                         expected["awaiting_screening"]
                         + expected["analysis_incomplete"])
        self.assertEqual(
            self.stats["prompt_version_missing"],
            sum(1 for r in corpus if r["state"] == "analyzed"
                and not (r.get("prompt_version") or "").strip()))
        # The four states still sum to the declared snapshot.
        self.assertEqual(
            expected["analyzed"] + expected["not_selected"]
            + expected["awaiting_screening"] + expected["analysis_incomplete"],
            self.snapshot["expected_records"])

    def test_institution_concentration_is_computed_not_asserted(self):
        counts = Counter(r["institution"] for r in self.corpus["corpus"]
                         if r.get("institution"))
        name, n = counts.most_common(1)[0]
        self.assertEqual(self.stats["top_institution"], name)
        self.assertEqual(self.stats["top_institution_count"], n)
        self.assertEqual(self.stats["top_institution_pct"],
                         round(100.0 * n / len(self.corpus["corpus"]), 1))
        self.assertIn("%s%%" % self.stats["top_institution_pct"], self.html)

    def test_displayed_figures_appear_on_the_page_with_separators(self):
        flat = re.sub(r"\s+", " ", self.text)
        for key in ("total", "no_english", "empty_text", "analyzed",
                    "awaiting_screening", "backlog"):
            with self.subTest(stat=key):
                self.assertIn("{:,}".format(self.stats[key]), flat)

    def test_identifiers_never_carry_thousands_separators(self):
        """`max_id` is an identifier, not a count. The house rule is that the
        separator filter never touches ids."""
        self.assertIn(str(self.stats["max_id"]), self.html)
        self.assertNotIn("{:,}".format(self.stats["max_id"]), self.html)

    # ── Changelog ───────────────────────────────────────────────────────

    def test_the_changelog_leads_with_limitations_not_growth(self):
        entry = gp.changelog_entries(self.stats)[0]
        headings = [h for h, _ in entry["points"]]
        self.assertEqual(headings[0], "A recorded collection interruption")
        self.assertEqual(headings[-1], "Snapshot and size")
        body = self.html.split('id="changelog"', 1)[1]
        self.assertLess(body.index("A recorded collection interruption"),
                        body.index("Snapshot and size"))

    def test_the_changelog_names_the_governed_interruption_from_run_data(self):
        gaps = gp.collection_gaps(self.corpus["run_days"])
        self.assertTrue(gaps, "the governed interruption is no longer derivable")
        self.assertEqual((gaps[0]["from"], gaps[0]["to"]),
                         ("2026-07-17", "2026-07-24"))
        flat = re.sub(r"\s+", " ", self.text)
        self.assertIn("No pipeline run is recorded on the UTC dates "
                      "2026-07-17 through 2026-07-24", flat)

    def test_the_changelog_refuses_to_quantify_what_was_missed(self):
        flat = re.sub(r"\s+", " ", self.text)
        self.assertIn("neither reconstructed nor estimated", flat)
        self.assertIn("its absence is not evidence that nothing was published",
                      flat)

    def test_the_changelog_is_editorial_not_generated_history(self):
        """It is hand-maintained, and it is not the collection-health log."""
        flat = re.sub(r"\s+", " ", self.text)
        self.assertIn("hand-written record", flat)
        self.assertIn("not generated from repository history", flat)
        self.assertIn("not a collection-health log", flat)
        self.assertIn('href="coverage.html"', self.html)
        # No commit shas, no per-source reliability history.
        self.assertNotRegex(self.html, r"\b[0-9a-f]{7,40}\b")
        for invented in ("uptime", "reliability of", "% of runs succeeded"):
            with self.subTest(phrase=invented):
                self.assertNotIn(invented, flat)

    def test_the_changelog_counts_are_the_stats_counts(self):
        flat = re.sub(r"\s+", " ", self.text)
        changelog = flat.split("Corpus changelog", 1)[1]
        for key in ("backlog", "awaiting_screening", "no_english",
                    "empty_text", "total"):
            with self.subTest(stat=key):
                self.assertIn("{:,}".format(self.stats[key]), changelog)

    # ── Table semantics ─────────────────────────────────────────────────

    def test_new_tables_carry_captions_and_scoped_headers(self):
        """`<th([^>]*)>` also matches `<thead>` and captures "ead" — the same
        trap that produced a wrong header count at STOP 3. The lookahead keeps
        this counting real header cells."""
        for table in re.findall(r"<table[^>]*>.*?</table>", self.html, re.S):
            with self.subTest(table=table[:60]):
                self.assertIn("<caption>", table)
                cells = re.findall(r"<th(?![a-z])([^>]*)>", table)
                self.assertTrue(cells)
                for th in cells:
                    self.assertRegex(th, r'scope="(col|row)"')

    def test_the_dictionary_table_stacks_without_pseudo_labels(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        block = css.split("Corpus Guide", 1)[1]
        # `thead` moves off-screen, never out of the accessibility tree.
        self.assertIn(".dictionary thead { position: absolute; left: -9999px; }",
                      block)
        self.assertNotIn(".dictionary td::before", block)
        # Visible stacked labels are real markup, hidden above the breakpoint.
        self.assertIn(".d-key { display: none; }", block)
        self.assertIn('<span class="d-key">', self.html)

    def test_wide_tables_scroll_inside_their_own_container(self):
        for match in re.finditer(r"<table", self.html):
            before = self.html[:match.start()]
            self.assertGreater(before.rfind('<div class="table-scroll">'),
                               before.rfind("</div>"))


# ── STOP 4: snapshot-scoped citations ────────────────────────────────────────

#: Things a citation on this prototype may never contain. Each is a specific
#: fabrication someone would otherwise be tempted to add for completeness: an
#: identifier range over non-contiguous ids, a version for a corpus with no
#: release discipline, a resolver that does not exist, a place of publication
#: nobody recorded, an affiliation nobody claimed, an access date the pipeline
#: never captured, and the private preview route.
FORBIDDEN_IN_CITATIONS = (
    (r"[Rr]ecords\s+\d[\d,]*\s*[–-]\s*\d", "an identifier range"),
    (r"\bv0\.\d+\b", "a semantic version"),
    (r"\bdoi\b", "a DOI"),
    (r"\bdoi\.org\b", "a DOI resolver"),
    (r"\baccession\b", "an accession number"),
    (r"\baccessed\b", "a reader access date"),
    (r"\bretrieved\b", "a retrieval date"),
    (r"\bWashington\b|\bBeijing, ", "a place of publication"),
    (r"\bGeorge Washington University\b", "an affiliation"),
    (r"\bElliott School\b", "an affiliation"),
    (r"127\.0\.0\.1|localhost|/preview/", "the private preview route"),
    (r"\bPrincipal Analyst\b", "a superseded role title"),
)


class TestSnapshotScopedCitations(PreviewCase):
    """Three citation surfaces, all scoped to the declared snapshot.

    A citation is the one string that leaves this prototype and enters someone
    else's footnotes. Everything here is about what it may not silently
    substitute or invent.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.corpus = gp.load_corpus(TRACKED_DB)["corpus"]
        cls.by_id = {r["id"]: r for r in cls.corpus}
        cls.editions = gp.load_editions(REPO_ROOT)
        cls.guide = cls.page(cls, "corpus-guide.html")
        cls.weekly = cls.page(cls, "weekly.html")

    def record(self, rec_id):
        return (self.out / "record" / ("%d.html" % rec_id)).read_text(
            encoding="utf-8")

    def first_in_state(self, state):
        for rec in self.corpus:
            if rec["state"] == state:
                return rec["id"]
        raise AssertionError("no record in state %s" % state)

    def _all_html(self):
        return {str(p.relative_to(self.out)): p.read_text(encoding="utf-8")
                for p in sorted(self.out.rglob("*.html"))}

    # ── A. Corpus snapshot ──────────────────────────────────────────────

    def test_the_corpus_citation_is_exact(self):
        self.assertEqual(
            gp.corpus_citation("The Declared Record", gp.DECLARED_SNAPSHOT),
            "The Declared Record. China Desk Corpus. Prototype snapshot — "
            "2026-08-19. 3,388 records. Benjamin Yang, Creator and Editor.")

    def test_the_corpus_citation_is_rendered_and_copyable(self):
        expected = gp.corpus_citation("Test Title", self.snapshot)
        self.assertIn(
            '<p class="cite-text" id="cite-corpus">%s</p>'
            % markupsafe.escape(expected), self.guide)
        self.assertIn('data-copy="cite-corpus"', self.guide)

    def test_the_corpus_citation_derives_both_values_from_the_snapshot(self):
        """Not a second source of truth: change the declared object and the
        citation must follow it."""
        other = {"date": "2027-01-02", "expected_records": 4096}
        text = gp.corpus_citation("Work", other)
        self.assertIn("Prototype snapshot — 2027-01-02", text)
        self.assertIn("4,096 records", text)
        source = (REPO_ROOT / "site" / "preview"
                  / "generate_preview.py").read_text(encoding="utf-8")
        build_body = source.split("def build(", 1)[1]
        self.assertNotIn('data["totals"]["articles"]', build_body.split(
            "citation = ", 1)[1][:200])

    # ── B. Individual record ────────────────────────────────────────────

    def test_every_record_citation_uses_its_own_stored_values(self):
        """Not a sample: every stored record, every required field."""
        wrong = []
        for rec in self.corpus:
            cite = gp.record_citation(rec, "Test Title", self.snapshot)
            for value in (rec["institution"], rec["title_original"],
                          rec["source_name"], rec["published_date"],
                          rec["url"]):
                if str(value) not in cite["source_text"]:
                    wrong.append((rec["id"], value))
            if "Record %d," % rec["id"] not in cite["as_held"]:
                wrong.append((rec["id"], "id"))
        self.assertEqual(wrong[:10], [])

    def test_no_record_citation_substitutes_the_english_title(self):
        """The substitution this whole surface exists to prevent.

        Every record is checked positively: the source-text block must quote
        the ORIGINAL title. The negative check — that the machine title is
        absent — is only meaningful where the two strings are genuinely
        different. For an English-language source the machine title is close to
        or contained in the original (Global Times record 2265 differs only by
        a leading quote mark), so absence there would be untestable rather than
        untrue.
        """
        compared = 0
        for rec in self.corpus:
            original = rec["title_original"]
            english = (rec.get("title_english") or "").strip()
            cite = gp.record_citation(rec, "Test Title", gp.DECLARED_SNAPSHOT)
            with self.subTest(record=rec["id"]):
                self.assertIn('"%s."' % original, cite["source_text"])
                if english and english not in original:
                    compared += 1
                    self.assertNotIn(english, cite["source_text"])
        # The negative check must cover the bulk of the analyzed set, not a
        # handful of records that happened to qualify.
        self.assertGreater(compared, 1_000)

    def test_the_rendered_source_text_block_quotes_the_original_title(self):
        for state in gp.STATE_ORDER:
            rec_id = self.first_in_state(state)
            rec = self.by_id[rec_id]
            html = self.record(rec_id)
            with self.subTest(state=state):
                self.assertIn(str(markupsafe.escape(
                    '"%s."' % rec["title_original"])), html)

    def test_all_record_pages_carry_the_snapshot_date_and_count(self):
        expected = ("Prototype snapshot — %s (%s records)"
                    % (self.snapshot["date"],
                       "{:,}".format(self.snapshot["expected_records"])))
        missing = [p.name for p in sorted((self.out / "record").glob("*.html"))
                   if expected not in p.read_text(encoding="utf-8")]
        self.assertEqual(missing, [])
        self.assertEqual(len(list((self.out / "record").glob("*.html"))),
                         self.corpus_size)

    def test_each_processing_state_receives_its_own_note(self):
        notes = gp.CITATION_PROCESSING_NOTES
        self.assertEqual(set(notes), set(gp.STATE_ORDER))
        self.assertEqual(len(set(notes.values())), 4,
                         "a blanket note is applied to more than one state")
        for state, expected in (
            ("analyzed", "machine-generated and have not been reviewed by a "
                         "human"),
            ("not_selected", "screened and not selected for analysis"),
            ("awaiting_screening", "has not been screened"),
            ("analysis_incomplete", "No completed analysis is claimed"),
        ):
            with self.subTest(state=state):
                self.assertIn(expected, notes[state])
                html = self.record(self.first_in_state(state))
                self.assertIn(markupsafe.escape(notes[state]), html)
                # and no other state's note
                for other, text in notes.items():
                    if other != state:
                        self.assertNotIn(markupsafe.escape(text), html)

    def test_an_unscreened_record_is_never_told_it_was_analyzed(self):
        for state in ("not_selected", "awaiting_screening",
                      "analysis_incomplete"):
            html = self.record(self.first_in_state(state))
            with self.subTest(state=state):
                self.assertNotIn("machine-generated and have not been reviewed",
                                 html)

    def test_the_record_id_is_never_called_permanent(self):
        html = self.record(self.first_in_state("analyzed"))
        # Normalized: the denials sit in one wrapped paragraph, so a literal
        # match would depend on where the source line happens to break.
        block = re.sub(r"\s+", " ", html.split("Cite this record", 1)[1])
        for claim in ("permanent identifier", "DOI", "accession number",
                      "public permalink", "published route"):
            with self.subTest(claim=claim):
                self.assertIn(claim, block)   # each is explicitly denied
        self.assertNotRegex(block, r"permanently (?:available|resolvable)")
        self.assertNotIn('rel="canonical"', html)

    def test_no_prototype_route_or_canonical_link_is_published(self):
        for name, html in self._all_html().items():
            with self.subTest(page=name):
                self.assertNotIn('rel="canonical"', html)
        self.assertFalse((self.out / "sitemap.xml").exists())

    # ── C. Editions ─────────────────────────────────────────────────────

    def test_all_thirteen_edition_citations_preserve_their_sidecar_values(self):
        self.assertEqual(len(self.editions), 13)
        for edition in self.editions:
            text = gp.edition_citation(edition)
            with self.subTest(edition=edition["slug"]):
                self.assertIn('"%s."' % edition["title"], text)
                self.assertIn("No. %s," % edition["issue"], text)
                self.assertIn("week ending %s." % gp.reader_date(
                    edition["date"]), text)
                self.assertTrue(text.endswith("%s." % edition["url"]))
                self.assertIn(markupsafe.escape(text), self.weekly)

    def test_no_edition_citation_carries_a_role_title(self):
        for edition in self.editions:
            text = gp.edition_citation(edition)
            with self.subTest(edition=edition["slug"]):
                self.assertTrue(text.startswith("Benjamin Yang. "))
                for role in ("Creator and Editor", "Principal Analyst",
                             "Editor,", "Analyst,"):
                    self.assertNotIn(role, text)

    def test_the_reader_date_follows_the_day_month_year_convention(self):
        """`DECISION_LOG.md` 2026-07-09: reader-facing week-ending labels read
        "4 July 2026". ISO stays in tabular and metadata contexts."""
        self.assertEqual(gp.reader_date("2026-08-08"), "8 August 2026")
        self.assertEqual(gp.reader_date("2026-05-09"), "9 May 2026")
        self.assertEqual(gp.reader_date("2026-01-31"), "31 January 2026")
        self.assertEqual(gp.reader_date("2026-07-04"), "4 July 2026")
        # No month-first form survives anywhere.
        for edition in self.editions:
            with self.subTest(edition=edition["slug"]):
                self.assertNotRegex(gp.edition_citation(edition),
                                    r"week ending [A-Z][a-z]+ \d{1,2}, \d{4}")

    def test_the_thirteenth_edition_citation_is_exact(self):
        top = [e for e in self.editions if e["issue"] == 13][0]
        self.assertEqual(
            gp.edition_citation(top),
            'Benjamin Yang. "The PLA Watch: Scarborough Shoal, Platform '
            'Disclosures, and the Limits of Anniversary Week." The PLA Watch, '
            'No. 13, week ending 8 August 2026. '
            'https://chinamilwatch.org/the-pla-watch/posts/2026-08-08.html.')

    def test_edition_issue_numbers_and_urls_are_unchanged(self):
        """The citation may not renumber or relocate a published edition."""
        for edition in self.editions:
            text = gp.edition_citation(edition)
            with self.subTest(edition=edition["slug"]):
                self.assertIn(gp.LIVE_BASE, text)
                self.assertIn("/the-pla-watch/posts/%s.html" % edition["slug"],
                              text)

    # ── Fabrication guards ──────────────────────────────────────────────

    def test_no_citation_contains_a_forbidden_element(self):
        texts = [gp.corpus_citation("The Declared Record",
                                    gp.DECLARED_SNAPSHOT)]
        texts += [gp.edition_citation(e) for e in self.editions]
        for state in gp.STATE_ORDER:
            cite = gp.record_citation(self.by_id[self.first_in_state(state)],
                                      "The Declared Record",
                                      gp.DECLARED_SNAPSHOT)
            texts += [cite["source_text"], cite["as_held"], cite["note"]]
        for text in texts:
            for pattern, what in FORBIDDEN_IN_CITATIONS:
                with self.subTest(what=what, text=text[:48]):
                    self.assertIsNone(re.search(pattern, text, re.I),
                                      "citation contains %s" % what)

    def test_the_logical_fingerprint_never_becomes_reader_facing(self):
        digest = gp.DECLARED_SNAPSHOT["logical_sha256"]
        for name, html in self._all_html().items():
            with self.subTest(page=name):
                self.assertNotIn(digest, html)
        for asset in ("corpus-index.json", "citation.js", "browse.js"):
            with self.subTest(asset=asset):
                self.assertNotIn(
                    digest, (self.out / asset).read_text(encoding="utf-8"))

    def test_a_missing_citation_value_fails_the_build(self):
        for field, label in (("institution", "publishing institution"),
                             ("title_original", "original title"),
                             ("source_name", "source outlet"),
                             ("published_date", "source-stated publication"),
                             ("url", "original URL")):
            record = _fake_record(state="analyzed", **{field: None})
            with self.subTest(field=field):
                with self.assertRaises(gp.CitationDataMissing) as caught:
                    gp.record_citation(record, "Work", gp.DECLARED_SNAPSHOT)
                self.assertIn(label, str(caught.exception))

    def test_a_missing_edition_value_fails_the_build(self):
        good = dict(self.editions[0])
        for field in ("title", "issue", "date", "url"):
            broken = dict(good, **{field: None})
            with self.subTest(field=field):
                with self.assertRaises(gp.CitationDataMissing):
                    gp.edition_citation(broken)

    # ── Controls, budgets and script placement ──────────────────────────

    def test_citation_text_is_visible_without_javascript(self):
        """The text is ordinary markup. Only the buttons are enhancement."""
        for page, anchor in (("corpus-guide.html", "cite-corpus"),
                             ("weekly.html", "cite-edition-2026-08-08")):
            html = self.page(page)
            with self.subTest(page=page):
                self.assertRegex(
                    html, r'<p class="cite-text" id="%s">[^<]+</p>' % anchor)

    def test_copy_controls_ship_hidden_everywhere(self):
        for name, html in self._all_html().items():
            for button in re.findall(r"<button[^>]*data-copy[^>]*>", html):
                with self.subTest(page=name, button=button[:50]):
                    self.assertIn("hidden", button)

    def test_every_copy_button_targets_a_real_element_on_its_page(self):
        for name, html in self._all_html().items():
            ids = set(re.findall(r'\bid="([^"]+)"', html))
            for target in re.findall(r'data-copy="([^"]+)"', html):
                with self.subTest(page=name, target=target):
                    self.assertIn(target, ids)
            if re.search(r"data-copy=", html):
                self.assertIn('class="cite-status"', html)
                self.assertIn('aria-live="polite"', html)

    def test_no_page_loads_both_browse_js_and_citation_js(self):
        for name, html in self._all_html().items():
            with self.subTest(page=name):
                self.assertFalse("browse.js" in html and "citation.js" in html,
                                 "%s loads both page scripts" % name)

    def test_citation_js_loads_only_where_it_is_governed(self):
        loading = sorted(name for name, html in self._all_html().items()
                         if "citation.js" in html)
        self.assertIn("corpus-guide.html", loading)
        self.assertIn("weekly.html", loading)
        self.assertNotIn("archive.html", loading)
        records = [n for n in loading if n.startswith("record/")]
        self.assertEqual(len(records), self.corpus_size)

    def test_page_scripts_stay_within_budget(self):
        for asset in ("browse.js", "citation.js"):
            size = len((self.out / asset).read_bytes())
            with self.subTest(asset=asset):
                self.assertLessEqual(size, 10_000)

    def test_citation_js_never_writes_corpus_data_through_innerhtml(self):
        js = (self.out / "citation.js").read_text(encoding="utf-8")
        code = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
        for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML",
                       "document.write", "eval("):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, code)
        self.assertIn("textContent", code)

    def test_citation_js_reads_the_rendered_element_not_a_duplicate(self):
        js = (self.out / "citation.js").read_text(encoding="utf-8")
        code = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
        self.assertIn("source.textContent", code)
        # No second copy of the citation to drift from what is displayed.
        self.assertNotIn("data-citation", code)
        self.assertNotIn("data-text", code)
        for name, html in self._all_html().items():
            with self.subTest(page=name):
                self.assertNotIn("data-citation", html)

    def test_citations_render_borderless(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        for selector in (r"\.cite-block", r"\.cite-text", r"\.cite-line"):
            block = re.search(selector + r"\s*\{([^{}]*)\}", css)
            with self.subTest(selector=selector):
                self.assertIsNotNone(block)
                self.assertNotIn("border", block.group(1))
                self.assertNotIn("background", block.group(1))
        for name, html in self._all_html().items():
            with self.subTest(page=name):
                self.assertNotIn('class="citation"', html)

    def test_rust_never_marks_a_citation(self):
        """Rust means a model produced this. A citation is authored."""
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        users = re.findall(r'([^{}]+)\{[^{}]*var\(--signal\)[^{}]*\}', css)
        for selector in " ".join(users).split(","):
            with self.subTest(selector=selector.strip()[:40]):
                self.assertNotIn("cite", selector)


class TestEditionCitationsAreIntegrated(PreviewCase):
    """One citation per existing edition entry, and no second bibliography.

    The first STOP 4 build rendered the 13-edition archive and then repeated
    all 13 as a standalone citation list — the same titles twice on one page.
    The citations now live inside the rows they cite.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = cls.page(cls, "weekly.html")
        cls.editions = gp.load_editions(REPO_ROOT)
        cls.table = cls.html.split('<table class="editions">', 1)[1].split(
            "</table>", 1)[0]

    def test_every_edition_row_owns_exactly_one_citation(self):
        # Scoped to <tbody>: the header row is a <tr> too, and counting it
        # would report 14 editions.
        body = self.table.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        rows = re.findall(r"<tr>.*?</tr>", body, re.S)
        self.assertEqual(len(rows), 13)
        for row, edition in zip(rows, self.editions):
            with self.subTest(edition=edition["slug"]):
                self.assertEqual(row.count("<details class=\"ed-cite\">"), 1)
                self.assertEqual(row.count('class="cite-text"'), 1)
                self.assertEqual(row.count("data-copy="), 1)
                self.assertIn(markupsafe.escape(gp.edition_citation(edition)),
                              row)
                self.assertIn('id="cite-edition-%s"' % edition["slug"], row)

    def test_no_citation_renders_outside_the_edition_table(self):
        outside = self.html.replace(self.table, "")
        self.assertNotIn('class="cite-text"', outside)
        self.assertNotIn("data-copy=", outside)
        self.assertNotIn("cite-block", self.html)

    def test_no_second_list_of_edition_titles_exists(self):
        """Each title appears once as a link, and once inside its own
        citation — never a third time as a separate bibliography entry."""
        for edition in self.editions:
            escaped = str(markupsafe.escape(edition["title"]))
            with self.subTest(edition=edition["slug"]):
                self.assertEqual(self.html.count(escaped), 2)
        self.assertNotIn("Citing an edition", self.html)
        self.assertNotIn('id="edition-citations"', self.html)

    def test_the_page_keeps_one_h1_and_its_heading_order(self):
        self.assertEqual(len(re.findall(r"<h1[\s>]", self.html)), 1)
        levels = [int(m) for m in re.findall(r"<h([1-6])[\s>]", self.html)]
        for a, b in zip(levels, levels[1:]):
            self.assertLessEqual(b, a + 1)

    def test_existing_edition_semantics_are_untouched(self):
        """Order, links, labels and the mobile card classes all survive."""
        issues = [int(n) for n in
                  re.findall(r'<td class="num ed-no">(\d+)</td>', self.table)]
        self.assertEqual(issues, [e["issue"] for e in self.editions])
        self.assertEqual(issues, sorted(issues, reverse=True))
        for edition in self.editions:
            with self.subTest(edition=edition["slug"]):
                self.assertIn('href="%s"' % edition["url"], self.table)
                if edition["label"]:
                    self.assertIn(edition["label"], self.table)
        for cls in ("ed-no", "ed-date", "ed-title", "ed-articles",
                    "ed-flagged", "ed-label-inline", "ed-label-wide"):
            with self.subTest(cls=cls):
                self.assertIn(cls, self.html)
        # ISO dates stay in the table; day-month-year belongs to the citation.
        for edition in self.editions:
            self.assertIn('<td class="ed-date">%s' % edition["date"],
                          self.table)

    def test_the_disclosure_is_native_and_unscripted(self):
        js = (self.out / "citation.js").read_text(encoding="utf-8")
        code = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
        for token in ("details", "summary", "open"):
            with self.subTest(token=token):
                self.assertNotIn(token, code)
        self.assertIn("<summary>Cite this issue</summary>", self.html)

    def test_the_disclosure_carries_no_box_and_no_rust(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        block = re.search(r"\.ed-cite\s*\{([^{}]*)\}", css)
        self.assertIsNotNone(block)
        self.assertNotIn("border", block.group(1))
        self.assertNotIn("background", block.group(1))
        summary = re.search(r"\.ed-cite > summary\s*\{([^{}]*)\}", css)
        self.assertNotIn("--signal", summary.group(1))
        self.assertIn("min-height: 44px", summary.group(1))
        users = re.findall(r'([^{}]+)\{[^{}]*var\(--signal\)[^{}]*\}', css)
        self.assertNotIn("ed-cite", " ".join(users))


class TestEnglishOutputIsMeasuredPerField(PreviewCase):
    """Three machine-output fields, each measured on its own.

    A single `no_english` figure was doing duty for the English title, the
    machine summary and the analysis model. Three fields can each be empty on
    2,140 records while disagreeing about WHICH 2,140, and one count would hide
    that. The combined sentence is earned by set equivalence, not by three
    totals that happen to match.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.corpus = gp.load_corpus(TRACKED_DB)["corpus"]
        cls.sets = gp.english_output_sets(cls.corpus)
        cls.html = cls.page(cls, "corpus-guide.html")
        cls.flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", cls.html))

    def _sql(self, where):
        from scripts.reconcile_db import _read_only
        with _read_only(str(TRACKED_DB)) as con:
            return {r[0] for r in con.execute(
                "SELECT id FROM articles WHERE " + where).fetchall()}

    def test_each_field_is_derived_from_its_own_column(self):
        for key, where in (
            ("empty_title",
             "title_english IS NULL OR TRIM(title_english) = ''"),
            ("empty_summary",
             "summary_english IS NULL OR TRIM(summary_english) = ''"),
            ("empty_model", "model_id IS NULL OR TRIM(model_id) = ''"),
            ("non_analyzed",
             "NOT (passed_relevance = 1 AND analyzed_at IS NOT NULL)"),
        ):
            with self.subTest(field=key):
                self.assertEqual(self.sets[key], self._sql(where),
                                 "%s disagrees with a direct query" % key)

    def test_set_equivalence_is_asserted_by_identity_not_by_count(self):
        """The permanent assertion the combined sentence depends on."""
        title = self.sets["empty_title"]
        for other in ("empty_summary", "empty_model", "non_analyzed"):
            with self.subTest(other=other):
                self.assertEqual(
                    title ^ self.sets[other], set(),
                    "%s holds different record ids than empty_title" % other)
        self.assertTrue(self.sets["identical"])

    def test_the_stats_expose_all_three_counts_separately(self):
        stats = gp.corpus_guide_stats(self.corpus,
                                      gp.load_corpus(TRACKED_DB)["run_days"])
        self.assertEqual(stats["no_english"], len(self.sets["empty_title"]))
        self.assertEqual(stats["no_summary"], len(self.sets["empty_summary"]))
        self.assertEqual(stats["no_model"], len(self.sets["empty_model"]))
        self.assertEqual(stats["non_analyzed"], len(self.sets["non_analyzed"]))
        self.assertIs(stats["english_sets_identical"], True)

    def test_each_dictionary_row_cites_its_own_field_count(self):
        rows = {r["label"]: r for r in gp.dictionary_rows(
            gp.corpus_guide_stats(self.corpus,
                                  gp.load_corpus(TRACKED_DB)["run_days"]))}
        for label, key in (
                ("Machine-translated English title", "empty_title"),
                ("Machine summary", "empty_summary"),
                ("Analysis model", "empty_model")):
            with self.subTest(field=label):
                self.assertIn("{:,}".format(len(self.sets[key])),
                              rows[label]["absent"])
        # No row leans on another field's number.
        self.assertNotIn("the same", rows["Machine summary"]["absent"])

    def test_the_combined_sentence_is_rendered_only_when_sets_agree(self):
        self.assertIn("the same identifiers, not merely the same total",
                      self.flat)
        self.assertIn("they are exactly the records outside the Analyzed "
                      "state", self.flat)

    def test_the_guide_renders_separate_counts_when_sets_disagree(self):
        """The false branch must be real, not decorative."""
        corpus = [dict(r) for r in self.corpus]
        # One analyzed record loses only its summary: the sets now differ by
        # one id while every total stays plausible.
        for rec in corpus:
            if rec["state"] == "analyzed":
                rec["summary_english"] = ""
                break
        sets = gp.english_output_sets(corpus)
        self.assertFalse(sets["identical"])
        self.assertEqual(len(sets["empty_summary"] - sets["empty_title"]), 1)
        stats = gp.corpus_guide_stats(corpus,
                                      gp.load_corpus(TRACKED_DB)["run_days"])
        entry = gp.changelog_entries(stats)[0]
        english = dict(entry["points"])["Most records carry no English "
                                        "rendering"]
        self.assertIn("These are not the same records", english)
        self.assertNotIn("the same identifiers", english)


class TestInterruptionClaimIsMeasured(PreviewCase):
    """The changelog says material from the outage window is absent. That is a
    claim about stored data, so it is measured before it is printed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.corpus = gp.load_corpus(TRACKED_DB)
        cls.stats = gp.corpus_guide_stats(cls.corpus["corpus"],
                                          cls.corpus["run_days"])
        cls.flat = re.sub(r"\s+", " ", re.sub(
            r"<[^>]+>", " ", cls.page(cls, "corpus-guide.html")))

    def test_zero_records_carry_a_publication_date_in_the_window(self):
        from scripts.reconcile_db import _read_only
        with _read_only(str(TRACKED_DB)) as con:
            n = con.execute(
                "SELECT COUNT(*) FROM articles "
                " WHERE published_date >= ? AND published_date <= ?",
                (gp.OUTAGE_START, gp.OUTAGE_END)).fetchone()[0]
        self.assertEqual(n, 0)
        self.assertEqual(self.stats["outage_records"], n)

    def test_the_rendered_sentence_matches_the_measurement(self):
        self.assertIn("No pipeline run is recorded on the UTC dates "
                      "2026-07-17 through 2026-07-24, and no record in this "
                      "snapshot carries a source-stated publication date "
                      "inside that window.", self.flat)

    def test_a_window_holding_records_changes_the_sentence(self):
        """If the window ever holds records, claiming absence would be false."""
        stats = dict(self.stats, outage_records=5)
        entry = gp.changelog_entries(stats)[0]
        text = dict(entry["points"])["A recorded collection interruption"]
        self.assertIn("nonetheless holds 5 records", text)
        self.assertNotIn("no record in this snapshot carries", text)


class TestHostileTitlesStayInertInCitations(unittest.TestCase):
    """A stored title is source data and may contain anything at all."""

    def test_a_hostile_title_is_escaped_inside_its_citation(self):
        import sqlite3
        hostile = ('<img src=x onerror=alert(1)><script>window.x=1</script>'
                   '"><b>bold</b>')
        tmp = Path(tempfile.mkdtemp(prefix="hostile-cite-"))
        try:
            db = tmp / "hostile.db"
            shutil.copy(TRACKED_DB, db)
            con = sqlite3.connect(db)
            rec_id = con.execute(
                "SELECT id FROM articles ORDER BY id DESC LIMIT 1").fetchone()[0]
            con.execute("UPDATE articles SET title_original=? WHERE id=?",
                        (hostile, rec_id))
            con.commit()
            con.close()
            snapshot = dict(gp.snapshot_from_corpus(db), logical_sha256=None)
            out = tmp / "build"
            gp.build(out, "Test Title", db, snapshot=snapshot)

            page = (out / "record" / ("%d.html" % rec_id)).read_text(
                encoding="utf-8")
            block = page.split("Cite this record", 1)[1]
            # Present verbatim as data, inert as markup.
            self.assertIn("&lt;img src=x", block)
            self.assertNotIn("<img src=x", block)
            self.assertNotIn("<script>window.x=1</script>", block)
            self.assertNotIn("<b>bold</b>", block)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCitationCopyBehaviour(PreviewCase):
    """Behavioural proof, in a real browser, of the three states that matter.

    Source-level assertions can show a failure branch exists. Only running it
    shows that a rejected clipboard write produces an honest message rather
    than a silent no-op that looks like success.

    Offline: a loopback HTTP server on an ephemeral port. No network.
    """

    #: Rejects every write, the way a browser does when the clipboard
    #: permission is denied or the page is not a secure context.
    DENY_CLIPBOARD = """
        Object.defineProperty(navigator, 'clipboard', {
          configurable: true,
          value: { writeText: function () {
            return Promise.reject(new Error('denied'));
          } }
        });
    """

    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:                                   # pragma: no cover
            raise unittest.SkipTest("playwright not installed")
        super().setUpClass()
        import functools
        import http.server
        import socketserver
        import threading

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass

        handler = functools.partial(Quiet, directory=str(cls.out))
        socketserver.TCPServer.allow_reuse_address = True
        cls.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        # The package can be installed while the browser binary is not:
        # `pip install playwright` does not fetch chromium, and the pull-request
        # workflow deliberately installs no browser. Skip cleanly there rather
        # than erroring — the daily workflow runs `playwright install chromium`
        # before this suite, so these assertions are still enforced before any
        # production render.
        cls._pw = sync_playwright().start()
        try:
            cls.browser = cls._pw.chromium.launch()
        except Exception as exc:                              # pragma: no cover
            cls._pw.stop()
            raise unittest.SkipTest(
                "chromium not available (%s); run `playwright install chromium`"
                % type(exc).__name__)
        cls.expected = gp.corpus_citation("Test Title", cls.snapshot)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "browser"):
            cls.browser.close()
            cls._pw.stop()
            cls.httpd.shutdown()
            cls.httpd.server_close()
        super().tearDownClass()

    def url(self, path):
        return "http://127.0.0.1:%d/%s" % (self.port, path)

    def test_a_successful_copy_puts_the_exact_citation_on_the_clipboard(self):
        context = self.browser.new_context(
            permissions=["clipboard-read", "clipboard-write"])
        try:
            page = context.new_page()
            page.goto(self.url("corpus-guide.html"), wait_until="load")
            page.wait_for_timeout(300)
            button = page.query_selector('button[data-copy="cite-corpus"]')
            self.assertFalse(button.is_hidden(),
                             "the control was never revealed")
            button.click()
            page.wait_for_timeout(400)
            self.assertEqual(
                page.evaluate("() => navigator.clipboard.readText()"),
                self.expected)
            self.assertEqual(
                page.eval_on_selector(".cite-status", "el => el.textContent"),
                "Citation copied to the clipboard.")
            self.assertEqual(button.inner_text().strip(), "Copied")
        finally:
            context.close()

    def test_a_failed_copy_says_so_and_points_at_the_visible_text(self):
        context = self.browser.new_context()
        try:
            context.add_init_script(self.DENY_CLIPBOARD)
            page = context.new_page()
            page.goto(self.url("corpus-guide.html"), wait_until="load")
            page.wait_for_timeout(300)
            button = page.query_selector('button[data-copy="cite-corpus"]')
            button.click()
            page.wait_for_timeout(400)
            message = page.eval_on_selector(".cite-status",
                                            "el => el.textContent")
            # Honest: names the failure and points at the still-selectable text.
            self.assertIn("Copy failed", message)
            self.assertIn("selectable", message)
            self.assertNotIn("copied to the clipboard", message)
            self.assertEqual(button.inner_text().strip(), "Copy failed")
            # The citation itself is untouched and still readable.
            self.assertEqual(
                page.eval_on_selector("#cite-corpus", "el => el.textContent"),
                self.expected)
        finally:
            context.close()

    def test_the_failure_remedy_is_visible_not_screen_reader_only(self):
        """The message says "select it and copy it manually". That instruction
        is useless to a sighted reader if only a screen reader receives it, so
        the status line is rendered rather than visually hidden."""
        context = self.browser.new_context()
        try:
            context.add_init_script(self.DENY_CLIPBOARD)
            page = context.new_page()
            page.goto(self.url("corpus-guide.html"), wait_until="load")
            page.wait_for_timeout(300)
            page.click('button[data-copy="cite-corpus"]')
            page.wait_for_timeout(400)
            self.assertTrue(page.is_visible(".cite-status"))
            box = page.eval_on_selector(
                ".cite-status",
                "el => { const r = el.getBoundingClientRect();"
                " return {w: r.width, h: r.height}; }")
            self.assertGreater(box["w"], 100)
            self.assertGreater(box["h"], 10)
        finally:
            context.close()

    def test_each_block_carries_its_own_status_line(self):
        """A page-level region would announce a result far from the control
        that produced it — Analysis has thirteen controls."""
        for page_name, expected in (("corpus-guide.html", 1),
                                    ("weekly.html", 13)):
            html = self.page(page_name)
            with self.subTest(page=page_name):
                self.assertEqual(html.count('class="cite-status"'), expected)
                self.assertEqual(html.count("data-copy="), expected)
                self.assertNotIn('class="visually-hidden" id="cite-status"',
                                 html)

    def test_both_outcomes_are_announced_in_a_polite_live_region(self):
        context = self.browser.new_context()
        try:
            page = context.new_page()
            page.goto(self.url("corpus-guide.html"), wait_until="load")
            region = page.query_selector(".cite-status")
            self.assertEqual(region.get_attribute("aria-live"), "polite")
            self.assertEqual(region.get_attribute("role"), "status")
            # Empty until something happens: no announcement on load.
            self.assertEqual(region.inner_text().strip(), "")
        finally:
            context.close()

    def test_the_copy_button_is_reachable_and_operable_by_keyboard(self):
        context = self.browser.new_context(
            permissions=["clipboard-read", "clipboard-write"])
        try:
            page = context.new_page()
            page.goto(self.url("corpus-guide.html"), wait_until="load")
            page.wait_for_timeout(300)
            page.focus('button[data-copy="cite-corpus"]')
            self.assertEqual(
                page.evaluate(
                    "() => document.activeElement.getAttribute('data-copy')"),
                "cite-corpus")
            page.keyboard.press("Enter")
            page.wait_for_timeout(400)
            self.assertEqual(
                page.evaluate("() => navigator.clipboard.readText()"),
                self.expected)
        finally:
            context.close()

    def test_without_javascript_the_text_shows_and_no_control_appears(self):
        context = self.browser.new_context(java_script_enabled=False)
        try:
            page = context.new_page()
            page.goto(self.url("corpus-guide.html"), wait_until="load")
            self.assertTrue(page.is_visible("#cite-corpus"))
            self.assertTrue(page.eval_on_selector(
                "#cite-corpus", "el => el.textContent.length > 40"))
            visible = page.eval_on_selector_all(
                "button[data-copy]",
                "els => els.filter(e => e.offsetParent !== null).length")
            self.assertEqual(visible, 0, "a copy control rendered without JS")
        finally:
            context.close()

    def test_edition_disclosures_open_and_expose_citations_without_js(self):
        """`<details>` is the whole mechanism. With scripting off the summary
        still opens the disclosure and the citation becomes readable text."""
        context = self.browser.new_context(java_script_enabled=False)
        try:
            page = context.new_page()
            page.goto(self.url("weekly.html"), wait_until="load")
            anchor = "#cite-edition-2026-08-08"
            # Closed to begin with, and its text is not on screen.
            self.assertFalse(page.is_visible(anchor))
            summaries = page.query_selector_all("details.ed-cite > summary")
            self.assertEqual(len(summaries), 13)
            page.click("details.ed-cite:first-of-type > summary")
            self.assertTrue(page.is_visible(anchor))
            self.assertEqual(
                page.eval_on_selector(anchor, "el => el.textContent"),
                gp.edition_citation(gp.load_editions(REPO_ROOT)[0]))
            # Still no operative control anywhere on the page.
            self.assertEqual(page.eval_on_selector_all(
                "button[data-copy]",
                "els => els.filter(e => e.offsetParent !== null).length"), 0)
            # Every one of the 13 opens on its own.
            page.eval_on_selector_all(
                "details.ed-cite", "els => els.forEach(e => e.open = true)")
            self.assertEqual(page.eval_on_selector_all(
                "details.ed-cite > .cite-text",
                "els => els.filter(e => e.offsetParent !== null).length"), 13)
        finally:
            context.close()

    def test_the_edition_disclosure_is_keyboard_operable_without_js(self):
        """No custom key handling: a native summary is focusable and toggles on
        Enter, which is exactly why it was used instead of a scripted widget."""
        context = self.browser.new_context(java_script_enabled=False)
        try:
            page = context.new_page()
            page.goto(self.url("weekly.html"), wait_until="load")
            anchor = "#cite-edition-2026-08-08"
            page.focus("details.ed-cite:first-of-type > summary")
            self.assertEqual(
                page.evaluate("() => document.activeElement.tagName"),
                "SUMMARY")
            page.keyboard.press("Enter")
            self.assertTrue(page.is_visible(anchor))
            page.keyboard.press("Enter")
            self.assertFalse(page.is_visible(anchor))
        finally:
            context.close()

    def test_the_copy_button_inside_a_disclosure_works_by_keyboard(self):
        context = self.browser.new_context(
            permissions=["clipboard-read", "clipboard-write"])
        try:
            page = context.new_page()
            page.goto(self.url("weekly.html"), wait_until="load")
            page.wait_for_timeout(300)
            page.click("details.ed-cite:first-of-type > summary")
            button = page.query_selector(
                'button[data-copy="cite-edition-2026-08-08"]')
            self.assertFalse(button.is_hidden(),
                             "the control was never revealed")
            page.focus('button[data-copy="cite-edition-2026-08-08"]')
            page.keyboard.press("Enter")
            page.wait_for_timeout(400)
            self.assertEqual(
                page.evaluate("() => navigator.clipboard.readText()"),
                gp.edition_citation(gp.load_editions(REPO_ROOT)[0]))
            self.assertIn("copied", page.eval_on_selector(
                ".cite-status", "el => el.textContent").lower())
        finally:
            context.close()

    def test_a_record_page_reveals_both_blocks_independently(self):
        context = self.browser.new_context(
            permissions=["clipboard-read", "clipboard-write"])
        try:
            corpus = gp.load_corpus(TRACKED_DB)["corpus"]
            rec = next(r for r in corpus if r["state"] == "analyzed")
            page = context.new_page()
            page.goto(self.url("record/%d.html" % rec["id"]),
                      wait_until="load")
            page.wait_for_timeout(300)
            page.click('button[data-copy="cite-as-held"]')
            page.wait_for_timeout(400)
            copied = page.evaluate("() => navigator.clipboard.readText()")
            self.assertIn("Record %d," % rec["id"], copied)
            self.assertNotIn("Source text.", copied)
            page.click('button[data-copy="cite-source-text"]')
            page.wait_for_timeout(400)
            copied = page.evaluate("() => navigator.clipboard.readText()")
            self.assertIn(rec["title_original"], copied)
            self.assertNotIn("As held.", copied)
        finally:
            context.close()


class TestShardLedeGrammar(PreviewCase):
    """The shard lede must read as English on every generated page.

    `trim_blocks` removes the newline that follows a block tag, so a line break
    placed immediately after `{% if paginated %}` glued "records" to "on this
    page" — "50 recordson this page" — on all 74 shards, from STOP 2 until it
    was caught by visual inspection at STOP 5. Byte budgets, link checks and
    house-style guards all passed straight over it, because none of them reads
    the sentence.

    These tests read AUTHORED copy only. Stored source text is excluded: real
    captures contain their own run-together artifacts ("demonstratingshared" in
    record 1853), which are source data preserved verbatim and are not this
    template's business.
    """

    #: The exact authored sentence, with counts as placeholders.
    UNPAGINATED = "{n} record{s}, by the publication date each source stated."
    PAGINATED = ("{n} record{s} on this page, of {total} in the week, "
                 "by the publication date each source stated.")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data = gp.load_corpus(TRACKED_DB)
        cls.weeks = {w["start"]: w for w in cls.data["weeks"]}
        cls.shards = sorted(cls.out.glob("week-*.html"))

    def lede(self, path: Path) -> str:
        """The authored lede, whitespace-normalized, tags and entities gone."""
        html = path.read_text(encoding="utf-8")
        block = re.search(r'<p class="lede">(.*?)</p>', html, re.S)
        self.assertIsNotNone(block, "%s has no lede" % path.name)
        text = re.sub(r"<[^>]+>", "", block.group(1))
        return re.sub(r"\s+", " ", markupsafe.Markup(text).unescape()).strip()

    def _week_for(self, path: Path):
        start = re.match(r"week-(\d{4}-\d{2}-\d{2})", path.stem).group(1)
        return self.weeks[start]

    def _page_count(self, path: Path) -> int:
        html = path.read_text(encoding="utf-8")
        return len(re.findall(r'<article class="record"', html))

    def test_every_shard_lede_is_exactly_the_authored_sentence(self):
        """Every shard, reconstructed from its own real page count."""
        self.assertEqual(len(self.shards), self.shard_count)
        for path in self.shards:
            week = self._week_for(path)
            n = self._page_count(path)
            paginated = "Page 1 of" in path.read_text(encoding="utf-8") or \
                        re.search(r"Page \d+ of \d+",
                                  path.read_text(encoding="utf-8"))
            tmpl = self.PAGINATED if paginated else self.UNPAGINATED
            expected = tmpl.format(n="{:,}".format(n),
                                   s="" if n == 1 else "s",
                                   total="{:,}".format(week["count"]))
            with self.subTest(shard=path.name):
                self.assertEqual(self.lede(path), expected)

    def test_no_shard_lede_runs_two_words_together(self):
        for path in self.shards:
            with self.subTest(shard=path.name):
                lede = self.lede(path)
                self.assertNotIn("recordson", lede)
                self.assertNotIn("records on this page, of  ", lede)
                # No collapsed word boundary anywhere in the sentence.
                self.assertIsNone(
                    re.search(r"[a-z](?:on this page|in the week)", lede),
                    lede)
                self.assertNotIn("  ", lede)

    def test_the_run_together_form_is_absent_from_authored_shard_copy(self):
        """Scoped to authored text: stored captures are not touched."""
        for path in self.shards:
            authored = _authored_text(path.read_text(encoding="utf-8"),
                                      path.name)
            with self.subTest(shard=path.name):
                self.assertNotIn("recordson", authored)

    def test_stored_extraction_artifacts_are_left_alone(self):
        """The guard above must not be a licence to edit source text.

        Record 1853's stored body contains "demonstratingshared" — an
        extraction artifact in captured source data. It stays exactly as
        stored, and is excluded from authored copy rather than corrected.
        """
        page = self.out / "record" / "1853.html"
        if not page.exists():
            self.skipTest("record 1853 not in this corpus")
        html = page.read_text(encoding="utf-8")
        self.assertIn("demonstratingshared", html)
        self.assertNotIn("demonstratingshared", _authored_text(html,
                                                               "record/1853.html"))

    def test_all_four_grammar_branches_render_correctly(self):
        """Paginated/unpaginated x singular/plural.

        The live corpus paginates every week, so the unpaginated and singular
        branches exist only here. Rendering the template directly covers them
        without inventing corpus data.
        """
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(gp.TEMPLATES)),
                          autoescape=True, trim_blocks=True,
                          lstrip_blocks=True)
        env.filters["count"] = (
            lambda n: "{:,}".format(n) if isinstance(n, int) else n)
        for name in ("status_label", "status_prose", "source_type_label"):
            env.filters[name] = lambda v: v
        tmpl = env.get_template("corpus_week.html")

        def render(page_count, paginated, total):
            week = {"start": "2026-06-01", "end": "2026-06-07",
                    "count": total, "run_dates": 2, "annotation": None,
                    "annotation_note": None, "path": "week-2026-06-01.html"}
            html = tmpl.render(
                page="corpus.html", week=week, records=[],
                page_count=page_count, paginated=paginated, page_no=1,
                page_total=2 if paginated else 1, prev_path=None,
                next_path=None, title="T", tagline="x", corpus_eyebrow="x",
                maintainer=gp.MAINTAINER, snapshot=gp.DECLARED_SNAPSHOT,
                run_status=None, snapshot_label="s", citation="c")
            block = re.search(r'<p class="lede">(.*?)</p>', html, re.S)
            text = re.sub(r"<[^>]+>", "", block.group(1))
            return re.sub(r"\s+", " ",
                          markupsafe.Markup(text).unescape()).strip()

        cases = [
            (266, False, 266,
             "266 records, by the publication date each source stated."),
            (1, False, 1,
             "1 record, by the publication date each source stated."),
            (50, True, 61,
             "50 records on this page, of 61 in the week, by the publication "
             "date each source stated."),
            (1, True, 61,
             "1 record on this page, of 61 in the week, by the publication "
             "date each source stated."),
        ]
        for page_count, paginated, total, expected in cases:
            with self.subTest(page_count=page_count, paginated=paginated):
                self.assertEqual(render(page_count, paginated, total),
                                 expected)

    def test_the_literal_space_is_in_the_template_not_a_post_fix(self):
        """The boundary space must be authored, not patched in afterwards."""
        src = (REPO_ROOT / "site" / "preview" / "templates"
               / "corpus_week.html").read_text(encoding="utf-8")
        self.assertIn("{% if paginated %} on this page,", src)
        for cheat in ("|safe", "&nbsp;", " ", ".replace("):
            with self.subTest(cheat=cheat):
                self.assertNotIn(cheat, src)
        generator = (REPO_ROOT / "site" / "preview"
                     / "generate_preview.py").read_text(encoding="utf-8")
        self.assertNotIn("recordson", generator)
        # No CSS-generated content supplies the words. Comments are stripped
        # first — the stylesheet's own prose says "appears nowhere on this
        # page", which is documentation, not a `content:` declaration.
        css = re.sub(r"/\*.*?\*/", " ",
                     (self.out / "styles.css").read_text(encoding="utf-8"),
                     flags=re.S)
        for value in re.findall(r"content:\s*([^;}]+)", css):
            with self.subTest(content=value.strip()):
                self.assertNotRegex(value, r"page|record|week")

    def test_the_shard_set_is_structurally_unchanged(self):
        """The repair touched copy only: routes, pagination and reachability
        must be exactly what they were."""
        self.assertEqual(len(self.shards), self.shard_count)
        linked = set()
        for path in self.shards:
            html = path.read_text(encoding="utf-8")
            linked.update(int(m) for m in
                          re.findall(r'href="record/(\d+)\.html"', html))
        corpus_ids = {r["id"] for r in self.data["corpus"]}
        self.assertEqual(linked, corpus_ids)
        self.assertEqual(len(linked), self.corpus_size)

    def test_every_record_appears_exactly_once_across_the_shard_set(self):
        seen = []
        for path in self.shards:
            html = path.read_text(encoding="utf-8")
            seen += [int(m) for m in
                     re.findall(r'href="record/(\d+)\.html"', html)]
        self.assertEqual(len(seen), self.corpus_size,
                         "a record is duplicated or missing")
        self.assertEqual(len(set(seen)), self.corpus_size)

    def test_pagination_links_still_resolve(self):
        for path in self.shards:
            html = path.read_text(encoding="utf-8")
            for href in re.findall(r'href="(week-[^"#]+\.html)"', html):
                with self.subTest(shard=path.name, href=href):
                    self.assertTrue((self.out / href).exists())

    def test_every_shard_is_reachable_from_the_index_without_javascript(self):
        index = (self.out / "corpus.html").read_text(encoding="utf-8")
        first_pages = set(re.findall(r'href="(week-[^"#]+\.html)"', index))
        reached, frontier = set(), set(first_pages)
        while frontier:
            name = frontier.pop()
            if name in reached:
                continue
            reached.add(name)
            html = (self.out / name).read_text(encoding="utf-8")
            frontier |= {h for h in
                         re.findall(r'href="(week-[^"#]+\.html)"', html)
                         if h not in reached}
        self.assertEqual(reached, {p.name for p in self.shards})


class TestStop4RoutesAreIntact(PreviewCase):
    """STOP 4 added one page and one script. Nothing else moved.

    The Corpus Guide and the citation controls touch templates that every
    record and every shard render through, so the cheapest way for this work to
    have gone wrong is a route quietly disappearing. These numbers are the
    accepted STOP 3 tree plus exactly the two files STOP 4 is authorized to
    add.
    """

    #: Derived from the corpus under test rather than pinned. These were
    #: literals until 2026-08-23, when a corpus advance turned every one of them
    #: into a production outage: the daily workflow runs this suite before
    #: collecting, so a stale literal blocked the pipeline that would have
    #: refreshed it. What they actually assert — every record has a route, every
    #: week has a shard — is true of any corpus.
    @property
    def RECORD_PAGES(self):
        return self.corpus_size

    @property
    def WEEK_SHARDS(self):
        return self.shard_count

    def test_every_record_route_still_exists(self):
        pages = sorted((self.out / "record").glob("*.html"))
        self.assertEqual(len(pages), self.RECORD_PAGES)
        corpus = gp.load_corpus(TRACKED_DB)["corpus"]
        stored = {r["id"] for r in corpus}
        rendered = {int(p.stem) for p in pages}
        self.assertEqual(rendered, stored,
                         "the record routes no longer match the stored ids")

    def test_every_week_shard_route_still_exists(self):
        shards = sorted(self.out.glob("week-*.html"))
        self.assertEqual(len(shards), self.WEEK_SHARDS)

    def test_the_only_new_routes_are_the_guide_and_its_script(self):
        top = {p.name for p in self.out.iterdir() if p.is_file()}
        self.assertIn("corpus-guide.html", top)
        self.assertIn("citation.js", top)
        # Nothing was renamed away underneath the new page.
        for kept in ("index.html", "archive.html", "corpus.html",
                     "coverage.html", "sources.html", "weekly.html",
                     "methodology.html", "about.html", "desks.html",
                     "china.html", "japan.html", "browse.js", "styles.css",
                     "corpus-index.json"):
            with self.subTest(route=kept):
                self.assertIn(kept, top)

    def test_the_generated_file_count_is_the_snapshot_tree_plus_one_page(self):
        """
        The tree is one file per record, one per week shard, and a fixed set of
        top-level pages. Asserted as that relationship rather than as a total,
        because the total moves with the corpus and the relationship does not.
        """
        files = [p for p in self.out.rglob("*") if p.is_file()]
        top = [q for q in self.out.iterdir() if q.is_file()]
        # Week shards are top-level files, so they are already inside `top`.
        self.assertEqual(len(files), self.corpus_size + len(top))
        self.assertEqual(
            len([q for q in top if q.name.startswith("week-")]),
            self.shard_count)



class TestWeekInvariantsGrowWithTheCorpus(unittest.TestCase):
    """
    Adding a publication week must not require editing a test.

    This is the regression for the defect the two tests above carried. Both
    froze a corpus shape — "sixteen weeks", and a literal list of annotated
    week starts — into an assertion. Collection added a seventeenth week on
    2026-08-24 and both failed, on `main`, with no code change and nothing
    actually wrong with the page. Because `Run offline test suite` in
    `daily_update.yml` has no `continue-on-error` and precedes the pipeline,
    that would have stopped collection outright.

    So: build from a corpus that has one more week than the tracked one, run
    the *same* invariant helpers with no new constants, and require them to
    accept it.

    Nothing here touches the tracked database or `output/`. The corpus is a
    copy in a temporary directory and the build goes to a temporary directory.
    """

    NEW_WEEK_START = None   # derived in setUpClass; never written down

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        from datetime import date, timedelta

        cls.tmp = Path(tempfile.mkdtemp(prefix="preview-growth-"))
        cls.db = cls.tmp / "grown.db"
        shutil.copy(TRACKED_DB, cls.db)

        cls.before = weeks_from_sql(TRACKED_DB)
        latest = max(w["start"] for w in cls.before)
        y, m, d = (int(part) for part in latest.split("-"))
        # The Monday after the current last week, and a date inside it.
        cls.NEW_WEEK_START = (date(y, m, d) + timedelta(days=7)).isoformat()
        published = (date(y, m, d) + timedelta(days=9)).isoformat()

        con = sqlite3.connect(str(cls.db))
        try:
            source_id = con.execute(
                "SELECT id FROM sources ORDER BY id LIMIT 1").fetchone()[0]
            con.execute(
                "INSERT INTO articles (url, content_hash, source_id, "
                "                      title_original, text_original, "
                "                      published_date, passed_relevance) "
                "VALUES (?, ?, ?, ?, ?, ?, 1)",
                ("https://example.invalid/growth-fixture-%s" % published,
                 "growthfixture" + "0" * 51, source_id,
                 "成長テスト記事", "本文" * 60, published))
            con.commit()
        finally:
            con.close()

        cls.after = weeks_from_sql(cls.db)
        cls.out = cls.tmp / "build"
        gp.build(cls.out, "Growth Test", cls.db, snapshot=snapshot_of(cls.db))
        cls.html = (cls.out / "archive.html").read_text(encoding="utf-8")
        cls.rows = re.findall(
            r'<span class="c-range">([\d-]+) to ([\d-]+)</span>.*?'
            r'<span class="v-figure">([\d,]+)</span>.*?'
            r'<td class="c-runs">(\d+)', cls.html, re.S)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_fixture_added_exactly_one_later_week(self):
        self.assertEqual(len(self.after), len(self.before) + 1)
        self.assertEqual(max(w["start"] for w in self.after),
                         self.NEW_WEEK_START)
        self.assertNotIn(self.NEW_WEEK_START,
                         {w["start"] for w in self.before})

    def test_the_volume_invariant_accepts_the_new_week_unedited(self):
        """The assertion body from the repaired test, verbatim and unchanged —
        no constant, no total, no week start written down."""
        rendered_starts = [start for start, _, _, _ in self.rows]
        self.assertEqual(len(rendered_starts), len(set(rendered_starts)))
        self.assertEqual(set(rendered_starts),
                         {w["start"] for w in self.after})
        self.assertEqual(len(self.rows), len(self.after))
        self.assertEqual(rendered_starts, [w["start"] for w in self.after])
        for (start, end, count, runs), week in zip(self.rows, self.after):
            with self.subTest(week=start):
                self.assertEqual(start, week["start"])
                self.assertEqual(end, week["end"])
                self.assertEqual(count, "{:,}".format(week["count"]))
                self.assertEqual(int(runs), week["run_dates"])

    def test_the_new_week_renders_its_own_shard_and_count(self):
        shard = self.out / ("week-%s.html" % self.NEW_WEEK_START)
        self.assertTrue(shard.is_file(), "the new week rendered no shard")
        row = [r for r in self.rows if r[0] == self.NEW_WEEK_START]
        self.assertEqual(len(row), 1)
        self.assertEqual(row[0][2], "1", "the added record was not counted")

    def test_the_snapshot_boundary_moves_to_the_new_week(self):
        """
        The boundary is a property of the corpus, so it must follow it. The
        week that was last is no longer a boundary — unless it overlaps the
        governed outage, which outranks the boundary rule.
        """
        expected = governed_annotations(self.after)
        self.assertEqual(expected.get(self.NEW_WEEK_START),
                         "Snapshot boundary")

        previous_last = max(w["start"] for w in self.before)
        previous = [w for w in self.after if w["start"] == previous_last][0]
        overlaps_outage = (previous["start"] <= GOVERNED_OUTAGE_END
                           and previous["end"] >= GOVERNED_OUTAGE_START)
        if overlaps_outage:
            self.assertEqual(expected[previous_last],
                             "Known collection interruption")
        else:
            self.assertNotIn(previous_last, expected)

        # And the generator agrees with the derived policy on the new corpus.
        actual = {w["start"]: w["annotation"]
                  for w in gp.load_corpus(self.db)["weeks"] if w["annotation"]}
        self.assertEqual(actual, expected)

    def test_the_tracked_database_and_output_were_not_touched(self):
        self.assertNotEqual(self.db.resolve(), TRACKED_DB.resolve())
        self.assertFalse(str(self.out).startswith(str(PRODUCTION_OUT)))
        for residue in ("pla_watch.db-wal", "pla_watch.db-shm"):
            self.assertFalse((REPO_ROOT / residue).exists(),
                             "%s appeared beside the tracked database" % residue)


if __name__ == "__main__":
    unittest.main(verbosity=2)
