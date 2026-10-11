"""Mock provider matrix at the analyzer's actual raw/tool/stream boundaries."""
from __future__ import annotations

import copy
import json
import threading
import unittest
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest.mock import patch

import anthropic
import httpx

from analysis.admission import (AdmissionController, AdmissionDeferred, ReceiptFailure,
                                exposure, pricing_snapshot, request_exposure)
from analysis.analyzer import Analyzer, AnalysisError, FatalAPIError
from analysis.usage import UsageLedger
from config import ANALYSIS_MODEL, RELEVANCE_MODEL, TRANSLATION_MAX_TOKENS

TASKS = {"relevance": (RELEVANCE_MODEL, 500), "translation": (ANALYSIS_MODEL, TRANSLATION_MAX_TOKENS),
         "summary": (ANALYSIS_MODEL, 1000), "categorization": (ANALYSIS_MODEL, 500)}


def response(usage=True, **changes):
    obj = NS(usage=NS(input_tokens=1000, output_tokens=100,
                      cache_creation_input_tokens=0, cache_read_input_tokens=0) if usage is True else None if usage is False else usage,
             stop_reason="end_turn", content=[NS(type="text", text='{"score":0.9,"reasoning":"FICTIONAL"}')])
    for key, value in changes.items(): setattr(obj, key, value)
    return obj


class MockClient:
    """Faithful request surface with explicit retry options, no network."""
    base_url = "https://api.anthropic.com/"
    default_query = {}
    _custom_headers = {}
    max_retries = 2

    def __init__(self, hook=None):
        self.requests = []
        self.options = []
        self.messages = self
        self.hook = hook
        self._lock = threading.Lock()

    def with_options(self, **kwargs):
        self.options.append(kwargs)
        self.max_retries = kwargs["max_retries"]
        return self

    def create(self, **kwargs):
        with self._lock: self.requests.append(kwargs)
        if self.hook is not None:
            override = self.hook(kwargs)
            if override is not None: return override
        tool = kwargs.get("tools", [{}])[0].get("name")
        if tool == "emit_translation":
            return response(content=[NS(type="tool_use", name=tool, input={"title_en": "FICTIONAL translated title", "body_en": "FICTIONAL translated body"})])
        if tool == "emit_relevance":
            return response(content=[NS(type="tool_use", name=tool, input={"score": .9, "reasoning": "FICTIONAL"})])
        if kwargs["max_tokens"] == 1000:
            return response(content=[NS(type="text", text='{"summary":"FICTIONAL summary"}')])
        if kwargs["model"] == ANALYSIS_MODEL:
            return response(content=[NS(type="text", text='{"categories":["exercises"],"significance":false}')])
        return response()

    def stream(self, **kwargs):
        outer = self
        class Stream:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def get_final_message(self): return outer.create(**kwargs)
        return Stream()


def guarded(budget="24", hook=None, sink=None):
    receipts = []
    guard = AdmissionController(budget, plan_id="plan", execution_id="test", sink=sink or (lambda r: receipts.append(r)))
    analyzer = Analyzer.__new__(Analyzer)
    analyzer._client, analyzer._usage, analyzer._admission = MockClient(hook), UsageLedger(), guard
    return analyzer, guard, receipts


