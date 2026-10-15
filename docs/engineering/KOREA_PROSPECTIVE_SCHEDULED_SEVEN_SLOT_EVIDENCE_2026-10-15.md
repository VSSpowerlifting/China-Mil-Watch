# Korea prospective scheduled seven-slot ledger observer

**Date:** October 15, 2026 (UTC). **Status:** proposed read-only machine-observability improvement, not qualification, publisher-body reuse, Korean-language review, original-file privacy or a release.

## Why this exists

Korea's original **October 7–13** formal Day-7 evidence window contains a **real failed October 12 scheduled attempt**, [Actions #38323793488](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38323793488), `result=timeout`, with no published successful state receipt. A later lookback, manual source recovery or correct HWPX byte check cannot turn that **historical scheduled attempt** into a success. `scripts/korea_day7_machine_preflight.py` consequently remains **fixed to October 7–13** and has not been altered.

On October 14, Korea's latest [real scheduled collection](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38636466191) succeeded and left the isolated archive with 14 Korean HWPX originals. A separate [14-original true-byte source proof](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38671706676) later showed `machine_hwp_original_parity=PASS`, **`scheduled_continuity=FAIL`**, `human_source_review=UNMEASURED` and `production_promotion_authorized=false`. Both pieces of evidence are useful, but neither clears the failed Oct 12 slot.

## New read-only fields in the existing Korea slot watchdog

The existing `scripts/watch_korea_shadow_slots.py` already inspects **only immutable Git-ledger metadata and Day-0 clock** from a sparse source checkout after the nominal `17:47 UTC` slot plus **six hours of allowed schedule delay**. This change adds **observer data only**, using the same existing success rules (healthy `target_date_source=schedule-slot` and distinct first-attempt Actions-shaped IDs):

- `rolling_seven_mature_dates`: the **last seven matured scheduled logical dates** (shorter until seven exist)
- `rolling_seven_missing_scheduled_dates`: dates in that window **without** a successful scheduled ledger; an explicit/manual source-recovery receipt does not fill them
- `rolling_seven_consecutive_ledger_candidate`: a **candidate** boolean if seven full matured dates all have matching successful ledger provenance; **not** an authenticated census of all failed/deleted/cancelled Actions attempts
- `current_scheduled_ledger_streak_days`: the uninterrupted scheduled-ledger days up to the latest mature date; zero if current day absent
- `october_12_scheduled_gap_still_unrepaired`: the historically failed Oct 12 slot remains distinctly visible, even when a *later* seven-slot candidate eventually becomes clean
- `rolling_seven_observation_kind=LEDGER_ONLY_CANDIDATE_NOT_AUTHENTICATED_ACTIONS` and `rolling_seven_production_admission_authorized=false`

This is an additive report contract; **existing** error behavior, original `missing_scheduled_dates`, `current_mature_slot_missing`, workflow alarm and source-/rights-/Sunday-hold flags remain untouched. The scheduled workflow's only changes are to run the new no-network regressions as part of its offline contracts.

## Reviewable illustrative status

Using the genuine ledger set observed as of Oct 14: the rolling last-seven interval **October 8–14** has six observed successful scheduled ledger dates and **one missing October 12 slot**; the current streak is **two** (October 13–14). A possible *new* seven-slot candidate would comprise **October 13–19**, *only if* all the future October 15–19 scheduled jobs actually complete successfully with authentic first-attempt ledgers and after the October 19 `17:47 UTC` nominal slot has cleared its six-hour grace (October 19 **23:47 UTC**). This is a conditional future boundary, **not** a forecast of success or a retroactive historical Day-7 pass.

Even once the new window shows a candidate, the fixed original October 7–13 failure remains in the historical record, and a separate authenticated, exhaustive-enough GitHub Actions attempt census and exact-head human owner review is needed before anyone can characterize the new interval as qualified collection reliability. The observer never requests a source, refreshes a publisher page, reruns a collector, downloads HWPX, alters isolated Git state or starts an AI or SMTP job.

**Other permanent holds:** Korean-language and actual HWPX visual/semantic review, publisher text/attachment/photography rights, restricted archive owner decision [#520](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/520), distinct DAPA B00008 pilot authorization, and any eventual source-/desk-/Sunday admission remain independent and unapproved.

Related: [Korea source gate #221](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/221) and [unsigned original review register #596](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/596).
