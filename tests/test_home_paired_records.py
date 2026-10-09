"""Current home evidence contracts; old C1 six-record layout is superseded.

Retain fixture horizon, original-title rejection and fallback macro checks.
October photograph-led reader layout is measured by verify_frontend_candidate;
the governed counts, newest records and machine labels are checked below.
"""
from __future__ import annotations

import datetime as dt

import html as html_mod

import json

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

from scripts.reconcile_db import read_only                       # noqa: E402

TRACKED_DB = REPO_ROOT / "pla_watch.db"

TEMPLATES = REPO_ROOT / "site" / "preview" / "templates"

CSS = REPO_ROOT / "site" / "preview" / "styles.css"

HOME_RECORDS = 6

_FIXTURE_HORIZON = None

def _corpus_freshness():
    """
    The tracked corpus's newest `published_date`, or None.

    Read through `reconcile_db.read_only`, which copies the database and its
    sidecars to a scratch directory and reads the copy. Never
    `sqlite3.connect()` on the tracked file, even to read: it is WAL-mode, so an
    open can leave a -wal/-shm beside it. That is the run-475 defect, and
    `test_workflow_failure_paths` enforces the rule against this whole suite.
    """
    if not TRACKED_DB.exists():
        return None
    with read_only(str(TRACKED_DB)) as con:
        return con.execute(
            "SELECT MAX(published_date) FROM articles "
            " WHERE published_date GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*'").fetchone()[0]

def fixture_date(offset: int = 0) -> str:
    """`offset` days before the fixture horizon, as `YYYY-MM-DD`."""
    global _FIXTURE_HORIZON
    if _FIXTURE_HORIZON is None:
        newest = _corpus_freshness()
        base = (dt.date.fromisoformat(newest[:10]) if newest
                else dt.date(2026, 9, 14))
        _FIXTURE_HORIZON = base + dt.timedelta(days=HOME_RECORDS)
    return (_FIXTURE_HORIZON - dt.timedelta(days=offset)).isoformat()

ZH = "zh-Hans"

EN = "en"

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

def fixture_corpus(tmp: Path, rows: list, name="fixture"):
    """Return a corpus copy whose newest analyzed records match `rows`."""
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
             row.get("published_date") or fixture_date(),
             sources[slug]["id"], record_id))
    con.commit()
    con.close()

    # The fixture verifies its own premise: the records it rewrote are the ones
    # the page actually selected. Without this a mis-ordered fixture would make
    # every assertion below vacuously true.
    selected = gp.load_corpus(db)["recent"][:len(rows)]
    if [r["id"] for r in selected] != ids:
        raise AssertionError("fixture did not become the newest records")
    return db, selected

def build_fixture(tmp: Path, rows: list, name="fixture"):
    """
    Render a home page whose six newest analyzed records are exactly `rows`.

    `rows` is newest-first. Each entry may set `title_english`,
    `title_original` (None or "" for a record that has none) and `source_slug`;
    dates are assigned descending from `fixture_date()`, a horizon derived
    from the corpus rather than hard-coded, so
    `dates=True` produces a mixed-date register and the default produces one
    date shared by all six.
    """
    db, selected = fixture_corpus(tmp, rows, name)
    out = tmp / ("%s-build" % name)
    gp.build(out, gp.PUBLIC_TITLE, db, snapshot=gp.snapshot_from_corpus(db))
    home = (out / "index.html").read_text(encoding="utf-8")
    return home, selected, out

def homogeneous_rows(count=HOME_RECORDS):
    return [{"title_english": "Record %d in English" % n,
             "title_original": "第%d号原文标题" % n,
             "source_slug": "pla_daily",
             "published_date": fixture_date()} for n in range(count)]

class TestTheFixtureHorizonOutranksTheCorpus(unittest.TestCase):
    """
    The premise every controlled fixture in this file rests on.

    `build_fixture` rewrites the six newest analyzed records and then verifies
    that they really are the six the page selected. That verification can only
    succeed while the dates the fixture stamps outrank every real publication
    date in the corpus — including the OLDEST row of a descending series.

    This was a literal (`2026-09-20`) until the corpus advanced to within six
    days of it and three provenance cases failed with "fixture did not become
    the newest records". The literal is gone; this case is what stops a derived
    horizon from quietly drifting back into range.
    """

    def test_the_oldest_fixture_row_is_still_newer_than_the_whole_corpus(self):
        if not TRACKED_DB.exists():
            self.skipTest("tracked corpus not present")
        newest = _corpus_freshness()
        self.assertIsNotNone(newest, "corpus carries no usable published_date")
        oldest_fixture_row = fixture_date(HOME_RECORDS - 1)
        self.assertGreater(
            oldest_fixture_row, newest[:10],
            "the fixture horizon has drifted into the corpus: the oldest row "
            "of a %d-day descending series (%s) no longer outranks the "
            "corpus's newest record (%s), so build_fixture's own premise "
            "check will fail" % (HOME_RECORDS, oldest_fixture_row, newest[:10]))

    def test_the_horizon_is_derived_rather_than_written_down(self):
        """A date literal here is the defect, not the fix."""
        source = Path(__file__).read_text(encoding="utf-8")
        body = source.split("class TestTheFixtureHorizon", 1)[0]
        self.assertNotIn(
            "published_date = '2026-", body,
            "a corpus rewrite is stamping a hard-coded date again")

