"""Synthetic files only: triplet checkpoint integrity, gaps and human hold."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from core.collection.vietnam_sources import SOURCES
from scripts.review_vietnam_ministry_state import package_sha256
from scripts.shadow_collect_vietnam_ministry import load_source
from scripts.vietnam_ministry_checkpoint_rollup import (
    ARTIFACT_FILES, RollupRefused, read_packet, rollup,
)
from scripts.review_vietnam_shadow_state import SIGNOFF_SCHEMA, QUEUE_ALGORITHM


def plain(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


class ThreeMinistryRollupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="synthetic-vietnam-ministry-rollup-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folders = []

    def packet(self, slug, index, *, checkpoint="day-07", as_of="2026-10-14",
               shadow_day=7, missing=None, uncovered=None, anomalies=None,
               signoff=False):
        folder = self.root / ("p%02d" % len(self.folders))
        folder.mkdir()
        payloads = {
            "record_inventory.jsonl": plain({"synthetic_id": index}),
            "run_inventory.jsonl": plain({"synthetic_attempt": index}),
            "corpus_evidence.json": plain({"synthetic_corpus": True}),
            "signoff_template.json": plain({"reviewer": None, "synthetic_only": True}),
            "review_report.md": "# Synthetic ministry packet. No original source texts.\n",
        }
        hashes = {}
        for name, data in payloads.items():
            raw = data.encode("utf-8")
            hashes[name] = hashlib.sha256(raw).hexdigest()
            (folder / name).write_bytes(raw)
        manifest = {
            "tool": "scripts/review_vietnam_ministry_state.py",
            "tool_version": "2.0.0",
            "signoff_schema": SIGNOFF_SCHEMA,
            "queue_algorithm": QUEUE_ALGORITHM,
            "desk": "vietnam",
            "source_slug": slug,
            "family": "synthetic only",
            "publisher": "synthetic only",
            "language": "vi",
            "state_branch": load_source(slug).state_branch,
            "state_commit": ("%040x" % (index + 100)),
            "state_tree": ("%040x" % (index + 200)),
            "state_ref": "refs/heads/" + load_source(slug).state_branch,
            "provenance": "git-verified-tree/1",
            "formal": True,
            "checkpoint": checkpoint,
            "as_of": as_of,
            "checkpoint_reached": shadow_day >= {"day-07": 7, "day-14": 14, "day-30": 30}[checkpoint],
            "latest_shadow_day": shadow_day,
            "latest_run_id": "synthetic-run-same-attempt",
            "latest_collector_commit": ("%040x" % (index + 300)),
            "day_zero_utc": "2026-10-07T17:16:%02d+00:00" % (index + 1),
            "collecting_days": ["2026-10-07", "2026-10-08"],
            "missing_collecting_days": missing or [],
            "consecutive_collecting_days": 2,
            "window_coverage": [["2026-10-07", "2026-10-08"]],
            "uncovered_dates": uncovered or [],
            "required_collecting_days": 30,
            "input_sha256": {"shadow.db": "a" * 64},
            "required_review_records": ["synthetic-only-%s" % index],
            "anomalies": anomalies or [],
            "allowed_verdicts": ["pass", "pass_with_findings", "fail"],
            "qualification": None,
            "owner_signoff": None,
        }
        manifest["deterministic_sha256"] = package_sha256(
            manifest, {key: payloads[key] for key in (
                "record_inventory.jsonl", "run_inventory.jsonl", "corpus_evidence.json")})
        manifest["artifact_sha256"] = hashes
        (folder / "review_manifest.json").write_text(plain(manifest), encoding="utf-8")
        if signoff:
            (folder / "signoff.json").write_text(plain({"verdict": "pass"}))
        self.folders.append(folder)
        return folder

    def triplet(self):
        return [self.packet(s, n) for n, s in enumerate(sorted(SOURCES))]

    def test_three_source_packets_cohere_without_implying_signoff(self):
        report = rollup(self.triplet())
        self.assertEqual(report["source_count"], 3)
        self.assertEqual(report["checkpoint"], "day-07")
        self.assertEqual(report["as_of"], "2026-10-14")
        self.assertTrue(report["all_three_review_packets_integrity_checked"])
        self.assertTrue(report["all_three_machine_checkpoints_reached"])
        self.assertEqual(report["machine_warnings"], [])
        self.assertTrue(report["latest_published_run_attempts_aligned"])
        self.assertEqual([x["source_slug"] for x in report["sources"]], sorted(SOURCES))
        self.assertTrue(all(x["required_review_record_count"] == 1 for x in report["sources"]))
        self.assertFalse(report["desk_qualified"])
        self.assertFalse(report["human_signoff_complete"])
        self.assertFalse(report["production_promotion_authorized"])
        self.assertFalse(report["rights_to_publicly_republish_established"])
        self.assertTrue(report["requires_human_complete_corpus_review"])

    def test_partial_publication_run_divergence_is_warning_not_green_alignment(self):
        folders = self.triplet()
        m = json.loads((folders[1] / "review_manifest.json").read_text())
        m["latest_run_id"] = "synthetic-run-partial-push"
        self.rewrite(folders[1], m)
        report = rollup(folders)
        self.assertFalse(report["latest_published_run_attempts_aligned"])
        self.assertEqual(report["machine_warnings"][0]["kind"],
                         "latest_published_run_attempts_diverge")
        self.assertEqual(len(report["machine_warnings"][0]["source_run_ids"]), 3)
        self.assertFalse(report["desk_qualified"])

    def test_not_yet_day_seven_reports_machine_hold_not_failure_of_integrity(self):
        paths = [self.packet(s, i, shadow_day=6) for i,s in enumerate(sorted(SOURCES))]
        report = rollup(paths)
        self.assertFalse(report["all_three_machine_checkpoints_reached"])
        self.assertEqual(len(report["machine_warnings"]), 3)
        self.assertEqual({x["kind"] for x in report["machine_warnings"]}, {"checkpoint_not_reached"})
        self.assertFalse(report["human_signoff_complete"])

    def test_per_source_gap_and_anomaly_are_individual_not_averaged(self):
        names = sorted(SOURCES)
        paths = [
            self.packet(names[0], 0, missing=["2026-10-09"], uncovered=[["2026-10-09", "2026-10-09"]]),
            self.packet(names[1], 1, anomalies=[{"kind": "synthetic-watch"}]),
            self.packet(names[2], 2),
        ]
        report = rollup(paths)
        self.assertEqual([x["kind"] for x in report["machine_warnings"]],
                         ["missing_collecting_days", "uncovered_publication_window",
                          "unresolved_machine_anomaly"])
        self.assertEqual(report["sources"][0]["missing_collecting_days_count"], 1)
        self.assertEqual(report["sources"][1]["anomaly_count"], 1)
        self.assertFalse(report["desk_qualified"])

    def test_duplicate_source_packet_refused(self):
        folders = self.triplet()
        with self.assertRaisesRegex(RollupRefused, "duplicate ministry source"):
            rollup([folders[0], folders[0], folders[2]])

    def test_missing_packet_refused(self):
        paths = self.triplet()
        with self.assertRaisesRegex(RollupRefused, "exactly three"):
            rollup(paths[:2])

    def test_mixed_checkpoint_and_dates_refused(self):
        names = sorted(SOURCES)
        folders = [
            self.packet(names[0], 0),
            self.packet(names[1], 1, checkpoint="day-14", shadow_day=14),
            self.packet(names[2], 2)
        ]
        with self.assertRaisesRegex(RollupRefused, "mixed checkpoint"):
            rollup(folders)
        folders = self.triplet()
        changed = json.loads((folders[1] / "review_manifest.json").read_text())
        changed["as_of"] = "2026-10-15"
        self.rewrite(folders[1], changed)
        with self.assertRaisesRegex(RollupRefused, "mixed checkpoint"):
            rollup(folders)

    def rewrite(self, folder, manifest):
        payloads = {name: (folder / name).read_text() for name in ARTIFACT_FILES}
        manifest.pop("artifact_sha256", None)
        manifest.pop("deterministic_sha256", None)
        manifest["deterministic_sha256"] = package_sha256(manifest, {
            name: payloads[name] for name in
            ("record_inventory.jsonl", "run_inventory.jsonl", "corpus_evidence.json")
        })
        manifest["artifact_sha256"] = {name: hashlib.sha256(payloads[name].encode()).hexdigest()
                                        for name in ARTIFACT_FILES}
        (folder / "review_manifest.json").write_text(plain(manifest))

    def test_tampered_artifact_refused(self):
        folders = self.triplet()
        (folders[0] / "corpus_evidence.json").write_text('{"source_text":"tampered"}')
        with self.assertRaisesRegex(RollupRefused, "artifact digest mismatch"):
            rollup(folders)

    def test_forged_deterministic_identity_refused(self):
        folders = self.triplet()
        filename = folders[0] / "review_manifest.json"
        manifest = json.loads(filename.read_text())
        manifest["deterministic_sha256"] = "b" * 64
        filename.write_text(plain(manifest))
        with self.assertRaisesRegex(RollupRefused, "deterministic packet identity mismatch"):
            rollup(folders)

    def test_wrong_source_branch_refused_even_if_rehashed(self):
        folders = self.triplet()
        m = json.loads((folders[1] / "review_manifest.json").read_text())
        m["state_branch"] = "shadow/vietnam-mps-foreign-affairs"
        self.rewrite(folders[1], m)
        with self.assertRaisesRegex(RollupRefused, "source or state branch"):
            rollup(folders)

    def test_wrong_cross_source_day_zero_batch_refused(self):
        folders = self.triplet()
        m = json.loads((folders[2] / "review_manifest.json").read_text())
        m["day_zero_utc"] = "2026-10-08T17:16:03+00:00"
        self.rewrite(folders[2], m)
        with self.assertRaisesRegex(RollupRefused, "clocks do not form"):
            rollup(folders)

    def test_forged_checkpoint_reached_refused_even_if_rehashed(self):
        folders = self.triplet()
        m = json.loads((folders[0] / "review_manifest.json").read_text())
        m["latest_shadow_day"] = 2
        self.rewrite(folders[0], m)
        with self.assertRaisesRegex(RollupRefused, "threshold flag"):
            rollup(folders)

    def test_automatic_approval_and_signoff_files_refused(self):
        folders = self.triplet()
        m = json.loads((folders[0] / "review_manifest.json").read_text())
        m["owner_signoff"] = True
        self.rewrite(folders[0], m)
        with self.assertRaisesRegex(RollupRefused, "owner approval"):
            rollup(folders)
        folders = self.triplet()
        (folders[0] / "signoff.json").write_text(plain({"reviewer":"synthetic"}))
        with self.assertRaisesRegex(RollupRefused, "signoff is separately"):
            rollup(folders)

    def test_symlinked_packet_artifact_refused(self):
        folders = self.triplet()
        path = folders[0] / "corpus_evidence.json"
        out = self.root / "elsewhere.json"
        out.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(out)
        with self.assertRaises(RollupRefused):
            rollup(folders)

    def test_bad_or_duplicate_json_fields_refused(self):
        folders = self.triplet()
        p = folders[0] / "review_manifest.json"
        p.write_text('{"schema":1,"schema":2}')
        with self.assertRaisesRegex(RollupRefused, "duplicate JSON field"):
            rollup(folders)

    def test_no_io_to_external_sources_or_publication(self):
        import inspect
        from scripts import vietnam_ministry_checkpoint_rollup as module
        code = inspect.getsource(module)
        for forbidden in ("requests.", "urlopen(", "subprocess.", "sqlite3.connect",
                          "write_text(", "send_mail", "gh-pages", "git push"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
