"""Purely offline, no-email delivery-state and concurrency contracts."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from scripts.sunday_delivery_ledger import LedgerRefused, transition

WEEK="2026-10-17"
EDITOR="editor@example.edu"
KEY="test-only-stable-key-with-more-than-32-characters"
DIGEST="a"*64


class PrivateEditorialLedgerTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)/"private.sqlite3"

    def op(self, action, **extra):
        return transition(self.path,action=action,secret=KEY,week=WEEK,
                          recipient=EDITOR,**extra)

    def test_read_only_no_entry_does_not_create_file(self):
        x=self.op("inspect")
        self.assertEqual(x["status"],"LEDGER_MISSING_STOP")
        self.assertFalse(self.path.exists())
        self.assertFalse(x["automatic_retry_authorized"])

    def test_absent_or_lost_ledger_requires_manual_initialization(self):
        with self.assertRaisesRegex(LedgerRefused,"durable ledger missing"):
            self.op("reserve",attachment_sha256=DIGEST)
        init=self.op("initialize")
        self.assertEqual(init["status"],"LEDGER_INITIALIZED_NO_EDITION")
        with self.assertRaisesRegex(LedgerRefused,"already exists"):
            self.op("initialize")
        self.op("reserve",attachment_sha256=DIGEST)
        self.path.unlink()
        with self.assertRaisesRegex(LedgerRefused,"durable ledger missing"):
            self.op("reserve",attachment_sha256=DIGEST)

    def test_uncertainty_starts_before_smtp_acceptance(self):
        self.op("initialize")
        self.op("reserve",attachment_sha256=DIGEST)
        started=self.op("start",attachment_sha256=DIGEST)
        self.assertEqual(started["status"],"ATTEMPT_STARTED_DELIVERY_UNCERTAIN")
        self.assertFalse(started["gmail_sent_independently_verified"])
        with self.assertRaisesRegex(LedgerRefused,"previous SMTP attempt"):
            self.op("start",attachment_sha256=DIGEST)
        smtp=self.op("smtp-accepted",attachment_sha256=DIGEST,
                     attempt_token=started["attempt_token"])
        self.assertEqual(smtp["status"],"SMTP_ACCEPTED_UNCONFIRMED")
        self.assertFalse(smtp["automatic_retry_authorized"])
        attested=self.op("sent-attested",attachment_sha256=DIGEST,
                     attempt_token=started["attempt_token"],
                     sent_evidence="gmail:example1122334455")
        self.assertEqual(attested["status"],"SENT_ATTESTED_BY_OPERATOR")
        self.assertTrue(attested["operator_evidence_present"])
        self.assertFalse(attested["gmail_sent_independently_verified"])

    def test_refuses_new_file_or_duplicate_reservation_same_week(self):
        self.op("initialize")
        self.op("reserve",attachment_sha256=DIGEST)
        with self.assertRaisesRegex(LedgerRefused,"duplicate"):
            self.op("reserve",attachment_sha256="b"*64)
        with self.assertRaisesRegex(LedgerRefused,"attachment bytes differ"):
            self.op("start",attachment_sha256="b"*64)

    def test_no_attestation_without_attempt_and_matching_token(self):
        self.op("initialize")
        self.op("reserve",attachment_sha256=DIGEST)
        with self.assertRaises(LedgerRefused):
            self.op("sent-attested",attachment_sha256=DIGEST,
                    attempt_token="invalid",sent_evidence="gmail:112233444")
        x=self.op("start",attachment_sha256=DIGEST)
        with self.assertRaises(LedgerRefused):
            self.op("smtp-accepted",attachment_sha256=DIGEST,
                    attempt_token="invalid")
        with self.assertRaises(LedgerRefused):
            self.op("sent-attested",attachment_sha256=DIGEST,
                    attempt_token=x["attempt_token"],sent_evidence="bad value!")

    def test_no_plain_editor_address_or_hmac_key_in_database(self):
        self.op("initialize")
        self.op("reserve",attachment_sha256=DIGEST)
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)
        raw=self.path.read_bytes()
        self.assertNotIn(EDITOR.encode("utf-8"),raw)
        self.assertNotIn(KEY.encode("utf-8"),raw)

    def test_ledger_key_cannot_rotate_without_fail_closed_review(self):
        self.op("initialize")
        self.op("reserve",attachment_sha256=DIGEST)
        with self.assertRaisesRegex(LedgerRefused,"key changed"):
            transition(self.path,action="inspect",
                secret="new-different-32-character-secret-but-stable",
                week=WEEK,recipient=EDITOR)

    def test_bad_week_mailbox_digest_or_file_permissions(self):
        for week in ("2026-10-11","2026-10-99","2026-1-3"):
            with self.subTest(week=week),self.assertRaises(LedgerRefused):
                transition(self.path,action="reserve",secret=KEY,
                    week=week,recipient=EDITOR,attachment_sha256=DIGEST)
        for mailbox in ("Name <editor@example.edu>","one@site.org,two@site.org","bad\n@site.org"):
            with self.subTest(mailbox=mailbox),self.assertRaises(LedgerRefused):
                transition(self.path,action="reserve",secret=KEY,
                    week=WEEK,recipient=mailbox,attachment_sha256=DIGEST)
        self.op("initialize")
        with self.assertRaises(LedgerRefused):
            self.op("reserve",attachment_sha256="X"*64)
        self.op("reserve",attachment_sha256=DIGEST)
        os.chmod(self.path,0o644)
        with self.assertRaisesRegex(LedgerRefused,"0600"):
            self.op("inspect")

    def test_two_racers_cannot_reserve_same_editor_week(self):
        self.op("initialize")
        barrier=threading.Barrier(2)
        outcomes=[]
        def compete():
            try:
                barrier.wait(timeout=3)
                self.op("reserve",attachment_sha256=DIGEST)
                outcomes.append("reserved")
            except (LedgerRefused,sqlite3.Error):
                outcomes.append("refused")
        threads=[threading.Thread(target=compete) for _ in range(2)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(5)
        self.assertEqual(sorted(outcomes),["refused","reserved"])


if __name__=="__main__":
    unittest.main()
