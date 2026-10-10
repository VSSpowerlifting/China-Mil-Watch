# Living Dossiers B2.2a — private reader data model

**Implementation scope: isolated, fictional-only, nonrendering.** This PR is stacked on the B2.1 draft #335. It must not be merged ahead of B1.1 #328, B1.2 #329, B1.3 #330, or B2.1 #335. No public page, publication entitlement, source admission or rights review is implemented.

## Reader problem

A maintained Dossier should answer: what exact bounded question is being reviewed, what is documented by preserved sources, what is disputed or incomplete, how does IPR distinguish issuer claims from its own interpretation, and what changed in the latest reviewed version? The next UI phase needs one **reviewed plain-data presentation contract** before any shared Jinja template work.

## Files and ownership

- `core/dossier_private_view.py`: pure, deterministic Python 3.9 reader projection. Calls the real B2.1 preview gate. Rejects all ordinary/real-world sidecars, invalid B1.2 archive reports, stale versions, uncleared links and missing fictional review packets. No disk, network, model or renderer invocation.
- `tests/test_dossier_private_view.py`: 29 offline fictional cases, including two real B1.2 synthetic SQLite reconciliations.
- This document.

**Explicit no-touch files:** `site/render.py`, `site/preview/generate_preview.py`, `site/preview/templates/base.html`, `analysis.html`, `brief.html`, `timeline.html`, `output/`, `pla_watch.db`, existing Briefs/Timelines sidecars, collector workflows and deployment configuration. The Timeline #181 and frontend #323 owners retain their files.

## Contract

The view is plain Python dictionaries with a fixed `ipr-dossier-private-reader-view/1` schema, explicit fictional/private watermark and hard-disabled public metadata (`eligible_for_publication=false`, `indexable=false`, no `public_route`, `canonical`, `sitemap_route` or `feed_route`). There is no HTML or user-supplied template interpolation.

It contains the Dossier title, dek, question and explicit scope/collection gaps; two or more thematic sections; issuer/doc-publication/editorial-interpretation labels for each claim; exact in-ledger source/counterevidence anchor IDs; disputes and limits; original-language/source-ID ledger entries; updated/reviewed dates and changes. Source descriptions are from *fictional* test inputs. The only possible publisher URLs are B2.1-vetted `https://example.org`/RFC example hosts, and there is no local IPR record link, raw original publisher text, permission receipt or published citation link. Authored related Brief/Timeline slugs produce **no link** without independent public-target approval.

**Important dependency distinction:** B1.3's saved private review JSON is not a B1.2 report and cannot substitute for it. The caller must create a fresh B1.2 report by running the real reconciler on an isolated fictional SQLite archive, then call the B2.1 gate. This pure model cannot authenticate the provenance of a supplied report; it is not a production authority provider.

## Regression expectations

Focused tests cover:
1. Strictly fictional private projection and no routes/canonical/sitemap/feed.
2. Thematic structure, claim attribution, source ledger identities, original language, limitations, revisions, disagreements and counterevidence links.
3. Draft refusal, live-range ID refusal, stale archive hash, missing link authority, and rejection of B1.3 private CLI diagnostic JSON as B1.2 source evidence.
4. Nonleakage of author receipts, archived bodies, raw publisher copy or public HTML. Deterministic serialization and no mutation of input structures.
5. Real synthetic SQLite parity successful read-only handoff and negative archived-body drift.

Run with the actual dependency stack:

```
python -m unittest tests.test_dossier_contract tests.test_dossier_sources tests.test_validate_dossiers tests.test_dossier_publication tests.test_dossier_private_view -v
```

## Stop conditions

Stop at the plain-data model and tests. Do **not** create a page, CSS, shared site template, route, sitemap entry, index, alternate media format, deploy preview, editorial approval tool or source/copyright rule. B2.2b Jinja HTML authoring and responsive inspection requires frontend #323 and Timeline #181 ownership reconciliation plus explicit review of a future authenticated/public source-use contract. B0 #319, MINDEF rights #326 and specific editorial permission gates remain open.

Green synthetic CI is mechanical confidence in the private view contract, **not** public Dossier eligibility.

## Execution receipt — 2026-10-10

[Focused GitHub Actions #38060837428](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38060837428) ran the actual inherited B1/B2 Python modules under Python 3.9 and **passed 161/161 synthetic tests** (67 B1.1 + 23 B1.2 + 21 B1.3 + 33 B2.1 + 17 B2.2a). Python compilation and unchanged tracked SQLite/output/Briefs/Timelines checks also passed. The test executed only wholly fictional local SQLite fixtures and produced no site output.

The temporary PR workflow was removed in commit `329656d2f31a5c4b1f5c26b18cb7ba32dba92ab2`, preserving a three-file lasting diff. This focused result is **not** full repository exact-final-head CI and does not satisfy unresolved #328→#329→#330→#335 dependency integrations, frontend #323 / Timeline #181 ownership, B0 subject/source acceptance #319, or legal/source-use decisions #326. Release remains hard-disabled.

## Two-edition structural comparison (B2.2a extension)

The private reader now requires a real, separately supplied **fictional immediate predecessor** for any revision 2+, rather than treating an author-written `history_checked=true` flag as proof of continuity. It checks B1-valid prior approval shape, same subject and consecutive revisions, preservation of all earlier revision notes, and an actual substantive change beyond an incremented number. Its `revision_comparison` projects exact previous digest, added/modified/removed claim IDs and substantive field names. If a claim was added or altered but omitted from the latest revision's affected-claim list, the view refuses to assemble. Twelve additional fictional regression cases check missing/relabelled predecessors, rewritten prior notes, unchanged-substance revisions, claim omissions and scope-only changes.

**Important limit:** This is a structural comparison between two **caller-supplied** objects, not independently authenticated publication history. B1's existing schema disallows removed IDs in `changes[].affected_claim_ids`; the comparison reports removed IDs separately without representing the author's note as a verified deletion acknowledgment. The later authenticated release provider must pin historical versions in a durable, owner-controlled source store. No production authority is implemented, and no real archive content can enter the private fictional mode.

## Two-edition synthetic test receipt

[Focused GitHub Actions #38062683377](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38062683377) passed **173/173 tests** under Python 3.9 (67 B1.1 + 23 B1.2 + 21 B1.3 + 33 B2.1 + **29 B2.2a**), including real fictional SQLite integration, content/body drift denial, predecessor version lineage and claim-change acknowledgments. Python compilation and tracked archive/output/Briefs/Timelines no-write checks passed. A temporary read-only CI workflow was deleted in cleanup commit `28426e8955e9bca3977639e4f960f2eb409329e4` after the successful receipt. The lasting PR remains three new files and **does not** include workflow or site changes.

CI ran on a temporary test commit; the subsequent cleanup/documentation commit has no independent full repository CI. Because upstream B1/B2.1 changes and #323/#181 remain unintegrated, this result is bounded to a private fictional projection and is not a release or merge authorization.
