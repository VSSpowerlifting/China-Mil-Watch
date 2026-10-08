"""Synthetic end-to-end receipt join: #184 packet verifier -> #188 audit."""
import hashlib
import json
import unittest

from scripts.review_vietnam_ministry_state import package_sha256
from scripts.vietnam_ministry_checkpoint_attempt_join import (
    RECEIPT_SCHEMA, PacketJoinRefused, join,
)
from scripts.vietnam_ministry_attempt_reconciliation import (
    AttemptEvidenceRefused, DAY_ZERO_COLLECTOR_COMMIT, DAY_ZERO_SOURCE_TARGETS,
)
from tests.test_vietnam_ministry_checkpoint_rollup import (
    ThreeMinistryRollupTests,
)
from core.collection.vietnam_sources import SOURCES


def doc(obj):
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def attempts():
    return {"schema": RECEIPT_SCHEMA, "github_attempts": [
        {
            "run_id": 37656171920,
            "run_attempt": 2,
            "event": "workflow_dispatch",
            "conclusion": "success",
            "run_url": "https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37656171920",
            "target_date": None,
            "target_date_basis": None,
        },
        {
            "run_id": 37700200951,
            "run_attempt": 1,
            "event": "schedule",
            "conclusion": "success",
            "run_url": "https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37700200951",
            "target_date": "2026-10-07",
            "target_date_basis": "verified_schedule_slot",
        },
    ]}


def ledgers(source):
    baseline = {
        "run_id": "37656171920-2",
        "result": "ok",
        "health": "ok",
        "target_date": DAY_ZERO_SOURCE_TARGETS[source],
        "target_date_source": "explicit",
        "collector_commit": DAY_ZERO_COLLECTOR_COMMIT,
        "finished_utc": {
            "vn_mps_foreign_affairs_vi": "2026-10-07T17:16:33+00:00",
            "vn_moit_energy_vi": "2026-10-07T17:16:44+00:00",
            "vn_moit_foundational_industry_vi": "2026-10-07T17:16:53+00:00",
        }[source],
        "source_slug": source, "desk_id": "vietnam",
    }
    subsequent = {
        "run_id": "37700200951-1",
        "result": "ok" if source == "vn_mps_foreign_affairs_vi" else "ok_no_publications",
        "health": "ok",
        "target_date": "2026-10-07",
        "target_date_source": "schedule-slot",
        "collector_commit": "e9db628650b281786458d16d79db74fe0f664fe7",
        "finished_utc": {
            "vn_mps_foreign_affairs_vi": "2026-10-07T23:06:07+00:00",
            "vn_moit_energy_vi": "2026-10-07T23:06:12+00:00",
            "vn_moit_foundational_industry_vi": "2026-10-07T23:06:18+00:00",
        }[source],
        "source_slug": source, "desk_id": "vietnam",
    }
    return [baseline, subsequent]


