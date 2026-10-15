# Japan MOD shadow: per-selected-item failure receipt (15 October 2026)

**Status:** narrow, prospective machine-observability change for the *existing* Japan MOD isolated shadow; **not** a collector reliability fix, publisher-access workaround, retroactive source review or desk admission.

## Real defect: latest persisted partial run does not identify its three failed items in the JSON ledger

- [Actual Oct 14 logical scheduled run 38662142409](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38662142409), created after the Oct 14 scheduled slot and executed Oct 15 UTC, published `shadow/jp-mod` commit `0a19aa448b57ddec91dced8b08bee625a89172d5` and ledger `state/ledger/20261015T004957+0000-38662142409-1.json` (Git blob `c8ebca0421da67fd1a0fa0badc706787b3a082d9`).
- The collector observed **291 discovered**, **8 selected**, **2 retrieved**, **5 duplicates**, **0 inserted**, **1 fetch failure**, **2 extraction failures**, `health=partial`, **173 outstanding gap URLs** (170 access-challenged, 1 without source assignment). The terminal prints only these aggregate counts.
- The existing `sources[].failed_endpoints` is supplied by *listing discovery* and is empty for the `jp_mod_news_ja` family even while its selected-item fetch and extraction counters are nonzero. The `shadow_unretrieved` SQLite table does retain failed URL/reason, but neither the scheduled job log nor the convenient per-source JSON ledger presents the **per-attempt failed identities**. A reviewer seeing the count-only receipt cannot tell which three source records to inspect without separately opening and querying the full shadow database.

## Minimal forward-only change

`scripts/shadow_collect_japan.py` now emits an **additional optional** `sources[].attempt_failures` array in future, existing-style isolated shadow JSON ledgers. Each failure contains only `{url, stage, status}` for an actually *selected* item that failed at fetch or extraction stage. `stage` is `fetch` or `extract`; `status` is the controlled adapter state, or narrow literal `orphan_not_modified` (unexpected HTTP-not-modified without a stored record) / `empty_documents` (extractor reported OK but returned zero documents).

This intentionally **does not** copy HTML/PDF original bodies, scraper diagnostic strings, arbitrary exception text, media, protected credentials or extracted paragraphs into the ledger or Actions log. Successfully returned 304 duplicates and genuine access challenges remain distinct, not misclassified as fetch/extract failures. Discovery failures retain `failed_endpoints`, a separate source-entry category. A zero-error source gets `attempt_failures=[]`.

Scope is **prospective only**: no reading/editing old `state/ledger/*.json`, no changed state clock/Day-0, no reconnect to challenged HTML, no forced retry, no policy bypass, no claim the Oct 14 three actual failed URLs can be recovered from a new future field. New URLs are official publisher page endpoints already present in the shadow state's own `shadow_unretrieved` list. Existing `result=ok_all_duplicates` with `health=partial` behavior is **unchanged**; whether this source may become a complete production collection requires separate owner/reviewer decisions.

## Verification and review

- Dedicated synthetic tests in `tests/test_japan_shadow_runner.py` cover selected fetch failure, selected extraction failure, zero-document extraction, orphan 304, success/challenge with empty failure arrays, two-source separation, exact failure URL/status/stage and persisted ledger parity; diagnostic prose must not appear in `attempt_failures`.
- Repository-wide offline checks, preserved DB/output hashes, and exact PR-head validation must pass before any merge. After merging, observe the next actual scheduled Japan MOD shadow run, compare sum of per-source failure entries to reported counts, and keep earlier partial/blocked days unchanged.
- **No source-rights/media approval, unsigned checkpoint signature, JCG gate change, publisher fetch, AI, email, public record, source-classification promotion, manual retry or deployment** follows from this metadata visibility improvement.