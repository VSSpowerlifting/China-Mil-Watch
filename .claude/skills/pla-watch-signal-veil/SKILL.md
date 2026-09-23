---
name: pla-watch-signal-veil
description: Restore, extend, or review the photographic Signal Veil on The PLA Watch latest-edition card and weekly post. Use for veil imagery, source provenance, cropping, legibility, fallback, and responsive or print QA.
---

# The PLA Watch Signal Veil

Read `CLAUDE.md`, the current `PROJECT_STATE.md`, `docs/DESIGN_SYSTEM.md`, and the image rulings in `DECISION_LOG.md` (2026-07-12 and 2026-08-11/12) before editing. The Signal Veil is an existing system; determine which edition and surface actually lacks it before proposing a replacement.

## Trace the one existing path

- `scripts/pw_env.py`: `veil_for_edition()` chooses a curated, licensed manifest entry, then an image from an article in that edition's exact source trail, then the text-led fallback. `source_veil_for_edition()` requires fetch metadata, a derivative, and an exact URL match. Both `scripts/generate_pla_watch.py` and `scripts/rerender_pla_watch.py` must agree.
- `site/templates/pla-watch-index.html`: `latest_veil` on the latest-issue card. `site/templates/pla-watch-post.html`: `pw_veil` on the article hero. `site/templates/pla-watch-base.html`: shared veil geometry, motion, mobile and print treatment.
- `scripts/fetch_article_image.py` selects an article image; `scripts/validate_output.py` checks provenance. An article's own image must genuinely belong to it. For 81.cn, check that the asset filename embeds the cited article ID. Inspect the image and its page caption. Never borrow an image from a related story or another edition.

## Restore an edition

1. Identify the published latest edition and its exact `source_trail` URLs. Check whether a valid curated entry or source image already exists before fetching anything.
2. Inspect candidate photographs *in their cited article*, their subjects/captions, attribution and page rights. The cited article must be in this edition's trail. Prefer an image that leaves the text column legible at full established veil strength; never compensate for a busy frame with a new source-only opacity rule. Reject uncertain associations and preserve the text-led fallback.
3. Use the existing fetch/derivative/resolver path, not a new hardcoded image URL in Jinja or CSS. If using `fetch_best_image()` for a source image, pass `update_sidecar=False`; the edition sidecar is editorial source data. Keep the image metadata and derivative with the source image. Do not hand-edit generated HTML.
4. Preserve the visible link to the original article and “Context, not evidence” on both surfaces. An image supplies context, not proof of the analytical claim; describe only what is verifiable from its article and caption.
5. Work in an isolated frontend branch. Keep database, workflows, shadow state, and other frontend worktrees untouched. Generate local rendered output only when the ticket authorizes it; never publish or merge as a side effect.

## Verify

- Run `python -m unittest tests.test_pla_watch_veil_contrast tests.test_pla_watch_authoring_identity` and the relevant provenance/renderer tests. Run the output validator when generated output changes; compare to the governed 10-warning baseline.
- Inspect latest card and edition hero at 1280px and 375px, with the actual image composited under text. Check contrast at glyph locations, source-link focus/clickability, overflow, missing-image fallback, reduced motion, no-JS, and print. A whole-box color sample alone is insufficient.
- Compare title, dek, author, dates, counts, badges, links and source trail before/after. Report exact changed files, image/article URL and provenance, test and visual evidence, and any unresolved gate. Do not call the work deployed unless deployment is verified.
