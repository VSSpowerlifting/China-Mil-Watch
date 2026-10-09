"""Fail-closed translation tool values; no provider, network or DB access."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from analysis.analyzer import AnalysisError, Analyzer
from analysis.usage import TASK_TRANSLATION
from config import ANALYSIS_MODEL


class _Stream:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        block = SimpleNamespace(type="tool_use", name="emit_translation",
                                input=self.payload)
        return SimpleNamespace(content=[block], stop_reason="end_turn",
                               usage=SimpleNamespace(input_tokens=30,
                                                     output_tokens=12,
                                                     cache_read_input_tokens=0,
                                                     cache_creation_input_tokens=0))


class _Client:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        self.messages = self

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return _Stream(self.payload)


def _analyzer(payload):
    analyzer = Analyzer.__new__(Analyzer)
    analyzer._client = _Client(payload)
    return analyzer


def _translation_receipt(analyzer):
    rows = [row for row in analyzer.usage.rows()
            if row["task"] == TASK_TRANSLATION]
    assert len(rows) == 1
    return rows[0]


class TranslationToolValueContracts(unittest.TestCase):
    def assert_invalid(self, payload):
        analyzer = _analyzer(payload)
        with self.assertRaisesRegex(AnalysisError,
                                    "empty title_en or body_en"):
            analyzer.translate("原始标题", "原文正文")
        self.assertEqual(len(analyzer._client.calls), 1)
        receipt = _translation_receipt(analyzer)
        self.assertEqual(receipt["model"], ANALYSIS_MODEL)
        self.assertEqual((receipt["calls"], receipt["succeeded_calls"],
                          receipt["failed_calls"]), (1, 0, 1))
        # Rejecting a returned payload does not erase the consumed tokens.
        self.assertEqual((receipt["input_tokens"], receipt["output_tokens"]),
                         (30, 12))

    def test_null_title_never_becomes_literal_none(self):
        self.assert_invalid({"title_en": None, "body_en": "Valid English prose"})

    def test_null_body_never_becomes_literal_none(self):
        self.assert_invalid({"title_en": "Valid headline", "body_en": None})

    def test_whitespace_only_title_refused(self):
        self.assert_invalid({"title_en": " \t\n ", "body_en": "Valid prose"})

    def test_whitespace_only_body_refused(self):
        self.assert_invalid({"title_en": "Valid headline", "body_en": " \r\n\t "})

    def test_absent_title_refused(self):
        self.assert_invalid({"body_en": "Valid prose"})

    def test_absent_body_refused(self):
        self.assert_invalid({"title_en": "Valid headline"})

    def test_non_string_numeric_title_refused(self):
        self.assert_invalid({"title_en": 147, "body_en": "Valid prose"})

    def test_non_string_boolean_body_refused(self):
        self.assert_invalid({"title_en": "Valid headline", "body_en": False})

    def test_non_string_list_body_refused(self):
        self.assert_invalid({"title_en": "Valid headline", "body_en": ["part"]})

    def test_non_string_dictionary_body_refused(self):
        self.assert_invalid({"title_en": "Valid headline", "body_en": {"p": "x"}})

    def test_valid_translation_preserves_whitespace_and_unicode(self):
        title, body = "\tHeadline — 海军\n", "\n First paragraph.\n\n Second paragraph. \n"
        analyzer = _analyzer({"title_en": title, "body_en": body})
        self.assertEqual(analyzer.translate("原始标题", "原文正文"), (title, body))
        record = _translation_receipt(analyzer)
        self.assertEqual((record["calls"], record["succeeded_calls"],
                          record["failed_calls"]), (1, 1, 0))
        self.assertEqual((record["input_tokens"], record["output_tokens"]),
                         (30, 12))

    def test_valid_tool_call_uses_existing_request_fields(self):
        a = _analyzer({"title_en": "T", "body_en": "B"})
        self.assertEqual(a.translate("原文", "正文"), ("T", "B"))
        self.assertEqual(len(a._client.calls), 1)
        sent = a._client.calls[0]
        self.assertEqual(set(sent), {"model", "system", "messages", "max_tokens",
                                     "temperature", "tools", "tool_choice"})
        self.assertEqual(sent["model"], ANALYSIS_MODEL)
        self.assertEqual(sent["tool_choice"],
                         {"type": "tool", "name": "emit_translation"})
        self.assertTrue(sent["max_tokens"] > 1000)

    def test_analyze_marks_invalid_translation_as_partial_not_complete(self):
        analyzer = _analyzer({"title_en": None, "body_en": "Body"})
        with patch.object(analyzer, "score_relevance",
                          return_value=(0.91, "scripted")):
            result = analyzer.analyze("原标题", "原文正文")
        self.assertTrue(result["passed_relevance"])
        self.assertEqual(result["relevance_score"], 0.91)
        self.assertNotIn("title_english", result)
        self.assertNotIn("summary_english", result)
        self.assertNotIn("text_english", result)
        record = _translation_receipt(analyzer)
        self.assertEqual(record["failed_calls"], 1)


if __name__ == "__main__":
    unittest.main()
