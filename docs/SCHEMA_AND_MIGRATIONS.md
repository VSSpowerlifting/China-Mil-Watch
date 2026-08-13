# Schema and migrations

## Running them

```bash
.venv/bin/python -m migrations.cli --status     # what is applied
.venv/bin/python -m migrations.cli --apply      # apply pending + sync config
.venv/bin/python -m migrations.cli --verify     # counts, orphans, integrity
```

Migrations also run automatically inside `storage.db.init_db()`, which
`pipeline.py` calls before any collection. On a current database that is a no-op.

## Why they run on the write path

`scripts/reconcile_db.py` resolves a diverged `pla_watch.db` by copying the
**published side's file** and merging rows into it. That is right for row
identity and wrong for schema: if origin's file predates a schema change, the
merged database silently returns to the older shape — no conflict, no warning,
correct-looking row counts.

This has already happened twice to the same constraint. The 2026-08-09
`'degraded'` migration was reverted by a rebase (DECISION_LOG 2026-08-09 §7) and
found reverted again by the Phase 0 audit on 2026-08-13.

The standing rule from that incident — *re-apply and re-verify after the final
rebase* — depends on a person remembering. Applying idempotent migrations on the
write path does not.

**How this is now enforced end to end.** Three mechanisms, in order:

1. **`scripts/reconcile_db.py` migrates its output before merging rows.** The
   merge target is always current, so a legacy origin blob can no longer make
   the merged database legacy, and a local run with status `'degraded'` can be
   inserted against a pre-hotfix origin instead of raising.
2. **The reconciler merges `source_run_results` from both sides**, remapping
   local runs that were renumbered. Observed per-source data survives the merge.
   (It previously did not: local rows were deleted wholesale while every gate
   passed.)
3. **CI applies and verifies migrations before collection, and verifies after
   every rebase that precedes a push** — fail-closed, so a regressed database
   cannot reach origin.

`init_db()` still applies migrations, but it is now the last line of defence
rather than the only one. Relying on it alone was insufficient: by the time the
next pipeline run repairs the schema, the regressed file has already been
pushed, and rows the merge dropped are gone regardless of what a later migration
rebuilds.

## Migration rules

1. **Additive.** No column is dropped or renamed. Deprecate in documentation
   first; removal is a separately approved cleanup.
2. **Idempotent.** Re-running is a no-op. Optional `is_already_applied(conn)`
   detects a change that predates the framework, records it, and does not redo it.
3. **Transactional.** Each migration runs in its own transaction. A failure
   rolls that migration back entirely and leaves no `schema_migrations` row, so
   the next run retries from a consistent state.
4. **Foreign keys checked inside the transaction.** `PRAGMA foreign_keys` is off
   during the run (SQLite's official table-rebuild procedure requires it and the
   pragma is a no-op inside a transaction), and every migration runs
   `PRAGMA foreign_key_check` before committing.
5. **Tested against the real legacy schema.** `tests/fixtures/legacy_schema.sql`
   is `storage/schema.sql` as it stood at the commit before `'degraded'`,
   extracted from git history — not a hand-written approximation.

## Applied migrations

| Version | Name | What it does |
|---|---|---|
| 0001 | `scrape_run_status_degraded` | Rebuilds `scrape_runs` so `status` accepts `'degraded'`. Already present in production; detected and recorded. |
| 0002 | `desks_and_institutions` | New `desks`, `institutions` tables. |
| 0003 | `sources_desk_metadata` | 17 additive columns on `sources`: desk, institution, `language_tag`, timezone, calendar, `authority_tier`, `source_type`, `originality`, cadence, `access_method`, `enabled`, endpoints, notes. |
| 0004 | `source_run_results` | One row per (run, source): discovered / fetched / extracted / duplicates / new / rejected, plus status and `is_failure`. |
| 0005 | `relax_source_language_check` | Rebuilds `sources` without the finite `CHECK (language IN ('zh','en'))`. Column retained, `NOT NULL` retained, every value preserved, `sources.id` preserved. |

Desk, institution and source metadata are **not** seeded by a migration. They
are synced from `desks/*/manifest.json` after migrations by
`core.registry.sync_desk_config()`, so a manifest correction reaches the
database on the next run rather than needing a new migration — and so a
reconcile-reverted database rebuilds config from git.

## What sync may and may not touch

On an existing source row, sync writes **only** the columns migration 0003
added. `display_name`, `base_url`, `language` and `is_active` are left exactly
as production holds them. A configuration sync must not be able to rename a live
source or re-point it at a different host.
(`tests/test_pipeline_compat.py::TestConfigSyncIsIdempotent`.)

## Legacy columns, deprecated but retained

| Legacy | Replacement | Accessor |
|---|---|---|
| `sources.language` (`'zh'`/`'en'`) | `sources.language_tag` (BCP 47) | `db.get_source_language_tag()` |
| `sources.is_active` | `sources.enabled` | `db.source_is_enabled()` |

Both accessors read the new column and fall back to the legacy one, so callers
migrate one at a time and an unmigrated database still answers correctly.

Backfill mapping: `zh → zh-Hans`, `en → en`. Every current source is a PRC
simplified-script or English publication; the mapping is recorded explicitly in
the China manifest, not inferred at runtime.

## Legacy language compatibility policy

`language_tag` (BCP 47) is authoritative. `language` is a **deprecated
compatibility mirror**, still present, still `NOT NULL`, still written, and read
by nothing that has been migrated to the new field yet.

Migration 0005 removed the original `CHECK (language IN ('zh','en'))`. That
constraint made persistence country-specific in a way the domain layer was not:
`core/manifests.py` accepts any well-formed BCP 47 tag, but a source with
`language_tag: "ru"` could not be written at all.

The value written to the legacy column is the tag's **primary language subtag**
— `zh-Hans` → `zh`, `en` → `en`, `ru-RU` → `ru`. That is a defensible narrowing
of the same fact, not a substitution of a different language.

**No new finite CHECK replaces it.** Enumerating permitted languages in the
schema would recreate this problem for the next desk and would put a
geopolitical list in a database constraint. Tag validation belongs in the
manifest layer, where the error can name the file and the field.

Until 0005, `_legacy_language()` raised for anything outside zh/en. That was the
right interim behaviour — silently coercing `ru` to `en` would have corrupted the
corpus undetectably — but refusing to persist is not neutrality either. It now
raises only for a structurally invalid primary subtag.

## Verification

`migrations.runner.verify()` returns row counts, orphan checks
(`articles_without_source`, `sources_with_null_desk`, …), `integrity_check` and
`foreign_key_check`. Verified against a copy of production on 2026-08-13, before and after migration
0005: 3,182 articles / 3,182 distinct URLs / max id 3188 / 110 runs / 2,023
article-category links — **byte-identical id↔URL digest and source-identity
digest before and after**, zero orphans, integrity `ok`.

`scripts/verify_db_current.py` is the gate form of this. It classifies a
database as `fully_current`, `ledger_absent`, `partially_applied` or
`structurally_incompatible`, and fails closed rather than repairing unless
`--repair` is passed on a path that provably commits the database.
