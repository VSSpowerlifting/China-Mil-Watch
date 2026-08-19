"""
Workflow ordering contract.

The daily workflow's correctness is largely a property of step ORDER, and order
is easy to break silently in a later edit. These tests parse
`.github/workflows/daily_update.yml` as text and assert the orderings that
matter, so a reordering fails here rather than in production at 12:23 UTC.

Deliberately text-based: PyYAML is not a dependency of this project, and adding
one to the daily collection path to parse a file we only need to check the shape
of would be the wrong trade. The assertions key off step names, which are stable
and human-meaningful.

Nothing here executes the workflow, contacts GitHub, or deploys.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily_update.yml"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def step_names(text: str):
    """Step names in file order."""
    return re.findall(r"^      - name:\s*(.+?)\s*$", text, re.M)


def index_of(names, fragment: str) -> int:
    for i, name in enumerate(names):
        if fragment.lower() in name.lower():
            return i
    raise AssertionError(
        "no workflow step matching %r; steps are: %s" % (fragment, names))


def strip_comment(line: str) -> str:
    """
    Drop a trailing shell/YAML comment, honouring quotes.

    Stripping only whole-line comments was not enough: a trailing
    `fetch-depth: 0   # ... push-back step` or `echo hi  # git push` puts the
    command vocabulary these tests key off into a line that survives, so a step
    could appear to push, or appear to verify, purely from prose. Quote-aware
    because the workflow legitimately contains `echo "### ..."`, where the hash
    is data rather than a comment.

    A `#` opens a comment only outside quotes and at the start of a word, which
    is the shell's own rule. Backslash escapes are not modelled; the workflow
    contains none, and a test parser that silently guessed at them would be
    worse than one with a stated limit.
    """
    out = []
    quote = None
    prev_ws = True                      # start of line counts as a word break
    for ch in line:
        if quote is not None:
            out.append(ch)
            if ch == quote:
                quote = None
            prev_ws = False
        elif ch in ("'", '"'):
            quote = ch
            out.append(ch)
            prev_ws = False
        elif ch == "#" and prev_ws:
            break
        else:
            out.append(ch)
            prev_ws = ch.isspace()
    return "".join(out).rstrip()


def step_blocks(text: str):
    """
    (name, executable-body) per step.

    Comments are stripped from the body: the workflow's comments quote the very
    commands under test (`git pull --rebase`, `git push`), and matching prose
    would attribute a rebase to whichever step the comment happens to precede.
    """
    parts = re.split(r"^      - name:", text, flags=re.M)[1:]
    out = []
    for part in parts:
        lines = part.splitlines()
        name = lines[0].strip()
        body = "\n".join(strip_comment(line) for line in lines[1:])
        out.append((name, body))
    return out


class TestPrePipelineGates(unittest.TestCase):
    """Migrations and the offline suite must precede any collection."""

    def setUp(self):
        self.text = workflow_text()
        self.names = step_names(self.text)

    def test_migrations_apply_before_pipeline(self):
        self.assertLess(index_of(self.names, "Apply database migrations"),
                        index_of(self.names, "Run pipeline"))

    def test_migrations_verified_before_pipeline(self):
        self.assertLess(index_of(self.names, "Verify database schema"),
                        index_of(self.names, "Run pipeline"))

    def test_apply_precedes_verify(self):
        self.assertLess(index_of(self.names, "Apply database migrations"),
                        index_of(self.names, "Verify database schema"))

    def test_offline_suite_runs_before_pipeline(self):
        self.assertLess(index_of(self.names, "Run offline test suite"),
                        index_of(self.names, "Run pipeline"),
                        "tests must gate collection, not follow it")

    def test_reconciliation_contract_runs_before_pipeline(self):
        self.assertLess(index_of(self.names, "Reconciliation contract"),
                        index_of(self.names, "Run pipeline"))

    def test_tests_run_before_any_commit_or_deploy(self):
        suite = index_of(self.names, "Run offline test suite")
        for later in ("Commit updated database", "Deploy to GitHub Pages",
                      "Record successful run"):
            self.assertLess(suite, index_of(self.names, later))

    def test_db_cleanliness_asserted_after_tests(self):
        self.assertLess(index_of(self.names, "Run offline test suite"),
                        index_of(self.names, "Assert offline tests left the tracked"))
        self.assertLess(index_of(self.names, "Assert offline tests left the tracked"),
                        index_of(self.names, "Run pipeline"))


class TestPostRebaseVerification(unittest.TestCase):
    """
    Every rebase that can precede a push must verify the database first.

    The reconciler now migrates its output before merging rows, so these checks
    are ordinarily no-ops. They exist so a regressed database fails closed
    instead of reaching origin.
    """

    def setUp(self):
        self.text = workflow_text()

    def test_every_push_is_preceded_by_verification(self):
        offenders = []
        for name, block in step_blocks(self.text):
            if "git push" not in block:
                continue
            push_at = block.index("git push")
            verify_at = block.find("verify_db_current.py")
            if verify_at == -1 or verify_at > push_at:
                offenders.append(name)
        self.assertEqual(
            offenders, [],
            "these steps push without a preceding database verification: %s"
            % offenders,
        )

    def test_every_rebase_step_verifies(self):
        offenders = []
        for name, block in step_blocks(self.text):
            if "git pull --rebase" not in block:
                continue
            if "verify_db_current.py" not in block:
                offenders.append(name)
        self.assertEqual(
            offenders, [],
            "these steps rebase without verifying the result: %s" % offenders,
        )

    def test_verification_follows_the_rebase_not_precedes_it(self):
        for name, block in step_blocks(self.text):
            if "git pull --rebase" not in block or "verify_db_current.py" not in block:
                continue
            self.assertLess(
                block.index("git pull --rebase"),
                block.index("verify_db_current.py"),
                "%s verifies before its rebase, which proves nothing" % name,
            )


class TestRepairIsScoped(unittest.TestCase):
    """
    `--repair` may only appear on a path that commits pla_watch.db, and must be
    provably included in the pushed commit.
    """

    def setUp(self):
        self.text = workflow_text()

    def test_repair_only_on_db_committing_paths(self):
        for name, block in step_blocks(self.text):
            if "verify_db_current.py --repair" not in block:
                continue
            self.assertIn(
                "git add pla_watch.db", block,
                "%s repairs the database but does not commit it" % name,
            )

    def test_repair_paths_prove_inclusion_in_the_pushed_commit(self):
        for name, block in step_blocks(self.text):
            if "verify_db_current.py --repair" not in block:
                continue
            self.assertIn(
                "git diff --quiet HEAD -- pla_watch.db", block,
                "%s does not prove the repaired database is in the commit "
                "it pushes" % name,
            )
            # A second, non-repairing verification must gate the push.
            tail = block[block.index("git diff --quiet HEAD -- pla_watch.db"):]
            self.assertIn(
                "verify_db_current.py", tail,
                "%s does not re-verify after repairing" % name,
            )

    def test_marker_paths_do_not_repair(self):
        for fragment in ("billing-failure marker", "Record successful run"):
            for name, block in step_blocks(self.text):
                if fragment.lower() not in name.lower():
                    continue
                self.assertNotIn(
                    "--repair", block,
                    "%s is a marker-only path and must not alter the database"
                    % fragment,
                )

    def test_marker_paths_guard_their_staging_scope(self):
        for fragment in ("billing-failure marker", "Record successful run"):
            for name, block in step_blocks(self.text):
                if fragment.lower() not in name.lower():
                    continue
                self.assertIn(
                    "Scope violation", block,
                    "%s does not guard against staging unrelated files"
                    % fragment,
                )


class TestPreservedSemantics(unittest.TestCase):
    """Remediation must not have altered existing publication behaviour."""

    def setUp(self):
        self.text = workflow_text()
        self.names = step_names(self.text)

    def test_no_force_push(self):
        self.assertNotIn("push --force", self.text)
        self.assertNotIn("push -f ", self.text)

    def test_persist_on_failure_still_gated_on_failure(self):
        self.assertIn("failure() &&", self.text)

    def test_billing_marker_still_runs_always(self):
        self.assertIn("always() &&", self.text)

    def test_health_gate_is_still_last(self):
        self.assertEqual(index_of(self.names, "Health gate"), len(self.names) - 1)

    def test_health_gate_still_follows_deploy_and_success_marker(self):
        gate = index_of(self.names, "Health gate")
        self.assertGreater(gate, index_of(self.names, "Deploy to GitHub Pages"))
        self.assertGreater(gate, index_of(self.names, "Record successful run"))

    def test_validator_still_gates_deploy(self):
        self.assertLess(index_of(self.names, "Validate rendered output"),
                        index_of(self.names, "Deploy to GitHub Pages"))

    def test_persist_step_still_commits_only_the_database(self):
        for name, block in step_blocks(self.text):
            if "Persist scraped articles" not in name:
                continue
            self.assertNotIn(
                "git add pla_watch.db output/", block,
                "the persist path must never stage output/ — it would bypass "
                "the validator gate",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
