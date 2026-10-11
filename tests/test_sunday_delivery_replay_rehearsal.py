"""Offline/fake-only Sunday reviewed-artifact and journal integration contracts."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from core.sunday_delivery_journal import DeliveryHold, DeliveryJournal, intent_id
from core.sunday_delivery_replay_rehearsal import (
    FictionalCrash, FictionalReplayRefused, rehearse_reviewed_delivery,
    source_use_fingerprint,
)
from scripts.sunday_pilot_owner_review import OwnerReviewRequired
from tests.test_sunday_editor_readable import reviewed_packet


def digest(x):
    return hashlib.sha256(x).hexdigest()


class DisabledReplayRehearsalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / "fictional-owner-reviewed.txt"
        self.original = reviewed_packet().encode("utf-8")
        self.path.write_bytes(self.original)
        self.journal_file = self.root / "fictional-journal.sqlite"
        self.journal = DeliveryJournal(self.journal_file, initialize_new=True)
        self.args = dict(
            week="2026-10-10", approved_week="2026-10-10",
            reviewed_sha256=digest(self.original),
            source_use_sha256=source_use_fingerprint(self.original),
            recipient="editor@example.invalid",
            owner_approval_sha256=digest(b"fictional explicitly reviewed"),
        )

    def call(self, scenario="preflight_only", **updates):
        return rehearse_reviewed_delivery(
            self.path, self.journal, scenario=scenario,
            **dict(self.args, **updates)
        )

    def key(self):
        return intent_id(self.args["week"], self.args["reviewed_sha256"],
                         self.args["recipient"])

    def test_preflight_does_not_reserve_call_model_or_smtp(self):
        with patch("scripts.sunday_editorial_handoff.send_packet") as smtp, \
             patch("scripts.sunday_briefs_auto_writer.compose") as model:
            response = self.call()
        self.assertEqual(response["state"], "preflight_only")
        self.assertFalse(response["reserved"])
        with self.assertRaises(DeliveryHold):
            self.journal.state(self.key())
        smtp.assert_not_called()
        model.assert_not_called()
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_mock_acceptance_is_never_an_actual_mail(self):
        with patch("scripts.sunday_editorial_handoff.send_packet") as smtp:
            out = self.call("mock_acceptance")
        self.assertEqual(out["state"], "smtp_accepted_mock_only")
        self.assertEqual(self.journal.state(self.key()), "smtp_accepted")
        smtp.assert_not_called()
        self.assertEqual(self.path.read_bytes(), self.original)
        with self.assertRaises(DeliveryHold):
            self.call("mock_acceptance")

    def test_mock_timeout_is_durable_non_retryable(self):
        self.assertEqual(self.call("mock_timeout")["state"], "outcome_unknown")
        self.assertEqual(DeliveryJournal(self.journal_file).state(self.key()),
                         "outcome_unknown")
        with self.assertRaises(DeliveryHold):
            self.call("mock_acceptance")

    def test_fake_acceptance_lost_ack_is_an_unknown_hold(self):
        self.assertEqual(self.call("mock_acceptance_lost_ack")["state"],
                         "outcome_unknown")
        with self.assertRaises(DeliveryHold):
            self.call("mock_timeout")

    def test_crash_after_reservation_never_rearms(self):
        with self.assertRaises(FictionalCrash):
            self.call("crash_after_reservation")
        self.assertEqual(DeliveryJournal(self.journal_file).state(self.key()),
                         "attempt_reserved")
        with self.assertRaises(DeliveryHold):
            self.call("mock_acceptance")

    def test_explicit_hold_before_contact_refuses_later_reservation(self):
        self.assertEqual(self.call("hold_before_contact")["state"], "held")
        with self.assertRaises(DeliveryHold):
            self.call("mock_acceptance")

    def test_wrong_or_absent_owner_week_fails_before_journal(self):
        for approved in ("", "2026-10-03", "2026-10-10 "):
            with self.subTest(approved=approved), self.assertRaises(OwnerReviewRequired):
                self.call("mock_acceptance", approved_week=approved)
        with self.assertRaises(DeliveryHold):
            self.journal.state(self.key())

    def test_wrong_manuscript_digest_fails_before_reservation(self):
        with self.assertRaises(OwnerReviewRequired):
            self.call("mock_acceptance", reviewed_sha256=digest(b"second AI draft"))
        with self.assertRaises(DeliveryHold):
            self.journal.state(self.key())

    def test_altered_attachment_fails_before_journal(self):
        changed = self.original.replace(b"## WHAT STOOD OUT",
                                        b"## WHAT STOOD OUT\nALTERED WORDS", 1)
        self.path.write_bytes(changed)
        with self.assertRaises(OwnerReviewRequired):
            self.call("mock_acceptance")
        with self.assertRaises(DeliveryHold):
            self.journal.state(self.key())

    def test_missing_receipt_digest_fails_before_registration(self):
        for pinned in ("", "f" * 64, "TRUE"):
            with self.subTest(pinned=pinned), self.assertRaises(FictionalReplayRefused):
                self.call("mock_acceptance", source_use_sha256=pinned)
        with self.assertRaises(DeliveryHold):
            self.journal.state(self.key())

    def test_receipt_markers_cannot_be_duplicated_or_reordered(self):
        original = self.original
        for mutated in (
            original + b"\n" + b"END OF MANUSCRIPT SOURCE USE",
            original.replace(b"END OF MANUSCRIPT SOURCE USE",
                             b"END OF UNREVIEWED SOURCE USE", 1),
            original.replace(b"=== MANUSCRIPT SOURCE USE",
                             b"=== TAMPERED SOURCE USE", 1),
        ):
            with self.subTest(sample=mutated[-35:]), \
                 self.assertRaises((FictionalReplayRefused, ValueError)):
                source_use_fingerprint(mutated)

    def test_bad_recipient_or_owner_digest_rejected_without_reservation(self):
        for changes in (
            dict(recipient="two@example.invalid,three@example.invalid"),
            dict(owner_approval_sha256="not a digest"),
        ):
            with self.subTest(changes=changes), self.assertRaises(DeliveryHold):
                self.call("mock_acceptance", **changes)
        with self.assertRaises(DeliveryHold):
            self.journal.state(self.key())

    def test_invalid_scenario_rejected_before_journal(self):
        with self.assertRaises(FictionalReplayRefused):
            self.call("live_send")
        with self.assertRaises(DeliveryHold):
            self.journal.state(self.key())

    def test_concurrent_fake_workers_only_one_reserves(self):
        def one(_):
            try:
                return self.call("mock_acceptance")["state"]
            except DeliveryHold:
                return "denied"
        with ThreadPoolExecutor(max_workers=6) as pool:
            got = list(pool.map(one, range(6)))
        self.assertEqual(got.count("smtp_accepted_mock_only"), 1)
        self.assertEqual(got.count("denied"), 5)
        self.assertEqual(DeliveryJournal(self.journal_file).state(self.key()),
                         "smtp_accepted")

    def test_revised_reviewed_text_same_week_cannot_enable_second_mock_delivery(self):
        first = self.call("mock_acceptance")
        self.assertEqual(first["state"], "smtp_accepted_mock_only")
        # Change prose while keeping all source appendix/receipt bytes intact:
        # a fresh owner SHA cannot silently become a second same-week delivery.
        edited = self.original.replace(
            b"## WHAT STOOD OUT", b"## WHAT STOOD OUT\nA revised editorial sentence.", 1)
        self.path.write_bytes(edited)
        second_sha = digest(edited)
        self.assertNotEqual(second_sha, self.args["reviewed_sha256"])
        with self.assertRaises(DeliveryHold):
            self.call("mock_acceptance", reviewed_sha256=second_sha)
        self.assertEqual(self.journal.state(self.key()), "smtp_accepted")

    def test_source_use_receipt_is_an_unverified_model_report(self):
        """Fingerprint equality must never be described as human verification."""
        value = self.call("preflight_only")
        self.assertEqual(value["source_use_sha256"], self.args["source_use_sha256"])
        self.assertNotIn("approved", value["state"])
        self.assertFalse(value["reserved"])


if __name__ == "__main__":
    unittest.main()
