"""Contract tests for read-only China curation *review*, not publication."""
import copy
import unittest

from scripts.audit_china_public_curation import audit, REQUIRED_FIELDS


def fixture():
    return {
        "snapshot": {"date": "2026-10-14", "records": 8},
        "fields": list(REQUIRED_FIELDS),
        "sources": [
            {"code": "pla_daily", "desk": {"code": "china"}},
            {"code": "mod_china", "desk": {"code": "china"}},
            {"code": "sg_mindef_releases", "desk": {"code": "singapore"}},
        ],
        "states": [
            {"code": "analyzed"}, {"code": "not_selected"},
            {"code": "awaiting_screening"}, {"code": "analysis_incomplete"},
        ],
        "trail_ids": [2],
        "records": [
            [1, "2026-05-01", 0, 0, "test", "样本一"],
            [2, "2026-05-02", 0, 1, "", "样本二"],
            [3, "2026-06-01", 0, 0, "test", "样本三"],
            [4, "2026-06-02", 0, 0, "test", "样本四"],
            [5, "2026-05-04", 1, 0, "test", "样本五"],
            [6, "2026-06-03", 1, 0, "test", "样本六"],
            [7, "2026-06-04", 2, 0, "test", "test"],
            [8, "2026-06-05", 0, 2, "", "样本八"],
        ],
    }


class ChinaCurationAuditTest(unittest.TestCase):
    def test_never_promotes_or_removes_stored_records(self):
        source = fixture()
        before = copy.deepcopy(source)
        result = audit(source, target=4)
        self.assertEqual(source, before)
        self.assertEqual(result["china_stored_records"], 7)
        self.assertEqual(result["preserved_corpus_records"], 8)
        self.assertEqual(len(result["rows"]), 7)
        self.assertEqual(result["purpose"], "private_human_review_only")
        self.assertFalse(result["publication_allowlist"])
        self.assertTrue(all(not r["editorially_approved"]
                            for r in result["rows"]))
        self.assertNotIn(7, [r["id"] for r in result["rows"]])

    def test_published_trail_is_protected_despite_screening(self):
        result = audit(fixture(), target=2)
        by_id = {r["id"]: r for r in result["rows"]}
        self.assertEqual(by_id[2]["review_status"], "protected_trail_review")
        self.assertEqual(result["protected_china_trail_records"], 1)
        self.assertEqual(result["review_sample_count"], 2)
        self.assertEqual(by_id[8]["review_status"], "processing_not_complete")

    def test_sample_is_stable_and_spans_sources(self):
        first = audit(fixture(), target=5)
        self.assertEqual(first, audit(fixture(), target=5))
        self.assertIn("pla_daily", first["review_sample_by_source"])
        self.assertIn("mod_china", first["review_sample_by_source"])

    def test_protected_records_are_not_lost_to_target_limit(self):
        source = fixture()
        source["trail_ids"] = [1, 2, 3]
        result = audit(source, target=1)
        self.assertEqual(result["review_sample_count"], 3)
        self.assertEqual(result["protected_china_trail_records"], 3)

    def test_missing_protection_and_bad_index_fail_closed(self):
        source = fixture()
        del source["trail_ids"]
        with self.assertRaises(ValueError):
            audit(source)
        source = fixture()
        source["trail_ids"] = [999]
        with self.assertRaises(ValueError):
            audit(source)
        source = fixture()
        source["records"].append(list(source["records"][0]))
        with self.assertRaises(ValueError):
            audit(source)
        source = fixture()
        source["fields"] = ["id"]
        with self.assertRaises(ValueError):
            audit(source)
        source = fixture()
        with self.assertRaises(ValueError):
            audit(source, target=0)


if __name__ == "__main__":
    unittest.main()
