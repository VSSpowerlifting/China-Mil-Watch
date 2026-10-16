"""C2 offline-only fictional approval tests: no signing credentials or SMTP."""
import copy
import hashlib
import hmac
import unittest
from datetime import datetime, timezone

from core.sunday_fictional_approval import (
    DOMAIN, PURPOSE, SCHEMA, FictionalApprovalHold,
    canonical_fixture_claims, verify_fictional_editor_release,
)


class FictionalReleaseTests(unittest.TestCase):
    def setUp(self):
        self.key = b"synthetic unit-test verifier key not authorized 0123456789"
        self.body = b"synthetic reviewed manuscript bytes, no third-party source body"
        self.source = hashlib.sha256(b"synthetic source-use receipt only").hexdigest()
        self.clock = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
        self.claims = {
            "schema": SCHEMA,
            "decision_id": "fictional-decision-pilot",
            "signer_id": "fictional-owner@example.invalid",
            "reporting_week": "2026-10-10",
            "manuscript_sha256": hashlib.sha256(self.body).hexdigest(),
            "source_use_sha256": self.source,
            "byte_length": len(self.body),
            "recipient": "editor@example.invalid",
            "purpose": PURPOSE,
            "source_review_id": "fictional-source-review-pilot",
            "rights_decision_id": "fictional-rights-decision-pilot",
            "approved_at": "2026-10-11T11:00:00Z",
            "expires_at": "2026-10-12T11:00:00Z",
        }

    def signed(self, claims=None, key=None):
        claims = copy.deepcopy(self.claims if claims is None else claims)
        key = self.key if key is None else key
        mac = hmac.new(key, DOMAIN + canonical_fixture_claims(claims),
                       hashlib.sha256).hexdigest()
        return {"claims": claims, "mac_sha256": mac}

    def verify(self, signed=None, **changes):
        params = {
            "manuscript_bytes": self.body,
            "source_use_sha256": self.source,
            "signed_receipt": self.signed() if signed is None else signed,
            "verifier_key": self.key,
            "now_utc": self.clock,
            "revoked_decision_ids": frozenset(),
        }
        params.update(changes)
        return verify_fictional_editor_release(**params)

    def test_valid_fictional_approval_returns_explicit_no_send(self):
        result = self.verify()
        self.assertEqual(result.week, "2026-10-10")
        self.assertEqual(result.recipient, "editor@example.invalid")
        self.assertFalse(result.authenticated_owner)
        self.assertFalse(result.rights_verified)
        self.assertFalse(result.mail_authorized)

    def test_changed_original_bytes_or_length_never_authorize(self):
        with self.assertRaises(FictionalApprovalHold):
            self.verify(manuscript_bytes=self.body + b".")
        wrong = copy.deepcopy(self.claims)
        wrong["byte_length"] += 1
        with self.assertRaises(FictionalApprovalHold):
            self.verify(signed=self.signed(wrong))

    def test_source_use_receipt_drift_rejected(self):
        with self.assertRaises(FictionalApprovalHold):
            self.verify(source_use_sha256=hashlib.sha256(b"other").hexdigest())

    def test_modified_claims_after_signing_rejected(self):
        payload = self.signed()
        payload["claims"]["recipient"] = "different@example.invalid"
        with self.assertRaises(FictionalApprovalHold):
            self.verify(signed=payload)

    def test_wrong_verification_key_or_mac_refused(self):
        with self.assertRaises(FictionalApprovalHold):
            self.verify(verifier_key=b"unrelated fictional unit test verification key 09876")
        payload = self.signed()
        payload["mac_sha256"] = "0" * 64
        with self.assertRaises(FictionalApprovalHold):
            self.verify(signed=payload)

    def test_real_addresses_and_header_injection_rejected(self):
        for address in ("editor@example.com", "fictional-owner@example.invalid",
                        "editor@example.invalid\r\nCc:test@example.invalid",
                        "editor@example.invalid,other@example.invalid",
                        "Editor@example.invalid", "editor..backup@example.invalid"):
            with self.subTest(address=address), self.assertRaises(FictionalApprovalHold):
                altered = dict(self.claims, recipient=address)
                self.signed(altered)

    def test_recipient_purpose_and_week_cannot_expand(self):
        for name, value in (("reporting_week", "2026-10-17"),
                            ("purpose", "publish_and_send"),
                            ("schema", "ipr-sunday-real-release/1")):
            with self.subTest(name=name), self.assertRaises(FictionalApprovalHold):
                self.signed(dict(self.claims, **{name: value}))

    def test_theme_token_or_untrusted_rights_ids_rejected(self):
        for name, value in (("source_review_id", ""),
                            ("rights_decision_id", "missing"),
                            ("decision_id", "theme-approval-only"),
                            ("signer_id", "unknown-owner@example.invalid")):
            with self.subTest(name=name), self.assertRaises(FictionalApprovalHold):
                self.signed(dict(self.claims, **{name: value}))

    def test_expired_and_before_approval_refused(self):
        for when in (datetime(2026, 10, 11, 10, 59, tzinfo=timezone.utc),
                     datetime(2026, 10, 12, 11, 0, tzinfo=timezone.utc)):
            with self.subTest(when=when), self.assertRaises(FictionalApprovalHold):
                self.verify(now_utc=when)

    def test_explicit_revocation_refused(self):
        with self.assertRaises(FictionalApprovalHold):
            self.verify(revoked_decision_ids=frozenset(("fictional-decision-pilot",)))

    def test_missing_revocation_source_refused(self):
        with self.assertRaises(FictionalApprovalHold):
            self.verify(revoked_decision_ids=None)

    def test_noncanonical_time_and_bounded_duration_refused(self):
        for field, value in (("approved_at", "2026-10-11T11:00:00+00:00"),
                             ("approved_at", "2026-10-11T11:00:00"),
                             ("expires_at", "2026-10-11T11:00:00Z"),
                             ("expires_at", "2026-10-21T11:00:00Z"),
                             ("expires_at", "bad")):
            with self.subTest(field=field, value=value), self.assertRaises(FictionalApprovalHold):
                self.signed(dict(self.claims, **{field: value}))

    def test_unknown_field_or_missing_field_not_accepted(self):
        added = dict(self.claims, send_email=True)
        removed = dict(self.claims)
        removed.pop("source_review_id")
        for value in (added, removed):
            with self.subTest(keys=tuple(value)), self.assertRaises(FictionalApprovalHold):
                self.signed(value)

    def test_weak_or_nonstrict_verifier_key_rejected(self):
        for key in (b"tiny", "synthetic string", None):
            with self.subTest(key=key), self.assertRaises(FictionalApprovalHold):
                self.verify(verifier_key=key)

    def test_malformed_receipt_signature_refused(self):
        for receipt in ({"claims": self.claims},
                        {"claims": self.claims, "mac_sha256": "A" * 64},
                        {"claims": self.claims, "mac_sha256": "0" * 64, "extra": 1}):
            with self.subTest(keys=tuple(receipt)), self.assertRaises(FictionalApprovalHold):
                self.verify(signed=receipt)

    def test_non_bytes_artifact_and_wrong_receipt_format_refused(self):
        for bad in (None, "str", b"", b"x" * 2_000_001):
            with self.subTest(type=str(type(bad))), self.assertRaises(FictionalApprovalHold):
                self.verify(manuscript_bytes=bad)
        with self.assertRaises(FictionalApprovalHold):
            self.verify(source_use_sha256="A" * 64)

    def test_no_clock_or_utc_naive_time_refused(self):
        with self.assertRaises(FictionalApprovalHold):
            self.verify(now_utc=datetime(2026, 10, 11, 12, 0, 0))

    def test_signed_receipt_does_not_mutate_original(self):
        x = self.signed()
        original = copy.deepcopy(x)
        self.verify(signed=x)
        self.assertEqual(x, original)


if __name__ == "__main__":
    unittest.main()
