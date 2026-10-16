"""Offline adversarial tests for the current Korean publisher policy callback."""
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from core.korea_current_policy_replay import (
    CurrentKoreaPolicyReplay, KOGL_CLAUSES, KOGL_TERMS, PolicyHold,
    PUBLISHER_CLAUSES, PUBLISHER_POLICY, verify_policy_pair,
)
from core.standing_source_rights import POLICIES


def page(clauses):
    # HTML itself is fictional; legal clauses are the fixed public contract.
    return ("<!doctype html><html><body><main>"
            + "".join("<p>" + c + "</p>" for c in clauses)
            + "</main><footer>" + ("synthetic navigation only " * 40)
            + "</footer></body></html>").encode("utf-8")


class Response:
    def __init__(self, url, content, status=200, mime="text/html"):
        self.url = url
        self.content = content
        self.status_code = status
        self.headers = {"Content-Type": mime + "; charset=utf-8"}
        self.history = []


class CurrentKoreaPolicyTests(unittest.TestCase):
    def setUp(self):
        self.pub = page(PUBLISHER_CLAUSES)
        self.kogl = page(KOGL_CLAUSES)

    def verify(self, pub=None, kogl=None):
        return verify_policy_pair(self.pub if pub is None else pub,
                                  self.kogl if kogl is None else kogl,
                                  "2026-10-15T23:00:00Z")

    def test_complete_pair_is_policy_only_not_original_publication(self):
        r = self.verify()
        self.assertEqual(set(r), {
            "policy_id", "official_policy_url", "observed_at_utc",
            "publisher_policy_sha256", "text_reproduction_permitted",
            "derivatives_permitted", "third_party_exclusions_preserved",
            "policy_changed_or_withdrawn",
        })
        self.assertTrue(r["third_party_exclusions_preserved"])
        self.assertFalse(r["policy_changed_or_withdrawn"])
        self.assertNotIn("original_text", str(r))

    def test_missing_per_article_mark_condition_is_held(self):
        self.assertRaisesRegex(
            PolicyHold, "official_policy_terms_changed_or_incomplete",
            self.verify, self.pub.replace(
                PUBLISHER_CLAUSES[1].encode(), b"permission changed"))

    def test_missing_attribution_is_held(self):
        self.assertRaisesRegex(
            PolicyHold, "official_policy_terms_changed_or_incomplete",
            self.verify, self.pub.replace(
                PUBLISHER_CLAUSES[2].encode(), b"no attribution required"))

    def test_missing_photography_exclusion_is_held(self):
        self.assertRaisesRegex(
            PolicyHold, "official_policy_terms_changed_or_incomplete",
            self.verify, self.pub.replace(
                PUBLISHER_CLAUSES[5].encode(), b"photos unrestricted"))

    def test_kogl_derivative_permission_loss_is_held(self):
        self.assertRaisesRegex(
            PolicyHold, "official_policy_terms_changed_or_incomplete",
            self.verify, self.pub, self.kogl.replace(
                KOGL_CLAUSES[1].encode(), b"no derivatives"))

    def test_kogl_nonendorsement_loss_is_held(self):
        self.assertRaisesRegex(
            PolicyHold, "official_policy_terms_changed_or_incomplete",
            self.verify, self.pub, self.kogl.replace(
                KOGL_CLAUSES[3].encode(), b"endorsement granted"))

    def test_conflicting_restriction_detected(self):
        poisoned = self.pub.replace(b"</main>", "공공누리 제1유형 사용을 전면 금지</main>".encode())
        self.assertRaisesRegex(
            PolicyHold, "official_policy_contains_conflicting_restriction",
            self.verify, poisoned)

    def test_non_utf8_and_oversize_fail(self):
        self.assertRaisesRegex(
            PolicyHold, "official_policy_capture_not_utf8",
            self.verify, self.pub + b"\xff")
        self.assertRaisesRegex(
            PolicyHold, "official_policy_capture_missing_or_oversize",
            self.verify, b"x" * 2_000_001)

    def test_malformed_clock_is_held(self):
        self.assertRaisesRegex(
            PolicyHold, "untrusted_policy_observation_clock",
            verify_policy_pair, self.pub, self.kogl, "2026-02-30T12:00:00Z")

    def _callback(self, url_override=None, status=200, mime="text/html"):
        responses = {
            PUBLISHER_POLICY: Response(url_override or PUBLISHER_POLICY,
                                       self.pub, status=status, mime=mime),
            KOGL_TERMS: Response(KOGL_TERMS, self.kogl),
        }
        class Session:
            def get(self, url, **kwargs):
                if kwargs.get("allow_redirects") is not False:
                    raise AssertionError("redirects cannot be followed")
                return responses[url]
        return CurrentKoreaPolicyReplay(
            session=Session(),
            clock=lambda: datetime(2026, 10, 15, 23, tzinfo=timezone.utc))

    def test_live_callback_contract_from_exact_official_hosts(self):
        c = self._callback()
        x = c(POLICIES["kr_policy_mnd_releases"])
        self.assertEqual(x["official_policy_url"], PUBLISHER_POLICY)
        self.assertEqual(x["observed_at_utc"], "2026-10-15T23:00:00Z")
        self.assertEqual(x["publisher_policy_sha256"], c.last_policy_sha256)

    def test_redirecting_publisher_is_rejected(self):
        c = self._callback(url_override="https://evil.invalid/terms")
        self.assertRaisesRegex(
            PolicyHold, "official_policy_http_identity_failed",
            c, POLICIES["kr_policy_mnd_releases"])

    def test_non_html_policy_response_is_rejected(self):
        c = self._callback(mime="application/json")
        self.assertRaisesRegex(
            PolicyHold, "official_policy_content_type_mismatch",
            c, POLICIES["kr_policy_mnd_releases"])

    def test_other_publisher_policy_is_not_supported(self):
        c = self._callback()
        self.assertRaisesRegex(
            PolicyHold, "policy_family_not_korea",
            c, POLICIES["jp_mod_news_ja"])


if __name__ == "__main__":
    unittest.main()
