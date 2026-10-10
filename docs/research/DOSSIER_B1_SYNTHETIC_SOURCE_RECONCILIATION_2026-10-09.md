# Living Dossiers B1.2 — synthetic-only read-only source reconciliation

**Engineering slice:** stacked on [B1.1 PR #328](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/328), intentionally not merged into the public site or production pipeline. This note distinguishes **implemented integrity checks** from all source-use and editorial decisions that remain open under [#319](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/319), [#321](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/321) and [#326](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/326).

## Exact files added

- \`core/dossier_sources.py\`: \`reconcile_dossier_sources(sidecar, db_path, registry=None)\`, a metadata-only report using \`core.dossier_contract.validate_dossier_shape\`, registered production-source eligibility and \`scripts.reconcile_db.read_only\`. The function does not alter the production DB, rewrite source text, call a model, access a publisher website or approve content.
- \`tests/test_dossier_sources.py\`: synthetic SQLite fixture builders and fake desk registry, with 23 new negative/positive tests. No actual IPR record IDs, URLs or bodies are used: fabricated IDs 900001/900002 and fictional \`example.org\` URLs only.
- This implementation note. No new \`dossiers/\` sidecar, production output, runner, renderer or dependency installer.

## Mechanically checked vs NOT established

| Check | Result |
| --- | --- |
| Canonical Dossier JSON and claim/source IDs | B1.1 shape validation must pass first |
| Public/collecting desk with production records | Reject shadow-only/noncollecting/nonpublic desks |
| Source is enabled and contract-validated | Reject unapproved or disabled source origin |
| Institution and original language | Exact manifest + stored archive match |
| Numeric source record ID, URL, source slug and publisher date | Exact archive match; orphan ID or drift is an **error** |
| Stored original body | Recompute SHA-256 over the archived UTF-8 \`text_original\`, compare to frozen digest from Dossier; empty body is an **error** |
| Publisher original title exists | An absent/blank title is an **error** |
| Existing model relevance disposition | \`not_selected\` or \`NULL\` generates a distinct **human screening hold**, never a database rewrite |
| Human source admission | **Always held**; a source-ledger reference is author-editable, not independently trusted |
| Publisher rights to link, quote, show body/photos | **Always held**; a text string naming a permission is not permission |
| Editor approval and exact-version authorization | **Always held**; a calculated SHA is not an authenticated human action |
| Publish eligibility | **Always false** in B1.2; no B2 rendering code exists |

The report contains only record IDs, source screen state and diagnostic codes; **no stored publisher body or model reasoning** is serialized. Repeated reports of one activity are not treated as independent corroboration. No source page is refetched, and collection gaps cannot be used as proof that an event did not occur.

The implementation accepts an injected fake desk registry for unit tests, with a real \`load_registry()\` default for future read-only audits. **No actual IPR production-source audit was run as part of this slice**, because B0 subject and rights gates have not been cleared. Introducing the function is not authority to add a real Dossier.

## Verification

[One-time GitHub Actions run #38016518726](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38016518726) passed on Python 3.9:

- **90/90 tests** — 67 B1.1 synthetic JSON contract tests + 23 B1.2 synthetic SQLite source-identity tests.
- Python module/test compilation succeeded; synthetic test checks original DB bytes remain unchanged with no WAL/SHM.
- GitHub runner verified unchanged tracked \`pla_watch.db\`, \`output/\`, \`briefs/\` and \`timelines/\` by hash/status.
- Its single-use workflow was deleted from this PR after testing. Repository-wide CI on the **final PR head** remains a separate gate; the focused success is not full CI.

To reproduce focused tests after stacking B1.1 and B1.2:

~~~sh
python -m unittest tests.test_dossier_contract tests.test_dossier_sources -v
~~~

The observed test runtime was short; the live site's browser/accessibility tests are not part of this scope, because no renderer was edited.

## Future B1.3 work (not shipped here)

A **private** \`scripts/validate_dossiers.py\` CLI could return errors and holds in a structured human review report, defaulting to **not publishable** even after all hash checks pass. Its format should explicitly distinguish archive parity, model-screening state, source admission, rights decision and exact-version editorial approval. Avoid any \`--approve\`, \`--publish\` or source text in stdout. Do not introduce a scheduler or trigger real source citation without an accepted B0 matrix.

**Hard stop:** This PR is stacked on #328; integrate B1.1 first, then rebase/retarget B1.2, preserving strict dependency order and current-main DB. No merges to \`main\`, no production rendering, no MINDEF permission conclusions and no live pilot content authorized by a green synthetic test suite.
