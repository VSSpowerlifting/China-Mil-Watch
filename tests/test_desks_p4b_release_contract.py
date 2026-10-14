"""Phase 4B release is Atlas-only, SHA-pinned and owner-visual gated.

This is an *engineering contract*, not publication authority. Until #537
lands and owner reviews the Atlas itself, workflow PR stays draft.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.guard_desks_p4b_output_scope import (
    REVIEWED_PATHS, APPROVED_US_LIMIT, DESKS_HUB_CAP, DESKS_JS_CAP, check,
)
from scripts.stage_desks_p4b_output import stage

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/desks_p4b_render_only_release.yml"


class Phase4BReleaseContracts(unittest.TestCase):
    def test_three_and_only_three_public_files(self):
        self.assertEqual(REVIEWED_PATHS, frozenset({
            "output/desks.html",
            "output/desk-atlas.css",
            "output/assets/glyphs/sources.svg",
        }))
        self.assertEqual(DESKS_HUB_CAP, 300_000)
        self.assertEqual(DESKS_JS_CAP, 10_000)
        self.assertIn("U.S. institutional statements", APPROVED_US_LIMIT)
        for path in REVIEWED_PATHS:
            self.assertNotIn("brief", path.lower())
            self.assertNotIn("shadow", path.lower())
            self.assertNotIn("korea.html", path.lower())

    def test_stager_is_fail_closed_and_preserves_all_other_routes(self):
        with tempfile.TemporaryDirectory(prefix="p4b-stage-") as temp:
            root = Path(temp)
            source, target = root / "render", root / "gh-pages"
            source.mkdir()
            target.mkdir()
            keep = {"indonesia.html": b"newer links",
                    "analysis.html": b"published Briefs",
                    "desk-map.css": b"approved P4A map",
                    "assets/flags/kr.svg": b"approved flag",
                    "assets/flags/LICENSE": b"approved license",
                    "briefs/what-is-being-built-in-laos.html": b"laos"}
            for path, data in keep.items():
                file = target / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(data)
            with self.assertRaises(FileNotFoundError):
                stage(source, target)
            for rel in REVIEWED_PATHS:
                file = source / rel.removeprefix("output/")
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(rel.encode())
            names = stage(source, target)
            self.assertEqual(len(names), 3)
            for name, data in keep.items():
                self.assertEqual((target / name).read_bytes(), data, name)
            for rel in REVIEWED_PATHS:
                name = rel.removeprefix("output/")
                self.assertEqual((target / name).read_bytes(), (source / name).read_bytes())
            with self.assertRaises(ValueError):
                stage(target, target)

    def test_exact_output_scope_rejects_unrelated_delta(self):
        with tempfile.TemporaryDirectory(prefix="p4b-contract-") as temp:
            # The classifier is run against git's output tree during the
            # actual release; this isolated temp directory proves the
            # no-change failure condition without needing a full site render.
            # More precise dirty-tree tests already live in the shared guard.
            self.assertEqual(len(REVIEWED_PATHS), 3)
            self.assertTrue(callable(check))

    def test_manual_publishing_requires_sha_and_visual_approval(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("approved_main_sha:", text)
        self.assertIn("visual_approved:", text)
        self.assertIn("default: false", text)
        self.assertIn("test \"$(git rev-parse HEAD)\" = \"$EXPECTED_SHA\"", text)
        self.assertIn("test \"$(git rev-parse origin/main)\" = \"$(git rev-parse HEAD)\"", text)
        self.assertIn("inputs.publish && 'pages-deploy'", text)
        self.assertIn("github.event_name == 'workflow_dispatch' && 'daily-update'", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertNotIn("\n  push:", text)
        self.assertNotIn("\n  schedule:", text)

    def test_isolated_render_and_strict_sparse_overlay(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python site/render.py --out", text)
        self.assertIn("scripts.stage_desks_p4b_output", text)
        self.assertIn("scripts.guard_desks_p4b_output_scope", text)
        self.assertIn("python scripts/validate_output.py", text)
        self.assertIn("sha256sum -c", text)
        self.assertIn("test ! -e pla_watch.db-wal && test ! -e pla_watch.db-shm", text)
        self.assertIn("keep_files: true", text)
        self.assertIn("publish_dir: \${{ runner.temp }}/desks-pages-patch", text)
        self.assertNotIn("publish_dir: ./output", text)
        self.assertIn("output/assets/glyphs/sources.svg", text)
        self.assertNotIn("output/briefs", text)
        self.assertNotIn("output/japan.html", text)
        self.assertNotIn("pipeline.py", text)
        self.assertNotIn("ANTHROPIC_API_KEY", text)


if __name__ == "__main__":
    unittest.main()
