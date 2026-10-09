"""Malformed model output must never enter an Actions-visible error message.

No API key, provider call, production database, or network access.
"""
from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from analysis.analyzer import AnalysisError, Analyzer


LEAK = "CLASSIFIED-LIKE-MODEL-TEXT-NOT-FOR-ACTIONS-LOGS"
BROKEN = '{"score": 0.9, "reasoning": "' + LEAK + '", trailing_invalid_item}'


class _Client:
    def __init__(self, raw):
        self.raw = raw
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(text=self.raw)],
            stop_reason="end_turn",
            usage=SimpleNamespace(
                input_tokens=120, output_tokens=55,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0),
        )


def analyzer(raw):
    value = Analyzer.__new__(Analyzer)
    value._client = _Client(raw)
    return value


class SafeMalformedModelMessages(unittest.TestCase):
    def assert_safe_failure(self, method, raw=BROKEN):
        obj = analyzer(raw)
        with self.assertRaisesRegex(AnalysisError, "JSON parse failed") as cm:
            getattr(obj, method)("Test title", "Test text")
        output = str(cm.exception)
        self.assertNotIn(LEAK, output)
        self.assertNotIn(raw[:50], output)
        self.assertNotIn("Raw output was:", output)
        self.assertIn("response_chars=", output)
        self.assertIn("line=", output)
        self.assertIn("column=", output)
        self.assertEqual(len(obj._client.calls), 1)
        self.assertEqual(obj.usage.rows()[0]["failed_calls"], 1)
        self.assertEqual(obj.usage.rows()[0]["output_tokens"], 55)

    def test_relevance_parse_error_redacts_model_prose(self):
        self.assert_safe_failure("score_relevance")

    def test_summary_parse_error_redacts_model_prose(self):
        self.assert_safe_failure("summarize")

    def test_category_parse_error_redacts_model_prose(self):
        self.assert_safe_failure("categorize")

    def test_long_malformed_response_is_not_exposed(self):
        raw = "[" + LEAK * 50 + "{" + LEAK
        self.assert_safe_failure("summarize", raw)

    def test_unexpected_plain_response_cannot_enter_error(self):
        raw = LEAK + " unstructured"
        self.assert_safe_failure("score_relevance", raw)

    def test_analyze_error_log_is_redacted_and_failure_counted(self):
        obj = analyzer(BROKEN)
        with self.assertLogs("analysis.analyzer", level="ERROR") as logged:
            result = obj.analyze("新闻标题", "新闻正文")
        self.assertIsNone(result)
        whole_log = "\n".join(logged.output)
        self.assertIn("Relevance scoring failed: JSON parse failed", whole_log)
        self.assertNotIn(LEAK, whole_log)
        self.assertNotIn("Raw output was:", whole_log)
        self.assertEqual(obj.usage.rows()[0]["failed_calls"], 1)

    def test_normal_json_relevance_unchanged(self):
        raw = json.dumps({"score": 0.77, "reasoning": "Routine statement"})
        obj = analyzer(raw)
        value, reason = obj.score_relevance("Title", "Body")
        self.assertEqual(value, 0.77)
        self.assertEqual(reason, "Routine statement")
        self.assertEqual(obj.usage.rows()[0]["succeeded_calls"], 1)

    def test_valid_fenced_json_still_parses(self):
        raw = "    ```json\n" + json.dumps({
            "summary": "Ordinary published summary."
        }) + "\n```   "
        obj = analyzer(raw)
        self.assertEqual(obj.summarize("Title", "Body"),
                         "Ordinary published summary.")
        self.assertEqual(obj.usage.rows()[0]["failed_calls"], 0)

    def test_valid_surrounding_prose_fallback_still_parses(self):
        raw = "Result follows:\n" + json.dumps({
            "score": 0.82, "reasoning": "Standard record"
        }) + "\nEnd."
        obj = analyzer(raw)
        self.assertEqual(obj.score_relevance("Title", "Body")[0], 0.82)

    def test_malformed_exception_message_does_not_include_any_raw_snippet(self):
        raw = "{\"answer\": " + LEAK + "\nlinebreak\n" + LEAK
        obj = analyzer(raw)
        with self.assertRaises(AnalysisError) as cm:
            obj.summarize("Title", "Body")
        message = str(cm.exception)
        for piece in ("answer", LEAK, "linebreak", "Raw output"):
            self.assertNotIn(piece, message)
        self.assertIn("response_chars=%d" % len(raw), message)


if __name__ == "__main__":
    unittest.main()
