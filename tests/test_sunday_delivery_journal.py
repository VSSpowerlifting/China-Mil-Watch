"""Synthetic-only durability and no-resend contracts for Sunday email intent."""
import concurrent.futures
import hashlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

from core.sunday_delivery_journal import DeliveryHold, DeliveryJournal, intent_id


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "private.sqlite"
        self.journal = DeliveryJournal(self.path)
        self.fields = {
            "week": "2026-10-10", "manuscript_sha256": sha("fictional article"),
            "source_receipt_sha256": sha("fictional source receipt"),
            "recipient": "editor@example.invalid",
            "owner_approval_sha256": sha("fictional approval evidence"),
        }

    def register(self):
        return self.journal.register(**self.fields)

    def test_not_created_on_import_or_non_private_dir(self):
        bad = Path(self.tmp.name) / "public"
        bad.mkdir(mode=0o755)
        with self.assertRaises(DeliveryHold):
            DeliveryJournal(bad / "state.sqlite")
        self.assertFalse((bad / "state.sqlite").exists())

    def test_symlink_file_rejected(self):
        link = Path(self.tmp.name) / "link.sqlite"
        link.symlink_to(self.path)
        with self.assertRaises(DeliveryHold):
            DeliveryJournal(link)

    def test_required_saturday_and_single_recipient(self):
        for week in ("2026-10-11", "2026-10-10x", "yesterday"):
            with self.subTest(week=week), self.assertRaises(DeliveryHold):
                intent_id(week, self.fields["manuscript_sha256"], self.fields["recipient"])
        for recipient in ("two@example.invalid,three@example.invalid", "x\ny@example.invalid", "X <x@example.invalid>"):
            with self.subTest(recipient=recipient), self.assertRaises(DeliveryHold):
                intent_id(self.fields["week"], self.fields["manuscript_sha256"], recipient)

    def test_missing_approval_receipt_rejected(self):
        f = dict(self.fields, owner_approval_sha256="not an approval digest")
        with self.assertRaises(DeliveryHold):
            self.journal.register(**f)

    def test_reopen_does_not_retry_reserved_or_accepted(self):
        key = self.register()
        self.assertEqual(self.journal.reserve_attempt(key), "attempt_reserved")
        restarted = DeliveryJournal(self.path)
        self.assertEqual(restarted.register(**self.fields), key)
        with self.assertRaises(DeliveryHold):
            restarted.reserve_attempt(key)
        self.assertEqual(restarted.record_smtp_acceptance(key, sha("server acceptance")), "smtp_accepted")
        with self.assertRaises(DeliveryHold):
            restarted.reserve_attempt(key)
        with self.assertRaises(DeliveryHold):
            restarted.mark_unknown(key)

    def test_ambiguous_send_never_auto_retries(self):
        key = self.register()
        self.journal.reserve_attempt(key)
        self.journal.mark_unknown(key)
        self.assertEqual(DeliveryJournal(self.path).state(key), "outcome_unknown")
        with self.assertRaises(DeliveryHold):
            self.journal.reserve_attempt(key)
        with self.assertRaises(DeliveryHold):
            self.journal.record_smtp_acceptance(key, sha("later guess"))

    def test_cannot_claim_smtp_acceptance_before_attempt(self):
        key = self.register()
        with self.assertRaises(DeliveryHold):
            self.journal.record_smtp_acceptance(key, sha("invented"))
        self.assertEqual(self.journal.state(key), "registered")

    def test_conflicting_source_or_approval_does_not_reset(self):
        key = self.register()
        self.journal.reserve_attempt(key)
        for field in ("source_receipt_sha256", "owner_approval_sha256"):
            alt = dict(self.fields, **{field: sha(field + " replaced")})
            with self.subTest(field=field), self.assertRaises(DeliveryHold):
                self.journal.register(**alt)
        self.assertEqual(self.journal.state(key), "attempt_reserved")

    def test_parallel_workers_only_one_reserves(self):
        key = self.register()
        def reserve(_):
            try:
                return DeliveryJournal(self.path).reserve_attempt(key)
            except DeliveryHold:
                return "denied"
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            values = list(pool.map(reserve, range(8)))
        self.assertEqual(values.count("attempt_reserved"), 1)
        self.assertEqual(values.count("denied"), 7)

    def test_hold_prevents_send(self):
        key = self.register()
        self.journal.hold_before_send(key)
        with self.assertRaises(DeliveryHold):
            self.journal.reserve_attempt(key)

    def test_private_metadata_only(self):
        key = self.register()
        with closing(sqlite3.connect(str(self.path))) as db:
            row = db.execute("SELECT * FROM intents WHERE identity=?", (key,)).fetchone()
        self.assertEqual(len(row), 9)
        self.assertNotIn("fictional article", repr(row))
        self.assertNotIn("editor@example.invalid", repr(row))
        self.assertEqual(self.path.stat().st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
