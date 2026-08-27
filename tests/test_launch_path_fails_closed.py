"""
The launch path must refuse to publish an unsafe site rather than publish one.

Three things have to be true at once for this repository to publish as
Indo-Pacific Record: the mode is flipped, a real origin is named, and the
declared snapshot matches the corpus in the database. All three are true as of
2026-08-27, and each of the three refusals still has to work — a guard that
only ever ran while it was failing was never tested.

What changed at the launch, and why these tests changed with it:

  * The origin used to have no default, so "no origin anywhere" was the case
    that mattered. It now defaults to `config.SITE_ORIGIN`, because production
    has to build without every caller remembering a flag. The fail-closed
    property moved rather than disappeared: the *constant* must be a real
    absolute HTTPS origin, and an explicitly blank origin must still stop the
    build.
  * The snapshot used to be deliberately stale, and its staleness was pinned so
    that nobody could freeze a moving corpus into the launch branch early. It
    is now accepted, and the pin holds the accepted values instead — a snapshot
    that drifts from the corpus still aborts before anything is written.
  * The domain used to be forbidden from the tree. It is now required to be
    present, correct, and the same in all four places that carry it.
"""
import importlib.util
import re
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

from config import SITE_ORIGIN                                    # noqa: E402

LAUNCH_DOMAIN = "indopacificrecord.org"
PREDECESSOR_DOMAIN = "chinamilwatch.org"


class TestThisIsTheLaunchedRepository(unittest.TestCase):

    def test_the_mode_is_flipped(self):
        self.assertEqual(render.DEFAULT_SITE_MODE, render.INDO_PACIFIC_RECORD)

    def test_there_is_still_exactly_one_switch_to_change_back(self):
        source = (ROOT / "site" / "render.py").read_text(encoding="utf-8")
        self.assertEqual(
            len(re.findall(r"^DEFAULT_SITE_MODE\s*=", source, re.M)), 1)


class TestTheOriginIsRealAndRequired(unittest.TestCase):

    def test_the_configured_origin_is_an_absolute_https_origin(self):
        self.assertTrue(SITE_ORIGIN.startswith("https://"), SITE_ORIGIN)
        self.assertEqual(SITE_ORIGIN, "https://" + LAUNCH_DOMAIN)
        self.assertFalse(SITE_ORIGIN.endswith("/"), "no trailing slash")

    def test_an_explicitly_blank_origin_is_still_refused(self):
        """
        A default is not the same as an unconditional value. A caller that
        passes an empty origin is asking for the failure the default exists to
        prevent, and must get it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(render.MissingSiteOrigin):
                render.render_site(output_dir=Path(tmp) / "out", environ={},
                                   site_origin="   ")

    def test_the_refusal_still_names_the_environment_variable(self):
        with tempfile.TemporaryDirectory() as tmp:
            try:
                render.render_site(output_dir=Path(tmp) / "out", environ={},
                                   site_origin="   ")
            except render.MissingSiteOrigin as exc:
                self.assertIn(render.SITE_ORIGIN_ENV, str(exc))
                self.assertIn("noindex", str(exc))
            else:
                self.fail("expected MissingSiteOrigin")

    def test_the_environment_still_overrides_the_default(self):
        """Scratch builds must be able to name another origin without editing
        the constant the production build reads."""
        with tempfile.TemporaryDirectory() as tmp:
            report = render.render_site(
                output_dir=Path(tmp) / "out",
                environ={render.SITE_ORIGIN_ENV: "https://a-real-domain.org"})
            self.assertEqual(report["site_origin"], "https://a-real-domain.org")


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


class TestTheAcceptedSnapshot(unittest.TestCase):

    ACCEPTED = {
        "date": "2026-08-26",
        "expected_records": 3574,
        "logical_sha256":
            "d5b897cd48029650df66f968e525d9fb4bc198fd84b11266e9360f87e444fe9c",
    }

    def test_the_declared_snapshot_is_the_one_accepted_at_launch(self):
        """
        Accepted 2026-08-27. Three values describing one corpus: if any of them
        is edited alone, the build stops rather than republishing a changed
        corpus under an unchanged identity.
        """
        self.assertEqual(gp.DECLARED_SNAPSHOT, self.ACCEPTED)

    def test_the_declared_snapshot_still_matches_the_tracked_corpus(self):
        derived = gp.snapshot_from_corpus(gp.TRACKED_DB)
        for key in ("date", "expected_records", "logical_sha256"):
            with self.subTest(key=key):
                self.assertEqual(derived[key], gp.DECLARED_SNAPSHOT[key])

    def test_a_snapshot_that_does_not_match_the_corpus_is_refused(self):
        """The guard that mattered before the launch has to keep mattering
        after it: this is what stops tomorrow's corpus publishing under
        today's snapshot identity."""
        wrong = dict(gp.DECLARED_SNAPSHOT)
        wrong["expected_records"] = wrong["expected_records"] + 1
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as caught:
                render.render_site(output_dir=Path(tmp) / "out", environ={},
                                   snapshot=wrong,
                                   site_origin="https://a-real-domain.org")
            self.assertEqual(type(caught.exception).__name__,
                             "SnapshotMismatch")

    def test_a_changed_fingerprint_alone_is_enough_to_refuse(self):
        wrong = dict(gp.DECLARED_SNAPSHOT)
        wrong["logical_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                render.render_site(output_dir=Path(tmp) / "out", environ={},
                                   snapshot=wrong,
                                   site_origin="https://a-real-domain.org")


