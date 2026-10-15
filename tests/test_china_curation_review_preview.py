"""Private China curation preview must never publish or discard old records."""
from pathlib import Path
import copy
import tempfile
import unittest

from scripts.preview_china_curation_review import preview, write_preview
from tests.test_china_curation_review_ledger import index, ledger


class CurationPrivatePreviewTest(unittest.TestCase):
    def test_readable_two_view_preview_preserves_all_ids_and_provenance(self):
        source, docket = index(), ledger()
        before_source, before_docket = copy.deepcopy(source), copy.deepcopy(docket)
        pages, report = preview(source, docket)
        self.assertEqual(source, before_source)
        self.assertEqual(docket, before_docket)
        self.assertEqual(set(pages), {"index.html", "preserved.html"})
        self.assertEqual(report["owner_approved"], 0)
        self.assertEqual(report["china_unreviewed_preserved"], 3)
        for html in pages.values():
            self.assertIn('name="robots" content="noindex,nofollow,noarchive"', html)
            self.assertIn("Not a published archive or editorial endorsement.", html)
            self.assertIn("https://indopacificrecord.org/record/11.html", html)
            self.assertIn("preserved.html", html)
            self.assertIn("index.html", html)
            self.assertNotIn("<script src=", html)
            self.assertNotIn("<link rel='stylesheet'", html)
            self.assertNotIn("sitemap.xml", html)
        self.assertEqual(pages["index.html"].count("class='record'"), 1)
        self.assertEqual(pages["preserved.html"].count("class='record'"), 5)
        for ident in (11, 12, 13, 14, 15):
            self.assertEqual(pages["preserved.html"].count(
                "https://indopacificrecord.org/record/%d.html" % ident), 1)
        self.assertNotIn("https://indopacificrecord.org/record/15.html",
                         pages["index.html"])

    def test_escaping_does_not_allow_stored_titles_or_notes_to_inject_tags(self):
        source, docket = index(), ledger()
        source["records"][0][5] = 'Malicious <script>alert("x")</script> title'
        docket["decisions"][0]["source_title"] = source["records"][0][5]
        docket["decisions"][0]["rationale"] = "Potential relevance <script>alert(1)</script> requires verification."
        pages, _ = preview(source, docket)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", pages["index.html"])
        self.assertNotIn("<script>alert", pages["index.html"])

    def test_all_newly_collected_records_appear_only_in_preserved_view(self):
        source, docket = index(), ledger()
        source["snapshot"] = {"date": "2026-10-15", "records": 6}
        source["records"].append([16, "2026-10-15", 0, 1, "", "新来的资料"])
        pages, report = preview(source, docket)
        self.assertEqual(report["china_unreviewed_preserved"], 4)
        self.assertEqual(pages["preserved.html"].count("class='record'"), 6)
        self.assertNotIn("record/16.html", pages["index.html"])
        self.assertIn("record/16.html", pages["preserved.html"])

    def test_missing_trail_or_invented_approval_refuses_before_file_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "not-created"
            source, docket = index(), ledger()
            docket["publication_enabled"] = True
            with self.assertRaisesRegex(ValueError, "publication-disabled"):
                pages, _ = preview(source, docket)
                write_preview(target, pages)
            self.assertFalse(target.exists())
            source, docket = index(), ledger()
            source["trail_ids"] = [999]
            with self.assertRaisesRegex(ValueError, "unknown published"):
                pages, _ = preview(source, docket)
                write_preview(target, pages)
            self.assertFalse(target.exists())

    def test_output_is_new_private_directory_and_not_repo(self):
        pages, _ = preview(index(), ledger())
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "private-prototype"
            result = write_preview(target, pages)
            self.assertEqual(result, target)
            self.assertEqual(sorted(x.name for x in target.iterdir()),
                             ["index.html", "preserved.html"])
            self.assertIn("noindex", (result / "index.html").read_text())
            with self.assertRaisesRegex(ValueError, "new external directory"):
                write_preview(target, pages)
            with self.assertRaisesRegex(ValueError, "absolute output directory"):
                write_preview(Path("relative-preview"), pages)
            with self.assertRaisesRegex(ValueError, "new external directory"):
                write_preview(
                    Path(__file__).resolve().parents[1] / "output" / "fake-preview",
                    pages)
            link = Path(tmp) / "symlink"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "new external directory"):
                write_preview(link / "subdir", pages)

    def test_html_is_stable_and_statuses_separate(self):
        p1, _ = preview(index(), ledger())
        p2, _ = preview(index(), ledger())
        self.assertEqual(p1, p2)
        self.assertIn("not selected", p1["index.html"].lower())
        self.assertIn("Unsigned China review docket", p1["index.html"])


if __name__ == "__main__":
    unittest.main()
