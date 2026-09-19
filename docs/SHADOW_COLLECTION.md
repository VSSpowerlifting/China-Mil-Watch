# Shadow collection

A shadow desk is a source under evaluation. It collects into isolated state so
its reliability can be measured before anything it produces is treated as
coverage. Nothing a shadow desk collects appears in the public site, in
`pla_watch.db`, or in any public count.

**Two shadow desks exist.** Neither is qualified, neither is approved for
public promotion, and neither may be described as coverage.

| Desk | State branch | Collector | Workflow | Scope document |
|---|---|---|---|---|
| **Singapore MINDEF** | `shadow/singapore-mindef` | `scripts/shadow_collect.py` | `singapore_shadow.yml` | `shadow/singapore_mindef/README.md` |
| **Japan MOD** | `shadow/jp-mod` | `scripts/shadow_collect_japan.py` | `japan_shadow.yml` | `shadow/jp_mod/README.md` |

Each desk's manifest is authoritative for its sources; `desks/registry.json` is
authoritative for its status and public presentation. Both are declared
`shadow` there. Elapsed shadow days live in each desk's ledger and are
deliberately not restated in documentation — a number copied out of a ledger
goes stale the next day and reads as a promise.

**Japan is access-constrained, and that is reported rather than worked around.**
Its two official RSS feeds are served normally and PDF documents retrieve in
full, but HTML documents on the same host are returned behind an interactive
challenge. Those items are stored as titled, dated discovery records with no
body and nothing inferred. Partial retrieval is not coverage, and the challenge
is never to be defeated — see §Access below.

---

## Access

An institution that wants to refuse this collector must be able to recognise it
and say so. That rule binds every shadow desk:

* honest identification — a user agent naming this project, never browser
  impersonation, never a proxy;
* `robots.txt` is read and obeyed; a source whose `robots.txt` cannot be read
  is not collected;
* **an interactive challenge is never solved, bypassed or worked around.** A
  challenged document is recorded as unretrieved. It is never inferred to be
  absent, and its absence is never filled in from another source.

Defeating a challenge would destroy the capability the rule protects, so it is
prohibited regardless of how much coverage it would unlock.

## Isolation

Four independent barriers, because one of them is the one that fails. Written
below in terms of the Singapore desk, which established them; the Japan desk
carries the same four, with `shadow/jp_mod/`, `scripts/shadow_collect_japan.py`
and the `shadow/jp-mod` branch in the corresponding places. The US desk carries
the same four in code -- `shadow/us_indopacom/`,
`scripts/shadow_collect_us.py` -- but **has not been launched**: it has no state
branch, no workflow and no day zero. See "Built but not launched" below.

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

Neither collector is referenced by either renderer. The public site renders no
shadow record and no shadow count. Desk pages state that a shadow desk is under
evaluation and has no public records — that is a status disclosure, not
coverage.

## Durable state

Each *launched* desk's state lives on its own dedicated orphan branch —
**`shadow/singapore-mindef`** and **`shadow/jp-mod`** — with the same layout:

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
| Concurrency | a per-desk concurrency group, `cancel-in-progress: false` |
| Attributable | Every commit names the run id and the collector SHA |
| No secrets | The ledger holds counts, hashes and statuses only |
| No WAL/SHM | The publish step refuses to commit a sidecar |
| Interrupted-run recovery | A failed run pushes nothing; the next clone is intact |
| Non-fast-forward safety | A stale writer is **rejected**, never fast-forwarded over |

## Built but not launched: the US Indo-Pacific desk

The DVIDS collector exists, is tested and has been rehearsed, and **collects
nothing**. There is no `shadow/us-indopacom` branch, no `us_shadow.yml`
workflow, no `clock.json` and therefore no day zero. Launching it is a separate,
deliberate act: creating the state branch and enabling a workflow on a cron
clear of 21:10 and 22:40 UTC.

Two things must stay true when it is launched, and neither is a formality.

**The route is not the declared target.** `www.pacom.mil` and
`www.defense.gov` still return HTTP 403 for `robots.txt` itself. DVIDS is a
separate host with a readable policy; it is an alternative official route, not
permission that pacom.mil withheld. The `us-indopacific` registry entry stays
`access_blocked` until this desk has actually collected and been reviewed.

**The feed is not what its name suggests.** The required framing, used
everywhere the source is described, is the **DVIDS USINDOPACOM-tagged reference
stream**:

* a **Tier B DoD media-service feed**, published by Defense Media Activity;
* **unit tagging does not imply command authorship or comprehensive
  Indo-Pacific relevance**;
* **not a complete USINDOPACOM command-release wire**;
* **not presently a peer of the China Desk**;
* the public **US Indo-Pacific Reference Desk remains `access_blocked`**;
* shadow collection **evaluates whether this source can support that desk
  later**, and does not presuppose that it can.

Measured 2026-09-17: 428 items, 171 of them `/news/`, and 15 of those 171 titles
carry any Indo-Pacific keyword at all. No record may be called
Indo-Pacific-relevant merely because DVIDS tagged it to the unit.
`shadow/us_indopacom/README.md` holds the measurement and
`tests/test_us_source_scope.py` holds the prose to it.

**The complete eligible stream is collected.** No relevance filter is applied.
Filtering on title keywords at collection would decide the usefulness question
the shadow phase exists to measure; the keyword indicator in the checkpoint
report is a diagnostic, never a gate.

One thing differs from the other two desks and changes how a missed day is
read: the DVIDS window is a fixed item count, not a date range. A collection gap
is **permanent** -- those documents cannot be recovered from this route -- so
`scripts/review_us_shadow_state.py` reports a gap as a failure rather than as
lateness, and has its own reviewer rather than borrowing Singapore's.

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
anything, and no code anywhere flips a mode based on it. **There is no
automatic promotion**: no date, no counter and no collection milestone makes a
shadow desk public. Promotion is an owner decision recorded in
`DECISION_LOG.md`, and it comes after the reviews, not before them.

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

1. **Stop collecting.** Disable that desk's shadow workflow in the Actions
   tab, or delete it (`singapore_shadow.yml` / `japan_shadow.yml`). Nothing
   else references either.
2. **Discard the evidence.** Delete that desk's state branch
   (`shadow/singapore-mindef` / `shadow/jp-mod`). No other ref depends on it
   and no history is rewritten.
3. **Remove the desk.** Delete its manifest directory, its adapter, its
   collector, its tests and its fixtures — for Singapore,
   `shadow/singapore_mindef/`, `scraper/sources/sg_mindef.py`,
   `scripts/shadow_collect.py`, `tests/test_singapore_shadow.py` and
   `tests/fixtures/sg_mindef/`; for Japan, `shadow/jp_mod/`,
   `scraper/sources/jp_mod.py`, `scripts/shadow_collect_japan.py` and its
   `tests/test_japan_*.py` files.

None of these touches `pla_watch.db`, `output/`, the public site, the daily
China workflow, or the renderer. There is nothing to un-publish, because
nothing was published.
