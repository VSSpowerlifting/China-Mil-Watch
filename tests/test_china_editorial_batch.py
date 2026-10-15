"""Review-only China 25-record batch: custody, original URLs and no publish."""
import copy
from pathlib import Path
import tempfile
import unittest

from scripts.prepare_china_editorial_batch import (
    private_html, record_custody, validate_batch, write_private,
)


def fixture():
    index = {
        "snapshot": {"date": "2026-10-14", "records": 26},
        "fields": ["id", "date", "source", "state", "title_en", "title_orig"],
        "sources": [
            {"code": "pla_daily", "desk": {"code": "china"}},
            {"code": "sg_mindef_releases", "desk": {"code": "singapore"}},
        ],
        "states": [{"code": "analyzed"}, {"code": "not_selected"}],
        "trail_ids": [1],
        "records": [
            [i, "2026-08-%02d" % i, 0, i % 2, "", "军事档案%d" % i]
            for i in range(1, 26)
        ] + [[26, "2026-08-26", 1, 0, "Singapore release", ""]],
    }
    items = []
    for i in range(1, 26):
        items.append({
            "id": i, "source": "pla_daily",
            "published_date": "2026-08-%02d" % i,
            "source_title": "军事档案%d" % i,
            "review_lane": "screened_out_primary_source",
            "review_question": "Verify the primary article against its original publisher and independently assess the issuer and title %d." % i,
            "compare_ids": [2] if i == 1 else [1] if i == 2 else [],
            "editorial_decision": None, "reviewer": None, "reviewed_on": None,
        })
    batch = {
        "version": 1, "scope": "china",
        "purpose": "diagnostic_editorial_intake_not_selection",
        "publication_enabled": False, "owner_approved": False,
        "baseline_snapshot": copy.deepcopy(index["snapshot"]),
        "batch_id": "china-2026-10-15-01",
        "created_on": "2026-10-15", "entries": items,
    }
    def html(i, text="Original captured words from the source."):
        return (
            '<div class="original-text"><p>' + text
            + '</p></div><table><tr><th scope="row">Original URL</th>'
            '<td class="prov-value"><a href="https://publisher.example/%d">source</a></td></tr>'
            '<tr><th scope="row">Collected at</th>'
            '<td class="prov-value">2026-08-%02d 14:30:00 '
            '<span>collection metadata only</span></td></tr></table>'
        ) % (i, i)
    pages = {i: html(i) for i in range(1, 26)}
    return index, batch, pages


