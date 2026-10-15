"""China archival editorial decisions: custody and fail-closed validation."""
import copy
import unittest

from scripts.validate_china_curation_review import validate_ledger


def index():
    return {
        "snapshot": {"date": "2026-10-14", "records": 5},
        "fields": ["id", "date", "source", "state", "title_en", "title_orig"],
        "sources": [
            {"code": "pla_daily", "desk": {"code": "china"}},
            {"code": "global_times_mil", "desk": {"code": "china"}},
            {"code": "sg_mindef_releases", "desk": {"code": "singapore"}},
        ],
        "states": [{"code": "analyzed"}, {"code": "not_selected"}],
        "trail_ids": [11],
        "records": [
            [11, "2026-07-01", 0, 1, "", "南海外交部声明"],
            [12, "2026-07-02", 1, 0, "Naval live-fire training", ""],
            [13, "2026-07-02", 1, 0, "Naval live-fire training", ""],
            [14, "2026-07-03", 0, 1, "", "日常部队报道"],
            [15, "2026-07-03", 2, 0, "Singapore announcement", ""],
        ],
    }


def decision(id=11, source="pla_daily", title="南海外交部声明",
             published_date="2026-07-01", disposition="retain_primary"):
    return {
        "id": id, "source": source, "published_date": published_date,
        "source_title": title, "review_stage": "triage",
        "disposition": disposition,
        "rationale": "An evidence-related review lead, not a human approval.",
        "evidence": [{
            "kind": "stored_record",
            "url": "https://indopacificrecord.org/record/%d.html" % id,
        }],
        "source_check": None, "owner_approval": None, "representative_id": None,
    }


def ledger():
    return {
        "version": 1, "scope": "china",
        "purpose": "internal_editorial_review", "publication_enabled": False,
        "baseline_snapshot": {"date": "2026-10-14", "records": 5},
        "decisions": [decision()],
    }


def checked(d):
    d["review_stage"] = "source_checked"
    d["evidence"].append({
        "kind": "publisher_original",
        "url": "https://example.org/official/original",
    })
    d["source_check"] = {
        "checked_by": "Human reviewer",
        "checked_on": "2026-10-15",
        "capture_quality": "complete",
        "issuer": "Official issuing institution",
        "verification_note": "Compared the stored title and text to the named original.",
    }
    return d


class CurationLedgerTest(unittest.TestCase):
    def test_triage_never_publishes_and_protected_records_remain_preserved(self):
        data, review = index(), ledger()
        original_data, original_review = copy.deepcopy(data), copy.deepcopy(review)
        result = validate_ledger(data, review)
        self.assertEqual(data, original_data)
        self.assertEqual(review, original_review)
        self.assertEqual(result["china_preserved"], 4)
        self.assertEqual(result["china_unreviewed_preserved"], 3)
        self.assertEqual(result["brief_trail_records_with_review_dockets"], 1)
        self.assertEqual(result["approved_primary_or_context_candidates"], 0)
        self.assertFalse(result["publication_enabled"])

    def test_daily_new_records_do_not_erase_or_auto_decide_old_rows(self):
        data = index()
        data["snapshot"] = {"date": "2026-10-15", "records": 6}
        data["records"].append([16, "2026-10-15", 0, 0, "", "新收集的报道"])
        result = validate_ledger(data, ledger())
        self.assertTrue(result["snapshot_advanced"])
        self.assertEqual(result["china_unreviewed_preserved"], 4)

    def test_title_source_date_and_scope_are_identity_bound(self):
        review = ledger()
        review["decisions"][0]["source_title"] = "Incorrect original"
        with self.assertRaisesRegex(ValueError, "drift"):
            validate_ledger(index(), review)
        review = ledger()
        review["decisions"][0]["source"] = "global_times_mil"
        with self.assertRaisesRegex(ValueError, "drift"):
            validate_ledger(index(), review)
        review = ledger()
        review["decisions"] = [decision(15, "sg_mindef_releases",
                                         "Singapore announcement", "2026-07-03")]
        with self.assertRaisesRegex(ValueError, "non-China"):
            validate_ledger(index(), review)

    def test_never_enabled_or_implicit_editorial_approval(self):
        review = ledger()
        review["publication_enabled"] = True
        with self.assertRaisesRegex(ValueError, "publication-disabled"):
            validate_ledger(index(), review)
        review = ledger()
        review["decisions"][0]["review_stage"] = "owner_approved"
        with self.assertRaisesRegex(ValueError, "complete review receipt"):
            validate_ledger(index(), review)

    def test_source_checked_requires_distinct_evidence_and_receipt(self):
        review = ledger()
        checked(review["decisions"][0])
        self.assertEqual(validate_ledger(index(), review)["source_checked"], 1)
        review["decisions"][0]["evidence"] = [
            review["decisions"][0]["evidence"][0]]
        with self.assertRaisesRegex(ValueError, "stored record"):
            validate_ledger(index(), review)

    def test_approved_requires_separate_owner_receipt_not_authentication(self):
        review = ledger()
        d = checked(review["decisions"][0])
        d["review_stage"] = "owner_approved"
        with self.assertRaisesRegex(ValueError, "owner approval"):
            validate_ledger(index(), review)
        d["owner_approval"] = {
            "approved_by": "Editorial owner", "approved_on": "2026-10-15"}
        result = validate_ledger(index(), review)
        self.assertEqual(result["owner_approved"], 1)
        self.assertEqual(result["approved_primary_or_context_candidates"], 1)
        self.assertFalse(result["publication_enabled"])

    def test_holds_and_contaminated_text_cannot_be_approved(self):
        review = ledger()
        d = checked(review["decisions"][0])
        d["review_stage"] = "owner_approved"
        d["owner_approval"] = {
            "approved_by": "Editorial owner", "approved_on": "2026-10-15"}
        d["disposition"] = "hold_quality"
        with self.assertRaisesRegex(ValueError, "quality holds"):
            validate_ledger(index(), review)
        d["disposition"] = "retain_primary"
        d["source_check"]["capture_quality"] = "contaminated"
        with self.assertRaisesRegex(ValueError, "contaminated text"):
            validate_ledger(index(), review)

    def test_secondary_needs_reviewed_retained_representative(self):
        review = ledger()
        d = decision(12, "global_times_mil", "Naval live-fire training",
                     "2026-07-02", "group_secondary")
        d["representative_id"] = 13
        review["decisions"].append(d)
        with self.assertRaisesRegex(ValueError, "reviewed retained representative"):
            validate_ledger(index(), review)
        review["decisions"].append(decision(
            13, "global_times_mil", "Naval live-fire training",
            "2026-07-02", "retain_context"))
        self.assertEqual(validate_ledger(index(), review)["china_with_review_dockets"], 3)

    def test_missing_trail_unknown_schema_and_duplicate_ids_fail(self):
        data = index()
        del data["trail_ids"]
        with self.assertRaisesRegex(ValueError, "trail IDs"):
            validate_ledger(data, ledger())
        review = ledger()
        review["decisions"].append(copy.deepcopy(review["decisions"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_ledger(index(), review)
        review = ledger()
        review["decisions"][0]["invented_field"] = "yes"
        with self.assertRaisesRegex(ValueError, "unrecognized"):
            validate_ledger(index(), review)

    def test_older_or_smaller_index_never_pretends_to_be_current(self):
        data = index()
        data["snapshot"] = {"date": "2026-10-13", "records": 5}
        with self.assertRaisesRegex(ValueError, "older/smaller"):
            validate_ledger(data, ledger())


if __name__ == "__main__":
    unittest.main()
