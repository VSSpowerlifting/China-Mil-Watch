# Living Dossier B1.1 — pure contract implementation

**Status:** synthetic-only Python implementation; **not** a real-source reconciler, content approval or publishing authorization.
**Related design:** [B1 #321](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/321), [RFC draft #327](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/327), [B0 source audit #324](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/324), [rights #326](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/326).

## What is implemented

- \`core/dossier_contract.py\`: pure \`validate_dossier_shape(sc)\`, \`read_dossier(path, source_dir)\`, and \`dossier_content_digest(sc)\`, plus \`DossierValidationError\`. Python standard library only; **no database import, publisher fetch, model, email, site-renderer hook or file write**.
- \`tests/test_dossier_contract.py\`: **63** focused tests using made-up source records, invalid JSON, deliberately forged permissions-style strings, malformed dates and references, and version digest mutations.
- \`tests/fixtures/dossiers/fictional-exercise-reporting.json\`: a completely **fictional** draft with two invented example.org sources and two thematic sections. The ID numbers 900001 and 900002 **are not production sources**, and the fixture must never be placed under the future \`dossiers/\` directory, imported into public site output or used to infer source admission.
- A branch-only one-time smoke workflow ran, passed all **63** tests and proved no changed \`pla_watch.db\`, \`output/\`, \`briefs/\`, \`timelines/\` or SQLite WAL/SHM sidecars. It was **removed from this PR** after execution. See [run #38015955086](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38015955086).

## Reader contract / implementation properties

- Canonical direct-child JSON files: exact safe slug = file stem; no parent traversal or symlink escape; UTF-8, duplicate-key rejection at every nesting level, non-finite-number rejection and strict unknown-field rejection.
- Distinct IDs: \`sources[].record_id\` is a **strict positive integer**, not boolean, shadow/private string or a claim ID; \`sections[].claims[].id\` is an independently unique slug. Claim \`source_record_ids[]\` and \`counterevidence_ids[]\` can point only to the source ledger; disagreements refer to **claim IDs**, not record IDs.
- Meaningful structures: bounded retrospective research scope and explicit collection limitations; at least two thematic sections; attributed claim kinds \`issuer_statement\`, \`documented_publication\`, \`editorial_interpretation\`; publisher-stated dates remain distinct from optional attributed event periods, with \`planned\`/\`reported\`/\`retrospective\`/\`uncertain\` basis.
- Revision lineage: change notes follow \`1..revision\` and tie to latest edit date. Draft sidecars cannot carry approval. Approval-like objects are mechanically checked against current editorial content through canonical SHA-256 **excluding only the approval object**; any editorial/source/rights-reference change invalidates it.
- Human/rights trust boundary: approval strings and source-use references are **self-authored fields** here. Their shape is verified, **not their signer or legal force**. A structurally valid \`approved\` sidecar does not become publishable; independent human authority and source-use checks remain **unimplemented**, intentionally.

### Local focused test

~~~shell
python -m unittest tests.test_dossier_contract -v
~~~

Run with Python 3.9+ using the repository root. No API key, database or network dependency.

## Deliberately not implemented in B1.1

- No \`dossiers/<live-subject>.json\` (Singapore pilot not yet owner/source-use approved).
- No SQLite/archive source identity, frozen original-text SHA-256 parity, machine-screening disposition or source authorization verification (B1.2, after B0 pilot decision).
- No approved-only/draft publication route, static rendering, sitemap/canonical, revisions archive, CLI review receipts or deploy gate (B1.3/B2).
- No action to send the MINDEF permissions request, alter existing source full-text pages, delete archive bodies or override Singaroo #4428's negative relevance filter.
- No edits to existing Timeline #181, Briefs, frontend #323, site templates, production DB, generated output or Sunday operation.

## Handoff and gate before continued execution

1. **Review pure contract vs pending RFC #327**, particularly whether every edited claim must retain an event-period basis and how human permissions receipts are authenticated externally. Future refinements must preserve the synthetic negative tests and not weaken source/rights states.
2. **For B1.2**, implement read-only \`reconcile_dossier_sources()\` against a synthetic SQLite fixture first. Only then independently test real record IDs from a frozen, explicitly owner-accepted B0 source matrix; report \`parity_error\`, \`screening_hold\`, \`rights_hold\` and \`editorial_hold\` separately. Do not build “source_use_granted=true” from a self-authored JSON value.
3. **Stop at private validation.** Do not implement or call a public renderer, approve the pilot, merge/deploy or authorize quotes simply because the contract tests pass.

**Authority boundary:** the editor must approve the exact Dossier source and current version; publisher permissions and source admissibility are independent. Even fully green CI is not an editorial signature.