class ChinaReviewBatchTest(unittest.TestCase):
    def test_custody_and_deterministic_private_packet(self):
        index, batch, pages = fixture()
        old = copy.deepcopy((index, batch, pages))
        report = validate_batch(index, batch, pages)
        self.assertEqual(old, (index, batch, pages))
        self.assertEqual(report["batch_records"], 25)
        self.assertEqual(report["preserved_records"], 26)
        self.assertEqual(report["protected_brief_trail"], 1)
        self.assertFalse(report["publication_enabled"])
        self.assertFalse(report["owner_approved"])
        self.assertEqual(report["source_review_status"], "all_pending")
        self.assertTrue(all(e["editorial_decision"] is None for e in report["entries"]))
        html = private_html(report)
        self.assertEqual(html, private_html(validate_batch(index, batch, pages)))
        self.assertIn("PRIVATE DRAFT. NOT A SELECTION OR PUBLICATION.", html)
        self.assertIn("noindex,nofollow,noarchive", html)
        self.assertIn("record/1.html", html)
        self.assertIn("record/25.html", html)
        self.assertNotIn("record/26.html", html)
        self.assertEqual(html.count("class='case'"), 25)
        self.assertNotIn("<script", html)

    def test_missing_body_is_not_mutated_or_marked_unimportant(self):
        index, batch, pages = fixture()
        pages[3] = pages[3].replace(
            '<div class="original-text"><p>Original captured words from the source.</p></div>',
            "")
        report = validate_batch(index, batch, pages)
        missing = next(e for e in report["entries"] if e["id"] == 3)
        self.assertEqual(missing["stored_text_status"], "no_readable_original_text_block")
        self.assertEqual(missing["stored_characters"], 0)
        self.assertIsNone(missing["editorial_decision"])
        self.assertEqual(missing["human_original_review"], "pending")
        self.assertTrue(missing["original_url"].startswith("https://publisher.example"))

    def test_reject_any_review_decision_or_owner_publishing_flag(self):
        for field, value in (
            ("publication_enabled", True), ("owner_approved", True),
            ("purpose", "approved_for_publication"),
        ):
            index, batch, pages = fixture()
            batch[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "publication approval"):
                validate_batch(index, batch, pages)
        for field, value in (
            ("editorial_decision", "retain_primary"),
            ("reviewer", "Editor"), ("reviewed_on", "2026-10-15"),
        ):
            index, batch, pages = fixture()
            batch["entries"][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "reviewer or approval"):
                validate_batch(index, batch, pages)

    def test_corpus_identity_and_brief_citations_are_not_optional(self):
        index, batch, pages = fixture()
        index["trail_ids"] = [999]
        with self.assertRaisesRegex(ValueError, "source-trail ID"):
            validate_batch(index, batch, pages)
        index, batch, pages = fixture()
        batch["entries"][0]["source_title"] = "unrelated record"
        with self.assertRaisesRegex(ValueError, "identity drift"):
            validate_batch(index, batch, pages)
        index, batch, pages = fixture()
        index["snapshot"]["records"] = 27
        with self.assertRaisesRegex(ValueError, "snapshot drift"):
            validate_batch(index, batch, pages)
        index, batch, pages = fixture()
        batch["entries"][0]["id"] = 26
        with self.assertRaisesRegex(ValueError, "non-China"):
            validate_batch(index, batch, pages)
        index, batch, pages = fixture()
        batch["entries"][0]["compare_ids"] = [26]
        with self.assertRaisesRegex(ValueError, "same batch"):
            validate_batch(index, batch, pages)

    def test_reject_unilateral_comparison_and_missing_record_html(self):
        index, batch, pages = fixture()
        batch["entries"][1]["compare_ids"] = []
        with self.assertRaisesRegex(ValueError, "reciprocal"):
            validate_batch(index, batch, pages)
        index, batch, pages = fixture()
        del pages[3]
        with self.assertRaisesRegex(ValueError, "missing preserved record HTML"):
            validate_batch(index, batch, pages)
        index, batch, pages = fixture()
        pages[3] = pages[3].replace('Original URL', 'Deleted source')
        with self.assertRaisesRegex(ValueError, "provenance"):
            validate_batch(index, batch, pages)

    def test_private_html_escapes_dangerous_stored_titles_and_notes(self):
        index, batch, pages = fixture()
        malicious = "军事<script>malicious</script>档案"
        index["records"][0][5] = malicious
        batch["entries"][0]["source_title"] = malicious
        batch["entries"][0]["review_question"] += " Example <script>alert(1)</script>."
        result = private_html(validate_batch(index, batch, pages))
        self.assertIn("&lt;script&gt;malicious&lt;/script&gt;", result)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", result)
        self.assertNotIn("<script>malicious", result)

    def test_render_only_to_fresh_external_restricted_directory(self):
        report = validate_batch(*fixture())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "new-packet"
            result = write_private(out, report)
            self.assertEqual(result, out)
            self.assertEqual(sorted(p.name for p in out.iterdir()),
                             ["review.html", "summary.json"])
            self.assertIn("noindex", (out / "review.html").read_text())
            with self.assertRaisesRegex(ValueError, "fresh external"):
                write_private(out, report)
            with self.assertRaisesRegex(ValueError, "absolute"):
                write_private(Path("relative_packet"), report)
            with self.assertRaisesRegex(ValueError, "fresh external"):
                write_private(
                    Path(__file__).resolve().parents[1] / "output" / "private-review",
                    report)
            alias = Path(tmp) / "link"
            alias.symlink_to(out, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "fresh external"):
                write_private(alias / "another", report)

    def test_bad_outlet_url_and_ambiguous_body_fail_closed(self):
        index, batch, pages = fixture()
        pages[1] = pages[1].replace("https://publisher.example/1",
                                   "https://name:secret@publisher.example/1")
        with self.assertRaisesRegex(ValueError, "publisher URL"):
            validate_batch(index, batch, pages)
        index, batch, pages = fixture()
        pages[1] += '<div class="original-text"><p>Another source body</p></div>'
        with self.assertRaisesRegex(ValueError, "ambiguous captured"):
            validate_batch(index, batch, pages)


if __name__ == "__main__":
    unittest.main()
