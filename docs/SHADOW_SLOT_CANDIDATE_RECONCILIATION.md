# Offline shadow logical-slot candidate reconciliation

**Status:** Internal, read-only **candidate** report. No production readiness or publication authorization.

This module solves a narrow operational question: given a fixed starting date, daily UTC cron and a bounded set of **previously reviewed** per-source run observations, which logical dates have plausible scheduled evidence, are still inside the late-start grace interval, require investigation, or are missing from the *supplied* evidence?

It does **not** discover GitHub Actions runs, read or authenticate Git state, inspect official publisher sites, or infer that a ministry issued no new publications.

## Why not infer from green workflows?

The existing `core.shadow_schedule` module documents late Singapore GitHub Actions runs that started after UTC midnight and were originally attributed to the next date. Collector code now derives the nominal scheduled date from its declared cron and observed starting time. This reconciliation layer calls that same date rule, rather than inventing another. A delayed start is not a missed collection if its authenticated source ledger supports the previous logical slot.

A **manual dispatch without explicit target-date provenance** never repairs a missing scheduled slot. The only candidate for recovery is an explicit `target_date` on `workflow_dispatch`, **started no earlier than that target day's nominal UTC cron slot**. A manual dispatch before its named slot is visible as nonqualifying rather than preemptively filling future collection evidence. An Actions re-run with `event=schedule` and attempt greater than 1 does not become an original scheduled collection. The report requires independent source-state and Actions identity checks as input indicators, but does *not* authenticate these assertions itself.

## Command (no network)

```sh
python scripts/reconcile_shadow_slot_candidates.py \
  --contract /tmp/ipr-slot-contract.json \
  --observations /tmp/ipr-slot-observations.json \
  --as-of-utc 2026-10-09T08:00:00Z
```

**Example contract** (an illustration; choose the actual review starting date):

```json
{
  "source_slug": "id_kemhan_news",
  "state_branch": "shadow/indonesia-kemhan",
  "start_date": "2026-10-07",
  "cron_utc": "17:17",
  "grace_hours": 12
}
```

The observations input is a JSON array of **reviewed metadata**, one element per known run attempt. Required fields are `source_slug`, `state_branch`, `run_id` formatted `<Actions id>-<attempt>`, `target_date`, `target_date_source`, `github_event`, `github_conclusion`, `ledger_health`, `ledger_result`, `started_utc`, `finished_utc`, `new_records`, `action_identity_checked`, and `pinned_state_checked`.

The final two booleans may be set to true **only after** the caller independently checks the exact Actions metadata and immutable state evidence. Even then, the script labels positives only as **candidates**. It does not prove that an operator-supplied JSON export came from GitHub or exhaustively includes failed/re-run attempts.

The module accepts at most 31 calendar days and 500 run observations per source. It refuses non-UTC or impossible dates, duplicate run identities, foreign source branches, malformed attempt numbers and contradictory field types.

## Interpretation

- `pending_grace`: the UTC slot plus its configured grace period has not elapsed. **Do not page** or record a missed slot.
- `scheduled_success_new_records_candidate`: one reported successful, corroborated original scheduled attempt with a positive insertion count.
- `scheduled_success_no_new_records_candidate`: the same, with no new archived records. This **does not prove the government published nothing**.
- `explicit_manual_recovery_candidate`: one reported successful, corroborated manual run naming an exact logical target. It does not prove that the original scheduled event occurred.
- `mature_slot_missing_from_supplied_evidence`: mature logical date absent from the supplied evidence. This **does not prove a workflow never ran**, because the export might be incomplete.
- `attempt_present_but_not_attested_success`, `only_nonqualifying_attempts_observed`, and the conflicting/unresolved categories: require investigation, never a green badge.

A failed scheduled attempt followed by an explicit successful recovery is **flagged for review**, not silently rolled up into a spotless streak. The script does not dispatch recovery or alter historical ledgers.

### Non-goals and integration gate

All reports return `supplied_actions_export_authenticated=false`, `source_capture_chain_verified_by_this_audit=false`, `all_historical_scheduled_attempts_exhaustively_observed=false`, `government_silence_established=false`, and all production, weekly writer and editor-delivery authorization flags **false**.

This can eventually accept fully reviewed receipts from [Operations Center Issue #250](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/250), but it is **not currently wired to** the Phase 1 dashboard, shared workflows, Vietnam watchdog, or desk-specific audit. First establish authenticated Actions/ledger inputs and freeze a review start date from owner-approved configuration. Never infer the start date from the first currently visible positive run, as that would erase historical missing slots.

## Verification

```sh
python -m unittest tests.test_shadow_slot_candidates -v
```

Run the repository-wide PR CI before merging. All tests are synthetic and exercise UTC midnight, immature/mature slots, inferred vs explicit recovery, failures, missing or forged evidence, reruns and identity mismatches. No publisher requests, database writes, email or source changes occur.
