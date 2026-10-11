"""No-network functional tests for one-command local private research desks."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.launch_private_country_desks import (
    ReaderHold, create, exact_state_inputs, main,
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
        cases = [
            ("ph_afp_articles", "shadow/ph-afp", "Philippine maritime briefing",
             "https://www.afp.mil.ph/news/sample", "afp:994"),
            ("ph_nsc_official_statements", "shadow/ph-nsc", "Official maritime statement",
             "https://nsc.gov.ph/2026/10/11/example/", "ph-nsc:994"),
            ("vn_mps_foreign_affairs_vi", "shadow/vietnam-mps-foreign-affairs",
             "Hội nghị giao lưu", "https://bocongan.gov.vn/tin/1", "vn-mps:994"),
            ("vn_moit_energy_vi", "shadow/vietnam-moit-energy",
             "Bảo đảm an ninh năng lượng", "https://moit.gov.vn/tin/1", "vn-moit-energy:994"),
            ("vn_moit_foundational_industry_vi",
             "shadow/vietnam-moit-foundational-industry",
             "Công nghiệp Việt Nam", "https://moit.gov.vn/tin/2", "vn-moit-foundation:994"),
        ]
        self.commits = {}
        for slug, branch, title, url, ident in cases:
            commit = state_commit(self.original, slug, title=title, url=url,
                                  identity=ident,
                                  content="MARITIME PRIVATE BODY MUST NOT EXPORT")
            git(self.original, "branch", branch, commit)
            self.commits[slug] = commit

    def tearDown(self):
        self.temp.cleanup()

    def test_explicit_optin_blocks_network_before_any_fetch(self):
        with patch("scripts.launch_private_country_desks.exact_state_inputs") as fetch, \
             redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["--desk", "both", "--format", "json"])
        fetch.assert_not_called()

    def test_one_command_real_local_git_fetches_exact_snapshots(self):
        with patch("scripts.launch_private_country_desks.REMOTE", str(self.original)):
            repo = self.root / "ephemeral"
            repo.mkdir()
            observed = exact_state_inputs(repo, "philippines")
            self.assertEqual(len(observed), 2)
            self.assertEqual([x.split(",")[2] for x in observed],
                             [self.commits["ph_afp_articles"],
                              self.commits["ph_nsc_official_statements"]])
            for x in observed:
                self.assertTrue(x.split(",")[1].startswith(str(self.root)))
            self.assertFalse((self.original / "output").exists())

    def test_actual_private_browser_from_all_five_offline_git_refs(self):
        dest = self.root / "real-use-private-desks.html"
        with patch("scripts.launch_private_country_desks.REMOTE", str(self.original)):
            receipt = create("both", output=str(dest), query="maritime",
                             limit=20, fmt="html")
        self.assertEqual(receipt["source_families"], 5)
        self.assertEqual(receipt["matched_total"], 5)
        self.assertTrue(receipt["metadata_only"])
        self.assertTrue(receipt["no_publisher_requests"])
        self.assertFalse(receipt["production_activated"])
        page = dest.read_text(encoding="utf-8")
        self.assertIn("Country desk reader", page)
        self.assertIn("Armed Forces of the Philippines", page)
        self.assertIn("Ministry of Public Security", page)
        self.assertIn("PUBLIC REVIEW PENDING", page)
        self.assertNotIn("MARITIME PRIVATE BODY MUST NOT EXPORT", page)
        self.assertNotIn("<html", json.dumps(receipt))
        self.assertFalse((self.original / "state" / "shadow.db").exists())

    def test_json_mode_body_queries_and_source_evidence_no_body(self):
        with patch("scripts.launch_private_country_desks.REMOTE", str(self.original)):
            report = create("vietnam", query="PRIVATE BODY", fmt="json")
        self.assertEqual(report["matched_total"], 3)
        self.assertEqual({x["source_slug"] for x in report["results"]},
                         {"vn_mps_foreign_affairs_vi", "vn_moit_energy_vi",
                          "vn_moit_foundational_industry_vi"})
        self.assertNotIn("MARITIME PRIVATE BODY MUST NOT EXPORT", json.dumps(report))
        self.assertFalse(report["public_release_authorized"])

    def test_output_cannot_replace_existing_private_file(self):
        dest = self.root / "existing-report.html"
        dest.write_text("existing")
        with patch("scripts.launch_private_country_desks.REMOTE", str(self.original)):
            with self.assertRaisesRegex(ReaderHold, "unsafe destination"):
                create("philippines", output=str(dest))
        self.assertEqual(dest.read_text(), "existing")

    def test_missing_source_branch_must_be_blocked(self):
        git(self.original, "branch", "-D", "shadow/ph-nsc")
        with patch("scripts.launch_private_country_desks.REMOTE", str(self.original)):
            with self.assertRaisesRegex(ReaderHold, "unavailable"):
                create("philippines", fmt="json")

    def test_runner_cli_with_local_test_remote_only(self):
        dest = self.root / "cli.html"
        buf = io.StringIO()
        with patch("scripts.launch_private_country_desks.REMOTE", str(self.original)), \
             redirect_stdout(buf):
            rc = main(["--desk", "philippines", "--format", "html",
                       "--approve-github-shadow-fetch", "--output", str(dest)])
        self.assertEqual(rc, 0)
        parsed = json.loads(buf.getvalue())
        self.assertEqual(parsed["source_families"], 2)
        self.assertEqual(parsed["matched_total"], 2)
        self.assertTrue(dest.is_file())
        self.assertNotIn("MARITIME PRIVATE BODY", dest.read_text())


if __name__ == "__main__":
    unittest.main()
