# Vietnam ministries — three-source checkpoint rollup

Status: evidence preparation only. No collection, publication, signoffs,
qualification, collector activation or source-rights change.

The three ministry publication families began their independent remote
shadow clocks on October 7, 2026, only seconds apart.

| Source | Isolated state branch |
| --- | --- |
| vn_mps_foreign_affairs_vi | shadow/vietnam-mps-foreign-affairs |
| vn_moit_energy_vi | shadow/vietnam-moit-energy |
| vn_moit_foundational_industry_vi | shadow/vietnam-moit-foundational-industry |

Scheduled earliest eligible checkpoint reviews (after each scheduled run):
Day 7, October 14; Day 14, October 21; Day 30, November 6, 2026.

## Why this tool matters

The existing per-source producer at
scripts/review_vietnam_ministry_state.py verifies each source's committed
state tree and creates a complete source-corpus review packet for Day
7, 14 or 30. It cannot by itself show whether *all three* separate
sources have produced comparable packets. A green MPS packet is not a
green Vietnam Desk; every source needs independent evidence.

The new read-only script at
scripts/vietnam_ministry_checkpoint_rollup.py takes exactly three
already-generated formal packet directories. It checks each packet's
five SHA-256 artifact hashes and deterministic package identity, the
declared source/branch/commit identities, an aligned checkpoint name and
as-of date, consistency of machine checkpoint thresholds, and Day 0
clocks belonging to the same original five-minute activation batch.

It rejects missing/duplicate/foreign sources, wrong branch assignments,
mixed checkpoint days, mismatched dates, unexpected files, symlinks,
corrupt artifacts, contradictory threshold flags, and in-band human
signoffs. It also **warns** when the three latest published run IDs differ,
which can expose a partial cross-branch publication or recovery mismatch;
that mismatch requires reconciliation, not automatic state repair. Its output describes per-source collecting days, gaps,
uncovered publication windows, anomalies and records awaiting review.

## Procedure

First run the existing *formal* producer independently for each source,
from a legitimate state Git checkout that contains all fixed branches.
Replace each placeholder SHA with that branch's actual, immutable state
commit obtained after the relevant checkpoint run. Never put actual
source HTML or entire state captures into the production branch.

Example for MPS:

~~~bash
python scripts/review_vietnam_ministry_state.py \
  --source vn_mps_foreign_affairs_vi \
  --state-repo /path/to/source-state-repo \
  --state-commit <MPS-40-character-SHA> \
  --checkpoint day-07 --as-of 2026-10-14 \
  --out-dir /tmp/vn-mps-day07
~~~

Repeat with vn_moit_energy_vi and
vn_moit_foundational_industry_vi, their own pinned commits, and
their own output directories. Ensure every packet is complete and
verified by the producer. Only then:

~~~bash
python -m scripts.vietnam_ministry_checkpoint_rollup \
  /tmp/vn-mps-day07 \
  /tmp/vn-moit-energy-day07 \
  /tmp/vn-moit-foundational-day07
~~~

The command prints a machine evidence summary to stdout, makes
no publisher requests, and writes nothing. Day 14/30 use the same
three-packet contract with those specific checkpoint names.

## Evidence and authority boundaries

- The separate per-source **producer** establishes Git provenance.
  The rollup rechecks the local packet hashes but does not independently
  verify remote branch reachability or original publisher authenticity.
- Failed GitHub Actions attempts may never publish their state to the
  source branches. Reviewers must inspect Actions run histories,
  complete attempt artifacts and manual-recovery explanations outside
  this rollup. A clean state packet does not erase a failed attempt.
- The checkpoint_reached flag means elapsed machine time only. Human
  review requires reading every source record/version against the
  publisher; a reviewer must independently validate each source's
  signoff through the existing --check-signoff flow.
- All report qualification, human signoff, republication-rights and
  production-promotion booleans are unconditionally false.
- Day 30 additionally requires 30 consecutive collecting days and
  explicit owner approval. Do not inherit MPS/MOIT findings for the
  disabled National Defence Journal source.
- MPS's separate editorial queue has unapproved, mechanically
  reviewable candidates; this rollup cannot authorize promotion.

See:
docs/VIETNAM_MINISTRY_RELIABILITY_CADENCE_2026-10-07.md
docs/VIETNAM_MPS_FIRST_REVIEW_QUEUE_EVIDENCE_2026-10-08.md
docs/VIETNAM_MINISTRY_EXPANSION_2026-10-07.md

All unit-test packet data is synthetic. No state corpus is read or
retained in the tracked repository.
