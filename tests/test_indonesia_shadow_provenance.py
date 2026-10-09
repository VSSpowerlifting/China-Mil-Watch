"""Synthetic isolated Git-state tests: Indonesia shadow provenance never mutates or fetches."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import audit_indonesia_shadow_provenance as audit


def digest(data):
    return hashlib.sha256(data).hexdigest()


class IndonesiaProvenance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-indonesia-proof-")
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "state-repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Local test")
        self.git("config", "user.email", "test@example.invalid")
        self.b1, self.b2 = digest(b"dayzero bytes"), digest(b"after schedule")
        self.actions = [
            {"id": 37533271730, "run_attempt": 1,
             "workflow_id": audit.WORKFLOW_ID,
             "name": audit.WORKFLOW_NAME, "event": "workflow_dispatch",
             "status": "completed", "conclusion": "success",
             "head_branch": "main", "head_sha": "b" * 40,
             "created_at": "2026-10-06T21:21:00Z"},
            {"id": 37693074726, "run_attempt": 1,
             "workflow_id": audit.WORKFLOW_ID,
             "name": audit.WORKFLOW_NAME, "event": "schedule",
             "status": "completed", "conclusion": "success",
             "head_branch": "main", "head_sha": "c" * 40,
             "created_at": "2026-10-07T21:58:00Z"},
        ]
        self.ledgers = [
            self.entry("local-native-20261006-indonesia",
                       "2026-10-06T16:52:15+00:00", "2026-10-06T16:53:00+00:00",
                       "2026-10-06", None, self.b1, "a" * 40,
                       "manual-utc-date"),
            self.entry("37533271730-1",
                       "2026-10-06T21:21:00+00:00", "2026-10-06T21:22:00+00:00",
                       "2026-10-06", self.b1, self.b1, "b" * 40,
                       "manual-utc-date", result="ok_all_duplicates"),
            self.entry("37693074726-1",
                       "2026-10-07T21:58:00+00:00", "2026-10-07T21:59:00+00:00",
                       "2026-10-07", self.b1, self.b2, "c" * 40,
                       "schedule-slot"),
        ]
        self.clock = {"desk": "indonesia",
                      "day_zero_run_id": "local-native-20261006-indonesia",
                      "day_zero_utc": "2026-10-06T16:52:15+00:00"}
        self.write_pinned()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args],
                              check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE).stdout.decode().strip()

    def entry(self, run, started, finished, target, before, after, commit,
              date_source, result="ok"):
        return {
            "desk": "indonesia", "run_id": run,
            "collector_commit": commit, "started_utc": started,
            "finished_utc": finished, "target_date": target,
            "target_date_source": date_source, "health": "ok", "result": result,
            "state_sha256_before": before, "state_sha256_after": after,
            "fetch_failures": 0, "extraction_failures": 0, "access_failures": 0,
        }

    def write_pinned(self):
        state = self.repo / "state"
        ledger = state / "ledger"
        ledger.mkdir(parents=True, exist_ok=True)
        (state / "clock.json").write_text(json.dumps(self.clock), encoding="utf-8")
        (state / "shadow.db").write_bytes(b"after schedule")
        for i, item in enumerate(self.ledgers):
            (ledger / ("2026100%d-%s.json" % (i + 6, item["run_id"]))).write_text(
                json.dumps(item), encoding="utf-8")
        self.git("add", "state")
        self.git("commit", "-qm", "pinned Indonesia state")
        self.commit = self.git("rev-parse", "HEAD")
        self.git("branch", audit.STATE_BRANCH)

    def load(self):
        return audit.pinned_state(self.repo, self.commit)

    def report(self):
        clock, ledgers, h = self.load()
        actions = audit.parse_actions_export(
            {"total_count": len(self.actions), "workflow_runs": self.actions})
        return audit.assess(clock, ledgers, h, actions)

    def test_verified_local_manual_and_scheduled_distinct(self):
        result = self.report()
        self.assertEqual(result["ledgers_checked"], 3)
        self.assertEqual(result["adjacent_hash_links_checked"], 2)
        self.assertEqual(result["scheduled_run_matches"], 1)
        self.assertEqual(result["manual_run_matches"], 1)
        self.assertEqual(result["local_day_zero_runs"], 1)
        self.assertEqual([x["kind"] for x in result["observations"]],
                         ["local_day_zero", "manual", "scheduled"])
        for field in ("production_eligible", "weekly_ai_writer_eligible",
                      "actions_export_independently_authenticated",
                      "all_scheduled_slots_exhaustively_audited",
                      "source_rights_approved", "editor_delivery_authorized"):
            self.assertFalse(result[field])

    def test_pinned_git_reader_never_changes_worktree(self):
        before = self.git("status", "--porcelain", "--untracked-files=all")
        self.load()
        self.assertEqual(before, self.git("status", "--porcelain",
                                           "--untracked-files=all"))

    def test_broken_adjacent_hash_link_refused(self):
        clock, ledgers, h = self.load()
        ledgers[2]["state_sha256_before"] = "0" * 64
        with self.assertRaisesRegex(audit.ProvenanceError, "broken adjacent"):
            audit.assess(clock, ledgers, h, audit.parse_actions_export(
                {"total_count": 2, "workflow_runs": self.actions}))

    def test_db_byte_digest_mismatch_refused(self):
        clock, ledgers, h = self.load()
        with self.assertRaisesRegex(audit.ProvenanceError, "SQLite bytes"):
            audit.assess(clock, ledgers, "0" * 64, audit.parse_actions_export(
                {"total_count": 2, "workflow_runs": self.actions}))
        self.assertEqual(h, self.b2)

    def test_mutating_worktree_does_not_change_pinned_commit(self):
        (self.repo / "state" / "shadow.db").write_bytes(b"tampered working copy")
        self.assertEqual(self.load()[2], self.b2)

    def test_modified_branch_does_not_change_historical_commit(self):
        (self.repo / "state" / "shadow.db").write_bytes(b"new branch head")
        self.git("add", "state")
        self.git("commit", "-qm", "new data")
        self.git("branch", "-f", audit.STATE_BRANCH, "HEAD")
        self.assertEqual(self.load()[2], self.b2)

    def test_unreachable_or_missing_pinned_commit_refused(self):
        with self.assertRaises(audit.ProvenanceError):
            audit.pinned_state(self.repo, "f" * 40)
        self.git("branch", "-D", audit.STATE_BRANCH)
        with self.assertRaises(audit.ProvenanceError):
            audit.pinned_state(self.repo, self.commit)

    def test_action_mismatches_fail_closed(self):
        mutations = [
            ({"event": "schedule"}, "manual run"),
            ({"head_sha": "d" * 40}, "collector branch/commit"),
            ({"run_attempt": 2}, "attempt mismatch"),
            ({"workflow_id": 101}, "workflow identity"),
            ({"conclusion": "failure"}, "did not complete"),
            ({"status": "in_progress"}, "did not complete"),
            ({"head_branch": audit.STATE_BRANCH}, "collector branch/commit"),
        ]
        for mutation, reason in mutations:
            with self.subTest(mutation=mutation):
                self.actions[0].update(mutation)
                with self.assertRaisesRegex(audit.ProvenanceError, reason):
                    self.report()
                self.actions[0] = {
                    "id": 37533271730, "run_attempt": 1,
                    "workflow_id": audit.WORKFLOW_ID,
                    "name": audit.WORKFLOW_NAME, "event": "workflow_dispatch",
                    "status": "completed", "conclusion": "success",
                    "head_branch": "main", "head_sha": "b" * 40,
                    "created_at": "2026-10-06T21:21:00Z",
                }

    def test_schedule_wrong_logical_date_refused(self):
        self.actions[1]["created_at"] = "2026-10-08T21:58:00Z"
        with self.assertRaisesRegex(audit.ProvenanceError, "logical target date"):
            self.report()

    def test_missing_action_run_is_not_silent_success(self):
        self.actions.pop()
        with self.assertRaisesRegex(audit.ProvenanceError, "missing"):
            self.report()

    def test_duplicate_or_incomplete_actions_export_refused(self):
        base = copy.deepcopy(self.actions)
        for sample in [
            [{"total_count": 2, "workflow_runs": [base[0]]}],
            [{"total_count": 2, "workflow_runs": [base[0]]},
             {"total_count": 3, "workflow_runs": [base[1]]}],
            [{"total_count": 2, "workflow_runs": [base[0]]},
             {"total_count": 2, "workflow_runs": [base[0]]}],
        ]:
            with self.subTest(sample=sample), \
                    self.assertRaises(audit.ProvenanceError):
                audit.parse_actions_export(sample)

    def test_ledger_reuse_rights_and_publication_never_inferred(self):
        result = self.report()
        self.assertNotIn("approved", result["verdict"])
        self.assertFalse(result["human_reviews_approved"])
        self.assertEqual(0, result["writes"])


if __name__ == "__main__":
    unittest.main()
