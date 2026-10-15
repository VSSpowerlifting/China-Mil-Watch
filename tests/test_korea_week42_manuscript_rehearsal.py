"""No-send, actual-source-bound Korean Week-42 manuscript rehearsal tests."""
import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from core.korea_private_research_candidates import (
    ROOT, KoreaResearchHold, load,
)
from scripts import rehearse_korea_week42_manuscript as draft

ROWS = load(week_ending="2026-10-17", as_of="2026-10-17")


class KoreaWeek42ManuscriptTests(unittest.TestCase):
    def test_three_real_authored_sources_and_exact_citations(self):
        rendered = draft.compose(ROWS)
        receipt = draft.check_exact(ROWS, rendered)
        self.assertEqual(receipt["citation_count"], 3)
        self.assertTrue(receipt["source_attribution_contract_passed"])
        for field in ("human_review_authenticated", "publisher_originals_loaded",
                      "model_called", "email_sent", "sunday_admission_authorized",
                      "source_rights_approved",
                      "production_or_publication_authorized"):
            self.assertIs(receipt[field], False)
        for num, row in enumerate(ROWS, 1):
            self.assertEqual(rendered.count("[^K%d]" % num), 2)
            self.assertEqual(rendered.count(row["summary"]), 1)
            self.assertEqual(rendered.count(row["source_url"]), 1)
        self.assertIn("2026-10-09", rendered)
        self.assertIn("2026-10-12", rendered)
        self.assertIn("156785161", rendered)
        self.assertIn("October 12 scheduled collector failed", rendered)

    def test_source_changes_duplication_reordering_or_new_claims_rejected(self):
        for kind in ("reorder", "remove", "new_source", "new_claim",
                     "rights_permission", "source_hash", "date_change"):
            rows = copy.deepcopy(ROWS)
            if kind == "reorder":
                rows.reverse()
            elif kind == "remove":
                rows.pop()
            elif kind == "new_source":
                rows[1]["source_id"] = "KR-MND-W42-99"
            elif kind == "new_claim":
                rows[1]["summary"] += " A signed deal was finalized."
            elif kind == "rights_permission":
                rows[0]["status"] = "approved-for-sunday"
            elif kind == "source_hash":
                rows[1]["source_content_sha256"] = "f" * 64
            else:
                rows[1]["published_date"] = "2026-10-08"
            with self.subTest(kind=kind), self.assertRaises(KoreaResearchHold):
                draft.compose(rows)

    def test_injected_manuscript_is_not_accepted_as_matching_renderer(self):
        original = draft.compose(ROWS)
        tampering = (
            original.replace(ROWS[0]["summary"], ROWS[0]["summary"] +
                             " Four additional hubs are already open.", 1),
            original.replace(ROWS[1]["source_url"], "https://example.invalid", 1),
            original.replace("[^K2]", "[^K1]", 1),
            original.replace("NOT APPROVED", "APPROVED", 1),
            original.replace("October 12 scheduled collector failed",
                             "October 12 was a clean scheduled run", 1),
        )
        for item in tampering:
            with self.assertRaises(KoreaResearchHold):
                draft.check_exact(ROWS, item)

    def test_create_check_private_0600_outside_repo_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "private-korea-manuscript.md"
            with redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(draft.main([
                    "--create", str(p), "--explicit-local-no-send"]), 0)
            receipt = json.loads(stdout.getvalue())
            self.assertEqual(receipt["citation_count"], 3)
            self.assertNotIn(str(p), stdout.getvalue())
            self.assertNotIn(ROWS[0]["summary"], stdout.getvalue())
            if os.name == "posix":
                self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            with redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(draft.main([
                    "--check", str(p), "--explicit-local-no-send"]), 0)
            self.assertEqual(json.loads(stdout.getvalue()), receipt)
            with self.assertRaises(KoreaResearchHold):
                draft.main(["--create", str(p), "--explicit-local-no-send"])
            p.write_text(p.read_text() + "\nUnauthorized assertion", encoding="utf-8")
            with self.assertRaises(KoreaResearchHold):
                draft.check_local_file(str(p), rows=ROWS)

    def test_relative_repo_path_symlink_and_unapproved_cli_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "draft.md"
            with self.assertRaises(SystemExit):
                draft.main(["--create", str(p)])
            self.assertFalse(p.exists())
            draft.main(["--create", str(p), "--explicit-local-no-send"])
            link = Path(tmp) / "symlink.md"
            link.symlink_to(p)
            with self.assertRaises(KoreaResearchHold):
                draft.check_local_file(str(link), rows=ROWS)
            with self.assertRaises(KoreaResearchHold):
                draft.check_local_file("relative.md", rows=ROWS)
            with self.assertRaises(KoreaResearchHold):
                draft.check_local_file(str(ROOT / "output" / "draft.md"), rows=ROWS)
            if os.name == "posix":
                p.chmod(0o644)
                with self.assertRaises(KoreaResearchHold):
                    draft.check_local_file(str(p), rows=ROWS)

    def test_no_original_source_binary_or_sunday_editor_io_dependencies(self):
        source = (ROOT / "scripts" / "rehearse_korea_week42_manuscript.py")
        code = source.read_text(encoding="utf-8")
        for forbidden in ("import anthropic", "import smtplib", "requests.get",
                          "urllib.request", "send_message(", "site.render(",
                          "shadow.db", "pla_watch.db"):
            self.assertNotIn(forbidden, code)
        receipt = draft.check_exact(ROWS, draft.compose(ROWS))
        self.assertFalse(receipt["sunday_admission_authorized"])


if __name__ == "__main__":
    unittest.main()
