"""Canonical-record safety checks for the bounded No. 14 migration."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import correct_no14 as migration


class No14CorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for path in migration.BASE_SHA256:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((Path(__file__).parent / "fixtures/no14-original" / path).read_bytes())

    def test_preparation_preserves_canonical_files_and_source_provenance(self):
        original, proposed = migration.prepare(self.root, "2026-10-03")
        old = json.loads(original[migration.SIDECAR])
        new = json.loads(proposed[migration.SIDECAR])
        for path, content in original.items():
            self.assertEqual((self.root / path).read_bytes(), content)
        changed_fields = {key for key in set(old) | set(new) if old.get(key) != new.get(key)}
        self.assertEqual(changed_fields, {
            "dek", "signal", "opening_note", "what_stood_out", "why_it_matters",
            "what_was_routine", "term_to_know_explanation", "what_im_watching_next",
            "sources_seen", "source_trail",
        })
        trail = copy.deepcopy(old["source_trail"])
        trail[6]["title"] = trail[6]["title"].replace(" (Lái)", "")
        self.assertEqual(new["source_trail"], trail)
        self.assertEqual(len(new["sources_seen"]), 4)
        self.assertLessEqual(len(new["signal"].split()), 28)

    def test_stale_companion_refuses_before_any_canonical_write(self):
        sidecar = (self.root / migration.SIDECAR).read_bytes()
        (self.root / migration.LINKEDIN).write_text("Another editor's change\n")
        with self.assertRaisesRegex(ValueError, "re-review"):
            migration.prepare(self.root, "2026-10-03")
        self.assertEqual((self.root / migration.SIDECAR).read_bytes(), sidecar)

    def test_invalid_correction_date_refuses(self):
        with self.assertRaises(ValueError):
            migration.prepare(self.root, "2026-02-30")

    def test_change_between_preparation_and_apply_is_preserved(self):
        originals, proposed = migration.prepare(self.root, "2026-10-03")
        (self.root / migration.LINKEDIN).write_text("New edit\n")
        with self.assertRaisesRegex(ValueError, "during preparation"):
            migration.apply(self.root, originals, proposed)
        self.assertEqual((self.root / migration.SIDECAR).read_bytes(), originals[migration.SIDECAR])
        self.assertEqual((self.root / migration.LINKEDIN).read_text(), "New edit\n")

    def test_failed_second_replacement_restores_first_file(self):
        originals, proposed = migration.prepare(self.root, "2026-10-03")
        actual_replace = migration.os.replace
        count = [0]

        def fail_second(source, target):
            count[0] += 1
            if count[0] == 2:
                raise OSError("Simulated second-file failure")
            return actual_replace(source, target)

        with patch.object(migration.os, "replace", side_effect=fail_second):
            with self.assertRaises(OSError):
                migration.apply(self.root, originals, proposed)
        for path, content in originals.items():
            self.assertEqual((self.root / path).read_bytes(), content)
        self.assertEqual(list(self.root.rglob(".no14-*")), [])

    def test_apply_changes_only_the_two_reviewed_files(self):
        originals, proposed = migration.prepare(self.root, "2026-10-03")
        unrelated = self.root / "unrelated.txt"
        unrelated.write_text("Preserve me\n")
        migration.apply(self.root, originals, proposed)
        for path, content in proposed.items():
            self.assertEqual((self.root / path).read_bytes(), content)
        self.assertEqual(unrelated.read_text(), "Preserve me\n")
        with self.assertRaisesRegex(ValueError, "re-review"):
            migration.prepare(self.root, "2026-10-03")


if __name__ == "__main__":
    unittest.main()
