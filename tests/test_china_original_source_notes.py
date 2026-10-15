"""Offline test cases for preliminary China original-source research receipts."""
import copy
import unittest

from scripts.audit_china_original_source_notes import validate_packet


def fixture():
    index = {
        "snapshot": {"date": "2026-10-14", "records": 3},
        "fields": ["id", "date", "source", "state", "title_en", "title_orig"],
        "sources": [
            {"code": "pla_daily", "desk": {"code": "china"}},
            {"code": "sg_mindef_releases", "desk": {"code": "singapore"}},
        ],
        "states": [{"code": "not_selected"}],
        "trail_ids": [11],
        "records": [
            [11, "2026-07-31", 0, 0, "", "黄岩岛外交部声明"],
            [12, "2026-07-31", 1, 0, "Singapore source", ""],
            [13, "2026-07-31", 0, 0, "", "海军原始记录"],
        ],
    }
    packet = {
        "version": 1,
        "purpose": "assistant_research_preliminary_not_editorial_signoff",
        "publication_enabled": False,
        "owner_approved": False,
        "baseline_snapshot": copy.deepcopy(index["snapshot"]),
        "checks": [{
            "id": 11,
            "source": "pla_daily", "published_date": "2026-07-31",
            "title": "黄岩岛外交部声明",
            "captured_url": "http://www.81.cn/yw_208727/16477077.html",
            "research_url": "https://www.fmprc.gov.cn/official-original",
            "research_kind": "issuer_publication",
            "comparison": "apparent_substantive_match",
            "research_date": "2026-10-15",
            "issuer_attribution": "Chinese Ministry of Foreign Affairs",
            "source_observation": "Publisher title and stored diplomatic text align in this research spot check, without any verified external factual claims.",
            "stored_body_anchor": "外交部关于菲律宾的声明",
            "next_step": "candidate_original_review",
            "human_original_review_required": True,
            "owner_approved": False,
        }],
    }
    pages = {11: (
        "<html><div class='stuff'>unrelated</div>"
        "<div class='original-text'><p>外交部关于菲律宾的声明 正文的一部分。</p></div>"
        "<table><tr><th scope=\"row\">Original URL</th><td class=\"prov-value\">"
        "<a href=\"http://www.81.cn/yw_208727/16477077.html\">original</a>"
        "</td></tr></table></html>"
    )}
    return packet, index, pages


