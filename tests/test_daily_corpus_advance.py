"""
The daily render describes the corpus it is actually rendering.

This is the regression suite for a P0 that stopped production. After the launch
made `indo-pacific-record` the default mode, `render_site()` defaulted its
snapshot to `DECLARED_SNAPSHOT` — the accepted release metadata for 2026-08-26,
3,574 records. Collection then added 37 records. Every subsequent render aborted
with `SnapshotMismatch`, and because `daily_update.yml` runs the offline suite
before `Run pipeline` with no `continue-on-error`, a red suite would have
stopped collection outright.

The distinction this file pins:

  omitted snapshot    the daily run. Derive the identity from the corpus in
                      hand and render it truthfully.
  explicit snapshot   a release build. Render exactly that declared corpus, or
                      fail before writing anything.
  DECLARED_SNAPSHOT   immutable accepted release metadata. Not the daily corpus
                      identity, and not advanced by any of this.

Every case below builds against a TEMPORARY COPY of the corpus. Nothing here
opens the tracked database for writing, and `tests/test_local_db_reads.py`
covers that separately.
"""
from __future__ import annotations

import importlib.util
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TRACKED_DB = REPO_ROOT / "pla_watch.db"

#: A real-looking origin. `build()` refuses reserved and placeholder domains
#: without an explicit opt-in, and that refusal is not what these tests are for.
TEST_ORIGIN = "https://a-real-domain.org"


