"""Fail-closed contract for Philippine AFP scheduled Actions attempt artifacts.

No publisher calls, capture downloads, shadow database writes or credentials.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ph_afp_shadow.yml"
ALLOWED = (
    "${{ runner.temp }}/shadow-state/state/ledger/*.json",
    "${{ runner.temp }}/shadow-state/state/evidence/*.json",
    "${{ runner.temp }}/shadow-state/state/clock.json",
    "${{ runner.temp }}/ph-afp-run.log",
)


class AFPArtifactBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.block = cls.text.split("      - name: Preserve metadata-only attempt evidence", 1)[1]

    def test_success_or_failure_still_preserves_attempt_metadata(self):
        for required in ("if: always()", "uses: actions/upload-artifact@v4",
                         "retention-days: 90", "if-no-files-found: warn"):
            with self.subTest(required=required):
                self.assertIn(required, self.block)

    def test_only_predeclared_flat_metadata_and_log_paths_are_uploaded(self):
        block = self.block.split("          path: |", 1)[1]
        lines = block.split("          if-no-files-found:", 1)[0]
        observed = tuple(line.strip() for line in lines.splitlines() if line.strip())
        self.assertEqual(observed, ALLOWED)
        self.assertEqual(len(set(observed)), len(ALLOWED))

    def test_never_upload_original_binary_or_full_shadow_db(self):
        paths = self.block.split("          path: |", 1)[1]
        paths = paths.split("          if-no-files-found:", 1)[0]
        for forbidden in (
            "shadow-state/state/\n", "state/shadow.db", "state/captures",
            "evidence/payloads", "payloads/*.bin", "state/*.bin",
            "output/", "pla_watch.db",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, paths)

    def test_collector_gates_and_actual_state_push_remain_separate(self):
        self.assertIn("  schedule:", self.text)
        self.assertIn("  workflow_dispatch:", self.text)
        self.assertIn("      - name: Preserve completed shadow attempt", self.text)
        self.assertIn("git push origin HEAD:refs/heads/shadow/ph-afp", self.text)
        self.assertNotIn("gh-pages", self.text)
        self.assertNotIn("git push origin HEAD:refs/heads/main", self.text)


if __name__ == "__main__":
    unittest.main()
