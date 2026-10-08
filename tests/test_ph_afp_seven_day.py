"""Synthetic offline AFP seven-day evidence audit contracts.

All simulated ledgers and 'human review counts' are test fixtures; no source
was fetched, no reviewer acted, and no desk approval is represented.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import audit_ph_afp_seven_day as audit  # noqa: E402


def make_db():
    with tempfile.TemporaryDirectory() as temp:
        p = Path(temp) / "shadow.db"
        with sqlite3.connect(p) as cx:
            cx.executescript("""
                CREATE TABLE shadow_records (
                    source_identity TEXT, content_sha256 TEXT,
                    text_original TEXT, text_status TEXT, capture_sha256 TEXT
                );
                CREATE TABLE captures (
                    source_identity TEXT, payload BLOB, payload_sha256 TEXT
                );
                CREATE TABLE revisions (revision_id INTEGER);
            """)
            payload = b'{"id":123, "title":"SYNTHETIC"}'
            text = "SYNTHETIC NOT A SOURCE"
            cx.execute("INSERT INTO shadow_records VALUES (?,?,?,?,?)",
                       ("afp:123", audit.digest(text.encode()), text, "text",
                        audit.digest(payload)))
            cx.execute("INSERT INTO captures VALUES (?,?,?)",
                       ("afp:123", payload, audit.digest(payload)))
        return p.read_bytes()


class FakeState:
    def __init__(self, seven=True):
        self.commit = "c" * 40
        self.data = {}
        db = make_db()
        self.data["state/shadow.db"] = db
        self.data["state/clock.json"] = json.dumps({
            "day_zero_utc": "2026-10-07T13:51:44+00:00",
            "day_zero_run_id": "123450-1",
        }).encode()
        last = "2026-10-07"
        for i in range(7 if seven else 1):
            target = (date(2026, 10, 7) + timedelta(days=i)).isoformat()
            run = "12345%d-1" % i
            payload = ("SYNTHETIC REQUEST CAPTURE %d" % i).encode()
            digest = audit.digest(payload)
            self.data["state/evidence/payloads/" + digest + ".bin"] = payload
            receipts = [{"payload_retained": True,
                         "payload_sha256": digest}]
            evidence = json.dumps(receipts, sort_keys=True).encode()
            self.data["state/evidence/" + run + ".json"] = evidence
            ledger = {
                "run_id": run, "desk": "ph-afp", "rehearsal": False,
                "target_date": target, "target_date_source": "schedule-slot",
                "started_utc": target + "T13:50:40+00:00",
                "finished_utc": target + "T13:51:44+00:00",
                "day_zero_utc": "2026-10-07T13:51:44+00:00",
                "shadow_day": i, "health": "ok",
                "result": "ok" if i == 0 else "ok_no_publications",
                "robots_status": "allowed",
                "listing_status": "ok" if i == 0 else "ok_no_publications",
                "cap": 100, "lookback_days": 14,
                "selected": 1 if i == 0 else 0,
                "retrieved": 1 if i == 0 else 0,
                "inserted": 1 if i == 0 else 0,
                "duplicates": 0, "revisions": 0,
                "sample_limit": None, "sample_unselected": 0,
                "collector_commit": "a" * 40,
                "collector_identity": "IndoPacificRecord-ShadowCollector/0.1 (SYNTHETIC)",
                "fetch_failures": 0, "extraction_failures": 0,
                "access_failures": 0, "redirect_refusals": 0,
                "identity_collisions": 0, "failure_log": [],
                "aborted": None, "stored_total": 1,
                "state_sha256_before": None if i == 0 else audit.digest(db),
                "state_sha256_after": audit.digest(db),
                "observed": {"count_mismatch": False, "listing_end": "next_null",
                             "list_pages": 1, "listed_items": 1,
                             "api_reported_count": 1},
                "request_evidence": {
                    "path": "evidence/" + run + ".json",
                    "sha256": audit.digest(evidence), "requests": 1
                },
            }
            self.data["state/ledger/%d-%s.json" % (i, run)] = json.dumps(ledger).encode()
        self.files = set(self.data)

    def read(self, path, **kwargs):
        if path not in self.data:
            raise audit.AFPSevenDayError("missing pinned state file: " + path)
        return self.data[path]

    def read_json(self, path):
        return json.loads(self.read(path))

    def change_ledger(self, i, key, value):
        name = "state/ledger/%d-12345%d-1.json" % (i, i)
        row = json.loads(self.data[name])
        row[key] = value
        self.data[name] = json.dumps(row).encode()

    def get_ledger(self, i):
        name = "state/ledger/%d-12345%d-1.json" % (i, i)
        return json.loads(self.data[name])

    def replace_ledger(self, i, row):
        name = "state/ledger/%d-12345%d-1.json" % (i, i)
        self.data[name] = json.dumps(row).encode()


class LedgerReliability(unittest.TestCase):
    def setUp(self):
        self.state = FakeState()

    def test_seven_complete_ledgers_only_support_preliminary_gate(self):
        out = audit.assess(self.state, as_of="2026-10-13")
        self.assertTrue(out["all_seven_ledger_slots_supported"])
        self.assertEqual(out["successfully_supported_ledger_slots"], 7)
        self.assertEqual(out["required_human_review_records"], 1)
        self.assertFalse(out["github_actions_event_and_failure_artifacts_independently_verified"])
        self.assertFalse(out["human_review_completed_or_verified"])
        self.assertFalse(out["philippines_desk_qualified"])
        self.assertFalse(out["production_admission_authorized"])
        self.assertEqual(out["database"]["records"], 1)

    def test_first_two_days_due_remaining_days_not_assumed_failed(self):
        out = audit.assess(self.state, as_of="2026-10-08")
        self.assertEqual(out["successfully_supported_ledger_slots"], 2)
        self.assertEqual(
            [s["status"] for s in out["slots"][2:]],
            ["future_not_due"] * 5
        )
        self.assertFalse(out["all_seven_ledger_slots_supported"])

    def test_one_stored_ledger_does_not_mean_seven_day_clock(self):
        s = FakeState(seven=False)
        out = audit.assess(s, as_of="2026-10-13")
        self.assertEqual(out["successfully_supported_ledger_slots"], 1)
        self.assertEqual(out["slots"][1]["status"], "missing_scheduled_ledger")

    def test_missing_middle_scheduled_day_breaks_gate(self):
        name = "state/ledger/3-123453-1.json"
        self.state.files.remove(name)
        self.state.data.pop(name)
        out = audit.assess(self.state, as_of="2026-10-13")
        self.assertFalse(out["all_seven_ledger_slots_supported"])
        self.assertEqual(out["slots"][3]["status"], "missing_scheduled_ledger")

    def test_manual_and_rehearsal_ledger_never_count(self):
        self.state.change_ledger(2, "target_date_source", "explicit")
        out = audit.assess(self.state, as_of="2026-10-13")
        self.assertEqual(out["slots"][2]["status"], "missing_scheduled_ledger")
        self.state.change_ledger(2, "target_date_source", "schedule-slot")
        self.state.change_ledger(2, "rehearsal", True)
        out = audit.assess(self.state, as_of="2026-10-13")
        self.assertEqual(out["slots"][2]["status"], "invalid_ledger_evidence")
        self.assertIn("rehearsal_or_missing", out["slots"][2]["issues"])

    def test_duplicate_scheduled_slots_are_ambiguous(self):
        orig = self.state.get_ledger(3)
        dup = copy.deepcopy(orig)
        dup["run_id"] = "909090-2"
        dup["started_utc"] = "2026-10-10T14:50:40+00:00"
        dup["finished_utc"] = "2026-10-10T14:51:44+00:00"
        self.state.data["state/ledger/duplicate.json"] = json.dumps(dup).encode()
        self.state.files.add("state/ledger/duplicate.json")
        out = audit.assess(self.state, as_of="2026-10-13")
        self.assertEqual(out["slots"][3]["status"], "ambiguous_multiple_scheduled_ledgers")

    def test_source_robots_refusal_or_listing_truncation_block_day(self):
        for key, value, expected in (
            ("robots_status", "disallowed", "robots_not_allowed"),
            ("listing_status", "listing_failure", "listing_incomplete"),
            ("fetch_failures", 1, "nonzero_fetch_failures"),
            ("sample_unselected", 1, "sampling_or_truncation"),
        ):
            with self.subTest(key=key):
                state = FakeState()
                state.change_ledger(4, key, value)
                s = audit.assess(state, as_of="2026-10-13")["slots"][4]
                self.assertEqual(s["status"], "invalid_ledger_evidence")
                self.assertIn(expected, s["issues"])

    def test_quiet_window_is_eligible_but_not_human_review(self):
        out = audit.assess(self.state, as_of="2026-10-13")
        quiet = out["slots"][1]
        self.assertEqual(quiet["status"], "ledger_success_unverified_actions")
        self.assertEqual(quiet["inserted"], 0)
        self.assertEqual(quiet["required_human_reviews"], 0)

    def test_truncated_unreconciled_source_listing_fails(self):
        row = self.state.get_ledger(1)
        row["observed"]["listing_end"] = "next_unknown"
        self.state.replace_ledger(1, row)
        s = audit.assess(self.state, as_of="2026-10-13")["slots"][1]
        self.assertIn("listing_not_reconciled", s["issues"])

    def test_changed_original_receipt_refused(self):
        name = "state/evidence/123451-1.json"
        self.state.data[name] += b"\nMUTATED"
        s = audit.assess(self.state, as_of="2026-10-13")["slots"][1]
        self.assertEqual(s["status"], "invalid_ledger_evidence")
        self.assertIn("request_evidence_invalid", s["issues"][0])

    def test_missing_original_policy_or_listing_payload_refused(self):
        entry = self.state.get_ledger(1)
        receipts = json.loads(self.state.read("state/" + entry["request_evidence"]["path"]))
        payload = "state/evidence/payloads/" + receipts[0]["payload_sha256"] + ".bin"
        self.state.data[payload] = b"synthetic mutation"
        s = audit.assess(self.state, as_of="2026-10-13")["slots"][1]
        self.assertEqual(s["status"], "invalid_ledger_evidence")

    def test_modified_db_or_capture_digest_refused(self):
        self.state.data["state/shadow.db"] = b"not sqlite"
        with self.assertRaisesRegex(audit.AFPSevenDayError, "not SQLite"):
            audit.assess(self.state, as_of="2026-10-13")
        state = FakeState()
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "test.db"
            db.write_bytes(state.data["state/shadow.db"])
            with sqlite3.connect(db) as cx:
                cx.execute("UPDATE captures SET payload = ?", (b"broken",))
            state.data["state/shadow.db"] = db.read_bytes()
        with self.assertRaisesRegex(audit.AFPSevenDayError, "capture hash mismatch"):
            audit.audit_database(state.data["state/shadow.db"])

    def test_mutated_state_and_latest_ledger_mismatch_fail_closed(self):
        self.state.change_ledger(6, "stored_total", 2)
        with self.assertRaisesRegex(audit.AFPSevenDayError, "corpus total"):
            audit.assess(self.state, as_of="2026-10-13")
        state = FakeState()
        state.change_ledger(6, "state_sha256_after", "0"*64)
        with self.assertRaisesRegex(audit.AFPSevenDayError, "latest ledger state hash"):
            audit.assess(state, as_of="2026-10-13")

    def test_noncanonical_dates_and_clock_fail_closed(self):
        with self.assertRaises(audit.AFPSevenDayError):
            audit.assess(self.state, as_of="2026-10-14T00:00:00Z")
        with self.assertRaisesRegex(audit.AFPSevenDayError, "predates"):
            audit.assess(self.state, as_of="2026-10-06")
        self.state.data["state/clock.json"] = b'{"day_zero_utc": "2026-10-07T13:51:44+00:00", "day_zero_run_id":"faked"}'
        with self.assertRaisesRegex(audit.AFPSevenDayError, "Day-0 clock"):
            audit.assess(self.state, as_of="2026-10-13")

    def test_explicit_later_seven_day_window_can_be_requested(self):
        out = audit.assess(self.state, as_of="2026-10-14",
                           start="2026-10-08")
        self.assertEqual(out["window_start"], "2026-10-08")
        self.assertEqual(out["window_end"], "2026-10-14")
        self.assertEqual(out["slots"][-1]["status"], "missing_scheduled_ledger")
        self.assertFalse(out["all_seven_ledger_slots_supported"])

    def test_later_window_cannot_predate_day_zero(self):
        with self.assertRaisesRegex(audit.AFPSevenDayError, "predates"):
            audit.assess(self.state, as_of="2026-10-13",
                         start="2026-10-06")


class ImmutableGitSnapshot(unittest.TestCase):
    def test_refuses_moving_ref_and_missing_historical_object(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            with self.assertRaisesRegex(audit.AFPSevenDayError, "literal"):
                audit.FrozenState(repo, "shadow/ph-afp")
            with self.assertRaisesRegex(audit.AFPSevenDayError, "unavailable"):
                audit.FrozenState(repo, "f"*40)

    def test_reads_only_exact_commit_and_rejects_post_snapshot_updates(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            files = {
                "state/clock.json": b'{"day_zero_run_id":"synthetic"}',
                "state/shadow.db": b"SYNTHETIC NOT REAL SQLITE",
                "state/ledger/synthetic.json": b'{"run_id": "synthetic"}'
            }
            for p, b in files.items():
                f = repo / p
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(b)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run([
                "git", "-c", "user.name=SYNTHETIC",
                "-c", "user.email=synthetic@example.invalid",
                "commit", "-qm", "SYNTHETIC"
            ], cwd=repo, check=True)
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo).decode().strip()
            snapshot = audit.FrozenState(repo, sha)
            (repo / "state/clock.json").write_bytes(b"MUTATED WORKTREE")
            self.assertEqual(snapshot.read("state/clock.json"),
                             files["state/clock.json"])
            self.assertEqual(snapshot.read("state/ledger/synthetic.json"),
                             files["state/ledger/synthetic.json"])


if __name__ == "__main__":
    unittest.main()
