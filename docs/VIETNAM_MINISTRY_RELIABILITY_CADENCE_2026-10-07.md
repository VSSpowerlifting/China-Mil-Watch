# Vietnam ministry reliability cadence — 2026-10-07

## Decision

Vietnam's three approved ministry sources move from one-off remote activation to
a bounded daily reliability period. The schedule is activated only when the
cadence PR is merged. Vietnam remains a research/shadow desk; nothing here
admits production records, changes public coverage claims, or authorizes the
Government News source.

## Day 0 evidence

The first dispatch, Actions run `37656171920` attempt 1, stopped before
publication when `https://moit.gov.vn/robots.txt` returned HTTP 502. MPS had
completed locally, but all three state branches remained absent.

Attempt 2 of the same run succeeded end to end on collector
`2c21b0d091ffc288b1a106d5459d758aaaac6ff5` and is the durable Day 0:

| Source | Day 0 UTC | Branch head | Day-0 result |
|---|---|---|---|
| `vn_mps_foreign_affairs_vi` | 2026-10-07T17:16:33+00:00 | `9098f48ea1e6d33d5a3600d08337e53f19270490` | 2 new |
| `vn_moit_energy_vi` | 2026-10-07T17:16:44+00:00 | `e4e97954011fffbe1fe5cb80a4a658cf09c58f8a` | 2 new |
| `vn_moit_foundational_industry_vi` | 2026-10-07T17:16:53+00:00 | `4da050e41ddddc068ada016d8fcd98b4348400e1` | 1 new |

Attempt-2 artifact: `vietnam-ministry-shadow-37656171920-2`, ID
`11499686512`, digest
`sha256:e935588163b383335d7daf1c021cf530c6c843f287fbe6b3e760983119131dc5`.
Attempt 1 remains separate failed-attempt evidence and its MPS clock is never
imported.

## Daily collection contract

The workflow runs once per day at **18:17 UTC**. That is 01:17 in Hanoi on the
following calendar day. For a scheduled first attempt, the repository
`core.shadow_schedule` resolver assigns the UTC date of the 18:17 slot as the
logical target date, which is the Hanoi publication date the run is closing
out. GitHub runner delay therefore cannot silently move the ledger to the next
UTC date.

Every scheduled run uses:

- six-day lookback;
- cap 40 per source; a larger proven window fails rather than samples;
- serial order: MPS foreign affairs, MOIT energy, MOIT foundational industry;
- one shared cross-process gate for the two MOIT families;
- the existing Indo-Pacific Record collector identity;
- success-only publication to the three existing orphan state branches;
- complete attempt artifacts retained for 90 days.

The schedule may not bootstrap a missing state branch or clock. Day 0 already
exists; an absent branch is an incident, not permission to restart the clock.

## Failure and recovery

A collection failure stops the remaining sources and publishes none. Publication
still consists of three ordinary fast-forward pushes, so a push failure can
produce a partial publication boundary; if that occurs, stop for owner review
rather than repairing or retrying automatically.

There is **no automatic retry**. Do not use the Actions re-run button for a
failed scheduled slot. Recovery is a fresh manual workflow dispatch with
`target_date=YYYY-MM-DD` naming the intended logical date. Manual recovery
uses the same six-day lookback and cap 40. The collector records
`target_date_source=explicit`; scheduled runs record `schedule-slot`.

## Checkpoints

The three source clocks differ only by seconds, so the checkpoint calendar is
shared:

| Checkpoint | Earliest scheduled run that reaches it | Human action |
|---|---|---|
| Day 7 | 2026-10-14 18:17 UTC | Generate three commit-bound Day-07 packets and complete human review |
| Day 14 | 2026-10-21 18:17 UTC | Generate three Day-14 packets from then-current branch heads |
| Day 30 | 2026-11-06 18:17 UTC | Generate three Day-30 packets; owner decides qualification/cadence continuation |

After each checkpoint run completes, clone each fixed state branch, pin its
current commit, and generate the formal packet with
`scripts/review_vietnam_ministry_state.py --state-repo ... --state-commit ...
--checkpoint day-07|day-14|day-30 --as-of YYYY-MM-DD --out-dir ...`.
The packet must be completed by a human and validated with `--check-signoff`.
An early, blank, or failed packet is not a completed checkpoint.

A 30-day clock does not qualify or promote Vietnam by itself. The standing rule
still requires 30 consecutive collecting days, completed human checkpoint
reviews, and owner sign-off. Day 30 is also the decision point for whether this
cron continues, is revised, or is removed.

## Explicitly out of scope

Government News `vn_vgp_defense_en`, production admission, rendering,
deployment, automated review publication, automatic promotion, new ministry
sources, Defence/Finance probing, and any bypass of source access controls.
