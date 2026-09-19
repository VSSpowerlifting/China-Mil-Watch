"""
The US shadow workflow: what it may do, and what it may never do.

A workflow is the one place in this project where a mistake writes to a durable
remote ref without anyone watching. These tests hold the properties that make
that safe, and they read the file rather than trusting the comments in it.

Read as TEXT, not with a parser. PyYAML is deliberately not a dependency of
this project -- see `tests/test_workflow_yaml_shape.py` for why -- so these
assertions work on the source the way GitHub's own diff reader does.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
US = WORKFLOWS / "us_shadow.yml"
RAW = US.read_text(encoding="utf-8")
STATE_BRANCH = "shadow/us-indopacom"

#: `- name: X` down to the next one. Enough to ask which steps exist, in what
#: order, with which `if:` guard and which `run:` body.
_STEP_RE = re.compile(r"^      - name: (.+?)$", re.MULTILINE)


def step_names():
    return _STEP_RE.findall(RAW)


def step_block(name):
    """The text of one step, from its `- name:` to the next step or the end."""
    starts = [(m.group(1), m.start()) for m in _STEP_RE.finditer(RAW)]
    for i, (found, pos) in enumerate(starts):
        if found == name:
            end = starts[i + 1][1] if i + 1 < len(starts) else len(RAW)
            return RAW[pos:end]
    raise AssertionError("no step named %r" % name)


def executable_lines():
    """
    The workflow with comments stripped.

    Checking for a deployment step against the raw text matched the comment
    that says there is no Pages step. A guard that a denial can trip is not a
    guard.
    """
    out = []
    for line in RAW.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        out.append(line.split(" #", 1)[0] if " #" in line else line)
    return "\n".join(out)


EXEC = executable_lines()


def crons(text):
    return re.findall(r"^\s*- cron: '([^']+)'", text, re.MULTILINE)


class TestItCanOnlyWriteItsOwnStateBranch(unittest.TestCase):

    def test_the_only_permission_is_contents_write(self):
        block = RAW.split("permissions:", 1)[1].split("\njobs:", 1)[0]
        granted = re.findall(r"^\s+([a-z-]+):\s*(\S+)", block, re.MULTILINE)
        self.assertEqual(granted, [("contents", "write")])

    def test_it_names_only_its_own_state_branch(self):
        self.assertIn(STATE_BRANCH, RAW)
        for other in ("shadow/singapore-mindef", "shadow/jp-mod"):
            self.assertNotIn(other, EXEC, other)

    def test_every_push_targets_that_branch(self):
        pushes = re.findall(r"git push[^\n]*", RAW)
        self.assertTrue(pushes)
        for push in pushes:
            self.assertIn(STATE_BRANCH, push, push)

    def test_no_push_is_forced(self):
        """
        Not even --force-with-lease. A divergent state branch means another
        writer got there first, and this run must fail and be re-run against
        the new state rather than decide its own state is the correct one.
        """
        for forced in ("--force", "force-with-lease", "push -f"):
            self.assertNotIn(forced, EXEC, forced)

    def test_it_never_pushes_to_main(self):
        self.assertNotRegex(RAW, r"git push[^\n]*\bmain\b")

    def test_it_has_no_deployment_step(self):
        low = EXEC.lower()
        for deploy in ("pages", "deploy", "gh-pages", "upload-pages-artifact"):
            self.assertNotIn(deploy, low, deploy)

    def test_it_never_names_the_production_database_or_output(self):
        self.assertNotIn("pla_watch.db", EXEC)
        self.assertNotRegex(EXEC, r"(?<!shadow-)(?<!GITHUB_)\boutput/")


class TestConcurrencyAndScheduling(unittest.TestCase):

    def test_a_running_collection_is_never_cancelled(self):
        """
        A cancelled run can leave a half-written state directory. The next run
        would then clone a branch that is fine but rehearse against local
        wreckage, so runs queue instead.
        """
        self.assertIn("cancel-in-progress: false", RAW)

    def test_the_concurrency_group_is_this_desk_alone(self):
        group = re.search(r"concurrency:\n\s+group: (\S+)", RAW).group(1)
        self.assertEqual(group, "us-indopacom-shadow")
        for other in ("singapore", "japan", "jp-mod", "daily"):
            self.assertNotIn(other, group)

    def test_the_schedule_is_separated_from_every_other_workflow(self):
        """
        Separation is measured against the lateness each schedule has actually
        shown, not its nominal time. Japan has run up to 7h38m late.
        """
        mine = crons(RAW)[0]
        self.assertEqual(mine, "40 8 * * *")
        others = set()
        for path in WORKFLOWS.glob("*.yml"):
            if path != US:
                others.update(crons(path.read_text(encoding="utf-8")))
        self.assertNotIn(mine, others)
        # No other schedule sits in the same UTC hour.
        my_hour = int(mine.split()[1])
        for cron in others:
            self.assertNotEqual(int(cron.split()[1]), my_hour, cron)

    def test_the_cron_and_the_collector_argument_agree(self):
        """
        `--cron-utc` is how the collector learns the LOGICAL slot. If it drifts
        from the cron above it, a late run is stamped with the wrong day --
        the exact defect that left two Singapore days with no ledger.
        """
        cron = crons(RAW)[0]
        minute, hour = cron.split()[0], cron.split()[1]
        expected = "%02d:%02d" % (int(hour), int(minute))
        self.assertIn('--cron-utc "%s"' % expected, RAW)

    def test_a_manual_dispatch_can_name_the_day_it_recovers(self):
        self.assertIn("workflow_dispatch:", RAW)
        self.assertIn("target_date:", RAW)

    def test_the_dispatch_input_reaches_the_script_through_the_environment(self):
        # Never interpolated into a shell body, where a crafted value would be
        # executed rather than parsed.
        self.assertIn("TARGET_DATE: ${{ inputs.target_date }}", RAW)
        self.assertNotIn('--target-date "${{', RAW)


class TestStateIsolation(unittest.TestCase):

    def test_state_is_checked_out_outside_the_collector(self):
        self.assertIn("${RUNNER_TEMP}/shadow-state", RAW)
        self.assertIn("--state-dir \"${RUNNER_TEMP}/shadow-state/state\"", RAW)

    def test_an_isolation_assertion_runs_before_collection(self):
        names = step_names()
        self.assertIn("Assert the state checkout is not the repository", names)
        self.assertLess(names.index("Assert the state checkout is not the repository"),
                        names.index("Run shadow collection"))

    def test_the_branch_is_created_as_an_orphan_when_absent(self):
        self.assertIn("checkout --orphan %s" % STATE_BRANCH, RAW)

    def test_a_wal_or_shm_sidecar_is_refused_before_commit(self):
        self.assertIn("shadow.db-wal", RAW)
        self.assertIn("shadow.db-shm", RAW)
        self.assertIn("refusing to commit a WAL/SHM sidecar", RAW)

    def test_publishing_only_happens_after_a_successful_collection(self):
        self.assertIn("if: success()", step_block("Publish shadow state"))


class TestTheLedgerIsAppendOnly(unittest.TestCase):

    def test_an_append_only_assertion_exists(self):
        self.assertIn("Assert the ledger is append-only", step_names())

    def test_it_fails_on_a_modified_or_deleted_entry(self):
        body = step_block("Assert the ledger is append-only")
        self.assertIn("git diff --name-status -- state/ledger", body)
        self.assertIn("grep -E '^(M|D|R)'", body)
        self.assertIn("exit 1", body)

    def test_it_fails_when_the_entry_count_falls(self):
        self.assertIn('-lt "${before}"',
                      step_block("Assert the ledger is append-only"))

    def test_it_runs_even_when_collection_failed(self):
        self.assertIn("if: always()",
                      step_block("Assert the ledger is append-only"))


class TestTheWorkflowSaysWhatItCollects(unittest.TestCase):

    def test_the_header_carries_the_required_framing(self):
        # The framing lives in the header COMMENT and wraps across lines, so
        # the leading "#" must come off before flattening or every multi-line
        # phrase looks absent.
        prose = re.sub(r"^\s*#\s?", "", RAW.lower(), flags=re.MULTILINE)
        flat = re.sub(r"\s+", " ", prose)
        for phrase in ("dvids usindopacom-tagged reference stream",
                       "tier b dod media-service feed",
                       "unit tagging does not imply command authorship",
                       "not a complete usindopacom command-release wire",
                       "not presently a peer of the china desk",
                       "access_blocked"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, flat)


if __name__ == "__main__":
    unittest.main()
