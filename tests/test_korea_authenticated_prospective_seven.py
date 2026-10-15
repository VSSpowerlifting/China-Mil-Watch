"""Synthetic authenticated-run-shaped seven-day Korea evidence contracts."""
import copy
import unittest

from scripts import korea_authenticated_prospective_seven as rolling
from scripts import audit_korea_actions_attempts as census
from tests.test_korea_actions_attempts import action, artifact, ledger

HISTORICAL_FAILURE = 38323793488


def scenario(*, end=19):
    runs = []
    artifacts = {}
    ledgers = [ledger(census.LOCAL, "2026-10-06", "manual-utc-date",
                      result="ok")]
    for d in range(7, end + 1):
        ident = 400000 + d
        day = "2026-10-%02d" % d
        if d == 12:
            ident = HISTORICAL_FAILURE
            run = action(ident, day + "T23:45:27Z",
                         status="completed", conclusion="failure")
        else:
            run = action(ident, day + "T20:40:00Z")
            ledgers.append(ledger(str(ident) + "-1", day, "schedule-slot"))
        runs.append(run)
        artifacts[str(ident)] = artifact(ident)
    return ([{"total_count": len(runs), "workflow_runs": runs}],
            artifacts, ledgers)


def judge(data, *, now="2026-10-20T00:00:00Z"):
    return rolling.evaluate(*data, as_of_utc=now)


