# Living Dossiers B2.2a — private reader data model

**Implementation scope: isolated, fictional-only, nonrendering.** This PR is stacked on the B2.1 draft #335. It must not be merged ahead of B1.1 #328, B1.2 #329, B1.3 #330, or B2.1 #335. No public page, publication entitlement, source admission or rights review is implemented.

## Reader problem

A maintained Dossier should answer: what exact bounded question is being reviewed, what is documented by preserved sources, what is disputed or incomplete, how does IPR distinguish issuer claims from its own interpretation, and what changed in the latest reviewed version? The next UI phase needs one **reviewed plain-data presentation contract** before any shared Jinja template work.

## Files and ownership

- `core/dossier_private_view.py`: pure, deterministic Python 3.9 reader projection. Calls the real B2.1 preview gate. Rejects all ordinary/real-world sidecars, invalid B1.2 archive reports, stale versions, uncleared links and missing fictional review packets. No disk, network, model or renderer invocation.
- `tests/test_dossier_private_view.py`: 17 offline fictional cases, including two real B1.2 synthetic SQLite reconciliations.
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
