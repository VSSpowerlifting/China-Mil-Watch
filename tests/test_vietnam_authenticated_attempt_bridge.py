"""No-network authenticity and gap tests for Phase 0B Actions metadata bridge."""
from __future__ import annotations

import base64
import copy
import io
import json
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from scripts.attest_vietnam_run_state import PREFIX, sha_blob
from scripts.audit_shadow_workflow_bindings import validate as source_bindings
from scripts.bridge_vietnam_actions_reconciliation import (
    AttestationHold, OUTPUT_SCHEMA, WORKFLOW, bridge, main,
)
from scripts.vietnam_ministry_attempt_reconciliation import (
    DAY_ZERO_COLLECTOR_COMMIT, DAY_ZERO_SOURCE_TARGETS, SOURCES,
)

THROUGH = "2026-10-10"
START = "2026-10-07"
RUNS = (
    (37656171920, 2, "workflow_dispatch", START, "2026-10-07T17:16:10Z"),
    (37700200951, 1, "schedule", START, "2026-10-07T23:05:45Z"),
    (37858935683, 1, "schedule", "2026-10-08", "2026-10-08T23:20:17Z"),
    (38000282894, 1, "schedule", "2026-10-09", "2026-10-09T22:38:51Z"),
    (38088742605, 1, "schedule", THROUGH, "2026-10-10T21:43:57Z"),
)
NAMES = (
    "20261007T171633+0000-37656171920-2.json",
    "20261007T230607+0000-37700200951-1.json",
    "20261008T232202+0000-37858935683-1.json",
    "20261009T223915+0000-38000282894-1.json",
    "20261010T214458+0000-38088742605-1.json",
)


def blob(obj):
    data = json.dumps(obj, sort_keys=True).encode("utf-8")
    return {"encoding": "base64",
            "content": base64.b64encode(data).decode("ascii"),
            "sha": sha_blob(data)}


def rebuild_blob(blob_envelope, mutator):
    record = json.loads(base64.b64decode(blob_envelope["content"]))
    mutator(record)
    return blob(record)


class FakeRest:
    def __init__(self, *, moit_anomaly=True):
        self.declarations = source_bindings()
        self.routes = {}
        self.calls = []
        self.ref_count = {}
        listing = []
        for run_id, final_attempt, event, day, started in RUNS:
            listing.append({"id": run_id, "run_attempt": final_attempt, "path": WORKFLOW})
            for attempt in range(1, final_attempt + 1):
                self.routes[PREFIX + "/actions/runs/{}/attempts/{}".format(run_id, attempt)] = {
                    "id": run_id, "run_attempt": attempt, "path": WORKFLOW,
                    "event": event, "status": "completed",
                    "conclusion": "failure" if run_id == 37656171920 and attempt == 1
                                  else "success",
                    "run_started_at": started,
                    "head_sha": "b" * 40,
                }
        self.index_key = (PREFIX + "/actions/workflows/vietnam_ministry_shadow.yml/runs"
                          "?created=2026-10-07..2026-10-10&per_page=30&page=1")
        self.routes[self.index_key] = {
            "total_count": len(listing), "workflow_runs": listing}
        self.ledger_paths = {}
        for i, (slug, state_branch) in enumerate(sorted(SOURCES.items())):
            state_sha = "{:040x}".format(i + 1)
            self.routes[PREFIX + "/git/ref/heads/" + state_branch] = {
                "ref": "refs/heads/" + state_branch,
                "object": {"sha": state_sha}}
            self.routes[PREFIX + "/contents/state/ledger?ref=" + state_sha] = [
                {"name": name} for name in NAMES
            ]
            clock = {"day_zero_run_id": "37656171920-2",
                     "day_zero_utc": "2026-10-07T17:16:33+00:00"}
            self.routes[PREFIX + "/contents/state/clock.json?ref=" + state_sha] = blob(clock)
            self.ledger_paths[slug] = []
            for index, name in enumerate(NAMES):
                run_id, attempt, event, day, started = RUNS[index]
                key = PREFIX + "/contents/state/ledger/" + name + "?ref=" + state_sha
                ledger = {
                    "source_slug": slug, "desk_id": "vietnam",
                    "run_id": "{}-{}".format(run_id, 2 if index == 0 else 1),
                    "target_date": DAY_ZERO_SOURCE_TARGETS[slug] if index == 0 else day,
                    "target_date_source": "explicit" if index == 0 else "schedule-slot",
                    "health": "ok", "result": "ok" if slug == "vn_mps_foreign_affairs_vi"
                              else "ok_no_publications",
                    "collector_commit": DAY_ZERO_COLLECTOR_COMMIT if index == 0
                                        else "a" * 40,
                    "finished_utc": started.replace("Z", "+00:00"),
                    "day_zero_utc": clock["day_zero_utc"],
                    "anomalies": [],
                    "source_anomalies": (["robots_content_type: text/html"]
                                         if moit_anomaly and
                                         slug.startswith("vn_moit") and index == 4 else []),
                }
                self.routes[key] = blob(ledger)
                self.ledger_paths[slug].append(key)

    def get(self, path):
        self.calls.append(path)
        if path not in self.routes:
            raise AssertionError("unexpected / unapproved GitHub API URL: " + path)
        return copy.deepcopy(self.routes[path])


