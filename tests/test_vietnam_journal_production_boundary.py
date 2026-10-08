"""Static regression contracts against illicit direct journal activation paths.

This does not claim to find arbitrary dynamic Python imports or prove rights.
It checks the live source manifest, authoritative registry, production desk
manifests and repository GitHub Actions definitions without network or DB I/O.
"""
import copy
import json
import unittest
from pathlib import Path

from scripts.validate_vietnam_journal_production_boundary import (
    JOURNAL_BINDINGS, BoundaryRefused, check_repository, validate_boundary,
)

ROOT = Path(__file__).resolve().parents[1]


def inputs():
    base = ROOT / "shadow" / "vietnam_journal"
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    readiness = json.loads((base / "readiness.v1.json").read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "desks" / "registry.json").read_text(encoding="utf-8"))
    production = {
        p.relative_to(ROOT).as_posix(): json.loads(p.read_text(encoding="utf-8"))
        for p in ROOT.glob("desks/*/manifest.json")
    }
    workflows = {
        p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8")
        for pattern in (".github/workflows/*.yml", ".github/workflows/*.yaml")
        for p in ROOT.glob(pattern)
    }
    return manifest, readiness, registry, production, workflows


class JournalProductionBoundaryTests(unittest.TestCase):
    def test_repository_has_no_direct_journal_activation_paths(self):
        report = check_repository()
        self.assertEqual(report["source_status"], "disabled_research_only")
        self.assertGreaterEqual(report["production_manifests_examined"], 2)
        self.assertGreaterEqual(report["workflows_examined"], 10)
        self.assertEqual(report["direct_workflow_bindings_found"], 0)
        self.assertEqual(report["direct_production_manifest_bindings_found"], 0)
        self.assertTrue(report["static_check_only"])
        for key in (
            "journal_day_zero_started", "authorized_collection",
            "authorized_source_text_retention", "historical_completeness_proven",
        ):
            self.assertFalse(report[key], key)

    def test_registry_must_keep_vietnam_research_without_manifest(self):
        for field, new_value in (
            ("status", "shadow"),
            ("status", "live"),
            ("manifest", "desks/vietnam/manifest.json"),
            ("has_production_records", True),
            ("public", False),
        ):
            args = list(inputs())
            vn = next(x for x in args[2]["desks"] if x["slug"] == "vietnam")
            vn[field] = new_value
            with self.subTest(field=field, new_value=new_value):
                with self.assertRaisesRegex(BoundaryRefused, "research-only"):
                    validate_boundary(*args)

    def test_duplicate_or_missing_vietnam_registry_entry_refused(self):
        for should_duplicate in (True, False):
            args = list(inputs())
            desks = args[2]["desks"]
            entry = next(x for x in desks if x["slug"] == "vietnam")
            if should_duplicate:
                desks.append(copy.deepcopy(entry))
            else:
                desks.remove(entry)
            with self.subTest(duplicate=should_duplicate):
                with self.assertRaisesRegex(BoundaryRefused, "exactly once"):
                    validate_boundary(*args)

    def test_direct_journal_slug_in_production_manifest_refused(self):
        args = list(inputs())
        path = next(iter(args[3]))
        args[3][path]["sources"] = [{"slug": "vn_national_defence_journal_en",
                                     "enabled": False}]
        with self.assertRaisesRegex(BoundaryRefused, "production manifest"):
            validate_boundary(*args)

    def test_production_source_aliases_are_not_safe(self):
        for token in JOURNAL_BINDINGS:
            args = list(inputs())
            key = next(iter(args[3]))
            args[3][key]["added_source_adapter"] = token
            with self.subTest(token=token):
                with self.assertRaisesRegex(BoundaryRefused, "production manifest"):
                    validate_boundary(*args)

    def test_any_manual_or_scheduled_workflow_binding_is_reviewed(self):
        for trigger in ("schedule", "workflow_dispatch", "push"):
            args = list(inputs())
            path = ".github/workflows/proposed_journal.yml"
            args[4][path] = (
                "name: journal probe\non:\n  %s:\n" % trigger
                + "jobs:\n  test:\n    steps:\n      - run: python -m "
                + "scripts.vn_journal_forward_window_audit\n"
            )
            with self.subTest(trigger=trigger):
                with self.assertRaisesRegex(BoundaryRefused, "workflow"):
                    validate_boundary(*args)

    def test_no_host_based_alias_workflow_escape(self):
        for token in ("tapchiqptd.vn", "vn_defence_journal", "vietnam_journal"):
            args = list(inputs())
            args[4][".github/workflows/sneaky.yaml"] = "on: {workflow_dispatch: {}}\n# " + token
            with self.subTest(token=token):
                with self.assertRaisesRegex(BoundaryRefused, "workflow"):
                    validate_boundary(*args)

    def test_missing_workflow_inventory_fails_closed(self):
        args = list(inputs())
        args[4] = {}
        with self.assertRaisesRegex(BoundaryRefused, "definitions absent"):
            validate_boundary(*args)

    def test_missing_production_inventory_fails_closed(self):
        args = list(inputs())
        args[3] = {}
        with self.assertRaisesRegex(BoundaryRefused, "returned no files"):
            validate_boundary(*args)

    def test_original_disabled_manifest_not_silently_altered(self):
        args = list(inputs())
        args[0]["sources"][0]["enabled"] = True
        with self.assertRaises(Exception):
            validate_boundary(*args)
        args = list(inputs())
        args[1]["derived_permissions"]["automatic_collection"] = True
        with self.assertRaises(Exception):
            validate_boundary(*args)

    def test_source_state_is_not_legal_authorization(self):
        report = check_repository()
        self.assertFalse(report["authorized_collection"])
        self.assertFalse(report["authorized_source_text_retention"])
        self.assertFalse(report["historical_completeness_proven"])

    def test_static_reader_never_contacts_publisher_or_production_db(self):
        import inspect
        from scripts import validate_vietnam_journal_production_boundary as script
        body = inspect.getsource(script)
        for forbidden in ("requests.", "urlopen(", "sqlite3", "pla_watch.db",
                          "output/", "write_text(", "subprocess.run("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, body)


if __name__ == "__main__":
    unittest.main()
