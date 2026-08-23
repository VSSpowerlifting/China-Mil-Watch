# Singapore shadow checkpoint reviews

The 30-day qualification requires that manual corpus reviews happen around days
7, 14 and 30, and that there is evidence they happened. This document is how
those reviews are run so that they are reproducible rather than improvised.

`scripts/review_shadow_state.py` produces the evidence package. It validates
what a machine can validate and then stops. **The checkpoint is a person
reading stored records against the ministry's own pages.** Nothing in the tool
substitutes for that, and the report says so on its first screen.

---

## Running a checkpoint

Take a fresh copy of the state branch — never review the branch in place, and
never point the tool at a working tree:

```bash
git clone --branch shadow/singapore-mindef --single-branch \
  https://github.com/VSSpowerlifting/China-Mil-Watch.git /tmp/shadow-review
rm -rf /tmp/shadow-review/.git

python scripts/review_shadow_state.py \
  --state-dir /tmp/shadow-review/state \
  --out ~/shadow-reviews/day-07 \
  --as-of 2026-08-27 \
  --review-all
```

`--as-of` is what makes a package reproducible; pass it explicitly. Exit status
is `0` when no anomalies were found, `1` when there are anomalies to explain,
and `2` when the state was refused outright.

While the corpus is small enough to read end to end, use `--review-all`. Once it
is not, use `--since-ledger <filename>` to queue everything first seen since the
previous checkpoint; the focused rules below fill in the rest.

## What the tool refuses

It fails closed rather than reviewing something it does not understand:

* a `--state-dir` inside the repository, or one containing `pla_watch.db` or
  `output/` — that is production, not shadow state
* an `--out` inside the repository (review evidence is not source)
* a `shadow_records` table whose columns are not exactly what the collector
  creates, or a ledger missing any required field
* a missing or unparseable `clock.json`
* any input file that changes while the review is running — the package is void

The database is opened `mode=ro&immutable=1`: no lock is taken and no `-wal` or
`-shm` can appear beside it. Every input is hashed before and after.

The runtime imports are stdlib plus `core.collection.status`, a module of
constants. The adapter is deliberately not imported — it pulls in `requests`,
and `config` reads `.env` and names the production database. The URL shape, slug
date and slug kind are re-derived in the tool, and a test imports both and
asserts they agree, so the copies cannot drift.

## What it checks

Schema and integrity; foreign keys; clock validity, single initialisation, and
agreement with the day-zero ledger; ledger filename/content identity; unique run
ids; chronological order; missing days inside the observed period; recognised
results; health/result agreement; the collector's own result-taxonomy decision
tree re-evaluated against the counts; the state-hash chain including the rule
that a duplicate-only run must not change the database; the final hash against
the database on disk; that a failed run did not advance the clock; `shadow_day`
recomputed as complete elapsed 24-hour periods; required record fields; unique
canonical URLs; recomputed content hashes; dates and kinds against the official
slug; empty bodies and known challenge/error stubs; and that no foreign or
production record has entered the Singapore database.

Bodies are judged by structure, not by length. The collector refuses a body
under 200 characters, so anything shorter contradicts the collector that wrote
it — but no length is treated as proof of completeness. That is a reviewer
judgement, which is why the queue exists.

## The review queue

`shadow-review-queue/1`. Every reason is a property of the data, so the same
state always yields the same queue:

* every record first seen since the previous checkpoint (`--since-ledger`)
* every record carrying a validation flag
* every member of a duplicate-title group
* one representative of each publication kind
* oldest and newest by publication date
* shortest substantive and longest body
* a deterministic remainder chosen by lowest content hash

This is a **targeted queue, not a statistically representative sample.** No
conclusion about unreviewed records follows from it.

## What the reviewer must do

For each queued record: open the canonical URL, and confirm the stored title,
publication date, body completeness, canonical URL and publication kind against
the page — and that no access-denial or template text was stored instead of the
document. Then complete the sign-off block: reviewer identity, completion
timestamp, records reviewed, anomalies accepted with reasons, and a verdict.

**An unfilled report is not evidence of a completed review.** A package with an
empty sign-off block records that a review was requested, not that one happened.

---

## Where completed review evidence should live

Four mechanisms were considered. None is implemented; this section is the
recommendation, not a change.

| | Durability | Auditability | Privacy | Contaminates state | Can trigger deploy | Compares across days | Proves which corpus |
|---|---|---|---|---|---|---|---|
| **1. Commit into the state branch** | high | high | public | **yes** | no | easy | yes |
| **2. Actions artifacts** | **90 days** | medium | repo-private | no | no | awkward | yes |
| **3. Separate private review branch** | high | high | private if the repo is | no | no | easy | yes |
| **4. Local hash-identified packets** | operator-dependent | low once off-machine | private | no | no | manual | yes |

**Recommended: (3), a separate review branch — `review/singapore-mindef`.**

Option 1 is rejected for one specific reason: the state branch is the artifact
under review. Writing review output into it means the thing being audited and
the audit live in the same history, and a later hash comparison can no longer
distinguish collector output from reviewer output. It also makes an
`ok_all_duplicates` day, which currently leaves the database untouched, start
carrying unrelated commits.

Option 2 expires at 90 days. The Day 7 artifact would be gone before a Day 30
review needed to compare against it, which defeats the purpose.

Option 4 has no durability guarantee once the machine changes.

Option 3 keeps every property that matters — durable, diffable, attributable,
easy to compare across checkpoints — while keeping reviewer output strictly out
of the evidence it assesses. Each packet is identified by its
`deterministic_sha256`, which is computed over the manifest and inventory and
excludes wall-clock time, so it names exactly which corpus was reviewed.

If it is adopted, the branch must be orphan, must never be merged to `main`, and
must have no workflow of its own — the same constraints the state branch already
carries.
