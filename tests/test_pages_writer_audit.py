"""Ratchet tests for scripts/audit_pages_writers.py (issue #346).

These pin the current Pages-writer inventory and prove the auditor catches
new or widened publication paths. Passing them does NOT mean the stale
deployment race is fixed; see tests/test_pages_stale_deploy_race.py.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import audit_pages_writers as audit  # noqa: E402

PEACEIRIS_JOB = """\
name: Synthetic
on:
  workflow_dispatch:
concurrency:
  group: daily-update
  cancel-in-progress: false
jobs:
  ship:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: main
      - name: Deploy
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./output
"""


class RepoInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = audit.run_audit(ROOT)
        cls.by_id = {w["id"]: w for w in cls.report["writers"]}

    def test_no_ratchet_violations(self):
        self.assertEqual(self.report["violations"], [])

    def test_inventory_matches_registry(self):
        self.assertEqual(set(self.by_id), set(audit.REGISTRY))
        self.assertEqual(self.report["script_writers"], [])

    def test_known_writers_outside_shared_lock(self):
        self.assertEqual(self.report["summary"]["outside_shared_lock"], [
            "deploy_output_only.yml::deploy",
            "korea_original_text_pages_release.yml::release-only-this-korean-original",
            "korea_verified_official_link_production.yml::publish-korea-official-links",
        ])

    def test_known_hazards_are_reported_not_hidden(self):
        dep = self.by_id["deploy_output_only.yml::deploy"]
        self.assertEqual(dep["checkout_ref"], "<trigger>")
        for code in ("FULL_TREE_REPLACE", "OUTSIDE_SHARED_LOCK",
                     "NO_PREPUBLISH_FRESHNESS", "NO_MAIN_REF_GUARD"):
            self.assertIn(code, dep["hazards"])
        self.assertIn("NO_PREPUBLISH_FRESHNESS",
                      self.by_id["daily_update.yml::update"]["hazards"])
        self.assertEqual(self.by_id["desks_p4a_render_only_release.yml::release"]["class"],
                         "overlay")

    def test_no_writer_has_a_generation_fence_yet(self):
        # Flip this assertion in the PR that implements the fence.
        self.assertEqual(self.report["summary"]["with_generation_fence"], 0)
        self.assertTrue(all("NO_GENERATION_FENCE" in w["hazards"]
                            for w in self.report["writers"]))

    def test_file_only_writers_keep_pages_cas(self):
        for wid, writer in self.by_id.items():
            if writer["class"] == "file-only":
                self.assertIn("pages_cas", writer["guards"], wid)

    def test_output_is_deterministic_and_secret_free(self):
        cmd = [sys.executable, str(ROOT / "scripts" / "audit_pages_writers.py"), "--json"]
        first = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout
        second = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout
        self.assertEqual(first, second)
        json.loads(first)
        for needle in ("secrets.", "GITHUB_TOKEN", "x-access-token", "github.token"):
            self.assertNotIn(needle, first)


class SyntheticWorkflows(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / ".github" / "workflows").mkdir(parents=True)
        (self.tmp / "scripts").mkdir()

    def write(self, name, text):
        (self.tmp / ".github" / "workflows" / name).write_text(text, encoding="utf-8")

    def run_audit(self, registry=None):
        return audit.run_audit(self.tmp, registry={} if registry is None else registry)

    def kinds(self, report):
        return sorted(v["kind"] for v in report["violations"])

    def test_unregistered_peaceiris_writer_fails(self):
        self.write("new.yml", PEACEIRIS_JOB)
        report = self.run_audit()
        self.assertEqual(self.kinds(report), ["UNREGISTERED_WRITER"])
        self.assertEqual(report["writers"][0]["class"], "full-tree")

    def test_removing_keep_files_is_scope_escalation(self):
        self.write("overlay.yml", PEACEIRIS_JOB)
        reg = {"overlay.yml::ship": {"class": "overlay", "locks": ("daily-update",),
                                     "guards": ()}}
        self.assertEqual(self.kinds(self.run_audit(reg)), ["SCOPE_ESCALATION"])
        self.write("overlay.yml", PEACEIRIS_JOB + "          keep_files: true\n")
        self.assertEqual(self.kinds(self.run_audit(reg)), [])

    def test_force_orphan_is_escalation(self):
        self.write("o.yml", PEACEIRIS_JOB + "          force_orphan: true\n")
        reg = {"o.yml::ship": {"class": "full-tree", "locks": ("daily-update",), "guards": ()}}
        self.assertEqual(self.kinds(self.run_audit(reg)), ["SCOPE_ESCALATION"])

    def test_dropped_lock_and_guard_fail(self):
        self.write("x.yml", PEACEIRIS_JOB.replace("group: daily-update", "group: elsewhere"))
        reg = {"x.yml::ship": {"class": "full-tree", "locks": ("daily-update",),
                               "guards": ("main_cas",)}}
        self.assertEqual(self.kinds(self.run_audit(reg)), ["GUARD_DROPPED", "LOCK_DROPPED"])

    def test_branch_push_to_gh_pages_is_file_only_writer(self):
        self.write("f.yml", PEACEIRIS_JOB.split("      - name: Deploy")[0] + """\
      - run: |
          old="$(git rev-parse HEAD)"
          git fetch origin gh-pages
          test "$(git rev-parse origin/gh-pages)" = "$old"
          git push origin HEAD:refs/heads/gh-pages
