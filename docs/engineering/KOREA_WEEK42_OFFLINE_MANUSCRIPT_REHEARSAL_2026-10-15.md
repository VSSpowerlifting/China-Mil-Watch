# Korea Week 42 — restricted manuscript and citation rehearsal

**October 15, 2026. NO-SEND LOCAL REHEARSAL, not a complete Sunday Brief, Korea desk admission, model or publication authorization.** The three real [source-pinned authored synopses](../../research/korea/private_research_candidates/2026-10-17.json) are held at frozen Korean shadow commit 0595f0fd29b769cbab5dd57c2ef57af174237a67. They cover the Pangyo defense AI hub (only the first site opened; four planned), the October 8–9 Japan defense talks (consultation, not an agreement), and the October 14 Gwangju readiness inspection (prospective relocation, not completed).

## This is a functional editorial test, not a reading-aid duplicate

The [manuscript CLI](../../scripts/rehearse_korea_week42_manuscript.py) now performs **deterministic editorial assembly** of the exact three pre-authored summaries. It generates a working digest followed by three separate narrative sections, each with a uniquely numbered footnote, caveats, canonical government URLs, differentiated portal versus ministry document dates and independently pinned Korean-text/HWPX/page-response digests. It ends in a held issue/permissions ledger. It neither invents new Korean translations nor attempts AI synthesis. An exact-output checker rejects manipulated claims, duplicate/lost citations, changed source identities/versions, changed permission labels and post-generation edits.

The input source is the already-validated **staged** JSON, not Sunday-consumed research evidence, the public article DB, or real original HWPX documents. Its reporting week *ends in the future* (October 17); the manuscript is therefore explicitly a **preliminary rehearsal** rather than an assertion that Week 42 is editorially complete on October 15.

## Safe use by editor/reviewer

Run from a local checkout on a trusted workstation, providing a new absolute path **outside this public repository**:

    python -m scripts.rehearse_korea_week42_manuscript --create /absolute/private/korea-week42-rehearsal.md --explicit-local-no-send

The tool writes a new owner-only 0600 file, refuses existing paths and paths inside the repo, and prints only source IDs/count, a document SHA-256 digest and fixed authority=false fields. Do **not** upload the generated manuscript, completed human reviewer forms, sensitive editorial notes or raw source originals into a public issue or PR.

After human edits, the generated file becomes an *unverified* new manuscript until separately reviewed. The exact checker deliberately fails if any text changes:

    python -m scripts.rehearse_korea_week42_manuscript --check /absolute/private/korea-week42-rehearsal.md --explicit-local-no-send

This is **not** a censorship or editing workflow; it prevents an edited version from masquerading as the automatically source-pinned baseline. A real editorial revision needs independent source/citation checks and authenticated owner approval.

## Limitations — release gates still separate

1. The current input holds do not include signed original-language reviewer identity, the actual mapped HWPX Korean lines or independently adjudicated limited-use rights. The version-bound local reviewer-intake machinery merged in #614 supplies only a structural form, not an authenticated signature.
2. The archived KOGL Type 1 notice is **text only**, requires attribution, and does not by itself grant media, translation, full HWPX, AI or public original archive rights. This tool copies **none** of those originals.
3. The original October 12 scheduled Korea collection **failed**. A later lookback cannot backdate a scheduled success or qualify seven prospective days. The contradictory Inje year in article 156785161 remains excluded (#601).
4. The production Korea originals currently reside on a **public** Git shadow ref. The separate [private vault](https://github.com/VSSpowerlifting/ipr-source-evidence-private) still contains metadata plus fictional pilot only; full original-copy, independent encrypted backup/restore, rights and one-writer cutover are held in #520.
5. Sunday model input, owner/editor SMTP, web/DB updates, DAPA, public record admission, rendered Brief pages and deployment **remain disabled** for these Korea notes. The working digest is not an AI-generated interpretation or published analysis.

## Automated acceptance

A **PR-only** read-only workflow uses the actual three-source staging packet, runs adversarial source/substitution/citation tests, creates and validates an owner-only local Markdown draft under RUNNER_TEMP, and deletes it with **no artifact**. No government fetch, Korean source binary, model, SMTP, private vault credential, Sunday workflow or deployment is used. Exact-head repository-wide offline CI still required before merging.

**End state:** real source-bound draft-and-citation rehearsal is technically repeatable, while the editorial authorization and secure operational chain remain independent human decisions.
