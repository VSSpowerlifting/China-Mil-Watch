"""
Offline-test cleanliness gate: phase boundary and behaviour.

The daily workflow asserts that the offline suite did not dirty the tracked
database. Until 2026-08-19 it did that with `git diff --quiet -- pla_watch.db`,
which compares the working tree against the CHECKED-OUT blob — a state recorded
before migrations run. `sync_desk_config()` writes legitimate manifest changes
into the database during the migration step, so any real manifest edit was
reported as test residue and blocked collection outright. A reworded
`sources.mod_china.notes` in `desks/china/manifest.json` did exactly that, and
the daily run failed on it every day from 2026-08-18.

The fix is a phase boundary: hash the database AFTER migrations and schema
verification, and compare AFTER the offline suite and before anything else can
write. These tests pin both halves — where the two steps sit relative to every
other phase, and what the shell in them actually does.

The behavioural tests execute the workflow's own shell, extracted from the YAML,
against disposable databases in a temporary directory. They never touch the
tracked `pla_watch.db`, and they bind to the workflow text rather than to a copy
of it, so editing the workflow without editing the contract fails here.

Deliberately text-based for the ordering half, matching test_workflow_contract:
PyYAML is not a dependency of this project.
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

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily_update.yml"

BASELINE_STEP = "Record offline-test database baseline"
ASSERT_STEP = "Assert offline tests left the tracked database unchanged"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def step_names(text: str):
    return re.findall(r"^      - name:\s*(.+?)\s*$", text, re.M)


def index_of(names, fragment: str) -> int:
    for i, name in enumerate(names):
        if fragment.lower() in name.lower():
            return i
    raise AssertionError(
        "no workflow step matching %r; steps are: %s" % (fragment, names))


def run_body(text: str, fragment: str) -> str:
    """
    The literal shell of one step, dedented and otherwise untouched.

    Comments are NOT stripped here (unlike test_workflow_contract, which is
    matching command vocabulary and must not be fooled by prose): this body gets
    executed, so it has to be exactly what the runner would execute.
    """
    blocks = re.split(r"^      - name:", text, flags=re.M)[1:]
    for block in blocks:
        lines = block.splitlines()
        if fragment.lower() not in lines[0].strip().lower():
            continue
        for i, line in enumerate(lines):
            if re.match(r"^        run: \|\s*$", line):
                body = []
                for candidate in lines[i + 1:]:
                    if candidate.strip() and not candidate.startswith(" " * 10):
                        break
                    body.append(candidate[10:])
                return "\n".join(body).rstrip() + "\n"
        raise AssertionError("step %r has no literal `run: |` block" % fragment)
    raise AssertionError("no step matching %r" % fragment)


class TestPhaseBoundary(unittest.TestCase):
    """Where the baseline and the comparison sit relative to every writer."""

    def setUp(self):
        self.text = workflow_text()
        self.names = step_names(self.text)

    def test_baseline_follows_migrations(self):
        self.assertLess(index_of(self.names, "Apply database migrations"),
                        index_of(self.names, BASELINE_STEP),
                        "config sync writes real manifest changes; baselining "
                        "before it reintroduces the misattribution")

    def test_baseline_follows_schema_verification(self):
        self.assertLess(index_of(self.names, "Verify database schema"),
                        index_of(self.names, BASELINE_STEP))

    def test_baseline_precedes_the_offline_suite(self):
        self.assertLess(index_of(self.names, BASELINE_STEP),
                        index_of(self.names, "Run offline test suite"),
                        "a baseline taken after the suite would measure nothing")

    def test_comparison_follows_the_offline_suite(self):
        self.assertLess(index_of(self.names, "Run offline test suite"),
                        index_of(self.names, ASSERT_STEP))

    def test_comparison_precedes_every_later_writer(self):
        gate = index_of(self.names, ASSERT_STEP)
        for later in ("Reconciliation contract", "Run pipeline",
                      "Validate rendered output", "Persist scraped articles",
                      "Commit updated database", "Deploy to GitHub Pages"):
            self.assertLess(gate, index_of(self.names, later),
                            "%s could otherwise be blamed on the tests" % later)

    def test_gate_no_longer_diffs_against_the_checked_out_blob(self):
        body = run_body(self.text, ASSERT_STEP)
        self.assertNotIn("git diff", body,
                         "comparing against the checkout is the defect this "
                         "step exists to remove")

    def test_baseline_is_stored_outside_the_worktree(self):
        for step in (BASELINE_STEP, ASSERT_STEP):
            body = run_body(self.text, step)
            self.assertIn("${RUNNER_TEMP}/", body,
                          "%s must keep its baseline out of the worktree, "
                          "where it cannot dirty the tree it measures" % step)

    def test_both_steps_fail_closed(self):
        for step in (BASELINE_STEP, ASSERT_STEP):
            self.assertIn("set -euo pipefail", run_body(self.text, step))

    def test_gate_does_not_repair_the_database(self):
        body = run_body(self.text, ASSERT_STEP)
        for repairing in ("git checkout", "git restore", "git stash", "cp ",
                          "VACUUM"):
            self.assertNotIn(repairing, body,
                             "residue is evidence; the gate must not tidy it")

    def test_offline_suite_command_is_unweakened(self):
        blocks = dict((n.strip(), b) for n, b in
                      [(bl.splitlines()[0], bl) for bl in
                       re.split(r"^      - name:", self.text, flags=re.M)[1:]])
        suite = [b for n, b in blocks.items() if "Run offline test suite" in n]
        self.assertEqual(len(suite), 1)
        self.assertIn("python -m unittest discover -s tests -t . -v", suite[0])


class TestGateBehaviour(unittest.TestCase):
    """
    Execute the workflow's own shell against disposable databases.

    Nothing here reads or writes the tracked database.
    """

    def setUp(self):
        text = workflow_text()
        self.baseline_sh = run_body(text, BASELINE_STEP)
        self.assert_sh = run_body(text, ASSERT_STEP)

        self.tmp = tempfile.mkdtemp(prefix="gate-contract-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.work = Path(self.tmp) / "checkout"
        self.runner_temp = Path(self.tmp) / "runner-temp"
        self.work.mkdir()
        self.runner_temp.mkdir()
        self.db = self.work / "pla_watch.db"
        self.db.write_bytes(b"SQLite format 3\x00" + b"\x01" * 4096)

        self.env = dict(os.environ)
        self.env["RUNNER_TEMP"] = str(self.runner_temp)
        if shutil.which("sha256sum") is None:      # macOS ships shasum instead
            shim = Path(self.tmp) / "shim"
            shim.mkdir()
            (shim / "sha256sum").write_text(
                '#!/bin/sh\nexec shasum -a 256 "$@"\n', encoding="utf-8")
            (shim / "sha256sum").chmod(0o755)
            self.env["PATH"] = "%s:%s" % (shim, self.env["PATH"])

    def _run(self, script: str):
        return subprocess.run(
            ["bash", "-c", script], cwd=str(self.work), env=self.env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def _baseline(self):
        result = self._run(self.baseline_sh)
        self.assertEqual(result.returncode, 0, result.stdout)
        return result

    def test_unchanged_database_passes(self):
        self._baseline()
        result = self._run(self.assert_sh)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("left the tracked database unchanged", result.stdout)

    def test_a_change_before_the_baseline_does_not_fail_the_gate(self):
        # Exactly the production case: config sync rewrites a `notes` row during
        # the migration step. That is legitimate, and must not be blamed on the
        # suite that runs afterwards.
        self.db.write_bytes(b"SQLite format 3\x00" + b"\x02" * 4096)
        self._baseline()
        result = self._run(self.assert_sh)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_a_mutation_after_the_baseline_is_detected(self):
        self._baseline()
        self.db.write_bytes(b"SQLite format 3\x00" + b"\x03" * 4096)
        result = self._run(self.assert_sh)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("The offline suite modified pla_watch.db", result.stdout)

    def test_a_detected_mutation_reports_both_hashes(self):
        self._baseline()
        before = (self.runner_temp / "pla_watch.db.baseline.sha256").read_text()
        before_hash = before.split()[0]
        self.db.write_bytes(b"SQLite format 3\x00" + b"\x04" * 4096)
        result = self._run(self.assert_sh)
        self.assertEqual(result.returncode, 1, result.stdout)
        after_hash = subprocess.run(
            ["shasum", "-a", "256", str(self.db)], stdout=subprocess.PIPE,
            text=True).stdout.split()[0]
        self.assertIn(before_hash, result.stdout)
        self.assertIn(after_hash, result.stdout)
        self.assertNotEqual(before_hash, after_hash)

    def test_a_detected_mutation_is_not_repaired(self):
        self._baseline()
        mutated = b"SQLite format 3\x00" + b"\x05" * 4096
        self.db.write_bytes(mutated)
        self._run(self.assert_sh)
        self.assertEqual(self.db.read_bytes(), mutated,
                         "the gate must leave the residue in place")

    def test_a_write_that_lands_only_in_the_wal_is_detected(self):
        # A hash of pla_watch.db alone — and `git diff`, which cannot see an
        # ignored sidecar at all — would both pass this.
        (self.work / "pla_watch.db-wal").write_bytes(b"\x00" * 32)
        self._baseline()
        (self.work / "pla_watch.db-wal").write_bytes(b"\x09" * 32)
        result = self._run(self.assert_sh)
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_a_sidecar_present_at_baseline_is_not_itself_an_error(self):
        # The migration step legitimately leaves a checkpointed -wal behind, so
        # sidecar presence must not fail the daily run the way it does in the PR
        # workflow, where no migration runs.
        (self.work / "pla_watch.db-wal").write_bytes(b"\x00" * 32)
        self._baseline()
        result = self._run(self.assert_sh)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_a_missing_baseline_fails_closed(self):
        result = self._run(self.assert_sh)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Baseline missing", result.stdout)

    def test_the_baseline_is_written_outside_the_checkout(self):
        self._baseline()
        self.assertTrue(
            (self.runner_temp / "pla_watch.db.baseline.sha256").is_file())
        stray = [p.name for p in self.work.iterdir()
                 if p.name not in ("pla_watch.db", "pla_watch.db-wal")]
        self.assertEqual(stray, [],
                         "the gate must not drop files into the worktree it "
                         "is measuring")


if __name__ == "__main__":
    unittest.main()
