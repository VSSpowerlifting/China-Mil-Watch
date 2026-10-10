# C2-D — Hash-pinned native manifest source selection (fictional only)

**October 10, 2026.** Stack: merged C1 #356 → C2-A #359 → C2-B #360 → C2-C #361 → this independent C2-D increment.

## Gap addressed

The C2-C source plan is a durable, immutable record, but it originally accepted a caller's source-name list. That prevents later omissions; it does **not** ensure that the initial list corresponds to any legitimate desk configuration.

`storage/evidence_manifest_policy.py` adds a second, stricter *candidate-selection* layer. For one named desk, it reads the **real validated native desk manifest** using `core.manifests.load_manifest`, checks an explicit expected SHA-256 digest before and after parsing, rejects path escape/symlink drift, selects **all enabled sources** declared by that manifest, and stores a write-once, read-back verified manifest-policy object tied to the C1 execution identity. It then freezes those exact source IDs through C2-C's immutable source plan.

Every subsequent `load()`, `seal_collection()`, or `verify_before_analysis()` revalidates the manifest digest and the full selected source set against its frozen policy and source plan. A changed file or an attempted omission causes failure rather than an invented healthy collection.

The native repository manifest source inventory is **read-only**. A desk's actual source bodies, URLs, crawler adapters, language content, collection status and article records are not fetched or modified. The selected source list is never proof of publication rights.

## Independent tests

The `tests/test_evidence_manifest_policy.py` module exercises the declared China and Singapore manifest *metadata* as examples without collecting from them. It also runs a complete fictional C2-A/B/C/D sequence: a fixture-only record attributed to a manifest-derived slug, all expected source-run outcomes, immutable collected checkpoint, write-ahead paid-intent reservation, measured **fictional token usage**, native relevance update and a nonpublishing analyzed generation. Every operation runs through the existing C1 test database and never calls a real source or provider. Collection outcomes are fictional `ok_no_publications` receipts in a temporary native C1 database. The tests verify missing-source refusal, all-source durability, manifest digest mismatch, escaped desk IDs, lost write acknowledgement, immutable tampering, local-copy file drift, and restart restoration of an already collected generation.

## **Critical unresolved authority / security limits**

- **No owner-approved selection yet.** A caller still provides the desk ID and expected manifest hash, and this code does not authenticate who selected them. It labels `policy_owner_approved=False`, `production_selection_authorized=False`, and `eligible_for_publication=False`.
- A local, hash-checked manifest is not signed, access-controlled release policy. The production selector requires an independent owner-controlled policy/commit-signature decision and launch scheduler gating.
- This slice handles **one desk at a time** and should not be presented as the final multi-desk collection plan.
- There is no real source fetching, external provider, LLM API call, paid model dispatch or validated spend pricing, and no binding to Daily or any scheduled workflow.
- Main's `pipeline.run()` retains its **non-dry private refusal**. Source rights #326, provider security, retention policy, release/projection and deployment are all still outside authorization.

## 2026-10-10 fixture correction

The C1 native schema already seeds the `pla_daily` source. The combined
fictional lifecycle test now reuses that row instead of attempting a duplicate
`INSERT`, which the strict native schema correctly rejects. The initial
A+B+C+D full CI failed one setup error (`UNIQUE constraint failed:
sources.slug`), while the DB/output preservation step passed. The replacement
exact-head run must pass before acceptance; the old failure is not waived.

## Validation receipt rule

Because this is stacked on A+B+C, the combined exact-head Python 3.9
workflow may be launched by temporarily comparing this branch to `main`.
Immediately after the combined run is queued, the pull request is retargeted
back to the C2-C feature branch to retain a **three-file incremental diff**.
Only the actual final Actions result (all tests, output validation and DB/output
preservation) counts; a queued/in-progress run never counts as a pass.

## Review and CI gates

Do not merge this stacked PR before #359, #360 and #361 are individually accepted and merged in order. Run exact-head Python 3.9 full offline CI, output validation and tracked database/output preservation; review its **three-file incremental diff**. No production cutover or further rights assumptions.

Targeted rehearsal:

```bash
python -m unittest tests.test_evidence_manifest_policy -v
python -m unittest tests.test_evidence_source_plan tests.test_evidence_lifecycle tests.test_evidence_spend -v
```
