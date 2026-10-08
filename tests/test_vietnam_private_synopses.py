"""No-network tests for source-use-gated Vietnam private synopsis drafting."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.draft_vietnam_private_synopses import (
    SCHEMA, SOURCE, BRANCH, EXCERPT_SCOPE, SynopsisRefused, authorization,
    select, model_schema, make_note, draft,
)

SAT = "2026-10-10"
SHA = "a" * 40
URL = ("https://bocongan.gov.vn/bai-viet/"
       "mo-rong-hop-tac-cong-nghe-cong-nghiep-an-ninh-voi-cac-doi-tac-tho-nhi-ky-1791199100")
IDENT = "mps-vi:1791199100"
DIGEST = "d" * 64
BODY = "Bộ Công an của Việt Nam thảo luận với các đối tác về công nghệ. " * 30


def grant():
    return {
        "schema": SCHEMA, "source_slug": SOURCE, "state_commit": SHA,
        "reporting_saturday": SAT, "reviewer": "Reviewed Research Lead",
        "approved_at_utc": "2026-10-08T12:00:00Z",
        "scope": EXCERPT_SCOPE,
        "records": [{
            "source_identity": IDENT, "canonical_url": URL,
            "content_sha256": DIGEST,
            "decision": "allow-private-model-bounded-excerpt",
            "source_use_basis": (
                "Synthetic fixture: explicit reviewer examined permission for "
                "this one text excerpt and documented a narrow private-use basis."
            ),
            "max_excerpt_chars": 250,
        }],
    }


def evidence():
    return {
        "records": [{
            "source_identity": IDENT, "source_slug": SOURCE,
            "canonical_url": URL, "current_content_sha256": DIGEST,
            "published_date": "2026-10-05",
        }],
        "versions": [{
            "source_identity": IDENT, "content_sha256": DIGEST,
            "title_original": "Mở rộng hợp tác công nghệ, công nghiệp an ninh",
            "body_status": "text", "text_original": BODY,
        }],
    }


class DummyMessages:
    def __init__(self, value=None):
        self.calls = []
        self.value = value if value is not None else {
            "summary": (
                "Vietnam's Ministry of Public Security reported preliminary "
                "security-technology cooperation discussions, without an "
                "announced acquisition, procurement or completed deployment."
            ),
            "caveats": [
                "The excerpt may omit qualifications appearing later in the publisher's original.",
                "This limited Vietnamese text is not a complete independent translation.",
            ],
            "topics": ["technology_cooperation", "security_industry"],
        }

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason="tool_use", content=[
            SimpleNamespace(type="tool_use",
                            name="draft_official_source_note", input=self.value),
        ])


class GateTests(unittest.TestCase):
    def test_explicit_per_source_authorization_is_required(self):
        rows = authorization(grant(), state_commit=SHA, week_ending=SAT)
        self.assertEqual(len(rows), 1)
        for key, value in (
            ("scope", "public-article-reuse"),
            ("state_commit", "b" * 40),
            ("reporting_saturday", "2026-10-17"),
            ("reviewer", ""),
        ):
            bad = grant()
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(SynopsisRefused):
                authorization(bad, state_commit=SHA, week_ending=SAT)

    def test_malformed_decision_wrong_version_and_overlong_excerpt_fail(self):
        for key, value in (
            ("decision", "pending"),
            ("content_sha256", "f" * 64),
            ("canonical_url", "https://bocongan.gov.vn.evil.test/bai-viet/x-1791199100"),
            ("max_excerpt_chars", 1401),
            ("max_excerpt_chars", True),
            ("source_use_basis", "approved"),
        ):
            bad = grant()
            bad["records"][0][key] = value
            with self.subTest(key=key):
                if key == "content_sha256":
                    rows = authorization(bad, state_commit=SHA,
                                         week_ending=SAT)
                    with self.assertRaisesRegex(SynopsisRefused, "changed"):
                        select(evidence(), rows, SAT)
                else:
                    with self.assertRaises(SynopsisRefused):
                        authorization(bad, state_commit=SHA, week_ending=SAT)

    def test_synthetic_private_grant_never_implies_approval_of_source(self):
        v = authorization(grant(), state_commit=SHA, week_ending=SAT)
        got = select(evidence(), v, SAT)
        self.assertEqual(len(got), 1)
        self.assertEqual(len(got[0][2]), 250)
        self.assertNotEqual(got[0][2], BODY)
        self.assertNotIn("production", str(v).lower())

    def test_scope_refuses_stale_week_or_missing_body_before_model(self):
        for alteration in (
            lambda ev: ev["records"][0].update({"published_date": "2026-10-03"}),
            lambda ev: ev["versions"][0].update({"body_status": "denied"}),
            lambda ev: ev["records"][0].update({"current_content_sha256": "e" * 64}),
        ):
            ev = evidence()
            alteration(ev)
            with self.assertRaises(SynopsisRefused):
                select(ev, authorization(grant(), state_commit=SHA,
                                         week_ending=SAT), SAT)

    def test_one_source_model_prompt_is_bounded_and_typed(self):
        msg = DummyMessages()
        item = select(evidence(), authorization(grant(), state_commit=SHA,
                                                 week_ending=SAT), SAT)[0]
        value = make_note(*item, client=SimpleNamespace(messages=msg))
        self.assertEqual(value["content_sha256"], DIGEST)
        self.assertEqual(value["source_identity"], IDENT)
        self.assertEqual(value["source_url"], URL)
        self.assertTrue(value["summary"].startswith("Vietnam"))
        self.assertEqual(len(msg.calls), 1)
        prompt = msg.calls[0]["messages"][0]["content"]
        self.assertIn(BODY[:250], prompt)
        self.assertNotIn(BODY[:600], prompt)
        self.assertEqual(msg.calls[0]["tools"][0]["input_schema"],
                         model_schema())
        self.assertEqual(msg.calls[0]["tool_choice"]["name"],
                         "draft_official_source_note")

    def test_poisoned_model_output_is_not_accepted_as_analyst_note(self):
        record, version, excerpt = select(
            evidence(), authorization(grant(), state_commit=SHA,
                                      week_ending=SAT), SAT)[0]
        for value in (
            {"summary": "too brief", "caveats": ["A valid long enough caveat."],
             "topics": ["technology_cooperation"]},
            {"summary": "A" * 90, "caveats": ["A valid long enough caveat."],
             "topics": ["unsupported_nuclear_trade"]},
            {"summary": "A" * 90, "caveats": [], "topics": ["hadr"]},
            {"summary": "A" * 90, "caveats": ["A valid long enough caveat."],
             "topics": ["hadr"], "approved": True},
        ):
            with self.subTest(value=value), self.assertRaises(SynopsisRefused):
                make_note(record, version, excerpt,
                          client=SimpleNamespace(messages=DummyMessages(value)))

    def test_independent_shadow_review_happens_before_any_model_api_call(self):
        client = SimpleNamespace(messages=DummyMessages())
        with patch("scripts.draft_vietnam_private_synopses.formal.resolve_state_repo",
                   return_value=Path("/fake/repo")), \
             patch("scripts.draft_vietnam_private_synopses.formal.verify_state_commit",
                   return_value={"state_commit": SHA}) as verify, \
             patch("scripts.draft_vietnam_private_synopses.formal.export_state_tree",
                   return_value=Path("/fake/state")) as export, \
             patch("scripts.draft_vietnam_private_synopses.ministry.review",
                   return_value=evidence()) as review:
            prepared = draft(Path("/fake/repo"), SHA, SAT, grant(), client=client)
        verify.assert_called_once_with(Path("/fake/repo"), SHA, BRANCH)
        self.assertTrue(export.called and review.called)
        self.assertEqual(prepared["schema"], "vietnam-editorial-notes/1")
        self.assertEqual(prepared["entries"][0]["content_sha256"], DIGEST)
        self.assertEqual(len(client.messages.calls), 1)

        # Invalid rights and changed source-version must fail before model call.
        client.messages.calls.clear()
        bad = grant()
        bad["records"][0]["decision"] = "not-authorized"
        with self.assertRaises(SynopsisRefused):
            draft(Path("/fake/repo"), SHA, SAT, bad, client=client)
        self.assertFalse(client.messages.calls)
        ev = evidence()
        ev["records"][0]["current_content_sha256"] = "f" * 64
        with patch("scripts.draft_vietnam_private_synopses.formal.resolve_state_repo",
                   return_value=Path("/fake/repo")), \
             patch("scripts.draft_vietnam_private_synopses.formal.verify_state_commit"), \
             patch("scripts.draft_vietnam_private_synopses.formal.export_state_tree",
                   return_value=Path("/fake/state")), \
             patch("scripts.draft_vietnam_private_synopses.ministry.review",
                   return_value=ev):
            with self.assertRaises(SynopsisRefused):
                draft(Path("/fake/repo"), SHA, SAT, grant(), client=client)
        self.assertFalse(client.messages.calls)


if __name__ == "__main__":
    unittest.main()
