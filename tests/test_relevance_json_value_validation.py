"""Default (non-tool) relevance JSON value contracts: offline, no model spend.

The default free-text JSON parser already fails safely on syntax errors.
A syntactically valid JSON payload with invalid score/reasoning must also be
counted as one *failed spent* response rather than a success in the ledger.
"""
from __future__ import annotations

import json
import math
import unittest
from unittest.mock import patch

from analysis.analyzer import AnalysisError
from config import RELEVANCE_MODEL
from tests.test_relevance_tool_optin import _Client, analyzer, receipt


def scored(raw):
    a = analyzer(_Client(legacy=raw))
    with patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", False):
        result = a.score_relevance("Chinese military headline", "Original text")
    return a, result


class DefaultRelevanceJSONValues(unittest.TestCase):

    def test_valid_numeric_score_keeps_its_old_result_and_spend(self):
        for score in (0, 0.0, 0.27, 0.6, 1, 1.0):
            with self.subTest(score=score):
                a, result = scored(json.dumps({
                    "score": score, "reasoning": "Specific rubric evidence",
                }))
                self.assertEqual(result, (float(score), "Specific rubric evidence"))
                self.assertEqual(len(a._client.create_kwargs), 1)
                self.assertEqual(len(a._client.stream_kwargs), 0)
                r = receipt(a)
                self.assertEqual(
                    (r["model"], r["calls"], r["succeeded_calls"],
                     r["failed_calls"], r["input_tokens"], r["output_tokens"]),
                    (RELEVANCE_MODEL, 1, 1, 0, 120, 24),
                )

    def test_out_of_range_numeric_scores_retain_legacy_clamping(self):
        for score, expected in ((-0.1, 0.0), (-100, 0.0),
                                (1.1, 1.0), (500, 1.0)):
            with self.subTest(score=score):
                a, value = scored(json.dumps({
                    "score": score, "reasoning": "Valid response",
                }))
                self.assertEqual(value, (expected, "Valid response"))
                self.assertEqual(receipt(a)["succeeded_calls"], 1)

    def test_invalid_value_shapes_fail_as_spent_responses(self):
        invalid = [
            {"reasoning": "Missing score"},
            {"score": None, "reasoning": "None score"},
            {"score": True, "reasoning": "Boolean score"},
            {"score": False, "reasoning": "Boolean score"},
            {"score": "0.7", "reasoning": "Numeric-looking string"},
            {"score": "PRIVATE_JSON", "reasoning": "Leaky model text"},
            {"score": [0.5], "reasoning": "List score"},
            {"score": {"secret": "PRIVATE_JSON"}, "reasoning": "Object score"},
            {"score": float("nan"), "reasoning": "Not a number"},
            {"score": float("inf"), "reasoning": "Positive infinity"},
            {"score": float("-inf"), "reasoning": "Negative infinity"},
            {"score": 0.5},
            {"score": 0.5, "reasoning": None},
            {"score": 0.5, "reasoning": 3},
            {"score": 0.5, "reasoning": ""},
            {"score": 0.5, "reasoning": " \t\n"},
            {"score": 0.5, "reasoning": {"secret": "PRIVATE_JSON"}},
            ["valid but not an object"],
            "valid but not an object",
            None,
        ]
        for payload in invalid:
            with self.subTest(payload=repr(payload)[:65]):
                a = analyzer(_Client(legacy=json.dumps(payload)))
                with patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", False):
                    with self.assertRaisesRegex(
                        AnalysisError, "Invalid relevance JSON values"
                    ) as cm:
                        a.score_relevance("headline", "body")
                self.assertNotIn("PRIVATE_JSON", str(cm.exception))
                r = receipt(a)
                self.assertEqual(
                    (r["calls"], r["succeeded_calls"], r["failed_calls"],
                     r["input_tokens"], r["output_tokens"]),
                    (1, 0, 1, 120, 24),
                )
                self.assertEqual(len(a._client.create_kwargs), 1)
                self.assertEqual(len(a._client.stream_kwargs), 0)

    def test_nonfinite_values_are_rejected_not_silently_clamped(self):
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token):
                a = analyzer(_Client(legacy=(
                    '{"score":' + token + ',"reasoning":"Test"}'
                )))
                with patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", False):
                    with self.assertRaisesRegex(AnalysisError, "Invalid relevance JSON"):
                        a.score_relevance("headline", "body")
                self.assertEqual(receipt(a)["failed_calls"], 1)

    def test_very_large_integer_clamps_without_float_overflow(self):
        # Python int has arbitrary precision; math.isfinite(10**400) overflows.
        a, answer = scored(json.dumps({
            "score": 10**400, "reasoning": "valid overshoot",
        }))
        self.assertEqual(answer, (1.0, "valid overshoot"))
        self.assertEqual(receipt(a)["succeeded_calls"], 1)

    def test_invalid_syntax_keeps_one_failed_spent_response(self):
        a = analyzer(_Client(legacy='{"score": 0.8, "reasoning": "PRIVATE_UNCLOSED'))
        with patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", False):
            with self.assertRaisesRegex(AnalysisError, "JSON parse failed") as cm:
                a.score_relevance("headline", "body")
        self.assertNotIn("PRIVATE_UNCLOSED", str(cm.exception))
        r = receipt(a)
        self.assertEqual((r["calls"], r["succeeded_calls"],
                          r["failed_calls"], r["output_tokens"]), (1, 0, 1, 24))

    def test_opt_in_tool_contract_is_still_covered_by_existing_suite(self):
        from tests.test_relevance_tool_optin import response
        a = analyzer(_Client(response=response({
            "score": 0.7, "reasoning": "Tool response",
        })))
        with patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", True):
            self.assertEqual(a.score_relevance("headline", "body"),
                             (0.7, "Tool response"))
        self.assertEqual(len(a._client.stream_kwargs), 1)
        self.assertEqual(len(a._client.create_kwargs), 0)
        self.assertEqual(receipt(a)["succeeded_calls"], 1)


if __name__ == "__main__":
    unittest.main()
