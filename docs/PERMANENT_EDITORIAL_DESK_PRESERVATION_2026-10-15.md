# Permanent IPR editorial desk publication — source links and preservation

**Owner decision: October 15, 2026.** A public IPR desk may consist of independently authored, reviewed and published IPR research with exact first-party links, original-source metadata and citations. It need not rehost the government publisher's full text or photographs, and it must not pretend a shadow collector or a private custody repository is operational when it is not.

## What is genuinely preserved

| Record | Public reader can retrieve it from IPR? | Persistence meaning |
| --- | --- | --- |
| IPR-authored approved analysis and its citations | Yes, as a committed IPR Brief HTML page | The IPR publication itself is preserved in source/rendered Git history, subject to genuine backup and restore |
| Official original URL, title, date, identity, issuer | Yes, in an approved Brief's citation and permanent desk reference | Bibliographic provenance survives in IPR even if the government link later disappears; **the original content does not** |
| Official source SHA-256 and exact shadow Git-state commit, when available | A validated, provenance-linked identity digest may be recorded | Can compare against a *separately available* original; a digest cannot reconstruct deleted original bytes or authenticate an actual third-party capture on its own |
| Actual original-source body or PDF captured in public Git shadow branch | Not reproduced on IPR site by this mechanism, but public Git history is externally reachable | Byte-bearing copy if collected, **not private custody**; existing public distribution cannot be undone by later migration |
| Verified access-controlled original plus independent encrypted restored backup | Not claimed currently | Requires genuine transfer to private repository, byte parity, permission review and independently successful recovery; private repo provisioning or Korea metadata inventory alone does not establish this |
| Source photographs, maps, scanned PDFs and third-party visuals | No | Remain with official publisher by default. No downloading/rehosting or hotlink embedding via this release |

This is **partial preservation** that keeps citations and original analysis independently accessible and provides some evidence for later forensic review. It does not mean IPR is a mirror of every government document.

## Editorial launch criteria — no beta category

Permanent public editorial release is **not** a collector activation. Publish only when a real IPR-authored Brief has passed source-original editorial review, language/issuer/date/claim checks, and output-specific rights review. The title, release date, named editor, exact approved IPR commit and source URLs enter `research/approved_desk_research.json` through a separately reviewed PR. Neither an empty register nor a string naming an editor proves they actually authorized release; the written editorial decision and the independent PR review are mandatory.

The automatic register (schema `ipr-permanent-editorial-desk-research/1`) accepts at most 40 IPR Briefs and 20 original source citations per paper. Only official HTTPS domains and exact source families are allowed. Each source has an original-language title, issuer, date and identity. Optional source-state SHA plus capture digest are provenance **identifiers**, not assertions of verified private backup. Fields containing source text, translations, articles, image paths, photographer media, embed codes or private custody assertions are rejected.

The actual renderer `site/preview/generate_preview.py` adds the approved article and its official links to the corresponding country page. It labels an editorially publishing desk as research published while keeping collector status and production archive counts separate; no temporary `beta`/preview label is introduced. The initial catalog contains **one already published and owner-approved IPR Brief**, No. 18 *What Is Being Built in Laos?* (editorial approval 2026-10-13, `briefs/what-is-being-built-in-laos.json`, commit `504e8a95cb53e6fe500695aaa051f9dca82d8fe1`). It assigns that existing public IPR-authored investigation to the Vietnam research desk and cites **three exact, previously source-checked Vietnamese government originals**: two Vietnamese Government News articles (October 8) and the Ministry of Public Security article (October 9). The approved manuscript pins every original URL and Vietnamese title. The citation deliberately has **null** original capture digest/state: it does not claim independent byte-retained ministry custody. No new, unapproved Briefs, translations or government originals have been added. Other countries' catalogs remain empty until their actual editorial releases are approved.

`scripts/guard_public_editorial_research.py` checks **real rendered files**: every registered IPR Brief must exist; its HTML must link to each exact declared publisher original; its country page must link to that Brief and its originals; the original-source corpus must not be falsely exposed. This guard runs in the existing read-only source-reference CI and guarded render-only country site release, *before* GitHub Pages deployment.

## First permanent Vietnam editorial reference

- Existing IPR article: `briefs/what-is-being-built-in-laos.html` (Issue No.18); first committed to rendered output by October 13 and revised October 14. The source manuscript records the owner's substantive editorial and limited-source-use approval on October 13.
- Exact first-party originals: two Vietnamese Government News sources dated October 8 and Vietnam MPS dated October 9, “Hợp tác an ninh tiếp tục là trụ cột trong quan hệ Việt Nam – Lào.” The public editorial citation links directly to `https://bocongan.gov.vn/bai-viet/hop-tac-an-ninh-tiep-tuc-la-tru-cot-trong-quan-he-viet-nam-lao-1791535381`.
- This is **actual IPR-authored writing**, not a copied source article, extra photo, newly generated model claim or phantom human review. A Vietnam source collector is still not marked `live`; no full original-body archive is claimed.
- The new country-page feature must pass the exact rendered Brief/official-link gate before it is visible on the desk page. The **owner-reviewed merge of this publication-contract or approved-catalog PR** now starts an exact-Git-SHA-bound GitHub Actions scoped release automatically on main (same style as the approved Korea bibliography release). A mere source merge is **not proof** of deployment: the release may fail on main drift, stale DB, missing local rendered Brief or source-link parity, an unexpected output change, or unavailable Pages permission. Confirm the actual Actions release and deployed public page. A separate manual `workflow_dispatch` with `approved_main_sha` and `publish=true` remains the fallback after independently reviewing the new main SHA.

## Next genuinely missing work

1. Finalize and sign a source-version-bound original-language review of selected official sources for the **first actual IPR research article** (Indonesia's exact 31-item queue or AFP's 22-item docket provide candidates). Choose a narrow topic with clear provenance; do not rubber-stamp all records as one unit.
2. Draft or adapt an independently authored IPR analysis with accurate source citations; check original language and corrections; complete editor and owner approval. Verify the output-specific reuse/quotation rights.
3. Register the approved IPR Brief and exact official links, run the full website render and guard, independently inspect the output, and **merge the owner-reviewed catalog/release-contract PR to trigger the exact-SHA-bound scoped Pages release**. The manual approved-main-SHA workflow remains a fallback if concurrent main changes invalidate a release. Verify successful actual deployment and the public URL; only then call the editorial research desk publicly active.
4. Separately finish original-source custody in `VSSpowerlifting/ipr-source-evidence-private`, including failed attempts, byte-parity and encrypted backup restore. **Do not delete/rewrite already-public shadow branches** before independently verified migration and source-use assessment.
5. When genuine collection and source-use evidence qualifies a source set, pursue the separate production archive admission. Editorial research publication does not waive collecting continuity for a claimed live collector.

**No change by this PR:** source-original storage, copyright or robots decisions, permissions, shadow branches, `pla_watch.db`, production manifests, source photos, Brief contents, collection schedules, email/model calls or public deployment.

Relevant preservation distinction: the U.S. Library of Congress notes that stable URLs/metadata support web preservation and link durability but bit-level preservation requires actual managed content copies; even a bitstream by itself does not guarantee future usability.
