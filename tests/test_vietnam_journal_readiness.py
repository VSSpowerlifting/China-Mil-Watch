"""Freeze the unresolved rights/activation gates of the Vietnam journal.

Synthetic mutations prove the current research-only ledger and source manifest
cannot diverge silently. No network, production DB or generated output.
"""
import copy
import json
import unittest
from pathlib import Path

from scripts.validate_vietnam_journal_readiness import (
    DENIED_ACTIONS, EVIDENCE, GATES, ReadinessRefused,
    check_repository, validate_research_hold,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "shadow" / "vietnam_journal"


def inputs():
    return (json.loads((BASE / "manifest.json").read_text(encoding="utf-8")),
            json.loads((BASE / "readiness.v1.json").read_text(encoding="utf-8")))


class JournalReadinessHoldTests(unittest.TestCase):
    def test_actual_repo_is_disabled_and_all_actions_denied(self):
        result = check_repository()
        self.assertEqual(result["status"], "research_disabled")
        self.assertFalse(result["historical_completeness_proven"])
        self.assertFalse(result["day_zero_started"])
        _, ledger = inputs()
        self.assertEqual(set(ledger["derived_permissions"]), set(DENIED_ACTIONS))
        self.assertTrue(all(v is False for v in ledger["derived_permissions"].values()))

    def test_bounded_proofs_are_not_promoted_to_full_archive(self):
        _, ledger = inputs()
        self.assertEqual(ledger["gates"], GATES)
        self.assertEqual(ledger["evidence"], EVIDENCE)
        self.assertIn("unproven", ledger["gates"]["historical_enumeration"])
        self.assertIn("not_started", ledger["gates"]["forward_listing_reliability"])

    def test_rejects_activation_of_source_or_desk(self):
        for field in ("source", "desk"):
            manifest, ledger = inputs()
            if field == "source":
                manifest["sources"][0]["enabled"] = True
            else:
                manifest["desk"]["active"] = True
            with self.subTest(field=field), self.assertRaises(ReadinessRefused):
                validate_research_hold(manifest, ledger)

    def test_rejects_forged_rights_or_activation_boolean(self):
        for action in DENIED_ACTIONS:
            manifest, ledger = inputs()
            ledger["derived_permissions"][action] = True
            with self.subTest(action=action), self.assertRaisesRegex(ReadinessRefused, "cannot authorize"):
                validate_research_hold(manifest, ledger)

    def test_rejects_rights_claim_not_supported_by_owner_decision(self):
        for name, replacement in (
            ("metadata_retention_rights", "approved"),
            ("full_text_retention_rights", "approved"),
            ("public_republication_rights", "approved"),
            ("owner_shadow_activation", "authorized"),
            ("owner_production_promotion", "authorized"),
            ("historical_enumeration", "proven"),
            ("four_category_discovery", "historically_complete"),
        ):
            manifest, ledger = inputs()
            ledger["gates"][name] = replacement
            with self.subTest(gate=name), self.assertRaisesRegex(ReadinessRefused, "gate changed"):
                validate_research_hold(manifest, ledger)

    def test_cannot_forge_success_or_missing_issue_evidence(self):
        manifest, ledger = inputs()
        ledger["evidence"]["source_use_decision"] = "https://example.com/permission-granted"
        with self.assertRaisesRegex(ReadinessRefused, "references changed"):
            validate_research_hold(manifest, ledger)
        manifest, ledger = inputs()
        del ledger["evidence"]["historical_investigation"]
        with self.assertRaises(ReadinessRefused):
            validate_research_hold(manifest, ledger)

    def test_rejects_spurious_fields_or_omitted_rights_scopes(self):
        manifest, ledger = inputs()
        ledger["publisher_html"] = "publisher text must never enter policy"
        with self.assertRaises(ReadinessRefused):
            validate_research_hold(manifest, ledger)
        manifest, ledger = inputs()
        del ledger["derived_permissions"]["public_full_text"]
        with self.assertRaisesRegex(ReadinessRefused, "missing or unexpected"):
            validate_research_hold(manifest, ledger)

    def test_refuses_wrong_source_publisher_type_and_duplicate_feed(self):
        for key, value in (
            ("authority_tier", "A"),
            ("source_type", "ministry_statement"),
            ("institution_id", "vn_ministry_of_defence"),
            ("language_tag", "vi"),
        ):
            manifest, ledger = inputs()
            manifest["sources"][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ReadinessRefused, "misclassified"):
                validate_research_hold(manifest, ledger)
        manifest, ledger = inputs()
        manifest["sources"].append(copy.deepcopy(manifest["sources"][0]))
        with self.assertRaisesRegex(ReadinessRefused, "one journal source"):
            validate_research_hold(manifest, ledger)

    def test_rejects_missing_copyright_reservation(self):
        manifest, ledger = inputs()
        manifest["rights"] = "Public website, therefore no publisher conditions"
        with self.assertRaisesRegex(ReadinessRefused, "hold was weakened"):
            validate_research_hold(manifest, ledger)

    def test_no_network_db_or_site_code_is_needed(self):
        import inspect
        from scripts import validate_vietnam_journal_readiness
        source = inspect.getsource(validate_vietnam_journal_readiness)
        for token in ("requests.", "urllib.request", "sqlite3", "urlopen(", "write_text(", "import site.render"):
            with self.subTest(token=token):
                self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
