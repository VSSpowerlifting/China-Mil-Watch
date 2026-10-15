"""Offline guard for the manually dispatched Korea HWPX fidelity workflow.

Regression of the 2026-10-14 operator run that cloned correctly but launched
`python -m scripts.audit_korea_source_fidelity` from the outer workspace.
No publisher requests, GitHub dispatch, originals or approval state involved.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/korea_source_fidelity_review.yml"


class KoreaFidelityWorkflowBindings(unittest.TestCase):
    def test_module_runs_from_actual_repo_checkout_and_status_uses_same_root(self):
        raw = WORKFLOW.read_text(encoding="utf-8")
        start = "      - name: Read exact Korean shadow branch and prepare private reviewer packet\n"
        end = "      - name: Preserve machine-only review packet for actual human source comparison\n"
        self.assertEqual(raw.count(start), 1)
        self.assertEqual(raw.count(end), 1)
        step = raw.split(start, 1)[1].split(end, 1)[0]
        self.assertIn("        working-directory: repo\n", step)
        self.assertIn("python -m scripts.audit_korea_source_fidelity", step)
        self.assertIn('--state-repo "$RUNNER_TEMP/korea-state"', step)
        self.assertIn('--state-commit "$tip"', step)
        self.assertIn('--as-of "$as_of"', step)
        self.assertIn('--out "$RUNNER_TEMP/korea-source-review"', step)
        self.assertIn('git -C "$RUNNER_TEMP/korea-state" status', step)
        self.assertIn('test -z "$(git status --porcelain --untracked-files=all)"', step)
        self.assertNotIn('git -C repo status', step)
        self.assertNotIn("PYTHONPATH=", step)
        self.assertIn('tip="$(git -C "$RUNNER_TEMP/korea-state" rev-parse HEAD)"', step)

    def test_manual_only_and_reviewers_cannot_approve_by_running_workflow(self):
        raw = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("  workflow_dispatch:", raw)
        self.assertNotIn("  schedule:", raw)
        self.assertIn("          persist-credentials: false", raw)
        self.assertIn("          ref: main", raw)
        self.assertIn("          path: repo", raw)
        self.assertIn("      - name: Run offline Korea fidelity regressions", raw)
        self.assertIn("      - name: Preserve machine-only review packet for actual human source comparison", raw)
        self.assertNotIn("ANTHROPIC_API_KEY", raw)
        self.assertNotIn("IPR_SMTP", raw)


if __name__ == "__main__":
    unittest.main()
