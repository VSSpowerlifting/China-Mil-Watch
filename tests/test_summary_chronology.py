"""Synthetic chronology contracts, not model-accuracy tests; no API or DB access."""
import json
import unittest
from unittest.mock import patch

from analysis.analyzer import Analyzer
from analysis.prompts import (
    ANALYSIS_PROMPT_VERSION,
    PROMPT_VERSION,
    SUMMARY_SCHEMA,
    build_summary_messages,
    build_translation_messages,
)
from analysis.usage import TASK_SUMMARY, TASK_TRANSLATION


# Fictional source/translation/summary pairs, never historical record corrections.
# Mocked summaries prove request wiring and output compatibility, not generation.
CASES = (
    ("scheduled", "交流将举行", "10月10日消息，双方将于10月13日举行交流活动。",
     "Exchange to take place", "An October 10 announcement says the two sides will hold an exchange on October 13.",
     "The two sides plan an exchange on October 13. The announcement does not establish completion."),
    ("meeting", "计划会晤", "双方宣布计划于下周会晤。",
     "Meeting planned", "The two sides announced plans to meet next week.",
     "The two sides announced plans to meet next week. The agenda remains unspecified."),
    ("completed", "演习结束", "演习已于昨日结束。",
     "Exercise concluded", "The exercise concluded yesterday.",
     "The exercise concluded yesterday. Its scale is unspecified."),
    ("postponed", "会晤推迟", "原定明日举行的会晤已推迟，新日期尚未确定。",
     "Meeting postponed", "The meeting scheduled for tomorrow has been postponed; no new date has been set.",
     "The meeting scheduled for tomorrow has been postponed. Its new date remains unknown."),
    ("cancelled", "演习取消", "原定下周举行的演习已取消。",
     "Exercise cancelled", "The exercise scheduled for next week has been cancelled.",
     "The exercise scheduled for next week has been cancelled. The announcement gives no reason."),
    ("mixed", "交流与演习", "双方昨日举行交流，并计划下月举行演习。",
     "Exchange and exercise", "The two sides held an exchange yesterday and plan an exercise next month.",
     "The two sides held an exchange yesterday and plan an exercise next month. The exercise's scale is unspecified."),
    ("ambiguous", "演习安排", "演习时间待定。",
     "Exercise arrangements", "The exercise's timing is yet to be determined.",
     "The exercise's timing remains undetermined. The source does not establish that it occurred."),
)


class SummaryChronologyContracts(unittest.TestCase):
    def setUp(self):
        # Bypass SDK initialization; every possible provider entry point is mocked.
        self.analyzer = Analyzer.__new__(Analyzer)

    def test_temporal_contract_in_both_prompts(self):
        translation = build_translation_messages("标题", "正文")[0]["content"]
        summary = build_summary_messages("Title", "Body")[0]["content"]
        for prompt in (translation, summary):
            for instruction in (
                "Preserve event chronology and completion status",
                "planned, scheduled, ongoing, completed, postponed, and cancelled",
                "An announcement of an upcoming activity is not evidence",
                "Never infer completion merely because a scheduled date has passed",
                "ambiguous timing",
            ):
                with self.subTest(instruction=instruction, translation=prompt == translation):
                    self.assertIn(instruction, prompt)
        self.assertIn("将, 将于, 计划, and 将举行", translation)
        self.assertIn("distinguish past events from future plans", summary)
        self.assertIn("conflicting title/body timing", summary)
        self.assertIn("at most about 90 words", summary)
        self.assertEqual(SUMMARY_SCHEMA, {
            "type": "object", "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        })

    def test_synthetic_cases_pass_through_translation_and_summary(self):
        for name, title_zh, body_zh, title_en, body_en, expected in CASES:
            with self.subTest(case=name), patch.object(
                self.analyzer, "_call_tool",
                return_value={"title_en": title_en, "body_en": body_en},
            ) as translate, patch.object(
                self.analyzer, "_call", return_value=json.dumps({"summary": expected}),
            ) as summarize:
                translated = self.analyzer.translate(title_zh, body_zh)
                self.assertEqual(translated, (title_en, body_en))
                self.assertEqual(self.analyzer.summarize(*translated), expected)
                translate.assert_called_once()
                self.assertEqual(translate.call_args.args[0],
                                 build_translation_messages(title_zh, body_zh))
                self.assertEqual(translate.call_args.kwargs["task"], TASK_TRANSLATION)
                summarize.assert_called_once_with(
                    build_summary_messages(title_en, body_en),
                    max_tokens=1000, temperature=0.3, task=TASK_SUMMARY,
                )

    def test_correct_title_does_not_establish_correct_body(self):
        # Deliberately contradictory translation: both fields must reach summary.
        title, body = "Exchange to take place", "The two sides held the exchange."
        with patch.object(self.analyzer, "_call", return_value=json.dumps({
            "summary": "The source's timing is conflicting. Completion remains unestablished.",
        })) as call:
            self.analyzer.summarize(title, body)
        prompt = call.call_args.args[0][0]["content"]
        self.assertIn(f"Title: {title}", prompt)
        self.assertIn(f"Body:\n{body}", prompt)

    def test_no_rejection_rewrite_or_extra_call_for_bad_chronology(self):
        title, body = CASES[0][3:5]
        wrong = "The two sides held the exchange on October 13. It was completed."
        with patch.object(self.analyzer, "_call", return_value=json.dumps({
            "summary": wrong,
        })) as call:
            self.assertEqual(self.analyzer.summarize(title, body), wrong)
        call.assert_called_once()

    def test_full_analysis_versions_changed_bundle_only(self):
        with patch.object(self.analyzer, "score_relevance", return_value=(1.0, "test")), \
             patch.object(self.analyzer, "translate", return_value=CASES[0][3:5]), \
             patch.object(self.analyzer, "summarize", return_value=CASES[0][5]) as summary, \
             patch.object(self.analyzer, "categorize", return_value=([], False, None)):
            result = self.analyzer.analyze(CASES[0][1], CASES[0][2])
        self.assertEqual(result["summary_english"], CASES[0][5])
        self.assertEqual(result["prompt_version"], ANALYSIS_PROMPT_VERSION)
        self.assertEqual(ANALYSIS_PROMPT_VERSION, "v1+chronology-v1")
        summary.assert_called_once_with(*CASES[0][3:5])
        with patch.object(self.analyzer, "score_relevance", return_value=(0.0, "test")), \
             patch.object(self.analyzer, "translate") as translate:
            rejected = self.analyzer.analyze("synthetic", "synthetic")
        translate.assert_not_called()
        self.assertEqual(rejected["prompt_version"], PROMPT_VERSION)
        self.assertEqual(PROMPT_VERSION, "v1")


if __name__ == "__main__":
    unittest.main()
