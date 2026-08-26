"""
The launch path must refuse to publish an unsafe site rather than publish one.

Three things have to be true at once before this repository can publish as
Indo-Pacific Record: the mode is flipped, a real origin is named, and a fresh
snapshot has been accepted. Each is checked, and each failure is loud.

The origin check is the one that had to be added. `generate_preview.build()`
leaves a tree `noindex` and writes no sitemap unless it is given an origin —
right for a candidate, catastrophic for a launch — and `render_site()` did not
pass one. Flipping the mode alone would therefore have produced a build that
*succeeded* while telling every crawler to ignore the entire publication. An
optional flag production never passes is not a safety feature.
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("site_render",
                                               ROOT / "site" / "render.py")
render = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(render)

sys.path.insert(0, str(ROOT / "site" / "preview"))
import generate_preview as gp                                     # noqa: E402


class TestThisBranchIsTheLaunchBranch(unittest.TestCase):

    def test_the_mode_is_flipped(self):
        self.assertEqual(render.DEFAULT_SITE_MODE, render.INDO_PACIFIC_RECORD)


class TestAMissingOriginStopsTheBuild(unittest.TestCase):

    def test_no_origin_anywhere_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(render.MissingSiteOrigin):
                render.render_site(output_dir=Path(tmp) / "out", environ={})

    def test_an_empty_origin_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(render.MissingSiteOrigin):
                render.render_site(output_dir=Path(tmp) / "out", environ={},
                                   site_origin="   ")

    def test_the_refusal_names_the_environment_variable(self):
        with tempfile.TemporaryDirectory() as tmp:
            try:
                render.render_site(output_dir=Path(tmp) / "out", environ={})
            except render.MissingSiteOrigin as exc:
                self.assertIn(render.SITE_ORIGIN_ENV, str(exc))
                self.assertIn("noindex", str(exc))
            else:
                self.fail("expected MissingSiteOrigin")

    def test_the_environment_variable_is_accepted(self):
        """
        Supplied but stale-snapshotted: it must get past the origin gate and
        fail on the snapshot instead.

        Caught as SystemExit, and matched by name. SnapshotMismatch subclasses
        SystemExit, so it is a BaseException and `assertRaises(Exception)` will
        not see it. And `render.py` loads its own copy of `generate_preview`,
        so the class object it raises is not the one imported here — comparing
        the classes would fail for a reason unrelated to the launch.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as caught:
                render.render_site(
                    output_dir=Path(tmp) / "out",
                    environ={render.SITE_ORIGIN_ENV: "https://a-real-domain.org"})
            self.assertNotIsInstance(caught.exception, render.MissingSiteOrigin)
            self.assertEqual(type(caught.exception).__name__, "SnapshotMismatch")


class TestAnUnusableOriginStopsTheBuild(unittest.TestCase):

    def test_a_placeholder_origin_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(gp.UnusableSiteOrigin):
                gp.build(Path(tmp), gp.PUBLIC_TITLE, gp.TRACKED_DB,
                         snapshot=gp.snapshot_from_corpus(gp.TRACKED_DB),
                         site_origin="https://example.com")

    def test_a_reserved_origin_is_refused_without_the_named_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(gp.UnusableSiteOrigin):
                gp.build(Path(tmp), gp.PUBLIC_TITLE, gp.TRACKED_DB,
                         snapshot=gp.snapshot_from_corpus(gp.TRACKED_DB),
                         site_origin="https://x.invalid")


class TestAStaleSnapshotStopsTheBuild(unittest.TestCase):

    def test_the_declared_snapshot_is_still_stale_on_this_branch(self):
        """
        The snapshot is a launch-day decision and is deliberately not advanced
        here. If this test ever fails, someone froze a moving corpus into the
        launch branch early.
        """
        self.assertEqual(gp.DECLARED_SNAPSHOT["date"], "2026-08-19")

    def test_a_real_origin_with_the_stale_snapshot_is_still_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as caught:
                render.render_site(
                    output_dir=Path(tmp) / "out",
                    environ={render.SITE_ORIGIN_ENV: "https://a-real-domain.org"})
            self.assertEqual(type(caught.exception).__name__, "SnapshotMismatch")


class TestNoRealDomainIsCommitted(unittest.TestCase):
    """The domain is an owner decision. Nothing here may pre-empt it."""

    WATCHED = ("site/render.py", "site/preview/generate_preview.py",
               "output/CNAME", ".github/workflows/deploy_output_only.yml",
               ".github/workflows/daily_update.yml")

    def test_no_indopacificrecord_domain_is_committed_anywhere(self):
        for rel in self.WATCHED:
            path = ROOT / rel
            if not path.exists():
                continue
            with self.subTest(file=rel):
                self.assertNotIn("indopacificrecord", path.read_text("utf-8"))

    def test_the_cname_is_untouched(self):
        self.assertEqual((ROOT / "output" / "CNAME").read_text("utf-8").strip(),
                         "chinamilwatch.org")


class TestLegacyStillWorksOnThisBranch(unittest.TestCase):

    def test_legacy_can_still_be_asked_for_explicitly(self):
        self.assertEqual(render.resolve_site_mode("legacy"), render.LEGACY)

    def test_an_unknown_mode_is_refused(self):
        with self.assertRaises(render.UnsupportedSiteMode):
            render.resolve_site_mode("nonsense")

    def test_the_legacy_generator_is_untouched(self):
        gen = (ROOT / "site" / "generator.py").read_text("utf-8")
        for name in ("site_origin", "PLA_WATCH_SITE_ORIGIN"):
            with self.subTest(name=name):
                self.assertNotIn(name, gen)


if __name__ == "__main__":
    unittest.main()
