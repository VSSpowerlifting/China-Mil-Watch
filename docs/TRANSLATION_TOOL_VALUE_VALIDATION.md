# Translation tool-value validation: fail closed before database completion

The translation task in `analysis/analyzer.py` uses a forced
`emit_translation` tool call. Its declared schema requires English
headline and body strings; however, the previous runtime code coerced
values with `str(...)`, which could silently accept `None` as
`"None"` or even store whitespace-only strings as successfully
translated content.

The analyzer now requires actual `str` values containing at least
one non-whitespace character for **both** `title_en` and `body_en`.
Valid translations are returned **unchanged**, including paragraph
breaks, Chinese terms, quote punctuation and leading/trailing whitespace.
Invalid values raise the existing `AnalysisError` and are **accounted
as failed paid translation calls**, retaining reported token usage.

The surrounding pipeline already catches `AnalysisError`, records an
incomplete analysis, leaves `analyzed_at` unset and applies the existing
reviewable retry/pause budget. This change does not alter prompts,
request parameters, models, token ceilings, model spending limits, desk
routing, publication standards or database schema.

**Evidence boundary:** the October 2–8 tracked usage ledger recorded
20 failed translation calls; it does **not** establish which failure
causes those calls encountered. This strict validation is a directly
verified code contract defect, **not an asserted fix for those 20
historical failures**. A fail-closed response can increase the counted
failed-call total relative to the old buggy code on a future malformed
response, because previously it was incorrectly counted as success.

The new offline synthetic test module asserts numeric/null/list/
dictionary/empty/whitespace values refuse completion and preserve
response token accounting. Positive tests prove valid outputs and
request shape are unchanged, and integration tests prove an invalid
translation produces only a **partial relevance result**, never a
publishable analysis.

Dedicated CI executes the new cases and the existing 20+ usage
telemetry tests without an Anthropic key, plus a preservation check
against the tracked database and site output. Require focused and
full exact-head PR checks before merge. No actual retries or model
calls have been initiated by this change.
