"""No-network tests for source-bounded automatic Briefs writing."""
from __future__ import annotations

import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from scripts.weekly_briefs_auto_writer import (
    choose_evidence, compose, validate_manuscript, MAX_RECORDS,
)


class FakeRecord(dict):
    def __getitem__(self, key):
        return dict.__getitem__(self, key)


def evidence():
    return [
        (FakeRecord(id=1, desk_id="china", analyzed_at="2026-10-09", is_significant=1,
                    published_date="2026-10-08", source_language_tag="zh-Hans",
                    text_english="A" * 600, text_original="原" * 600,
                    source_name="Agency A", title_english="Example China development",
                    title_original="Original", url="https://example.com/1"), "A" * 600),
        (FakeRecord(id=2, desk_id="singapore", analyzed_at=None, is_significant=0,
                    published_date="2026-10-08", source_language_tag="en",
                    text_english=None, text_original="B" * 600,
                    source_name="Agency B", title_english="Example Singapore development",
                    title_original="Example Singapore development",
                    url="https://example.com/2"), "B" * 600),
    ]


def valid_manuscript():
    sections = {
        "title": "Official statements around a concrete development",
        "dek": "Two institutions described recent activity differently and within narrow documentary limits.",
        "development": "An official Chinese publication described the development on Thursday, with supporting language in its text.",
        "opening_note": "A source-by-source account of the event makes clear what is documented and what is not established.",
        "what_stood_out": "The record is more important for its specific institutional framing than its size or novelty.",
        "why_it_matters": "This is an account of what the agencies publicized, not a statement of either government's strategic intent.",
        "what_was_routine": "The institutions used familiar wording, although this alone does not establish a broader weekly pattern.",
        "what_im_watching_next": "A later official statement or a source-linked update would help to determine how the narrative develops.",
        "cross_desk_comparison": "The two desks' records provide separate institutional accounts rather than proof of a coordinated policy.",
        "editorial_questions": "Verify original-language wording, consider institutional attribution and check the Saturday updates.",
    }
    sections["citations"] = {
        "development": [1],
        "opening_note": [1, 2],
        "what_stood_out": [1],
        "why_it_matters": [1, 2],
        "what_was_routine": [2],
        "what_im_watching_next": [1],
        "cross_desk_comparison": [1, 2],
    }
    return sections


class WriterContractTests(unittest.TestCase):
    def test_good_manuscript_passes(self):
        result = valid_manuscript()
        self.assertIs(validate_manuscript(result, evidence()), result)

    def test_unknown_citation_refused(self):
        result = valid_manuscript()
        result["citations"]["why_it_matters"] = [999]
        with self.assertRaisesRegex(ValueError, "source ids"):
            validate_manuscript(result, evidence())

    def test_comparison_must_cite_two_desks(self):
        result = valid_manuscript()
        result["citations"]["cross_desk_comparison"] = [1]
        with self.assertRaisesRegex(ValueError, "both desks"):
            validate_manuscript(result, evidence())

    def test_no_legacy_title(self):
        result = valid_manuscript()
        result["title"] = "The PLA Watch: a familiar pattern"
        with self.assertRaisesRegex(ValueError, "legacy series"):
            validate_manuscript(result, evidence())

    def test_friday_window_required_before_db_query(self):
        sidecar = {"week_start": "2026-10-04", "week_ending": "2026-10-10",
                   "desks": ["china", "singapore"], "source_trail": []}
        with self.assertRaises(ValueError):
            choose_evidence(sidecar, as_of="2026-10-10")

    def test_no_model_call_when_evidence_missing(self):
        sidecar = {"week_start": "2026-10-04", "week_ending": "2026-10-10",
                   "desks": ["china", "singapore"], "source_trail": []}
        fake = SimpleNamespace(messages=SimpleNamespace(stream=lambda **kw:
            self.fail("must not call the model")))
        with patch("scripts.weekly_briefs_auto_writer.choose_evidence", side_effect=ValueError("no evidence")):
            with self.assertRaisesRegex(ValueError, "no evidence"):
                compose(sidecar, "2026-10-09", client=fake)

    def test_exactly_one_structured_model_call(self):
        manuscript = valid_manuscript()
        response = SimpleNamespace(
            stop_reason="tool_use",
            content=[SimpleNamespace(type="tool_use", name="compose_editorial_draft", input=manuscript)],
        )
        recorded = []
        fake = SimpleNamespace(messages=SimpleNamespace(stream=lambda **kwargs:
            (recorded.append(kwargs), nullcontext(SimpleNamespace(
                get_final_message=lambda: response)))[1]))
        sidecar = {"week_start": "2026-10-04", "week_ending": "2026-10-10",
                   "desks": ["china", "singapore"], "source_trail": []}
        with patch("scripts.weekly_briefs_auto_writer.choose_evidence", return_value=evidence()):
            self.assertEqual(compose(sidecar, "2026-10-09", client=fake), manuscript)
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]["tool_choice"]["name"], "compose_editorial_draft")
        self.assertNotIn("messages", str(manuscript))
        self.assertLessEqual(MAX_RECORDS, 20)

    def test_model_fails_closed_if_incomplete(self):
        response = SimpleNamespace(stop_reason="max_tokens", content=[])
        fake = SimpleNamespace(messages=SimpleNamespace(stream=lambda **kw:
            nullcontext(SimpleNamespace(get_final_message=lambda: response))))
        sidecar = {"week_start": "2026-10-04", "week_ending": "2026-10-10",
                   "desks": ["china", "singapore"], "source_trail": []}
        with patch("scripts.weekly_briefs_auto_writer.choose_evidence", return_value=evidence()):
            with self.assertRaisesRegex(ValueError, "did not complete"):
                compose(sidecar, "2026-10-09", client=fake)

    def test_stream_timeout_does_not_synthesize_draft(self):
        class BrokenStream:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def get_final_message(self):
                raise TimeoutError("mock API connection timed out")

        fake = SimpleNamespace(messages=SimpleNamespace(stream=lambda **kw: BrokenStream()))
        sidecar = {"week_start": "2026-10-04", "week_ending": "2026-10-10",
                   "desks": ["china", "singapore"], "source_trail": []}
        with patch("scripts.weekly_briefs_auto_writer.choose_evidence", return_value=evidence()):
            with self.assertRaisesRegex(TimeoutError, "timed out"):
                compose(sidecar, "2026-10-09", client=fake)



if __name__ == "__main__":
    unittest.main()
