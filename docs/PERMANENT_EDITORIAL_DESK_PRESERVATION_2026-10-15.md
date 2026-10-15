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

The actual renderer `site/preview/generate_preview.py` adds the approved article and its official links to the corresponding country page. It labels an editorially publishing desk as research published while keeping collector status and production archive counts separate; no temporary `beta`/preview label is introduced. When the catalog is empty, the new section is not shown and no country's status is promoted.

`scripts/guard_public_editorial_research.py` checks **real rendered files**: every registered IPR Brief must exist; its HTML must link to each exact declared publisher original; its country page must link to that Brief and its originals; the original-source corpus must not be falsely exposed. This guard runs in the existing read-only source-reference CI and guarded render-only country site release, *before* GitHub Pages deployment.

## Next genuinely missing work

1. Finalize and sign a source-version-bound original-language review of selected official sources for the **first actual IPR research article** (Indonesia's exact 31-item queue or AFP's 22-item docket provide candidates). Choose a narrow topic with clear provenance; do not rubber-stamp all records as one unit.
2. Draft or adapt an independently authored IPR analysis with accurate source citations; check original language and corrections; complete editor and owner approval. Verify the output-specific reuse/quotation rights.
3. Register the approved IPR Brief and exact official links, run the full website render and guard, independently inspect the output, and deploy via the existing exact-reviewed-SHA guarded release. Only then call the editorial research desk publicly active.
4. Separately finish original-source custody in `VSSpowerlifting/ipr-source-evidence-private`, including failed attempts, byte-parity and encrypted backup restore. **Do not delete/rewrite already-public shadow branches** before independently verified migration and source-use assessment.
5. When genuine collection and source-use evidence qualifies a source set, pursue the separate production archive admission. Editorial research publication does not waive collecting continuity for a claimed live collector.

**No change by this PR:** source-original storage, copyright or robots decisions, permissions, shadow branches, `pla_watch.db`, production manifests, source photos, Brief contents, collection schedules, email/model calls or public deployment.

Relevant preservation distinction: the U.S. Library of Congress notes that stable URLs/metadata support web preservation and link durability but bit-level preservation requires actual managed content copies; even a bitstream by itself does not guarantee future usability.
