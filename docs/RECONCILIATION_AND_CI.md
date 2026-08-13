# Reconciliation and CI durability

How a diverged `pla_watch.db` is merged, and how CI keeps a regressed database
from reaching production.

Background: `pla_watch.db` is a binary file committed to git and written by two
authors — CI on a schedule, and humans on branches. Git can only offer "take
mine or take theirs", and either choice silently destroys a day of collection
(DECISION_LOG 2026-08-02). `scripts/reconcile_db.py` merges by content instead,
and runs as a git merge driver named in `.gitattributes`.

## Reconciliation algorithm

Order matters; each step depends on the one before.

0. **Validate every input, read-only** (`validate_inputs()`). Base, origin and
   local must each pass `integrity_check`, have an empty `foreign_key_check`,
   carry the legacy tables, and — for any newer table they *do* have — carry the
   columns needed to read it. A legacy input missing newer tables or the
   migration ledger is valid; that is what step 2 exists for. Corruption or a
   dangling foreign key is not, and merging from it can only produce a wrong
   answer. Validation reads a scratch copy (including any `-wal`), so an input
   cannot be altered even by opening it.

1. **Copy origin to the output path.** Origin is authoritative for identity: its
   article ids are already live as `output/article/<id>.html`.
2. **Migrate the output** (`normalize_schema()`) before a single row is merged.
   The merge target is therefore always current.
3. **Merge scrape runs.** Runs present in local but not in the merge base are
   local-authored; origin may have independently reused those ids, so they are
   renumbered above origin's maximum. The remap is retained.