""")
        report = self.run_audit()
        self.assertEqual(report["writers"][0]["class"], "file-only")
        self.assertIn("pages_cas", report["writers"][0]["guards"])

    def test_force_push_to_gh_pages_is_orphan_class(self):
        self.write("f.yml", PEACEIRIS_JOB.split("      - name: Deploy")[0]
                   + "      - run: git push --force origin HEAD:gh-pages\n")
        self.assertEqual(self.run_audit()["writers"][0]["class"], "orphan")

    def test_unresolved_variable_refspec_fails_closed(self):
        self.write("v.yml", PEACEIRIS_JOB.split("      - name: Deploy")[0] + """\
      - run: |
          git checkout gh-pages
          git push origin "HEAD:${TARGET}"
""")
        self.assertIn("UNRESOLVED_PUSH_TARGET", self.kinds(self.run_audit()))

    def test_literal_shadow_state_branch_push_is_not_a_writer(self):
        self.write("s.yml", PEACEIRIS_JOB.split("      - name: Deploy")[0] + """\
      - run: |
          state_branch=shadow/example-desk
          git push origin "HEAD:refs/heads/${state_branch}"
          git push origin HEAD:shadow/other
""")
        report = self.run_audit()
        self.assertEqual(report["writers"], [])
        self.assertEqual(report["violations"], [])

    def test_gh_pages_reader_and_commented_push_are_not_writers(self):
        self.write("r.yml", PEACEIRIS_JOB.split("      - name: Deploy")[0] + """\
      - uses: actions/checkout@v4
        with:
          ref: gh-pages
          path: deployed
      - run: |
          # git push origin HEAD:gh-pages   (documentation only)
          test -f deployed/index.html
""")
        report = self.run_audit()
        self.assertEqual(report["writers"], [])
        self.assertEqual(report["violations"], [])

    def test_pages_artifact_deployer_is_detected(self):
        self.write("a.yml", PEACEIRIS_JOB.replace("peaceiris/actions-gh-pages@v3",
                                                  "actions/deploy-pages@v4"))
        self.assertEqual(self.kinds(self.run_audit()), ["UNREGISTERED_WRITER"])

    def test_unregistered_script_writer_fails(self):
        (self.tmp / "scripts" / "ship.sh").write_text(
            "#!/bin/sh\ngit push origin HEAD:gh-pages\n", encoding="utf-8")
        self.assertEqual(self.kinds(self.run_audit()), ["UNREGISTERED_SCRIPT_WRITER"])

    def test_job_and_workflow_groups_are_both_recorded(self):
        text = PEACEIRIS_JOB.replace("    runs-on: ubuntu-latest\n", (
            "    runs-on: ubuntu-latest\n    concurrency:\n      group: pages-deploy\n"), 1)
        self.write("j.yml", text)
        writer = self.run_audit()["writers"][0]
        self.assertEqual(writer["concurrency"], ["daily-update", "pages-deploy"])

    def test_missing_registered_writer_is_note_not_failure(self):
        reg = {"gone.yml::ship": {"class": "full-tree", "locks": (), "guards": ()}}
        report = self.run_audit(reg)
        self.assertEqual(report["violations"], [])
        self.assertEqual(report["notes"][0]["kind"], "REGISTERED_WRITER_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
