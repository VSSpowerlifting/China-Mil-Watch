"""No collector, source promotion or hidden output in the Phase 4A release."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.guard_desks_p4a_output_scope import REVIEWED_PATHS, validate_staged
from scripts.stage_desks_p4a_output import stage

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github/workflows/desks_p4a_render_only_release.yml"


class Phase4AReleaseContract(unittest.TestCase):
    def test_exact_public_output_scope_only(self):
        expected = {"output/desks.html", "output/desk-map.css",
                    "output/assets/flags/LICENSE"}
        expected.update("output/assets/flags/%s.svg" % iso
                        for iso in ("cn", "id", "jp", "kr", "ph", "sg", "us", "vn"))
        self.assertEqual(REVIEWED_PATHS, frozenset(expected))
        self.assertEqual(len(expected), 11)
        self.assertFalse(any("/briefs/" in p or "/shadow" in p or
                             "/country" in p or p.endswith("pla_watch.db")
                             for p in REVIEWED_PATHS))

    def test_stage_refuses_missing_asset_and_does_not_touch_other_routes(self):
        with tempfile.TemporaryDirectory(prefix="desks-p4a-stage-") as tmp:
            root = Path(tmp)
            src, dest = root / "generated", root / "public"
            src.mkdir()
            dest.mkdir()
            (dest / "archive.html").write_text("existing", encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                stage(src, dest)
            self.assertEqual((dest / "archive.html").read_text(), "existing")
            for rel in REVIEWED_PATHS:
                leaf = src / rel.removeprefix("output/")
                leaf.parent.mkdir(parents=True, exist_ok=True)
                leaf.write_bytes(rel.encode("utf-8"))
            written = stage(src, dest)
            self.assertEqual(len(written), 11)
            self.assertEqual((dest / "archive.html").read_text(), "existing")
            for rel in REVIEWED_PATHS:
                name = rel.removeprefix("output/")
                self.assertEqual((src / name).read_bytes(), (dest / name).read_bytes())
            with self.assertRaises(ValueError):
                stage(src, src)

    def test_sparse_overlay_preserves_live_country_and_editorial_routes(self):
        # Simulate the real case: gh-pages:indonesia.html is newer than the
        # tracked output/ version, so a full publish would regress it.
        untouched = {
            "indonesia.html": b"approved newer live bibliography",
            "analysis.html": b"published Briefs incl No.18",
            "index.html": b"existing homepage",
            "korea.html": b"reviewed five-reference Korea page",
            "briefs.css": b"existing Briefs styling",
            "briefs/no-18.html": b"unrelated editorial file",
        }
        with tempfile.TemporaryDirectory(prefix="desks-pages-overlay-") as tmp:
            root = Path(tmp)
            source, live = root / "staged", root / "gh-pages"
            for rel in REVIEWED_PATHS:
                file = source / rel.removeprefix("output/")
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(rel.encode("utf-8"))
            for path, content in untouched.items():
                file = live / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(content)
            (live / "desks.html").write_bytes(b"old map")
            names = stage(source, live)
            self.assertEqual(len(names), 11)
            for path, content in untouched.items():
                self.assertEqual((live / path).read_bytes(), content, path)
            self.assertEqual((live / "desks.html").read_bytes(),
                             b"output/desks.html")

    def test_owner_sha_pin_and_manual_only_publication(self):
        text = WF.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("approved_main_sha:", text)
        self.assertIn("type: boolean", text)
        self.assertIn("default: false", text)
        self.assertNotIn("\n  push:", text)
        self.assertNotIn("\n  schedule:", text)
        self.assertIn("test \"$(git rev-parse HEAD)\" = \"$EXPECTED_SHA\"", text)
        self.assertIn("test \"$(git rev-parse origin/main)\" = \"$(git rev-parse HEAD)\"", text)
        self.assertIn("if: inputs.publish", text)
        self.assertIn("github.event_name == 'workflow_dispatch' && 'daily-update'", text)
        self.assertIn("inputs.publish && 'pages-deploy'", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("      contents: write", text)

    def test_one_isolated_render_then_exact_allowlist_stage(self):
        text = WF.read_text(encoding="utf-8")
        self.assertEqual(text.count('python site/render.py --out "$RUNNER_TEMP/desks-render"'), 2)
        self.assertEqual(text.count("python -m scripts.stage_desks_p4a_output --from-dir"), 3)
        self.assertEqual(text.count("python -m scripts.guard_desks_p4a_output_scope"), 3)
        self.assertIn("python scripts/validate_output.py", text)
        self.assertIn("sha256sum -c", text)
        self.assertIn("test ! -e pla_watch.db-wal && test ! -e pla_watch.db-shm", text)
        self.assertNotIn("pipeline.py", text)
        self.assertNotIn("ANTHROPIC_API_KEY", text)
        self.assertNotIn("shadow_collect", text)
        self.assertNotIn("rerender_pla_watch.py", text)
        self.assertNotIn("output/japan.html", text)

    def test_no_publisher_permissions_or_unreviewed_generated_assets(self):
        text = WF.read_text(encoding="utf-8")
        self.assertEqual(text.count("actions-gh-pages@v3"), 1)
        self.assertIn("publish_dir: ${{ runner.temp }}/desks-pages-patch", text)
        self.assertIn("keep_files: true", text)
        self.assertIn("python -m scripts.guard_desks_p4a_output_scope --allow-unchanged", text)
        self.assertIn("if ! git diff --cached --quiet; then", text)
        self.assertNotIn("publish_dir: ./output", text)
        self.assertIn('find "$RUNNER_TEMP/desks-pages-patch" -type f | wc -l', text)
        self.assertIn("output/assets/flags/*.svg", text)
        self.assertIn("output/assets/flags/LICENSE", text)
        self.assertNotIn("output/assets/geo/**", text)
        self.assertNotIn("output/the-pla-watch", text)
        self.assertNotIn("output/briefs", text)


if __name__ == "__main__":
    unittest.main()
