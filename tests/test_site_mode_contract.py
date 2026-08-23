"""
Site-mode contract.

`site/render.py` is the one seam between the live China Mil Watch renderer and
The Declared Record desk architecture. The risk it exists to control is not a
rendering bug — it is a mode selected implicitly, so that a scheduled run that
believed it was publishing the live site published something else, or wrote the
prototype over `output/`.

Every assertion here is about that: what the default is, what happens to an
unrecognised mode, what Declared Record mode refuses to do, and whether the
scheduled workflow can reach it at all.

No network. No writes to the tracked database or `output/`.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RENDER_PY = REPO_ROOT / "site" / "render.py"
TRACKED_DB = REPO_ROOT / "pla_watch.db"
PRODUCTION_OUT = REPO_ROOT / "output"
DAILY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily_update.yml"


def load_render():
    spec = importlib.util.spec_from_file_location("site_render", RENDER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestModeResolution(unittest.TestCase):
    """Selection is explicit, defaults to legacy, and never guesses."""

    def setUp(self):
        self.r = load_render()

    def test_the_default_mode_is_legacy(self):
        self.assertEqual(self.r.DEFAULT_SITE_MODE, self.r.LEGACY)
        self.assertEqual(self.r.resolve_site_mode(environ={}), self.r.LEGACY)

    def test_an_unsupported_mode_fails_closed(self):
        """No silent fallback: a typo must stop the run, not publish legacy."""
        for bad in ("declared_record", "DeclaredRecord ", "prod", "preview",
                    "legacy-mode"):
            with self.subTest(mode=bad):
                with self.assertRaises(self.r.UnsupportedSiteMode):
                    self.r.resolve_site_mode(bad, environ={})

    def test_an_empty_selection_is_treated_as_unset(self):
        """
        An empty string is absence, not a mode. It resolves to the default
        rather than raising — an unset variable in a shell is the ordinary
        case, and failing there would make the default unreachable.
        """
        self.assertEqual(
            self.r.resolve_site_mode(environ={self.r.SITE_MODE_ENV: ""}),
            self.r.LEGACY)

    def test_an_unsupported_environment_value_fails_closed(self):
        with self.assertRaises(self.r.UnsupportedSiteMode):
            self.r.resolve_site_mode(environ={self.r.SITE_MODE_ENV: "nonsense"})

    def test_declared_record_must_be_selected_explicitly(self):
        self.assertEqual(
            self.r.resolve_site_mode(self.r.DECLARED_RECORD, environ={}),
            self.r.DECLARED_RECORD)
        self.assertEqual(
            self.r.resolve_site_mode(
                environ={self.r.SITE_MODE_ENV: self.r.DECLARED_RECORD}),
            self.r.DECLARED_RECORD)

    def test_the_explicit_argument_beats_the_environment(self):
        self.assertEqual(
            self.r.resolve_site_mode(
                self.r.LEGACY,
                environ={self.r.SITE_MODE_ENV: self.r.DECLARED_RECORD}),
            self.r.LEGACY)

    def test_there_is_exactly_one_launch_switch(self):
        """
        The launch is one constant. If a second default appears anywhere, the
        rollback story stops being 'change it back'.
        """
        source = RENDER_PY.read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"^DEFAULT_SITE_MODE\s*=", source,
                                        re.M)), 1)
        others = [p for p in REPO_ROOT.rglob("*.py")
                  if "DEFAULT_SITE_MODE =" in p.read_text(encoding="utf-8")
                  and p.name not in ("render.py",)
                  and "/preview/" not in str(p) and "/tests/" not in str(p)]
        self.assertEqual(others, [])

    def test_the_launch_switch_is_documented_where_it_lives(self):
        source = RENDER_PY.read_text(encoding="utf-8")
        self.assertIn("LAUNCH SWITCH", source)


class TestScheduledWorkflowCannotReachTheNewMode(unittest.TestCase):

    def test_the_daily_workflow_never_sets_the_mode_variable(self):
        r = load_render()
        self.assertNotIn(r.SITE_MODE_ENV,
                         DAILY_WORKFLOW.read_text(encoding="utf-8"))

    def test_no_workflow_sets_the_mode_variable(self):
        r = load_render()
        for wf in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
            with self.subTest(workflow=wf.name):
                self.assertNotIn(r.SITE_MODE_ENV,
                                 wf.read_text(encoding="utf-8"))

    def test_the_pipeline_selects_no_mode_so_it_resolves_to_legacy(self):
        """
        pipeline.py must call render_site() with no mode. Passing one here
        would be a second selection point.
        """
        src = (REPO_ROOT / "pipeline.py").read_text(encoding="utf-8")
        self.assertIn("render_site()", src)
        self.assertNotIn("DECLARED_RECORD", src)
        self.assertNotIn("declared-record", src)

    def test_the_pla_watch_draft_workflow_still_runs_its_generator(self):
        wf = (REPO_ROOT / ".github" / "workflows"
              / "generate_pla_watch_draft.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/generate_pla_watch.py", wf)


class TestDeclaredRecordRefusesProduction(unittest.TestCase):

    def setUp(self):
        self.r = load_render()

    def test_it_refuses_to_run_without_a_destination(self):
        with self.assertRaises(self.r.UnsupportedSiteMode):
            self.r.render_site(self.r.DECLARED_RECORD, environ={})

    def test_it_refuses_the_production_output_directory(self):
        with self.assertRaises(self.r.UnsupportedSiteMode):
            self.r.render_site(self.r.DECLARED_RECORD,
                               output_dir=PRODUCTION_OUT, environ={})

    def test_it_refuses_a_directory_inside_production_output(self):
        with self.assertRaises(self.r.UnsupportedSiteMode):
            self.r.render_site(self.r.DECLARED_RECORD,
                               output_dir=PRODUCTION_OUT / "nested",
                               environ={})

    def test_the_renderer_reads_the_database_read_only(self):
        gp = (REPO_ROOT / "site" / "preview"
              / "generate_preview.py").read_text(encoding="utf-8")
        self.assertIn("_read_only", gp)
        self.assertNotRegex(gp, r"sqlite3\.connect\(\s*str\(db_path\)\s*\)")


class TestDeclaredRecordBuild(unittest.TestCase):
    """One real build, asserted for routes and desk state."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.r = load_render()
        cls.tmp = Path(tempfile.mkdtemp(prefix="site-mode-"))
        cls.out = cls.tmp / "dr"
        cls.db_before = TRACKED_DB.stat().st_size
        # Clear any sidecar left by an earlier legacy render in this process or
        # working tree, so the assertion below is about THIS build and not
        # about `storage/db.py`, which opens the tracked database read-write.
        for ext in ("-wal", "-shm"):
            Path(str(TRACKED_DB) + ext).unlink(missing_ok=True)
        spec = importlib.util.spec_from_file_location(
            "gp_snapshot", REPO_ROOT / "site" / "preview" / "generate_preview.py")
        gp = importlib.util.module_from_spec(spec)
        sys.modules["gp_snapshot"] = gp
        spec.loader.exec_module(gp)
        cls.report = cls.r.render_site(
            cls.r.DECLARED_RECORD, output_dir=cls.out, environ={},
            snapshot=gp.snapshot_from_corpus(TRACKED_DB))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_build_reports_declared_record_mode(self):
        self.assertEqual(self.report["mode"], self.r.DECLARED_RECORD)

    def test_the_desk_routes_render(self):
        for route in ("index.html", "desks.html", "china.html", "japan.html",
                      "archive.html", "coverage.html", "sources.html",
                      "weekly.html", "methodology.html", "about.html",
                      "corpus.html", "corpus-guide.html"):
            with self.subTest(route=route):
                self.assertTrue((self.out / route).is_file())

    def test_legacy_record_routes_are_preserved_as_redirects(self):
        """
        /article/<id>.html is live today. Every one must still resolve after a
        launch, and must point at a record page that exists in this snapshot.
        """
        stubs = sorted((self.out / "article").glob("*.html"))
        self.assertEqual(len(stubs), self.report["records"])
        self.assertEqual(len(stubs), self.report["legacy_redirects"])
        checked = 0
        for stub in stubs:
            html = stub.read_text(encoding="utf-8")
            m = re.search(r'href="\.\./record/(\d+)\.html"', html)
            self.assertIsNotNone(m, "%s is not a redirect" % stub.name)
            self.assertTrue((self.out / "record" / (m.group(1) + ".html")).is_file())
            self.assertIn('content="noindex"', html)
            checked += 1
        self.assertEqual(checked, len(stubs))

    def test_a_redirect_stub_names_its_own_record(self):
        for name in ("3379.html", "3388.html"):
            stub = self.out / "article" / name
            if not stub.is_file():
                continue
            rec_id = name[:-5]
            self.assertIn('href="../record/%s.html"' % rec_id,
                          stub.read_text(encoding="utf-8"))

    def test_china_is_the_only_collecting_desk_in_the_build(self):
        html = (self.out / "desks.html").read_text(encoding="utf-8")
        self.assertIn("Live — collecting", html)
        self.assertIn("not yet collecting", html)
        self.assertIn("1</b> collecting desk",
                      (self.out / "index.html").read_text(encoding="utf-8"))

    def test_japan_renders_with_no_records_and_no_sources(self):
        html = (self.out / "japan.html").read_text(encoding="utf-8")
        self.assertIn("No records collected. No sources enabled.", html)
        self.assertIn("No Japan source is enabled", html)

    def test_the_us_is_not_a_collecting_desk_in_the_build(self):
        html = (self.out / "desks.html").read_text(encoding="utf-8")
        self.assertIn("not presented as a desk", html)
        headings = [re.sub(r"<[^>]+>", "", h).strip() for h in
                    re.findall(r"<h[123][^>]*>(.*?)</h[123]>", html, re.S)]
        for h in headings:
            with self.subTest(heading=h):
                self.assertNotIn("United States", h)

    def test_no_other_desk_was_introduced(self):
        """Candidates under research must not leak into the release build."""
        html = (self.out / "desks.html").read_text(encoding="utf-8")
        for absent in ("Korea", "Australia", "Philippines", "Taiwan",
                       "Singapore", "India", "Cross-Regional"):
            with self.subTest(desk=absent):
                self.assertNotIn(absent, html)

    def test_the_build_did_not_touch_the_tracked_database(self):
        """
        The Declared Record renderer reads through `reconcile_db._read_only`,
        which works on a scratch copy, so it leaves the tracked file and its
        sidecars alone. (The legacy renderer does open the tracked database
        directly and does leave a checkpointed -wal; that is pre-existing
        behaviour, both sidecars are gitignored, and it happens after the
        workflow's cleanliness gate. It is not asserted here.)
        """
        self.assertEqual(TRACKED_DB.stat().st_size, self.db_before)
        for ext in ("-wal", "-shm"):
            with self.subTest(sidecar=ext):
                self.assertFalse(Path(str(TRACKED_DB) + ext).exists())

    def test_the_build_wrote_nothing_into_production_output(self):
        self.assertNotIn(str(PRODUCTION_OUT), str(self.out))


class TestSnapshotStillGuardsTheBuild(unittest.TestCase):

    def test_a_snapshot_mismatch_aborts_before_writing(self):
        sys.path.insert(0, str(REPO_ROOT / "site" / "preview"))
        spec = importlib.util.spec_from_file_location(
            "gp_guard", REPO_ROOT / "site" / "preview" / "generate_preview.py")
        gp = importlib.util.module_from_spec(spec)
        sys.modules["gp_guard"] = gp
        spec.loader.exec_module(gp)
        tmp = Path(tempfile.mkdtemp(prefix="snap-guard-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        target = tmp / "out"
        wrong = dict(gp.DECLARED_SNAPSHOT)
        wrong["expected_records"] = wrong["expected_records"] + 1
        with self.assertRaises(gp.SnapshotMismatch):
            gp.build(target, "Test", TRACKED_DB, snapshot=wrong,
                     legacy_routes=True)
        self.assertFalse(any(target.rglob("*.html")) if target.exists()
                         else False, "pages were written despite a mismatch")


if __name__ == "__main__":
    unittest.main()
