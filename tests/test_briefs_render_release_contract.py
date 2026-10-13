"""Static contract tests for the manual-only Briefs render/release workflow."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/briefs_render_only_release.yml"
RUNNER = ROOT / "scripts/run_briefs_render_release.py"


class BriefsRenderReleaseContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_release_is_manual_only_and_defaults_to_preview(self):
        text = self.workflow
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("approved_main_sha:", text)
        self.assertIn("default: false", text)
        self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.publish == true && github.ref == 'refs/heads/main'", text)
        self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.publish == false && github.ref == 'refs/heads/main'", text)
        self.assertIn('[[ "$EXPECTED_SHA" =~ ^[a-f0-9]{40}$ ]]', text)
        self.assertIn('test "$ACTUAL_SHA" = "$EXPECTED_SHA"', text)
        self.assertNotIn("\n  push:", text)
        self.assertNotIn("\n  schedule:", text)

    def test_render_reuses_existing_sources_and_never_collects(self):
        text = self.workflow + self.runner
        for required in (
            "scripts/rerender_pla_watch.py", "site/render.py",
            "scripts/validate_output.py", "scripts/build_brief_cover.py",
            "scripts/build_catalogue_media.py", "pla_watch.db-wal",
            "pla_watch.db-shm", "sha256sum", "classify_output_changes",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        for forbidden in (
            "python pipeline.py", "ANTHROPIC_API_KEY",
            "shadow_collect.py", "scripts/shadow_collect",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_scope_gate_precedes_staging_commit_and_deployment(self):
        text = self.workflow
        strict = text.index("python -m scripts.run_briefs_render_release --scope strict")
        stage = text.index("git add -A -- output/")
        push = text.index("git push origin HEAD:main")
        deploy = text.index("uses: peaceiris/actions-gh-pages@v3")
        self.assertLess(strict, stage)
        self.assertLess(stage, push)
        self.assertLess(push, deploy)
        self.assertIn("python -m scripts.guard_briefs_render_scope", text)

    def test_preview_uploads_artifact_and_does_not_commit_or_deploy(self):
        text = self.workflow
        preview = text.split("  preview:", 1)[1].split("  publish:", 1)[0]
        self.assertIn("--scope report-only", preview)
        self.assertIn("actions/upload-artifact@v4", preview)
        self.assertNotIn("git push", preview)
        self.assertNotIn("peaceiris/actions-gh-pages", preview)

    def test_runner_uses_both_renderers_and_checks_expected_surfaces(self):
        text = self.runner
        self.assertIn('"scripts/rerender_pla_watch.py", "--no-covers"', text)
        self.assertIn('"site/render.py", "--out", "output"', text)
        self.assertIn("no-17-trident-resolve-basarnas-drone.jpg", text)
        self.assertIn("trident-resolve-basarnas-drone-800.webp", text)
        self.assertIn("does not imply or constitute DoW endorsement", text)
        self.assertIn("Downloaded from PLA Daily / 81.cn", text)
        self.assertIn("output deltas", text.lower())


if __name__ == "__main__":
    unittest.main()
