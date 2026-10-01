"""
Run-level LLM usage and cost telemetry.

OPERATIONAL ACCOUNTING ONLY. Nothing in this module influences which model is
called, what is sent to it, what is stored from it, or what is published. It
counts what the Anthropic API reports and writes one summary per pipeline run,
so that later decisions about call architecture (DECISION_LOG 2026-10-01) rest
on measurements rather than on an estimate.

Why it exists: before this module the only record of token usage was a DEBUG
log line in `Analyzer._call`, and the daily workflow logs at INFO — so
production kept nothing. The cost audit of 2026-10-01 had to reconstruct token
volumes from stored text lengths.

Shape
-----
`Analyzer` owns one `UsageLedger` per instance. Every API call is recorded
against an explicit `(task, model)` key; the task label is passed by the
caller, never inferred from prompt text. After the analysis stage
`record_run_usage()` turns the ledger into one JSON object and logs a compact
summary at INFO.

Two files, two owners
---------------------
The pipeline never touches the tracked history. If `LLM_USAGE_RECORD_PATH` names
a file, `record_run_usage()` writes this run's one record there (a temp file
outside the repository on GitHub Actions); if it is unset, which is every local
run, the summary is logged and nothing is written. A local run therefore cannot
dirty production state, and no tracked file is dirty while the workflow's later
`git pull --rebase --autostash` steps run.

The tracked, append-only history is `USAGE_LOG_PATH`. Only the workflow's
dedicated persistence step writes it, through `scripts/append_llm_usage.py`,
which validates the runtime record and appends exactly that object as one line.

What is deliberately NOT here
-----------------------------
No article text, title, URL, prompt or API key is ever recorded — only counts.
No per-article breakdown. No new service, dependency, or database table. The
history lives under `.github/state/`, not `output/`, so it is never published.

Failure semantics
-----------------
Recording must never break analysis, and persistence must never break the run.
Every ledger method swallows its own errors (one warning each) and
`record_run_usage()` returns None instead of raising. The cost of that choice
is that a telemetry bug is a log warning rather than a red run; the workflow's
persistence step and the tests are what make an absent record noticeable.

Estimates
---------
Cost uses the repository-pinned table in `analysis/pricing.py`. It is an
estimate, not an invoice. A model without a price on file is reported in
`unpriced_models` and contributes nothing to the total, so a non-empty
`unpriced_models` means `estimated_cost_usd` is an under-count.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

from analysis.pricing import PRICING_CHECKED, estimate_usage_cost_usd

logger = logging.getLogger(__name__)

#: Environment variable naming the runtime file the pipeline writes this run's
#: record to. Unset means log-only. The workflow sets it to a path under
#: `$RUNNER_TEMP` on the pipeline step and reads it back in the persistence step.
RECORD_PATH_ENV = "LLM_USAGE_RECORD_PATH"

#: The tracked, append-only history, relative to the repository root. Written
#: only by the workflow's persistence step (scripts/append_llm_usage.py), which
#: stages exactly this path; a test pins the two together. Under
#: `.github/state/` — never `output/`, which is published.
USAGE_LOG_PATH = ".github/state/llm_usage.jsonl"

#: Bump when a field is renamed or changes meaning. Adding a field does not.
SCHEMA_VERSION = 1

#: The stable task labels, in reporting order. Callers pass one explicitly.
TASK_RELEVANCE = "relevance"
TASK_TRANSLATION = "translation"
TASK_SUMMARY = "summary"
TASK_CATEGORIZATION = "categorization"
TASKS = (TASK_RELEVANCE, TASK_TRANSLATION, TASK_SUMMARY, TASK_CATEGORIZATION)

_COUNTERS = (
    "calls",
    "succeeded_calls",
    "failed_calls",
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def _tokens(usage, name: str) -> int:
    """A non-negative int from a usage field, 0 if absent or not an int."""
    value = getattr(usage, name, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


class UsageLedger:
    """
    Thread-safe counters keyed by `(task, model)`.

    Thread-safe because summary and categorization run concurrently in
    `Analyzer.analyze`.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: dict[tuple[str, str], dict[str, int]] = {}

    def _row(self, task: str, model: str) -> dict[str, int]:
        return self._rows.setdefault((task, model), dict.fromkeys(_COUNTERS, 0))

    def record_response(self, task: str, model: str, usage, failed: bool = False) -> None:
        """
        One call that returned a response. `usage` is the SDK's usage object
        (or None). A response later rejected as truncated or empty keeps its
        reported tokens and is counted as failed.
        """
        try:
            with self._lock:
                row = self._row(task, model)
                row["calls"] += 1
                row["failed_calls" if failed else "succeeded_calls"] += 1
                row["input_tokens"] += _tokens(usage, "input_tokens")
                row["output_tokens"] += _tokens(usage, "output_tokens")
                row["cache_creation_input_tokens"] += _tokens(
                    usage, "cache_creation_input_tokens")
                row["cache_read_input_tokens"] += _tokens(
                    usage, "cache_read_input_tokens")
        except Exception as exc:  # noqa: BLE001 — telemetry must not break analysis
            logger.warning("LLM usage telemetry: could not record a response: %s", exc)

    def record_failure(self, task: str, model: str) -> None:
        """One call that failed before any response existed: no tokens invented."""
        try:
            with self._lock:
                row = self._row(task, model)
                row["calls"] += 1
                row["failed_calls"] += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM usage telemetry: could not record a failure: %s", exc)

    def mark_failed(self, task: str, model: str) -> None:
        """
        Re-count the most recent success as a failure, keeping its tokens.

        For a response the API accepted but the caller then rejected (output
        that does not parse, an empty translation): the tokens were spent, and
        the article's result is an `AnalysisError`, so it is a failed call.
        """
        try:
            with self._lock:
                row = self._row(task, model)
                if row["succeeded_calls"] > 0:
                    row["succeeded_calls"] -= 1
                    row["failed_calls"] += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM usage telemetry: could not re-count a call: %s", exc)

    def rows(self) -> list[dict]:
        """Snapshot, one dict per `(task, model)`, in reporting order."""
        with self._lock:
            items = [(t, m, dict(c)) for (t, m), c in self._rows.items()]
        order = {t: i for i, t in enumerate(TASKS)}
        items.sort(key=lambda x: (order.get(x[0], len(TASKS)), x[0], x[1]))
        return [{"task": t, "model": m, **c} for t, m, c in items]


