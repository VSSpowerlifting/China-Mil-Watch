# Phase 3B — Briefs catalogue: design and engineering contract

**Status:** implemented as a review candidate, revised after independent review of PR #418 (2 photographs, 15 plates); not merged, not deployed, no `output/` regeneration. 2026-10-12. Governing: `docs/FRONTEND_REFINEMENT_PHASE0_2026-10-10.md` (B1, B2, B3/B4, B5, B6) and `docs/engineering/BRIEFS_MEDIA_ELIGIBILITY_PHASE3A_2026-10-11.md`. Evidence and receipts: `docs/evidence/briefs-catalogue-3b-2026-10-12/`.

## What changed

`analysis.html` lists all 17 published Briefs (14 historical issues, Nos. 15–17 native) as media cards in one ordered list, newest first. The navy hero is untouched except that its optional lead photograph now passes through the same media decision and credit macro (see "Hero"). Every number, title, dek, date, label, provenance line, link and `rel="noopener"` is the baseline's; the redesign adds only the media block, one credit block per card and one short key.

| Layer | File | Role |
|---|---|---|
| Decision | `core/catalogue_media.py` | The one catalogue-media decision. Reads only the admission record. |
| Record | `site/assets/catalogue/admissions.json` | Explicit per-issue admission, with verbatim credit, caption, alt and licence. |
| Derivatives | `scripts/build_catalogue_media.py` → `site/assets/catalogue/media/` | Deterministic 720×480 3:2 JPEGs; `--check` verifies hashes. |
| Markup | `site/preview/templates/analysis.html`, `_catalogue_credit.html` | Cards and hero; imports only `region_plate` from the relief macros. `photo_credit` is the one credit for card and hero. |
| Styles | `site/preview/briefs-catalog.css` | Grid, typography, tags, credit lines; no shadow, no lift token. |
| Wiring | `site/preview/generate_preview.py` | `catalogue_media` ctx; `CATALOGUE_STATIC_ASSETS`; copies exactly the admitted files shown. |

## The media decision

The default is an **Editorial plate**: original IPR region artwork (Natural Earth outlines, from `assets/geo/region.svg`) in a 3:2 frame, tagged "Editorial plate", with the line "No source photograph. Outlines from Natural Earth." beneath the copy. It never says "Signal Veil".

A **Photograph** appears only when an entry in `admissions.json` is `status: "admitted"` and `resolve_catalogue_media` passes every check, in this order:

1. Row is a published Brief (not `synthetic`, not `is_review`) with an integer issue number.
2. The issue is not in `DENIED_ISSUES` (No. 12, B5), whatever a record says.
3. A record exists for that issue **and** reporting week.
4. Record status is `admitted`.
5. Required fields are present: alt, caption, credit, creator, licence, source page, source label, change note, served path, source file, served hash, size.
6. `source_file` is under `site/assets/editorial/` and `served` is under `assets/catalogue/media/`; neither matches the veil / source-image pattern.
7. Licence is `Public domain` or `CC BY 4.0`; CC BY needs a licence link; the source page is `https://`.
8. Origin continuity: the source file's name begins with its `source_manifest_id`, the file exists and its SHA-256 equals `source_sha256`, and the curated manifest entry with that id still has the record's `license`, `license_url`, `source_page` and `credit`.
9. The served file exists and its SHA-256 equals `served_sha256`.

Any failure returns a plate with a reason code (for example `source-hash-mismatch`, `source-missing`, `manifest-changed:license`). Nothing raises at build. The manifest is read only to confirm the reviewed source is still the one on disk; it never grants permission.

**Isolation.** The module never calls `brief_veil`, `source_veil_for_edition` or `pw_env`, and never reads an entry's `cover` or `photo`. An article cover, a Signal Veil or a matching source-trail URL is never permission for this surface (3A gate 1). A test asserts the module does not name those surfaces and that a row carrying a `cover` still resolves to a plate.

## Admission outcomes (revised after independent review of PR #418)

Nos. 8 and 9 were approved, No. 10 held, by the independent review. Catalogue only; no blanket permission. Flipping an entry to `held` returns that card to a plate and changes nothing else.

