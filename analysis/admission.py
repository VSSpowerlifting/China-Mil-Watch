"""Optional exact-money per-run admission; separate from best-effort telemetry.

No provider calls, invoice claims, durable allowance or automatic recovery.
The bound is the full supported model context at the pinned 5m cache-write
rate plus configured output. This is deliberately expensive, not a forecast.
"""
from __future__ import annotations

import copy
import threading
from decimal import Decimal, InvalidOperation, localcontext

from analysis import pricing
from core.analysis_plan import digest

SCHEMA = "ipr-analysis-run/1"
TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens",
                "cache_read_input_tokens")
OUTCOMES = ("unattempted", "budget-deferred", "relevance-rejected",
            "fully-analyzed", "incomplete", "unknown")


class AdmissionDeferred(Exception):
    """Operational deferral; must never consume the article retry budget."""


class ReceiptFailure(RuntimeError):
    """Required private enforcement receipt failed; stop the guarded run."""


def money(value):
    if not isinstance(value, str):
        raise ValueError("budget must be a decimal USD string")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid USD budget") from exc
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -9 or amount > 1_000_000:
        raise ValueError("invalid USD budget")
    return amount


def canonical(amount):
    text = format(amount, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def pricing_snapshot():
    return {"checked": pricing.PRICING_CHECKED,
            "rates": copy.deepcopy(pricing.PRICING_USD_PER_MTOK),
            "cache_write": pricing.CACHE_WRITE_5M_MULTIPLIER,
            "cache_read": pricing.CACHE_READ_MULTIPLIER,
            "limits": copy.deepcopy(pricing.ADMISSION_LIMITS)}


def pricing_identity():
    return digest(pricing_snapshot())


def task_settings():
    from config import ANALYSIS_MODEL, RELEVANCE_MODEL, TRANSLATION_MAX_TOKENS, RELEVANCE_TOOL_OUTPUT_ENABLED
    return {"tasks": {"relevance": [RELEVANCE_MODEL, 500],
                      "translation": [ANALYSIS_MODEL, TRANSLATION_MAX_TOKENS],
                      "summary": [ANALYSIS_MODEL, 1000], "categorization": [ANALYSIS_MODEL, 500]},
            "relevance_tool_enabled": RELEVANCE_TOOL_OUTPUT_ENABLED}


def capacity_estimate(settings, budget_usd):
    """Upfront worst-case funding, never forecast completed throughput."""
    try:
        amount = sum((exposure(m, ceiling, pricing_snapshot())
                      for m, ceiling in settings["tasks"].values()), Decimal(0))
    except (AdmissionDeferred, ValueError, KeyError, TypeError):
        return {"evidence": "unavailable-capacity-bound", "article_reservation_usd": None,
                "initial_articles_funded": None}
    return {"evidence": "modeled-full-context-reservation", "article_reservation_usd": canonical(amount),
            "initial_articles_funded": None if budget_usd is None else int(money(budget_usd) // amount)}


def cost(model, tokens, pinned):
    rates = pinned["rates"][model]
    d = lambda v: Decimal(str(v))
    with localcontext() as ctx:
        ctx.prec = max(40, max(len(str(v)) for v in tokens) + 30)
        return (tokens[0] * d(rates["input"]) + tokens[1] * d(rates["output"]) +
                tokens[2] * d(rates["input"]) * d(pinned["cache_write"]) +
                tokens[3] * d(rates["input"]) * d(pinned["cache_read"])) / Decimal(1_000_000)


def exposure(model, max_tokens, pinned):
    if not isinstance(model, str):
        raise AdmissionDeferred("unsupported-model-or-pricing")
    if model not in pinned["rates"] or model not in pinned["limits"]:
        raise AdmissionDeferred("unsupported-model-or-pricing")
    limit = pinned["limits"][model]
    try:
        rates = [Decimal(str(pinned["rates"][model][k])) for k in ("input", "output")]
        if (any(not r.is_finite() or r <= 0 for r in rates)
                or pinned["cache_write"] != 1.25 or pinned["cache_read"] != .1
                or type(limit["context"]) is not int or limit["context"] <= 0
                or type(limit["output"]) is not int or limit["output"] <= 0):
            raise AdmissionDeferred("invalid-pinned-pricing-or-limits")
    except (InvalidOperation, KeyError, TypeError) as exc:
        raise AdmissionDeferred("invalid-pinned-pricing-or-limits") from exc
    if type(max_tokens) is not int or not 0 < max_tokens <= limit["output"]:
        raise AdmissionDeferred("unsupported-output-bound")
    return cost(model, (0, max_tokens, limit["context"], 0), pinned)


def request_exposure(kwargs, pinned):
    allowed = {"model", "system", "messages", "max_tokens", "temperature", "tools", "tool_choice"}
    if set(kwargs) - allowed or not kwargs.get("messages"):
        raise AdmissionDeferred("unsupported-request-bound")
    if (type(kwargs.get("temperature")) not in (int, float)
            or not 0 <= kwargs["temperature"] <= 1):
        raise AdmissionDeferred("unsupported-temperature")
    # Only the application's text-only Messages shape and ephemeral 5m cache.
    # Images/documents, server tools, TTL changes and betas have other exposure.
    for block in kwargs.get("system", []):
        if (set(block) - {"type", "text", "cache_control"} or block.get("type") != "text"
                or not isinstance(block.get("text"), str)
                or block.get("cache_control", {"type": "ephemeral"}) != {"type": "ephemeral"}):
            raise AdmissionDeferred("unsupported-system-bound")
    for message in kwargs["messages"]:
        if (set(message) != {"role", "content"} or message["role"] not in ("user", "assistant")
                or not isinstance(message["content"], str)):
            raise AdmissionDeferred("unsupported-message-bound")
    for tool in kwargs.get("tools", []):
        if set(tool) != {"name", "description", "input_schema"}:
            raise AdmissionDeferred("unsupported-tool-bound")
    # Pin the complete actual request (including all prompt/tool content), but
    # export only its digest. This is not a character-to-token assertion.
    digest(kwargs)
    return exposure(kwargs["model"], kwargs["max_tokens"], pinned)


class AdmissionController:
    def __init__(self, budget_usd, *, plan_id, execution_id, sink):
        self.budget = money(budget_usd)
        if not callable(sink) or not plan_id or not execution_id:
            raise ValueError("guarded execution requires plan, execution identity and receipt sink")
        self.pinned = pricing_snapshot()
        self._pricing_id = digest(self.pinned)
        self._lock = threading.RLock()
        self._sink = sink
        self._calls = []
        self._articles = {}
        self._pending = {}
        self._attempt_ceiling = {}
        self._spent = Decimal(0)
        self._unknown = Decimal(0)
        self.blocked = None
        self.plan_id, self.execution_id = plan_id, execution_id
        self.status = "incomplete"
        self._save()

    def snapshot(self):
        with self._lock:
            pending = sum((v[2] for v in self._pending.values()), Decimal(0))
            return {"schema": SCHEMA, "plan_id": self.plan_id, "execution_id": self.execution_id,
                    "status": self.status, "pricing_identity": self._pricing_id,
                    "budget_usd": canonical(self.budget), "known_cost_usd": canonical(self._spent),
                    "pending_usd": canonical(pending), "unresolved_usd": canonical(self._unknown),
                    "unused_usd": canonical(max(Decimal(0), self.budget - self._spent - pending - self._unknown)),
                    "blocked": self.blocked, "calls": copy.deepcopy(self._calls),
                    "articles": [{"record_id": i, **v} for i, v in sorted(self._articles.items())],
                    "origin_authenticated": False,
                    "limits": "per-run pinned-rate estimate; not an invoice, daily limit or restart allowance"}

    def _save(self):
        try:
            self._sink(self.snapshot())
        except BaseException as exc:
            self.blocked = "receipt-io-failure"
            raise ReceiptFailure("guarded receipt I/O failed") from exc

    def prepare(self, record_id, tasks):
        """Atomically fund ALL stages before relevance; no unaffordable start."""
        with self._lock:
            if record_id in self._articles:
                raise AdmissionDeferred("article-already-considered")
            self._articles[record_id] = {"outcome": "unattempted", "admitted": False, "attempted": False, "deferral_reason": None}
            try:
                if self.blocked or pricing_identity() != self._pricing_id or digest(self.pinned) != self._pricing_id:
                    raise AdmissionDeferred(self.blocked or "pricing-changed")
                reserves = {task: (model, ceiling, exposure(model, ceiling, self.pinned))
                            for task, (model, ceiling) in tasks.items()}
                if set(reserves) != {"relevance", "translation", "summary", "categorization"}:
                    raise AdmissionDeferred("unsupported-article-stages")
                total = sum((v[2] for v in reserves.values()), Decimal(0))
                pending = sum((v[2] for v in self._pending.values()), Decimal(0))
                if self._spent + self._unknown + pending + total > self.budget:
                    raise AdmissionDeferred("budget-deferral")
                for task, value in reserves.items():
                    self._pending[(record_id, task)] = value
                self._articles[record_id]["admitted"] = True
                self._save()
            except AdmissionDeferred as exc:
                self._articles[record_id]["outcome"] = "budget-deferred"
                self._articles[record_id]["deferral_reason"] = str(exc)
                self._save()
                raise

    def dispatch(self, record_id, task, kwargs):
        with self._lock:
            key = (record_id, task)
            if self.blocked or pricing_identity() != self._pricing_id or digest(self.pinned) != self._pricing_id:
                raise AdmissionDeferred(self.blocked or "pricing-changed")
            bound = request_exposure(kwargs, self.pinned)
            if key not in self._pending or self._pending[key] != (kwargs["model"], kwargs["max_tokens"], bound):
                raise AdmissionDeferred("unreserved-request")
            del self._pending[key]
            self._attempt_ceiling[key] = kwargs["max_tokens"]
            self._unknown += bound  # write ahead: until validated final usage
            entry = {"record_id": record_id, "task": task, "model": kwargs["model"],
                     "request_identity": digest(kwargs), "reserved_usd": canonical(bound),
                     "known_cost_usd": None, "state": "unknown", "tokens": None}
            self._calls.append(entry)
            self._articles[record_id]["attempted"] = True
            self._save()  # failure prevents provider dispatch
            return len(self._calls) - 1

    def response(self, ticket, response):
        with self._lock:
            entry = self._calls[ticket]
            if entry["state"] != "unknown" or entry["tokens"] is not None:
                raise ValueError("duplicate usage reconciliation")
            usage = getattr(response, "usage", None)
            tokens = [getattr(usage, k, None) for k in TOKEN_FIELDS]
            if (any(type(v) is not int or v < 0 for v in tokens)
                    or getattr(response, "model", entry["model"]) != entry["model"]
                    or digest(self.pinned) != self._pricing_id):
                self.blocked = "missing-or-invalid-usage"
                self._save()
                return
            actual = cost(entry["model"], tokens, self.pinned)
            bound = Decimal(entry["reserved_usd"])
            self._unknown -= bound
            self._spent += actual
            entry.update(state="measured", tokens=dict(zip(TOKEN_FIELDS, tokens)),
                         known_cost_usd=canonical(actual))
            limit = self.pinned["limits"][entry["model"]]
            if (actual > bound or tokens[0] + tokens[2] + tokens[3] > limit["context"]
                    or tokens[1] > self._attempt_ceiling[(entry["record_id"], entry["task"])]):
                self.blocked = "exposure-breach"
            self._save()

    def failure(self, ticket):
        # A connection/HTTP/stream failure does not establish zero billing.
        with self._lock:
            self.blocked = self.blocked or "ambiguous-provider-failure"
            self._save()

    def finish_article(self, record_id, outcome, *, reason=None):
        with self._lock:
            if outcome not in OUTCOMES:
                raise ValueError("invalid article outcome")
            if any(c["record_id"] == record_id and c["state"] == "unknown" for c in self._calls):
                outcome = "unknown"
            self._articles[record_id]["outcome"] = outcome
            if reason is not None:
                self._articles[record_id]["deferral_reason"] = reason
            self._pending = {k: v for k, v in self._pending.items() if k[0] != record_id}
            self._save()

    def finish_run(self, selected_ids):
        with self._lock:
            for i in selected_ids:
                self._articles.setdefault(i, {"outcome": "unattempted", "admitted": False, "attempted": False, "deferral_reason": None})
            self.status = ("incomplete" if self.blocked or self._pending or
                           any(v["outcome"] in ("unknown", "incomplete", "unattempted")
                               for v in self._articles.values()) else "completed")
            self._save()