4. **Merge local-only articles**, matched by `url` (the table's UNIQUE key),
   never by id. Inserted with fresh ids; categories and `scrape_run_id` follow
   the remap.
5. **Backfill analysis onto shared rows** still undecided in origin. Gated on
   `passed_relevance`, not `analyzed_at`: a rejection is a decision that cost a
   paid call (DECISION_LOG 2026-08-04).
6. **Merge per-source results** (below).
7. **Run the gates.** Any failure means the merged database is not used; in
   driver mode a non-zero exit leaves a normal conflict for a human.

### Why the schema is normalized first

Without step 2, a legacy origin blob produced a legacy merged database — no
`source_run_results`, no `schema_migrations`, and a `scrape_runs` CHECK that
rejects `'degraded'` — with every gate passing. Worse, a local run whose status
*was* `'degraded'` could not be inserted at all: the write raised, the driver
exited non-zero, and CI got a raw binary conflict unattended.

Leaving this to `init_db()` on the next pipeline run is not sufficient. By then
the regressed file has been committed and pushed, and rows the merge dropped are
gone regardless of what a later migration rebuilds.

Migration failure aborts reconciliation. Base, origin and local are never
mutated — only the output copy is written.

### Source-run-result merge

- **Source identity is the slug.** `source_run_results.source_slug` is TEXT.
  Numeric `sources.id` values are never compared across two independently
  evolved databases, so no identity guessing is involved.
- **Run lineage must be proven, never inferred from a coincidence.** A local
  row's run qualifies only if it is local-authored and present in the step-3
  remap, or inherited from the merge base and still present. **Anything else
  aborts reconciliation.** It is emphatically not enough that a run with the
  same numeric id exists in the output: origin allocates ids independently, so a
  dangling local id can coincide with a real and entirely unrelated origin run.
  Attaching an observation there misfiles analytical provenance, which is worse
  than losing it. Nothing is dropped, reattached or guessed.
- **Natural key** is `(scrape_run_id, source_slug)` *after* remapping.
- **Conflict rule: published/origin wins, and only on a true natural-key
  conflict.** That is possible only on a run both sides share (one present in
  the merge base) where each independently recorded the same source. Local-only
  rows are always kept.
- The surrogate `id` is never carried across, so the two sides' independently
  allocated ids cannot collide.

**Exact accounting.** Before writing, an expected map is built — origin's rows,
then mapped local rows, origin winning true conflicts — and the merged table is
compared against it key-for-key and payload-for-payload. Missing, unexpected or
altered rows abort the merge. This replaced a check that asked only whether a
slug appeared *somewhere* in the output, which could not see a dropped row
whenever any other row shared its slug.

Reconciliation is idempotent: it always starts from a fresh copy of origin, so
repeating it cannot accumulate duplicates.

### Article source attribution

A local article's numeric `source_id` is **never** carried into the output. For
each local article the reconciler resolves `loc.sources` → slug → the merged
database's own id for that slug.

Reconciliation stops for human review if the local `source_id` has no local
source row, if the slug is missing from the merged database, if a slug is
ambiguous there, or if a URL held by both sides is attributed to different
slugs. A source that cannot be mapped through tracked manifest/migration
configuration is not invented from local metadata.

Carrying the id verbatim was silently wrong: a local `pla_daily` article whose
`sources.id` happened to equal origin's `mod_china` id merged **as mod_china**,
with every gate green. Numeric ids may now differ freely between databases
provided the slugs map.

## Gates

A green gate result now proves all of:

- `integrity_check` is `ok`; `foreign_key_check` is empty
- every required table exists — **a missing table is a failure, never treated as
  an empty one**
- the migration ledger is complete
- `scrape_runs` accepts every status present in either input
- no duplicate article URLs; no article carried from base changed id
- no article URL lost from either side
- no screening decision lost from either side
- no `source_run_results` row unique to either side lost, **compared exactly by
  natural key and payload**, with local rows compared after their run remap
- no result present in the merge that belongs to neither input
- no origin payload altered by the merge
- no duplicate `(scrape_run_id, source_slug)`; no result orphaned from its run
- every article URL resolves to the source **slug** the inputs agree on

`tests/test_reconcile.py` drives the production `reconcile()` and `gates()` over
legacy/current permutations, colliding run ids, a true natural-key conflict, a
ledgerless database, unprovable run lineage in three shapes, slug/numeric-id
divergence and collision, conflicting shared-URL attribution, malformed inputs,
and deliberately tampered outputs that each gate must reject.

## Failed merges

When reconciliation fails — a malformed input, unprovable lineage, failed
accounting, or any gate — the driver exits non-zero and git's conflict is left
exactly as it was. The merge target is never replaced or partially modified, and
the temporary `.reconciled` database and its `-wal`/`-shm` sidecars are removed
so a failed unattended merge leaves no litter. Base, origin, local and the merge
target itself are never deleted, and cleanup cannot mask the original error.

## CI ordering

Before any collection, after dependency install:

1. `python -m migrations.cli --apply`
2. `python scripts/verify_db_current.py`
3. `python -m unittest discover -s tests -t .`
4. `python -m unittest tests.test_reconcile` (re-run alone for a clearer failure)
5. assert the suite left the tracked `pla_watch.db` clean

All carry implicit `success()`, so a failure at any of them stops the pipeline,
the commits and the deploy — before a single network request or paid model call.

### Post-rebase verification

Four steps can rebase before pushing: persist-on-failure, the billing marker,
the database/output commit, and the success marker. Each verifies the database
after its rebase and before its push.

**These are ordinarily no-ops**, because the reconciler's output is already
current. They exist so that a regressed database fails closed instead of
reaching origin.

- **Marker-only paths** (billing marker, success marker) verify but never
  repair. A repair there would put database changes into a commit whose
  documented responsibility is a single state file. Both also assert that
  nothing beyond their own marker is staged.
- **Database-committing paths** (persist-on-failure, the daily commit) may
  `--repair`, and must then prove the repair is inside the pushed commit: stage
  it, amend the not-yet-pushed commit, assert the working tree equals `HEAD`,
  and re-verify with repair disabled before pushing.

No force push is used anywhere. Persist-on-failure still commits `pla_watch.db`
only — never `output/`, which would route around the validator gate. The health
gate still runs last and only notifies.

`tests/test_workflow_contract.py` asserts this ordering by parsing the workflow,
so a later edit cannot silently move tests after the pipeline or push before
verification.

## Scope

This is Phase 1–2 **durability**: schema and per-source records survive a merge,
and CI fails closed. It is not Phase 3 **storage separation** — moving the
database and raw captures out of git, with snapshots and restore drills — which
remains unstarted and unauthorized.
