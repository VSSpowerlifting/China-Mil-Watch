# Optional structured relevance output: offline verification only

## Why

The October 6, 8 and 9 Daily logs record repeated failed relevance JSON
parses for article IDs 1077 and 1635. Neither record was judged irrelevant or
invalid. PR #309 addresses a separate problem: their stored unscored retry
counts were not restored into the automatic retry budget.

Translation already uses a forced Anthropic client tool instead of trying to
parse free prose as JSON. This change adds the equivalent **opt-in** output
mechanism for the **relevance** step only. The current China and desk-specific
scoring rubrics, Haiku model, threshold 0.60, max_tokens=500, source bodies,
55-article Daily cap, and persistence rules are unchanged.

## Operator control

The default remains the pre-existing raw-text JSON response.
RELEVANCE_TOOL_OUTPUT_ENABLED=1 opts into a forced emit_relevance tool
response. No production workflow, schedule or secret config turns this on.
Merging this PR alone does not enable it or spend any model tokens.

The tool uses RELEVANCE_MODEL (Haiku in default config), reuses the selected
desk's system prompt, and requires both score and reasoning. Python also
checks score is a finite number between zero and one (not a boolean) and
reasoning is a nonblank string. Invalid or missing tool data fails closed,
retains the article in the existing review/retry pathway, and never substitutes
a fabricated score.

The shared forced-tool method defaults to its historical Sonnet/system context
for translation; its new explicit model and system arguments are used only by
the optional relevance branch.

## Telemetry, privacy and risks

- API failures before a response are counted once without invented tokens.
- Responses with malformed tool values, missing tool blocks or token truncation
  are counted as failed **with the consumed token usage retained**.
- Error text does not include source/article contents, model response payloads,
  tool inputs or user-facing raw material.
- There are no schema, model-ID, source, database, public-output or publication
  changes.
- Tool-use schema and prompt-format overhead may increase input token spending
  per relevance call. This cannot be quantified from synthetic tests; compare
  actual per-task token counts and failure rates from owner-approved,
  budget-bounded live use before any routine enablement.
- Offline mocks prove local branch behavior, not provider acceptance or output
  quality. Forced tools have model/setting restrictions; verify compatibility
  against the currently pinned model and SDK before an approved live trial.

## Release gate

Run tests/test_relevance_tool_optin.py plus existing translation-tool,
JSON-redaction, usage-ledger and analysis failure suites, then the full repo PR
offline/Chromium/render/database-preservation checks on the **exact** head.
This PR is a draft pending CI. **Do not enable** the env flag in scheduled
workflows or perform a paid A/B test without an explicit owner decision.
No historical record is overwritten or reclassified by this change.