class TestTheLaunchDomainIsCommittedEverywhereItIsNeeded(unittest.TestCase):
    """
    The inverse of the pre-launch pin. Before the launch the domain was an
    owner decision and no file was allowed to pre-empt it. Now four files carry
    it and they must agree: a CNAME that disagrees with a workflow means the
    next scheduled run silently takes the domain back.
    """

    WORKFLOWS = (".github/workflows/deploy_output_only.yml",
                 ".github/workflows/daily_update.yml")

    def test_the_committed_cname_is_the_launch_domain(self):
        self.assertEqual((ROOT / "output" / "CNAME").read_text("utf-8").strip(),
                         LAUNCH_DOMAIN)

    def test_every_deploy_workflow_publishes_the_same_domain(self):
        for rel in self.WORKFLOWS:
            text = (ROOT / rel).read_text(encoding="utf-8")
            found = re.findall(r"^\s*cname:\s*(\S+)\s*$", text, re.M)
            with self.subTest(file=rel):
                self.assertEqual(found, [LAUNCH_DOMAIN])

    def test_no_deploy_workflow_still_claims_the_predecessor_domain(self):
        """
        This is the one that would undo the redirect site. The redirect host
        and the publication cannot both hold chinamilwatch.org, so a workflow
        that still names it would reclaim the domain on the next run and turn
        every preserved legacy address back into the old site.
        """
        for rel in self.WORKFLOWS:
            with self.subTest(file=rel):
                self.assertNotIn("cname: " + PREDECESSOR_DOMAIN,
                                 (ROOT / rel).read_text(encoding="utf-8"))

    def test_the_configured_origin_and_the_cname_name_one_host(self):
        cname = (ROOT / "output" / "CNAME").read_text("utf-8").strip()
        self.assertEqual(SITE_ORIGIN, "https://" + cname)

    def test_the_deploy_gate_agrees_with_the_configuration(self):
        """
        `scripts/validate_output.py` keeps its own copy of the origin because
        it runs on the runner's bare Python. A copy that drifts from the
        configuration is a validator checking the wrong site.
        """
        spec = importlib.util.spec_from_file_location(
            "validate_output_probe", ROOT / "scripts" / "validate_output.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.SITE_ORIGIN, SITE_ORIGIN)


class TestLegacyIsIntactAsTheRollbackPath(unittest.TestCase):
    """
    Rolling back is selecting legacy again. That only works while the legacy
    renderer still exists, still builds, and still writes the predecessor's own
    addresses — which is why it is the one thing the launch does not touch.
    """

    def test_legacy_can_still_be_asked_for_explicitly(self):
        self.assertEqual(render.resolve_site_mode("legacy"), render.LEGACY)

    def test_an_unknown_mode_is_refused(self):
        with self.assertRaises(render.UnsupportedSiteMode):
            render.resolve_site_mode("nonsense")

    def test_the_legacy_generator_is_untouched(self):
        gen = (ROOT / "site" / "generator.py").read_text(encoding="utf-8")
        for name in ("site_origin", "PLA_WATCH_SITE_ORIGIN"):
            with self.subTest(name=name):
                self.assertNotIn(name, gen)

    def test_the_legacy_generator_still_writes_the_predecessor_addresses(self):
        """Not an oversight. A rollback must restore the site that was there,
        and that site's canonicals were on the predecessor's domain."""
        gen = (ROOT / "site" / "generator.py").read_text(encoding="utf-8")
        self.assertIn(PREDECESSOR_DOMAIN, gen)


if __name__ == "__main__":
    unittest.main()
