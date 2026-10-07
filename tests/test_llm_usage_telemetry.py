"""
Run-level LLM usage telemetry (analysis/usage.py, analysis/pricing.py).

Operational accounting only. These tests pin two things: that the counters and
the estimate are right, and that adding them changed nothing the analysis
sends, stores or raises. No provider is contacted and no database is opened —
every response is a scripted stand-in.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import sys
import tempfile
import threading
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import anthropic
import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily_update.yml"
PIPELINE = REPO_ROOT / "pipeline.py"

SONNET = "claude-sonnet-4-6"
HAIKU = "claude-haiku-4-5-20251001"

RELEVANCE_JSON = json.dumps({"score": 0.9, "reasoning": "scripted"})
SUMMARY_JSON = json.dumps({"summary": "Scripted summary."})
CATEGORY_JSON = json.dumps({"categories": ["taiwan"], "significance": False,
                            "significance_reason": None})


def usage(i=0, o=0, cw=0, cr=0):
    return SimpleNamespace(input_tokens=i, output_tokens=o,
                           cache_creation_input_tokens=cw,
                           cache_read_input_tokens=cr)


def text_response(text, u=None, stop="end_turn"):
    return SimpleNamespace(content=[SimpleNamespace(text=text)],
                           stop_reason=stop, usage=u)


def tool_response(payload, u=None, stop="end_turn", name="emit_translation"):
    block = SimpleNamespace(type="tool_use", name=name, input=payload)
    return SimpleNamespace(content=[block], stop_reason=stop, usage=u)


class _Stream:
    def __init__(self, response):
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._response


class FakeClient:
    """
    `messages.create` and `messages.stream` answer from a script. A scripted
    item that is an exception is raised instead of returned.
    """

    def __init__(self, creates=(), streams=()):
        self.creates, self.streams = list(creates), list(streams)
        self.create_kwargs, self.stream_kwargs = [], []
        self.messages = self

    def create(self, **kwargs):
        self.create_kwargs.append(kwargs)
        item = self.creates.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def stream(self, **kwargs):
        self.stream_kwargs.append(kwargs)
        item = self.streams.pop(0)
        if isinstance(item, BaseException):
            raise item
        return _Stream(item)


def analyzer_for(client):
    """Built as the existing tests build it: `__new__`, only `_client` set."""
    from analysis.analyzer import Analyzer
    a = Analyzer.__new__(Analyzer)
    a._client = client
    return a


def rows_by_task(analyzer):
    return {r["task"]: r for r in analyzer.usage.rows()}


_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def status_error(code, message="boom"):
    return anthropic.APIStatusError(
        message, response=httpx.Response(code, request=_REQUEST), body=None)


class TestASuccessfulCallIsCounted(unittest.TestCase):

    def test_calls_successes_and_all_four_token_fields_are_recorded(self):
        a = analyzer_for(FakeClient(creates=[
            text_response(RELEVANCE_JSON, usage(1200, 55, 30, 400))]))
        a.score_relevance("title", "body")
        row = rows_by_task(a)["relevance"]
        self.assertEqual(row["model"], HAIKU)
        self.assertEqual(
            {k: row[k] for k in ("calls", "succeeded_calls", "failed_calls",
                                 "input_tokens", "output_tokens",
                                 "cache_creation_input_tokens",
                                 "cache_read_input_tokens")},
            {"calls": 1, "succeeded_calls": 1, "failed_calls": 0,
             "input_tokens": 1200, "output_tokens": 55,
             "cache_creation_input_tokens": 30, "cache_read_input_tokens": 400})

    def test_the_streamed_forced_tool_call_is_counted_as_translation(self):
        a = analyzer_for(FakeClient(streams=[tool_response(
            {"title_en": "T", "body_en": "B"}, usage(900, 1500))]))
        self.assertEqual(a.translate("标题", "正文"), ("T", "B"))
        row = rows_by_task(a)["translation"]
        self.assertEqual((row["model"], row["calls"], row["succeeded_calls"],
                          row["input_tokens"], row["output_tokens"]),
                         (SONNET, 1, 1, 900, 1500))

    def test_a_response_without_a_usage_object_is_a_success_with_no_tokens(self):
        a = analyzer_for(FakeClient(creates=[text_response(RELEVANCE_JSON)]))
        a.score_relevance("t", "b")
        row = rows_by_task(a)["relevance"]
        self.assertEqual((row["succeeded_calls"], row["input_tokens"],
                          row["output_tokens"]), (1, 0, 0))


class TestAFailedCallIsCountedWithoutInventingTokens(unittest.TestCase):

    def assertFailedNoTokens(self, row):
        self.assertEqual((row["calls"], row["succeeded_calls"],
                          row["failed_calls"]), (1, 0, 1))
        for k in ("input_tokens", "output_tokens",
                  "cache_creation_input_tokens", "cache_read_input_tokens"):
            self.assertEqual(row[k], 0, k)

    def test_an_api_status_error_before_any_response(self):
        from analysis.analyzer import AnalysisError, FatalAPIError
        a = analyzer_for(FakeClient(creates=[status_error(500)]))
        with self.assertRaises(AnalysisError) as cm:
            a.score_relevance("t", "b")
        self.assertNotIsInstance(cm.exception, FatalAPIError)
        self.assertFailedNoTokens(rows_by_task(a)["relevance"])

    def test_a_connection_error_before_any_response(self):
        from analysis.analyzer import AnalysisError
        a = analyzer_for(FakeClient(
            creates=[anthropic.APIConnectionError(request=_REQUEST)]))
        with self.assertRaises(AnalysisError):
            a.score_relevance("t", "b")
        self.assertFailedNoTokens(rows_by_task(a)["relevance"])

    def test_an_account_level_block_is_still_fatal_and_still_counted(self):
        from analysis.analyzer import FatalAPIError
        a = analyzer_for(FakeClient(creates=[status_error(402)]))
        with self.assertRaises(FatalAPIError):
            a.score_relevance("t", "b")
        self.assertFailedNoTokens(rows_by_task(a)["relevance"])

    def test_the_streamed_path_counts_a_failure_too(self):
        from analysis.analyzer import FatalAPIError
        a = analyzer_for(FakeClient(streams=[status_error(403)]))
        with self.assertRaises(FatalAPIError):
            a.translate("t", "b")
        self.assertFailedNoTokens(rows_by_task(a)["translation"])

    def test_an_unexpected_exception_propagates_unchanged_and_is_counted(self):
        a = analyzer_for(FakeClient(creates=[RuntimeError("not an sdk error")]))
        with self.assertRaises(RuntimeError):
            a.score_relevance("t", "b")
        self.assertFailedNoTokens(rows_by_task(a)["relevance"])

    def test_a_truncated_response_keeps_its_reported_tokens_and_is_failed(self):
        from analysis.analyzer import AnalysisError
        a = analyzer_for(FakeClient(creates=[
            text_response("{", usage(800, 1000), stop="max_tokens")]))
        with self.assertRaisesRegex(AnalysisError, "truncated"):
            a.summarize("t", "b")
        row = rows_by_task(a)["summary"]
        self.assertEqual((row["calls"], row["succeeded_calls"],
                          row["failed_calls"], row["input_tokens"],
                          row["output_tokens"]), (1, 0, 1, 800, 1000))

    def test_a_truncated_tool_call_keeps_its_tokens_and_is_failed(self):
        from analysis.analyzer import AnalysisError
        a = analyzer_for(FakeClient(streams=[tool_response(
            {"title_en": "T"}, usage(10, 32000), stop="max_tokens")]))
        with self.assertRaisesRegex(AnalysisError, "truncated"):
            a.translate("t", "b")
        row = rows_by_task(a)["translation"]
        self.assertEqual((row["succeeded_calls"], row["failed_calls"],
                          row["output_tokens"]), (0, 1, 32000))

    def test_a_tool_call_that_returns_no_tool_block_is_failed(self):
        from analysis.analyzer import AnalysisError
        a = analyzer_for(FakeClient(streams=[
            SimpleNamespace(content=[], stop_reason="end_turn",
                            usage=usage(10, 5))]))
        with self.assertRaisesRegex(AnalysisError, "no `emit_translation`"):
            a.translate("t", "b")
        row = rows_by_task(a)["translation"]
        self.assertEqual((row["succeeded_calls"], row["failed_calls"],
                          row["output_tokens"]), (0, 1, 5))

    def test_output_that_does_not_parse_is_failed_with_its_tokens(self):
        from analysis.analyzer import AnalysisError
        a = analyzer_for(FakeClient(creates=[
            text_response("not json at all", usage(500, 40))]))
        with self.assertRaisesRegex(AnalysisError, "JSON parse failed"):
            a.categorize("t", "b")
        row = rows_by_task(a)["categorization"]
        self.assertEqual((row["calls"], row["succeeded_calls"],
                          row["failed_calls"], row["input_tokens"],
                          row["output_tokens"]), (1, 0, 1, 500, 40))

    def test_an_empty_translation_is_failed_with_its_tokens(self):
        from analysis.analyzer import AnalysisError
        a = analyzer_for(FakeClient(streams=[tool_response(
            {"title_en": "", "body_en": ""}, usage(70, 9))]))
        with self.assertRaisesRegex(AnalysisError, "empty title_en"):
            a.translate("t", "b")
        row = rows_by_task(a)["translation"]
        self.assertEqual((row["succeeded_calls"], row["failed_calls"],
                          row["output_tokens"]), (0, 1, 9))


class TestTasksAreSeparate(unittest.TestCase):

    def test_relevance_and_summary_aggregate_independently(self):
        a = analyzer_for(FakeClient(creates=[
            text_response(RELEVANCE_JSON, usage(100, 10)),
            text_response(RELEVANCE_JSON, usage(300, 30)),
            text_response(SUMMARY_JSON, usage(1000, 200)),
        ]))
        a.score_relevance("t", "b")
        a.score_relevance("t", "b")
        a.summarize("t", "b")
        rows = rows_by_task(a)
        self.assertEqual((rows["relevance"]["model"], rows["relevance"]["calls"],
                          rows["relevance"]["input_tokens"],
                          rows["relevance"]["output_tokens"]),
                         (HAIKU, 2, 400, 40))
        self.assertEqual((rows["summary"]["model"], rows["summary"]["calls"],
                          rows["summary"]["input_tokens"],
                          rows["summary"]["output_tokens"]),
                         (SONNET, 1, 1000, 200))
        self.assertEqual(set(rows), {"relevance", "summary"})

    def test_a_full_analysis_records_exactly_one_call_per_task(self):
        client = FakeClient(
            creates=[], streams=[tool_response(
                {"title_en": "T", "body_en": "B"}, usage(900, 1500))])

        def create(**kwargs):
            client.create_kwargs.append(kwargs)
            prompt = kwargs["messages"][0]["content"]
            if kwargs["model"] == HAIKU:
                return text_response(RELEVANCE_JSON, usage(1500, 50))
            if prompt.startswith("Write a two to three"):
                return text_response(SUMMARY_JSON, usage(2000, 220))
            return text_response(CATEGORY_JSON, usage(1900, 60))

        client.create = create
        a = analyzer_for(client)
        result = a.analyze("标题", "正文")
        self.assertTrue(result["passed_relevance"])
        self.assertEqual(result["summary_english"], "Scripted summary.")
        rows = a.usage.rows()
        self.assertEqual([(r["task"], r["model"], r["calls"]) for r in rows],
                         [("relevance", HAIKU, 1), ("translation", SONNET, 1),
                          ("summary", SONNET, 1), ("categorization", SONNET, 1)])


class TestRequestsAreUnchanged(unittest.TestCase):
    """The task label names a ledger row; it must not reach the API."""

    def test_create_and_stream_receive_exactly_the_keys_they_always_did(self):
        from analysis.analyzer import Analyzer
        client = FakeClient(
            creates=[text_response(RELEVANCE_JSON, usage(1, 1))],
            streams=[tool_response({"title_en": "T", "body_en": "B"})])
        a = analyzer_for(client)
        a.score_relevance("t", "b")
        a.translate("t", "b")
        sent = client.create_kwargs[0]
        self.assertEqual(set(sent), {"model", "system", "messages",
                                     "max_tokens", "temperature"})
        self.assertIs(sent["system"], Analyzer._SYSTEM_WITH_CACHE)
        self.assertEqual(set(client.stream_kwargs[0]),
                         {"model", "system", "messages", "max_tokens",
                          "temperature", "tools", "tool_choice"})

    def test_an_analyzer_built_with_new_still_gets_a_working_ledger(self):
        a = analyzer_for(FakeClient())
        self.assertEqual(a.usage.rows(), [])
        self.assertIs(a.usage, a.usage)


class TestCostEstimate(unittest.TestCase):

    def test_the_pinned_rates_are_the_verified_ones(self):
        from analysis import pricing
        self.assertEqual(pricing.PRICING_USD_PER_MTOK[SONNET],
                         {"input": 3.00, "output": 15.00})
        self.assertEqual(pricing.PRICING_USD_PER_MTOK[HAIKU],
                         {"input": 1.00, "output": 5.00})
        self.assertEqual(pricing.CACHE_WRITE_5M_MULTIPLIER, 1.25)
        self.assertEqual(pricing.CACHE_READ_MULTIPLIER, 0.10)

    def test_the_spend_guard_reads_the_same_table(self):
        from analysis import pricing
        from scripts import spend_guard
        self.assertIs(spend_guard.PRICING_USD_PER_MTOK,
                      pricing.PRICING_USD_PER_MTOK)

    def test_deterministic_usage_gives_the_expected_estimate(self):
        from analysis.pricing import estimate_usage_cost_usd as cost
        # Sonnet: 1000*3 + 500*15 + 200*3*1.25 + 4000*3*0.1 = 12,450 / 1e6
        self.assertAlmostEqual(cost(SONNET, 1000, 500, 200, 4000), 0.01245, 9)
        # Haiku: 2000*1 + 100*5 = 2,500 / 1e6
        self.assertAlmostEqual(cost(HAIKU, 2000, 100), 0.0025, 9)

    def test_an_unpriced_model_has_no_estimate_and_is_named_in_the_record(self):
        from analysis.pricing import estimate_usage_cost_usd
        from analysis.usage import UsageLedger, build_run_record
        self.assertIsNone(estimate_usage_cost_usd("claude-not-priced", 1, 1))
        ledger = UsageLedger()
        ledger.record_response("summary", "claude-not-priced", usage(10, 10))
        ledger.record_response("relevance", HAIKU, usage(2000, 100))
        rec = build_run_record(ledger, **RUN_FIELDS)
        self.assertEqual(rec["unpriced_models"], ["claude-not-priced"])
        self.assertAlmostEqual(rec["estimated_cost_usd"], 0.0025, 9)
        by_task = {t["task"]: t for t in rec["tasks"]}
        self.assertIsNone(by_task["summary"]["estimated_cost_usd"])


RUN_FIELDS = dict(run_date="2026-10-01", recorded_at="2026-10-01T14:00:00+00:00",
                  run_status="completed", analysis_model=SONNET,
                  relevance_model=HAIKU, articles_queued=5,
                  articles_fully_analyzed=4)


def sample_ledger():
    from analysis.usage import UsageLedger
    ledger = UsageLedger()
    ledger.record_response("relevance", HAIKU, usage(2000, 100))
    ledger.record_response("translation", SONNET, usage(1000, 500, 200, 4000))
    ledger.record_failure("summary", SONNET)
    return ledger


class TestCostPerAnalyzedArticle(unittest.TestCase):

    def test_it_is_the_total_divided_by_the_fully_analyzed_count(self):
        from analysis.usage import build_run_record
        rec = build_run_record(sample_ledger(), **RUN_FIELDS)   # N = 4
        self.assertAlmostEqual(rec["estimated_cost_usd"], 0.01495, 9)
        self.assertAlmostEqual(
            rec["estimated_cost_per_analyzed_article_usd"], 0.01495 / 4, 5)

    def test_it_is_null_when_nothing_was_fully_analyzed(self):
        from analysis.usage import build_run_record
        rec = build_run_record(sample_ledger(),
                               **{**RUN_FIELDS, "articles_fully_analyzed": 0})
        self.assertIsNone(rec["estimated_cost_per_analyzed_article_usd"])
        self.assertGreater(rec["estimated_cost_usd"], 0)   # the spend is still there


class TestSerialization(unittest.TestCase):

    TOP = ["schema_version", "run_date", "recorded_at", "run_status",
           "analysis_model", "relevance_model", "articles_queued",
           "articles_fully_analyzed", "calls", "succeeded_calls",
           "failed_calls", "input_tokens", "output_tokens",
           "cache_creation_input_tokens", "cache_read_input_tokens",
           "estimated_cost_usd", "estimated_cost_per_analyzed_article_usd",
           "unpriced_models", "pricing_checked", "tasks"]
    TASK = ["task", "model", "calls", "succeeded_calls", "failed_calls",
            "input_tokens", "output_tokens", "cache_creation_input_tokens",
            "cache_read_input_tokens", "estimated_cost_usd"]

    def test_the_record_schema_and_totals(self):
        from analysis.usage import build_run_record
        rec = build_run_record(sample_ledger(), **RUN_FIELDS)
        self.assertEqual(list(rec), self.TOP)
        self.assertEqual(rec["schema_version"], 1)
        for t in rec["tasks"]:
            self.assertEqual(list(t), self.TASK)
        self.assertEqual([t["task"] for t in rec["tasks"]],
                         ["relevance", "translation", "summary"])
        self.assertEqual((rec["calls"], rec["succeeded_calls"],
                          rec["failed_calls"]), (3, 2, 1))
        self.assertEqual((rec["input_tokens"], rec["output_tokens"],
                          rec["cache_creation_input_tokens"],
                          rec["cache_read_input_tokens"]),
                         (3000, 600, 200, 4000))

    def test_the_log_is_append_only_jsonl_one_object_per_run(self):
        from analysis.usage import append_run_record, build_run_record
        rec = build_run_record(sample_ledger(), **RUN_FIELDS)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "llm_usage.jsonl"   # parent is created
            append_run_record(rec, str(path))
            append_run_record({**rec, "run_date": "2026-10-02"}, str(path))
            lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0]), rec)
        self.assertEqual(json.loads(lines[1])["run_date"], "2026-10-02")

    def test_the_summary_block_names_every_figure_the_brief_asks_for(self):
        from analysis.usage import build_run_record, format_run_summary
        text = format_run_summary(build_run_record(sample_ledger(), **RUN_FIELDS))
        for needle in ("calls: 3", "1 failed", "in=3,000", "out=600",
                       "cache_write=200", "cache_read=4,000", "$0.0149",
                       "fully analyzed: 4", "per analyzed article: $0.0037",
                       "relevance", "translation", "summary", HAIKU, SONNET):
            self.assertIn(needle, text)


class TestNoContentLeaks(unittest.TestCase):

    def test_a_full_run_record_carries_no_article_prompt_or_key_text(self):
        from analysis.usage import build_run_record
        sentinels = ("SENTINEL-TITLE-9f3", "SENTINEL-BODY-7c1",
                     "SENTINEL-TRANSLATION-2d8", "https://example.test/secret-url")
        client = FakeClient(streams=[tool_response(
            {"title_en": sentinels[2], "body_en": sentinels[2]}, usage(9, 9))])

        def create(**kwargs):
            if kwargs["model"] == HAIKU:
                return text_response(RELEVANCE_JSON, usage(5, 5))
            if kwargs["messages"][0]["content"].startswith("Write a two"):
                return text_response(SUMMARY_JSON, usage(5, 5))
            return text_response(CATEGORY_JSON, usage(5, 5))

        client.create = create
        a = analyzer_for(client)
        a.analyze(sentinels[0] + sentinels[3], sentinels[1])
        text = json.dumps(build_run_record(a.usage, **RUN_FIELDS))
        for s in sentinels:
            self.assertNotIn(s, text)
        self.assertNotIn("Scripted summary", text)
        self.assertNotIn("You are an analyst", text)        # the system prompt
        self.assertIsNone(re.search(r"https?://", text))
        from config import ANTHROPIC_API_KEY
        if ANTHROPIC_API_KEY:
            self.assertNotIn(ANTHROPIC_API_KEY, text)

    def test_every_value_in_a_record_is_a_number_label_or_known_enum(self):
        from analysis.usage import build_run_record
        rec = build_run_record(sample_ledger(), **RUN_FIELDS)
        strings = {rec[k] for k in ("run_date", "recorded_at", "run_status",
                                    "analysis_model", "relevance_model",
                                    "pricing_checked")}
        strings |= {t["task"] for t in rec["tasks"]} | {t["model"] for t in rec["tasks"]}
        self.assertTrue(all(len(s) < 40 for s in strings), strings)


class TestRuntimeRecord(unittest.TestCase):
    """The pipeline's side: one runtime file or log-only, never a tracked file."""

    @contextlib.contextmanager
    def in_tmp_cwd(self):
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                yield Path(tmp)
            finally:
                os.chdir(old)

    def call(self, analyzer, record_path=None):
        import pipeline
        from analysis.usage import RECORD_PATH_ENV
        env = {RECORD_PATH_ENV: record_path} if record_path else {}
        with mock.patch.dict(os.environ, env):
            if not record_path:
                os.environ.pop(RECORD_PATH_ENV, None)
            pipeline._record_llm_usage(analyzer, run_status="completed",
                                       articles_queued=5, articles_fully_analyzed=4)

    def test_it_writes_one_record_to_the_runtime_path_and_nothing_else(self):
        from analysis.usage import load_run_record
        with self.in_tmp_cwd() as tmp:
            target = tmp / "runner_temp" / "llm_usage_record.json"   # parent is created
            self.call(SimpleNamespace(usage=sample_ledger()), str(target))
            rec = load_run_record(str(target))
            leftovers = sorted(p.name for p in target.parent.iterdir())
        self.assertEqual((rec["articles_fully_analyzed"], rec["run_status"]),
                         (4, "completed"))
        self.assertRegex(rec["run_date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(leftovers, ["llm_usage_record.json"])      # no .tmp debris

    def test_unset_means_log_only_and_writes_no_file_anywhere(self):
        with self.in_tmp_cwd() as tmp:
            with self.assertLogs("analysis.usage", level="INFO") as logs:
                self.call(SimpleNamespace(usage=sample_ledger()))
            self.assertEqual(list(tmp.rglob("*")), [])
        text = "\n".join(logs.output)
        self.assertIn("LLM usage this run", text)        # the summary still logs
        self.assertIn("not written", text)

    def test_a_second_write_replaces_the_first_so_the_file_holds_one_object(self):
        from analysis.usage import build_run_record, load_run_record, write_run_record
        rec = build_run_record(sample_ledger(), **RUN_FIELDS)
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "r.json")
            write_run_record(rec, path)
            write_run_record({**rec, "run_date": "2026-10-02"}, path)
            self.assertEqual(load_run_record(path)["run_date"], "2026-10-02")
            self.assertEqual(len(Path(path).read_text().splitlines()), 1)

    def test_a_persistence_failure_warns_and_never_raises(self):
        with self.in_tmp_cwd() as tmp, mock.patch(
                "analysis.usage.write_run_record", side_effect=OSError("disk")):
            with self.assertLogs("analysis.usage", level=logging.WARNING) as logs:
                self.call(SimpleNamespace(usage=sample_ledger()),
                          str(tmp / "r.json"))
        self.assertIn("NOT persisted", "\n".join(logs.output))

    def test_a_serialization_failure_warns_and_never_raises(self):
        with self.in_tmp_cwd(), mock.patch(
                "analysis.usage.build_run_record", side_effect=ValueError("bad")):
            with self.assertLogs("analysis.usage", level=logging.WARNING):
                self.call(SimpleNamespace(usage=sample_ledger()))

    def test_a_broken_analyzer_object_warns_and_never_raises(self):
        with self.in_tmp_cwd():
            with self.assertLogs("pipeline", level=logging.WARNING):
                self.call(SimpleNamespace())          # no `.usage` at all

    def test_the_hook_runs_after_the_run_record_closes_and_before_the_summary(self):
        src = PIPELINE.read_text(encoding="utf-8")
        closed = src.index("db.complete_scrape_run(")
        hook = src.index("_record_llm_usage(analyzer,")
        summary = src.rindex("_print_summary(all_scraped")
        self.assertLess(closed, hook)
        self.assertLess(hook, summary)
        self.assertIn("analyzer is not None", src[hook - 120:hook])

    def test_the_pipeline_side_never_names_the_tracked_history(self):
        import inspect
        from analysis import usage
        self.assertNotIn("llm_usage.jsonl", PIPELINE.read_text(encoding="utf-8"))
        self.assertNotIn("USAGE_LOG_PATH", PIPELINE.read_text(encoding="utf-8"))
        self.assertNotIn("USAGE_LOG_PATH", inspect.getsource(usage.record_run_usage))
        self.assertNotIn("USAGE_LOG_PATH", inspect.getsource(usage.write_run_record))


class TestLoadAndAppend(unittest.TestCase):
    """The workflow step's side: runtime record in, one appended line out."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        from analysis.usage import build_run_record, write_run_record
        self.rec = build_run_record(sample_ledger(), **RUN_FIELDS)
        self.runtime = self.tmp / "llm_usage_record.json"
        write_run_record(self.rec, str(self.runtime))
        self.tracked = self.tmp / "state" / "llm_usage.jsonl"

    def run_script(self, *argv):
        from scripts import append_llm_usage
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), \
                contextlib.redirect_stderr(sink):
            return append_llm_usage.main(["append_llm_usage.py", *argv])

    def test_the_record_round_trips_unchanged(self):
        from analysis.usage import load_run_record
        self.assertEqual(load_run_record(str(self.runtime)), self.rec)

    def test_it_appends_exactly_that_object_as_one_line(self):
        self.assertEqual(self.run_script(str(self.runtime), str(self.tracked)), 0)
        lines = self.tracked.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0]), self.rec)
        self.assertEqual(list(json.loads(lines[0])), list(self.rec))   # key order too

    def test_earlier_history_is_preserved_byte_for_byte(self):
        self.tracked.parent.mkdir(parents=True)
        history = '{"schema_version":1,"run_date":"2026-09-30","tasks":[]}\n'
        self.tracked.write_text(history, encoding="utf-8")
        self.assertEqual(self.run_script(str(self.runtime), str(self.tracked)), 0)
        text = self.tracked.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(history))
        self.assertEqual(len(text.splitlines()), 2)

    def test_a_history_missing_its_final_newline_is_not_fused_with_the_new_line(self):
        self.tracked.parent.mkdir(parents=True)
        self.tracked.write_text('{"run_date":"2026-09-30"}', encoding="utf-8")
        self.assertEqual(self.run_script(str(self.runtime), str(self.tracked)), 0)
        lines = self.tracked.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[1]), self.rec)

    def test_the_runtime_record_is_left_alone(self):
        before = self.runtime.read_bytes()
        self.run_script(str(self.runtime), str(self.tracked))
        self.assertEqual(self.runtime.read_bytes(), before)

    def test_anything_but_one_valid_record_appends_nothing_and_fails(self):
        good = self.runtime.read_text(encoding="utf-8")
        bad = {
            "empty": "",
            "two records": good + good,
            "not json": "{not json\n",
            "a list": "[1, 2]\n",
            "wrong schema": json.dumps({**self.rec, "schema_version": 99}) + "\n",
            "no tasks": json.dumps({k: v for k, v in self.rec.items()
                                    if k != "tasks"}) + "\n",
        }
        for label, content in bad.items():
            self.runtime.write_text(content, encoding="utf-8")
            self.assertEqual(
                self.run_script(str(self.runtime), str(self.tracked)), 1, label)
            self.assertFalse(self.tracked.exists(), label)

    def test_a_missing_runtime_record_appends_nothing_and_fails(self):
        self.assertEqual(
            self.run_script(str(self.tmp / "absent.json"), str(self.tracked)), 1)
        self.assertFalse(self.tracked.exists())

    def test_the_default_destination_is_the_pinned_tracked_path(self):
        from analysis.usage import USAGE_LOG_PATH
        self.assertEqual(USAGE_LOG_PATH, ".github/state/llm_usage.jsonl")


class TestAFatalBlockKeepsUsage(unittest.TestCase):
    """
    The pipeline's real `run()`, a real `Analyzer`, and a fake provider that
    reports tokens and then refuses with an account-level 402.

    The spend that matters most is the spend of a run that did not finish. These
    pin that the record of it is still produced, that it counts the calls that
    completed, that the refused call is failed with no tokens invented, and that
    the pipeline's own failure behavior is exactly what it was.
    """

    #: Tokens each task's fake response reports.
    USAGE = {"relevance": (1000, 50), "translation": (2000, 3000),
             "summary": (500, 100), "categorization": (400, 40)}

    class Provider:
        """`refuse` maps a task to the call number (1-based) that gets a 402."""

        def __init__(self, refuse):
            self.refuse = refuse
            self.counts = Counter()
            self._lock = threading.Lock()
            self.messages = self

        def _answer(self, task, make):
            with self._lock:
                self.counts[task] += 1
                n = self.counts[task]
            if self.refuse.get(task) == n:
                raise status_error(402, "Your credit balance is too low")
            return make(usage(*TestAFatalBlockKeepsUsage.USAGE[task]))

        def create(self, **kwargs):
            if kwargs["model"] == HAIKU:
                return self._answer("relevance",
                                    lambda u: text_response(RELEVANCE_JSON, u))
            if kwargs["messages"][0]["content"].startswith("Write a two"):
                return self._answer("summary",
                                    lambda u: text_response(SUMMARY_JSON, u))
            return self._answer("categorization",
                                lambda u: text_response(CATEGORY_JSON, u))

        def stream(self, **kwargs):
            return _Stream(self._answer("translation", lambda u: tool_response(
                {"title_en": "T", "body_en": "B"}, u)))

    def setUp(self):
        from tests.integration.test_pipeline_run import PipelineRunCase
        self.case = PipelineRunCase("run")
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.record_path = self.case.tmp / "runner_temp" / "llm_usage_record.json"
        self.marker = self.case.tmp / "state" / "billing_marker.txt"
        self.tracked_history = REPO_ROOT / ".github" / "state" / "llm_usage.jsonl"
        self.real_marker = REPO_ROOT / ".github" / "state" / "last_billing_failure_date.txt"
        self.tracked_before = self._snapshot()
        self.renders = 0

    def _snapshot(self):
        return tuple(p.read_bytes() if p.exists() else None
                     for p in (self.tracked_history, self.real_marker))

    @contextlib.contextmanager
    def fake_provider(self, provider):
        """No network: the SDK client constructor returns the fake."""
        import importlib.util as iu
        import pipeline
        from analysis.usage import RECORD_PATH_ENV
        real_spec, real_mod = iu.spec_from_file_location, iu.module_from_spec
        sentinel = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda m: None))

        def render_site():
            self.renders += 1
            return {"mode": "stub", "output_dir": "-"}

        stub = SimpleNamespace(render_site=render_site)
        real_run = pipeline.run
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.dict(
                os.environ, {RECORD_PATH_ENV: str(self.record_path)}))
            stack.enter_context(mock.patch(
                "analysis.analyzer.anthropic.Anthropic", return_value=provider))
            stack.enter_context(mock.patch("analysis.analyzer.ANTHROPIC_API_KEY", "k"))
            stack.enter_context(mock.patch.object(pipeline, "ANTHROPIC_API_KEY", "k"))
            stack.enter_context(mock.patch.object(
                pipeline, "BILLING_FAILURE_STATE_FILE", str(self.marker)))
            # The harness drives run() with no_analysis=True; this run needs analysis.
            stack.enter_context(mock.patch.object(
                pipeline, "run", lambda **kw: real_run(**{**kw, "no_analysis": False})))
            # Stage 14 renders the site; stub it so no output/ is ever written.
            stack.enter_context(mock.patch.object(
                iu, "spec_from_file_location",
                lambda name, *a, **k: sentinel if name == "site_render"
                else real_spec(name, *a, **k)))
            stack.enter_context(mock.patch.object(
                iu, "module_from_spec",
                lambda spec: stub if spec is sentinel else real_mod(spec)))
            yield

    def drive(self, provider):
        from tests.integration.test_pipeline_run import article, scraper_factory
        urls = ["http://www.81.cn/x/a1.html", "http://www.81.cn/x/a2.html"]
        adapters = {"pla_daily": scraper_factory(
            urls=urls, pages={u: "<html/>" for u in urls},
            parsed={u: article(u) for u in urls})}
        with self.fake_provider(provider):
            self.case.run_pipeline(adapters)

    def record(self):
        from analysis.usage import load_run_record
        return load_run_record(str(self.record_path))

    def test_a_refusal_after_completed_calls_exits_2_and_keeps_their_usage(self):
        # Article 1: relevance and translation succeed, the summary is refused
        # while categorization (running in parallel) succeeds. The paid
        # translation is discarded by the pipeline, but it was still paid for.
        provider = self.Provider(refuse={"summary": 1})
        with self.assertRaises(SystemExit) as cm:
            self.drive(provider)
        self.assertEqual(cm.exception.code, 2)                 # existing semantics

        self.assertTrue(self.marker.exists())                  # billing marker still written
        self.assertEqual(self.case.run_status(), "failed")
        self.assertEqual(self.renders, 0)                      # nothing publishable: no render

        rec = self.record()
        self.assertEqual(rec["run_status"], "failed")
        self.assertEqual((rec["articles_queued"], rec["articles_fully_analyzed"]), (2, 0))
        self.assertEqual((rec["calls"], rec["succeeded_calls"], rec["failed_calls"]),
                         (4, 3, 1))
        self.assertEqual((rec["input_tokens"], rec["output_tokens"]),
                         (1000 + 2000 + 400, 50 + 3000 + 40))
        rows = {t["task"]: t for t in rec["tasks"]}
        self.assertEqual(rows["relevance"]["input_tokens"], 1000)
        self.assertEqual(rows["translation"]["output_tokens"], 3000)
        self.assertEqual(rows["categorization"]["input_tokens"], 400)
        refused = rows["summary"]                              # failed, nothing invented
        self.assertEqual((refused["calls"], refused["succeeded_calls"],
                          refused["failed_calls"]), (1, 0, 1))
        self.assertEqual((refused["input_tokens"], refused["output_tokens"],
                          refused["cache_creation_input_tokens"],
                          refused["cache_read_input_tokens"]), (0, 0, 0, 0))
        self.assertIsNone(rec["estimated_cost_per_analyzed_article_usd"])
        self.assertGreater(rec["estimated_cost_usd"], 0)
        self.assertEqual(provider.counts["relevance"], 1)      # aborted: article 2 untouched
        self.assertEqual(self._snapshot(), self.tracked_before)

    def test_a_refusal_on_the_next_article_keeps_the_finished_articles_usage(self):
        # Article 1 completes; article 2's very first call is refused. The run
        # still publishes what it finished (exit 0, "degraded") — and the record
        # must carry the completed article's full spend plus the refused call.
        provider = self.Provider(refuse={"relevance": 2})
        self.drive(provider)                                    # no SystemExit

        self.assertTrue(self.marker.exists())
        self.assertEqual(self.case.run_status(), "degraded")
        self.assertEqual(self.renders, 1)                       # partial work is published

        rec = self.record()
        self.assertEqual(rec["run_status"], "degraded")
        self.assertEqual((rec["articles_queued"], rec["articles_fully_analyzed"]), (2, 1))
        self.assertEqual((rec["calls"], rec["succeeded_calls"], rec["failed_calls"]),
                         (5, 4, 1))
        self.assertEqual((rec["input_tokens"], rec["output_tokens"]),
                         (1000 + 2000 + 500 + 400, 50 + 3000 + 100 + 40))
        rows = {t["task"]: t for t in rec["tasks"]}
        self.assertEqual((rows["relevance"]["calls"], rows["relevance"]["failed_calls"],
                          rows["relevance"]["input_tokens"]), (2, 1, 1000))
        self.assertEqual(rec["estimated_cost_per_analyzed_article_usd"],
                         round(rec["estimated_cost_usd"] / 1, 6))
        self.assertEqual(self._snapshot(), self.tracked_before)

    def test_a_clean_run_records_and_never_touches_a_tracked_file(self):
        self.drive(self.Provider(refuse={}))
        rec = self.record()
        self.assertEqual((rec["run_status"], rec["articles_fully_analyzed"],
                          rec["failed_calls"], rec["calls"]), ("completed", 2, 0, 8))
        self.assertFalse(self.marker.exists())                  # no block, no marker
        self.assertEqual(self._snapshot(), self.tracked_before)

    def test_without_the_env_var_the_run_logs_and_writes_no_record(self):
        provider = self.Provider(refuse={})
        from analysis.usage import RECORD_PATH_ENV
        with mock.patch.dict(os.environ):
            with self.assertLogs("analysis.usage", level="INFO") as logs:
                # fake_provider sets the variable; remove it inside the context
                from tests.integration.test_pipeline_run import article, scraper_factory
                urls = ["http://www.81.cn/x/a1.html"]
                adapters = {"pla_daily": scraper_factory(
                    urls=urls, pages={urls[0]: "<html/>"},
                    parsed={urls[0]: article(urls[0])})}
                with self.fake_provider(provider):
                    os.environ.pop(RECORD_PATH_ENV)
                    self.case.run_pipeline(adapters)
        self.assertIn("LLM usage this run", "\n".join(logs.output))
        self.assertFalse(self.record_path.exists())
        self.assertEqual(self._snapshot(), self.tracked_before)


class TestWorkflowStepScope(unittest.TestCase):

    STEP = "Commit LLM usage telemetry"
    RECORD_ENV = "LLM_USAGE_RECORD_PATH: ${{ runner.temp }}/llm_usage_record.json"

    @classmethod
    def setUpClass(cls):
        text = WORKFLOW.read_text(encoding="utf-8")
        cls.text = text
        # Comments sit between steps and would otherwise be attributed to the
        # step above; only executable lines are asserted on.
        code = "\n".join(l for l in text.splitlines()
                         if not l.lstrip().startswith("#"))
        cls.steps = re.split(r"\n      - name: ", code)[1:]
        cls.names = [s.splitlines()[0].strip() for s in cls.steps]
        cls.body = cls.steps[cls.names.index(cls.STEP)]

    def step(self, name):
        return self.steps[self.names.index(name)]

    def test_the_step_exists_after_publication_and_before_the_health_gate(self):
        n = self.names
        self.assertLess(n.index("Deploy to GitHub Pages"), n.index(self.STEP))
        self.assertLess(n.index("Record successful run"), n.index(self.STEP))
        self.assertLess(n.index(self.STEP), n.index("Health gate"))

    def test_it_stages_only_the_usage_file_and_guards_that(self):
        from analysis.usage import USAGE_LOG_PATH
        self.assertIn(f'FILE="{USAGE_LOG_PATH}"', self.body)
        adds = re.findall(r"^\s*git add (.+)$", self.body, re.M)
        self.assertEqual(adds, ['"$FILE"'])
        self.assertIn('if [ "$STAGED" != "$FILE" ] && [ -n "$STAGED" ]', self.body)
        self.assertRegex(self.body, r"Scope violation[^\n]*\n\s*exit 1")
        for forbidden in ("pla_watch.db", "output/", "--repair", "git add -A",
                          "git add .", "git commit -a", "--force"):
            self.assertNotIn(forbidden, self.body, forbidden)

    def test_it_cannot_turn_a_published_run_red(self):
        self.assertIn("continue-on-error: true", self.body)
        self.assertIn("always()", self.body)
        self.assertIn("steps.pipeline.outcome == 'success'", self.body)
        self.assertIn("steps.pipeline.outcome == 'failure'", self.body)

    def test_it_is_not_gated_by_how_the_run_was_started(self):
        # A manual run spends money too, unlike the billing marker's scheduled-only gate.
        self.assertNotIn("workflow_dispatch", self.body)

    def test_the_runtime_record_lives_under_runner_temp_on_both_steps(self):
        self.assertIn(self.RECORD_ENV, self.step("Run pipeline"))
        self.assertIn(self.RECORD_ENV, self.body)
        self.assertNotIn("github.workspace", self.RECORD_ENV)

    def test_the_tracked_file_is_written_only_inside_the_step_after_the_rebase(self):
        body = self.body
        pull = body.index("git pull --rebase --autostash origin main")
        verify = body.index("python scripts/verify_db_current.py")
        append = body.index('python scripts/append_llm_usage.py "$RECORD" "$FILE"')
        add = body.index('git add "$FILE"')
        self.assertLess(pull, verify)
        self.assertLess(verify, append)
        self.assertLess(append, add)
        # Nothing touches the tracked file before the append: it is clean
        # through the rebase, and the step reads the runtime record instead.
        before_append = body[:append]
        self.assertEqual(before_append.count('"$FILE"'), 0)
        self.assertNotRegex(body, r">>\s*\S*\$FILE|>>\s*\S*llm_usage")
        self.assertIn('RECORD="$LLM_USAGE_RECORD_PATH"', body)

    def test_an_absent_record_is_quiet_unless_the_pipeline_failed(self):
        body = self.body
        self.assertIn("PIPELINE_OUTCOME: ${{ steps.pipeline.outcome }}", body)
        empty = body[body.index('if [ ! -s "$RECORD" ]; then'):
                     body.index("git config user.name")]
        self.assertIn('if [ "$PIPELINE_OUTCOME" = "failure" ]; then', empty)
        self.assertIn("::warning title=LLM usage not recorded::", empty)
        self.assertIn("No LLM usage record this run.", empty)
        self.assertTrue(empty.rstrip().endswith("fi"), empty)
        self.assertIn("exit 0", empty)                  # still never red

    def test_no_step_but_this_one_names_the_tracked_history(self):
        for name, body in zip(self.names, self.steps):
            if name == self.STEP:
                continue
            self.assertNotIn("llm_usage.jsonl", body, name)
            self.assertNotIn("append_llm_usage", body, name)
            if name != "Run pipeline":
                self.assertNotIn("llm_usage", body.lower(), name)

    def test_the_markers_and_the_data_commit_keep_their_scope(self):
        d = dict(zip(self.names, self.steps))
        self.assertIn("git add pla_watch.db output/",
                      d["Commit updated database and site output"])
        self.assertIn("git add .github/state/last_daily_run_date.txt",
                      d["Record successful run"])


if __name__ == "__main__":
    unittest.main()
