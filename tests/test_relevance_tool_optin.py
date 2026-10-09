"""Opt-in relevance tool output contracts: no live provider or DB writes."""
from __future__ import annotations

import json
import math
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import anthropic
import httpx

from analysis.analyzer import AnalysisError, Analyzer, FatalAPIError
from analysis.usage import TASK_RELEVANCE
from config import RELEVANCE_MODEL, RELEVANCE_THRESHOLD


def tokens():
    return SimpleNamespace(input_tokens=120, output_tokens=24,
                           cache_read_input_tokens=10,
                           cache_creation_input_tokens=5)


class _Stream:
    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.response


class _Client:
    def __init__(self, *, response=None, error=None, legacy=None):
        self.response, self.error, self.legacy = response, error, legacy
        self.stream_kwargs, self.create_kwargs = [], []
        self.messages = self

    def stream(self, **kwargs):
        self.stream_kwargs.append(kwargs)
        if self.error is not None:
            raise self.error
        return _Stream(self.response)

    def create(self, **kwargs):
        self.create_kwargs.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(text=self.legacy)],
            stop_reason="end_turn", usage=tokens(),
        )


def response(payload, *, name="emit_relevance", stop="end_turn"):
    block = SimpleNamespace(type="tool_use", name=name, input=payload)
    return SimpleNamespace(content=[block], stop_reason=stop, usage=tokens())


def analyzer(client):
    a = Analyzer.__new__(Analyzer)
    a._client = client
    return a


def receipt(a):
    rows = [r for r in a.usage.rows() if r["task"] == TASK_RELEVANCE]
    assert len(rows) == 1
    return rows[0]


