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

Take a fresh clone of the state branch — never review the branch in place, and
never point the tool at the production worktree. Keep the clone's `.git`: it is
what proves which commit the evidence came from.

```bash
git clone --branch shadow/singapore-mindef --single-branch \
  https://github.com/VSSpowerlifting/China-Mil-Watch.git /tmp/shadow-review
STATE_COMMIT=$(git -C /tmp/shadow-review rev-parse HEAD)

python scripts/review_shadow_state.py \
  --state-repo /tmp/shadow-review \
  --out ~/shadow-reviews/day-07 \
  --as-of 2026-08-27 \
  --review-all \
  --checkpoint day-07 --state-commit "$STATE_COMMIT"
```

To exercise the tooling without producing a publishable packet, drop
`--state-repo`, `--checkpoint` and `--state-commit` and pass `--state-dir` at a
copy of `state/` instead. That is a rehearsal, and it says so.

`--as-of` is what makes a package reproducible; pass it explicitly. Exit status
is `0` when no anomalies were found, `1` when there are anomalies to explain,
and `2` when the state was refused outright.

While the corpus is small enough to read end to end, use `--review-all`. Once it
is not, use `--since-ledger <filename>` to queue everything first seen since the
previous checkpoint; the focused rules below fill in the rest.

## What the tool refuses

It fails closed rather than reviewing something it does not understand:

* a rehearsal `--state-dir` inside the repository, or one containing `pla_watch.db` or
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

## Formal packets versus rehearsals

A packet generated from `--state-dir` — an ordinary directory, trusted as-is —
is a **rehearsal**. It identifies a corpus but not a point in the state
branch's history, so it can describe evidence it cannot pin down. The report
says NOT PUBLISHABLE on its first screen and the publisher refuses it. Use it
to exercise the tooling.

A **formal** packet names both, and — this is the part a SHA alone cannot give
you — its inputs are read from the commit itself. `state/` is exported from the
Git object named by `--state-commit` with `git cat-file`, and those exported
bytes are the ones hashed, analysed and packaged. A working-tree copy is
refused in this mode rather than quietly preferred, because a directory that
merely looks like state is exactly what a substitution attack supplies.

Four claims are established before anything is written:

| Claim | Refused when |
|---|---|
| the commit exists in `--state-repo` | the object is absent, or is not a commit |
| it belongs to this desk's history | it is not reachable from `--state-ref` (default `shadow/singapore-mindef`) |
| it carries a reviewable tree | there is no `state/` tree, or a required file is missing |
| the tree cannot redirect a read | any entry is a symlink, submodule, or an unrecognised file |

The verified commit **and tree** identities travel in the manifest, the
receipt, and the preserved commit message. `state_commit` is what was claimed;
`state_tree` is what was read.

**Do not remove `.git`.** The old instruction to strip it before generating a
packet is what made the claim unverifiable: with no objects to check against,
`--state-commit` was trusted text.

```bash
git clone --branch shadow/singapore-mindef --single-branch \
  https://github.com/VSSpowerlifting/China-Mil-Watch.git /tmp/shadow-day7
STATE_COMMIT=$(git -C /tmp/shadow-day7 rev-parse HEAD)

python scripts/review_shadow_state.py \
  --state-repo /tmp/shadow-day7 \
  --out ~/shadow-reviews/day-07 \
  --as-of 2026-08-27 --review-all \
  --checkpoint day-07 --state-commit "$STATE_COMMIT"
```

Once the clone exists, verification touches the network no further: every
object it reads is already local.

## The structured sign-off

The packet emits `signoff_template.json`. Fill that, not the Markdown — prose a
program cannot check is not evidence a program can defend.

Every per-record check is an explicit boolean. `"yes"` is refused: a truthy
string is exactly the kind of answer that looks complete and means nothing.
Each record needs all of `source_page_opened`, `title_matches`,
`publication_date_matches`, `canonical_url_matches`, `body_appears_complete`,
`kind_is_reasonable`, `no_denial_or_template_stored`, plus a `note` (`""` when
there is nothing to say).

Verdicts:

| Verdict | Allowed when |
|---|---|
| `pass` | every check true **and** every packet anomaly disposed |
| `pass_with_findings` | findings exist, every anomaly disposed |
| `fail` | always — an honest failing review is evidence and is preserved |

A partially filled sign-off stays useful as a work-in-progress file and is
categorically non-publishable.

## Three identities

| Identity | Names |
|---|---|
| automated package id | what was **presented** for review |
| completed-review id | the review **answers** and attestation, bound to that package |
| the Git commit | **when and by whom** the completed review was preserved |

The completed-review id is a hash over the canonicalised sign-off plus the
package id, so key order in the file cannot change it and a changed answer
always does. **None of these is a cryptographic signature**, and none verifies
the reviewer's legal identity.

One package id names one set of bytes. Two runs of the same state commit with
the same `--as-of` produce byte-identical packet files, the manifest included,
so an independently regenerated packet republishes as a no-op rather than
colliding with itself. When a packet was generated, and where, goes to
`generation_context.json` beside it — not into the package, and not onto the
review branch. The Git commit records when the review was preserved.

## Publishing

```bash
# validate and prepare only — this is the default
python scripts/publish_shadow_review.py \
  --packet ~/shadow-reviews/day-07 \
  --signoff ~/shadow-reviews/day-07/signoff.json \
  --remote git@github.com:VSSpowerlifting/China-Mil-Watch.git \
  --checkpoint day-07 --bootstrap

# preserve it
... --bootstrap --publish            # first ever publication
... --expected-head <sha> --publish  # every publication after that
```

The target branch is a constant, not an argument: a publisher that can be
pointed anywhere is one typo from writing review output onto `main`. Pushes are
ordinary fast-forwards — no force, no lease, no ref deletion, and no ref but
`review/singapore-mindef`. The remote head is re-read immediately before the
push, so a writer who moved the branch during preparation causes a refusal
rather than a race.

Layout:

```
README.md
index.jsonl                                  append-only
reviews/day-07/<completed-review-id>/review_manifest.json
                                     review_report.md
                                     record_inventory.jsonl
                                     signoff.json
                                     receipt.json
```

Append-only in practice: republishing identical content is an explicit no-op;
different content under the same id is refused; existing files are never
rewritten; and a failing review can never be quietly replaced by a passing one.
Two honest attempts at one checkpoint may coexist under distinct ids, and each
receipt records the others.

The packet is allowlisted on the way in. A database, sidecar, workflow file,
executable, or anything matching a credential pattern is a refusal, not
something skipped quietly.

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
