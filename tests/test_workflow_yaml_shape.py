"""
Structural lint for workflow files.

PyYAML is deliberately not a dependency of this project, so a malformed
workflow cannot be caught by parsing it here. It is caught by GitHub, at
push time, as a run with no name, no triggers and no jobs — which is a slow
and confusing way to learn that a shell heredoc broke a block scalar.

That is exactly what happened to the Singapore shadow workflow: a `git commit
-m` message whose continuation lines began at column 0 terminated the `run: |`
block, and the whole document stopped parsing. GitHub then reported the file
by path rather than by name and refused `workflow_dispatch`, because as far as
it could tell the workflow declared no triggers at all.

This checks the one structural property that failure violated, across every
workflow, without a YAML parser.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

WORKFLOWS = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))

#: A line at column 0 in a workflow is only ever a top-level key, a comment,
#: a document marker, or blank. Anything else there is content that escaped a
#: block scalar — which is precisely how a `git commit -m` message with
#: column-0 continuation lines silently destroyed the Singapore shadow
#: workflow: YAML ended the `run: |` block at the first such line and then read
#: the message text as a top-level token.
TOP_LEVEL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*:")
ALLOWED_BARE = ("#", "---", "...")


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


class TestWorkflowsParseStructurally(unittest.TestCase):

    def test_there_is_at_least_one_workflow(self):
        self.assertTrue(WORKFLOWS)

    def test_no_content_sits_at_column_zero(self):
        """
        The check that would have caught the broken shadow workflow before it
        reached main, where it cost two failed runs and a refused dispatch.
        """
        for wf in WORKFLOWS:
            for n, line in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip() or indent_of(line) != 0:
                    continue
                if line.startswith(ALLOWED_BARE) or TOP_LEVEL_RE.match(line):
                    continue
                with self.subTest(workflow=wf.name, line=n):
                    self.fail("%s line %d is at column 0 but is not a top-level "
                              "key — it has escaped a block scalar: %r"
                              % (wf.name, n, line[:70]))

    def test_top_level_keys_are_the_expected_workflow_keys(self):
        allowed = {"name", "on", "true", "concurrency", "permissions", "jobs",
                   "env", "defaults", "run-name"}
        for wf in WORKFLOWS:
            for n, line in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
                if indent_of(line) or not line.strip() or line.startswith(ALLOWED_BARE):
                    continue
                m = TOP_LEVEL_RE.match(line)
                if not m:
                    continue
                key = line.split(":", 1)[0]
                with self.subTest(workflow=wf.name, line=n, key=key):
                    self.assertIn(key, allowed,
                                  "unexpected top-level key %r — usually a sign "
                                  "that block content escaped" % key)

    def test_every_workflow_declares_a_name_and_triggers(self):
        for wf in WORKFLOWS:
            text = wf.read_text(encoding="utf-8")
            with self.subTest(workflow=wf.name):
                self.assertRegex(text, r"(?m)^name:\s*\S",
                                 "no top-level name: GitHub will show the path")
                self.assertRegex(text, r"(?m)^on:\s*$|^on:\s*\S",
                                 "no top-level on: block")

    def test_no_tabs_and_no_carriage_returns(self):
        for wf in WORKFLOWS:
            raw = wf.read_bytes()
            with self.subTest(workflow=wf.name):
                self.assertNotIn(b"\t", raw)
                self.assertNotIn(b"\r", raw)

    def test_the_shadow_workflow_still_declares_manual_dispatch(self):
        wf = (REPO_ROOT / ".github" / "workflows" / "singapore_shadow.yml")
        text = wf.read_text(encoding="utf-8")
        on_block = text.split("\non:", 1)[1].split("\nconcurrency:", 1)[0]
        self.assertIn("workflow_dispatch:", on_block)
        self.assertIn("schedule:", on_block)


if __name__ == "__main__":
    unittest.main()
