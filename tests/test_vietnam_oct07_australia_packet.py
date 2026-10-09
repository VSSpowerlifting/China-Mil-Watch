"""October 7 MPS record: source-pinned, unapproved private Sunday material."""
import json
import unittest
from pathlib import Path
from core.brief_editorial_evidence import load_editorial_evidence

ROOT = Path(__file__).resolve().parents[1]
WEEK = "2026-10-10"
ID = "VN-MPS-1791366010"
CONTENT_SHA = "8707eaee31b0423d8b6835fee0d02a25207c2a8e5813718aa57c434c927fd6b5"
STATE = "c7c13dc7c15d855412afff99db23695dd50e51a5"


class NewMPSResearchTests(unittest.TestCase):
    def test_new_current_week_source_is_version_pinned_but_never_approved(self):
        packet = json.loads((ROOT / "research/briefs_editorial_evidence" /
                             (WEEK + ".json")).read_text())
        notes = json.loads((ROOT / "research/vietnam_briefs_candidates" /
                            "editorial_notes_2026-10-10.json").read_text())
        rows = load_editorial_evidence(WEEK, WEEK)
        self.assertEqual(len(rows), 6)
        self.assertEqual(sum(x["desk"] == "japan" for x in rows), 3)
        self.assertEqual(sum(x["desk"] == "vietnam" for x in rows), 3)
        new = next(x for x in rows if x["id"] == ID)
        note = next(x for x in notes["entries"]
                    if x["source_identity"] == "mps-vi:1791366010")
        self.assertEqual(new["source_content_sha256"], CONTENT_SHA)
        self.assertEqual(new["state_commit"], STATE)
        self.assertEqual(new["published_date"], "2026-10-07")
        self.assertEqual(new["source_kind"], "shadow-extracted-original")
        self.assertEqual(new["hash_rule"], "mps-vi-content-v1")
        for key in ("source_url", "published_date", "summary", "caveats", "topics"):
            self.assertEqual(new[key], note[key])
        self.assertEqual(new["source_content_sha256"], note["content_sha256"])
        self.assertIn("australia", new["source_url"])
        self.assertEqual(new["status"],
                         "unapproved-source-linked-editorial-candidate")
        self.assertEqual(new["copy_scope"],
                         "private-model-drafting-only-no-source-body")
        self.assertNotIn("text_original", new)
        self.assertNotIn("article_body", new)
        self.assertNotIn("human_review", new)
        self.assertNotIn("rights_approval", new)
        self.assertEqual(len(notes["entries"]), 3)
        self.assertEqual(len({x["source_identity"] for x in notes["entries"]}), 3)

    def test_no_fake_new_agreement_in_short_source_summary(self):
        notes = json.loads((ROOT / "research/vietnam_briefs_candidates" /
                            "editorial_notes_2026-10-10.json").read_text())
        text = next(x for x in notes["entries"]
                    if x["source_identity"] == "mps-vi:1791366010")
        self.assertIn("stated cooperation agenda", text["summary"])
        self.assertIn("not evidence of completed implementation", text["summary"])
        self.assertTrue(any("not establish new signed" in x for x in text["caveats"]))
        self.assertEqual(text["topics"],
                         ["regional_partnerships", "technology_cooperation"])


if __name__ == "__main__":
    unittest.main()
