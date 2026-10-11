"""No-network functional tests for single-command local private desk snapshot launcher."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.launch_private_country_desks import (
    BRANCHES, ReaderHold, create, exact_state_inputs, main,
)
from tests.test_private_country_desk_reader import git, state_commit


class DeskLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ipr-desk-launch-tests-")
        self.root = Path(self.temp.name)
        self.original = self.root / "original-git"
        self.original.mkdir()
        git(self.original, "init", "-q")
        git(self.original, "config", "user.name", "No Network")
        git(self.original, "config", "user.email", "offline@example.invalid")
        # These are synthetic source states, never publisher originals.
        self.afp = state_commit(
            self.original, "ph_afp_articles", title="Philippine maritime briefing",
            url="https://www.afp.mil.ph/news/sample", identity="afp:994",
            content="PRIVATE SECRET BODY DO NOT EXPORT")
        git(self.original, "branch", "shadow/ph-afp", self.afp)
        self.mps = state_commit(
            self.original, "vn_mps_foreign_affairs_vi", title="Hội nghị giao lưu",
            url="https://bocongan.gov.vn/tin/1", identity="vn-mps:994",
            content="PRIVATE VIETNAMESE BODY DO NOT EXPORT")
        git(self.original, "branch", "shadow/vietnam-mps-foreign-affairs", self.mps)

    def tearDown(self):
        self.temp.cleanup()

    def test_explicit_optin_blocks_any_network_without_flag(self):
        with patch("scripts.launch_private_country_desks.exact_state_inputs") as fetch, \
             redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["--desk", "both", "--format", "json"])
        fetch.assert_not_called()

    def test_one_command_actual_local_git_branch_clone_is_pinned(self):
        with patch("scripts.launch_private_country_desks.REMOTE",
                   str(self.original)):
            dest = self.root / "ephemeral"
            dest.mkdir()
            result = exact_state_inputs(dest, "philippines")
            # The real launcher expects both AFP and NSC; missing NSC is
            # explicitly unavailable, not fabricated or silently skipped.
            self.fail("missing branch must be refused")

