"""Fail-closed contracts for recovery after a partially failed Korea source release.

GitHub can mark a standing-original run failed after source and Pages commits
if only its last public HTTPS readback is temporarily stale. That upstream
failure must not permanently strand an editor handoff, but a failure also
cannot itself authorize drafting: verify real source-to-main-to-Pages-to-HTTPS
parity independently before any model request or email.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/korea_english_owner_draft_handoff.yml"


class KoreaPrivateDraftRecoveryContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def section(self, first, last):
        self.assertEqual(self.workflow.count(first), 1)
        a = self.workflow.index(first)
        b = self.workflow.index(last, a + len(first))
        self.assertLess(a, b)
        return self.workflow[a:b]

    def test_failed_source_workflow_can_reach_guard_but_not_untrusted_branches(self):
        expression = self.section(
            "  send-unreviewed-korea-drafts-to-owner:\n",
            "    runs-on: ubuntu-latest\n",
        )
        self.assertIn("github.event_name != 'pull_request'", expression)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", expression)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", expression)
        self.assertIn("github.event.workflow_run.conclusion == 'failure'", expression)
        self.assertNotIn("conclusion == 'cancelled'", expression)
        self.assertIn("types: [completed]", self.workflow)

    def test_independent_public_readback_is_before_every_draft_and_email(self):
        pending = self.workflow.index("- name: Select published originals")
        pages = self.workflow.index("- name: Read existing Pages branch")
        verify = self.workflow.index("- name: Independently prove source and desk")
        draft = self.workflow.index("- name: Generate bounded English and analytical drafts")
        self.assertLess(pending, pages)
        self.assertLess(pages, verify)
        self.assertLess(verify, draft)

        gate = self.section(
            "      - name: Independently prove source and desk are live over exact HTTPS\n",
            "      - name: Generate bounded English and analytical drafts and send to owner only\n",
        )
        self.assertIn("id: public_readback", gate)
        self.assertIn("if: steps.pending.outputs.has_pending == 'true'", gate)
        self.assertIn("python -m scripts.verify_korea_original_deployed_readback", gate)
        self.assertIn("--main-checkout .", gate)
        self.assertIn("--pages-checkout", gate)
        self.assertIn("--require-https-readback --attempts 8", gate)
        self.assertIn("git diff --exit-code -- pla_watch.db output/", gate)
        self.assertNotIn("send_korea_english_owner_drafts", gate)
        self.assertNotIn("ANTHROPIC_API_KEY", gate)
        self.assertNotIn("SMTP", gate)

    def test_no_pending_or_failed_https_can_invoke_model(self):
        generate = self.section(
            "      - name: Generate bounded English and analytical drafts and send to owner only\n",
            "      - name: Commit only source SHA-delivery receipts, never model content\n",
        )
        self.assertIn("steps.pending.outputs.has_pending == 'true'", generate)
        self.assertIn("steps.public_readback.outcome == 'success'", generate)
        self.assertIn("steps.credentials.outputs.ready == 'true'", generate)
        self.assertIn("id: draft", generate)
        self.assertIn("--send-owner-only-unreviewed", generate)

    def test_queue_selection_checks_publication_and_dedupes_first(self):
        section = self.section(
            "      - name: Select published originals without delivered/reviewed English\n",
            "      - name: Read existing Pages branch without publish credentials\n",
        )
        self.assertIn("from scripts.send_korea_english_owner_drafts import pending", section)
        self.assertIn("selected, _ = pending()", section)
        self.assertIn('out.write("has_pending="', section)
        self.assertNotIn("source_identity", section)
        self.assertNotIn("text_original", section)

    def test_failed_draft_receipts_still_persist_but_html_never_staged(self):
        receipt = self.section(
            "      - name: Commit only source SHA-delivery receipts, never model content\n",
            "      - name: Preserve failed private-draft status after receipt persistence\n",
        )
        self.assertIn("steps.draft.outcome != 'skipped'", receipt)
        self.assertIn("git add -- research/korea_english_draft_handoff_receipts.json", receipt)
        self.assertNotIn("git add -A", receipt)
        self.assertNotIn("git add -- output/", receipt)
        self.assertIn("git diff --exit-code -- pla_watch.db output/", receipt)

    def test_focused_ci_runs_source_https_and_recovery_contracts(self):
        run = self.section(
            "      - name: Prove no-repeat private owner-email delivery and unreviewed-only drafts\n",
            "  send-unreviewed-korea-drafts-to-owner:\n",
        )
        self.assertIn("tests.test_korea_original_deployed_readback", run)
        self.assertIn("tests.test_korea_owner_handoff_recovery_contract", run)


if __name__ == "__main__":
    unittest.main()
