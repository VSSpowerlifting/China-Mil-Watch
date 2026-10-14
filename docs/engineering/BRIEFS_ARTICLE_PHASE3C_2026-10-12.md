# Phase 3C — opened Brief articles: presentation and rendering contract

**Status:** implemented as a review candidate on 2026-10-12. Not merged, not deployed, and `output/` has not been regenerated.
- **Baseline:** main `18b57684e6`, which carries Phase 3B (PR #418).
- **Governing documents:**
  - `docs/FRONTEND_REFINEMENT_PHASE0_2026-10-10.md`;
  - `docs/engineering/BRIEFS_MEDIA_ELIGIBILITY_PHASE3A_2026-10-11.md`;
  - `docs/engineering/BRIEFS_CATALOGUE_PHASE3B_2026-10-12.md`.
- **Evidence:** `docs/evidence/briefs-article-3c-2026-10-12/`.

## What changed

All 17 published Briefs open on one of two templates:
- `historical-brief.html` serves the 14 earlier issues, published as *The PLA Watch*;
- `brief.html` serves the 3 native Briefs, Nos. 15–17.

This phase does four things:
- names the kind of each hero image in text;
- gives the two curated photographs their full credit and licence;
- adds a shared previous/next Brief navigation to both templates;
- styles the native author block.

Article text, headings, anchors, citations, provenance, canonical and social metadata, and attribution are unchanged (see "Invariants").

| Layer | File | Role |
|---|---|---|
| Presentation decision | `core/article_media.py` (new) | Says how an image already chosen by the article's own resolvers is shown: `photograph`, `signal-veil`, `plate`, `none`, `preserved`. Grants nothing. |
| Figure | `site/preview/templates/_article_media.html` (new) | `article_figure(m)`: one figure per kind, each labelled in text. |
| Navigation | `site/preview/templates/_article_nav.html` (new) | `issue_nav(prev, next, aria_label, nav_class)`: shared previous/next Brief links. |
| Adjacency | `core/brief_collection.py` | `adjacent_items(collection, slug)` for native Briefs; `display_title()` strips the "The PLA Watch: " series prefix for display only. |
| Historical render | `scripts/historical_brief_render.py` | Passes `article_media` (from the resolved `pw_veil`, the legacy cover and the editorial manifest entry's licence URL) and `adjacent` (from the existing `prev_post`/`next_post`). |
| Native render | `site/preview/generate_preview.py` (+6/−2) | Sets `brief.article_media` and `brief.adjacent`. Nothing else in the generator changes. |
| Templates | `historical-brief.html`, `brief.html` | Held figures keep their old markup in a `preserved` branch. The historical trail wraps "Model-flagged" in the existing evidence span. Both close with `issue_nav`. |
| Style | `site/preview/briefs.css` (+8 lines, additive) | Kind label, issue nav, native author block, TOC stretch under 900 px. Historical pages carry an inline copy of the kind-label and nav rules (see "Publication"). |
| Tests | `tests/test_article_media.py` (new, 22), `tests/test_historical_brief_shell.py` | Contract tests: kinds, preserved ids, credit splitting, Signal Veil caption parity, No. 12, nav order, display titles. |

Files left untouched: `scripts/pw_env.py`, `base.html`, `pla-watch-base.html`, `styles.css`, `core/catalogue_media.py`, every sidecar and the database. The editorial manifest gains two fields on one entry (No. 8's `credit_native` / `credit_native_lang`; see "No. 8 credit language"). No JavaScript was added.

## The media contract

`core/article_media.py` does not decide whether an image may appear. That decision was made upstream by the resolvers that already govern each page:
- for an earlier issue, `pw_env.editorial_veil_for_edition` and `pw_env.source_veil_for_edition`;
- for a native Brief, `brief_collection.brief_photo`.

The module only says how the image those resolvers returned is presented. It never:
- reads `core/catalogue_media.py` or its admissions (that record governs the catalogue only);
- creates or changes a source–image association;
- infers ownership or a licence from an article URL;
- reads a Signal Veil's stored `credit` field. For a source veil that field is a collector's note, not an attribution.

| Kind | Briefs | Caption |
|---|---|---|
| `signal-veil` | Nos. 2, 3, 5, 6, 7, 11, 13 | "**Signal Veil** · " followed by the pre-3C caption, word for word: "Image: [source id → source page] · subject · Context, not evidence." |
| `photograph` | No. 8 (Liaoning J-15 recovery), No. 9 (Scarborough Shoal from the ISS) | The caption runs: "**Photograph** · subject ·" the manifest credit, split on its own " · " separators. Then come the licence (No. 8's "CC BY 4.0" is linked to its deed from the manifest's `license_url`), "via [Wikimedia Commons → file page]", "Toned, cropped and resized by IPR." and "Visual context, not evidence." |
| `preserved` | No. 1, No. 10, No. 12, No. 15 | Figure markup byte-identical to the pre-3C page (see below). |
| `plate` | No. 4, No. 14 (China Desk), No. 16, No. 17 (their own desks) | The catalogue's regional relief (`assets/geo/region.svg`, referenced by `<use>`, never inlined), with the brief's desks picked out. The art is `aria-hidden`; the caption reads "**Editorial plate** · Original IPR artwork. No source photograph. Decorative, not evidence." Outlines are Natural Earth and not boundary claims (`geo.receipt.json`). |
| `none` | none on a production route | Kept for a caller that passes no `root`. |

Every word of a photograph credit comes from the manifest. If a credit names no host, a plain "Source" link to the source page is added, so the source stays one click away. An unrecognised veil kind falls back to `preserved` rather than being guessed at.

**The change note's basis.** It is true of every curated derivative:
- the duo-navy duotone;
- the `MAX_WIDTH = 1600` downscale at fetch (`scripts/fetch_editorial_image.py`);
- the hero's `object-fit: cover` crop.

The catalogue (Phase 3B) uses the same two notes.

### Held and preserved items

| Brief | Why its figure is untouched |
|---|---|
| No. 1 (2026-05-09) | **Legacy edition cover.** Phase 3B held it: identifiable people, and a filename used as alt text. |
| No. 10 (2026-07-11) | **`jin-class-type-094-ssbn`.** Phase 3B held it: the source establishes neither the author nor the drafted alt text ("underway on the surface"). |
| No. 12 (2026-08-01) | **`src-2026-08-01`, B5.** The cited Global Times article and the image's dated path disagree. The stored "Downloaded from PLA Daily / 81.cn" note names the wrong publisher and is **never** rendered as a credit. It did not appear before this phase and does not appear after; a test asserts this. |
| No. 15 (native) | **The brief photograph.** It keeps its Phase 0 §1.2 figure and two-level credit. |

A preserved item is not reclassified, relabelled or recaptioned. Clearing one is a separate, recorded decision.

## Navigation contract

- **Native Briefs.** `adjacent_items` follows the collection's own order, newest first. "Previous Brief" is the next older item and "Next Brief" the next newer one, whichever series each item first appeared in. Links are relative to `briefs/`:
  - a native Brief links its sibling page;
  - an earlier issue links `../the-pla-watch/posts/<date>.html`;
  - an earlier issue not rendered locally links its live address.

  As a result, No. 15's "Previous Brief" is No. 14's historical page, and No. 17 has no "Next Brief".
- **Earlier issues.** They use the same macro. Their targets are the existing `prev_post`/`next_post`, which `rerender_pla_watch.py` takes from the date-sorted sidecars, so every href is unchanged. Each link gains:
  - a "Previous Brief" / "Next Brief" label;
  - a "No. N · date" line;
  - the issue title, with the series prefix stripped for display.
- **The one cross-series bridge.** The newest earlier issue (No. 14) has no next issue, so its "Next Brief" is the published Brief that follows it in the collection: `next_brief_after` builds the editions from the sidecars, loads the collection through its own approval gate (`load_collection`; drafts are never loaded), and asks `brief_after_issue` for the item immediately newer than that issue. Today that is No. 15 (`../../briefs/maritime-cooperation-2026.html`), so No. 14 ↔ No. 15 are reciprocal. If the collection cannot be loaded the link is omitted with a warning, never guessed. Every other historical href is unchanged. The bridge is wired into `rerender_pla_watch.py` and the review builds.
- **Display titles.** The prefix strip is display-only. The canonical title, the `<title>`, the citation and the sidecar keep "The PLA Watch: …".

The nav is a `<nav>` with an `aria-label`: "Adjacent Briefs" on native pages and "Adjacent historical issues" on earlier ones. Links carry `rel="prev"` and `rel="next"`, a 44 px minimum target and visible focus. The two links stack below 600 px, the nav is hidden in print, and it uses `LinkText` in forced colours.

## Article anatomy

- **Hero to reading.** The hero, the curved paper shelf and the reading column are as Phase 0 left them. Under 900 px the table of contents now stretches to the column width instead of shrinking to its content (`.brief-reading-navigation{align-self:stretch}`).
- **Machine flags, preserved records and analysis.** The historical source trail now marks "Model-flagged" with the existing `evidence evidence--model` span, the same marker the analysis page's key uses. The text is unchanged, and so is the edition-level "Model-flagged" count in the issue's metadata list. Historical coverage remains a snapshot under the issue's original heading; native multi-desk analysis keeps its own sections.
- **Native author block.** Styles are added for the template's existing `brief-author-*` classes: label, name in the display face, title, and a bullet-free link row with 44 px targets. No markup changed.
- **Not changed:**
  - headline and dek sizes;
  - line lengths (prose 68ch);
  - the source-trail layout with original-language titles;
  - citations;
  - the signal block.

  These already met the Phase 0 rules, and changing them would have moved invariant fields for no reader benefit.

## Invariants

The tool is `tools/invariants.py`, comparing base and after renders of all 17 routes. The following fields are equal on every route:
- title and meta;
- h1, heading order and ids;
- article paragraphs and language spans;
- images;
- the citation, provenance line and byline;
- the model-flagged count.

Three fields change, as predicted before editing:
- `hrefs` on 17 routes: link text on earlier issues, and new nav links on native Briefs;
- `figcaptions` on 9 routes;
- `external_hrefs` on 1 route: No. 8's licence deed.

## Accessibility and degraded modes

- **Labels.** Every kind is named in text, not by colour or position.
- **Signal Veil.** Its figure keeps `aria-label="Historical visual context, not evidence"`.
- **Plate.** The plate art is `aria-hidden` and not focusable; its visible caption carries the meaning. It is hidden in forced colours and in print, where the caption alone remains.
- **Without JavaScript or motion.** The new parts render identically with JavaScript off, with no motion, and with reduced motion.
- **Forced colours.** The kind label and nav switch to `CanvasText` / `LinkText`.
- **Zoom.** At 200% (a 640 px layout) nothing overflows.
- **Print.** The photograph caption and credit stay visible; the nav is hidden.
- **Collapsed sections.** On native Briefs, a fragment or TOC link into a collapsed `<details>` opens it, in Chromium, Firefox and WebKit.
- **Results.** `receipts/browser-qa.txt` records the runs.

## Budgets and publication

**Size.** Pages stay well inside their budgets:
- historical articles: HTML+CSS 76,916–87,296 B;
- native articles: 79,523–79,751 B;
- `briefs.css` grows from 8,717 B to 10,936 B;
- the plate art (`region.svg`, already shipped by the catalogue) is one shared, cached request;
- JS is unchanged (372 B / 5,322 B).

The caps are 120,000 B HTML+CSS and 10,000 B JS per article (`scripts/verify_frontend_delivery.py`). The delivery verifier reports 0 failures on 7,609 routes.

**Inline CSS on historical pages.** `output/briefs.css` is written only by `site/render.py`, while the historical pages are written by `scripts/rerender_pla_watch.py`. So historical pages carry an inline copy of the kind-label and nav rules: whichever of the two renders is published first, the page is styled correctly. The plate art is different: `assets/geo/region.svg` is written only by `site/render.py` and is not yet in tracked `output/`, so the plates on Nos. 4 and 14 show their caption without the relief until that render lands. Both renders must therefore be published in the same commit. The mixed state (new historical pages with the tracked, pre-3C `briefs.css`) was checked; see the "Mixed state" section of `receipts/browser-qa.txt`. The legacy `.historical-issue-nav` rules were removed from the inline style because the nav now uses the shared classes; the old class is kept on the element.

**After merge.** The owner must run both documented renders before publishing:

```bash
.venv/bin/python scripts/rerender_pla_watch.py --no-covers
.venv/bin/python site/render.py
```

Then run `scripts/validate_output.py` (baseline: 10 governed warnings). This PR does not touch tracked `output/`.

## Limitations and unresolved items

- **Rights.** These items are unchanged by this phase and still open:
  - **81.cn source images behind the seven Signal Veils.** Their reuse rests on the existing cited-source caption, not on a licence.
  - **No. 12 (B5).** Attribution is unresolved; the stored note stays unrendered.
  - **No. 1.** Its alt text is a filename, and identifiable people are shown.
  - **No. 10.** Authorship and alt text are not established.
- **No. 8 credit language (resolved in review).** The caption shows the manifest credit's "統合幕僚監部". The manifest entry now records it as `credit_native` with `credit_native_lang: "ja"`, taken from the Commons file page's own author field ("日本防衛省・統合幕僚監部", `{{ja|…}}` description; checked 2026-10-12); the credit string is unchanged. `credit_parts` wraps only that name in `<span lang="ja">`, and only when it occurs exactly once in the credit. Tests assert the span, that the native name is a substring of the recorded `creator`, and that no photograph caption carries untagged CJK. The catalogue's admission record was not read.
- **Editorial plates: owner visual sign-off open.** Nos. 4, 14, 16 and 17 now carry a labelled editorial plate, meeting Phase 0 requirement 7 (a considered image on every opened Brief) in implementation. The requirement stays **conditional** until the owner signs off the plate's look; no source photograph is admitted and no protected image changed.
- **`_wm` false negatives.** `scripts/fetch_article_image.py:128` `_ASSET_ID_RE` misses ids with a `_wm` suffix (2026-06-27 and 2026-07-18 source images). This was noted during the audit and is not changed here.
- **Test normalisation (temporary).** `tests/test_historical_brief_shell.py` compares the checked-in historical pages with a fresh render. Until the owner's governed rerender, the fresh render is converted back to its exact pre-3C form by counted, context-built replacements (style block, kind label, plate, photograph caption, model-flag span, nav). Every replacement must match exactly once, and a guard test proves that changing a figure's source, alt, duotone, citation, model flag or a held figure still fails. Once the checked-in pages carry the 3C nav class the comparison is strict byte equality, with no normalisation.
- **Render drift unrelated to 3C.** Tracked `output/` already differs from a fresh base render in:
  - `analysis.html`;
  - `briefs-catalog.css`;
  - `sitemap.xml`;
  - `assets/catalogue`;
  - `assets/geo/region.svg` (shipped by the build; the browser test fixture copies it from `site/assets/geo`);
  - `in/`.

  The owner's next full render will carry that drift too.
- **Browser coverage.** Chromium only for screenshots and modes. Forced colours are emulated, and there was no screen-reader run.

## Out of scope

- Arc UI and Planes UI experiments.
- Phase 4 Desks.
- Sitewide integration.
- New photograph admissions or source–image associations.
- Changes to the catalogue's admissions.
- `pw_env.py`.
- The older broad frontend PRs #314 and #323.
