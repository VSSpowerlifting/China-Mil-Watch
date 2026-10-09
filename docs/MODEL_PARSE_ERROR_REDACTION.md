# No raw model response text in parse-error logs

## Reason for this change

`analysis/analyzer.py` previously formatted JSON parse exceptions using
`raw[:400]`. Three tasks—relevance, summarization, and categorization—
rely on this parser. Their failures are logged through the Daily pipeline
and may appear in GitHub Actions logs. The first 400 response characters
could include untrusted quoted source prose, a partial article translation,
or other model-generated content that does not belong in operational logs.

The error message now contains **only stable, non-content diagnostic
metadata**: `JSON parse failed`, JSON parser line, parser column and the
length of the original model response. It does **not** print the response
or a partial response. The existing `AnalysisError` type is preserved;
failures still count as one unsuccessful paid call with the same token
usage. No request shape, prompt, model, budget, retries, article result,
category validation, data storage or publication behavior changes.

## Privacy and failure boundaries

A Python exception may retain the original parser exception as its
`__cause__` in process memory; the Daily analyzer's existing
`logger.error("%s", exc)` path logs the safe message rather than a raw
exception chain. The change is **not** a comprehensive guarantee of
zero sensitive text elsewhere in the repository's logs: collectors and
other errors have separate responsibilities. The narrowed guarantee is
that this JSON parse-failure message and its observed analyzer log paths
no longer contain the model response.

Offline tests verify malformed, multiline and long outputs do not leak,
task-level failed-call and token accounting stays intact, and accepted
normal, fenced and prose-wrapped JSON still parses as before. The
existing telemetry tests are rerun. Nothing requires live model calls,
changed model credit, database changes or collector runs.

## CI / release gate

Dedicated CI runs all tests without an Anthropic API key, confirms the
tracked database and output tree are byte-identical, and full PR offline
checks must also pass on the **exact head**. Owner merge approval only
after those gates and a clean mergeability result.
