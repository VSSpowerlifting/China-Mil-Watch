# Indonesia and South Korea — cadence proposal, 2026-10-06

**Status: owner-approved cadence; not activated.** Ben explicitly approved the
slots and bounds below, dedicated commit/push and draft PR, and exact-head CI.
This branch is synced to current main after PR #112,
`ba5885c30e90ff05644a67b86eac01818de4be7d`. The sync had no Git conflicts;
AFP's separate 06:40 UTC workflow and concurrency group are preserved. No cron
slot or concurrency-group collision exists with the other main workflows.
Indonesia/Korea remain manual-only on main until separate owner-authorized merge.
No manual collection dispatch is authorized in this phase.

## Approved authorization

Ben authorized one daily shadow collection for each candidate, seven days a week:

| Candidate | Nominal UTC slot | Source-local time | Fixed state branch |
|---|---|---|---|
| Indonesia — Kemhan Berita | 17:17 | 00:17 WIB the following calendar day | `shadow/indonesia-kemhan` |
| South Korea — Policy Briefing MND-labeled republications | 17:47 | 02:47 KST the following calendar day | `shadow/korea-policy-briefing` |

The slots follow the production cron window (12:23–14:23 UTC) and its documented
60–100 minute lateness, precede Singapore/Japan's 21:10/22:40 UTC slots, and
stagger these candidates by thirty minutes. This is an operational placement,
not a claim about source publication frequency or completeness. Weekend runs
make missing-day evaluation explicit; a successful duplicate-only or proven
empty-window result is preserved without inventing new publication.

The existing bounds remain: six lookback days, forty-record cap, twenty-minute
job timeout, identifiable robots-gated native access, existing source/document
scope and ninety-day Actions artifact retention. State remains public isolated
evaluation evidence. No production collection, model call, rendering, deployment,
public desk declaration or promotion is included.

## Prepared execution

The local workflow diff adds two UTC cron entries to the existing manual
workflow. The triggering cron selects exactly one fixed desk; manual dispatch
continues to honor its desk input. Invalid events, schedules and desks fail
before state checkout or source access. Manual and scheduled jobs share the
same per-desk concurrency group with `cancel-in-progress: false`.

Each scheduled first attempt passes its matching `--cron-utc` to the existing
`core/shadow_schedule.py` resolver and records `schedule-slot`. Actual execution
timestamps remain actual timestamps. A manual dispatch without a date records
`manual-utc-date`; an explicit recovery date remains authoritative. Ambiguous
UI reruns remain refused. The resolver's under-24-hour delay assumption is
unchanged; this proposal does not claim to reconstruct GitHub's nominal event.

An absent state branch, DB or first-success clock on a scheduled run is fatal:
it cannot silently bootstrap a new corpus or clock. Successful batches alone
append and publish state through the existing explicit non-force destination.
Originals, old ledgers and clocks
remain immutable. Failed batches do not publish partial corpus; attempt evidence
is retained by the existing artifact step when that step can run. Missing and
failed dates remain visible and require deliberate disposition or explicit-date
manual recovery, never an invented successful day.

The first genuine scheduled run for each desk must be audited against its
published commit and artifact before scheduled operation is reported as verified.
Manual runs cannot prove that a cron actually fired. Day 7, 14 and 30 checkpoints
still require human source/document comparisons and sign-off. A cadence approval
supplies none of those reviews and qualifies neither candidate.

GitHub schedules run from the default branch, may be delayed or dropped, and
use UTC by default. These are documented platform behaviors, not delivery
guarantees: [GitHub schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Local verification

All 136 targeted desk, logical-date and workflow-shape tests pass, including nine
new workflow execution/contract checks. Tests exercise the actual workflow shell
blocks with offline command probes, feed the resulting arguments through the
collector CLI's real date resolver, and refuse missing scheduled state. No native
collection was dispatched. The complete diff passes `git diff --check`; the
production DB, generated output, source adapters and registry are unchanged.
Full PR offline CI and actual cron delivery remain future verification steps.

## Delivery and activation sequence

1. Owner approved these exact daily slots and bounds in this chat.
2. Authorization is recorded in `DECISION_LOG.md` and current-state documentation;
   commit/push the reconciled changes and open the draft cadence PR.
3. Complete the PR's full offline CI and inspect its exact base/head diff.
4. Separate owner authorization and merge of the cadence PR activate scheduling. Its presence on main enables GitHub scheduling;
   no separate UI scheduler or Codex automation is needed.
5. Audit the first actual scheduled pair. Retain the original October 6
   first-success clocks; do not reset or backdate the evaluation.

This phase stops at the clean, mergeable, CI-verified draft PR. Scheduling stays
off until separate owner authorization and merge. No manual dispatch, desk
promotion, production change or additional task is included.
