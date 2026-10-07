# Roadmap — Indo-Pacific Record

Authoritative forward plan. **Replaces the 2026-07-11 frontend release
sequence (R1–R5, tickets T1–T5)**, which was written before the rebrand, before
the record architecture launched, and before either shadow desk existed. That
plan is superseded; its remaining useful ideas are carried into
§Explicitly deferred below, and its full text is in Git history. This document
also continues to supersede `DESIGN_BACKLOG.md` (2026-07-11).

Pipeline-layer backlog (analyzer, scrapers, relevance filter) is in
`docs/v2_roadmap.md`. Specs referenced below:
`docs/VISUAL_AND_MOTION_SYSTEM.md` (V&M), `docs/DESIGN_SYSTEM.md` (DS).

Completed work is recorded in `DECISION_LOG.md` and in Git history, not here.
Current operational state is in `PROJECT_STATE.md`.

The ordering principle: **research and review gates before presentation.** The
project's credibility rests on the analytical publication cadence, on completed
human reviews, and on honest coverage — not on the front end. Nothing below
reorders around a frontend idea.

---

## Priority order

### 1. Restore the human analytical publication cadence

The latest approved edition is No. 14, week ending 2026-08-15.
No. 14 (week ending 2026-08-15) was served from 2026-09-05 without recorded
approval. The owner approved the reviewed corrections on 2026-10-03, retaining
No. 14 and its URL with a dated correction note (DECISION_LOG). Its status is
reconciled; the next number is 15, assigned only at a subsequent Brief's own
approval. The separate week-ending 2026-08-22 disposition remains open.

Restoration means editions published through the full `EDITORIAL_QA_CHECKLIST.md`
gate — source-to-claim tracing and a rendered-page review — not a catch-up
batch that repeats the No. 12/No. 13 shortfall. Decide explicitly whether the
missed weeks are published retrospectively or recorded as a disclosed gap; a
gap that is ruled and recorded is acceptable, a gap that is silently skipped is
not.

### 2. Close Singapore's Day 30 review evidence gap

**Singapore has been live since the 2026-09-21 owner sign-off** in
`DECISION_LOG.md`. The decision records 33 elapsed shadow days and completed
Day 7 and Day 14 human reviews, and explicitly proceeds without a distinct
Day 30 human review. The earlier reviews are published to
`review/singapore-mindef`, both `pass_with_findings` (completed-review ids
`403df921…3c3d89` and `10a28df1…e7b756`).

**The Day 30 human review remains unrecorded.** This is an evidence gap, not
a pending desk-status gate. To close it, complete a retrospective human review
against the exact historical state and publish the actual review date. That
would strengthen the record but would not make the review contemporaneous or
establish that Singapore is qualified.

Procedure is in `docs/SHADOW_REVIEW.md`. An unfilled or computed packet is not
evidence of a completed human review.

**Packet verified 2026-09-28; review not done.**
- State commit `be52cc125` (32 ledgers, `shadow_day` 30) reproduces the
  recorded state tree `ad97f27d…`: 59 records, `publishable: yes`.
- The package id depends on `--as-of`, `--state-ref` and scope. The recorded
  `4ad9a838…` did not record them, so the review binds to the packet it
  actually builds, dated on the day of review.
- What remains is the owner's:
  - choose a scope: the complete corpus (59), or the queue since the Day 14
    ledger (32);
  - review against the live pages;
  - sign;
  - publish;
  - record.
- The invocations and the known pre-overlay and drift findings are in
  `docs/DESK_CONSOLIDATION_AND_BRIEF_PREP_2026-09-28.md` §3.

**Being late does not close the checkpoint.** A Day 7 review that was not done
on day 7 can still be completed retrospectively, against the exact historical
state commit that the branch held at that checkpoint — that is what
`--state-commit` is for, and why the packet reads its inputs from the commit
object rather than from a working tree. The requirements are:

* the evidence packet names the historical state commit it was built from;
* the review and its sign-off carry **the actual date the human review
  happened**, not the date being reviewed;
* nothing is backdated, and no packet is presented as contemporaneous when it
  was not.

A delayed checkpoint review is still real evidence, and it still qualifies
nothing on its own.

### 3. Scoped screening and backfill for publication-ready windows

616 records have never been relevance-screened (measured 2026-09-28: China
desk 566, Singapore 50). Draining the whole backlog is not the goal and never
was — it is spend against material no edition cites.

