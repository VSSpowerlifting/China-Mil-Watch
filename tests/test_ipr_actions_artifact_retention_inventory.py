"""Offline fictional GitHub Actions API responses: no credentials or originals."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import inventory_ipr_actions_artifact_expiry as census

DAY = "2026-10-07"
NOW = "2026-10-15T07:30:00Z"
RUN = 37656171920
WORKFLOW = ".github/workflows/vietnam_ministry_shadow.yml"
END = "2027-01-05T17:04:25Z"


def run(run_id=RUN, attempt=2, workflow=WORKFLOW, event="workflow_dispatch",
        status="completed", conclusion="success"):
    return {
        "id": run_id, "path": workflow, "event": event, "status": status,
        "conclusion": conclusion, "run_attempt": attempt,
        "created_at": "2026-10-07T17:02:15Z",
    }


def artifact(ident=11498114543, run_id=RUN, attempt=1,
             name=None, expiry=END, expired=False):
    return {
        "id": ident,
        "name": name or ("vietnam-ministry-shadow-%s-%s" % (run_id, attempt)),
        "size_in_bytes": 160207,
        "expired": expired, "expires_at": expiry,
        "workflow_run": {"id": run_id},
    }


class FakeAPI:
    def __init__(self, runs=None, artifacts=None):
        self.runs = [run()] if runs is None else runs
        self.arts = {RUN: [artifact(), artifact(
            11499686512, attempt=2, expiry="2027-01-05T17:15:50Z")]} if artifacts is None else artifacts
        self.routes = []

    def __call__(self, path):
        self.routes.append(path)
        if "/actions/runs?" in path:
            if "page=2" in path:
                return {"total_count": len(self.runs), "workflow_runs": []}
            return {"total_count": len(self.runs), "workflow_runs": self.runs}
        if "/artifacts?" in path:
            ident = int(path.split("/actions/runs/")[1].split("/")[0])
            x = self.arts.get(ident, [])
            if "page=2" in path:
                return {"total_count": len(x), "artifacts": []}
            return {"total_count": len(x), "artifacts": x}
        raise AssertionError("Unexpected bounded API route")


class RetentionInventoryTest(unittest.TestCase):
    def test_two_real_shape_artifact_attempts_are_distinct(self):
        report = census.collect(FakeAPI(), DAY, DAY, NOW)
        self.assertEqual(report["schema"], census.SCHEMA)
        self.assertEqual(report["scoped_run_count"], 1)
        self.assertEqual(report["retained_artifact_count"], 2)
        self.assertEqual(report["retained_compressed_bytes"], 320414)
        self.assertEqual(report["earliest_retained_expiry_utc"], END)
        r = report["runs"][0]
        self.assertEqual(r["latest_run_attempt"], 2)
        self.assertEqual([a["name_attempt"] for a in r["artifacts"]], [1, 2])
        self.assertEqual(r["holds"], [])
        for field in ("actual_artifact_bytes_downloaded_or_hashed",
                      "deleted_or_preexisting_expired_run_history_exhaustive",
                      "failed_attempt_originals_independently_preserved",
                      "source_retention_rights_granted",
                      "production_cutover_authorized"):
            self.assertFalse(report[field])

    def test_failed_first_attempt_not_erased_by_second_attempt(self):
        fake = FakeAPI(artifacts={
            RUN: [artifact(11499686512, attempt=2)],
        })
        report = census.collect(fake, DAY, DAY, NOW)
        self.assertIn("earlier_attempt_receipt_not_established",
                      report["runs"][0]["holds"])
        self.assertEqual(report["runs"][0]["artifacts"][0]["name_attempt"], 2)
        self.assertFalse(report["failed_attempt_originals_independently_preserved"])

    def test_unlabeled_attempt_never_claims_provenance(self):
        fake = FakeAPI(runs=[run(attempt=1)],
                       artifacts={RUN: [artifact(
                           name="singapore-shadow-ledger-37656171920")]})
        report = census.collect(fake, DAY, DAY, NOW)
        self.assertEqual(report["runs"][0]["holds"],
                         ["artifact_attempt_name_not_decodable"])

    def test_no_artifact_and_failed_run_are_explicit_holds(self):
        fake = FakeAPI(runs=[run(status="completed", conclusion="failure")],
                       artifacts={RUN: []})
        row = census.collect(fake, DAY, DAY, NOW)["runs"][0]
        self.assertIn("run_unsuccessful_or_unfinished", row["holds"])
        self.assertIn("no_retained_artifacts", row["holds"])
        self.assertEqual(row["artifacts"], [])

    def test_expired_artifact_remains_visible_with_hold(self):
        fake = FakeAPI(runs=[run(attempt=1)],
                       artifacts={RUN: [artifact(expiry="2026-10-07T18:00:00Z",
                                                 expired=True)]})
        row = census.collect(fake, DAY, DAY, NOW)["runs"][0]
        self.assertIn("artifact_already_expired", row["holds"])
        self.assertLess(row["artifacts"][0]["hours_until_expiry"], 0)

    def test_us_shadow_collector_is_included_in_historic_coverage(self):
        old = run(run_id=32311419939, attempt=1,
                  workflow=".github/workflows/us_shadow.yml",
                  event="workflow_dispatch")
        actual = census.collect(FakeAPI(
            runs=[old], artifacts={32311419939: [artifact(
                ident=9386615960, run_id=32311419939, attempt=1,
                name="us-indopacom-shadow-ledger-32311419939",
                expiry="2026-11-17T23:01:01Z")]}),
            DAY, DAY, NOW)
        self.assertEqual(actual["scoped_run_count"], 1)
        self.assertIn("artifact_attempt_name_not_decodable",
                      actual["runs"][0]["holds"])

    def test_historical_august_manual_collector_window_allowed(self):
        base = run(run_id=32311419939, attempt=1,
                   workflow=".github/workflows/singapore_shadow.yml")
        base["created_at"] = "2026-08-19T23:01:01Z"
        fake = FakeAPI(runs=[base], artifacts={32311419939: [artifact(
            ident=9386615960, run_id=32311419939, attempt=1,
            name="singapore-shadow-ledger-32311419939",
            expiry="2026-11-17T23:01:01Z")]})
        report = census.collect(fake, "2026-08-19", "2026-08-19", NOW)
        self.assertEqual(report["earliest_retained_expiry_utc"],
                         "2026-11-17T23:01:01Z")
        self.assertEqual(report["scoped_run_count"], 1)

    def test_unknown_workflow_and_noncollection_event_skipped(self):
        fake = FakeAPI(runs=[run(workflow="other.yml")])
        self.assertEqual(census.collect(fake, DAY, DAY, NOW)["scoped_run_count"], 0)
        fake = FakeAPI(runs=[run(event="pull_request")])
        self.assertEqual(census.collect(fake, DAY, DAY, NOW)["scoped_run_count"], 0)

    def test_foreign_run_scope_rejected(self):
        fake = FakeAPI(artifacts={RUN: [artifact(run_id=55555555555)]})
        with self.assertRaisesRegex(census.CensusHold, "artifact_wrong_run_scope"):
            census.collect(fake, DAY, DAY, NOW)

    def test_pagination_is_exhaustive_and_rejects_shrunken_cursor(self):
        items = [{"id": i+1000} for i in range(101)]
        def fetch(endpoint):
            number = 2 if "page=2" in endpoint else 1
            return {"total_count": 101, "artifacts": (
                items[100:] if number == 2 else items[:100])}
        out = census.pages(fetch, "repos/" + census.REPO +
                           "/actions/runs/1234567/artifacts",
                           "artifacts", census.MAX_ARTIFACTS_PER_RUN)
        self.assertEqual(len(out), 101)
        def truncated(endpoint):
            page = 2 if "page=2" in endpoint else 1
            return {"total_count": 101, "artifacts": (
                [] if page == 2 else items[:100])}
        with self.assertRaisesRegex(census.CensusHold, "github_pagination_truncated"):
            census.pages(truncated, "scope?", "artifacts", 200)

    def test_duplicate_page_ids_and_changed_totals_rejected(self):
        ids = [{"id": i+1000} for i in range(100)]
        def dups(path):
            return {"total_count": 101, "artifacts": (
                [ids[0]] if "page=2" in path else ids)}
        with self.assertRaisesRegex(census.CensusHold, "github_pagination_duplicate_id"):
            census.pages(dups, "scope", "artifacts", 200)
        def changed(path):
            second = "page=2" in path
            return {"total_count": 102 if second else 101,
                    "artifacts": [] if second else ids}
        with self.assertRaisesRegex(census.CensusHold, "github_pagination_changed_or_excessive"):
            census.pages(changed, "scope", "artifacts", 200)

    def test_malformed_artifact_identity_and_future_attempt_rejected(self):
        for bad in (
            artifact(name="source-999999999-1"),
            artifact(attempt=3),
            dict(artifact(), expired="false"),
            dict(artifact(), size_in_bytes=-1),
        ):
            with self.subTest(bad=bad["name"]), self.assertRaises(census.CensusHold):
                census.collect(FakeAPI(artifacts={RUN: [bad]}), DAY, DAY, NOW)

    def test_out_of_scope_window_rejected(self):
        for first, last in (
            ("2026-10-15", "2026-10-14"),
            ("2026-10-01", "2026-12-31"),
            ("2026-07-31", "2026-08-01"),
            ("2026-10-15", "2026-10-17"),
        ):
            with self.subTest(first=first, last=last):
                with self.assertRaisesRegex(census.CensusHold, "requested_window_invalid"):
                    census.collect(FakeAPI(), first, last, NOW)

    def test_strict_timestamp_and_no_nontrivial_unbounded_network(self):
        with self.assertRaisesRegex(census.CensusHold, "malformed_utc_timestamp"):
            census.utc("2026-10-15T07:30:00")
        with mock.patch("subprocess.run") as task:
            task.return_value = mock.Mock(returncode=1, stdout=b"",
                                          stderr=b"SECRET_TOKEN_AND_CAPTURE")
            with self.assertRaisesRegex(census.CensusHold,
                                        "github_api_failed_or_oversize") as caught:
                census.gh_get("repos/" + census.REPO + "/actions/runs?per_page=100")
            self.assertNotIn("SECRET_TOKEN", str(caught.exception))
            self.assertNotIn("SECRET_TOKEN", task.call_args[0][0].__str__())
            self.assertFalse(task.call_args.kwargs.get("shell", False))
            self.assertEqual(task.call_args.kwargs["timeout"], 30)

    def test_fixed_error_report_has_no_source_or_credential_bytes(self):
        with mock.patch.object(census, "collect",
                               side_effect=census.CensusHold("github_pagination_truncated")):
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                status = census.main(["--from-date", DAY, "--through-date", DAY,
                                      "--as-of-utc", NOW,
                                      "--out", "/does-not-matter.json"])
        self.assertEqual(status, 2)
        obj = json.loads(buf.getvalue())
        self.assertEqual(obj["status"], "HOLD")
        self.assertFalse(obj["production_cutover_authorized"])


if __name__ == "__main__":
    unittest.main()