class ChinaOriginalResearchTest(unittest.TestCase):
    def test_structural_publisher_research_never_becomes_editorial_approval(self):
        packet, index, pages = fixture()
        before = copy.deepcopy((packet, index, pages))
        summary = validate_packet(packet, index, pages)
        self.assertEqual((packet, index, pages), before)
        self.assertEqual(summary["research_cases"], 1)
        self.assertFalse(summary["publication_enabled"])
        self.assertFalse(summary["owner_approved"])
        self.assertTrue(summary["requires_human_verification"])
        self.assertEqual(summary["historical_corpus_records_untouched"], 3)

    def test_never_allow_editorial_approval_or_release(self):
        for field in ("owner_approved", "publication_enabled"):
            packet, index, pages = fixture()
            packet[field] = True
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "non-publishing"):
                validate_packet(packet, index, pages)
        packet, index, pages = fixture()
        packet["checks"][0]["owner_approved"] = True
        with self.assertRaisesRegex(ValueError, "editor/owner approval"):
            validate_packet(packet, index, pages)
        packet, index, pages = fixture()
        packet["checks"][0]["human_original_review_required"] = False
        with self.assertRaisesRegex(ValueError, "editor/owner approval"):
            validate_packet(packet, index, pages)

    def test_identity_and_trail_protection_fail_closed(self):
        packet, index, pages = fixture()
        packet["checks"][0]["title"] = "Other article"
        with self.assertRaisesRegex(ValueError, "drift"):
            validate_packet(packet, index, pages)
        packet, index, pages = fixture()
        packet["checks"][0]["source"] = "sg_mindef_releases"
        with self.assertRaisesRegex(ValueError, "drift"):
            validate_packet(packet, index, pages)
        packet, index, pages = fixture()
        packet["checks"][0]["id"] = 12
        with self.assertRaisesRegex(ValueError, "non-China"):
            validate_packet(packet, index, pages)
        packet, index, pages = fixture()
        index["trail_ids"] = [999]
        with self.assertRaisesRegex(ValueError, "trail"):
            validate_packet(packet, index, pages)
        packet, index, pages = fixture()
        index["snapshot"]["records"] = 4
        with self.assertRaisesRegex(ValueError, "exact dated"):
            validate_packet(packet, index, pages)

    def test_bound_to_capture_body_and_actual_original_url(self):
        packet, index, pages = fixture()
        packet["checks"][0]["captured_url"] = "http://example.org/not-the-record"
        with self.assertRaisesRegex(ValueError, "stored source URL"):
            validate_packet(packet, index, pages)
        packet, index, pages = fixture()
        packet["checks"][0]["stored_body_anchor"] = "a sentence not in source"
        with self.assertRaisesRegex(ValueError, "anchor changed"):
            validate_packet(packet, index, pages)
        packet, index, pages = fixture()
        pages[11] = "<html><p>no original text</p></html>"
        with self.assertRaisesRegex(ValueError, "original-text"):
            validate_packet(packet, index, pages)

    def test_uncertain_original_cannot_pretend_confirmation(self):
        packet, index, pages = fixture()
        check = packet["checks"][0]
        check["research_kind"] = "source_not_independently_checked"
        with self.assertRaisesRegex(ValueError, "explicitly unknown"):
            validate_packet(packet, index, pages)
        check["research_url"] = None
        check["comparison"] = "original_not_checked"
        result = validate_packet(packet, index, pages)
        self.assertEqual(result["source_outcomes"]["original_not_checked"], 1)
        check["research_url"] = "https://publisher.example/unverified"
        with self.assertRaisesRegex(ValueError, "explicitly unknown"):
            validate_packet(packet, index, pages)

    def test_contamination_is_held_not_selected(self):
        packet, index, pages = fixture()
        check = packet["checks"][0]
        check["comparison"] = "historical_text_contamination"
        with self.assertRaisesRegex(ValueError, "remain held"):
            validate_packet(packet, index, pages)
        check["next_step"] = "quality_hold"
        self.assertEqual(validate_packet(packet, index, pages)["research_cases"], 1)

    def test_absent_body_has_null_anchor_and_requires_true_absence(self):
        packet, index, pages = fixture()
        c = packet["checks"][0]
        c["comparison"] = "historical_body_absent"
        c["next_step"] = "quality_hold"
        c["stored_body_anchor"] = None
        original = pages[11]
        with self.assertRaisesRegex(ValueError, "original text now present"):
            validate_packet(packet, index, pages)
        pages[11] = original[original.index("<table>"):]
        self.assertEqual(validate_packet(packet, index, pages)["research_cases"], 1)
        c["stored_body_anchor"] = "fabricated words"
        with self.assertRaisesRegex(ValueError, "null anchor"):
            validate_packet(packet, index, pages)
        c["stored_body_anchor"] = None
        c["next_step"] = "candidate_original_review"
        with self.assertRaisesRegex(ValueError, "remain held"):
            validate_packet(packet, index, pages)
        c["next_step"] = "quality_hold"
        pages[11] = "<html><p>no source, no provenance</p></html>"
        with self.assertRaisesRegex(ValueError, "provenance URL missing"):
            validate_packet(packet, index, pages)

    def test_evidence_url_requires_https_but_historical_captured_url_may_be_http(self):
        packet, index, pages = fixture()
        packet["checks"][0]["research_url"] = "http://www.fmprc.gov.cn/a"
        with self.assertRaisesRegex(ValueError, "unambiguous publisher URL"):
            validate_packet(packet, index, pages)
        packet, index, pages = fixture()
        packet["checks"][0]["research_url"] = "https://attacker:pass@example.org/source"
        with self.assertRaisesRegex(ValueError, "unambiguous publisher URL"):
            validate_packet(packet, index, pages)

    def test_duplicates_and_unknown_record_pages_fail(self):
        packet, index, pages = fixture()
        packet["checks"].append(copy.deepcopy(packet["checks"][0]))
        with self.assertRaisesRegex(ValueError, "repeated"):
            validate_packet(packet, index, pages)
        packet, index, pages = fixture()
        del pages[11]
        with self.assertRaisesRegex(ValueError, "page is missing"):
            validate_packet(packet, index, pages)


if __name__ == "__main__":
    unittest.main()