def build_run_record(
    ledger: UsageLedger,
    *,
    run_date: str,
    recorded_at: str,
    run_status: str,
    analysis_model: str,
    relevance_model: str,
    articles_queued: int,
    articles_fully_analyzed: int,
) -> dict:
    """One machine-readable record for a run. Counts and rates only."""
    tasks = []
    totals = dict.fromkeys(_COUNTERS, 0)
    total_cost = 0.0
    unpriced: set[str] = set()
    for row in ledger.rows():
        cost = estimate_usage_cost_usd(
            row["model"], row["input_tokens"], row["output_tokens"],
            row["cache_creation_input_tokens"], row["cache_read_input_tokens"])
        if cost is None:
            unpriced.add(row["model"])
        else:
            total_cost += cost
        for k in _COUNTERS:
            totals[k] += row[k]
        tasks.append({**row,
                      "estimated_cost_usd": None if cost is None else round(cost, 6)})

    per_article = (round(total_cost / articles_fully_analyzed, 6)
                   if articles_fully_analyzed > 0 else None)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_date": run_date,
        "recorded_at": recorded_at,
        "run_status": run_status,
        "analysis_model": analysis_model,
        "relevance_model": relevance_model,
        "articles_queued": articles_queued,
        "articles_fully_analyzed": articles_fully_analyzed,
        **totals,
        "estimated_cost_usd": round(total_cost, 6),
        "estimated_cost_per_analyzed_article_usd": per_article,
        "unpriced_models": sorted(unpriced),
        "pricing_checked": PRICING_CHECKED,
        "tasks": tasks,
    }


