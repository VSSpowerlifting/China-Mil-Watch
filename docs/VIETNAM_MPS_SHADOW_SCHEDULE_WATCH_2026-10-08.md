# Vietnam MPS — scheduled collection slot watchdog

## Why

The Sunday AI Brief relies on independently preserved, version-verified MPS
publications, not a country supplement Dylan assembles by hand. But a healthy
historical archive does **not** establish that each new calendar day's
scheduled collection happened. In particular, a GitHub Actions job can start
hours late or fail to dispatch, and a successful seven-day lookback is not
the same thing as a durable ledger for every nominal scheduled date.

This is an observability-only follow-on to the merged #211 source-verification
and #228 Sunday's private-model-readiness audit.

## Verified situation on October 8

The MPS isolated branch `shadow/vietnam-mps-foreign-affairs` was examined at
state commit `46f6a0e59e25b03868bf7ad600963d6921ee5124`. It contains
two source run ledgers:

- `37656171920-2`: October 5 **explicit** bootstrap date; completed on
  October 7 UTC, successful. This was NOT the first recurring schedule slot.
- `37700200951-1`: October 7 **schedule-slot** date, completed October 7
  23:06 UTC, successful, with three retrieved observations and no recorded
  source anomalies.

At the time of this audit, the repository's scheduled Actions history did
not yet show an October 8 MPS run. That is **not yet a failed slot**: its
nominal occurrence is October 8 at 18:17 UTC, and the program intentionally
allows **12 hours of GitHub scheduling delay** before flagging it as overdue.
The first overdue alert for October 8 would be due **October 9 at 06:17 UTC**
if there is still no successful logical-date October 8 ledger.

The collector and its original state branch remain separate from the main
repository's production database. Even a run marked successful proves only
that its bounded first-party listings and captures were processed: it cannot
prove that a government issued no other publications.

## Logic and contract

`scripts/watch_vietnam_shadow_slots.py` receives an exact immutable
shadow Git commit, verifies it belongs to
`shadow/vietnam-mps-foreign-affairs`, exports that Git tree and runs the
established complete ministry-state reviewer. Only the independently
verified source run ledgers are then used for freshness assessment.

The latest *mature* UTC collection slot is computed by subtracting 12 hours
from the observation time before comparing with the fixed 18:17 UTC cron.
A successful entry with `target_date_source=schedule-slot` begins the
daily reliability series. Explicit `target_date` **manual recovery** may
subsequently close a missing logical date; an earlier manual bootstrap
cannot create fictitious prior scheduled coverage. Failed runs do not count
as successes. The report caps detailed overdue dates to the last 30 mature
calendar days. Source/rights review and completeness of publisher coverage
are never assumed.

At 2026-10-08 21:15 UTC, the October 7 run is still current within the
12-hour grace window. If the October 8 run has still not happened by
2026-10-09 06:17 UTC, the watchdog reports
`overdue_logical_dates=["2026-10-08"]`. Running a later daily lookback
does not erase that logical-day warning unless an explicit successful
October 8 recovery is recorded.

## Daily read-only Actions job

`.github/workflows/vietnam_shadow_logical_slot_watchdog.yml` has an
independent **12:07 UTC daily** schedule (past the grace deadline for the
previous day's 18:17 UTC slot), plus an owner-controlled manual dispatch.
It uses read-only Git HTTPS, no push token, no external model/SMTP, and
outputs only aggregate overdue dates and source-state provenance.

### If a slot becomes overdue

Open **GitHub Actions → Vietnam Ministry Shadow Collection → Run workflow**.
Supply `target_date` with the **exact UTC date** reported as overdue,
e.g. `2026-10-08`. The existing collection runner expressly handles this
manual path, with bounded lookback and immutable state-history checks.
**Do not select Re-run jobs on the old scheduled run**. A GitHub re-run
retains its triggering event but not the original execution instant, so
the collector already refuses ambiguous retries. Verify the new collection
result and updated isolated Git state before treating that target day as
recovered. Recovery is never automatically initiated by this watchdog.

## Relationship to weekly editorial drafting

The watchdog checks **collection scheduling**. #228 checks whether
independently verified MPS articles within the week have current,
source-bound research synopses suitable for the private writer. These
are different questions: a source can be synopsis-ready even when the
latest Saturday collection slot is missing. The Sunday handoff must not
confuse one check with the other or tell Dylan a verified archive means
full publisher coverage.

Other Vietnam sources (MOIT energy and foundational industry) have
separate state branches, clocks and acceptance conditions; this watchdog
does not silently combine their results, nor does it activate those
sources for Sunday model drafting.

This PR does not change PR #203's common regional thematic writer,
the Japan source path, #211's archived evidence exports, #222's model
source-use gate, or #225's human publication citation controls.

## Tests

`python -m unittest tests.test_vietnam_shadow_logical_slot_watchdog -v`
covers the observed October 7 evidence shape, 12-hour grace boundary,
failed slot, explicit-date recovery, 30-day bound, incorrect provenance,
Git verification ordering, no secrets in logs, and refusal to auto-recover.
The new suite is in the fast PR preflight, followed by the normal full
offline tests and production DB/output-preservation gates.
