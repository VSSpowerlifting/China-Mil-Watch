# Vietnam ministry Actions-attempt versus state-ledger reconciliation

**October 8, 2026. Offline evidence safeguard for the October 14 Day 7
review; no new collection, publication, publisher requests or approvals.**

## Why another check is required

The Vietnam MPS/MOIT workflow writes its three isolated state branches
**only on successful publication**, and GitHub Actions uploads complete
attempt artifacts separately. An unsuccessful workflow may leave no
ledger at all. A failure after some ordinary fast-forward branch pushes
can leave the three sources at different latest attempts. Even a
perfectly verified three-packet rollup (PR #184) cannot prove that all
failed or cancelled Actions attempts were represented in those packets.

This tool cross-checks **manually supplied, independently reviewed**
GitHub Actions attempt receipts with **metadata-only extracts** from
all three independently pinned source-ledger inventories. It does
not request information from GitHub by itself and never reads source
article texts or capture binaries.

## Input: one explicit local JSON evidence file

Provide exactly the following top-level keys:

- schema: ipr-vn-ministry-attempt-reconciliation-input/1
- workflow: .github/workflows/vietnam_ministry_shadow.yml
- review_window: from and through, inclusive YYYY-MM-DD strings
- expected_target_dates: **every** calendar date from
  review_window.from through review_window.through, inclusive, in ascending
  order, with no omitted dates. The input validator now refuses an incomplete
  or reordered list. These are **schedule expectations**, never evidence
  that GitHub actually ran. This narrow policy is specific to the approved
  daily three-source MPS/MOIT reliability period.
- github_attempts: one object **per Actions attempt** with numeric
  run_id and run_attempt, exact canonical GitHub run URL, event
  (schedule or workflow_dispatch), completed conclusion, target_date
  or null, and target_date_basis or null.
- source_ledgers: exactly the three fixed source slugs, each with its
  fixed state_branch, pinned 40-character state_commit and a list of
  source's original completed successful-ledger metadata rows.

Each source ledger row contains run_id such as
37700200951-1, result, health, target_date, target_date_source,
collector_commit and finished_utc. **Extract these fields from actual
state ledger JSON and leave all publisher prose/capture bytes out.**

**Exception for the one genuine October 7 historical bootstrap.** The
successful run 37656171920 attempt 2 was a manually dispatched, explicitly
source-targeted first collection, not a daily scheduled slot: MPS used
2026-10-05, while *both* MOIT families used 2026-09-30. Those were the
logical dates recorded in their committed ledgers; all three batches
finished on October 7 with collector
2c21b0d091ffc288b1a106d5459d758aaaac6ff5. The validator checks
those exact source-specific historical targets and code identity for
run_id 37656171920-2. In its **Actions attempt** receipt, represent
target_date and target_date_basis as **null** for this single run: there
is no truthful single target date for all three sources. Do not write
2026-10-07 as its target or automatically call the earlier source dates
missed schedule days. The separate October 7 *scheduled* follow-up
37700200951-1 has target 2026-10-07 and must appear separately.

The review_window and complete expected_target_dates grid describe the
daily **observation/calendar** period beginning October 7; the one
anchored Day 0 bootstrap has earlier explicit *historical lookback*
targets and is the only such exception. Every other source run target
must fall inside the stated review window.
Do not invent missing Actions attempts or clone state into production.

A GitHub attempt's target_date should be populated only when separately
verified from its documented scheduled slot or explicit manual dispatch
input. For a scheduled attempt use target_date_basis
verified_schedule_slot; for a manual recovery use
verified_dispatch_input. If the date has not been independently
verified, use null for **both** fields. Never derive an editorial
target date by assuming an on-time runner start.

## What the report detects

- A failed/cancelled/timed-out Actions attempt that produced no
  successful-state source ledger; do not erase it as an empty day.
- One or more missing source ledgers after an Actions run otherwise
  concluded success.
- Source state that published after a workflow ended unsuccessfully.
- A source ledger with no corresponding supplied GitHub attempt
  receipt (possible incomplete Actions attempt inventory).
- MPS/MOIT branch latest run identities diverging after partial
  publication or recovery.
- The same serial batch claiming different logical target days, different
  date-origin labels, or incompatible collector commit SHA-1s across sources.
- Re-run of an ordinary scheduled job, which needs manual review because
  the supported recovery path is a new dispatch naming the explicit day.
- Action event versus ledger provenance mismatch, independently known
  logical target dates disagreeing, and planned days without a supplied
  full three-source success receipt.

The report **unconditionally states** that Actions enumeration is not
independently proven exhaustive, failed-attempt artifacts were not
verified, actual Git ancestry was not rechecked and human checkpoint
signoff is not complete. It cannot prove the absence of an **unlisted**
failed or cancelled attempt or a scheduled day missed entirely by
GitHub. Those require a human to inspect *all* relevant Actions runs,
attempt-number details, schedule history, retention-limited artifacts
and recovery instructions.

A report with zero warnings is **not** a valid Day 7 signoff, collection
qualification or production promotion.

## Procedure

After the October 14 scheduled run **actually completes**, gather the
full Actions run-and-attempt inventory for the review window, including
failed and earlier re-run attempts. Record those receipt references.
For the Day 7 review, set review_window.from to **2026-10-07** and
review_window.through to **2026-10-14**, then enumerate **October 7, 8, 9,
10, 11, 12, 13, and 14** as expected_target_dates. For Day 14/30 extend
the end date; the start is always the approved **October 7** Day 0.
Do not make a report with review_window.through in the future relative
to the completed scheduled slot. A missing action on an expected day
is flagged as a missing collection receipt; it is **not** interpreted as
a day when the ministry published nothing.
The first October 7 activation has a distinct failed attempt 1 and
successful attempt 2; an ordinary GitHub list of the latest attempt
alone is **not** a complete enumeration.

Then use the existing independent per-source Git-state reviewer to
validate the three branch histories. Transcribe only the seven
per-run metadata fields, state branch and **current pinned commit** into
the structured local input. Also specify independently verified
expected logical dates. Keep this evidence file out of public Git if
it includes nonpublic operational details.

Run:

~~~bash
python -m scripts.vietnam_ministry_attempt_reconciliation \
  /path/to/verified-vanilla-metadata.json
~~~

The script prints deterministic JSON and writes nothing. Resolve all
warning categories and separately inspect original Actions failure
artifacts and per-source publication status. Next generate three
commit-authenticated Day 7 source packets using the pre-existing formal
producer and run PR #184's three-source rollup, if merged. Each source
requires its own **human** complete-corpus review and valid signoff.
Do not auto-retry a failed schedule or auto-correct a branch mismatch.

The source-specific Day 0 reference clocks remain October 7 and
the earliest checkpoint is October 14 **after** its run. Day 14 is
October 21 and Day 30 is November 6. The disabled National Defence
Journal is a different source and is explicitly excluded from this
audit. Nothing here grants ministry reuse rights or adds original
content to the tracked production database.

Related:
- docs/VIETNAM_MINISTRY_RELIABILITY_CADENCE_2026-10-07.md
- docs/VIETNAM_MINISTRY_THREE_SOURCE_CHECKPOINT_ROLLUP_2026-10-08.md
- GitHub Issue #186 (Day 7 coordinator)
