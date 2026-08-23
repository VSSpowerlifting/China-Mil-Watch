"""
A corpus advance must not block the daily production run.

The outage this pins happened on 2026-08-21 and 2026-08-22. The dormant
Declared Record renderer carries a hand-advanced `DECLARED_SNAPSHOT` naming one
frozen corpus, and `assert_snapshot` refuses to build any other under that name.
Correct for a release. Fatal here, for two compounding reasons:

  * the daily workflow runs the whole offline suite BEFORE collection, so the
    suite gates the pipeline; and
  * `SnapshotMismatch` subclasses `SystemExit`, so an unexpected raise inside a
    `setUpClass` did not fail one test — it terminated the unittest process,
    aborting the suite with no summary.

The 2026-08-20 run collected and committed a corpus of 3,425 records against a
snapshot declaring 3,388. Every run after it died in the test step, so the one
pipeline that could have refreshed the snapshot was the pipeline being blocked.

These tests fix the two properties that failure violated. They fail against the
pre-fix suite.
"""

from __future__ import annotations

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

TRACKED_DB = REPO_ROOT / "pla_watch.db"
TEST_FILES = sorted((REPO_ROOT / "tests").glob("test_*.py"))


class TestNoSuiteBuildUsesTheReleaseConstant(unittest.TestCase):
    """
    Source-level, and the check that would have caught the outage in review.

    A build against the live corpus must always be handed an explicit snapshot.
    Relying on the `DECLARED_SNAPSHOT` default is what couples the daily gate to
    release metadata that is stale by design.
    """

    #: Builds that deliberately assert the guard fires, and so must keep using a
    #: snapshot the corpus does not match.
    GUARD_TESTS = ("test_a_snapshot_mismatch_aborts_before_writing",
                   "test_a_differing_count_fails_loudly",
                   "test_a_fixture_may_declare_its_own_snapshot")

    def test_every_build_against_the_tracked_database_passes_a_snapshot(self):
        pattern = re.compile(r"\.build\(\s*([^)]*?)\)", re.S)
        offenders = []
        for path in TEST_FILES:
            text = path.read_text(encoding="utf-8")
            for m in pattern.finditer(text):
                call = " ".join(m.group(1).split())
                if "TRACKED_DB" not in call:
                    continue
                if "snapshot" in call:
                    continue
                line = text[:m.start()].count("\n") + 1
                offenders.append("%s:%d  .build(%s)"
                                 % (path.name, line, call[:70]))
        self.assertEqual(
            offenders, [],
            "these builds inherit DECLARED_SNAPSHOT against the live corpus, "
            "so the suite aborts the moment production collects:\n  "
            + "\n  ".join(offenders))

    def test_the_preview_case_derives_its_snapshot(self):
        text = (REPO_ROOT / "tests"
                / "test_preview_prototype.py").read_text(encoding="utf-8")
        setup = text.split("class PreviewCase", 1)[1].split("\n    def page", 1)[0]
        self.assertIn("snapshot=", setup,
                      "PreviewCase must hand build() an explicit snapshot")
        self.assertIn("snapshot_of(TRACKED_DB)", setup)


class TestAnAdvancedCorpusStillBuilds(unittest.TestCase):
    """Behavioural: the exact condition that was live on 2026-08-21."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="corpus-advance-"))
        cls.db = cls.tmp / "advanced.db"
        shutil.copyfile(TRACKED_DB, cls.db)
        # Force divergence from whatever the declared snapshot currently says,
        # so this stays meaningful after the snapshot is next advanced.
        con = sqlite3.connect(str(cls.db))
        con.execute("PRAGMA foreign_keys=OFF")
        victim = con.execute(
            "SELECT id FROM articles ORDER BY id DESC LIMIT 1").fetchone()[0]
        con.execute("DELETE FROM articles WHERE id = ?", (victim,))
        con.commit()
        con.close()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_corpus_really_differs_from_the_declared_snapshot(self):
        current = gp.snapshot_from_corpus(self.db)
        self.assertNotEqual(current["logical_sha256"],
                            gp.DECLARED_SNAPSHOT["logical_sha256"])

    def test_building_it_under_its_own_snapshot_succeeds(self):
        out = self.tmp / "ok"
        report = gp.build(out, "Test Title", self.db,
                          snapshot=gp.snapshot_from_corpus(self.db))
        self.assertTrue((out / "index.html").is_file())
        self.assertEqual(report["records"],
                         gp.snapshot_from_corpus(self.db)["expected_records"])

    def test_building_it_under_the_release_constant_still_refuses(self):
        """The guard is intact; only its reach into the daily gate is gone."""
        with self.assertRaises(gp.SnapshotMismatch):
            gp.build(self.tmp / "refused", "Test Title", self.db,
                     snapshot=gp.DECLARED_SNAPSHOT)

    def test_a_snapshot_mismatch_would_abort_a_test_runner(self):
        """
        Why the above matters more than an ordinary failing assertion:
        SnapshotMismatch is a SystemExit, so an unexpected raise does not fail
        a test — it takes the whole process down.
        """
        self.assertTrue(issubclass(gp.SnapshotMismatch, SystemExit))


if __name__ == "__main__":
    unittest.main()
