"""No-network tests for source-bounded automatic Briefs writing."""
from __future__ import annotations

import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from scripts.weekly_briefs_auto_writer import (
    choose_evidence, compose, validate_manuscript, writing_schema, MAX_RECORDS,
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

    def test_schema_limits_every_citation_to_offered_nonempty_ids(self):
        schema = writing_schema([2, 1, 2])
        for section in ("development", "opening_note", "what_stood_out",
                        "why_it_matters", "what_was_routine", "what_im_watching_next",
                        "cross_desk_comparison"):
            field = schema["properties"]["citations"]["properties"][section]
            self.assertEqual(field["items"]["enum"], [1, 2])
            self.assertEqual(field["minItems"], 1)
            self.assertIs(field["uniqueItems"], True)
        with self.assertRaisesRegex(ValueError, "citation vocabulary"):
            writing_schema([])
        with self.assertRaisesRegex(ValueError, "citation vocabulary"):
            writing_schema([True])

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

    def test_non_friday_saturday_cutoff_refused_before_db_query(self):
        sidecar = {"week_start": "2026-10-04", "week_ending": "2026-10-10",
                   "desks": ["china", "singapore"], "source_trail": []}
        for cutoff in ("2026-10-08", "2026-10-11"):
            with self.subTest(cutoff=cutoff):
                with self.assertRaisesRegex(ValueError, "Friday or Saturday"):
                    choose_evidence(sidecar, as_of=cutoff)

    def test_saturday_cutoff_uses_complete_week_readonly_selection(self):
        sidecar = {"week_start": "2026-10-04", "week_ending": "2026-10-10",
                   "desks": ["china", "singapore"],
                   "source_trail": [{"record_id": 1}, {"record_id": 2}]}
        with patch("scripts.weekly_briefs_auto_writer.read_only",
                   return_value=nullcontext("DB")) as read, \
             patch("scripts.weekly_briefs_auto_writer.get_articles_for_desks",
                   return_value=[x[0] for x in evidence()]) as rows, \
             patch("scripts.weekly_briefs_auto_writer.trail_entry",
                   side_effect=lambda row: {"record_id": row["id"]}):
            chosen = choose_evidence(sidecar, as_of="2026-10-10", db="/tmp/fake.db")
        self.assertEqual({row["desk_id"] for row, _ in chosen}, {"china", "singapore"})
        rows.assert_called_once_with(
            "2026-10-04", "2026-10-10",
            ["china", "singapore"], conn="DB",
        )
        read.assert_called_once()

    def test_sunday_draft_prompt_does_not_call_week_unfinished(self):
        data = valid_manuscript()
        response = SimpleNamespace(
            stop_reason="tool_use",
            content=[SimpleNamespace(type="tool_use",
                                     name="compose_editorial_draft", input=data)],
        )
        calls = []
        fake = SimpleNamespace(messages=SimpleNamespace(stream=lambda **kw:
            (calls.append(kw), nullcontext(SimpleNamespace(
                get_final_message=lambda: response)))[1]))
        sidecar = {"week_start": "2026-10-04", "week_ending": "2026-10-10",
                   "desks": ["china", "singapore"], "source_trail": []}
        with patch("scripts.weekly_briefs_auto_writer.choose_evidence",
                   return_value=evidence()):
            compose(sidecar, "2026-10-10", client=fake)
        prompt = calls[0]["messages"][0]["content"]
        self.assertIn("SUNDAY DRAFT", prompt)
        self.assertIn("source-capture completeness", prompt)
        self.assertNotIn("Saturday 2026-10-10 has not elapsed", prompt)

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
        schema = recorded[0]["tools"][0]["input_schema"]
        self.assertEqual(schema["properties"]["citations"]["properties"]["opening_note"]["items"]["enum"], [1, 2])
        self.assertIn("The only allowed record IDs are 1, 2.", recorded[0]["messages"][0]["content"])
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

    def test_invalid_citations_regenerated_once_then_accepted(self):
        bad = valid_manuscript()
        bad["citations"]["opening_note"] = [999]
        good = valid_manuscript()
        inputs = [bad, good]
        calls = []

        def stream(**kwargs):
            calls.append(kwargs)
            content = inputs.pop(0)
            response = SimpleNamespace(
                stop_reason="tool_use",
                content=[SimpleNamespace(type="tool_use", name="compose_editorial_draft", input=content)],
            )
            return nullcontext(SimpleNamespace(get_final_message=lambda: response))

        fake = SimpleNamespace(messages=SimpleNamespace(stream=stream))
        sidecar = {"week_start": "2026-10-04", "week_ending": "2026-10-10",
                   "desks": ["china", "singapore"], "source_trail": []}
        with patch("scripts.weekly_briefs_auto_writer.choose_evidence", return_value=evidence()):
            self.assertEqual(compose(sidecar, "2026-10-09", client=fake), good)
        self.assertEqual(len(calls), 2)
        self.assertIn("PREVIOUS DRAFT WAS REJECTED", calls[1]["messages"][0]["content"])
        self.assertNotIn("PREVIOUS DRAFT WAS REJECTED", calls[0]["messages"][0]["content"])

    def test_invalid_citations_refused_after_two_attempts(self):
        calls = []

        def stream(**kwargs):
            calls.append(kwargs)
            bad = valid_manuscript()
            bad["citations"]["opening_note"] = []
            response = SimpleNamespace(
                stop_reason="tool_use",
                content=[SimpleNamespace(type="tool_use", name="compose_editorial_draft", input=bad)],
            )
            return nullcontext(SimpleNamespace(get_final_message=lambda: response))

        fake = SimpleNamespace(messages=SimpleNamespace(stream=stream))
        sidecar = {"week_start": "2026-10-04", "week_ending": "2026-10-10",
                   "desks": ["china", "singapore"], "source_trail": []}
        with patch("scripts.weekly_briefs_auto_writer.choose_evidence", return_value=evidence()):
            with self.assertRaisesRegex(ValueError, "opening_note"):
                compose(sidecar, "2026-10-09", client=fake)
        self.assertEqual(len(calls), 2)

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
