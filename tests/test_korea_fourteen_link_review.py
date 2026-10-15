"""Korea 14-link private review stage, without site or source material."""
import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from core.korea_reference_gate import ROOT, KoreaGateHold
from scripts import preview_korea_fourteen_official_links as review


class KoreaFourteenLinkReviewTests(unittest.TestCase):
    def setUp(self):
        self.original = json.loads(review.MANIFEST.read_text(encoding="utf-8"))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / "korea-private-review.md"

    def test_all_fourteen_exact_source_pairs_and_nine_new_held(self):
        rows, live = review.validate()
        self.assertEqual(len(rows), 14)
        self.assertEqual(len(live), 5)
        self.assertEqual(len([r for r in rows if r["status"].startswith("hold_")]), 9)
        self.assertEqual(len({r["source_url"] for r in rows}), 14)
        self.assertEqual(len([r for r in rows if r["editorial_exception"]]), 1)
        self.assertEqual(rows[11]["news_id"], "156785161")
        self.assertTrue(all(r["source_url"].startswith(
            "https://www.korea.kr/briefing/pressReleaseView.do?newsId=")
            for r in rows))

    def test_private_preview_created_without_originals_or_unapproved_titles(self):
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(review.main([
                "--private-preview-out", str(self.out),
                "--explicit-no-publish"]), 0)
        receipt = json.loads(output.getvalue())
        self.assertEqual(receipt["source_count"], 14)
        self.assertEqual(receipt["held_new_links"], 9)
        self.assertEqual(receipt["authorized_new_links"], 0)
        self.assertFalse(receipt["source_body_read"])
        self.assertFalse(receipt["published"])
        self.assertFalse(receipt["production_admitted"])
        body = self.out.read_text(encoding="utf-8")
        self.assertEqual(body.count("Official URL: "), 14)
        self.assertEqual(body.count("HELD — no new public link permission"), 9)
        self.assertEqual(body.count("EXISTING PUBLIC LINK"), 5)
        self.assertIn("contradictory excavation year (#601)", body)
        self.assertNotIn("d1b8c4d21f97c9a33da1602ec9433487c591e49e442f3b4a5960410bda145be4", body)
        self.assertNotIn("original Korean HWPX SHA", body)
        self.assertNotIn(str(self.out), output.getvalue())
        if os.name == "posix":
            self.assertEqual(self.out.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(KoreaGateHold):
            review.create(self.out)

    def test_new_source_cannot_be_promoted_by_flipping_json_flag(self):
        malicious = (
            ("owner_approval_for_new_public_links", True),
            ("eligible_new_public_links", 9),
            ("mode", "public_approved"),
            ("reviewer_attestation_authenticated", True),
            ("state_commit", "f" * 40),
        )
        for field, changed in malicious:
            data = copy.deepcopy(self.original)
            data[field] = changed
            self.reject(data)

    def reject(self, data):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "modified.json"
            p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with patch.object(review, "MANIFEST", p):
                with self.assertRaises(KoreaGateHold):
                    review.validate()

    def test_unknown_or_replaced_sources_and_license_identity_rejected(self):
        for field, changed in (
                ("news_id", "156999999"),
                ("source_url", "https://example.invalid/forged"),
                ("hwpx_capture_sha256", "f" * 64),
                ("publisher_html_capture_sha256", "f" * 64),
                ("status", "approved-for-release"),
                ("editorial_exception", None),
                ("extra", "unapproved original text")):
            data = copy.deepcopy(self.original)
            row = data["entries"][11]  # the held disputed source
            row[field] = changed
            with self.subTest(field=field):
                self.reject(data)
        data = copy.deepcopy(self.original)
        data["entries"].append(copy.deepcopy(data["entries"][0]))
        self.reject(data)
        data = copy.deepcopy(self.original)
        data["entries"].pop()
        self.reject(data)

    def test_unapproved_or_unsafe_output_locations(self):
        with self.assertRaises(KoreaGateHold):
            review.create("relative-private-preview.md")
        with self.assertRaises(KoreaGateHold):
            review.create(ROOT / "output" / "korea-public-archive.md")
        with self.assertRaises(SystemExit):
            review.main(["--private-preview-out", str(self.out)])
        self.assertFalse(self.out.exists())
        self.out.symlink_to(review.MANIFEST)
        with self.assertRaises(KoreaGateHold):
            review.create(self.out)

    def test_existing_public_five_and_release_controls_remain_frozen(self):
        root = ROOT
        from core.korea_public_bibliography import load_public_korea_links
        self.assertEqual(len(load_public_korea_links()), 5)
        workflow = (root / ".github/workflows/korea_public_bibliography_release.yml").read_text()
        self.assertIn("assert len(load_public_korea_links()) == 5", workflow)
        self.assertIn('k["status"] == "shadow"', workflow)
        # A changed held-review manifest must re-run PR checks, but must
        # NOT independently trigger the live Pages push release.
        pull_trigger, push_and_jobs = workflow.split("  push:", 1)
        push_trigger = push_and_jobs.split("permissions:", 1)[0]
        self.assertIn(
            '"research/korea/MND_14_PUBLIC_LINK_REVIEW_CANDIDATES_2026-10-15.json"',
            pull_trigger)
        self.assertNotIn("MND_14_PUBLIC_LINK_REVIEW_CANDIDATES",
                         push_trigger)
        self.assertIn(
            '"research/korea_additional_public_official_links_2026-10-15.json"',
            push_trigger)
        source = (root / "scripts/preview_korea_fourteen_official_links.py").read_text()
        for forbidden in ("git push", "smtplib", "anthropic", "urllib.request",
                          "requests.get", "site.render", "pla_watch.db"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
