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
             name=None, expiry=END, expired=False,
             digest="sha256:" + "a" * 64):
    return {
        "id": ident,
        "name": name or ("vietnam-ministry-shadow-%s-%s" % (run_id, attempt)),
        "size_in_bytes": 160207, "digest": digest,
        "expired": expired, "expires_at": expiry,
        "workflow_run": {"id": run_id},
    }


def job(ident, run_id=RUN, attempt=1, conclusion="success"):
    return {"id": ident, "run_id": run_id, "run_attempt": attempt,
            "name": "shadow", "status": "completed", "conclusion": conclusion}


class FakeAPI:
    def __init__(self, runs=None, artifacts=None, jobs=None):
        self.runs = [run()] if runs is None else runs
        self.arts = {RUN: [artifact(), artifact(
            11499686512, attempt=2, expiry="2027-01-05T17:15:50Z")]} if artifacts is None else artifacts
        self.jobs = jobs if jobs is not None else {
            (RUN, 1): [job(112911609417, attempt=1, conclusion="failure")],
            (RUN, 2): [job(112916943525, attempt=2, conclusion="success")],
        }
        self.routes = []

    def __call__(self, path):
        self.routes.append(path)
        if "/attempts/" in path and "/jobs?" in path:
            run_id = int(path.split("/actions/runs/")[1].split("/")[0])
            attempt = int(path.split("/attempts/")[1].split("/")[0])
            rows = self.jobs.get((run_id, attempt), [])
            return {"total_count": len(rows), "jobs": rows}
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
        self.assertEqual([a["provider_sha256"] for a in r["artifacts"]],
                         ["a" * 64, "a" * 64])
        self.assertEqual(r["holds"], ["historical_failed_or_unfinished_job"])
        self.assertEqual(len(r["historical_attempt_jobs"]), 2)
        self.assertTrue(r["historical_attempt_jobs"][0]["has_unsuccessful_job"])
        self.assertFalse(r["historical_attempt_jobs"][1]["has_unsuccessful_job"])
        self.assertEqual([x["jobs"][0]["job_id"]
                          for x in r["historical_attempt_jobs"]],
                         [112911609417, 112916943525])
        for field in ("actual_artifact_bytes_downloaded_or_hashed",
                      "deleted_or_preexisting_expired_run_history_exhaustive",
                      "failed_attempt_originals_independently_preserved",
                      "source_retention_rights_granted",
                      "production_cutover_authorized"):
            self.assertFalse(report[field])

    def test_missing_provider_digest_is_an_explicit_hold_not_fabricated(self):
        fake = FakeAPI(artifacts={RUN: [
            artifact(digest=None),
            artifact(11499686512, attempt=2),
        ]})
        row = census.collect(fake, DAY, DAY, NOW)["runs"][0]
        self.assertIn("provider_artifact_digest_unavailable", row["holds"])
        self.assertIsNone(row["artifacts"][0]["provider_sha256"])
        self.assertEqual(row["artifacts"][1]["provider_sha256"], "a" * 64)

    def test_malformed_provider_digest_fails_closed(self):
        for digest in ("sha1:" + "a" * 40, "sha256:NOT-A-DIGEST",
                       "sha256:" + "a" * 63, {"sha256": "a" * 64}):
            with self.subTest(digest=digest):
                fake = FakeAPI(artifacts={RUN: [artifact(digest=digest)]})
                with self.assertRaisesRegex(
                        census.CensusHold, "artifact_provider_digest_invalid"):
                    census.collect(fake, DAY, DAY, NOW)

    def test_changed_or_missing_historical_jobs_cannot_claim_complete_custody(self):
        no_jobs = FakeAPI(jobs={(RUN, 1): [], (RUN, 2): [
            job(112916943525, attempt=2)]})
        row = census.collect(no_jobs, DAY, DAY, NOW)["runs"][0]
        self.assertIn("attempt_has_no_retained_job_evidence", row["holds"])
        # Missing jobs are unknown, not evidence that a specific job failed.
        self.assertNotIn("historical_failed_or_unfinished_job", row["holds"])
        wrong = FakeAPI(jobs={(RUN, 1): [
            job(112911609417, run_id=123456789, attempt=1)],
            (RUN, 2): [job(112916943525, attempt=2)]})
        with self.assertRaisesRegex(census.CensusHold,
                                    "attempt_job_identity_or_status_invalid"):
            census.collect(wrong, DAY, DAY, NOW)

    def test_successful_top_level_rerun_must_keep_failed_first_attempt(self):
        value = census.collect(FakeAPI(), DAY, DAY, NOW)["runs"][0]
        self.assertEqual(value["conclusion"], "success")
        self.assertIn("historical_failed_or_unfinished_job", value["holds"])

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