class AdmissionTests(unittest.TestCase):
    def test_complete_article_at_exact_envelope_and_legacy_telemetry(self):
        total = sum(exposure(m, ceiling, pricing_snapshot()) for m, ceiling in TASKS.values())
        analyzer, guard, _ = guarded(str(total))
        analyzer.prepare_article(1)
        result = analyzer.analyze("FICTIONAL title", "FICTIONAL body")
        self.assertEqual(result["summary_english"], "FICTIONAL summary")
        guard.finish_article(1, "fully-analyzed")
        guard.finish_run([1])
        self.assertEqual(len(analyzer._client.requests), 4)
        self.assertTrue(all(o == {"max_retries": 0} for o in analyzer._client.options))
        receipt = guard.snapshot()
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["pending_usd"], "0")
        self.assertEqual(Decimal(receipt["unresolved_usd"]), 0)
        self.assertEqual(sum(r["calls"] for r in analyzer.usage.rows()), 4)
        from analysis.usage import build_run_record
        legacy = build_run_record(analyzer.usage, run_date="2026-10-11", recorded_at="2026-10-11", run_status="completed", analysis_model=ANALYSIS_MODEL, relevance_model=RELEVANCE_MODEL, articles_queued=1, articles_fully_analyzed=1)
        self.assertAlmostEqual(float(receipt["known_cost_usd"]), legacy["estimated_cost_usd"], places=6)

    def test_low_budget_invalid_money_and_unknown_model_never_dispatch(self):
        for budget in ("0", "0.01"):
            a, g, _ = guarded(budget)
            with self.assertRaises(AdmissionDeferred): a.prepare_article(1)
            self.assertEqual(a._client.requests, [])
        for value in (1, "-1", "NaN", "Infinity", "1e-10", "nonsense"):
            with self.assertRaises(ValueError): guarded(value)
        a, g, _ = guarded()
        with self.assertRaises(AdmissionDeferred): g.prepare(1, {**TASKS, "summary": ("unknown", 1000)})
        self.assertEqual(a._client.requests, [])

    def test_rejection_releases_downstream_reservations(self):
        a, g, _ = guarded(hook=lambda k: response(content=[NS(type="text", text='{"score":0.1,"reasoning":"FICTIONAL"}')]) if k["model"] == RELEVANCE_MODEL else None)
        a.prepare_article(1)
        self.assertFalse(a.analyze("FICTIONAL", "FICTIONAL")["passed_relevance"])
        g.finish_article(1, "relevance-rejected")
        self.assertEqual(len(a._client.requests), 1)
        self.assertEqual(g.snapshot()["pending_usd"], "0")

    def test_missing_usage_retains_exposure_and_blocks_next_dispatch(self):
        a, g, _ = guarded(hook=lambda k: response(usage=False))
        a.prepare_article(1)
        with self.assertRaises(AdmissionDeferred): a.analyze("FICTIONAL", "FICTIONAL")
        g.finish_article(1, "incomplete")
        self.assertEqual(len(a._client.requests), 1)
        self.assertGreater(Decimal(g.snapshot()["unresolved_usd"]), 0)
        self.assertEqual(sum(r["calls"] for r in a.usage.rows()), 1)
        self.assertEqual(g.snapshot()["articles"][0]["outcome"], "unknown")
        with self.assertRaises(AdmissionDeferred): a.prepare_article(2)

    def test_stream_interruption_and_fatal_failure_retain_unknown(self):
        for error in (RuntimeError("FICTIONAL stream interruption"),
                      anthropic.APIStatusError("FICTIONAL", response=httpx.Response(402, request=httpx.Request("POST", "https://fictional.invalid")), body={})):
            def hook(k):
                if k.get("tools"): raise error
            a, g, _ = guarded(hook=hook)
            a.prepare_article(1)
            with self.assertRaises((RuntimeError, FatalAPIError)): a.analyze("FICTIONAL", "FICTIONAL")
            g.finish_article(1, "incomplete")
            self.assertEqual(len(a._client.requests), 2)
            self.assertGreater(Decimal(g.snapshot()["unresolved_usd"]), 0)

    def test_parse_tool_empty_and_truncation_failures_keep_spent_receipt(self):
        malformed = [response(content=[NS(type="text", text="invalid JSON")]),
                     response(stop_reason="max_tokens"), response(content=[]),
                     response(content=[NS(type="text", text='{"score":true,"reasoning":"FICTIONAL"}')])]
        for resp in malformed:
            a, g, _ = guarded(hook=lambda k: resp)
            a.prepare_article(1)
            self.assertIsNone(a.analyze("FICTIONAL", "FICTIONAL"))
            g.finish_article(1, "incomplete")
            self.assertGreater(Decimal(g.snapshot()["known_cost_usd"]), 0)
            self.assertEqual(sum(r["failed_calls"] for r in a.usage.rows()), 1)
        a, g, _ = guarded(hook=lambda k: response(content=[NS(type="tool_use", name="emit_translation", input={"title_en": None, "body_en": "FICTIONAL"})]) if k.get("tools") else None)
        a.prepare_article(1)
        self.assertNotIn("title_english", a.analyze("FICTIONAL", "FICTIONAL"))
        self.assertEqual(len(g.snapshot()["calls"]), 2)

    def test_atomic_parallel_reservations_both_futures_resolved(self):
        barrier = threading.Barrier(2)
        completed = []
        def hook(k):
            if k["model"] == ANALYSIS_MODEL and not k.get("tools"):
                barrier.wait(timeout=3)
                completed.append(k["max_tokens"])
                if k["max_tokens"] == 1000: return response(content=[NS(type="text", text="invalid")])
        a, g, receipts = guarded(hook=hook)
        a.prepare_article(1)
        self.assertEqual(a.analyze("FICTIONAL", "FICTIONAL")["summary_english"], "")
        self.assertCountEqual(completed, [500, 1000])
        self.assertEqual(len(g.snapshot()["calls"]), 4)
        for r in receipts:
            self.assertLessEqual(sum(Decimal(r[k]) for k in ("known_cost_usd", "pending_usd", "unresolved_usd")), Decimal(r["budget_usd"]))

    def test_unreserved_duplicate_and_unsupported_request_refused(self):
        a, g, _ = guarded()
        with self.assertRaises(AdmissionDeferred): a.score_relevance("FICTIONAL", "FICTIONAL")
        a.prepare_article(1)
        a.score_relevance("FICTIONAL", "FICTIONAL")
        with self.assertRaises(AdmissionDeferred): a.score_relevance("FICTIONAL", "FICTIONAL")
        with self.assertRaises(AdmissionDeferred): request_exposure(dict(model=ANALYSIS_MODEL, max_tokens=1000, messages=[{"role":"user","content":[]}]), pricing_snapshot())
        self.assertEqual(len(a._client.requests), 1)

    def test_breach_records_true_cost_and_blocks(self):
        a, g, _ = guarded(hook=lambda k: response(usage=NS(input_tokens=2_000_000, output_tokens=100, cache_creation_input_tokens=0, cache_read_input_tokens=0)))
        a.prepare_article(1)
        a.score_relevance("FICTIONAL", "FICTIONAL")
        self.assertEqual(g.snapshot()["blocked"], "exposure-breach")
        self.assertGreater(Decimal(g.snapshot()["known_cost_usd"]), Decimal(g.snapshot()["calls"][0]["reserved_usd"]))
        with self.assertRaises(AdmissionDeferred): a.translate("FICTIONAL", "FICTIONAL")

    def test_write_ahead_receipt_failure_prevents_dispatch_and_interruption_is_incomplete(self):
        a, g, _ = guarded()
        a.prepare_article(1)
        self.assertEqual(g.snapshot()["status"], "incomplete")
        g._sink = lambda r: (_ for _ in ()).throw(OSError("FICTIONAL disk full"))
        with self.assertRaises(ReceiptFailure): a.score_relevance("FICTIONAL", "FICTIONAL")
        self.assertEqual(a._client.requests, [])
        self.assertGreater(Decimal(g.snapshot()["unresolved_usd"]), 0)

    def test_actual_sdk_hidden_retries_disabled_with_mock_transport(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(429, json={"type":"error", "error":{"type":"rate_limit_error","message":"FICTIONAL"}})
        a, g, _ = guarded()
        a._client = anthropic.Anthropic(api_key="fictional-offline-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        self.addCleanup(a._client.close)
        a.prepare_article(1)
        self.assertIsNone(a.analyze("FICTIONAL", "FICTIONAL"))
        self.assertEqual(len(requests), 1)
        self.assertGreater(Decimal(g.snapshot()["unresolved_usd"]), 0)

    def test_forced_relevance_tool_passes_same_guard(self):
        a, g, _ = guarded()
        a.prepare_article(1)
        with patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", True):
            self.assertEqual(a.score_relevance("FICTIONAL", "FICTIONAL")[0], .9)
        self.assertEqual(len(g.snapshot()["calls"]), 1)

    def test_parallel_article_admission_never_oversubscribes(self):
        total = sum(exposure(m, ceiling, pricing_snapshot()) for m, ceiling in TASKS.values())
        a, g, _ = guarded(str(total))
        barrier = threading.Barrier(2)
        admitted = []
        def work(i):
            barrier.wait(timeout=3)
            try:
                g.prepare(i, TASKS)
                admitted.append(i)
            except AdmissionDeferred: pass
        threads = [threading.Thread(target=work, args=(i,)) for i in (1, 2)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=3)
        self.assertEqual(len(admitted), 1)
        self.assertEqual(Decimal(g.snapshot()["pending_usd"]), total)

    def test_invalid_prices_limits_usage_and_changed_price_pin_fail_closed(self):
        a, g, _ = guarded()
        g.pinned["rates"][ANALYSIS_MODEL]["input"] = -1
        with self.assertRaises(AdmissionDeferred): a.prepare_article(1)
        for ceiling in (0, -1, True, 128_001):
            a, g, _ = guarded()
            with self.assertRaises(AdmissionDeferred): g.prepare(1, {**TASKS, "summary": (ANALYSIS_MODEL, ceiling)})
            self.assertEqual(a._client.requests, [])
        a, g, _ = guarded(hook=lambda k: response(usage=NS(input_tokens=True, output_tokens=100,
                                                  cache_creation_input_tokens=0, cache_read_input_tokens=0)))
        a.prepare_article(1)
        with self.assertRaises(AdmissionDeferred): a.analyze("FICTIONAL", "FICTIONAL")
        self.assertGreater(Decimal(g.snapshot()["unresolved_usd"]), 0)
        self.assertEqual(g.snapshot()["known_cost_usd"], "0")
