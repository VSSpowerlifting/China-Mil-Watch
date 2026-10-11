# Phase 3A — Briefs media eligibility and provenance audit

**Status:** scoped implementation preflight, not new image or publication permission. 2026-10-11. Binding source: `docs/FRONTEND_REFINEMENT_PHASE0_2026-10-10.md` (B2, B3/B4, B5, §6). This work neither edits `output/` nor adds photographs to a new public surface. Catalogue redesign and article-media changes are separate reviewed phases.

## Verified against the repository

The 14 tracked historical issue sidecars under `output/the-pla-watch/posts/` contain **11 source-image metadata pairs**, all with matching normalized `article_url` in the **same issue's** `source_trail`. The three native Brief sidecars under `briefs/` have one source-photo metadata pair, also matched to its own trail (No. 15). These are *repository metadata associations*, not proof of image ownership, licensing or that the pixels came from that precise article.

The historical resolver `scripts/pw_env.py::source_veil_for_edition` claimed to fail closed on unmatched URLs but previously returned an apparently sourced veil anyway. This phase adds an explicit no-match return and corrects trailing-slash normalization after removal of `www.`. Focused synthetic tests cover mismatches, missing trails, accepted matches, URL normalization, missing derivative, and unchanged curated-photo precedence; another test audits tracked published historical associations. Today all 11 historical metadata pairs match, so the guard is not expected to change existing opened-article images.

## New Briefs catalogue: eligibility by issue

**Photograph candidate** means an independently documented public-domain or licensed image that must additionally pass a new catalogue-route approval, source-credit, and derivative-change check. **Editorial plate** means original IPR geography artwork, clearly marked “Editorial plate” and “No source photograph.” Existing source-linked Signal Veils are **not** newly eligible for the catalogue merely because an article uses them.

| No. | Source publication window | Existing article treatment | New catalogue card |
|---|---|---|---|
| 1 | 2026-05-09 | Curated Roberto Villa Jr. image | **Photograph** — public domain, attribution |
| 2 | 2026-05-16 | 81.cn source veil | **Editorial plate** |
| 3 | 2026-05-23 | 81.cn source veil | **Editorial plate** |
| 4 | 2026-05-30 | Text-led, no source veil | **Editorial plate** |
| 5 | 2026-06-06 | 81.cn source veil | **Editorial plate** |
| 6 | 2026-06-13 | 81.cn source veil | **Editorial plate** |
| 7 | 2026-06-20 | 81.cn source veil | **Editorial plate** |
| 8 | 2026-06-27 | Curated Japan MOD photograph takes precedence | **Photograph** — CC BY 4.0, link, attribution, toned-by-IPR disclosure |
| 9 | 2026-07-04 | Curated NASA/ISS photograph takes precedence | **Photograph** — public domain, source credit |
| 10 | 2026-07-11 | Curated U.S. government/CRS photograph takes precedence | **Photograph** — public domain, source credit |
| 11 | 2026-07-18 | 81.cn source veil | **Editorial plate** |
| 12 | 2026-08-01 | Global Times veil; unresolved B5 rights/image-to-article question | **Editorial plate**; existing image remains only on existing surfaces |
| 13 | 2026-08-08 | 81.cn source veil | **Editorial plate** |
| 14 | 2026-08-15 | Text-led, no source veil | **Editorial plate** |
| 15 | 2026-09-19 (native) | PLA Daily/81.cn source photo/veil | **Editorial plate** |
| 16 | 2026-09-19 (native) | Text-led, no source veil | **Editorial plate** |
| 17 | 2026-09-26 (native) | Text-led, no source veil | **Editorial plate** |

Current B2/B5 preflight outcome: **4 PD/CC photograph candidates pending catalogue-route authorization, 13 editorial plates, zero newly added 81.cn images, and no new No. 12 image use.** None of the candidates is automatically approved for publication at a new route. The existing editorial manifest lists Nos. 8, 9 and 10 for pre-existing routes (such as `pw-post`), not `analysis.html`; No. 1 instead uses `output/the-pla-watch/media/2026-05-10-auto-image.json` (Roberto Villa Jr., public domain). Catalogue implementation must explicitly verify the new-surface route, source, license/credit, derivative and file availability before showing a photograph. Otherwise use an Editorial plate. This table is a preflight ledger, not a runtime permission list.

## Governance and release gates for 3B/3C

1. A matching source-trail URL is necessary to call an opened-article image a Signal Veil, but it never grants *new-surface* image rights. Media eligibility must be evaluated per surface. If image eligibility is absent, fall back to labelled geography, not an unrelated picture.
2. The previous D2/opened-article 81.cn treatment remains unchanged and under rights review; B2 does **not** extend it to new catalogue cards.
3. No. 12 metadata matches a Global Times trail URL, **but its `note` incorrectly credits PLA Daily/81.cn**. Its attribution and the physical image-to-article match are unresolved (B5). Do not render that legacy note, rewrite tracked output by hand, reuse the image on a new surface, or infer a rights clearance from this URL-only audit.
4. Preserve previous article credits/citations, issue identities, predecessor masthead and publication status. Historical articles use `scripts/rerender_pla_watch.py` + `scripts/pw_env.py`; native articles use `core/brief_collection.py` and the native Brief template. These are separate rendering paths, with single-owner file rules.
5. The 3B gate requires a 17/17 catalogue-card audit, source-credit/license receipts, responsive browser captures, no 81.cn catalogue-image requests, reduced-motion/no-JS/forced-colors behavior, output/route parity, and an independent review before merge. 3C article presentation needs its **own** review and owner for `pw_env.py`.

**Limits:** no fresh publisher-site retrieval or independent photo-origin investigation was performed. Exact URL linkage is not proof of attribution or copyright compliance; B5 remains open. The new tests use placeholder derivatives to verify the resolver, not real image pixels.
