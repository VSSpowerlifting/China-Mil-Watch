# Japan Coast Guard — guarded daily shadow qualification

**Status: candidate only, default OFF.** This is a plan for consecutive original-source evidence collection after the confirmed initial October 8, 2026 shadow Day 0. Merging the schedule workflow alone does **not** activate any automatic collection.

## Verified prerequisite

Owner-dispatched [Actions run 37828199188](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37828199188) successfully created the isolated `shadow/japan-jcg` root commit:

- State SHA: `81558026117067cbcf54bd7a7859a2d9db168a0c`.
- Collector SHA: `1323117a7eb2352f2780c8ee7178bb5c8535d48b`.
- Day 0 UTC: `2026-10-08T18:57:32.592661+00:00`.
- One official listing; three in-window original English HTML releases; three original-body extractions; three records stored, no failures; capture bytes/hash and ledger frozen.
- Source scope is Japan **Coast Guard**; HTML body only. Separate PDF audit #217 found 46–69 unmatched word tokens per linked PDF, which remains an editorial completeness hold.

**Day 0 is not Day 7/14/30 approval, production activation or full Japanese MOD coverage.** The isolated branch and record bodies must be reviewed against official publisher originals.

## Safeguarded qualification schedule

The candidate `.github/workflows/jcg_guarded_daily_shadow.yml` declares a daily cron **19:13 UTC**. Its job runs only if **all** are true:

1. The event is a schedule on `main`.
2. The owner has separately set the GitHub Actions **repository variable** `JCG_SHADOW_DAILY_ENABLED` to exactly `true` after the pinned Day 0 source/fidelity review.
3. The separate `shadow/japan-jcg` branch already exists with the original `state/clock.json`, `state/shadow.db` and immutable state-only tree. A scheduled run **cannot bootstrap a shadow clock**.
4. Focused JCG adapter, manual shadow and schedule-slot unit tests pass from that exact collector checkout.

Without the variable, scheduled workflow jobs are skipped. The original `japan_jcg_shadow_manual.yml` remains manual-only and can be used for an explicitly dated failed-day recovery.

Only the source-bounded `scripts/shadow_collect_desk.py --desk japan_jcg` runs, with the exact existing 9-day lookback, cap 20 and `--cron-utc 19:13`. The existing `core.shadow_schedule` nominal-slot rule retains the intended prior UTC day when an Actions job launches late across midnight, and disallows ambiguous reruns without an explicit manually supplied date. The manual workflow and daily workflow share the **same concurrency lock**, preventing simultaneous state writes.

Scheduled runs use append-only ledgers/capture hashes and a non-force push to `shadow/japan-jcg`. They cannot edit `main`, source manifests, the production database, output, newsletter, or the AI writer. Source restrictions, access challenges and unexpected document formats fail closed rather than being treated as good collection.

## Owner enabling path — after the source review

1. Review exact state commit `81558026117067cbcf54bd7a7859a2d9db168a0c` with `--as-of 2026-10-08`, using the formal reviewer or the read-only pinned-review workflow in #224 once merged.
2. Cross-check the three original publisher HTML bodies and visible/index dates, including the stale HTML `datetime=2021-3-1` attributes. Confirm first-party text use, attribution and PDF attachment exclusions.
3. If the owner accepts the shadow-only scope, first merge this guarded-workflow PR after exact-head CI passes. Then, separately, in **GitHub → Settings → Secrets and variables → Actions → Variables**, create `JCG_SHADOW_DAILY_ENABLED` with value `true`. Connecting GitHub for this workflow cannot set that variable through the tools currently available here.
4. Inspect the next actual schedule event, confirm `health=ok`, source capture integrity, logical target date, state commit ancestry and preserved day-zero clock. If unsuccessful, do not call it a healthy day; recover by an explicitly dated manual run after examining the refusal.
5. Keep Day 7, 14, 30 human checkpoint packets and source-specific publishing-coverage evidence. Revoke the variable (unset/false) to skip future scheduled collections if material source integrity or rights issues emerge.

## Explicit boundaries

A skipped scheduled job due to an unset variable is **not** a successful collecting day. A logical day with genuinely zero new official publications can be healthy if the listing was accessed, retrieved, fully evaluated and its ledger says `ok_no_publications` or `ok_all_duplicates`; this does not prove the ministry published nothing outside its declared source family. A source that returns partial original text, unexpected PDFs or access challenges does not pass merely because a workflow job succeeded.

**No automatic promotion, no Japan production manifest, no publication, no fabricated completeness, and no inference that Japan MOD is accessible.**
