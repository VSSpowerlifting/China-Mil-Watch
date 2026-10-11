"""No-network Sunday editorial dispatch diagnostics and false-success guards."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from scripts.audit_sunday_editor_delivery import (
    DeliveryAuditError, WORKFLOW, diagnose, fetch_live, parse_utc,
)

SUNDAY = parse_utc("2026-10-11T21:00:00Z")
WINTER = parse_utc("2027-11-14T21:00:00Z")


def row(*, id=9001, event="schedule", stamp="2026-10-11T19:25:49Z",
        status="completed", conclusion="success", path=WORKFLOW):
    return {
        "id": id, "event": event, "created_at": stamp, "status": status,
        "conclusion": conclusion, "path": path,
    }


def snapshot(*entries, state="active"):
    return {"workflow_state": state, "workflow_runs": list(entries)}


class ReadOnlyObserverTests(unittest.TestCase):
    def test_missing_october_11_uses_grace_then_flags_dispatch_absence(self):
        early = diagnose(snapshot(), now=parse_utc("2026-10-11T18:00:00Z"))
        grace = diagnose(snapshot(), now=parse_utc("2026-10-11T20:20:00Z"))
        late = diagnose(snapshot(), now=SUNDAY, daily_marker="2026-10-11")
        self.assertEqual(early["verdict"], "NOT_DUE")
        self.assertEqual(grace["verdict"], "WITHIN_SCHEDULER_GRACE")
        self.assertEqual(late["verdict"], "MISSING_SCHEDULED_RUN")
        self.assertEqual(late["week_ending"], "2026-10-10")
        self.assertEqual(late["collection_marker_verdict"], "SAME_SUNDAY_MARKER_PRESENT")
        self.assertEqual(late["editor_email"], "NOT_VERIFIED_FROM_ACTIONS")
        self.assertFalse(late["automatic_retry_authorized"])

    def test_manual_dispatch_cannot_substitute_for_missing_scheduled_run(self):
        manual = row(event="workflow_dispatch")
        self.assertEqual(diagnose(snapshot(manual), now=SUNDAY)["verdict"],
                         "MISSING_SCHEDULED_RUN")
        self.assertEqual(diagnose(snapshot(manual), now=SUNDAY)
                         ["manual_runs_same_sunday"], [manual["id"]])

    def test_success_cannot_claim_gmail_sent_receipt(self):
        result = diagnose(snapshot(row()), now=SUNDAY)
        self.assertEqual(result["verdict"], "RUN_SUCCEEDED_EMAIL_UNCONFIRMED")
        self.assertEqual(result["editor_email"], "NOT_VERIFIED_FROM_ACTIONS")
        self.assertEqual(result["publication_approval"], "NOT_ATTESTED")

    def test_skipped_failed_and_active_are_distinct(self):
        for status, conclusion, expected in (
            ("completed", "skipped", "RUN_SKIPPED"),
            ("completed", "failure", "RUN_FAILED_OR_CANCELLED"),
            ("completed", "cancelled", "RUN_FAILED_OR_CANCELLED"),
            ("in_progress", None, "WORKFLOW_IN_PROGRESS"),
            ("queued", None, "WORKFLOW_IN_PROGRESS"),
        ):
            with self.subTest(status=status, conclusion=conclusion):
                output = diagnose(snapshot(row(status=status, conclusion=conclusion)),
                                  now=SUNDAY)
                self.assertEqual(output["verdict"], expected)

    def test_explicitly_disabled_workflow_trumps_due_grace(self):
        result = diagnose(snapshot(state="disabled_manually"), now=SUNDAY)
        self.assertEqual(result["verdict"], "WORKFLOW_DISABLED")

    def test_duplicated_scheduled_execution_is_not_success(self):
        result = diagnose(snapshot(row(), row(id=9002)), now=SUNDAY)
        self.assertEqual(result["verdict"], "MULTIPLE_SCHEDULED_RUNS_NEED_REVIEW")
        self.assertFalse(result["automatic_retry_authorized"])

    def test_wrong_workflow_and_wrong_day_do_not_count(self):
        irrelevant = row(id=41, path=".github/workflows/vietnam_weekly_editorial_readiness.yml")
        prior = row(id=42, stamp="2026-10-04T19:20:00Z")
        future = row(id=43, stamp="2026-10-12T04:30:00Z")
        self.assertEqual(diagnose(snapshot(irrelevant, prior, future),
                                  now=SUNDAY)["verdict"], "MISSING_SCHEDULED_RUN")

    def test_new_york_local_sunday_across_utc_monday(self):
        now = parse_utc("2026-10-12T02:00:00Z")
        self.assertEqual(diagnose(snapshot(row()), now=now)["week_ending"],
                         "2026-10-10")
        monday = parse_utc("2026-10-12T08:00:00Z")
        out = diagnose(snapshot(row()), now=monday, daily_marker="2026-10-11")
        self.assertEqual(out["week_ending"], "2026-10-10")
        self.assertEqual(out["collection_marker_verdict"],
                         "HISTORICAL_MARKER_NOT_ATTESTED")

    def test_winter_utc_schedule_is_still_1917(self):
        result = diagnose(snapshot(), now=WINTER)
        self.assertEqual(result["week_ending"], "2027-11-13")
        self.assertEqual(result["expected_scheduled_utc"],
                         "2027-11-14T19:17:00Z")

    def test_metadata_must_be_well_typed_and_not_false_positive(self):
        invalid = [
            {"workflow_state": "active", "workflow_runs": {}},
            snapshot({"event": "schedule", "path": WORKFLOW,
                      "created_at": "2026-10-11", "status": "completed",
                      "conclusion": "success", "id": 3}),
            snapshot(row(id=1), row(id=1)),
            snapshot(row(id=True)),
            snapshot(row(status="mystery")),
        ]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(DeliveryAuditError):
                diagnose(data, now=SUNDAY)

    def test_read_only_fetch_requires_valid_repo_and_gets_exact_workflow(self):
        def fake_get(url, token):
            self.assertNotIn("workflow_dispatch", url)
            self.assertNotIn("POST", url)
            self.assertEqual(token, "")
            return ({"state": "active"} if "/runs?" not in url
                    else {"workflow_runs": [row()]})
        with patch("scripts.audit_sunday_editor_delivery._github_get",
                   side_effect=fake_get) as getter:
            result = fetch_live("VSSpowerlifting/China-Mil-Watch")
        self.assertEqual(result["workflow_state"], "active")
        self.assertEqual(len(result["workflow_runs"]), 1)
        self.assertEqual(getter.call_count, 2)
        with self.assertRaises(DeliveryAuditError):
            fetch_live("../invalid\\repo")


if __name__ == "__main__":
    unittest.main()