def load_render():
    spec = importlib.util.spec_from_file_location(
        "site_render_probe", REPO_ROOT / "site" / "render.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_gp():
    spec = importlib.util.spec_from_file_location(
        "generate_preview", REPO_ROOT / "site" / "preview" / "generate_preview.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_preview"] = module
    spec.loader.exec_module(module)
    return module


def copy_corpus(into: Path) -> Path:
    """A writable copy of the tracked corpus. The original is never opened."""
    target = into / "corpus.db"
    shutil.copy2(TRACKED_DB, target)
    return target


def drop_records(db: Path, count: int) -> int:
    """
    Remove `count` records from a COPY, newest ids first, and report the size
    that remains. Deleting from the top keeps the weekly and edition structure
    the renderer depends on intact.
    """
    con = sqlite3.connect(str(db))
    ids = [r[0] for r in con.execute(
        "SELECT id FROM articles ORDER BY id DESC LIMIT ?", (count,))]
    con.executemany("DELETE FROM articles WHERE id = ?", [(i,) for i in ids])
    con.commit()
    remaining = con.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    con.close()
    return remaining


def rendered_totals(out: Path) -> set:
    """
    Every comma-grouped number the public metric surfaces state.

    Read from the built pages rather than from the build report, because the
    report is what the renderer believes and these are what a reader is told.
    """
    found = set()
    for name in ("index.html", "methodology.html", "corpus.html"):
        page = out / name
        if page.exists():
            for raw in re.findall(r"\b\d{1,3}(?:,\d{3})+\b",
                                  page.read_text("utf-8")):
                found.add(int(raw.replace(",", "")))
    return found


@unittest.skipUnless(TRACKED_DB.exists(), "production database not present")
class TestTheDailyRenderFollowsTheCorpus(unittest.TestCase):
    """
    The repair, proved by mutation: change the corpus, and the figures the
    public pages state must change with it.
    """

    @classmethod
    def setUpClass(cls):
        cls.render = load_render()
        cls.gp = load_gp()
        cls.tmp = Path(tempfile.mkdtemp(prefix="corpus-advance-"))
        cls.db = copy_corpus(cls.tmp)
        cls.remaining = drop_records(cls.db, 40)
        cls.declared = dict(cls.gp.DECLARED_SNAPSHOT)
        cls.out = cls.tmp / "built"
        cls.report = cls.render.render_site(
            output_dir=cls.out, db_path=cls.db, environ={},
            site_origin=TEST_ORIGIN)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_temporary_corpus_really_differs_from_the_declared_one(self):
        """Otherwise every assertion below would pass for the wrong reason."""
        self.assertNotEqual(self.remaining, self.declared["expected_records"])

    def test_render_site_succeeds_with_no_snapshot_supplied(self):
        self.assertEqual(self.report["mode"], self.render.INDO_PACIFIC_RECORD)
        self.assertEqual(self.report["snapshot_source"], "derived")

    def test_the_build_describes_the_corpus_it_was_given(self):
        self.assertEqual(self.report["records"], self.remaining)

    def test_the_public_pages_state_the_temporary_corpus_total(self):
        totals = rendered_totals(self.out)
        self.assertIn(self.remaining, totals)

    def test_the_public_pages_do_not_state_the_declared_launch_total(self):
        """
        The failure this repair exists to prevent, in its quiet form: a page
        that renders successfully while describing a corpus it did not build.
        """
        totals = rendered_totals(self.out)
        self.assertNotIn(self.declared["expected_records"], totals)

    def test_the_derived_identity_is_not_the_declared_one(self):
        derived = self.gp.snapshot_from_corpus(self.db)
        self.assertNotEqual(derived["logical_sha256"],
                            self.declared["logical_sha256"])
        self.assertEqual(derived["expected_records"], self.remaining)


@unittest.skipUnless(TRACKED_DB.exists(), "production database not present")
class TestTheProductionCallPathIsTheOneThatWasRepaired(unittest.TestCase):
    """
    `pipeline.py` stage 14 calls `render_site()` with no mode, no destination,
    no database and no snapshot. That exact shape is what broke, so that exact
    shape is what is asserted here.
    """

    def test_the_pipeline_calls_render_site_with_nothing(self):
        source = (REPO_ROOT / "pipeline.py").read_text("utf-8")
        self.assertIn("_render.render_site()", source)

    def test_an_omitted_snapshot_is_derived_not_defaulted(self):
        render = load_render()
        source = (REPO_ROOT / "site" / "render.py").read_text("utf-8")
        self.assertIn("snapshot_from_corpus(selected_db)", source)
        # Truthiness would treat an empty declaration as absence and silently
        # substitute the launch pin.
        self.assertIn("if snapshot is not None:", source)
        self.assertNotIn("snapshot or gp.DECLARED_SNAPSHOT", source)

    def test_the_default_database_is_selected_before_the_snapshot(self):
        source = (REPO_ROOT / "site" / "render.py").read_text("utf-8")
        self.assertLess(source.index("selected_db = "),
                        source.index("snapshot_from_corpus(selected_db)"))


@unittest.skipUnless(TRACKED_DB.exists(), "production database not present")
class TestAnExplicitSnapshotStillFailsClosed(unittest.TestCase):
    """
    The repair widens exactly one door. A caller that names a corpus still gets
    that corpus or an abort — the release path is unchanged.
    """

    def setUp(self):
        self.render = load_render()
        self.gp = load_gp()
        self.tmp = Path(tempfile.mkdtemp(prefix="corpus-advance-strict-"))
        self.db = copy_corpus(self.tmp)
        self.out = self.tmp / "built"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def render_with(self, snapshot):
        return self.render.render_site(
            output_dir=self.out, db_path=self.db, environ={},
            snapshot=snapshot, site_origin=TEST_ORIGIN)

    def test_a_stale_declared_snapshot_is_still_rejected(self):
        stale = dict(self.gp.DECLARED_SNAPSHOT)
        with self.assertRaises(SystemExit) as caught:
            self.render_with(stale)
        self.assertEqual(type(caught.exception).__name__, "SnapshotMismatch")

    def test_rejection_happens_before_the_destination_is_written(self):
        """
        A build that aborted halfway would leave a partial tree that looks like
        a published site.
        """
        stale = dict(self.gp.DECLARED_SNAPSHOT)
        with self.assertRaises(SystemExit):
            self.render_with(stale)
        self.assertFalse((self.out / "index.html").exists())

    def test_a_matching_count_with_a_different_fingerprint_is_rejected(self):
        """
        The case a count alone cannot catch: the same number of records, one of
        them replaced. Without the fingerprint this would publish silently.
        """
        derived = self.gp.snapshot_from_corpus(self.db)
        forged = dict(derived)
        forged["logical_sha256"] = "0" * 64
        with self.assertRaises(SystemExit) as caught:
            self.render_with(forged)
        self.assertEqual(type(caught.exception).__name__, "SnapshotMismatch")

    def test_a_snapshot_matching_the_corpus_is_accepted(self):
        """The strict path still works when the declaration is true."""
        derived = self.gp.snapshot_from_corpus(self.db)
        report = self.render_with(derived)
        self.assertEqual(report["snapshot_source"], "declared")
        self.assertEqual(report["records"], derived["expected_records"])

    def test_a_corpus_that_moves_between_derivation_and_build_is_caught(self):
        """
        The race the derived path could otherwise hide. The identity is taken
        once and handed to the builder, which re-reads the database and checks
        what it loaded against what it was given — so a corpus that changes in
        between aborts instead of producing a tree describing neither state.
        """
        derived = self.gp.snapshot_from_corpus(self.db)
        drop_records(self.db, 5)
        with self.assertRaises(SystemExit) as caught:
            self.render_with(derived)
        self.assertEqual(type(caught.exception).__name__, "SnapshotMismatch")
        self.assertFalse((self.out / "index.html").exists())


class TestTheAcceptedLaunchPinIsUntouched(unittest.TestCase):
    """
    The owner's decision, pinned. The repair changes how the DAILY path gets an
    identity; it does not advance, relax or recompute the accepted one.
    """

    ACCEPTED = {
        "date": "2026-08-26",
        "expected_records": 3574,
        "logical_sha256":
            "d5b897cd48029650df66f968e525d9fb4bc198fd84b11266e9360f87e444fe9c",
    }

    def test_the_declared_snapshot_is_still_the_launch_pin(self):
        self.assertEqual(load_gp().DECLARED_SNAPSHOT, self.ACCEPTED)

    def test_the_daily_path_no_longer_reads_the_launch_pin(self):
        """
        It may still be referenced for release builds and for documentation.
        What it may not be is the value an omitted snapshot falls back to.
        """
        source = (REPO_ROOT / "site" / "render.py").read_text("utf-8")
        self.assertNotIn("or gp.DECLARED_SNAPSHOT", source)


if __name__ == "__main__":
    unittest.main()
