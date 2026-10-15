# Korea public feasibility — 14 archived official-link review without source redistribution

**October 15, 2026.** This PR creates a reviewable **14-source public-link candidate roster** tied to the actual frozen Korean MND original archive and official publisher page-license evidence. It does **not** authorize adding nine new links to the live site, change the five approved references, or distribute a Korean document. The live Korea desk remains a bounded five-official-link **public reference directory**, not a production ingestion source.

## Evidence advanced

Two existing substantive audits now have a machine-enforced intersection:

- [Fourteen HWPX source identities](../../research/korea/MND_HWPX_14_ORIGINAL_SOURCE_REVIEW_REGISTER_2026-10-14.md), with their exact issuer article IDs and response SHA-256 from archived real collector evidence.
- [Fourteen captured publisher-page notices](KOREA_MND_14_PAGE_KOGL_TYPE1_TEXT_MARK_AUDIT_2026-10-15.md), each explicitly marked **KOGL Type 1 for text only** and separately excluding photographs, illustrations, graphics and video without rightsholder permission.

The [new 14-source review manifest](../../research/korea/MND_14_PUBLIC_LINK_REVIEW_CANDIDATES_2026-10-15.json) matches all source IDs and HWPX/page hashes against those reviewed records. The five already public IDs are separately checked against the existing five-link production manifest. All nine additional official links are **HELD**. The contradiction in source `156785161` (2025 versus 2026 excavation year, #601) remains an explicit editorial exception.

## What is functional and safe now

The [operator preview tool](../../scripts/preview_korea_fourteen_official_links.py) validates those two audits, ensures exactly fourteen distinct canonical MND republication URLs, refuses mismatched capture identities and altered source-use or owner-approval flags, then writes a **new owner-only 0600 Markdown review document** to an explicitly chosen absolute path *outside* the repository. It uses the five original Korean titles already cleared for link-only bibliographic display; the other nine use neutral source-ID labels, **not unreviewed English translations**. It copies no body, HWPX, image, attachment, table or source quote. The output holds nine proposed public links and prints only counts and its document digest, never source prose or paths.

Example after opening a trusted local checkout:

    python -m scripts.preview_korea_fourteen_official_links --private-preview-out /absolute/owner-only/korea14-quick-review.md --explicit-no-publish

The CI workflow uses those same strict source identities, creates and checks the file under a disposable restricted runner directory and **deletes it without uploading any review artifact**. The live five-link bibliography tests continue to require precisely five source records, a shadow registry status, no new production records and no change to Pages output.

## Exact public feasibility gates

A publicly useful **link-only expansion** can be considered separately from the full production archive because official canonical government links and very sparse factual bibliographic information do not require mirroring Korean government HWPX files, photos or extracted text. Before nine new links are published, however, the owner must specifically review the source identity/title/date evidence, rights/attribution scope and publication wording, then authorize a *separate exact-head release PR*. This review manifest cannot be flipped into a release via an approval flag.

A **complete public production desk** is a different and much larger decision. It still requires (1) source-specific authenticated Korean human visual/semantic line review, (2) intended-use rights adjudication for English paraphrase, public body, external model and any media, (3) controlled private custody and independently tested recoverable encryption, (4) corroborated prospective scheduled collection reliability and source scope, (5) a source adapter and normalized production ingestion/desk registry with regressions and complete coverage caveats, (6) explicit no-send Sunday editorial testing before separately approved model/email use, (7) guarded site deployment and ongoing quality/rollback review. **DAPA is still research-only** and requires separate source authorization, not inferred MND coverage.

An original page's KOGL Type 1 text badge is favorable *rights evidence*, not an authenticated third-party photo license, automatic consent to external AI, or proof of a publisher page's substantive claims. Do not claim that official MND statements are independently corroborated. The historical October 12 failed scheduled slot remains failed, regardless of later new qualification.

**Disposition:** Nine additional exact-version official URLs are staged for a restricted owner review; **zero new URLs approved or published**. No source copy, subscriber mail, model, private-vault migration, publisher HTTP request or production mutation has occurred.