class HomeCase(unittest.TestCase):
    """One build of the tracked corpus, shared by the structural assertions."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="c1-home-"))
        cls.out = cls.tmp / "build"
        # These historical-issue contracts deliberately exercise the state
        # before a native Brief leads. Real publication must not change that
        # fixture; native-first behavior is covered by the publication suite.
        cls.briefs = cls.tmp / "briefs"
        cls.briefs.mkdir()
        gp.build(cls.out, gp.PUBLIC_TITLE, TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(TRACKED_DB),
                 briefs_dir=cls.briefs)
        cls.home = (cls.out / "index.html").read_text(encoding="utf-8")
        cls.data = gp.load_corpus(TRACKED_DB)
        cls.view = PublicView(TRACKED_DB)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def dateline(self) -> str:
        """
        The home page's dateline is the opening's LEDGER.

        It moved there with the CMW revival on 2026-09-15 and nothing else
        about it changed: same view model, same five rows, same labels, same
        run link as its footer. It is the opening's right-hand column now
        instead of a strip above the content, so `base.html` skips the strip
        on index.html and `home.html` renders the same context in its place.
        Every interior page still gets the strip.

        The contract below is unchanged, and that is the point of naming this
        helper rather than the markup: consolidation is a layout change, not
        permission to drop a disclosure.
        """
        self.assertIn('class="ledger"', self.home,
                      "the home page has no dateline ledger")
        after = self.home.split('class="ledger"', 1)[1]
        return after.split("</section>", 1)[0]

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

if __name__ == "__main__":                                  # pragma: no cover
    unittest.main()


class TestReviewedHome(HomeCase):
    def test_fresh_tree_contains_pinned_natural_jpeg_fallback(self):
        import hashlib
        source = REPO_ROOT / "site/assets/editorial/reagan-jmsdf-2015.jpg"
        emitted = self.out / "assets/editorial/reagan-jmsdf-2015.jpg"
        self.assertEqual(hashlib.sha256(emitted.read_bytes()).hexdigest(),
                         hashlib.sha256(source.read_bytes()).hexdigest())

    def test_one_reading_h1_and_selected_identity(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.home, 'html.parser')
        self.assertEqual(len(soup.find_all('h1')), 1)
        self.assertEqual(soup.h1.get_text(' ', strip=True), 'The region, in its own words.')
        self.assertIn('selected-ipr/ipr-ivory-', str(soup.header))

    def test_current_snapshot_and_search_scope(self):
        self.assertIn('{:,} preserved records'.format(gp.snapshot_from_corpus(TRACKED_DB)['expected_records']), self.home)
        self.assertIn('Search covers titles.', self.home)
        self.assertIn('Original texts and provenance', self.home)
        self.assertIn('Coverage is selective', self.home)
        self.assertIn('concentrated in Chinese sources', self.home)

    def test_latest_rows_keep_governed_titles_languages_and_links(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.home, 'html.parser')
        rows = soup.select('.home-recent .record-row')
        self.assertEqual(len(rows), 4)
        by_id = {r['id']: r for r in self.data['corpus']}
        for row in rows:
            link = row.select_one('h3 a')
            governed = by_id[int(Path(link['href']).stem)]
            record = BeautifulSoup((self.out / link['href']).read_text(), 'html.parser')
            self.assertEqual(link.get_text(' ', strip=True), record.h1.get_text(' ', strip=True))
            self.assertEqual(link.get_text(' ', strip=True),
                             governed['title_english'] or governed['title_original'])
            original = row.select_one('.original')
            paired = bool(governed['title_english'] and governed['title_original'].strip()
                          != governed['title_english'].strip())
            self.assertEqual(original is not None, paired)
            if paired:
                self.assertEqual(original.get_text(' ', strip=True), governed['title_original'])
                self.assertEqual(original.get('lang'), governed['language_tag'] or None)
            else:
                self.assertEqual(row.h3.get('lang'),
                                 (governed['language_tag'] or None)
                                 if not governed['title_english'] else None)
        # The selected analyzed record exercises the translated title pair
        # even when all four newest arrivals have only original titles.
        selected = soup.select_one('.home-selected')
        governed = by_id[int(Path(selected.select_one('h3 a')['href']).stem)]
        original = selected.select_one('.home-selected-original')
        self.assertIsNotNone(original)
        self.assertEqual(original.get_text(' ', strip=True), governed['title_original'])
        self.assertEqual(original.get('lang'), governed['language_tag'])

    def test_human_brief_and_machine_record_labels_are_explicit(self):
        self.assertIn('Human-controlled analysis', self.home)
        self.assertIn('Machine translation', self.home)
        self.assertIn('Latest analysis', self.home)

    def test_self_hosted_faces_and_native_mobile_menu(self):
        self.assertIn('href="fonts.css"', self.home)
        self.assertNotIn('fonts.googleapis.com', self.home)
        self.assertIn('class="shell-menu nav-mobile"', self.home)
