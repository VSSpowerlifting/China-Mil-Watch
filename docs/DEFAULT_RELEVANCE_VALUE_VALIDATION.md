# Default relevance JSON value validation

## Reproduced error path

The standard China Daily relevance call is still Anthropic Haiku returning
free-text JSON. The existing JSON parser marks *syntax* failures correctly
in the usage ledger. But syntactically valid JSON without a usable score
previously failed only **after** that parser's success: missing score raised
KeyError, a numeric-looking string raised TypeError, and bool True silently
became score 1.0. The ledger retained a successful call despite the article
having failed. Python's permissive JSON parser also accepts NaN and Infinity
as float values, where clamping is not a meaningful relevance judgment.

These are data-semantic failures, not evidence that the publisher document
lacked text or that the model judged the article irrelevant.

## Narrow fix

After parsing, require one JSON object with a non-boolean numeric finite
score and nonblank string reasoning. For invalid values, mark the already
recorded relevance response as failed (preserving consumed input/output
token counts) and raise a redacted AnalysisError. The source text/response
payload never appears in the exception. The pipeline continues through its
existing reversible retry/pause policy, as improved by #309.

**Compatibility:** numerically valid relevance scores, including numbers
outside [0,1], keep the original 0..1 clamping behavior. This differs
intentionally from the new opt-in structured tool path, which enforces its
declared schema strictly. Existing threshold (0.60), pinned model, system
prompt, budget/cap, output fields, source loading, usage-ledger schema and
default-off RELEVANCE_TOOL_OUTPUT_ENABLED setting are unchanged.

## Verification

Synthetic tests: finite values, boundaries, legacy range clamping, invalid
null/string/list/bool/NaN/Infinity scores and missing/blank/nonstring
reasoning, object versus top-level list, 400-digit integer, malformed JSON,
ledger failed/successful call accounting, no payload leakage, and the
unchanged tool opt-in route. No provider calls, network or model spend.

Run neighboring redaction, tool, usage and failure suites; check exact
tracked SQLite DB and published output hashes before/after. Require full
repo CI and rendered-output validation before owner squash-merge.

No historical article reclassification, new model scoring, production
switch flip or paid experimentation is authorized by this PR.
