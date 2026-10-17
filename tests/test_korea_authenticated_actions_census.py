"""No network: exact-workflow pagination, artifact provenance, shadow Git pin."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import audit_indonesia_shadow_provenance as provenance
from scripts import run_korea_authenticated_actions_census as live


def run(ident, date, event="schedule"):
    return {"id": ident, "workflow_id": provenance.WORKFLOW_ID,
            "name": provenance.WORKFLOW_NAME,
            "run_attempt": 1, "status": "completed",
            "conclusion": "success", "event": event,
            "head_branch": "main", "created_at": date}


def artifact(ident, desk="korea"):
    return {"total_count": 1, "artifacts": [{
        "name": "candidate-shadow-%s-%d-1" % (desk, ident),
        "expired": False}]}


class FakeGitHub:
    def __init__(self, runs):
        self.runs = runs
        self.count = len(runs)
        self.artifacts = {r["id"]: artifact(r["id"]) for r in runs}
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        if "/actions/workflows/%d/runs?" % provenance.WORKFLOW_ID in url:
            p = int(url.split("page=")[-1])
            return {"total_count": self.count,
                    "workflow_runs": self.runs[(p-1)*100:p*100]}
        if "/actions/runs/" in url and "/artifacts?" in url:
            ident = int(url.split("/actions/runs/")[1].split("/")[0])
            return self.artifacts[ident]
        raise AssertionError("unexpected network endpoint")


class KoreaAuthenticatedActionsCensus(unittest.TestCase):
    def setUp(self):
        self.api = FakeGitHub([
            run(1001, "2026-10-06T21:21:16Z", "workflow_dispatch"),
            run(1002, "2026-10-07T22:17:12Z"),
        ])
        self.now = "2026-10-07T23:55:00Z"

    def test_real_api_fetch_shape_preserves_exact_workflow_and_artifact_scope(self):
        e = live.fetch_authenticated(self.api, self.now)
        self.assertEqual(e["scoped_runs"], 2)
        self.assertEqual(e["api_pages_read"], 1)
        self.assertEqual(set(e["artifacts"]), {"1001", "1002"})
        self.assertTrue(all("/actions/" in url for url in self.api.calls))

    def test_live_census_uses_current_canonical_repository_and_rejects_legacy(self):
        # This executes in IndoPacificRecord. A stale hardcoded repository
        # rejects every real workflow_dispatch before any authenticated census.
        self.assertEqual(live.REPO, "VSSpowerlifting/IndoPacificRecord")
        self.assertEqual(live.API,
                         "https://api.github.com/repos/VSSpowerlifting/IndoPacificRecord")
        live.fetch_authenticated(self.api, self.now)
        self.assertTrue(self.api.calls)
        self.assertTrue(all(url.startswith(live.API + "/actions/")
                            for url in self.api.calls))
        # Fail closed on the *old* repository name, with no network request.
        with patch.dict("os.environ", {
            "GITHUB_REPOSITORY": "VSSpowerlifting/China-Mil-Watch",
            "GH_TOKEN": "synthetic-not-a-secret",
        }):
            with self.assertRaisesRegex(
                    provenance.ProvenanceError, "exact repository"):
                live.main([
                    "--shadow-checkout", "/nonexistent-test-shadow",
                    "--output", "/nonexistent-test-receipt.json",
                ])

    def test_pagination_beyond_one_page_must_be_complete(self):
        before = [run(1500+i, "2026-10-05T22:00:00Z")
                  for i in range(99)]
        api = FakeGitHub(before + self.api.runs)
        e = live.fetch_authenticated(api, self.now)
        self.assertEqual(e["total_repository_workflow_runs"], 101)
        self.assertEqual(e["api_pages_read"], 2)
        self.assertEqual(e["scoped_runs"], 2)
        self.assertEqual(len(e["artifacts"]), 2)
        self.assertEqual(sum("workflows/" in url for url in api.calls), 2)

    def test_short_page_or_changed_total_refuses_to_claim_full_history(self):
        self.api.count = 3
        with self.assertRaisesRegex(provenance.ProvenanceError, "incomplete"):
            live.fetch_authenticated(self.api, self.now)
        self.api.count = 2
        self.api.runs[1]["id"] = self.api.runs[0]["id"]
        with self.assertRaisesRegex(provenance.ProvenanceError, "duplicate"):
            live.fetch_authenticated(self.api, self.now)

    def test_expired_missing_or_partial_artifacts_fail_closed(self):
        self.api.artifacts[1002]["artifacts"][0]["expired"] = True
        with self.assertRaisesRegex(provenance.ProvenanceError, "expired"):
            live.fetch_authenticated(self.api, self.now)
        self.api.artifacts[1002] = {"total_count": 2,
                                    "artifacts": artifact(1002)["artifacts"]}
        with self.assertRaisesRegex(provenance.ProvenanceError, "incomplete"):
            live.fetch_authenticated(self.api, self.now)

    def test_wrong_workflow_and_unsafe_dates_are_refused(self):
        self.api.runs[1]["workflow_id"] = 123
        with self.assertRaisesRegex(provenance.ProvenanceError, "foreign"):
            live.fetch_authenticated(self.api, self.now)
        self.api.runs[1]["workflow_id"] = provenance.WORKFLOW_ID
        with self.assertRaisesRegex(provenance.ProvenanceError, "outside"):
            live.fetch_authenticated(self.api, "2026-12-01T00:00:00Z")

    def _checkout(self, root):
        root.mkdir()
        subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(root), "checkout", "-qb",
                        "shadow/korea-policy-briefing"], check=True)
        folder = root/"state"/"ledger"
        folder.mkdir(parents=True)
        for key, day, source in (("local-native-20261006-korea", "2026-10-06",
                                 "manual-utc-date"),
                                 ("1001-1", "2026-10-06", "manual-utc-date"),
                                 ("1002-1", "2026-10-07", "schedule-slot")):
            (folder/(key+".json")).write_text(json.dumps({
                "desk": "korea", "run_id": key, "target_date": day,
                "target_date_source": source, "health": "ok",
                "result": "ok"}))
        subprocess.run(["git", "-C", str(root), "add", "state/ledger"],
                       check=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.name=CI",
                        "-c", "user.email=ci@example.org", "commit",
                        "-qm", "Test pinned ledger snapshot"], check=True)

    def test_git_pinned_shadow_checkout_and_live_api_still_hold_all_approvals(self):
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t)/"shadow"
            self._checkout(repo)
            result = live.produce(self.api, repo, self.now)
            self.assertEqual(result["verdict"],
                             "CONSISTENT_UNAUTHENTICATED_CENSUS_ONLY")
            self.assertEqual(len(result["observed_git_state_commit"]), 40)
            self.assertTrue(result["github_api_request_authenticated"])
            self.assertFalse(result["github_retention_completeness_certified"])
            self.assertFalse(result["production_eligible"])
            self.assertFalse(result["human_day7_review_completed"])

    def test_wrong_or_missing_branch_and_symlink_checkout_are_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            repo = root/"shadow"
            self._checkout(repo)
            subprocess.run(["git", "-C", str(repo), "checkout", "-qb",
                            "irrelevant"], check=True)
            with self.assertRaisesRegex(provenance.ProvenanceError, "Korea shadow"):
                live.pinned_ledger_checkout(repo)
            link = root/"linked"
            link.symlink_to(repo, target_is_directory=True)
            with self.assertRaisesRegex(provenance.ProvenanceError, "symlink"):
                live.pinned_ledger_checkout(link)


    def test_manual_workflow_really_sparsely_checks_out_only_ledgers(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/korea_authenticated_actions_census.yml"
                    ).read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("  schedule:", workflow)
        self.assertNotIn("  push:", workflow)
        self.assertIn("  actions: read", workflow)
        self.assertIn("  contents: read", workflow)
        self.assertIn("ref: shadow/korea-policy-briefing", workflow)
        self.assertIn("sparse-checkout-cone-mode: false", workflow)
        self.assertIn("/state/ledger/**", workflow)
        self.assertNotIn("state/captures", workflow)
        self.assertEqual(workflow.count("persist-credentials: false"), 2)
        self.assertIn("confirm_read_only", workflow)


if __name__ == "__main__":
    unittest.main()