class VietnamAttemptBridgeTests(unittest.TestCase):
    def test_real_binding_declarations_and_all_attempts_are_reconciled(self):
        api = FakeRest()
        report = bridge(api, through=THROUGH, binding_report=api.declarations)
        self.assertEqual(report["schema"], OUTPUT_SCHEMA)
        self.assertEqual(report["github"]["listed_workflow_runs"], 5)
        self.assertEqual(report["github"]["observed_actions_attempts"], 6)
        self.assertEqual(report["status"], "needs_review")
        rec = report["reconciler"]
        self.assertEqual(rec["github_attempts_supplied"], 6)
        self.assertEqual(rec["per_source_ledger_counts"],
                         {slug: 5 for slug in SOURCES})
        self.assertIn("non_successful_workflow_attempt",
                      [x["kind"] for x in rec["warnings"]])
        self.assertFalse(rec["github_attempt_inventory_independently_proven_exhaustive"])
        self.assertFalse(rec["day_7_human_signoff_complete"])
        self.assertFalse(report["source_use_rights_approved"])
        self.assertFalse(report["production_or_publication_authorized"])
        self.assertEqual(sum(report["source_anomaly_counts"].values()), 2)
        self.assertNotIn("captured_original_text", str(report))
        self.assertNotIn("url_to_article", str(report))

    def test_clean_recent_source_cannot_erase_failed_day_zero_attempt(self):
        api = FakeRest(moit_anomaly=False)
        out = bridge(api, through=THROUGH, binding_report=api.declarations)
        self.assertEqual(out["status"], "needs_review")
        self.assertTrue(any(w["kind"] == "non_successful_workflow_attempt"
                            for w in out["reconciler"]["warnings"]))

    def test_partial_source_push_is_explicitly_reported(self):
        api = FakeRest()
        slug = "vn_moit_energy_vi"
        latest = api.ledger_paths[slug][-1]
        sha = api.routes[latest]
        del api.routes[latest]
        state_sha = next(x["object"]["sha"] for x in api.routes.values()
                         if isinstance(x, dict) and x.get("ref") ==
                         "refs/heads/" + SOURCES[slug])
        directory = PREFIX + "/contents/state/ledger?ref=" + state_sha
        api.routes[directory]["__dummy"] = 1 if isinstance(api.routes[directory], dict) else None
        # Remove from pinned listing instead of asking a missing GitHub blob.
        if isinstance(api.routes[directory], list):
            api.routes[directory] = api.routes[directory][:-1]
        result = bridge(api, through=THROUGH, binding_report=api.declarations)
        kinds = [w["kind"] for w in result["reconciler"]["warnings"]]
        self.assertIn("successful_workflow_missing_source_ledger", kinds)
        self.assertIn("source_latest_committed_attempts_diverge", kinds)

    def test_mutated_run_or_ledger_is_refused(self):
        for case in ("run_wrong_workflow", "day_zero_forged", "wrong_slug",
                     "digest_bad", "index_incomplete", "future_source"):
            api = FakeRest()
            if case == "run_wrong_workflow":
                api.routes[PREFIX + "/actions/runs/38088742605/attempts/1"]["path"] = "bad.yml"
            elif case == "day_zero_forged":
                api.routes[api.ledger_paths["vn_mps_foreign_affairs_vi"][0]] = rebuild_blob(
                    api.routes[api.ledger_paths["vn_mps_foreign_affairs_vi"][0]],
                    lambda x: x.__setitem__("target_date", "2026-10-07"))
            elif case == "wrong_slug":
                key = api.ledger_paths["vn_moit_energy_vi"][1]
                api.routes[key] = rebuild_blob(api.routes[key],
                    lambda x: x.__setitem__("source_slug", "vn_mps_foreign_affairs_vi"))
            elif case == "digest_bad":
                api.routes[api.ledger_paths["vn_moit_foundational_industry_vi"][1]]["sha"] = "0" * 40
            elif case == "index_incomplete":
                api.routes[api.index_key]["total_count"] = 30
            elif case == "future_source":
                key = api.ledger_paths["vn_mps_foreign_affairs_vi"][4]
                api.routes[key] = rebuild_blob(api.routes[key],
                    lambda x: x.__setitem__("target_date", "2026-10-12"))
            with self.subTest(case=case), self.assertRaises(AttestationHold):
                bridge(api, through=THROUGH, binding_report=api.declarations)

    def test_cli_no_get_without_flag_or_token(self):
        with redirect_stderr(io.StringIO()), patch("scripts.bridge_vietnam_actions_reconciliation.GithubRead") as net:
            with self.assertRaises(SystemExit):
                main(["--through", THROUGH])
            with patch.dict("os.environ", {}, clear=True), self.assertRaises(SystemExit):
                main(["--through", THROUGH, "--approve-github-read"])
            net.assert_not_called()

    def test_future_and_wrong_declaration_fail_closed(self):
        api = FakeRest()
        with self.assertRaises(AttestationHold):
            bridge(api, through="2040-01-01", binding_report=api.declarations)
        d = copy.deepcopy(api.declarations)
        d["sources"] = [x for x in d["sources"]
                        if x["source_slug"] != "vn_mps_foreign_affairs_vi"]
        with self.assertRaises(AttestationHold):
            bridge(api, through=THROUGH, binding_report=d)


if __name__ == "__main__":
    unittest.main()
