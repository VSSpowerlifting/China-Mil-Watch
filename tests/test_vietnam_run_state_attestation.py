"""No-network Phase-0 source-specific Github Action/ledger attestation contracts."""
import base64
import copy
import io
import json
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from unittest.mock import patch

from scripts.audit_shadow_workflow_bindings import validate as binding_audit
from scripts.attest_vietnam_run_state import (
    AttestationHold, PREFIX, SOURCES, GithubRead, main, observe, sha_blob,
)

HEAD = "a" * 40
OTHER_HEAD = "b" * 40
RUN = "38088742605-1"
LEDGER_NAME = "20261010T214458+0000-38088742605-1.json"
STARTED = "2026-10-10T21:44:00Z"


def blob(payload, tampered=False):
    data = json.dumps(payload, sort_keys=True).encode("utf-8")
    return {"encoding": "base64",
            "content": base64.b64encode(data).decode(),
            "sha": "0" * 40 if tampered else sha_blob(data)}


def fixture_maps(*, moit_anomaly=True):
    bindings = binding_audit()
    mapped = {x["source_slug"]: x for x in bindings["sources"]}
    reply = {}
    run = {
        "id": 38088742605, "run_attempt": 1, "status": "completed",
        "conclusion": "success", "event": "schedule",
        "head_sha": OTHER_HEAD, "run_started_at": STARTED,
        "path": ".github/workflows/vietnam_ministry_shadow.yml",
    }
    reply[PREFIX + "/actions/runs/38088742605/attempts/1"] = run
    for src in SOURCES:
        binding = mapped[src]
        branch = binding["state_branch"]
        reply[PREFIX + "/git/ref/heads/" + branch] = {
            "ref": "refs/heads/" + branch, "object": {"sha": HEAD}}
        reply[PREFIX + "/contents/state/ledger?ref=" + HEAD] = [
            {"name": LEDGER_NAME},
        ]
        # Fake transport has to be source-aware when 3 source branches share a
        # path and ref in real GitHub; each family gets its OWN immutable head.
    return bindings, mapped, run


class FakeGitHub:
    def __init__(self, *, moit_anomaly=True):
        self.bindings = binding_audit()
        self.routes = {}
        self.calls = []
        self.source_by_branch = {}
        for idx, src in enumerate(SOURCES):
            binding = next(x for x in self.bindings["sources"]
                           if x["source_slug"] == src)
            branch = binding["state_branch"]
            sha = format(idx + 1, "040x")
            self.source_by_branch[branch] = sha
            clock = {
                "day_zero_run_id": "37656171920-2",
                "day_zero_utc": "2026-10-07T17:16:33+00:00",
            }
            anomaly = (src.startswith("vn_moit") and moit_anomaly)
            ledger = {
                "desk_id": "vietnam", "source_slug": src,
                "target_date": "2026-10-10", "target_date_source": "schedule-slot",
                "run_id": RUN, "health": "ok",
                "result": "ok_no_publications" if anomaly else "ok",
                "day_zero_utc": clock["day_zero_utc"],
                "new_records": 0 if anomaly else 1,
                "anomalies": [],
                "source_anomalies": ["robots_content_type: text/html"] if anomaly else [],
            }
            self.routes[PREFIX + "/git/ref/heads/" + branch] = {
                "ref": "refs/heads/" + branch, "object": {"sha": sha}}
            self.routes[PREFIX + "/contents/state/ledger?ref=" + sha] = [
                {"name": LEDGER_NAME}]
            self.routes[PREFIX + "/contents/state/ledger/" + LEDGER_NAME +
                        "?ref=" + sha] = blob(ledger)
            self.routes[PREFIX + "/contents/state/clock.json?ref=" + sha] = blob(clock)
        self.routes[PREFIX + "/actions/runs/38088742605/attempts/1"] = {
            "id": 38088742605,
            "run_attempt": 1, "status": "completed", "conclusion": "success",
            "event": "schedule", "head_sha": OTHER_HEAD,
            "run_started_at": STARTED,
            "path": ".github/workflows/vietnam_ministry_shadow.yml",
        }

    def get(self, path):
        self.calls.append(path)
        if path not in self.routes:
            raise AssertionError("unexpected or non-allowlisted API request: " + path)
        return copy.deepcopy(self.routes[path])


