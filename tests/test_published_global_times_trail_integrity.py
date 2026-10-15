"""Published Brief source-trail custody and historical capture review tests."""
import copy
import json
from pathlib import Path
import unittest

from scripts.audit_published_global_times_trail_integrity import (
    audit, CASES, RECORDS, ISSUES,
)

# Frozen October 14 evidence (5,230 records, 5,144 China records).
# Live output/corpus-index.json advances with daily collection and is not
# the source of truth for exact 2026-10-14 historical audit assertions.
INDEX = Path(__file__).resolve().parent / "fixtures/china-corpus-index-2026-10-14.json"


def actual():
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    packet = json.loads(CASES.read_text(encoding="utf-8"))
    pages = {}
    issues = {}
    for c in packet["checks"]:
        ident, day = c["id"], c["issue_date"]
        pages[ident] = (RECORDS / ("%d.html" % ident)).read_text(encoding="utf-8")
        issues[day] = json.loads(
            (ISSUES / (day + ".json")).read_text(encoding="utf-8"))
    return index, packet, pages, issues


class PublishedTrailRiskTest(unittest.TestCase):
    def test_exact_real_published_trails_are_preserved_and_uncorrected(self):
        args = actual()
        frozen = copy.deepcopy(args)
        result = audit(*args)
        self.assertEqual(args, frozen)
        self.assertEqual(result["published_global_times_trails_reviewed"], 13)
        self.assertEqual(result["issues_affected"], [2, 10, 12, 13, 14])
        self.assertEqual(result["attention_counts"], {
            "already_caveated_in_issue": 3,
            "claim_level_review": 8,
            "machine_summary_conflict": 1,
            "published_claim_source_mismatch": 1,
        })
        self.assertEqual(result["stored_snippet_warning_count_not_proven_defects"], 13)
        self.assertEqual(result["historical_record_count"], 5230)
        self.assertFalse(result["publication_enabled"])
        self.assertFalse(result["owner_approved"])
        self.assertTrue(all(not x["brief_inaccuracy_established"]
                            and not x["correction_authorized"]
                            for x in result["cases"]))
        self.assertTrue(all(len(x["stored_body_sha256"]) == 64
                            for x in result["cases"]))
        self.assertEqual(len(set(x["publisher_url"] for x in result["cases"])), 13)

    def test_source_trail_claim_cannot_be_promoted_into_signoff(self):
        for field in ("publication_enabled", "owner_approved"):
            index, packet, pages, issues = actual()
            packet[field] = True
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "publication"):
                audit(index, packet, pages, issues)
        index, packet, pages, issues = actual()
        packet["checks"][0]["reviewer"] = "Automated model"
        with self.assertRaisesRegex(ValueError, "editor review or approval"):
            audit(index, packet, pages, issues)
        index, packet, pages, issues = actual()
        packet["checks"][0]["original_publisher_content_checked"] = True
        with self.assertRaisesRegex(ValueError, "editor review or approval"):
            audit(index, packet, pages, issues)

    def test_original_publisher_url_and_citation_must_still_match(self):
        index, packet, pages, issues = actual()
        packet["checks"][0]["expected_original_url"] += "?altered=1"
        with self.assertRaisesRegex(ValueError, "source URL changed"):
            audit(index, packet, pages, issues)
        index, packet, pages, issues = actual()
        case = packet["checks"][0]
        issues[case["issue_date"]]["source_trail"] = []
        with self.assertRaisesRegex(ValueError, "cited source URL missing"):
            audit(index, packet, pages, issues)
        index, packet, pages, issues = actual()
        index["trail_ids"].remove(packet["checks"][0]["id"])
        with self.assertRaisesRegex(ValueError, "published China Global Times trail"):
            audit(index, packet, pages, issues)

    def test_record_identity_and_corpus_custody_must_not_drift(self):
        index, packet, pages, issues = actual()
        packet["checks"][0]["original_source_date"] = "2026-09-01"
        with self.assertRaisesRegex(ValueError, "title/date drift"):
            audit(index, packet, pages, issues)
        index, packet, pages, issues = actual()
        index["snapshot"]["records"] -= 1
        with self.assertRaisesRegex(ValueError, "corpus moved backwards"):
            audit(index, packet, pages, issues)
        index, packet, pages, issues = actual()
        index["trail_ids"] = index["trail_ids"] + [99999999]
        with self.assertRaisesRegex(ValueError, "count or source trail"):
            audit(index, packet, pages, issues)

    def test_issue14_disclosure_is_an_explicit_existing_editorial_fact(self):
        index, packet, pages, issues = actual()
        issue = issues["2026-08-15"]
        issue["opening_note"] = "No warning about incomplete source text."
        with self.assertRaisesRegex(ValueError, "correction/caveat"):
            audit(index, packet, pages, issues)
        index, packet, pages, issues = actual()
        issue = issues["2026-08-15"]
        issue["issue_number"] = 999
        with self.assertRaisesRegex(ValueError, "identity/date drift"):
            audit(index, packet, pages, issues)

    def test_record2265_wrong_year_is_source_machine_summary_not_brief_proof(self):
        index, packet, pages, issues = actual()
        result = audit(index, packet, pages, issues)
        case = next(c for c in result["cases"] if c["id"] == 2265)
        self.assertEqual(case["editorial_attention"], "machine_summary_conflict")
        self.assertFalse(case["brief_inaccuracy_established"])
        self.assertFalse(case["correction_authorized"])
        pages[2265] = pages[2265].replace("Joint Sea-2025 naval exercise",
                                          "Joint Sea-2026 naval exercise")
        with self.assertRaisesRegex(ValueError, "machine summary conflict"):
            audit(index, packet, pages, issues)

    def test_specific_no12_atlas_vs_kvd002_claim_requires_review(self):
        index, packet, pages, issues = actual()
        case = next(c for c in packet["checks"] if c["id"] == 2881)
        self.assertEqual(case["editorial_attention"],
                         "published_claim_source_mismatch")
        result = audit(index, packet, pages, issues)
        self.assertFalse(next(x for x in result["cases"] if x["id"] == 2881)[
            "brief_inaccuracy_established"])
        issues["2026-08-01"]["opening_note"] = (
            issues["2026-08-01"]["opening_note"].replace(
                "Atlas drone swarm", "KVD002 armed reconnaissance"))
        with self.assertRaisesRegex(ValueError, "Atlas/KVD002 issue claim"):
            audit(index, packet, pages, issues)

    def test_forward_daily_collection_does_not_fabricate_new_approvals(self):
        index, packet, pages, issues = actual()
        index["snapshot"] = {"date": "2026-10-15", "records": 5231}
        new_id = max(row[0] for row in index["records"]) + 1
        index["records"].append([new_id, "2026-10-15", 0, 0, "", "新收集未审资料"])
        result = audit(index, packet, pages, issues)
        self.assertEqual(result["historical_record_count"], 5231)
        self.assertEqual(result["published_global_times_trails_reviewed"], 13)
        self.assertFalse(result["publication_enabled"])
        self.assertFalse(result["owner_approved"])

    def test_missing_record_page_or_source_provenance_fails(self):
        index, packet, pages, issues = actual()
        del pages[241]
        with self.assertRaisesRegex(ValueError, "record or published issue"):
            audit(index, packet, pages, issues)
        index, packet, pages, issues = actual()
        pages[241] = pages[241].replace("Original URL", "Modified URL")
        with self.assertRaisesRegex(ValueError, "missing original URL"):
            audit(index, packet, pages, issues)


if __name__ == "__main__":
    unittest.main()
