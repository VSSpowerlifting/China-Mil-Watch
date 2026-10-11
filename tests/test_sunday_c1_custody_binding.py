"""C1 fictional custody binding: no real recipient, transport, model or corpus."""
import concurrent.futures
import hashlib
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.sunday_c1_custody_binding import (
    FictionalCustodyHold, bind_fictional_reviewed_snapshot,
)
from core.sunday_delivery_journal import DeliveryHold, DeliveryJournal
from core.sunday_delivery_replay_rehearsal import source_use_fingerprint
from core.sunday_private_reviewed_snapshot import SnapshotHold
from scripts.sunday_first_pilot_reviewed_replay import inspect_file
from scripts.sunday_pilot_owner_review import OwnerReviewRequired
from tests.test_sunday_editor_readable import reviewed_packet


def digest(value):
    return hashlib.sha256(value).hexdigest()


class C1FictionalBindingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.original = reviewed_packet().encode("utf-8")
        self.source = self.folder / "fictional-owner-reviewed.txt"
        self.source.write_bytes(self.original)
        self.source.chmod(0o600)
        self.private = self.folder / "private"
        self.private.mkdir(mode=0o700)
        self.journal_path = self.folder / "fictional-journal.sqlite"
        self.journal = DeliveryJournal(self.journal_path, initialize_new=True)
        self.params = {
            "week": "2026-10-10",
            "approved_week": "2026-10-10",
            "reviewed_sha256": digest(self.original),
            "source_use_sha256": source_use_fingerprint(self.original),
            "recipient": "editor@example.invalid",
            "fictional_owner_approval_sha256": digest(b"synthetic owner approval only"),
        }

    def bind(self, **kwargs):
        return bind_fictional_reviewed_snapshot(
            self.source, self.private, self.journal, **dict(self.params, **kwargs)
        )

    def assert_no_copy(self):
        self.assertEqual(list(self.private.iterdir()), [])

    def test_exact_fictional_preflight_registers_without_reserving_or_sending(self):
        with patch("scripts.sunday_editorial_handoff.send_packet") as mail, \
             patch("scripts.sunday_briefs_auto_writer.compose") as model:
            result = self.bind()
        self.assertEqual(result["status"], "FICTIONAL_REGISTERED_NO_SEND")
        self.assertFalse(result["smtp_attempted"])
        self.assertFalse(result["sender_enabled"])
        self.assertFalse(result["owner_authenticated"])
        self.assertFalse(result["source_rights_verified"])
        self.assertEqual(self.journal.state(result["journal_identity"]), "registered")
        self.assertEqual(result["frozen_private_path"].read_bytes(), self.original)
        self.assertEqual(stat.S_IMODE(result["frozen_private_path"].stat().st_mode), 0o400)
        mail.assert_not_called()
        model.assert_not_called()

    def test_world_readable_original_refused_before_inspection(self):
        self.source.chmod(0o644)
        with patch("core.sunday_c1_custody_binding.inspect_file") as read:
            with self.assertRaisesRegex(
                FictionalCustodyHold, "caller-owned and privately readable"
            ):
                self.bind()
            read.assert_not_called()
        self.assert_no_copy()
        self.assert_no_registration()

    def test_symlink_original_outside_git_refused_before_inspection(self):
        link = self.folder / "symlink-original.txt"
        link.symlink_to(self.source)
        with patch("core.sunday_c1_custody_binding.inspect_file") as read:
            with self.assertRaisesRegex(
                FictionalCustodyHold, "caller-owned and privately readable"
            ):
                bind_fictional_reviewed_snapshot(
                    link, self.private, self.journal, **self.params
                )
            read.assert_not_called()
        self.assert_no_copy()
        self.assert_no_registration()

    def test_wrong_week_does_not_create_or_register(self):
        with self.assertRaises(FictionalCustodyHold):
            self.bind(week="2026-10-17", approved_week="2026-10-17")
        self.assert_no_copy()

    def test_owner_approval_week_missing_or_wrong_before_copy(self):
        for wrong in ("", "2026-10-03", "2026-10-10 "):
            with self.subTest(wrong=wrong), self.assertRaises(OwnerReviewRequired):
                self.bind(approved_week=wrong)
        self.assert_no_copy()

    def test_wrong_reviewed_document_hash_before_copy(self):
        for sha in (digest(b"different draft"), "A" * 64, "bad"):
            with self.subTest(sha=sha), self.assertRaises((OwnerReviewRequired, FictionalCustodyHold)):
                self.bind(reviewed_sha256=sha)
        self.assert_no_copy()

    def test_original_changed_since_review_fails_before_copy(self):
        self.source.write_bytes(self.original + b"modification")
        with self.assertRaises((OwnerReviewRequired, ValueError)):
            self.bind()
        self.assert_no_copy()

    def test_missing_or_changed_source_receipt_fails_before_copy(self):
        for sha in ("", "a" * 64, "uppercase"):
            with self.subTest(sha=sha), self.assertRaises(FictionalCustodyHold):
                self.bind(source_use_sha256=sha)
        self.assert_no_copy()

    def test_real_recipient_or_address_injection_refused(self):
        for candidate in ("editor@example.org", "editor@example.com",
                          "editor@example.invalid\nbcc@evil.test",
                          "Editor@example.invalid", "editor@example.invalid "):
            with self.subTest(value=candidate), self.assertRaises(FictionalCustodyHold):
                self.bind(recipient=candidate)
        self.assert_no_copy()

    def test_fake_approval_reference_cannot_be_missing(self):
        with self.assertRaises(FictionalCustodyHold):
            self.bind(fictional_owner_approval_sha256="not a digest")
        self.assert_no_copy()

    def test_malformed_manuscript_fails_without_private_copy(self):
        self.source.write_bytes(b"non-manuscript")
        with self.assertRaises(ValueError):
            self.bind(reviewed_sha256=digest(self.source.read_bytes()))
        self.assert_no_copy()

    def test_second_call_never_creates_new_copy_or_reserves(self):
        first = self.bind()
        with self.assertRaisesRegex(FictionalCustodyHold, "already holds"):
            self.bind()
        self.assertEqual(len(list(self.private.iterdir())), 1)
        self.assertEqual(self.journal.state(first["journal_identity"]), "registered")

    def test_previous_mock_send_cannot_be_reopened_by_c1(self):
        first = self.bind()
        self.journal.reserve_attempt(first["journal_identity"])
        with self.assertRaises(FictionalCustodyHold):
            self.bind()
        self.assertEqual(self.journal.state(first["journal_identity"]), "attempt_reserved")

    def test_revised_same_week_cannot_create_second_registered_intent(self):
        first = self.bind()
        changed = self.original.replace(
            b"## WHAT STOOD OUT", b"## WHAT STOOD OUT\nA revised paragraph", 1)
        self.source.write_bytes(changed)
        with self.assertRaises(DeliveryHold):
            self.bind(reviewed_sha256=digest(changed))
        self.assertEqual(self.journal.state(first["journal_identity"]), "registered")

    def test_snapshot_store_must_not_be_inside_git_tree(self):
        import core.sunday_private_reviewed_snapshot as snapshot
        repo = Path(snapshot.__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=str(repo)) as in_repo:
            os.chmod(in_repo, 0o700)
            with patch("core.sunday_c1_custody_binding.inspect_file") as read:
                with self.assertRaisesRegex(
                    FictionalCustodyHold, "outside the public repository"
                ):
                    bind_fictional_reviewed_snapshot(
                        self.source, in_repo, self.journal, **self.params
                    )
                read.assert_not_called()
        self.assert_no_copy()
        self.assert_no_registration()

    def test_corruption_of_frozen_file_before_final_read_is_held(self):
        real_inspect = inspect_file
        seen = [0]
        def changed(path, week_ending):
            seen[0] += 1
            if seen[0] == 2:
                Path(path).chmod(0o600)
                Path(path).write_bytes(b"corrupted after copy")
            return real_inspect(path, week_ending=week_ending)
        with patch("core.sunday_c1_custody_binding.inspect_file", side_effect=changed):
            with self.assertRaises(ValueError):
                self.bind()
        # No journal send allowance, even if a changed private artifact remains.
        self.assert_no_registration()

    def assert_no_registration(self):
        import sqlite3
        with sqlite3.connect(str(self.journal_path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM intents").fetchone()[0], 0)

    def test_competing_offline_registration_has_one_winner(self):
        def submit(_):
            try:
                return self.bind()["status"]
            except (FictionalCustodyHold, SnapshotHold, DeliveryHold):
                return "held"
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(submit, range(2)))
        self.assertEqual(outcomes.count("FICTIONAL_REGISTERED_NO_SEND"), 1)
        self.assertEqual(outcomes.count("held"), 1)

    def test_source_under_public_git_refused_before_private_copy(self):
        import core.sunday_c1_custody_binding as binding
        repo = Path(binding.__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=str(repo)) as inside:
            os.chmod(inside, 0o700)
            source = Path(inside) / "original.txt"
            source.write_bytes(self.original)
            with self.assertRaisesRegex(FictionalCustodyHold, "outside the public repository"):
                bind_fictional_reviewed_snapshot(
                    source, self.private, self.journal, **self.params
                )
        self.assert_no_copy()
        self.assert_no_registration()

    def test_journal_under_public_git_refused_before_private_copy(self):
        import core.sunday_c1_custody_binding as binding
        repo = Path(binding.__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=str(repo)) as inside:
            os.chmod(inside, 0o700)
            path = Path(inside) / "test-journal.sqlite"
            other = DeliveryJournal(path, initialize_new=True)
            with self.assertRaisesRegex(FictionalCustodyHold, "outside the public repository"):
                bind_fictional_reviewed_snapshot(
                    self.source, self.private, other, **self.params
                )
        self.assert_no_copy()
        self.assert_no_registration()

    def test_relative_source_rejected_before_private_copy(self):
        with self.assertRaisesRegex(FictionalCustodyHold, "absolute private path"):
            bind_fictional_reviewed_snapshot(
                Path("relative.txt"), self.private, self.journal, **self.params
            )
        self.assert_no_copy()
        self.assert_no_registration()

    def test_snapshot_destination_relative_path_is_refused_before_read(self):
        with patch("core.sunday_c1_custody_binding.inspect_file") as read:
            with self.assertRaisesRegex(FictionalCustodyHold, "absolute private path"):
                bind_fictional_reviewed_snapshot(
                    self.source, Path("private"), self.journal, **self.params
                )
            read.assert_not_called()
        self.assert_no_copy()
        self.assert_no_registration()

    def test_git_checkout_symlinked_parent_does_not_exempt_destination(self):
        import core.sunday_c1_custody_binding as binding
        repo = Path(binding.__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=str(repo)) as inside:
            os.chmod(inside, 0o700)
            link = Path(inside) / "outgoing"
            link.symlink_to(self.folder, target_is_directory=True)
            routed = link / "private"
            with patch("core.sunday_c1_custody_binding.inspect_file") as read:
                with self.assertRaisesRegex(
                    FictionalCustodyHold, "outside the public repository"
                ):
                    bind_fictional_reviewed_snapshot(
                        self.source, routed, self.journal, **self.params
                    )
                read.assert_not_called()
        self.assert_no_copy()
        self.assert_no_registration()

    def test_git_checkout_symlink_to_external_original_is_refused(self):
        import core.sunday_c1_custody_binding as binding
        repo = Path(binding.__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=str(repo)) as inside:
            os.chmod(inside, 0o700)
            linked = Path(inside) / "linked-source.txt"
            linked.symlink_to(self.source)
            with patch("core.sunday_c1_custody_binding.inspect_file") as read:
                with self.assertRaisesRegex(
                    FictionalCustodyHold, "outside the public repository"
                ):
                    bind_fictional_reviewed_snapshot(
                        linked, self.private, self.journal, **self.params
                    )
                read.assert_not_called()
        self.assert_no_copy()
        self.assert_no_registration()

    def test_missing_journal_instance_fails_before_snapshot(self):
        with self.assertRaises(FictionalCustodyHold):
            bind_fictional_reviewed_snapshot(
                self.source, self.private, None, **self.params)
        self.assert_no_copy()


if __name__ == "__main__":
    unittest.main()
