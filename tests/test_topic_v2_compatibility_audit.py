"""Contract tests: v1 labels cannot be silently promoted into taxonomy v2."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_topic_v2_compatibility import (  # noqa: E402
    CompatibilityError,
    V1_GIT_BLOB,
    V1_PATH,
    V2_PATH,
    audit,
    audit_files,
    blob_sha,
    render_markdown,
)


class VocabularyCompatibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v1 = json.loads(V1_PATH.read_text(encoding="utf-8"))
        cls.v2 = json.loads(V2_PATH.read_text(encoding="utf-8"))

    def fixture(self):
        return copy.deepcopy(self.v1), copy.deepcopy(self.v2)

    def run_audit(self, v1, v2, pin=V1_GIT_BLOB):
        return audit(
            v1, v2, v1_pin=pin, v2_pin="synthetic-v2-blob"
        )

    def test_real_file_diff_is_pinned_and_nonallocative(self):
        report = audit_files()
        self.assertEqual(report["versions"], [1, 2])
        self.assertEqual(report["summary"]["v1_topics"], 19)
        self.assertEqual(report["summary"]["v2_topics"], 20)
        self.assertEqual(report["summary"]["modified_legacy_definitions"], 11)
        self.assertEqual(report["summary"]["identical_legacy_definitions"], 8)
        self.assertEqual(report["summary"]["new_topics"], 1)
        self.assertEqual(report["summary"]["automatic_assignment_promotions"], 0)
        self.assertEqual(report["pins"]["v1"]["git_blob_sha"], V1_GIT_BLOB)
        self.assertEqual(len(report["changes"]), 20)
        self.assertTrue(all(not row["automatic_record_promotion"]
                            for row in report["changes"]))

    def test_display_rename_is_distinct_from_slug_rename(self):
        report = audit_files()
        record = next(
            r for r in report["changes"]
            if r["slug"] == "critical_minerals_supply_chains"
        )
        self.assertEqual(
            record["changed_fields"],
            ["display_name", "description", "scope_note"],
        )
        self.assertEqual(
            record["v2"]["display_name"],
            "Strategic Materials & Supply-Chain Resilience",
        )
        self.assertTrue(record["requires_scope_review"])

    def test_new_hadr_is_not_an_automatic_assignment(self):
        report = audit_files()
        row = next(r for r in report["changes"]
                   if r["slug"] == "military_hadr")
        self.assertIsNone(row["v1"])
        self.assertEqual(row["change"], "new_topic")
        self.assertEqual(row["v2"]["group"], "operations")
        self.assertTrue(row["requires_scope_review"])
        self.assertFalse(row["automatic_record_promotion"])

    def test_unchanged_topics_have_identical_definitions_but_no_promotion(self):
        report = audit_files()
        unchanged = [x for x in report["changes"]
                     if x["change"] == "unchanged"]
        self.assertEqual(len(unchanged), 8)
        self.assertTrue(all(x["v1"] == x["v2"] for x in unchanged))
        self.assertTrue(all(not x["requires_scope_review"] for x in unchanged))
        self.assertTrue(all(not x["automatic_record_promotion"]
                            for x in unchanged))

    def test_machine_and_human_formats_do_not_call_changes_approved(self):
        report = audit_files()
        result = render_markdown(report)
        self.assertIn("Not a migration", result)
        self.assertIn("modified old definitions: 11", result)
        self.assertIn("no definition change", result)
        self.assertIn("separately", result)
        self.assertNotIn("All records migrated", result)
        json.dumps(report, ensure_ascii=False)

    def test_bad_v1_blob_is_refused(self):
        a, b = self.fixture()
        with self.assertRaisesRegex(CompatibilityError,
                                    "v1 reference blob changed"):
            self.run_audit(a, b, pin="0" * 40)

    def test_actual_v1_file_edit_is_refused_by_blob_pin(self):
        with tempfile.TemporaryDirectory() as folder:
            altered = Path(folder) / "v1.json"
            altered.write_text(
                V1_PATH.read_text(encoding="utf-8") + " ",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CompatibilityError,
                                        "v1 reference blob changed"):
                audit_files(altered, V2_PATH)

    def test_v1_and_v2_misnumbering_is_refused(self):
        a, b = self.fixture()
        a["taxonomy_version"] = 2
        with self.assertRaisesRegex(CompatibilityError,
                                    "requested taxonomy version"):
            self.run_audit(a, b)
        a, b = self.fixture()
        b["taxonomy_version"] = 1
        with self.assertRaisesRegex(CompatibilityError,
                                    "requested taxonomy version"):
            self.run_audit(a, b)

    def test_unexpected_new_topic_is_refused(self):
        a, b = self.fixture()
        b["topics"][-1]["slug"] = "invented_topic"
        # Last item is doctrine_strategy, not HADR in the current ordering.
        with self.assertRaisesRegex(CompatibilityError,
                                    "deleted or renamed legacy topic"):
            self.run_audit(a, b)
        a, b = self.fixture()
        for row in b["topics"]:
            if row["slug"] == "military_hadr":
                row["slug"] = "invented_topic"
        with self.assertRaisesRegex(CompatibilityError,
                                    "reviewed HADR addition"):
            self.run_audit(a, b)

    def test_deleted_v1_topic_is_refused(self):
        a, b = self.fixture()
        b["topics"] = [
            x for x in b["topics"] if x["slug"] != "south_china_sea"
        ]
        with self.assertRaisesRegex(CompatibilityError,
                                    "unexpected topic count"):
            self.run_audit(a, b)

    def test_group_change_is_refused_even_if_slug_remains(self):
        a, b = self.fixture()
        b["groups"][0]["description"] = "altered group"
        with self.assertRaisesRegex(CompatibilityError,
                                    "group metadata changed"):
            self.run_audit(a, b)
        a, b = self.fixture()
        for row in b["topics"]:
            if row["slug"] == "military_hadr":
                row["group"] = "geoeconomics"
        with self.assertRaisesRegex(CompatibilityError,
                                    "HADR group"):
            self.run_audit(a, b)

    def test_silent_new_scope_change_is_refused(self):
        a, b = self.fixture()
        for row in b["topics"]:
            if row["slug"] == "maritime_security":
                row["scope_note"] += " New unapproved condition."
        with self.assertRaisesRegex(CompatibilityError,
                                    "unreviewed v2 definition changes"):
            self.run_audit(a, b)

    def test_silent_change_within_already_modified_legacy_scope_is_described(self):
        a, b = self.fixture()
        old = next(x for x in b["topics"]
                   if x["slug"] == "force_posture_basing")
        old["scope_note"] = "Different proposed scope -- subject to review."
        report = self.run_audit(a, b)
        row = next(x for x in report["changes"]
                   if x["slug"] == "force_posture_basing")
        self.assertEqual(row["v2"]["scope_note"], old["scope_note"])
        self.assertTrue(row["requires_scope_review"])

    def test_unexpected_schema_and_duplicate_slug_are_refused(self):
        a, b = self.fixture()
        b["topics"][0]["unapproved"] = "unexpected"
        with self.assertRaisesRegex(CompatibilityError,
                                    "unexpected topic fields"):
            self.run_audit(a, b)
        a, b = self.fixture()
        b["topics"][0]["slug"] = b["topics"][1]["slug"]
        with self.assertRaisesRegex(CompatibilityError,
                                    "invalid or duplicate topic slug"):
            self.run_audit(a, b)

    def test_no_record_access_required(self):
        report = audit_files()
        self.assertTrue(report["safety"]["old_assignments_stay_on_v1"])
        self.assertTrue(report["safety"]["no_human_approval_implied"])
        self.assertIn("record_topics", report["safety"]["no_promotion_rule"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
