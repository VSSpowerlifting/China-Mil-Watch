# Shadow collection

A shadow desk is a source under evaluation. It collects into isolated state so
its reliability can be measured before anything it produces is treated as
coverage. Nothing a shadow desk collects appears in the public site, in
`pla_watch.db`, or in any public count.

Currently one shadow desk exists: **Singapore MINDEF**. Its scope, inclusions
and exclusions are in `shadow/singapore_mindef/README.md`.

---

## Isolation

Four independent barriers, because one of them is the one that fails:

1. **The manifest is not under `desks/`.** `core.manifests.load_all_desks()`
   globs `desks/*/manifest.json`. A shadow manifest placed there would be
   written into the tracked database by `sync_desk_config()` on the next
   migration run, putting a non-collecting desk into public counts. It lives
   under `shadow/` instead, and a test asserts `desks/` contains only `china`.
2. **The source is `enabled: false`** in its own manifest, and its
   `healthcheck()` reports `skipped_disabled`.
3. **The runner refuses to write inside the repository.**
   `scripts/shadow_collect.py` raises if `--state-dir` resolves under the repo
   root, so a state file cannot be committed to `main` by accident.
4. **The runner never names the production database or output directory.** Not
   as a constant, not as a path. A path it never spells is a path it cannot
   open. A test strips docstrings and comments and asserts this of the code
   itself.

The collector is also absent from both renderers: the public site does not know
Singapore exists.

## Durable state

State lives on a dedicated orphan branch, **`shadow/singapore-mindef`**:

```
state/shadow.db          SQLite corpus — the collected documents
state/clock.json         day zero, written once, never rewritten
state/ledger/*.json      one entry per run, append-only
```

**Why a branch rather than a cache.** The 30-day evaluation needs state that
survives longer than any cache guarantee and that can be audited afterwards.
GitHub Actions caches are evictable and are explicitly not a durable store; an
artifact expires. A branch is durable, diffable, and every update is attributable
to the workflow run that made it. The cost is that a branch can be pushed to,
which is why the properties below are enforced rather than assumed.

**Properties, each rehearsed against a local bare remote:**

| Property | How |
|---|---|
| Never merged to `main` | Orphan branch; no PR targets it; no workflow merges it |
| Cannot trigger deployment | No Pages step; the branch has no workflow of its own |
| Bounded content | Only `state/`; the collector writes nothing else |
| Non-force pushes | The workflow has no `--force`, and a test asserts it |
| Concurrency | `concurrency: singapore-shadow`, `cancel-in-progress: false` |
| Attributable | Every commit names the run id and the collector SHA |
| No secrets | The ledger holds counts, hashes and statuses only |
| No WAL/SHM | The publish step refuses to commit a sidecar |
| Interrupted-run recovery | A failed run pushes nothing; the next clone is intact |
| Non-fast-forward safety | A stale writer is **rejected**, never fast-forwarded over |

## The ledger and the clock

Every run appends one entry recording start and finish, run id, collector
commit, robots status, listing status, counts (discovered, selected, retrieved,
inserted, updated, duplicates, filtered), failure counts split into **fetch**,
**extraction** and **access** — a source going dark must not read like a parser
bug — content hashes, state hash before and after, the result, and a health
verdict.

Results use the repository's existing taxonomy rather than a new vocabulary:
`ok`, `ok_no_publications`, `ok_all_duplicates`, `ok_all_filtered`,
`listing_failure`, `extraction_failure`, `fetch_failure`, `auth_failure`.

**Day 0 is derived, never hard-coded.** It is the finish time of the first run
whose result is terminal-successful, written once into `clock.json` and never
rewritten. A failed run neither starts nor advances the clock. An expected
empty day is a success: it records history without inventing records.

## Thirty-day qualification

Reaching day 30 creates a **launch-review checkpoint**. It does not launch
anything, and no code anywhere flips a mode based on it.

A review may proceed only if every scheduled day has a recorded terminal
result; expected empty days are distinguished from failures; no robots or
access-policy violation occurred; no silent listing failure occurred; full-body
extraction stayed reliable; identity and deduplication stayed deterministic; no
shadow write reached a production artifact; manual corpus reviews happened
around days 7, 14 and 30; any extraction break was repaired and followed by a
fresh uninterrupted interval if the break invalidated reliability; and the
corpus is substantively sufficient to represent a real desk.

## Rollback

The shadow collector is entirely additive and can be withdrawn in stages,
smallest first:

1. **Stop collecting.** Disable the *Singapore Shadow Collection* workflow in
   the Actions tab, or delete `.github/workflows/singapore_shadow.yml`. Nothing
   else references it.
2. **Discard the evidence.** Delete the `shadow/singapore-mindef` branch. No
   other ref depends on it and no history is rewritten.
3. **Remove the desk.** Delete `shadow/singapore_mindef/`,
   `scraper/sources/sg_mindef.py`, `scripts/shadow_collect.py`,
   `tests/test_singapore_shadow.py` and `tests/fixtures/sg_mindef/`.

None of these touches `pla_watch.db`, `output/`, the public site, the daily
China workflow, or the renderer. There is nothing to un-publish, because
nothing was published.