class LiveRunAttestationTests(unittest.TestCase):
    def test_actual_16_source_binding_audit_selects_only_three_vietnam(self):
        b = binding_audit()
        self.assertEqual(b["schema"], "ipr-shadow-source-workflow-bindings/1")
        self.assertEqual(b["source_families_checked"], 16)
        selected = [x for x in b["sources"] if x["source_slug"] in SOURCES]
        self.assertEqual(len(selected), 3)
        self.assertTrue(all(x["trigger"] == "scheduled" for x in selected))
        self.assertTrue(all(x["cron"] == "17 18 * * *" for x in selected))

    def test_three_pinned_sources_and_green_run_are_not_desk_qualification(self):
        api = FakeGitHub()
        report = observe(api, as_of="2026-10-10", binding_report=api.bindings)
        self.assertEqual(report["source_families_observed"], 3)
        self.assertTrue(report["shared_run_attempt_and_day"])
        self.assertEqual(report["cohort_state"], "needs_review")
        self.assertEqual(report["source_origin"], "live_github_rest_read_only")
        self.assertEqual([x["observation_state"] for x in report["sources"]],
                         ["verified_run_and_state_observation", "needs_review",
                          "needs_review"])
        self.assertEqual(len(api.calls), 3 * 5 + 1)
        self.assertEqual(len(set(api.calls)), 3 * 4 + 1)
        self.assertTrue(all(x["state_head_sha"] in api.source_by_branch.values()
                            for x in report["sources"]))
        for s in report["sources"]:
            self.assertFalse(s["source_rights_verified"])
            self.assertFalse(s["eligible_for_production"])
            self.assertFalse(s["eligible_for_publication"])
            self.assertFalse(s["all_actions_attempts_audited"])
            self.assertFalse(s["state_hash_chain_fully_audited"])
        self.assertFalse(report["full_30_day_continuity_verified"])
        self.assertFalse(report["human_source_review_verified"])

    def test_optional_clean_moit_still_does_not_promote(self):
        api = FakeGitHub(moit_anomaly=False)
        report = observe(api, as_of="2026-10-10", binding_report=api.bindings)
        self.assertEqual(report["cohort_state"], "consistent_recent_observations_only")
        self.assertFalse(report["public_collection_or_desk_promotion_authorized"])

    def test_mutated_action_ledger_and_blob_are_all_refused(self):
        def mutate_source(api, index, f):
            src = SOURCES[index]
            branch = next(x["state_branch"] for x in api.bindings["sources"]
                          if x["source_slug"] == src)
            sha = api.source_by_branch[branch]
            key = PREFIX + "/contents/state/ledger/" + LEDGER_NAME + "?ref=" + sha
            val = json.loads(base64.b64decode(api.routes[key]["content"]))
            f(val)
            api.routes[key] = blob(val)

        for label, method in [
            ("wrong issuer", lambda a: mutate_source(a, 0,
              lambda x: x.__setitem__("source_slug", "jp_jcg_press_en"))),
            ("wrong day", lambda a: mutate_source(a, 0,
              lambda x: x.__setitem__("target_date", "2026-10-09"))),
            ("wrong date provenance", lambda a: mutate_source(a, 0,
              lambda x: x.__setitem__("target_date_source", "explicit"))),
            ("unsuccessful run", lambda a: a.routes[
              PREFIX + "/actions/runs/38088742605/attempts/1"].update(conclusion="failure")),
            ("wrong workflow", lambda a: a.routes[
              PREFIX + "/actions/runs/38088742605/attempts/1"].update(path=".github/workflows/japan_shadow.yml")),
            ("wrong attempt", lambda a: a.routes[
              PREFIX + "/actions/runs/38088742605/attempts/1"].update(run_attempt=2)),
            ("missing UTC", lambda a: a.routes[
              PREFIX + "/actions/runs/38088742605/attempts/1"].update(run_started_at="2026-10-10")),
            ("missing source clock", lambda a: mutate_source(a, 0,
              lambda x: x.__setitem__("day_zero_utc", "2026-10-06T00:00:00+00:00"))),
        ]:
            api = FakeGitHub()
            method(api)
            with self.subTest(case=label), self.assertRaises(AttestationHold):
                observe(api, as_of="2026-10-10", binding_report=api.bindings)

    def test_github_blob_tamper_untrusted_head_and_branch_race_are_refused(self):
        api = FakeGitHub()
        branch = next(x["state_branch"] for x in api.bindings["sources"]
                      if x["source_slug"] == SOURCES[0])
        head = api.source_by_branch[branch]
        path = PREFIX + "/contents/state/clock.json?ref=" + head
        api.routes[path]["sha"] = "0" * 40
        with self.assertRaisesRegex(AttestationHold, "blob SHA"):
            observe(api, as_of="2026-10-10", binding_report=api.bindings)

        class MovingGitHub(FakeGitHub):
            def get(self, path):
                val = super().get(path)
                if path == PREFIX + "/git/ref/heads/" + branch:
                    count = self.calls.count(path)
                    if count == 2:
                        val["object"]["sha"] = OTHER_HEAD
                return val
        with self.assertRaisesRegex(AttestationHold, "moved"):
            observe(MovingGitHub(), as_of="2026-10-10",
                    binding_report=api.bindings)

    def test_fake_future_day_and_untrusted_binding_are_refused(self):
        api = FakeGitHub()
        with self.assertRaisesRegex(AttestationHold, "future"):
            observe(api, as_of="2030-01-01", binding_report=api.bindings)
        invalid = copy.deepcopy(api.bindings)
        invalid["declaration_only"] = False
        with self.assertRaisesRegex(AttestationHold, "binding audit"):
            observe(api, as_of="2026-10-10", binding_report=invalid)

    def test_cli_never_connects_without_explicit_approval(self):
        with redirect_stderr(io.StringIO()), patch.object(GithubRead, "get") as getter:
            with self.assertRaises(SystemExit) as ex:
                main(["--as-of", "2026-10-10"])
        self.assertEqual(ex.exception.code, 2)
        getter.assert_not_called()


if __name__ == "__main__":
    unittest.main()
