"""Collection must survive a failing Pages-writer audit (issue #346).

The writer ratchet is publication eligibility, not build health. These tests
prove that with an unregistered gh-pages writer present:

* daily_update's pre-collection suite invocation still passes, so collection,
  validation and the database commit proceed;
* the publication gate (the auditor CLI) still fails, so the deploy is blocked;
* the PR CI invocation still fails.

They also pin where daily_update places each half. This does NOT fix the
stale-deploy race; see tests/test_pages_stale_deploy_race.py.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import audit_pages_writers as audit  # noqa: E402

WORKFLOWS = ROOT / ".github" / "workflows"
GATE_RUN = "python scripts/audit_pages_writers.py"
SUITE_RUN = "python -m unittest discover -s tests -t ."

UNREGISTERED_WRITER = """\
name: Unregistered publisher
on:
  workflow_dispatch:
jobs:
  ship:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: main
      - uses: peaceiris/actions-gh-pages@v3
        with:
          publish_dir: ./output
"""


def steps(workflow_text):
    """Split a workflow into (name, body) step blocks, in order."""
    parts = re.split(r"^      - name: (.+)$", workflow_text, flags=re.M)
    return [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts), 2)]


class CollectionSurvivesFailingAudit(unittest.TestCase):
    """End to end in a scratch repository holding the real ratchet files."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        for rel in ("scripts/audit_pages_writers.py", "tests/__init__.py",
                    "tests/test_pages_writer_audit.py"):
            (cls.tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, cls.tmp / rel)
        wf = cls.tmp / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "unregistered.yml").write_text(UNREGISTERED_WRITER, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def run_in_tmp(self, cmd, defer):
        env = {k: v for k, v in os.environ.items() if k != audit.DEFER_ENV}
        if defer:
            env[audit.DEFER_ENV] = "1"
        return subprocess.run([sys.executable, *cmd.split()[1:]], cwd=self.tmp,
                              env=env, capture_output=True, text=True)

    def test_scratch_repo_really_has_an_audit_violation(self):
        report = audit.run_audit(self.tmp)
        self.assertIn("UNREGISTERED_WRITER",
                      [v["kind"] for v in report["violations"]])

    def test_collection_suite_step_passes(self):
        result = self.run_in_tmp(SUITE_RUN + " -v", defer=True)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertIn("deferred to daily_update's publication gate", result.stderr)

    def test_publication_gate_blocks(self):
        result = self.run_in_tmp(GATE_RUN, defer=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("UNREGISTERED_WRITER", result.stdout)

    def test_pr_ci_suite_blocks(self):
        result = self.run_in_tmp(SUITE_RUN, defer=False)
        self.assertNotEqual(result.returncode, 0)


class WorkflowPlacement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.daily = steps((WORKFLOWS / "daily_update.yml").read_text(encoding="utf-8"))
        cls.names = [name for name, _ in cls.daily]

    def index_running(self, command):
        hits = [i for i, (_, body) in enumerate(self.daily) if command in body]
        self.assertEqual(len(hits), 1, command)
        return hits[0]

    def test_pre_collection_suite_defers_the_ratchet(self):
        body = self.daily[self.index_running(SUITE_RUN)][1]
        self.assertRegex(body, rf'{audit.DEFER_ENV}: "1"')

    def test_gate_sits_after_collection_and_commit_and_before_deploy(self):
        gate = self.index_running(GATE_RUN)
        for name in ("Run offline test suite", "Run pipeline",
                     "Validate rendered output",
                     "Commit updated database and site output"):
            self.assertLess(self.names.index(name), gate, name)
        self.assertEqual(self.names[gate + 1], "Deploy to GitHub Pages")
        self.assertNotIn("continue-on-error", self.daily[gate][1])

    def test_only_daily_update_defers_and_pr_ci_stays_blocking(self):
        users = sorted(p.name for p in WORKFLOWS.glob("*.y*ml")
                       if audit.DEFER_ENV in p.read_text(encoding="utf-8"))
        self.assertEqual(users, ["daily_update.yml"])
        pr = (WORKFLOWS / "pr_offline_checks.yml").read_text(encoding="utf-8")
        self.assertIn(SUITE_RUN, pr)


if __name__ == "__main__":
    unittest.main()