class KoreaAuthenticatedProspectiveSeven(unittest.TestCase):
    def test_rolling_seven_true_without_rewriting_failed_october_twelve(self):
        r = judge(scenario())
        self.assertTrue(r["seven_day_actions_and_ledger_candidate"])
        self.assertEqual(r["prospective_dates"],
                         ["2026-10-%02d" % d for d in range(13, 20)])
        self.assertEqual(r["unqualified_dates"], [])
        self.assertEqual(r["prospective_consecutive_successful_days"], 7)
        self.assertFalse(r["historical_october_12_gap_automatically_repaired"])
        for key in ("source_rights_approved", "model_or_email_authorized",
                    "production_or_publication_authorized",
                    "caller_evidence_authenticated_by_this_function",
                    "capture_bytes_reverified_by_this_function",
                    "publisher_completeness_proved"):
            self.assertIs(r[key], False)

    def test_october_fourteen_shape_has_streak_two_and_failed_day_in_window(self):
        r = judge(scenario(end=14), now="2026-10-15T00:00:00Z")
        self.assertFalse(r["seven_day_actions_and_ledger_candidate"])
        self.assertIn("2026-10-12", r["unqualified_dates"])
        self.assertEqual(r["prospective_consecutive_successful_days"], 2)
        self.assertEqual(r["latest_mature_date"], "2026-10-14")

    def test_grace_boundary_blocks_early_seven_day_claim(self):
        a = scenario()
        pre = judge(a, now="2026-10-19T23:46:59Z")
        self.assertEqual(pre["latest_mature_date"], "2026-10-18")
        self.assertFalse(pre["seven_day_actions_and_ledger_candidate"])
        complete = judge(a, now="2026-10-19T23:47:00Z")
        self.assertTrue(complete["seven_day_actions_and_ledger_candidate"])

    def test_late_and_manual_dispatch_cannot_forge_a_scheduled_date(self):
        base = scenario()
        for adjustment in ("manual", "rerun", "failure", "unhealthy",
                           "bad_target", "missing_ledger", "extra_artifact",
                           "duplicate_attempt"):
            pages, artifacts, ledgers = copy.deepcopy(base)
            last = pages[0]["workflow_runs"][-1]
            ident = last["id"]
            if adjustment == "manual":
                last["event"] = "workflow_dispatch"
            elif adjustment == "rerun":
                last["run_attempt"] = 2
                artifacts[str(ident)] = artifact(ident, attempt=2)
            elif adjustment == "failure":
                last["conclusion"] = "failure"
            elif adjustment == "unhealthy":
                ledgers[-1]["health"] = "failed"
            elif adjustment == "bad_target":
                ledgers[-1]["target_date"] = "2026-10-18"
            elif adjustment == "missing_ledger":
                ledgers.pop()
            elif adjustment == "extra_artifact":
                artifacts[str(ident)]["artifacts"].append(
                    {"name": "candidate-shadow-indonesia-%d-1" % ident})
                artifacts[str(ident)]["total_count"] = 2
            else:
                new_id = 500000
                pages[0]["workflow_runs"].append(action(
                    new_id, "2026-10-19T22:00:00Z"))
                pages[0]["total_count"] += 1
                artifacts[str(new_id)] = artifact(new_id)
                ledgers.append(ledger(str(new_id) + "-1",
                                      "2026-10-19", "schedule-slot"))
            with self.subTest(adjustment=adjustment):
                r = judge((pages, artifacts, ledgers))
                self.assertFalse(r["seven_day_actions_and_ledger_candidate"])
                self.assertIn("2026-10-19", r["unqualified_dates"])

    def test_unclassified_shared_scheduled_attempt_blocks_candidate(self):
        # Other desk artifacts can be safely scoped, but an unselected
        # scheduled attempt might be a failed Korea run, not proof of silence.
        pages, artifacts, ledgers = scenario()
        unknown = action(620019, "2026-10-19T20:55:00Z")
        pages[0]["workflow_runs"].append(unknown)
        pages[0]["total_count"] += 1
        artifacts[str(unknown["id"])] = {"total_count": 0, "artifacts": []}
        r = judge((pages, artifacts, ledgers))
        self.assertFalse(r["seven_day_actions_and_ledger_candidate"])
        self.assertIn("2026-10-19", r["unqualified_dates"])
        self.assertIn("2026-10-19", r["ambiguous_shared_scheduled_dates"])
        self.assertEqual(r["prospective_consecutive_successful_days"], 0)

        # The exact same successful Indonesia action is scoped and does not
        # taint an otherwise genuine seven-day Korean success sequence.
        artifacts[str(unknown["id"])] = artifact(unknown["id"], "indonesia")
        clean = judge((pages, artifacts, ledgers))
        self.assertTrue(clean["seven_day_actions_and_ledger_candidate"])
        self.assertEqual(clean["ambiguous_shared_scheduled_dates"], [])

    def test_12_manual_recovery_does_not_rewrite_original_failure(self):
        pages, artifacts, ledgers = scenario(end=14)
        manual = action(999991, "2026-10-13T09:00:00Z",
                        event="workflow_dispatch")
        pages[0]["workflow_runs"].append(manual)
        pages[0]["total_count"] += 1
        artifacts[str(manual["id"])] = artifact(manual["id"])
        ledgers.append(ledger("999991-1", "2026-10-12", "explicit"))
        r = judge((pages, artifacts, ledgers), now="2026-10-15T00:00:00Z")
        self.assertFalse(r["seven_day_actions_and_ledger_candidate"])
        self.assertIn("2026-10-12", r["unqualified_dates"])
        self.assertFalse(r["historical_october_12_gap_automatically_repaired"])

    def test_unknown_artifact_or_changed_originals_cannot_fake_pass(self):
        pages, artifacts, ledgers = scenario()
        artifacts.pop(str(pages[0]["workflow_runs"][-1]["id"]))
        with self.assertRaises(Exception):
            judge((pages, artifacts, ledgers))
        pages, artifacts, ledgers = scenario()
        ledgers.pop(0)
        with self.assertRaises(Exception):
            judge((pages, artifacts, ledgers))

    def test_current_authenticated_runner_contains_rolling_census(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        text = (root / "scripts" /
                "run_korea_authenticated_actions_census.py").read_text()
        self.assertIn("from scripts.korea_authenticated_prospective_seven import evaluate",
                      text)
        self.assertIn('"prospective_seven_slot_observation": rolling', text)
        self.assertIn('"october_12_original_failure_remains_unrepaired": True',
                      text)
        workflow = (root / ".github" / "workflows" /
                    "korea_authenticated_actions_census.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("  schedule:", workflow)
        self.assertIn("  actions: read", workflow)
        self.assertIn("/state/ledger/**", workflow)
        self.assertNotIn("state/captures", workflow)


if __name__ == "__main__":
    unittest.main()