class RelevanceToolOptInContracts(unittest.TestCase):
    def tool_score(self, payload, *, stop="end_turn"):
        a = analyzer(_Client(response=response(payload, stop=stop)))
        with patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", True):
            answer = a.score_relevance("标题", "正文")
        return a, answer

    def test_explicit_opt_in_uses_haiku_and_forced_tool(self):
        a, value = self.tool_score({"score": 0.82, "reasoning": "Relevant military detail"})
        self.assertEqual(value, (0.82, "Relevant military detail"))
        self.assertEqual(len(a._client.create_kwargs), 0)
        self.assertEqual(len(a._client.stream_kwargs), 1)
        request = a._client.stream_kwargs[0]
        self.assertEqual(set(request), {"model", "system", "messages", "max_tokens",
                                        "temperature", "tools", "tool_choice"})
        self.assertEqual(request["model"], RELEVANCE_MODEL)
        self.assertEqual(request["tool_choice"],
                         {"type": "tool", "name": "emit_relevance"})
        self.assertEqual(request["tools"][0]["input_schema"]["required"],
                         ["score", "reasoning"])
        self.assertEqual(request["max_tokens"], 500)
        self.assertEqual(request["temperature"], 0.0)
        self.assertIs(request["system"], Analyzer._SYSTEM_WITH_CACHE)
        self.assertTrue(request["messages"][0]["content"].startswith(
            "You will receive a Chinese-language article"))
        self.assertEqual(RELEVANCE_THRESHOLD, 0.60)
        r = receipt(a)
        self.assertEqual((r["model"], r["calls"], r["succeeded_calls"],
                          r["failed_calls"]), (RELEVANCE_MODEL, 1, 1, 0))
        self.assertEqual((r["input_tokens"], r["output_tokens"],
                          r["cache_read_input_tokens"],
                          r["cache_creation_input_tokens"]), (120, 24, 10, 5))

    def test_singapore_profile_system_and_messages_remain_scoped(self):
        profile = SimpleNamespace(
            build_messages=lambda title, body: [
                {"role": "user", "content": "Singapore scope"}],
            system_prompt="Desk-specific system",
        )
        a = analyzer(_Client(response=response({"score": 1, "reasoning": "MINDEF"})))
        with patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", True):
            self.assertEqual(a.score_relevance("t", "b", profile), (1.0, "MINDEF"))
        sent = a._client.stream_kwargs[0]
        self.assertEqual(sent["messages"][0]["content"], "Singapore scope")
        self.assertEqual(sent["system"][0]["text"], "Desk-specific system")

    def test_valid_score_boundaries_and_zero_score(self):
        for value in (0, 0.0, 1, 1.0):
            with self.subTest(value=value):
                a, answer = self.tool_score({"score": value, "reasoning": "Valid"})
                self.assertEqual(answer[0], float(value))
                self.assertEqual(receipt(a)["succeeded_calls"], 1)

    def test_bad_tool_values_fail_closed_without_leaking_payload(self):
        invalid = [
            {"score": None, "reasoning": "text"},
            {"score": "0.7", "reasoning": "text"},
            {"score": True, "reasoning": "text"},
            {"score": float("nan"), "reasoning": "text"},
            {"score": float("inf"), "reasoning": "text"},
            {"score": float("-inf"), "reasoning": "text"},
            {"score": 10 ** 400, "reasoning": "text"},
            {"score": -0.01, "reasoning": "text"},
            {"score": 1.01, "reasoning": "text"},
            {"reasoning": "text"},
            {"score": 0.9, "reasoning": None},
            {"score": 0.9, "reasoning": False},
            {"score": 0.9, "reasoning": ""},
            {"score": 0.9, "reasoning": "  \n"},
            {"score": 0.9, "reasoning": {"secret": "PRIVATE_BLOB"}},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                a = analyzer(_Client(response=response(payload)))
                with patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", True):
                    with self.assertRaisesRegex(AnalysisError, "Invalid relevance tool values") as ctx:
                        a.score_relevance("Title", "Body")
                self.assertNotIn("PRIVATE_BLOB", str(ctx.exception))
                r = receipt(a)
                self.assertEqual((r["calls"], r["succeeded_calls"], r["failed_calls"]),
                                 (1, 0, 1))
                self.assertEqual((r["input_tokens"], r["output_tokens"]), (120, 24))

    def test_nonobject_tool_input_is_rejected_with_token_receipt(self):
        for payload in (None, ["private-output"], "private-output"):
            with self.subTest(type=type(payload).__name__):
                a = analyzer(_Client(response=response(payload)))
                with patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", True):
                    with self.assertRaisesRegex(AnalysisError,
                                                "Invalid .* tool input type") as cm:
                        a.score_relevance("Title", "Body")
                self.assertNotIn("private-output", str(cm.exception))
                r = receipt(a)
                self.assertEqual((r["calls"], r["succeeded_calls"],
                                  r["failed_calls"], r["output_tokens"]),
                                 (1, 0, 1, 24))

    def test_missing_tool_is_a_failed_spent_call(self):
        a = analyzer(_Client(response=response({"score": 0.8}, name="other")))
        with patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", True):
            with self.assertRaisesRegex(AnalysisError, "no .emit_relevance."):
                a.score_relevance("Title", "Body")
        self.assertEqual((receipt(a)["failed_calls"], receipt(a)["output_tokens"]),
                         (1, 24))

    def test_truncation_is_a_failed_spent_call(self):
        a = analyzer(_Client(response=response({"score": 0.9, "reasoning": "R"},
                                              stop="max_tokens")))
        with patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", True):
            with self.assertRaisesRegex(AnalysisError, "truncated"):
                a.score_relevance("Title", "Body")
        self.assertEqual((receipt(a)["failed_calls"], receipt(a)["output_tokens"]),
                         (1, 24))

    def test_account_level_failure_remains_fatal_without_invented_tokens(self):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        err = anthropic.APIStatusError(
            "credit balance is too low",
            response=httpx.Response(402, request=request), body=None,
        )
        a = analyzer(_Client(error=err))
        with patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", True):
            with self.assertRaises(FatalAPIError):
                a.score_relevance("Title", "Body")
        r = receipt(a)
        self.assertEqual((r["model"], r["calls"], r["failed_calls"],
                          r["input_tokens"], r["output_tokens"]),
                         (RELEVANCE_MODEL, 1, 1, 0, 0))

    def test_legacy_default_still_uses_raw_json_path(self):
        payload = json.dumps({"score": 0.73, "reasoning": "Legacy result"})
        a = analyzer(_Client(legacy=payload))
        with patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", False):
            self.assertEqual(a.score_relevance("Title", "Body"),
                             (0.73, "Legacy result"))
        self.assertEqual(len(a._client.create_kwargs), 1)
        self.assertEqual(len(a._client.stream_kwargs), 0)
        self.assertEqual(receipt(a)["succeeded_calls"], 1)


if __name__ == "__main__":
    unittest.main()
