"""
LLM analysis engine for PLA Watch.

Runs four tasks per article using the Anthropic Messages API:
  1. Relevance scoring (Chinese text → 0.0–1.0 score)
  2. Translation     (Chinese text → English title + body)
  3. Analytic summary (English text → 2–3 sentence CFR-voice summary)
  4. Categories + significance flag (English text → taxonomy tags + flag)

Steps 3 and 4 run in parallel after translation completes.

Token budgets and temperatures per task:
  Relevance:   max_tokens=500,  temperature=0.0  (deterministic classification)
  Translation: TRANSLATION_MAX_TOKENS (32K default), temperature=0.3, streamed
  Summary:     max_tokens=1000, temperature=0.3  (analytic writing, slight variation)
  Categories:  max_tokens=500,  temperature=0.0  (deterministic classification)
"""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import anthropic

from analysis.prompts import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    VALID_CATEGORIES,
    build_category_messages,
    build_relevance_messages,
    build_summary_messages,
    build_translation_messages,
)
from config import (
    ANALYSIS_MODEL,
    ANTHROPIC_API_KEY,
    RELEVANCE_MODEL,
    RELEVANCE_THRESHOLD,
    TRANSLATION_MAX_TOKENS,
)

logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Raised when an API call fails or returns unparseable output."""


class FatalAPIError(AnalysisError):
    """
    Raised when a call fails for an *account-level* reason that retrying cannot
    fix: spend limit reached, credit exhausted, or bad/revoked credentials.

    Distinguished from AnalysisError because the correct response is opposite.
    A normal AnalysisError is per-article — skip it and continue the queue. An
    account-level failure applies to every remaining call, so continuing just
    burns the queue against a wall. On 2026-07-31 the spend limit was reached
    mid-run and the pipeline made 40 further doomed calls, and the translation
    backfill made 60, because nothing distinguished the two cases
    (DECISION_LOG 2026-07-31). Callers should abort the run on this.
    """


# Substrings identifying account-level failures in an API error message.
# Matched case-insensitively against the message body.
_FATAL_MESSAGE_MARKERS = (
    "reached your specified api usage limits",
    "credit balance is too low",
    "billing",
    "quota",
)

# Status codes that are always account-level, never per-article.
_FATAL_STATUS_CODES = frozenset({401, 402, 403})


def _classify_status_error(exc: "anthropic.APIStatusError") -> AnalysisError:
    """
    Map an APIStatusError to FatalAPIError (abort the run) or AnalysisError
    (skip this article). Keeps the message format identical either way so
    existing log-scraping and the billing-marker check still behave the same.
    """
    message = str(getattr(exc, "message", "") or exc)
    detail = f"API status error ({exc.status_code}): {message}"

    if exc.status_code in _FATAL_STATUS_CODES:
        return FatalAPIError(detail)
    lowered = message.lower()
    if any(marker in lowered for marker in _FATAL_MESSAGE_MARKERS):
        return FatalAPIError(detail)
    return AnalysisError(detail)


class Analyzer:
    """
    Runs all four LLM analysis tasks.

    Thread-safe: the Anthropic client uses per-request HTTP connections.
    Multiple threads in ThreadPoolExecutor can safely call _call() concurrently.
    """

    def __init__(self) -> None:
        if not ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Add it to .env or export it."
            )
        self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # ── Core API call ─────────────────────────────────────────────────────────

    # The system prompt is identical across all four tasks and sent on every
    # API call — up to 4 times per article, 100+ times per daily run at full
    # scale.  Marking it ephemeral tells Anthropic to cache the compiled KV
    # state for 5 minutes, cutting cached-token cost by ~90% on subsequent
    # calls within that window.
    _SYSTEM_WITH_CACHE: list[dict] = [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    def _call(
        self,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
        model: Optional[str] = None,
        stream: bool = False,
    ) -> str:
        """
        Single API call. Returns raw text. Raises AnalysisError on failure.

        `stream=True` is required for large `max_tokens` — the SDK raises on
        non-streaming requests it estimates will exceed the HTTP timeout.

        A response that stops at the token ceiling raises AnalysisError naming
        the truncation. Before 2026-07-30 this fell through to `_parse_json`,
        which reported a generic parse failure and hid a systematic length
        limit for months (DECISION_LOG 2026-07-30).
        """
        used_model = model or ANALYSIS_MODEL
        kwargs = dict(
            model=used_model,
            system=self._SYSTEM_WITH_CACHE,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            if stream:
                with self._client.messages.stream(**kwargs) as s:
                    response = s.get_final_message()
            else:
                response = self._client.messages.create(**kwargs)

            usage = getattr(response, "usage", None)
            if usage:
                logger.debug(
                    "  [%s] tokens in=%d out=%d cache_read=%d cache_write=%d",
                    used_model,
                    getattr(usage, "input_tokens", 0),
                    getattr(usage, "output_tokens", 0),
                    getattr(usage, "cache_read_input_tokens", 0),
                    getattr(usage, "cache_creation_input_tokens", 0),
                )

            if response.stop_reason == "max_tokens":
                raise AnalysisError(
                    f"Response truncated at the {max_tokens}-token ceiling "
                    f"(stop_reason=max_tokens, model={used_model}). The output is "
                    f"incomplete, not malformed — raise the ceiling rather than "
                    f"loosening the parser."
                )
            if not response.content:
                raise AnalysisError(
                    f"Empty response content (stop_reason={response.stop_reason})"
                )
            return response.content[0].text
        except anthropic.APIStatusError as exc:
            raise _classify_status_error(exc) from exc
        except anthropic.APIConnectionError as exc:
            raise AnalysisError(f"API connection error: {exc}") from exc

    # The translation is the one task whose output contains long free prose, and
    # prose is exactly where hand-rolled JSON breaks: the prompt asks the model
    # to preserve quoted rhetorical language ("决不"), and an unescaped inner
    # quote terminates the JSON string early. Tool inputs are serialized and
    # escaped by the API, so the whole class of failure disappears. Sonnet 4.6
    # supports tool use (it does NOT support the `output_config.format`
    # structured-outputs path — that would require a different model).
    _TRANSLATION_TOOL: dict = {
        "name": "emit_translation",
        "description": "Return the English translation of the article's title and body.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title_en": {
                    "type": "string",
                    "description": "English translation of the headline.",
                },
                "body_en": {
                    "type": "string",
                    "description": (
                        "English translation of the complete article body, "
                        "preserving the original paragraph breaks."
                    ),
                },
            },
            "required": ["title_en", "body_en"],
        },
    }

    def _call_tool(
        self,
        messages: list[dict],
        tool: dict,
        max_tokens: int,
        temperature: float,
    ) -> dict:
        """
        Forced-tool call. Returns the tool input already parsed by the SDK.

        Streams, because the callers that need a tool are the ones producing
        long output. Raises AnalysisError on truncation or a missing tool block.
        """
        try:
            with self._client.messages.stream(
                model=ANALYSIS_MODEL,
                system=self._SYSTEM_WITH_CACHE,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
            ) as s:
                response = s.get_final_message()
        except anthropic.APIStatusError as exc:
            raise _classify_status_error(exc) from exc
        except anthropic.APIConnectionError as exc:
            raise AnalysisError(f"API connection error: {exc}") from exc

        if response.stop_reason == "max_tokens":
            raise AnalysisError(
                f"Response truncated at the {max_tokens}-token ceiling "
                f"(stop_reason=max_tokens). Output is incomplete — raise the ceiling."
            )
        for block in response.content:
            if block.type == "tool_use" and block.name == tool["name"]:
                return dict(block.input)
        raise AnalysisError(
            f"Model returned no `{tool['name']}` tool call "
            f"(stop_reason={response.stop_reason})"
        )

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """
        Parse JSON from LLM output.

        Belt-and-suspenders approach:
          1. Strip any leading ```json/``` fence and trailing ``` fence via
             regex — handles the common case where the model wraps its output.
          2. Fallback: locate the outermost { ... } in the raw string in case
             the fence was non-standard or there was unexpected surrounding text.
        """
        cleaned = raw.strip()
        # Remove leading fence: optional whitespace, ```, optional "json", newline
        cleaned = re.sub(r"^\s*```(?:json)?\s*\n?", "", cleaned)
        # Remove trailing fence: optional newline, ```, optional whitespace
        cleaned = re.sub(r"\n?\s*```\s*$", "", cleaned).strip()

        # Fallback: if what remains still doesn't look like JSON, extract braces
        if not cleaned.startswith("{"):
            start = raw.find("{")
            end   = raw.rfind("}")
            if start != -1 and end > start:
                cleaned = raw[start : end + 1]

        try:
            return json.loads(cleaned, strict=False)
        except json.JSONDecodeError as exc:
            # Resolved 2026-07-30. The prior note here identified real drift
            # but conflated two independent failures, and only one was drift:
            #
            #   1. Truncation (the dominant cause, ~2/3 of losses).
            #      `translate()` was capped at max_tokens=4000, so long
            #      articles were cut mid-JSON and arrived here as fragments —
            #      deterministic above 5000 Chinese chars, not intermittent.
            #      Fixed by raising the ceiling and detecting
            #      stop_reason=max_tokens before parsing.
            #   2. Unescaped inner quotes (genuine drift). The translation
            #      prompt asks the model to preserve quoted rhetorical
            #      language, and a literal `"` inside a JSON string value
            #      terminates it early. The old note's prescription — forced
            #      tool use — was correct for this, and `translate()` now
            #      uses it. (Its other suggestion, `output_config.format`
            #      structured outputs, is not available on Sonnet 4.6.)
            #
            # This parser now only serves the three short-output tasks
            # (relevance, summary, categories), whose outputs are brief and
            # rarely carry embedded quotes.
            raise AnalysisError(
                f"JSON parse failed. Raw output was:\n{raw[:400]}"
            ) from exc

    # ── Individual task methods ───────────────────────────────────────────────

    def score_relevance(self, title: str, body: str) -> tuple[float, str]:
        """
        Returns (score, reasoning).
        Score is clamped to [0.0, 1.0] as a safeguard against out-of-range values.
        Uses RELEVANCE_MODEL (Haiku) — cheaper first-pass binary classifier.
        """
        messages = build_relevance_messages(title, body)
        raw  = self._call(messages, max_tokens=500, temperature=0.0, model=RELEVANCE_MODEL)
        data = self._parse_json(raw)
        score = float(max(0.0, min(1.0, data["score"])))
        return score, str(data.get("reasoning", ""))

    def translate(self, title: str, body: str) -> tuple[str, str]:
        """
        Returns (title_en, body_en).

        Streams: TRANSLATION_MAX_TOKENS is far above the ~16K non-streaming
        threshold, and this is the only call that renders a full article body.
        """
        messages = build_translation_messages(title, body)
        data = self._call_tool(
            messages,
            self._TRANSLATION_TOOL,
            max_tokens=TRANSLATION_MAX_TOKENS,
            temperature=0.3,
        )
        title_en, body_en = str(data.get("title_en", "")), str(data.get("body_en", ""))
        if not title_en or not body_en:
            raise AnalysisError(
                "Translation tool returned an empty title_en or body_en"
            )
        return title_en, body_en

    def summarize(self, title_en: str, body_en: str) -> str:
        messages = build_summary_messages(title_en, body_en)
        raw  = self._call(messages, max_tokens=1000, temperature=0.3)
        data = self._parse_json(raw)
        return str(data["summary"])

    def categorize(
        self, title_en: str, body_en: str
    ) -> tuple[list[str], bool, Optional[str]]:
        """
        Returns (categories, is_significant, significance_reason).
        Category slugs are validated against VALID_CATEGORIES; any hallucinated
        values returned by the model are silently dropped to prevent bad DB writes.
        """
        messages = build_category_messages(title_en, body_en)
        raw  = self._call(messages, max_tokens=500, temperature=0.0)
        data = self._parse_json(raw)

        categories = [c for c in data.get("categories", []) if c in VALID_CATEGORIES]
        is_significant = bool(data.get("significance", False))
        reason: Optional[str] = data.get("significance_reason") if is_significant else None

        return categories, is_significant, reason

    # ── Full pipeline ─────────────────────────────────────────────────────────

    def analyze(self, title_zh: str, body_zh: str) -> Optional[dict]:
        """
        Run the full four-task pipeline for one article.

        Returns a dict with all analysis fields populated, or None only if
        a hard failure occurs before translation (relevance failure still
        returns a partial result so it can be stored for the audit trail).

        Return keys:
            relevance_score, relevance_reasoning, passed_relevance,
            title_english, text_english, summary_english,
            categories, is_significant, significance_reasoning,
            model_id, prompt_version
        """
        # ── Step 1: Relevance ─────────────────────────────────────────────────
        # FatalAPIError propagates out of every stage below: it means the whole
        # account is blocked, so the caller must abort the run rather than
        # advance to the next article.
        try:
            score, reasoning = self.score_relevance(title_zh, body_zh)
        except FatalAPIError:
            raise
        except AnalysisError as exc:
            logger.error("Relevance scoring failed: %s", exc)
            return None

        if score < RELEVANCE_THRESHOLD:
            logger.debug(
                "Below relevance threshold (%.2f): %.60s", score, title_zh
            )
            return {
                "relevance_score":     score,
                "relevance_reasoning": reasoning,
                "passed_relevance":    False,
                "model_id":            ANALYSIS_MODEL,
                "prompt_version":      PROMPT_VERSION,
            }

        # ── Step 2: Translation ───────────────────────────────────────────────
        try:
            title_en, body_en = self.translate(title_zh, body_zh)
        except FatalAPIError:
            raise
        except AnalysisError as exc:
            logger.error("Translation failed: %s", exc)
            # Return partial result so relevance data isn't lost
            return {
                "relevance_score":     score,
                "relevance_reasoning": reasoning,
                "passed_relevance":    True,
                "model_id":            ANALYSIS_MODEL,
                "prompt_version":      PROMPT_VERSION,
            }

        # ── Steps 3 + 4: Summary and categories (parallel) ───────────────────
        summary             = ""
        categories: list[str]   = []
        is_significant          = False
        significance_reason: Optional[str] = None

        with ThreadPoolExecutor(max_workers=2) as pool:
            f_summary    = pool.submit(self.summarize,  title_en, body_en)
            f_categories = pool.submit(self.categorize, title_en, body_en)

            fatal: Optional[FatalAPIError] = None

            try:
                summary = f_summary.result()
            except FatalAPIError as exc:
                fatal = exc
            except AnalysisError as exc:
                logger.error("Summary generation failed: %s", exc)

            try:
                categories, is_significant, significance_reason = f_categories.result()
            except FatalAPIError as exc:
                fatal = fatal or exc
            except AnalysisError as exc:
                logger.error("Categorization failed: %s", exc)

        # Both futures are resolved before raising, so neither thread is
        # abandoned mid-flight. The paid translation is discarded rather than
        # stored without a summary: a record with analyzed_at set but a blank
        # summary satisfies this function's notion of "done" while violating
        # the deploy gate, which is what produced the 14 damaged rows on
        # 2026-07-31. Leaving the article unanalyzed keeps it retryable.
        if fatal is not None:
            raise fatal

        return {
            "relevance_score":        score,
            "relevance_reasoning":    reasoning,
            "passed_relevance":       True,
            "title_english":          title_en,
            "text_english":           body_en,
            "summary_english":        summary,
            "categories":             categories,
            "is_significant":         is_significant,
            "significance_reasoning": significance_reason,
            "model_id":               ANALYSIS_MODEL,
            "prompt_version":         PROMPT_VERSION,
        }