def rewrite_packet(folder, *, rows=None, edits=None):
    manifest_path = folder / "review_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if rows is not None:
        (folder / "run_inventory.jsonl").write_text(
            "".join(json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n" for item in rows), encoding="utf-8")
    if edits:
        manifest.update(edits)
    files = ("record_inventory.jsonl", "run_inventory.jsonl", "corpus_evidence.json",
             "signoff_template.json", "review_report.md")
    texts = {file: (folder / file).read_text(encoding="utf-8") for file in files}
    manifest.pop("deterministic_sha256", None)
    manifest.pop("artifact_sha256", None)
    manifest["deterministic_sha256"] = package_sha256(
        manifest, {name: texts[name] for name in (
            "record_inventory.jsonl", "run_inventory.jsonl", "corpus_evidence.json")})
    manifest["artifact_sha256"] = {
        name: hashlib.sha256(text.encode("utf-8")).hexdigest()
        for name, text in texts.items()
    }
    manifest_path.write_text(doc(manifest), encoding="utf-8")


class MinistryPacketAttemptJoinTests(unittest.TestCase):
    def setUp(self):
        self.base = ThreeMinistryRollupTests(
            "test_three_source_packets_cohere_without_implying_signoff")
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.packets = []
        for i, source in enumerate(sorted(SOURCES)):
            folder = self.base.packet(source, i)
            rewrite_packet(folder, rows=ledgers(source),
                           edits={
                               "latest_run_id": "37700200951-1",
                               "latest_collector_commit":
                                   "e9db628650b281786458d16d79db74fe0f664fe7",
                           })
            self.packets.append(folder)

    def test_actual_two_run_bootstrap_shape_roundtrips(self):
        output = join(self.packets, attempts())
        self.assertEqual(output["schema"], "ipr-vn-ministry-packet-attempt-join/1")
        self.assertEqual(output["attempt_reconciliation"]["warnings"],
                         [{"kind": "expected_day_without_fully_evidenced_three_source_attempt",
                           "target_date": "2026-10-08"},
                          *[{"kind": "expected_day_without_fully_evidenced_three_source_attempt",
                             "target_date": "2026-10-%02d" % day} for day in range(9, 15)]])
        self.assertTrue(output["three_source_rollup"]["all_three_machine_checkpoints_reached"])
        self.assertEqual(output["attempt_reconciliation"]["github_attempts_supplied"], 2)
        self.assertTrue(all(x["runs_extracted"] == 2
                            for x in output["source_packet_anchors"].values()))
        self.assertFalse(output["human_checkpoint_signed"])
        self.assertFalse(output["desk_qualified"])
        self.assertFalse(output["production_publication_authorized"])
        self.assertFalse(output["actions_history_exhaustive"])

    def test_packet_input_order_does_not_change_result(self):
        a = join(self.packets, attempts())
        b = join(list(reversed(self.packets)), attempts())
        self.assertEqual(a, b)

    def test_tampered_run_inventory_denied_by_sha256(self):
        p = self.packets[0] / "run_inventory.jsonl"
        p.write_text('{"run_id":"completely-forged"}\n')
        with self.assertRaisesRegex(ValueError, "artifact digest mismatch"):
            join(self.packets, attempts())

    def test_rehashed_foreign_source_ledger_refused(self):
        folder = self.packets[0]
        original = json.loads((folder / "run_inventory.jsonl").read_text().splitlines()[0])
        original["source_slug"] = "vn_impossible_source"
        following = json.loads((folder / "run_inventory.jsonl").read_text().splitlines()[1])
        rewrite_packet(folder, rows=[original, following])
        with self.assertRaisesRegex(PacketJoinRefused, "does not belong"):
            join(self.packets, attempts())

    def test_rehashed_duplicate_ledger_refused(self):
        folder = self.packets[0]
        source = sorted(SOURCES)[0]
        rows = ledgers(source)
        rows.append(dict(rows[-1]))
        rewrite_packet(folder, rows=rows)
        with self.assertRaisesRegex(PacketJoinRefused, "duplicate"):
            join(self.packets, attempts())

    def test_lies_about_latest_source_run_refused(self):
        folder = self.packets[0]
        rewrite_packet(folder, edits={"latest_run_id": "123456789-1"})
        with self.assertRaisesRegex(PacketJoinRefused, "latest run differs"):
            join(self.packets, attempts())

    def test_incomplete_machine_checkpoint_refused(self):
        folder = self.packets[0]
        rewrite_packet(folder, edits={"latest_shadow_day": 6,
                                       "checkpoint_reached": False})
        with self.assertRaisesRegex(PacketJoinRefused, "prematurely"):
            join(self.packets, attempts())

    def test_missing_actions_attempts_cannot_be_hidden(self):
        receipt = attempts()
        receipt["github_attempts"] = []
        result = join(self.packets, receipt)
        warnings = result["attempt_reconciliation"]["warnings"]
        self.assertTrue(any(x["kind"] == "source_ledger_missing_actions_receipt"
                            for x in warnings))
        self.assertFalse(result["actions_history_exhaustive"])

    def test_bad_or_duplicate_action_receipts_refused(self):
        receipt = attempts()
        receipt["github_attempts"].append(dict(receipt["github_attempts"][-1]))
        with self.assertRaisesRegex(AttemptEvidenceRefused, "duplicate GitHub"):
            join(self.packets, receipt)
        with self.assertRaisesRegex(PacketJoinRefused, "explicitly verified input schema"):
            join(self.packets, {"github_attempts": []})

    def test_original_prose_never_passes_through_metadata_report(self):
        folder = self.packets[0]
        source = sorted(SOURCES)[0]
        rows = ledgers(source)
        rows[-1]["publisher_full_article_text"] = "PROHIBITED_PUBLISHER_TEXT_EXAMPLE"
        rewrite_packet(folder, rows=rows)
        output = json.dumps(join(self.packets, attempts()), sort_keys=True)
        self.assertNotIn("PROHIBITED_PUBLISHER_TEXT_EXAMPLE", output)
        self.assertNotIn("publisher_full_article_text", output)
        self.assertFalse(json.loads(output)["source_original_text_in_report"])

    def test_refuses_signed_or_symlinked_local_packets(self):
        (self.packets[1] / "signoff.json").write_text('{"reviewer":"synthetic"}')
        with self.assertRaisesRegex(ValueError, "signoff is separately"):
            join(self.packets, attempts())

    def test_no_network_git_database_write_or_clock_in_join_module(self):
        import inspect
        from scripts import vietnam_ministry_checkpoint_attempt_join as module
        code = inspect.getsource(module)
        for forbidden in ("requests.", "urlopen(", "subprocess.", "sqlite3",
                          "write_text(", "open(", "datetime.now(", "time.time("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
