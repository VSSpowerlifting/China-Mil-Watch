# ADR — Country-neutral core

Status: **accepted, Phases 1–2 implemented** (2026-08-13)
Scope: internal architecture only. No public rename, no route change, no new desk.

## Context

China Mil Watch works, and its weaknesses are structural rather than cosmetic:

- The corpus is ~87% PLA Daily. A smaller source can die without moving any
  total, and one did — MOD China was silent for four weeks with no failed run
  (DECISION_LOG 2026-08-09 §5).
- A configured source could contribute nothing while every run reported success.
  Xinhua Military has produced zero rows for the life of the project.
- China-specific institutions, languages, categories and prompts sat in central
  modules, so a second desk could not exist without editing the pipeline.
- `scripts/reconcile_db.py` resolves a diverged database by copying the
  published side's *file*. A schema change therefore reverts silently on rebase.
  It has happened twice to the same `'degraded'` constraint.

## Decision

Introduce a neutral core **alongside** the existing packages rather than
relocating them.

```
core/        domain vocabulary, manifest loading, registry, collection contract
adapters/    compatibility wrappers over existing scrapers
desks/       per-country configuration (manifest.json, taxonomy.json)
migrations/  versioned, idempotent schema evolution
```

`scraper/`, `analysis/`, `processing/`, `storage/`, `site/` keep their present
locations and behaviour. Nothing was moved to make the tree look tidier.

### 1. Configuration, not central imports

`pipeline.py` no longer names a scraper class. Sources come from
`desks/*/manifest.json`, including the dotted path to each adapter, resolved at
call time by `core/registry.py`. Adding, disabling or re-pointing a source is a
configuration edit; a second desk needs no change to the pipeline at all.

`SCRAPERS` remains only as a **slug view** for the CLI's `--source` choices —
`in`, `.keys()`, iteration and `len()`. It briefly also exposed
`SCRAPERS[slug](target_date=…)` to mimic the old slug→class mapping; review found
that interface returned an adapter (which has no `.scrape()`) and silently
discarded `target_date`, with no callers anywhere in the repository. Rather than
implement a legacy contract nothing used, it was narrowed to what it can honour
truthfully, and subscripting now raises with a pointer to
`get_registry().get_adapter(slug).collect(window)`.

### 2. Wrap the existing scrapers; do not rewrite them

`adapters/legacy.py` calls exactly the same methods in exactly the same order as
`BaseScraper.scrape()`, and hands downstream stages the parser's dict verbatim.
Months of accumulated selector and encoding corrections are preserved. Only the
bookkeeping around the loop is new.

### 3. Every outcome is named

`core/collection/status.py` replaces the bare empty list. `ok_no_publications`
(healthy silence), `listing_failure`, `fetch_failure`, `extraction_failure`,
`not_implemented` and the rest each declare whether they are a failure. One
required source failing now degrades the aggregate run even when everything else
succeeded.

`not_implemented` and `skipped_disabled` are deliberately **not** failures — an
alarm that is always on is not an alarm — but they are always visible.

### 4. Additive migrations, enforced at every seam

Migrations run inside `storage.db.init_db()`, in CI before any collection, and —
critically — inside `scripts/reconcile_db.py`, which migrates its output copy
*before* merging rows.

That last one is what actually closes the hole. `init_db()` alone was not
enough: the reconciler copies the published side's file, so a legacy origin blob
produced a legacy merged database, and by the time the next pipeline run
repaired the schema that file had already been committed and pushed — with the
per-source rows the merge dropped gone for good. The reconciler now also validates every input before touching the merge target,
merges `source_run_results` from both sides under proven run lineage, resolves
article sources by slug rather than by cross-database numeric id, and verifies
the result against an exactly computed expected map. Its gates fail on a missing
table, an incomplete ledger, a lost or altered row from either side, an
unexpected row, a changed article attribution, or a `scrape_runs` CHECK that
cannot represent a status present in an input. Anything unmappable aborts the
merge and leaves git's conflict in place.

`tests/test_reconcile.py` exercises the production `reconcile()` and `gates()`
directly across legacy/current permutations, rather than simulating reversion.

No column was dropped. `sources.language` and `sources.is_active` are still
written; `language_tag` and `enabled` were added beside them with fallback
accessors in `storage/db.py`.

### 5. Two taxonomy layers

A small universal genre vocabulary for cross-desk comparison, and desk-scoped
topical labels for regional detail. The existing 14 China categories stay
exactly as they are, recorded as China-desk configuration. "Taiwan" and "South
China Sea" are not promoted into a shared taxonomy — they have no meaning on
another desk, and forcing them there would distort both.

## Consequences

**Gained.** Per-source observability; a run that degrades when a source fails;
configuration-driven sources; a migration path that survives the reconciler;
an offline test suite covering migrations, manifests, the adapter contract and
an end-to-end chain.

**Not gained, and deliberately.** No capture storage, no document versioning, no
translation records, no claims model — those are Phase 3 and need a storage
decision first. No Russia or US desk. No public rename.

**Costs.** Two ways to express a source (legacy columns and manifest) until the
cleanup. The `SCRAPERS` slug view. `init_db()` now does more than its name
implies — documented in its docstring. `reconcile_db.py` now depends on the
migration package; the whole chain is stdlib-only, so `--install-driver` still
runs on a CI runner before `pip install`.

**Phase 1–2 durability vs. Phase 3 storage separation.** What is finished here is
*migration and reconciliation durability*: the schema and the per-source records
survive a merge, and CI fails closed rather than pushing a regressed database.
That is not the same as Phase 3, which is about moving the database and raw
captures out of git entirely (snapshots, restore drills, untracking). Phase 3
remains unstarted and unauthorized.

**A blocker this surfaced, since closed.** `sources.language` carried
`CHECK (language IN ('zh','en'))`, so persistence rejected valid non-zh/en tags
even though the domain layer accepted them. Migration 0005 removed that finite
constraint; the legacy column is retained and now stores the tag's primary
language subtag. No new finite list replaces it, and no Russia desk or source
was added. See the language compatibility policy in
docs/SCHEMA_AND_MIGRATIONS.md.

## Alternatives rejected

- **Rewrite the scrapers to the new contract now.** Risks working parsers for no
  collection benefit.
- **Move packages into the target tree immediately.** A large diff that breaks
  imports and reviews poorly, for a cosmetic gain.
- **YAML manifests.** Needs a new dependency on the 3.9 collection path to buy
  comment syntax.
- **Postgres.** Nothing about multiple desks requires it at this volume; the
  triggers that would are listed in the storage strategy.
- **Derive `is_failure` at read time.** A later change to the status vocabulary
  would retroactively rewrite what old runs reported.
