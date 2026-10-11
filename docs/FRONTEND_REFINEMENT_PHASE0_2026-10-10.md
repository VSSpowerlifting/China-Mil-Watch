# Frontend expressive refinement: Phase 0 decision packet

**Date:** 2026-10-10.
**Base:** `main` at `6d1c88f87c2f8f04cce0443a9188a14e2679d50c` (merge of #341).
**Branch:** `claude/ipr-frontend-refinement-review-ead1c5`.
**Scope:** Phase 0 design and technical preflight only, under charter v1.1 and the Phase 0 kickoff.
**Status:** Phase 0 closed. The owner approved all five decisions on 2026-10-10 (B1 = A, B9 = A, B3/B4 = A, B2 = B, B5 = B), recorded in `DECISION_LOG.md` under 2026-10-10. **Independent visual sign-off of the study screenshots has not been given.** Image-rights and attribution questions listed in §1.2 remain open.
**Production changes: none.** No template, CSS, JS, script, `output/`, sidecar, DB or deployment change. `DESIGN_SYSTEM.md` is not edited; its §5 exception is recorded in `DECISION_LOG.md` and applied in a later reviewed phase.

Changed files (one documentation-only commit on this branch):

- this document
- a pointer in `PROJECT_STATE.md`
- a 2026-10-10 entry in `DECISION_LOG.md` recording the owner rulings
- `docs/evidence/frontend-refinement-phase0-2026-10-10/`, containing:
  - 45 JPG captures
  - the disposable study overlays and their data
  - the study tools
  - capture plans and capture reports
  - the validator receipt

Nothing in the evidence folder is production code. The overlays inject into a served `output/` build at review time and are scoped to `html.study`.

## 1. Owner decisions

### 1.1 Rulings (binding, 2026-10-10)

| ID | Ruling | Contract |
|---|---|---|
| **B1** | **A: controlled shadow levels** | Exactly three restrained, named elevation tokens, used only on the finder, the homepage record cards, the analysis plane, the Brief card, the desk plate and the desk source-scope panel. The IPR palette stays. A narrow exception to `DESIGN_SYSTEM.md` §5, recorded in `DECISION_LOG.md`; no general-purpose drop shadows anywhere else. |
| **B9** | **A: full-colour country flags** | Small, accessible 4×3 flags on country-labelled desk plates, with flag-icons 7.3.2's MIT licence and notice preserved. National flag red is not the crimson analysis signal; status stays a separate textual or graphic marker. |
| **B3/B4** | **A: distinct media classifications** | **Signal Veil** only for a provenance-supported duotone derivative of a photograph in the Brief's own cited source. An approved photograph is called a **photograph** and is visibly credited and licensed. Original maps and drawings are **Editorial plates**, labelled as non-source imagery ("No source photograph"). Illustration is never presented as documentary evidence. |
| **B2** | **B: editorial artwork on the Briefs catalogue** | Permission assumptions for 81.cn / PLA Daily images are **not** extended to the catalogue card. Catalogue cards use authored, geographically grounded Editorial plates where no approved photograph exists, under the B3/B4 contract. |
| **B5** | **B: use the existing No. 12 image now** | The existing No. 12 image is retained rather than replaced by a held plate. This is a presentation choice only (see §1.2). |
| — | Light desk map | Already owner-directed: Phase 4 replaces the dark map with a light basemap, status-based country treatment and geographically anchored flag-tab plates. The US Indo-Pacific desk is never a sovereign polygon. |

### 1.2 Questions the rulings do not resolve

These stay open. Nothing in Phase 1 depends on them, and no phase may treat them as settled.

- **Opened-article 81.cn treatment.** B2 does not newly approve or settle the existing veils on the opened historical editions and weekly index card (DECISION_LOG 2026-08-12, ruling D2), nor No. 15's photograph in its opened article. They are preserved as they are unless separately directed, and their rights review continues.
- **No. 12 attribution and image rights.** Retaining the image does not resolve either. The Global Times URL is dated 2026-06-22, before the 2026-08-01 edition; chronology alone does not show the image is unrelated, and it does not show it belongs to the cited article. The source-image metadata `note` carries mismatched 81.cn boilerplate. A narrow governed follow-up, which does not block P1, will correct the metadata and confirm the image against the article. Until it closes:
  - the incorrect note is never rendered (the public caption keeps coming from the source trail);
  - no source association or permission is invented;
  - generated output is not hand-edited;
  - the image does not move onto the catalogue card or any other new surface without a specific, reviewable rights and attribution assessment.
- **Visual sign-off.** The owner's rulings approve design choices, not the study screenshots. Those need independent examination before any sitewide redesign advances (P2 onward).

### 1.3 Options as presented to the owner

Kept for the record. Recommendations below are the packet's original advice; §1.1 is what governs.

| ID | Decision | Options | Recommendation | Evidence |
|---|---|---|---|---|
| **B1** | Elevation versus `DESIGN_SYSTEM.md` §5, which allows "**no box-shadows** except the hairline under the sticky nav rail". | **(a)** A bounded exception: three lift tokens, used only on the finder, the home record cards, the analysis plane, the Brief card, the desk plate and the scope panel. **(b)** An offset paper stack: a hard second sheet built from a pseudo-element, with no blur and no `box-shadow`. **(c)** Keep the surface shift as it is today. | **(a)**, recorded in `DECISION_LOG.md` with that component list. The charter asks for a raised 3D search, and (c) is a hard fail ("search left flat"). Choose (b) if the no-shadow rule should stay literal. | `shots/home-after-finder-1280.jpg` (a), `shots/home-stack-finder-1280.jpg` (b), `shots/home-before-finder-1280.jpg` (c) |
| **B9** | Flag colour versus the crimson reservation. China and Vietnam flags are red. | **(a)** Full-colour flag-icons at 22×16.5 px in a paper tab, beside a country name only. **(b)** Desaturated or navy duotone. **(c)** No flag; ISO code text. | **(a)**, with the rule that a flag identifies a country and never carries status or signal. Status stays on the plate's top rule (solid / dashed / warning). | `shots/desks-study-map-1280.jpg`, `shots/desks-study-reads-1280.jpg` |
| **B3/B4** | The naming and disclosure contract for Brief images (charter D5). | **(a)** "Signal Veil" applies only to a duotone of a photograph from the Brief's own cited source. A curated licensed photo stays a **photograph** with credit and licence. A drawn map is an **"Editorial plate"**, tagged on the image, with "No source photograph" in the caption. **(b)** Broaden "Signal Veil" to every Brief image. | **(a)**. **(b)** would describe a drawing as source-derived, which "decoration must never masquerade as evidence" forbids. | `shots/briefs-no81-list-1280.jpg`, `shots/briefs-no81-list-mid-1280.jpg` |
| **B2** | 81.cn / PLA Daily veils on a **new** surface, the Briefs catalogue card. Today they appear on the opened edition and the weekly index card under DECISION_LOG 2026-08-12 ("provably the cited article's own") and ruling D2. | **(a)** Extend that ruling to the catalogue: same derivative file, same credit, no new copy. **(b)** Show the photograph only in the opened article, with a labelled plate on the catalogue card. | **Owner ruling required.** The packet does not assume (a), because the kickoff forbids inferring rights. With (a), seven historical Briefs (Nos. 2, 3, 5, 6, 7, 11, 13) plus native No. 15 show their veil. With (b), they show plates and No. 15's photograph stays in the opened article. | Withheld in this packet: `shots/briefs-no81-list-1280.jpg` shows the placeholder. |
| **B5** | No. 12 (2026-08-01). The source-image metadata `note` is 81.cn boilerplate, but the file is a Global Times `og:image` whose URL path is dated 2026-06-22, six weeks before the edition. | **(a)** Hold No. 12 on a plate until a human confirms the image belongs to the cited article and the record is corrected through a governed path. **(b)** Use the veil now. | **(a)**. The public caption is built from the source trail and is correct today. `veil.credit` is not rendered, but it would become wrong if anyone ever rendered it. The meta file is in `output/`, so it must not be hand-edited. | Audit in §6 |
| — | Light desk map. This **supersedes** the dark map applied in `07b5672b2b` (2026-10-10, "owner-approved Pacific surfaces"). | Already decided by charter B, image 8. | Phase 4 records the supersession in `DECISION_LOG.md`. | `shots/desks-base-map-1280.jpg` compared with `shots/desks-study-map-1280.jpg` |

These were and remain constraints, not choices:

- **B6:** the curated `chengdu-j20` image is CC BY-SA. It is not used by any Brief study, and it needs share-alike review before use.
- **B7:** the US Indo-Pacific reference is never filled as a sovereign polygon.
- **B8:** home JS is at 11,940 of 12,000 B and archive JS at 9,847 of 10,000 B. Both pages therefore get CSS-only and template-only additions.
- **B10:** a desk-map label-collision probe is a Phase 4 gate.

## 2. Art direction

**Chosen direction: raised paper relief over hydrographic water-lining.**

- Records, the finder, analysis planes, Brief prints and desk plates are paper sheets lifted a few millimetres off the chart-paper ground.
- Geography appears only as real Natural Earth outlines. Each outline is ringed with nested water-lines, the cartographer's coastline ripple, and carries a seat dot.
- Motion is limited to two things: paper settling into place, and lines drawing in.
- The navy band, the crimson analysis signal, the turquoise Briefs and the rust machine labels all keep their current roles.

Each contentious motif was studied two or three ways:

| Motif | Chosen (A) | Alternative (B) | Rejected (C) |
|---|---|---|---|
| Search | A raised field with a three-layer lift, a −82 px overlap into ivory, a press-in button, and a 2/2/80/2 coastal corner. | Offset paper stack, no blur (`home-stack-*`). | Flat white field on ivory. Hard fail. |
| Home records | Cards at 86% width alternating left/right, with a 96 px emblem column (64 px on mobile), chart paper, and a 2 px accent top rule. | Uniform full-width cards with the emblem always on the left. | Text rows. Hard fail. |
| Record emblem | Real NE silhouette with water-lines and the desk seat dot. | Flag chip. | Seal or crest. Fabricated official insignia. |
| Latest analysis | Two raised navy-paper planes with a 3 px crimson top edge, offset vertically by 140 px, over a Singapore Strait relief (NE 1:10m). | A single plane over the existing contour field. | Plain navy slab. Hard fail. |
| Desks behind the record | Desk cards with 84 px silhouettes. Hairlines draw from each card into the headline, and hovering a card thickens its wire. | Inline flag chips. | Inline words only. Hard fail. |
| Brief image | A mounted print card (3:2) with a type tag and a credit line. | Full-bleed banner. | Text-only catalogue. Hard fail. |
| Desk map | Light chart. Desk countries filled navy; declared desks get a quiet dashed fill. Floating paper plates carry flag tabs and leaders. | Light chart with pins and a side list. | Dark map, the current design. The owner asked for light. |
| What each desk reads | One panel per desk: emblem, flag, sources with family glyphs, the full Limits list, and "Locate on the map". | Tabbed panels. Rejected: they hide limits and need JS. | Prose dump. Hard fail. |
| Archive | Modestly raised search, plus a CSS-mask desk glyph on each row link. | Coloured desk chips. Rejected: no colour budget. | — |

Declined: parallax. Charter D3 calls it "optional", but `VISUAL_AND_MOTION_SYSTEM.md` prohibits it, and the design does not need it.

The owner asked for cards that "float out from their country". The plates are **positioned**, not animated: V&M prohibits "floating cards" as motion.

## 3. Requirement matrix

`O` = original owner feedback image and `C` = current published image (both in the packet's `screenshots/`). Study shots are in `evidence/frontend-refinement-phase0-2026-10-10/shots/`.

| Req | Owner requirement (charter B) | O | C | Study evidence | Preserve | Change | Phase |
|---|---|---|---|---|---|---|---|
| 1–2 | Raised search; no dead gaps; keep the bridge | 01, 02 | 02 | `home-{before,after}-finder-{1280,375}`, `home-stack-finder-1280`, `home-forced-finder-1280` | Naval hero and credit; turquoise contour bridge | Finder raised and overlapping the hero edge. F-1 background fix. Hover, focus and press states. | P2 |
| 3 | Records become physical cards L–R–L–R; keep the navy card | 03 | 01, 02 | `home-{before,after}-register-{1280,375}`, `home-{before,after}-selected-*`, `home-stack-register-1280`, `home-forced-register-1280` | Navy "A record to explore" card; dates, original-language headings, status labels | Four records become staggered emblem cards with a scroll settle and an emblem draw | P2 |
| 4 | Latest analysis gets depth and real relief | 04 | 03 | `home-{before,after}-band-{1280,375}` | Dark band, top contour, the Maritime Cooperation photograph and credits (in `.home-brief`) | Raised inner planes and a Strait relief rising into view | P2 |
| 5 | Desks get silhouettes and hairlines into the headline | 05 | 04 | `home-{before,after}-desks-{1280,375}` | Right contour composition | Silhouette cards for the **contributing** desks only (China and Singapore at this snapshot, bound to data); hairline draw | P2 |
| 6 | Briefs hero: island profile and a quiet interaction | 06 | 07 | `briefs-{base,study}-hero-{1280,375}` | Navy hero, type, wave hairlines, metadata, CTA | One Singapore island plate; on CTA hover or focus the land lifts 1.6 px and the water-lines widen 4% | P3 |
| 7 | Every Brief gets an image card (catalogue and article) | 07 | 08 | `briefs-base-list-1280`, `briefs-no81-list-1280`, `briefs-no81-list-mid-1280` | Sculpted margin and contour; all copy; status | Mounted print per Brief under the §1 B3/B4 contract | P3 (rulings in; follows the §1.1 contracts and §1.2 limits) |
| 8 | Desks map: light, desk countries highlighted, plates anchored | 08 | 09 | `desks-{base,study}-map-1280`, `desks-study-map-{900,375}`, `desks-study-focus-sg-1280` | Projection, coordinates, anchors, counts, statuses, chips, navigation, mobile register | Light palette; status-toned fills; flagged plates; hover/focus lights the matching leader and country | P4 |
| 9 | What each desk reads: graphic panels, nothing truncated | 09 | 10 | `desks-{base,study}-reads-1280`, `desks-study-reads-375` | Every limitation, verbatim from the registry | Panel per desk, with sources and run status bound to `source_health_report` | P4 |
| 2b | Archive: modest elevation and desk markers | — | 05, 06 | `archive-{base,study}-{top,rows}-1280`, `archive-study-{top,rows}-375` | `title_english or title_original` (Chinese stays); "Awaiting screening"; "Not selected for analysis" | Raised search panel; CSS-only desk glyph on 50 of 50 rows | P2b |

**Defer:** everything in the Change column is deferred to the phase listed. Phase 0 changes nothing in production.

All hard-fail items from charter F are preserved or addressed in the studies. The one exception is "Briefs without Signal Veil or image cards": that is answered by the B3/B4 contract and the B2 = B ruling: every catalogue card gets a photograph, a Signal Veil or a labelled Editorial plate, and no 81.cn image is added to the catalogue.

## 4. Reference board

| # | Reference | Took | Licence / reuse |
|---|---|---|---|
| R1 | Owner original 02 (old raised search) | Paper edge, offset backing, dimensional button | Owner's own site. **Adapt.** |
| R2 | Josh Comeau, ["Designing beautiful shadows"](https://www.joshwcomeau.com/css/designing-shadows/) | Layered, hue-matched shadows (`--lift-hue:197 45% 15%`) and a single light source | Article. **Adapt the technique; no code copied.** |
| R3 | Better Design `get-ui-principle` (depth and elevation) | Elevation encodes hierarchy, and the pressed state reduces elevation | MCP guidance. **Adapt.** |
| R4 | [Rest of World](https://restofworld.org/) | Photo-led editorial cards with credit lines | © Rest of World. **Reference only; reject reuse.** |
| R5 | AMTI [Island Tracker](https://amti.csis.org/island-tracker/) | Feature-scale island plates in a regional frame | © CSIS. **Adapt the idea; reject reuse.** |
| R6 | Lowy [Pacific Aid Map](https://pacificaidmap.lowyinstitute.org/) / [Asia Power Index](https://power.lowyinstitute.org/) | Light basemap with country emphasis and anchored callouts | © Lowy. **Reference only.** |
| R7 | IPR's own pre-`07b5672b2b` light map (PR #104) | Light land and sea; proven projection | Repo. **Reuse** (`studies/old-map.css`). |
| R8 | [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/) via world-atlas 2.0.2 | All silhouettes, plates and relief | Public domain / ISC. **Reuse.** |
| R9 | [flag-icons 7.3.2](https://github.com/lipis/flag-icons) | 4×3 SVG flags (cn, sg, jp, vn, us) | MIT, © 2013 Panayiotis Lipiridis. **Reuse with notice.** |
| R10 | MDN [`animation-timeline: view()`](https://developer.mozilla.org/en-US/docs/Web/CSS/animation-timeline/view) and Chrome [scroll-driven animations](https://developer.chrome.com/docs/css-ui/scroll-driven-animations) | CSS-only scroll reveals behind `@supports`, no JS | Docs. **Adapt.** Same pattern as `home.css:109-110`. |
| R11 | WCAG 2.2 [2.3.3 Animation from Interactions](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html) (C39 / SCR40) | Reduced-motion kill path | Standard. **Comply.** |
| R12 | [d3-contour](https://github.com/d3/d3-contour) | Considered for generated relief; NE water-lines chosen instead | ISC. **Rejected:** a runtime dependency with no data warrant. |

Also inspected and not adopted: NOAA ETOPO (bathymetry is heavier than the brief needs) and s-ings.com.

**Tools used:**

- `frontend-design` skill
- Better Design MCP
- Firecrawl and WebFetch for the reference sites and docs
- Browser pane on the `pla-watch-site` preview
- Playwright in `.venv` at 375 / 900 / 1280
- `rg` and direct reads

**Unavailable or not used, with substitutes:**

- Mobbin: paywalled. Substitute: Better Design and direct sites.
- Figma and Context7: need auth. Substitute: MDN and Chrome docs read directly.
- `ui-ux-pro-max`, Impeccable and 21st: not invoked. Substitute: the frontend-design skill and the repo's own design docs.
- Tokensave, Serena and Graphify: not used. Substitute: `rg`, `GRAPH_REPORT.md` and file reads.

## 5. Dependency map

Templates in `site/preview/templates/`, CSS and JS in `site/preview/`:

| Surface | Renderer | Templates | CSS / JS | Data | Git history |
|---|---|---|---|---|---|
| Home | `site/render.py` → `generate_preview.py::build()` | `home.html`, `_records.html` (`record_row`), `_terrain.html` | `home.css`, `surfaces.css`, `topography.css`, `reveal.js`, `intro.js` | DB records; desk registry; home Briefs-band veil (DECISION_LOG 2026-10-01) | `07b5672b2b`, `4dbf42c5ca` (#279) |
| Archive | same | `archive.html`, `_records.html` | `archive.css`, `browse.js` (its `card()` is parity-tested against `record_row` in `tests/test_preview_prototype.py`) | Search index, newest 50 server-rendered | `07b5672b2b` |
| Briefs catalogue | same | `briefs` index in `generate_preview.py` | `briefs-catalog.css`, `briefs.css` | `briefs/*.json`, historical sidecars | `534f3b3f1f` (#296), `07b5672b2b` |
| Native Brief | same | `brief.html` | `briefs.css` | `core/brief_collection.py::brief_veil` (line 414) | — |
| Historical Brief | `scripts/rerender_pla_watch.py --no-covers` | `historical-brief.html`, `pla-watch-base.html` (single-owner) | `topography.css` | `scripts/pw_env.py::veil_for_edition` (line 370) → `editorial_veil_for_edition` (216) → `source_veil_for_edition` (302); single-owner file | — |
| Desks | same as Home | `desks.html`, `_desk_map_geo.svg` (generated) | `desk-map.css`, `desk-map.js` (2,681 B), `support.css` | `scripts/desk_map.py` (Miller projection, NE 1:50m), `desks/geography.json`, `core/desk_registry.py`, `scripts/source_health_report.py` | `ffe7edabcc`, `58b32481af`, `07b5672b2b` |
| Specimens | `generate_preview.py --gallery`, never published | `gallery.html` | production CSS | real corpus data | — |

## 6. Signal Veil and media audit

Method: a fresh read-only run of `tools/veil_coverage.py`, which calls the production resolvers against every historical sidecar and native Brief.

| No. | Kind | Image the edition can use today | Rights basis | Study card |
|---|---|---|---|---|
| 1 | historical | Auto image (`2026-05-10-auto-image-optimized.jpg`) | Roberto Villa Jr., public domain (Wikimedia) | Photograph |
| 2, 3, 5, 6, 7, 11, 13 | historical | Source veil from 81.cn; trail URL matches | DECISION_LOG 2026-08-12 / D2. Unlicensed. | Catalogue: Editorial plate (B2 = B). Opened article: unchanged, rights review open (§1.2). Withheld in this packet. |
| 4, 14 | historical | None | — | Editorial plate (China) |
| 8 | historical | Curated `liaoning-j15-recovery`, which beats the 81.cn source veil | Japan MOD Joint Staff, CC BY 4.0. Toned by IPR, so the card needs a change note and a licence link. | Photograph |
| 9 | historical | Curated `scarborough-shoal-iss`, which beats the source veil | NASA ISS Expedition 45, public domain | Photograph |
| 10 | historical | Curated `jin-class-type-094-ssbn`, which beats the source veil | U.S. government (CRS RL33153), public domain | Photograph |
| 12 | historical | Source veil from globaltimes.cn; trail matches; note mismatched | Unresolved (§1.2) | Existing image kept where it already appears (B5 = B). Not added to the catalogue card or any new surface; catalogue gets an Editorial plate until the follow-up clears it. The study's held plate is superseded. |
| 15 | native | `brief_veil`: `maritime-cooperation-2026-veil.jpg` | "Photo: 葛瀚强 / PLA Daily (via 81.cn)", with SHA-256 and provenance | Catalogue: Editorial plate (B2 = B). Opened article and existing home band: unchanged, rights review open. |
| 16, 17 | native | None | — | Editorial plate (China and Singapore) |

**Totals:**

- 17 Briefs: 14 historical and 3 native.
- **True source veils exist for 12:** 11 historical and No. 15.
- Three of those 12 already render a curated licensed photograph instead.
- **No source veil and no curated photo for 5:** Nos. 1, 4, 14, 16 and 17. No. 1 still has its existing public-domain auto image.

The source path returns `credit: meta.get("note","")`. That note is the same 81.cn boilerplate on all 11 historical source-veil records, including No. 12, which comes from globaltimes.cn. Any future render of `veil.credit` must therefore use the trail-built caption helper (P3) instead.

**Hero:** "U.S. Navy / Nathan Burke · 23 November 2015 · Public domain" (`home.html:15`). Unchanged.

## 7. Motion storyboard and animation matrix

The studies use only existing primitives:

- The draw-path is V&M:16, "dashoffset 1→0" with `pathLength=1`, so a stroke draw is not a new exception.
- CSS scroll reveals follow the `profile-settle` precedent at `home.css:109-110` and `surfaces.css:29-30`.

All scroll motion sits inside this gate:

```css
@media (prefers-reduced-motion: no-preference) and (scripting: enabled) {
  @supports (animation-timeline: view()) { … }
}
```

When any part of that gate fails (reduced motion, no JS, a browser without the feature, print), the page shows the finished artwork. There are no loops, so the page's one ambient slot stays free.

| Component | Rest | Hover | Focus-visible | Press | Scroll entry | Reduced motion / no-JS / forced colors |
|---|---|---|---|---|---|---|
| Finder field and button | Lift 1+2+3 (B1a) or stack (B1b) | Button `translateY(-1px)`, 140 ms | 2 px accent outline, offset 2 | `translateY(1px)` plus an inset shadow | — | Static. Forced colors: CanvasText border, no lift. |
| Home record card | Lift 1, accent top rule | `translateY(-2px)`, 180 ms | Outline on the title link; the card lifts through `:focus-within` | — | `rc-in`: ±22 px x and opacity .55→1 over entry 0–70%; emblem `rc-draw` | Finished state, no transform. Forced colors: border. |
| Analysis plane | Raised navy paper, crimson 3 px top edge | — | Link outline (`--focus-band`) | — | Relief `rl-rise` 8 px; water-line draw | Static |
| Desks headline hairlines | Drawn | Matching wire thickens. **P2 change:** swap the study's `stroke-width` transition for an opacity crossfade between two strokes, so only transform and opacity animate. | Same through `:focus-within` | — | `hd-x` scaleX plus `rc-draw` | Wires static; hidden ≤600 px |
| Brief card | Lift 1 | Card −2 px, print image scale 1.03, 220 ms | Same through `:focus-within` | — | — | No transform |
| Briefs hero island | Static plate | CTA hover lifts the land 1.6 px and widens the water-lines 4%, 200 ms | Same on CTA focus | CTA `translateY(1px)` | — | Static; hidden in forced colors |
| Desk plate | Lift 1, flag tab | −2 px; matching leader opacity 1; country darkens (fill, 180 ms) | Same through `:focus-within` | — | — | No transition. Forced colors: border, `Highlight` fill. |
| Scope panel | Lift 1 | — | Link outlines | — | — | Static |
| Archive row marker | Mask glyph | — | — | — | — | CSS only; no JS cost |

Timings stay inside V&M: micro-interactions 140–220 ms, editorial reveals scroll-linked, and every animation under 1.2 s. None bounce, glow, use parallax or follow the cursor.

**The country-fill hover is the one non-transform transition.** It is a colour change of 180 ms. V&M allows colour state changes for micro-interactions, but P4 should confirm this against `DESIGN_SYSTEM.md:383`.

## 8. Asset and rights ledger

| Asset | Source | Licence | Notice / credit | Ships as |
|---|---|---|---|---|
| Country silhouettes and regional plates | Natural Earth 1:50m and 1:10m via world-atlas 2.0.2 (input SHA-256 `04342cdc…9502394` for 50m, `3bc6f1d3…db45f79` for 10m) | Public domain / ISC | "Outlines from Natural Earth" in captions | A generated SVG sprite committed with a source comment, like `_desk_map_geo.svg` |
| Strait and island relief | Same, as nested water-line strokes | Same | Caption: "Natural Earth 1:10m" | Inline symbol or sprite |
| Flags (cn, sg, jp, vn, us) | flag-icons 7.3.2, 4×3 | MIT | LICENSE text travels with the files (`studies/LICENSE-flag-icons.txt`) | `site/assets/flags/*.svg` plus LICENSE |
| Source-family glyphs (newspaper, ministry, agency, journal, portal, feed) | Drawn for IPR (`studies/glyphs/`) | IPR original | — | SVG sprite |
| Home hero | U.S. Navy / Nathan Burke, Wikimedia | Public domain | Existing credit kept | Unchanged |
| Maritime Cooperation photo | PLA Daily / 葛瀚强 via 81.cn | Existing ruling | Existing credit and "Context, not evidence." | Unchanged |
| Brief photos Nos. 1, 8, 9, 10 | Curated manifest | PD / CC BY 4.0 | No. 8 needs "toned by IPR" and a licence link | Existing derivatives |
| 81.cn veils | Source articles | **Unlicensed**; existing ruling only, not newly approved | Trail-built caption | Existing opened-article surfaces only. **Never on the Briefs catalogue** (B2 = B). |
| No. 12 image (globaltimes.cn) | Source trail | **Unresolved** (§1.2) | Trail-built caption; the mismatched `note` is never rendered | Existing surfaces only, pending the governed follow-up |
| Editorial plates | IPR, from Natural Earth outlines | IPR original / public domain | "Editorial plate" tag; "No source photograph" | Catalogue cards without an approved photograph |
| `chengdu-j20` | Curated manifest | CC BY-SA | Share-alike | **Not used** (B6) |

The decorative emblems are geography, not insignia. There are no seals, no agency logos, and no invented coats of arms.

## 9. Accessibility and performance plan

**Budgets.** Caps come from `scripts/verify_frontend_delivery.py`:

- 300 KB HTML+CSS for hub pages (`index.html`, `archive.html`, `desks.html`, and others), 120 KB for any other page
- JS: 12,000 B on home, 10,000 B elsewhere

| Page | HTML+CSS now / cap | JS now / cap | Study overlay | Production rule |
|---|---|---|---|---|
| Home | 68,138 / 300,000 | **11,940 / 12,000** | CSS 12.7 KB; JS 4.9 KB (study only) | **Zero new JS.** Template nodes plus CSS scroll timelines. Emblems via a cached external sprite with `<use>`. Record dates come from the record data; nothing hard-coded. |
| Archive | 132,897 / 300,000 | **9,847 / 10,000** | CSS 10.8 KB (data URIs, study only) | **Zero new JS.** The mask glyph uses an external SVG, not data URIs. `browse.js` parity is unchanged. |
| Desks | 178,566 / 300,000 | 2,681 / 10,000 | CSS 9.8 KB; JS 7.3 KB (study only) | The study's JS moves to build time (`desk_map.py` and the template). `desk-map.js` stays the only script. |
| Briefs catalogue | 102,296 / 300,000 | 3,118 / 10,000 | CSS 5.3 KB; JS 6.9 KB (study only) | Build-time figures. Images lazy-loaded with explicit width and height. |
| Brief article | 76,451 / 120,000 (No. 15) | — | — | One figure. |

Shared primitives go in a new `relief.css`, at most 4 KB, linked only by the pages above. They are **never** added to `styles.css`, which loads on 7,000+ routes.

**Accessibility:**

- Decorative SVG gets `aria-hidden="true" focusable="false"`.
- The map keeps its semantic plate register and keyboard path.
- "Locate on the map" links to `#desk-<slug>`.
- Every hover effect has a `:focus-visible` / `:focus-within` twin.
- Touch never depends on hover.
- Forced colors drops lifts and uses `CanvasText` / `Highlight`.
- Print removes lifts and animation.
- Contrast is checked for the light-map labels and the plate tags.
- Zoom at 200% must cause no overflow.

## 10. Source-level architecture

| Area | Files (P = phase) | Decision |
|---|---|---|
| Primitives | **P1:** new `site/preview/relief.css`, `site/preview/templates/_relief.html` (macros `emblem()`, `flag()`, `glyph()`, `water_lines()`), `gallery.html` specimens | Tokens, tactile states and the reveal gate. Specimens render only in `--gallery`. |
| Geo assets | **P1:** new `scripts/build_geo_assets.py <countries-50m.json> <countries-10m.json>`, built on `desk_map.py`'s decoder and projection. Output: `site/assets/geo/emblems.svg` plus a JSON receipt. | Deterministic. The study builder already reproduces `_desk_map_geo.svg` byte for byte and rebuilds `emblems.json` identically. |
| Flags and glyphs | **P1:** `site/assets/flags/` with LICENSE; `site/assets/glyphs/sources.svg` | Static and vendored. |
| Home | **P2:** `home.html`, `_records.html` (home card variant only), `home.css` | F-1: `surfaces.css:5` `[data-surface] main#main>.wrap{background:transparent}` is specificity (1,2,1) and beats `.home-finder`. Fix it in `home.css` with `[data-surface] main#main>.wrap.home-finder` (1,3,1), which wins regardless of load order. `home.css` already loads after `surfaces.css` (`base.html:35-36`). Leave `surfaces.css` untouched. Desk wires bind to desks that publish records. |
| Archive | **P2b:** `archive.css`, plus an `_records.html` data attribute only if needed | Leave the `record_row` / `browse.js card()` parity test untouched, or update both sides together. |
| Briefs | **P3:** caption helper in `pw_env.py` (**single owner**), `brief_veil`, `brief.html`, `historical-brief.html`, catalogue template, `briefs-catalog.css` | One image-card contract with four kinds: veil / photograph / plate / held. No sidecar writes. The hero island is bound to the lead Brief's desks. |
| Desks | **P4:** `desk_map.py` (light tones and plate placements), `desks/geography.json` (Japan wide placement `--wt:4.5%`, leader `797.0,227.1 960.0,64.1`, ocean label offset), `desks.html` (move the note and context out of `.deskmap-stage`), `desk-map.css`, `support.css` | Source run status bound to `source_health_report --json`. The study shows manifest state only. Limits rendered verbatim. |

## 11. Risk and dependency register

| Risk | Impact | Mitigation |
|---|---|---|
| Elevation spreads past the six B1 surfaces | Breach of the §5 exception | Three named tokens only; a P1 test fails on any other use |
| Home and archive JS near their caps | A budget fail | CSS and template only; the verifier is a gate |
| Scroll timelines unsupported in some browsers | No reveal | `@supports` shows the finished state |
| Desk-map label collisions at new widths | Unreadable map | Probe at 375 / 768 / 900 / 1100 / 1280 (labelHits, overlaps) as a gate |
| Flag red read as analysis crimson | Signal confusion | B9; status stays on the plate's top rule |
| 81.cn reuse on a new surface | Rights exposure | B2 = B: plates on the catalogue; opened-article treatment preserved, not extended |
| Opened-article 81.cn rights unsettled | Rights exposure | Rights review continues outside this programme; no frontend phase widens use |
| No. 12 attribution unresolved | False attribution | Image kept only where it is today; mismatched note never rendered; governed follow-up for metadata correction and image-to-article confirmation |
| Study screenshots treated as approved | Unreviewed design ships | Visual sign-off is a separate gate before P2 |
| `pw_env.py`, `base.html`, `pla-watch-base.html` single-owner | Edit collisions | One writer per PR |
| Shared CSS bloat across 7k routes | Performance | Page-scoped `relief.css` |
| Light map reverses an owner-approved dark map | Governance | DECISION_LOG entry in P4 |
| Desk status drift | Untruthful UI | Bind to the registry and run health; no hard-coded copy |

## 12. PR packages

Each package is one PR, rendered, verified and stopped for review. None deploys.

- **P1 Primitives:** `relief.css`, `_relief.html`, the geo, flag and glyph builders and assets, and gallery specimens, with tests. No page changes.
- **P2 Home:** requirements 1–5 and F-1.
- **P2b Archive:** modest search elevation and the row marker.
- **P3 Briefs:** requirements 6–7. Rulings are in; P3 follows the B3/B4 and B2 contracts, keeps No. 12 off new surfaces until its follow-up closes, and does not alter the opened-article 81.cn treatment.
- **P4 Desks:** requirements 8–9, the label probe, the `source_health` binding and the DECISION_LOG entry.
- **P5 Integration:** a full Playwright sweep, all verifiers and budgets, and a release-readiness note. No deploy.

## 13. Phase 1 engineering ticket

**Title:** IPR frontend P1: shared relief, motion and geo primitives (no page redesign).

**Preconditions:**

- B1 and B9 are answered (2026-10-10). B1 = A: three named lift tokens, six surfaces. B9 = A: full-colour flags.
- Branch from **fresh current `main`**, and re-verify the HEAD. The Phase 0 base `6d1c88f87c` is history, not a starting point.
- Record a fresh-main baseline before any change: validator warnings, test results, delivery budgets and output hashes.
- Visual sign-off is not given. P1 builds shared infrastructure and gallery specimens only; it does not redesign a live page.

**Build:**

1. **`site/preview/relief.css`** (≤ 4 KB):
   - Exactly three named lift tokens per B1 = A, used only by the six approved surfaces.
   - `.tactile` button and field states for rest, hover, focus-visible and press.
   - Water-line stroke classes.
   - `@keyframes` `settle`, `draw` and `rise` inside the reduced-motion / scripting / `@supports(animation-timeline:view())` gate.
   - Overrides for forced colors and print.
2. **`site/preview/templates/_relief.html`:** the macros `emblem(slug, seat=True)`, `flag(iso)`, `glyph(family)` and `water_lines(symbol)`. Each emits `aria-hidden="true" focusable="false"` and an external `<use href>`.
3. **`scripts/build_geo_assets.py`:** reuses `scripts/desk_map.py`'s decoder and Miller projection.
   - Inputs: world-atlas 2.0.2 `countries-50m.json` and `countries-10m.json`, passed as arguments and never fetched.
   - Writes `site/assets/geo/emblems.svg` (china, singapore, japan, vietnam, hawaii seat, strait, regional plate) and `emblems.receipt.json` (input SHA-256, tolerances, licence).
4. **Vendored assets:**
   - `site/assets/flags/{cn,sg,jp,vn,us}.svg` from flag-icons 7.3.2, with its MIT `LICENSE`.
   - `site/assets/glyphs/sources.svg` from the six IPR-drawn source-family glyphs.
5. **`gallery.html` specimens:** a raised finder, a record card with an emblem, a desk plate with a flag, a scope-panel header and a Brief print card. All use real corpus data and render only with `--gallery`.
6. **`tests/test_relief_primitives.py`:**
   - Builder determinism (two runs give identical bytes).
   - The receipt matches the inputs.
   - LICENSE present.
   - Lift tokens appear only in the six approved surface selectors.
   - Macros are aria-hidden.
   - `relief.css` has reduced-motion, forced-colors and print blocks, and no start state outside the gate.
   - No `relief.css` link from `base.html` / `styles.css`.

**Gates:**

- `.venv/bin/python scripts/validate_output.py` passes with **no unexplained new warnings or failures against the fresh-main baseline**. Phase 0 saw 10 governed warnings; that number is a reference, not a fixed gate.
- No unexplained output drift and no budget regressions against the same baseline.
- Make a disposable build: `.venv/bin/python site/preview/generate_preview.py --out <scratch>/candidate --snapshot-from-corpus --gallery`.
- `.venv/bin/python scripts/verify_frontend_delivery.py --root <scratch>/candidate --receipt <scratch>/delivery.json` must report no new budget failures.
- `.venv/bin/python scripts/verify_frontend_integrity.py --public <scratch>/candidate --receipt <scratch>/integrity.json` must pass.
- `scripts/verify_expressive_frontend.py --before <baseline URL> --after <candidate URL> --evidence <dir>` serves as browser evidence.
- `verify_frontend_candidate.py` and `verify_briefs_catalog.py` apply to P2–P5, not P1.
- Production `index.html`, `archive.html`, `desks.html` and briefs pages are **byte-identical** before and after.
- Gallery screenshots in Playwright at 375 / 768 / 1280 cover reduced motion, forced colors and no-JS.
- `pytest tests/test_relief_primitives.py tests/test_preview_prototype.py tests/test_desk_map.py` passes.

**Out of scope:**

- page redesigns
- `pw_env.py`
- Briefs images
- the desk-map palette
- translation
- `output/` regeneration in commits
- deployment

## 14. Optional, out of scope: title translation

Chinese archive titles fall back through `title_english or title_original`. They are correct data, not a frontend defect.

Any translation needs its own governed and costed proposal, covering:

- the model or human route
- the batch size and budget
- a "Machine translation" (rust) label
- storage in a new field, never overwriting `title_original`
- review sampling
- a DECISION_LOG ruling

This packet makes no translation change and recommends none for the frontend phases.

## 15. Tests and receipts

- **Validator:** `scripts/validate_output.py` exited 0 with "Validation passed (10 warning(s))", the governed baseline. Saved as `reports/validate-output-baseline.txt`.
- **Capture reports:** `reports/*.json` for home, Briefs, desks, archive and probe. Every capture has `errors: []`.
- **Desks probe** at 1280, 900 and 375:
  - labelHits [], overflow [], overlaps []
  - 5 panels and 20 limit items, all rendered in full
- **Briefs probe:** at 375, 17 cards, 5 plates and no overflow.
- **Archive probe:** 50 of 50 row links marked.
- **Geo assets:** the emblem rebuild is identical, and the 1:50m rebuild equals the committed `_desk_map_geo.svg` (`True`).
- **Excluded from the evidence:** 81.cn / PLA Daily imagery. The 375 px band captures are cropped above the Maritime Cooperation photograph.

## CHECKPOINT

- **Branch:** `claude/ipr-frontend-refinement-review-ead1c5`, based on `6d1c88f87c2f8f04cce0443a9188a14e2679d50c`. Phase 0 is preserved in one documentation-only commit. Not pushed, merged or deployed.
- **Owner rulings:** B1 = A, B9 = A, B3/B4 = A, B2 = B, B5 = B (2026-10-10).
- **Open:** opened-article 81.cn rights review; No. 12 attribution and metadata follow-up; independent visual sign-off.
- **Selected references:** R1, R2, R3, R5 (idea only), R7, R8, R9, R10, R11. R4, R6 and R12 are reference-only or rejected.
- **Art direction:** raised paper relief over hydrographic water-lining.
- **Next action:**
  1. A fresh session runs the §13 P1 ticket from fresh current `main`, using this document, the evidence folder and the 2026-10-10 DECISION_LOG entry. One tested PR with gallery and browser evidence, then stop.
  2. Separately, a narrow follow-up handles the No. 12 metadata correction and image-to-article confirmation.
