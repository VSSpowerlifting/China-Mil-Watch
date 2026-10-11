"""Synthetic-only tests for private snapshot of reviewed first-Sunday TXT."""
import concurrent.futures
import hashlib
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.sunday_private_reviewed_snapshot import (
    SnapshotHold, freeze_exact_reviewed_attachment,
)
from scripts.sunday_first_pilot_reviewed_replay import ReplayRefused
from tests.test_sunday_editor_readable import reviewed_packet


def sha(value):
    return hashlib.sha256(value).hexdigest()


class PrivateReviewedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "downloaded-original.txt"
        self.raw = reviewed_packet().encode("utf-8")
        self.source.write_bytes(self.raw)
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)
        self.digest = sha(self.raw)

    def freeze(self, **changes):
        params = dict(expected_sha256=self.digest)
        params.update(changes)
        return freeze_exact_reviewed_attachment(self.source, self.private, **params)

    def test_exact_snapshot_is_byte_identical_owner_only_readonly(self):
        with patch("scripts.sunday_editorial_handoff.send_packet") as mail, \
             patch("scripts.sunday_briefs_auto_writer.compose") as model:
            result = self.freeze()
        self.assertEqual(result["sha256"], self.digest)
        self.assertEqual(result["bytes"], len(self.raw))
        self.assertEqual(result["path"].read_bytes(), self.raw)
        self.assertEqual(stat.S_IMODE(result["path"].stat().st_mode), 0o400)
        mail.assert_not_called()
        model.assert_not_called()

    def test_changed_input_after_freeze_does_not_change_approved_snapshot(self):
        stored = self.freeze()["path"]
        self.source.write_bytes(b"later accidental rewrite")
        self.assertEqual(stored.read_bytes(), self.raw)

    def test_duplicate_digest_cannot_overwrite_frozen_bytes(self):
        stored = self.freeze()["path"]
        with self.assertRaisesRegex(SnapshotHold, "already stored"):
            self.freeze()
        self.assertEqual(stored.read_bytes(), self.raw)

    def test_bad_digest_fails_before_creating_copy(self):
        with self.assertRaisesRegex(SnapshotHold, "does not match"):
            self.freeze(expected_sha256=sha(b"wrong"))
        self.assertEqual(list(self.private.iterdir()), [])

    def test_missing_or_noncanonical_digest_rejected(self):
        for wrong in ("", "0" * 63, "A" * 64, "not a digest"):
            with self.subTest(wrong=wrong), self.assertRaises(SnapshotHold):
                self.freeze(expected_sha256=wrong)
        self.assertEqual(list(self.private.iterdir()), [])

    def test_wrong_week_never_stored(self):
        with self.assertRaisesRegex(SnapshotHold, "pilot only"):
            self.freeze(week_ending="2026-10-17")
        self.assertEqual(list(self.private.iterdir()), [])

    def test_symlink_input_rejected(self):
        link = self.root / "fake-reviewed.txt"
        link.symlink_to(self.source)
        with self.assertRaises(SnapshotHold):
            freeze_exact_reviewed_attachment(link, self.private, expected_sha256=self.digest)
        self.assertEqual(list(self.private.iterdir()), [])

    def test_symlink_or_world_readable_destination_rejected(self):
        wide = self.root / "world"
        wide.mkdir(mode=0o755)
        with self.assertRaises(SnapshotHold):
            freeze_exact_reviewed_attachment(self.source, wide, expected_sha256=self.digest)
        link = self.root / "alias"
        link.symlink_to(self.private, target_is_directory=True)
        with self.assertRaises(SnapshotHold):
            freeze_exact_reviewed_attachment(self.source, link, expected_sha256=self.digest)
        self.assertEqual(list(self.private.iterdir()), [])

    def test_private_files_cannot_be_stored_inside_public_repository(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=str(repo)) as tmp:
            os.chmod(tmp, 0o700)
            with self.assertRaisesRegex(SnapshotHold, "inside the repository"):
                freeze_exact_reviewed_attachment(
                    self.source, tmp, expected_sha256=self.digest)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_repo_symlinked_parent_to_external_private_store_refused(self):
        import core.sunday_private_reviewed_snapshot as snapshot
        repo = Path(snapshot.__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=str(repo)) as entry:
            os.chmod(entry, 0o700)
            shortcut = Path(entry) / "redirected"
            shortcut.symlink_to(self.root, target_is_directory=True)
            routed = shortcut / "private"
            with self.assertRaisesRegex(SnapshotHold, "inside the repository"):
                freeze_exact_reviewed_attachment(
                    self.source, routed, expected_sha256=self.digest
                )
            self.assertEqual(list(self.private.iterdir()), [])

    def test_non_article_source_does_not_survive_validation(self):
        self.source.write_bytes(b"not a reviewable manuscript")
        with self.assertRaises((ReplayRefused, ValueError)):
            self.freeze(expected_sha256=sha(self.source.read_bytes()))
        self.assertEqual(list(self.private.iterdir()), [])

    def test_preexisting_target_symlink_never_overwritten(self):
        target = self.private / ("IPR-2026-10-10-" + self.digest + ".txt")
        trap = self.root / "do-not-overwrite"
        trap.write_bytes(b"precious")
        target.symlink_to(trap)
        with self.assertRaises(SnapshotHold):
            self.freeze()
        self.assertEqual(trap.read_bytes(), b"precious")
        self.assertTrue(target.is_symlink())

    def test_two_concurrent_freezes_only_one_creates_snapshot(self):
        def one(_):
            try:
                return self.freeze()["path"]
            except SnapshotHold:
                return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(one, range(2)))
        self.assertEqual(sum(v is not None for v in results), 1)
        self.assertEqual([p for p in self.private.iterdir()][0].read_bytes(), self.raw)

    def test_hardlinked_original_refused(self):
        alias = self.root / "linked-original.txt"
        os.link(self.source, alias)
        with self.assertRaises(SnapshotHold):
            self.freeze()
        alias.unlink()
        self.assertEqual(list(self.private.iterdir()), [])

    def test_source_rewrite_is_detected_by_exact_approved_digest(self):
        self.source.write_bytes(self.raw + b"altered after review")
        with self.assertRaises(SnapshotHold):
            self.freeze()
        self.assertEqual(list(self.private.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