def format_run_summary(record: dict) -> str:
    """A compact multi-line block for one INFO log entry."""
    per_article = record["estimated_cost_per_analyzed_article_usd"]
    lines = [
        "LLM usage this run (estimate from the repository-pinned price table, "
        f"checked {record['pricing_checked']}):",
        f"  calls: {record['calls']} "
        f"({record['succeeded_calls']} ok, {record['failed_calls']} failed)",
        f"  tokens: in={record['input_tokens']:,} out={record['output_tokens']:,} "
        f"cache_write={record['cache_creation_input_tokens']:,} "
        f"cache_read={record['cache_read_input_tokens']:,}",
        f"  estimated cost: ${record['estimated_cost_usd']:.4f}  |  fully analyzed: "
        f"{record['articles_fully_analyzed']}  |  per analyzed article: "
        + ("n/a" if per_article is None else f"${per_article:.4f}"),
    ]
    for t in record["tasks"]:
        cost = t["estimated_cost_usd"]
        lines.append(
            f"    {t['task']:<14} {t['model']:<27} calls={t['calls']} "
            f"failed={t['failed_calls']} in={t['input_tokens']:,} "
            f"out={t['output_tokens']:,} "
            + ("cost=unpriced" if cost is None else f"cost=${cost:.4f}"))
    if record["unpriced_models"]:
        lines.append("  UNPRICED models (total is an under-count): "
                     + ", ".join(record["unpriced_models"]))
    return "\n".join(lines)


def _line(record: dict) -> str:
    return json.dumps(record, separators=(",", ":")) + "\n"


def write_run_record(record: dict, path: str) -> None:
    """
    Write this run's one record to the runtime file, replacing any earlier
    content, so the file always holds exactly one object. Written to a sibling
    temp file and renamed, so a reader never sees half a line.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(_line(record), encoding="utf-8")
    os.replace(tmp, p)


def load_run_record(path: str) -> dict:
    """
    Read a runtime record back, refusing anything that is not exactly one JSON
    object of the current schema. Raises ValueError (or OSError for a missing
    file); the persistence step treats either as "do not commit".
    """
    lines = [ln for ln in Path(path).read_text(encoding="utf-8").splitlines()
             if ln.strip()]
    if len(lines) != 1:
        raise ValueError(f"{path}: expected exactly one record, found {len(lines)} lines")
    record = json.loads(lines[0])
    if (not isinstance(record, dict)
            or record.get("schema_version") != SCHEMA_VERSION
            or not isinstance(record.get("tasks"), list)
            or not isinstance(record.get("run_date"), str)):
        raise ValueError(f"{path}: not a schema-{SCHEMA_VERSION} usage record")
    return record


def append_run_record(record: dict, path: str = USAGE_LOG_PATH) -> None:
    """
    Append one JSON object as one line to the tracked history. Creates the file
    on first use, and starts a new line first if the file lacks a final newline
    so a hand edit cannot fuse two records.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    needs_newline = False
    if p.exists() and p.stat().st_size:
        with p.open("rb") as f:
            f.seek(-1, os.SEEK_END)
            needs_newline = f.read(1) != b"\n"
    with p.open("a", encoding="utf-8") as f:
        f.write(("\n" if needs_newline else "") + _line(record))


def record_run_usage(
    ledger: UsageLedger, *, path: Optional[str] = None, **run_fields
) -> Optional[dict]:
    """
    Log the run summary and, if `path` is given, write the runtime record there.
    Never raises, and never touches the tracked history.

    `path=None` is log-only (a local run). Returns the record, or None if it
    could not even be built. A record that was built but not written is still
    returned, with a warning logged.
    """
    try:
        record = build_run_record(ledger, **run_fields)
        logger.info("\n%s", format_run_summary(record))
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM usage telemetry NOT recorded: %s", exc)
        return None
    if not path:
        logger.info("LLM usage record not written (%s is unset; log only).",
                    RECORD_PATH_ENV)
        return record
    try:
        write_run_record(record, path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM usage telemetry built but NOT persisted to %s: %s",
                       path, exc)
    return record