Screen **only** the window an edition will draw on, using
`backfill_unscored.py --since X --until Y`, sequentially, never concurrently.
Re-measure before estimating; pass rates move. This unblocks priority 1 and is
sequenced behind it for that reason.

**Singapore's screening is repaired in source; it is not yet run.**
- The old rules were China-scoped, and all 14 screened Singapore records were
  rejected.
- Since 2026-09-29, Singapore is judged against its registry scope
  (`processing/screening.py`).
- It is held out of the daily queue until the owner rules on three things: the
  rubric, a reviewed re-screening proposal (64 records, about $0.27 at most),
  and what analysis follows a pass.
- See `docs/SINGAPORE_SCREENING_REPAIR_2026-09-29.md`.

A brief can cite `awaiting_screening` records
as they are, since the brief contract carries each record's processing state
and never filters on it.

### 4. Processing states and collection continuity

**Processing states are implemented** (`core/processing_state.py`,
2026-09-16):
- a retry budget of 5;
- `retriable`, `paused` and `terminal` dispositions, recorded and never deleted.

`terminal` is reachable only through an adapter's content verdict, currently
from `global_times_mil` and `xinhua_mil`. Measured 2026-09-28: 7 paused, 5
retriable, 0 terminal.

**Remaining:**
- Publicly, paused records are shown as `analysis_incomplete`. Whether the
  coverage surface should show them separately is still open.
- An article that passed relevance on its title alone should still be
  identifiable.

**Collection continuity is the newer gap.**
- The daily workflow runs the offline test suite before collecting, so a test
  failure cancels that day's collection. That happened on 09-15, 09-18 and
  09-19. 09-15 is unrecovered for `pla_daily`, `china_mil_online` and
  `global_times_mil`.
- Health and liveness reports read stored records, so they cannot see a day
  that never reached collection.
- Singapore's single-day production window was fixed on 2026-09-28. The
  three releases it lost were not recovered by the authorized 09-28 run.
  The 2026-10-06 refresh confirms `23sep26-mq` is now stored (id 4759).
  - The authorized 09-28 run was withheld whole by `22sep26-infographic`,
    an image-only page whose 178 characters of text are page furniture.
  - PR #85 is refreshed against current main, pending an owner merge decision:
    an image-only release is stored as a text-unavailable record and no longer
    blocks the batch
    (`docs/SINGAPORE_IMAGE_ONLY_RELEASES_2026-09-29.md`). After review and
    merge and separate recovery authorization, one Singapore-only, no-analysis
    recovery for 09-22 → 09-28 proposes exactly three inserts (`22sep26-nr`,
    `22sep26-speech`, the infographic) and eight duplicates. These are the only
    eligible September releases missing in the fresh sitemap/database comparison;
    `16sep26-speech` remains a governed hold.
- To decide:
  - disclose or recover 09-15;
  - whether collection should depend on the test gate.

### 5. Japan shadow: an explicit continue or pause decision

**Measured 2026-09-28.** Japan has 34 ledgers, health `partial` on every
recent run.
- Only 4 bodies have ever been stored, all PDFs.
- HTML documents on the same host are returned behind an interactive
  challenge. The challenge is never to be bypassed, so the ceiling on this
  desk is set by the ministry, not by engineering.
- Oldest-first selection under a 40-item cap re-selects the same challenged
  items every run. Items published since about 09-18 are deferred and never
  recorded, and the `ok_all_duplicates` label hides it. If the desk continues,
  fix that and report the deferral and challenge counts, without any change to
  access.

The decision to take, and to record in `DECISION_LOG.md`: **continue** shadow
collection as a discovery-only record with retrieval openly reported as
partial, **pause** it pending a request for an official route, or **stop** it.
Letting it run indefinitely without a ruling is the option to avoid — it
accumulates evaluation days that cannot support a promotion argument.

**US DVIDS shadow, same class of decision.**
- The DVIDS route is separate from the `access_blocked` command website.
- It has failed every scheduled run since 2026-09-20, all robots.txt 5xx, so
  permission was undetermined. Its only success was a manual dispatch on
  09-19.
- The cause is not established. Any diagnosis is a single identified request,
  never a workaround.
- On every shadow desk, a failed run's ledger survives only as a 90-day
  artifact, because state is persisted only on success. Whether to persist
  failed-run ledgers is a decision for all three workflows together.

### 6. Decouple preservation and rendering from LLM availability

Collection already survives an analysis-stage failure, but preservation,
rendering and publication remain coupled to model availability more tightly
than they should be. An account-level block should degrade analysis only: the
record must still be preserved, the site must still render, and the public
surface must say which layer is degraded. This is the durability property that
makes the archive claim honest.

