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

The last edition is No. 13, week ending 2026-08-08. The weeks ending
2026-08-15, 08-22 and 08-29 have no edition. This is the highest priority: the
analytical series is the layer that distinguishes this publication from a
scraper, and a lapsed cadence is visible to every reader.

Restoration means editions published through the full `EDITORIAL_QA_CHECKLIST.md`
gate — source-to-claim tracing and a rendered-page review — not a catch-up
batch that repeats the No. 12/No. 13 shortfall. Decide explicitly whether the
missed weeks are published retrospectively or recorded as a disclosed gap; a
gap that is ruled and recorded is acceptable, a gap that is silently skipped is
not.

### 2. Complete Singapore's required human reviews — Day 30 remains

**Day 7 and Day 14 are complete and published** to `review/singapore-mindef`,
both `pass_with_findings` (completed-review ids `403df921…3c3d89` and
`10a28df1…e7b756`). Day 7 was retrospective, against the historical state
commit; Day 14 used a focused queue of 16 of 40 records with Day 7's decisions
deliberately not carried forward.

**Day 30 is the remaining Singapore gate**, and it is a gate, not a formality:
two completed checkpoints qualify nothing. What is still missing is 30
consecutive collecting days, the Day 30 review, and an owner sign-off recorded
in `DECISION_LOG.md`.

Procedure is in `docs/SHADOW_REVIEW.md`. Nothing about this is automatable: an
unfilled report is not evidence of a completed review.

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

903 records have never been relevance-screened. Draining the whole backlog is
not the goal and never was — it is spend against material no edition cites.

Screen **only** the window an edition will draw on, using
`backfill_unscored.py --since X --until Y`, sequentially, never concurrently.
Re-measure before estimating; pass rates move. This unblocks priority 1 and is
sequenced behind it for that reason.

### 4. Terminal processing states and retry budgets

There is no terminal state for a record that cannot be processed. 48 records
hold an empty body; 3 of those passed relevance and are unanalyzed, so they
re-enter the analysis queue on every run and can never clear. A body that was
never captured at scrape time is a collection defect, and no number of
translation retries will fix it.

What is needed: an explicit terminal disposition (recorded, not deleted, and
distinguishable from "pending"), a bounded retry budget per record, and a count
of terminal records on the coverage surface so the state is visible rather than
silently absorbed. Empty-body records are also a scoring-path question — an
article that passed relevance on its title alone should be identifiable.

### 5. Japan shadow: an explicit continue or pause decision

Japan is at shadow day 5 with health `partial`. RSS discovery works and PDF
documents retrieve in full, but HTML documents on the same host are returned
behind an interactive challenge — 28 of 32 selected items in the most recent
run. The challenge is never to be bypassed, so the ceiling on this desk is set
by the ministry, not by engineering.

The decision to take, and to record in `DECISION_LOG.md`: **continue** shadow
collection as a discovery-only record with retrieval openly reported as
partial, **pause** it pending a request for an official route, or **stop** it.
Letting it run indefinitely without a ruling is the option to avoid — it
accumulates evaluation days that cannot support a promotion argument.

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
re-measure before asserting one. The **PLA Watch edition archive** is a
separate surface with its own shape, and month grouping there at ~20+ editions
remains a legitimate later consideration.

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