| No. | Outcome | Basis |
|---|---|---|
| 8 | **Photograph** — CC BY 4.0, linked licence, creator in English and Japanese | Japan MOD / Joint Staff original; Commons record verified (receipt); manifest credit, caption and alt used verbatim |
| 9 | **Photograph** — Public domain (NASA / ISS Expedition 45) | Commons record verified (receipt) |
| 10 | **Held** — plate | Commons' PD-US-Government category and a "provided to CRS" attribution do not establish who made the photograph; the file's author field describes the CRS report. The drafted alt ("underway on the surface") is not established by the source and must not be reused. The opened-article use is a separate, unchanged surface. Clear only with original-photographer or originating-agency evidence |
| 1 | **Held** — plate | Identifiable, named U.S. and PLA officers at an unrelated 2012 event, auto-selected by keyword for a Brief about former defence ministers; beside that headline a card could read as identification. The sidecar alt text is a filename. Clear only with an owner-reviewed alt and short caption |
| 12 | **Denied** — plate | B5 |
| 2–7, 11, 13–17 | Plate | No admission record |

No 81.cn / PLA Daily imagery, no CC BY-SA file (B6) and no No. 12 image is referenced anywhere on the page; the verifier asserts zero requests for `*-source-image*`, `*-veil*`, `81.cn`. No. 10's catalogue derivative was removed from `site/assets/catalogue/media/`; its record keeps the Commons page and credit string as provenance.

**Derivatives.** The two card images are re-crops (focal point recorded per entry) of the existing curated, already-toned `*-duo-navy.jpg` derivatives, resized to 720×480, progressive JPEG, no metadata, encoded with Pillow 11.3.0 (recorded as `built_with`; bytes are only reproducible for that encoder, so production verifies the committed file's SHA-256, never a re-encode). The card says "Toned, cropped and resized by IPR." and "Visual context, not evidence." The label is "Photograph", never "Signal Veil".

## Card anatomy

`li > article.rl-brief.brief-card[data-media]`:

1. `.brief-media[data-catalogue-media]` — a 3:2 `.rl-print` frame (plate SVG with a decorative issue numeral, or a lazy `<img>` with explicit width/height) and a text tag.
2. `.issue-ledger-meta` — number, date, labels (unchanged classes and text).
3. `.issue-ledger-copy` — headline link, dek, desks line, provenance line (unchanged).
4. `.brief-credit` — plate note, or caption, date note, creator, licence link, "via Wikimedia Commons" link, change note.

One primary link per card (the headline). It stretches over the card; credit links sit above it. Card-level `:has()` focus ring replaces the link's own outline (fallback: the link keeps its outline where `:has()` is unsupported). The only elevation is the approved B1 `rl-brief` lift. Grid: 1 column to 639 px, 2 to 1039 px, 3 above; 3:2 frames throughout. A short key under "All Briefs" explains the two media labels.

## Accessibility and degraded modes

- Plate art and the numeral are `aria-hidden`; the tag and note carry the meaning in text.
- Forced colours and print: plate frames are removed (`relief.css` already hides the art) and the tag becomes a bordered text label; photographs stay.
- Reduced motion: image scale and card lift wait for `prefers-reduced-motion: no-preference` (relief.css gating plus one rule here). No-JS: no script is needed; captures are byte-identical to default.
- No new JavaScript. Page JS is 3,118 B (unchanged).

## Hero

`briefs-lead-photo` is rendered only if the lead row resolves to a photograph, and its figcaption calls the same `photo_credit` macro as a card: caption and date note, creator with native name, licence link (`rel="noopener"`), source link, change note and "Visual context, not evidence." The lead is No. 17, which has no cover, so nothing changes today. The old path rendered a native Brief's cover with no catalogue decision; that path is closed. `HeroPhotographTests` builds the page with a non-synthetic fixture lead whose media is admitted (resolver patched with No. 8's real record) and asserts the credit; the same build without an admission has no hero figure.

## Budgets and publication

HTML + CSS for `analysis.html`: 119,787 B (main 102,225 B, measured at `9586568437`; cap 300,000 B). JS: 3,118 B (cap 10,000 B). Photographs: 50,835 B in total, loaded lazily. `region.svg` (49,760 B) is referenced through `<use>` and is not counted by the delivery verifier's asset list; `receipts/analysis-budget.json` reports the corrected page weight (HTML+CSS+JS 122,905 B; with photographs 173,740 B; with `region.svg` 223,500 B) without changing the shared checker. Production publishes exactly `assets/geo/region.svg` plus the admitted files a card shows (two JPEGs); `relief.css` is now linked by the homepage, Archive and catalogue only.

## Out of scope / not done

Hero redesign, Phase 3C article presentation, the opened-article No. 1 alt text, No. 12's existing surfaces, any change to sidecars or `output/`, owner visual sign-off. Chromium only; no Safari, Firefox or assistive-technology run.
