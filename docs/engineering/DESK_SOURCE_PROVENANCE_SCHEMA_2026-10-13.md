# Desk source provenance — schema and contract (2026-10-13)

Status: Milestone A of the frontend engineering program (parent issue #498). This is a
data foundation only. It renders no page, changes no template and does not touch the
Phase 4A map (PR #504). Milestone B (the Desks Source Atlas) consumes it.

| Piece | Path |
|---|---|
| Typed adapter (pure, deterministic) | `core/desk_source_provenance.py` |
| Reviewed family bindings | `config/desk_source_provenance.json` |
| Gather CLI (real loaders, read-only DB) | `scripts/desk_source_provenance.py` |
| Eight-desk evidence matrix | `docs/engineering/DESK_SOURCE_PROVENANCE_MATRIX_2026-10-13.md` |
| Tests | `tests/test_desk_source_provenance.py` |

## Why an adapter

The desk hub has to say, for every source family of every desk, what IPR actually
holds. Several records answer different parts of that question, and some of them sound
stronger than they are. An official ministry index is not an IPR collector. A shadow
declaration is not production. A bibliography is not a collection count. The adapter is
the single place that merges those records, and it is built to fail toward the weaker
claim.

## Inputs and their authority

| Input | Authoritative for | Never used for |
|---|---|---|
| `desks/registry.json` via `core.desk_registry` | desk status, scope, `status_explanation`, `limits`, blockers, research families, `contract_validated` | run health |
| Desk manifests under `desks/` (`contract_validated`) | which sources are **production** | anything on a non-collecting desk |
| `config/desk_source_provenance.json` | the reviewed class of each research family, plus a `basis` pointer | creating production; new evidence |
| `config/shadow_source_workflow_bindings.json` + `shadow/*/manifest.json` | shadow slug, desk id, language tags, access method, shadow enabled, top-level `rights` text | production, health, branch, workflow or schedule identity (never emitted) |
| Gated reference loaders (`core.korea_public_bibliography`, `core.indonesia_official_index`, `core.indonesia_press_index`, `core.reviewed_source_links`) | outbound link metadata and its editorial status | record counts, collection claims |
| `source_run_results` (m0004), read-only | the latest run row per **production** slug | any non-production source |

The adapter never reads private shadow originals, receipts or unpublished bodies, and it
makes no network call.

## Evidence classes

| Class | Meaning | Who may assign it |
|---|---|---|
| `production` | Contract-validated manifest source on a collecting desk (`COLLECTING_DESK_STATUSES`) | the registry only; a binding that says `production` is rejected |
| `shadow` | Declared in a shadow manifest bound to this desk; not admitted to production | a binding, and only if the slug is declared on one of the desk's `shadow_desk_ids` |
| `public_reference` | An approved official index, bibliography or reviewed link lane | a binding with a lane or a registry publisher URL |
| `access_blocked` | The registry records that the source refused or could not be reached | a binding citing that record |
| `insufficient_evidence` | Nothing recorded supports a stronger class | the default for anything unbound, contradictory or unsupported |

### Downgrade rules (a conflict never promotes)

Each is recorded in `conflicts`, and the family becomes `insufficient_evidence`:

- registry family with no binding;
- shadow binding whose slug is a production slug, is already shown on the desk, has no
  shadow declaration, or is declared under a desk id outside `shadow_desk_ids`;
- `shadow` class without a slug; `public_reference` with neither a lane nor a publisher URL;
- a contract-validated source on a desk that is not collecting (never production, never health);
- a registry source that is neither validated nor bound.

Also recorded: a binding for a family the registry does not declare (ignored, nothing
shown) and a family name repeated in the registry (shown once).

A reference lane whose loader refuses its input becomes unavailable (recorded), and a URL
that repeats within a desk is dropped (recorded). Values for language, access, rights and
shadow-enabled come only from the declaration that justified the class; when the class is
downgraded they are left unknown.

## Production run health

Health attaches **only** to a production source, by exact slug. Health supplied for any
other slug is ignored and listed in `unmatched_health_slugs`.

| `RunState` | Rule |
|---|---|
| `collected_new` | latest row status `ok`, `is_failure = 0`, `new_documents > 0` |
| `collected_no_new` | a success status (`ok`, `ok_no_publications`, `ok_all_duplicates`, `ok_all_filtered`) with no new documents |
| `collection_failed` | `is_failure = 1` or a failure status; if the two signals disagree the reason says so and failure wins |
| `not_attempted` | `not_implemented` or `skipped_disabled` (stored as non-failures, but not a run with no publications) |
| `no_history` | no table, no row, an unknown status, a malformed row (non-int or boolean `is_failure`, negative or non-int `new_documents`), or a non-`ok` success status that still stored new documents |

`last_successful_collection_at` counts only the four success statuses, so a
`not_implemented` run is never a successful collection. `record_count` is the stored article
count for that slug; reference links never contribute to it.

## Verbatim fields

`status_explanation`, `limits`, blocker and resolved pairs, observed volume, the
qualification explanation and the shadow manifest `rights` text are copied verbatim. The
adapter does not filter, shorten or reword them; any public subset is a rendering decision
recorded against the editorial doctrine.

## Bindings file (`ipr-desk-source-provenance-bindings/1`)

```json
{
  "schema": "ipr-desk-source-provenance-bindings/1",
  "reference_lanes": {"<lane_id>": {"loader": "<known loader>", "kind": "bibliography|official_index|reviewed_links", "filter_by_source_slug": false}},
  "desks": {"<desk slug>": {"shadow_desk_ids": ["<shadow desk id>"], "families": [
    {"name": "<exact registry family name>", "evidence_class": "shadow|public_reference|access_blocked|insufficient_evidence",
     "source_slug": "<shadow slug or null>", "reference_lanes": ["<lane_id>"], "basis": "<pointer to recorded evidence>"}
  ]}}
}
```

Parsing is strict. It rejects unknown or missing fields, a duplicate JSON key, a symlink or
an oversized file, an unknown loader or kind, two lanes sharing a loader, a shadow desk id
bound to two desks, a family named twice, a slug bound twice, an undeclared lane, a
slug-filtered lane on a family without a slug, an empty or untrimmed name, and an empty
basis.

## Output (`ipr-desk-source-provenance/1`)

`atlas_to_json` emits sorted keys, two-space indent, UTF-8 (no ASCII escaping) and a trailing
newline; identical inputs give byte-identical output. The top level carries `schema`,
`as_of`, `health_supplied`, `desks`, `undisplayed_shadow_declarations`,
`unmatched_health_slugs` and `conflicts`. Each desk carries the registry fields above,
`sources` (one `SourceProvenance` per family, production first in manifest order),
`references` (one `ReferenceGroup` per bound lane) and its own `conflicts`.

`render_matrix` produces the Markdown evidence matrix. It shows how many sources carry run
health but never the health values, which change every run.

## Commands

```bash
.venv/bin/python scripts/desk_source_provenance.py --no-health --as-of 2026-10-13 --matrix -
.venv/bin/python scripts/desk_source_provenance.py --json -          # with read-only DB health
.venv/bin/python -m unittest tests.test_desk_source_provenance -v
```
