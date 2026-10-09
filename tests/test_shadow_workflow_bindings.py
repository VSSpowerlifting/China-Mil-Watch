"""Strict offline shadow source workflow binding contracts. No collector or network."""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import audit_shadow_workflow_bindings as audit


class BindingContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = audit.validate()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-workflow-binding-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        config = json.loads((audit.ROOT / "config/shadow_source_workflow_bindings.json").read_text())
        self.config = copy.deepcopy(config)
        self.manifest_paths = sorted({x["manifest"] for x in config["sources"]})
        self.workflow_paths = sorted({x["workflow"] for x in config["sources"] if x["workflow"]})
        for path in self.manifest_paths + self.workflow_paths:
            dst = self.root / path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(audit.ROOT / path, dst)
        self.write_config()

    def write_config(self):
        path = self.root / "config/shadow_source_workflow_bindings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.config), encoding="utf-8")

    def report(self):
        self.write_config()
        return audit.validate(self.root)

    def test_real_repository_has_exact_explicit_coverage(self):
        result = self.original
        self.assertEqual(11, result["manifests_checked"])
        self.assertEqual(16, result["source_families_checked"])
        self.assertFalse(result["all_runs_attested"])
        self.assertFalse(result["shadow_promotion_authorized"])
        self.assertFalse(result["editorial_publication_authorized"])
        self.assertFalse(result["production_eligible"])
        self.assertEqual(0, result["writes"])
        self.assertEqual(len(result["sources"]), 16)

    def test_synthetic_mirror_preserves_count_without_modifications(self):
        result = self.report()
        self.assertEqual(result["source_families_checked"], 16)
        self.assertTrue(all(not s["run_attested"] for s in result["sources"]))

    def test_missing_source_binding_is_a_hard_error(self):
        self.config["sources"].pop()
        with self.assertRaisesRegex(audit.BindingError, "coverage drift"):
            self.report()

    def test_duplicate_source_binding_is_a_hard_error(self):
        self.config["sources"].append(copy.deepcopy(self.config["sources"][0]))
        with self.assertRaisesRegex(audit.BindingError, "duplicate"):
            self.report()

    def test_new_source_in_existing_manifest_fails_closed(self):
        name = self.root / "shadow/id_kemhan/manifest.json"
        d = json.loads(name.read_text())
        second = copy.deepcopy(d["sources"][0])
        second["slug"] = "id_kemhan_new"
        d["sources"].append(second)
        name.write_text(json.dumps(d))
        with self.assertRaisesRegex(audit.BindingError, "coverage drift"):
            self.report()

    def test_new_manifest_family_cannot_be_silently_ignored(self):
        name = self.root / "shadow/new_candidate/manifest.json"
        name.parent.mkdir(parents=True)
        d = json.loads((self.root / "shadow/id_kemhan/manifest.json").read_text())
        d["sources"][0]["slug"] = "new_candidate_source"
        name.write_text(json.dumps(d))
        with self.assertRaisesRegex(audit.BindingError, "coverage drift"):
            self.report()

    def test_promoted_shadow_manifest_cannot_claim_safe_shadow_state(self):
        name = self.root / "shadow/id_kemhan/manifest.json"
        d = json.loads(name.read_text())
        d["desk"]["active"] = True
        name.write_text(json.dumps(d))
        with self.assertRaisesRegex(audit.BindingError, "admission status"):
            self.report()

    def test_commented_cron_is_not_a_live_schedule(self):
        name = self.root / ".github/workflows/ph_afp_shadow.yml"
        s = name.read_text()
        self.assertIn("- cron: '40 6 * * *'", s)
        name.write_text(s.replace("- cron: '40 6 * * *'",
                                  "# - cron: '40 6 * * *'"))
        with self.assertRaisesRegex(audit.BindingError, "expected active schedule"):
            self.report()

    def test_branch_mention_in_comment_does_not_count(self):
        name = self.root / ".github/workflows/ph_afp_shadow.yml"
        s = name.read_text()
        self.assertIn("shadow/ph-afp", s)
        name.write_text(s.replace("shadow/ph-afp", "shadow/ph-afp-unknown") +
                        "\n# shadow/ph-afp\n")
        with self.assertRaisesRegex(audit.BindingError, "branch not in active"):
            self.report()

    def test_manual_only_workflow_cannot_gain_schedule_without_review(self):
        name = self.root / ".github/workflows/vietnam_shadow.yml"
        s = name.read_text()
        self.assertIn("on:\n", s)
        name.write_text(s.replace("on:\n", "on:\n  schedule:\n    - cron: '35 17 * * *'\n", 1))
        with self.assertRaisesRegex(audit.BindingError, "manual-only binding"):
            self.report()

    def test_shared_korean_coverage_cannot_use_indonesia_branch(self):
        item = next(s for s in self.config["sources"]
                    if s["source_slug"] == "kr_policy_mnd_releases")
        item["state_branch"] = "shadow/indonesia-kemhan"
        # Both branch literals occur in this shared YAML! Explicit row still
        # cannot automatically prove correct routing: the audit is a text
        # declaration match, not a runtime Actions/ledger attestation.
        result = self.report()
        korea = next(s for s in result["sources"]
                     if s["source_slug"] == "kr_policy_mnd_releases")
        self.assertEqual(korea["evidence"],
                         "cron_and_branch_literals_found_not_run_verified")
        self.assertFalse(korea["run_attested"])

    def test_research_only_journal_cannot_claim_hidden_workflow(self):
        item = next(s for s in self.config["sources"]
                    if s["source_slug"] == "vn_national_defence_journal_en")
        item["workflow"] = ".github/workflows/vietnam_shadow.yml"
        with self.assertRaisesRegex(audit.BindingError, "research-only source"):
            self.report()

    def test_invalid_or_traversing_workflow_path_refused(self):
        item = self.config["sources"][0]
        item["workflow"] = ".github/workflows/../../shadow/id_kemhan/manifest.json"
        with self.assertRaises(audit.BindingError):
            self.report()

    def test_duplicate_source_slug_in_manifest_refused(self):
        name = self.root / "shadow/jp_mod/manifest.json"
        d = json.loads(name.read_text())
        d["sources"][1]["slug"] = d["sources"][0]["slug"]
        name.write_text(json.dumps(d))
        with self.assertRaisesRegex(audit.BindingError, "duplicate shadow source"):
            self.report()

    def test_schema_or_evidence_label_drift_is_refused(self):
        self.config["status"] = "live_healthy"
        with self.assertRaisesRegex(audit.BindingError, "non-live evidence label"):
            self.report()

    def test_workflow_cron_parser_ignores_non_trigger_crons(self):
        snippet = "\n".join([
            "# on:\n#   schedule:\n#     - cron: '40 6 * * *'",
            "on:", "  workflow_dispatch:",
            "jobs:", "  sample:", "    steps:",
            "      - run: 'echo schedule: cron: 40 6 * * *'"
        ])
        self.assertEqual([], audit.workflow_crons(snippet))
        self.assertEqual(["40 6 * * *"], audit.workflow_crons(
            "on:\n  schedule:\n    - cron: '40 6 * * *'\n  workflow_dispatch:\n"))


if __name__ == "__main__":
    unittest.main()
