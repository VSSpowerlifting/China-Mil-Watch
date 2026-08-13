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

A `SCRAPERS` compatibility shim remains for scripts and the CLI. It is
documented as a shim and removed in a later approved cleanup.

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

### 4. Additive migrations, applied on the write path

Migrations run inside `storage.db.init_db()`, which `pipeline.py` calls before
any collection. Because every migration is idempotent and everything they create
is either DDL or reconstructible from tracked manifests, a reconcile that
reverts the schema is repaired by the next run instead of by someone remembering
the standing re-apply rule. `tests/test_migrations.py::TestReconcileReversion`
tests exactly that sequence.

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
cleanup. The `SCRAPERS` shim. `init_db()` now does more than its name implies —
documented in its docstring.

**A blocker this surfaced.** `sources.language` carries
`CHECK (language IN ('zh','en'))`. Syncing a desk in any other language fails
loudly rather than corrupting the column. **Relaxing that constraint is a
prerequisite migration for the Russia desk** — see docs/SCHEMA_AND_MIGRATIONS.md.

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