### 7. Cross-source occurrence and provenance modelling

Canonical selection keeps one copy of a same-story group and discards the
losing copies' URLs, so "both institutions carried this release" is recorded
nowhere. That is a provenance-model gap, not a dedup bug, and it will get worse
as desks are added: cross-desk occurrence is exactly the analytical signal a
multi-desk publication exists to show.

Needs an occurrence model that records every institution that published a text
and every URL it appeared at, with canonical selection as a presentation choice
over that record rather than a destructive one.

### 8. Repository growth thresholds and a storage strategy

Three different measurements, which are routinely conflated. All taken
2026-09-02 on this project checkout.

| Measurement | Value | What it means |
|---|---|---|
| `git count-objects -vH` → `size-pack` | **296.28 MiB** in 18 packs, plus 30.11 MiB loose | Git object store as this checkout holds it. Repeatable, but pack layout dependent. |
| Fresh clone, repacked | **~167.50 MiB** packed / ~169 MB `.git` (independent measurement) | The portable figure: what someone cloning today actually downloads and stores. |
| `du -sh .git` | 334 MB | **Checkout-specific.** Reflects 18 unconsolidated packs and loose objects accumulated by incremental fetches. Not an intrinsic property of the repository. |
| `du -sh output` | ~94 MB, 5,400 tracked files | Tracked generated output. |
| `du -sh pla_watch.db` | ~32 MB | Tracked database, committed on every daily run. |

The gap between the first two rows is the point: `size-pack` on a
long-lived working checkout roughly doubles the packed size a fresh clone
sees, so **never quote a local `.git` directory size as the repository's
size.** Quote `size-pack` with its date and pack count, or quote a fresh
clone.

Nothing here is broken yet and nothing should be rewritten reactively.

What is needed first is a **threshold**, recorded in `PROJECT_STATE.md` and
stated against the fresh-clone packed size rather than a local directory: the
size at which the current arrangement stops being acceptable, and what happens
then — artifact storage for generated output, a separate data branch, LFS, or
periodic snapshots. Deciding after the fact means deciding under pressure, and
history rewriting on a repository holding cited evidence is not a step to take
in a hurry.

---

## Explicitly deferred

**Further frontend polish is deferred** until priorities 1–5 are healthy. The
record architecture launched, the component and homepage passes have landed,
and additional visual refinement is not what the publication is short of.

**Geographic promotion is deferred.** No new desk is declared, promoted or
presented as coverage until an existing shadow desk completes 30 consecutive
collecting days, its human checkpoint reviews, and an owner sign-off recorded in
`DECISION_LOG.md`. The US Indo-Pacific desk stays `access_blocked` while
`robots.txt` returns 403; a desk that cannot establish permission is not built.

**The record archive is not on this list, and the old "archive weight" ticket
is retired.** It was written against an 804 KB flat all-records page that no
longer exists. Measured 2026-09-02 on the tracked tree: `output/archive.html`
is **15,911 bytes**, a compact index of 18 linked weeks, and the corpus is
served by **85 generated `week-*.html` pages**, paginated within a week where
needed; the largest of them is under 30 KB against the DS §8 budget of 300 KB.
There is no present defect to fix. Re-open the question only on a measured
budget crossing — an archive index over 300 KB, a single generated week page
over 300 KB, or a week index that no longer fits one screen of scanning — and
re-measure before asserting one. The earlier PLA Watch issues are rows of the one Briefs catalog on Analysis
(DECISION_LOG 2026-09-30), and month grouping there at ~20+ items remains a
legitimate later consideration. Brief feed ordering (`build_briefs_feed` sorts
by issue number, which is unsafe for unnumbered Briefs) is future work.

Also deferred, carried forward from the superseded plan and still valid when
the gates above are healthy:

* Image and asset hygiene against the DS §8 budgets.
* `executive_readout` rendering — analyst-authored only, render-if-present,
  never synthesized.
* Cross-edition continuity and term relations — only from real sidecar data.
* Cadence-aware summaries and relevance-filter tightening
  (`docs/v2_roadmap.md`).

---

## Ticket hygiene

Every ticket must state: objective, reader value, affected routes, files,
dependencies, required metadata, model + skills, complexity, risk, acceptance
criteria, validation method. A ticket that cannot fill its metadata honestly —
because the data does not exist — goes to §Explicitly deferred, not to
implementation.
