"""Offline contracts for authenticated Indonesia/Korea GitHub run census."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import fetch_indonesia_actions_census as census
from scripts import audit_indonesia_actions_attempts as inventory
from scripts import audit_indonesia_shadow_provenance as prov


def run(number, when, *, event="schedule", desk="indonesia"):
    return {
        "id": number, "workflow_id": prov.WORKFLOW_ID,
        "name": prov.WORKFLOW_NAME, "created_at": when,
        "head_branch": "main", "head_sha": "a" * 40, "run_attempt": 1,
        "event": event, "status": "completed", "conclusion": "success",
        "actor": {"login": "github-actions[bot]"}, "desk": desk,
    }


class PinnedCensusContracts(unittest.TestCase):
    def setUp(self):
        self.runs = [
            run(101, "2026-10-06T21:21:12Z", event="workflow_dispatch"),
            run(102, "2026-10-07T21:58:19Z"),
            run(103, "2026-10-07T22:00:00Z", desk="korea"),
        ]
        self.requests = []

    def fake_pages(self, repo, route, query, kind, token, maximum):
        self.requests.append((repo, route, query, kind, maximum))
        if kind == "workflow_runs":
            return {"total_count": len(self.runs),
                    "workflow_runs": copy.deepcopy(self.runs)}
        ident = int(route.split("/")[3])
        desk = next(x["desk"] for x in self.runs if x["id"] == ident)
        return {"total_count": 1, "artifacts": [{
            "id": ident * 100, "name":
            "candidate-shadow-%s-%s-1" % (desk, ident)}]}

    def test_day_zero_through_day_one_is_exhaustively_attributed(self):
        pages, artifacts = census.export(census.OWNER_REPO, "fake-token",
                                         "2026-10-07", self.fake_pages)
        self.assertEqual(pages[0]["total_count"], 3)
        self.assertEqual(len(artifacts), 3)
        self.assertEqual(self.requests[0][2]["created"],
                         "2026-10-06..2026-10-08")
        self.assertEqual(self.requests[0][1],
                         "/actions/workflows/%d/runs" % prov.WORKFLOW_ID)
        ledgers = [{"run_id": "local-native-20261006-indonesia"},
                   {"run_id": "101-1"}, {"run_id": "102-1"}]
        outcome = inventory.scan(pages, artifacts, ledgers, "2026-10-07")
        self.assertEqual(outcome["verdict"],
                         "CONSISTENT_THROUGH_AS_OF_NOT_DAY7_SIGNOFF")
        self.assertEqual(outcome["counts"]["indonesia_attempts"], 2)
        self.assertEqual(outcome["counts"]["korea_attempts"], 1)
        self.assertFalse(outcome["day7_human_checkpoint_completed"])

    def test_missing_desk_artifact_fails_closed(self):
        def fake(repo, route, query, kind, token, maximum):
            x = self.fake_pages(repo, route, query, kind, token, maximum)
            if route == "/actions/runs/102/artifacts":
                return {"total_count": 0, "artifacts": []}
            return x
        pages, artifacts = census.export(census.OWNER_REPO, "token",
                                         "2026-10-07", fake)
        ledgers = [{"run_id": "local-native-20261006-indonesia"},
                   {"run_id": "101-1"}, {"run_id": "102-1"}]
        result = inventory.scan(pages, artifacts, ledgers, "2026-10-07")
        self.assertIn("shared_workflow_unattributed_run", result["holds"])
        self.assertEqual(result["verdict"], "HOLD")

    def test_unexpected_workflow_or_branch_rejected(self):
        mutations = [
            lambda row: row.update(workflow_id=1),
            lambda row: row.update(head_branch="other"),
            lambda row: row.update(event="push"),
            lambda row: row.update(created_at="2026-10-04T21:58:00Z"),
        ]
        for alter in mutations:
            bad = copy.deepcopy(self.runs)
            alter(bad[1])
            original = self.runs
            self.runs = bad
            with self.subTest(alter=alter), self.assertRaises(
                    (census.CensusError, prov.ProvenanceError)):
                census.export(census.OWNER_REPO, "token",
                              "2026-10-07", self.fake_pages)
            self.runs = original

    def test_requires_unique_pagination_and_exact_api_totals(self):
        def page_factory(rows, count, kind="workflow_runs"):
            return {"total_count": count, kind: rows}
        rows = [{"id": i} for i in range(1, 102)]
        pages = iter([page_factory(rows[:100], 101),
                      page_factory(rows[100:], 101)])
        with mock.patch.object(census, "request_json",
                               side_effect=lambda url, token: next(pages)):
            data = census.paginated(census.OWNER_REPO,
                                    "/actions/workflows/376840713/runs",
                                    {"created": "2026-10-06..2026-10-08"},
                                    "workflow_runs", "dummy", 500)
        self.assertEqual(data["total_count"], 101)
        self.assertEqual(len(data["workflow_runs"]), 101)
        invalid = [
            [page_factory([{"id": 1}], 2)],
            [page_factory([{"id": 1}, {"id": 1}], 2)],
            [page_factory([], 501)],
            [page_factory([{"id": 1}], 0)],
        ]
        for chunks in invalid:
            with mock.patch.object(census, "request_json",
                                   side_effect=chunks):
                with self.assertRaises((census.CensusError, StopIteration)):
                    census.paginated(census.OWNER_REPO, "/actions/runs/1/artifacts",
                                     {}, "workflow_runs", "x", 500)

    def test_token_and_repository_boundaries(self):
        with self.assertRaises(census.CensusError):
            census.endpoint("attacker/repository", "/actions/runs", {})
        with self.assertRaises(census.CensusError):
            census.endpoint(census.OWNER_REPO, "/contents/README", {})
        with self.assertRaises(census.CensusError):
            census.request_json("https://evil.example/actions/runs", "secret")
        with self.assertRaises(census.CensusError):
            census.request_json(
                "https://api.github.com/repos/" + census.OWNER_REPO +
                "/actions/runs", "short")

    def test_unverified_api_is_not_a_successful_audit(self):
        with tempfile.TemporaryDirectory() as td:
            receipt = Path(td) / "receipt.json"
            with mock.patch.object(census, "audit",
                                   side_effect=census.CensusError("internal secret")):
                with mock.patch.dict("os.environ", {"GH_TOKEN": "token"}, clear=False):
                    code = census.main([
                        "--state-repo", td,
                        "--state-commit", "a" * 40,
                        "--as-of", "2026-10-11",
                        "--receipt", str(receipt),
                    ])
            self.assertEqual(code, 2)
            data = receipt.read_text()
            self.assertIn("HOLD_UNVERIFIED_INPUTS", data)
            self.assertNotIn("internal secret", data)
            self.assertIn('"production_eligible": false', data)


if __name__ == "__main__":
    unittest.main()
