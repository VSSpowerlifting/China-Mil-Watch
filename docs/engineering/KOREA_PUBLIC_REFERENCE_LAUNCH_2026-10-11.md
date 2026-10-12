# South Korea Desk — public source-link-only launch (owner instructed)

**Date:** October 11, 2026. **Scope:** a publicly navigable fixed bibliography of five Ministry of National Defense press releases **republished by Republic of Korea Policy Briefing**. This is NOT the full Republic of Korea research desk or production archive. Owner explicitly directed public availability of source links and questioned whether separate document-reuse signoff should block plain bibliographic links.

## Rationale

The publisher's official [copyright policy](https://www.korea.kr/guide/copyRight.do) says properly marked KOGL Type 1 text may be used with source attribution, distinguishes potentially third-party media, and requests that linked works be accompanied by a link to its policy. The official page for document `156784297` shows the exact wording and publisher notices.

This release copies **only official source Korean headline, canonical outbound link, official issuing institution, republishing government portal, posting/distribution dates and source identity**. These are factual source identifiers; no source body, imagery, HWPX, translation, paraphrase, excerpt or unsigned reviewer packet is made public. Such a bibliography can be published with attribution; substantial document reuse has different permission and accuracy considerations.

## Hard bounds in code

- `research/korea_public_reference_ids.json` is an exact five-ID release allowlist and frozen original-state SHA, without any body or rights-reviewer assertion.
- `core/korea_public_bibliography.py` validates the manifest, frozen `core/korea_reference_gate.load_candidates()` corpus hashes, exact canonical government URLs and original issuer/publisher. It exports **only five bibliographic fields per row**.
- Registry: `public=true`, `status=shadow`, `manifest=null`, `has_production_records=false`. This makes a **reference desk** publicly accessible but explicitly does not enable any collector/source or production-record count.
- The existing IPR `desk.html` template has one Korea-only block, separate from the Vietnam/Philippines *human-reviewed* link pattern and from the separate private Korean review preview. The visible source is original Korean, not an unverified English interpretation.
- No model input, Sunday Briefs, publisher fetch, new Korean source, DAPA, HWPX/photo replication, direct MND crawler, production SQLite mutation or automatic update is allowed.
- A list error, sixth ID, wrong immutable SHA, wrong URL/issuer, or drift of the original candidates fails the release before it becomes a public page.
- Corrections/takedowns: remove or disable the individual bibliography item only via a new reviewed allowlist change; never silently admit other sources.

## Deployment

The narrow `korea_public_bibliography_release.yml` GitHub Actions workflow verifies actual site rendering, protected DB hash, five external canonical links, no copied source bodies, publisher attribution, noindex removal, sitemap inclusion, and preserved production counts. On the first owner-authorized merge to `main`, a `push` path rule builds and commits only regenerated `output/` to main and updates GitHub Pages, without collecting or calling a language model. Deployment uses the existing Pages CNAME `indopacificrecord.org` and serializes with `daily-update`.

A successful source PR merge or even output commit alone is not conclusive deployment proof: check the release Actions run and the actual live [South Korea Desk](https://indopacificrecord.org/korea.html).

Full Korean original-language analysis, rehosting and model-based publication still require separate content-specific checks, which have **not** been completed here.
