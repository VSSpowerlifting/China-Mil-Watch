# JCG September 2026 one-time historical source backfill — approval runbook

**Status: DRAFT ONLY, NO OWNER DISPATCH AUTHORIZED BY THIS DOCUMENT.**
This introduces a separate, owner-triggered historical **content** import. It is not a backdated collecting day, a scheduled job, source promotion or public dissemination.

## Why a special case is necessary

The verified Day 0 persistent JCG archive [run 37828199188](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37828199188) and state commit `81558026117067cbcf54bd7a7859a2d9db168a0c` collected three Sept29/Oct6 original English press releases using an Oct8 logical date and 9-day window.

The same publisher's original archived October 8 listing contains **two additional September publications** in the declared Sept1-onward scope: 2026-09-07 `jcg-en:9399` and 2026-09-18 `jcg-en:9424`. The bounded original HTML proof in [PR #229](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/229) and [run 37830207339](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37830207339) extracted **1,736** and **1,195** original English text characters, with publisher/index dates matching and capture/content digests. Neither has been persisted to the shadow state.

The shared runner correctly refuses ordinary lookback >30 days. A wider lookback is needed to reach September 7 from Oct8, but **we must not forge September collecting dates**, reset the original Day 0 clock, rewrite ledger evidence, or give other desk collectors unlimited history.

## Hardwired narrow owner operation

A special `--jcg-september-backfill` flag is supported **only when**:

- `desk=japan_jcg`, `target_date=2026-10-08`, `lookback_days=38`, `cap=5`;
- the event is owner-requested `workflow_dispatch` with an explicit source date;
- the state branch already contains `state/shadow.db`, `state/clock.json`, and the original `37828199188-1` ledger;
- the shadow clock specifically says Day 0 run `37828199188-1`;
- **no previous JCG September historical-backfill ledger exists**.

The workflow requires the owner to enter the **exact current `shadow/japan-jcg` HEAD SHA** and the affirmative string `APPROVE_JCG_SEPTEMBER_BACKFILL`. It verifies Day 0 commit ancestry, source state and the expected SHA before any source request. The job shares a concurrency lock with the existing manual and guarded-schedule workflows.

It re-runs source discovery for the original cutoff to obtain five official HTML source identities, then requires exact results: three already-stored records deduplicated unchanged, two new verified records added. If the source changes, an identity/date changes, a capture conflicts, or any request fails, the job does **not** push modified state.

A success adds exactly one separately typed ledger `operation=jcg_2026_09_historical_backfill` with `counts_as_qualifying_shadow_day=false`. It preserves the real October 8 Day 0 clock and original ledgers, original first-seen IDs and SHA-bound capture evidence.

## Steps after review and green full CI

1. Independently review and merge the read-only original-source evidence [#229](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/229).
2. Complete the Day 0 pinned review of `81558026117067cbcf54bd7a7859a2d9db168a0c` via #224 after it merges, resolving the known publisher stale `datetime=2021-3-1` date discrepancy as appropriate.
3. Review the separate backfill PR's exact changed files, tests and content-use exclusions. **Only then** merge this workflow and explicit one-shot CLI gate.
4. From GitHub Actions → *JCG September 2026 — One-time Historical Shadow Backfill*, select `main` and enter the **actual current shadow state SHA**, not a guessed SHA. Set approval to `APPROVE_JCG_SEPTEMBER_BACKFILL`. Manually dispatch.
5. Verify the new state HEAD commit is a descendant of Day 0, its clock and original ledger are byte-identical, all five source identities/dates exist, two were newly inserted, and three were duplicates. Record run ID and new state commit in the activation tracker.
6. Run the pinned read-only reviewer again at that new state commit, preserve a new separate human-reviewed decision on all five original HTML documents and their linked uncollected PDFs.

## Boundaries

No JCG state is automatically written by merging this PR. No general crawler is enabled, and all other desk lookback limits remain 30 days. The backfill is an auditable content migration into **isolated shadow**, not a new healthy collection day. It must not be counted as a 7/14/30 collecting-day checkpoint.

All source records remain `published_html_text_only`; linked PDF bodies, images and other third-party work are not represented as archived originals. The known publisher HTML `datetime=2021-3-1` remains a reviewer hold. Permanent Japan MOD/Joint Staff production coverage and weekly AI-writer eligibility are unaffected.
