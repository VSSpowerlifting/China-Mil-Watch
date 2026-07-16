# DECISION_LOG — China Mil Watch

Newest first. Record decisions that constrain future work.

## 2026-07-17 — No. 10 final text: revised package adopted, edition badge ruling

1. **The revised draft package (`pla-watch-draft-2026-07-11-revised.zip`,
   Jul 12) is the final approved text of No. 10**, superseding the earlier
   package published first. All seven prose fields (dek, signal, opening
   note, what stood out, why it matters, routine baseline, term explanation,
   watching next) replaced verbatim via the established extraction path;
   round-trip verified against the package. Title, dates, window,
   issue_number, byline, term name, source trail (13/13), media, and covers
   unchanged. No public correction banner: same facts and sources,
   editorial revision only.
2. **The revised package's `edition_label: "Model-flagged"` is rejected.**
   "Model-flagged" is an article-level mechanical triage state;
   the edition classification ("Significant") is the analyst's human
   editorial judgment and stays. The visible model-flagged article count
   remains a separate surface.
3. **The earlier LinkedIn file (article body pasted in error) is replaced**
   by the revised package's 15-line post. Local file only; never posted
   externally by an agent.

## 2026-07-17 — Session recovery, reconciliation onto origin/main, and No. 10 publication

1. **Recovery mechanics.** The 2026-07-12/13/16 uncommitted passes were
   snapshotted onto local-only branch `rescue/unfinished-pla-watch-2026-07-16`
   (three separated WIP commits; `.claude-flow` excluded) and re-applied onto
   `origin/main` in a clean worktree (branch
   `reconcile/unfinished-pla-watch-2026-07-16`). Local `1f0917c` was verified
   by identical patch-id to be the same change as remote `5e92dc4`
   (cherry-picked); it was not merged. Local `main` was left untouched.
   Output was regenerated fresh from the latest remote DB, never carried
   over from the stale snapshot. Rescue WIP commits are safety history only.
2. **No. 10 (week ending 2026-07-11) integrated from the approved draft
   package** (`pla-watch-draft-29148303565.zip`) via
   `backfill_sidecar_bodies.py`: body fields extracted verbatim from the
   analyst-approved HTML (round-trip verified), issue_number 10 assigned,
   author fields normalized from the package's stale
   "Founder & Principal Analyst" to the ruled public identity, trail
   `title_zh` filled by exact URL match (13/13). No prose was composed.
   The edition ships without `executive_readout` / `recurring_threads`
   by analyst instruction, superseding for this edition the earlier
   adopt-from-No. 10 plan.
3. **No. 10 Night Desk veil = `jin-class-type-094-ssbn`**, routed to
   `pw-post` for edition 2026-07-11 only. Grounded: the manifest entry was
   fetched 2026-07-11 and already tied by exact URL to this edition's lead
   SLBM article (81.cn/16472265); PD (U.S. gov via CRS RL33153); duo-navy
   derivative generated deterministically. Its existing home/article
   routes are unchanged; the J-20 homepage atmosphere is unaffected.
4. **`edition_label: "Significant"` kept for No. 10** as the
   analyst-approved edition classification carried by the approved package,
   consistent with Nos. 5, 6, 8, 9. Reader-facing automated counts remain
   "model-flagged" everywhere.

## 2026-07-16 — Homepage atmospheric image decoupled from the model-flagged story

1. **The homepage veil is an atmospheric publication visual, selected only
   by the explicit manifest field `"placement": "homepage-atmosphere"`** —
   never by the daily model, article matching, or flag status. This
   supersedes the veil half of the 2026-07-12 §3 ruling: the model-flagged
   signal card in the hero's right rail still ties to the most recent
   flagged item by exact URL (`_select_home_editorial`, unchanged), but
   the image behind the hero no longer illustrates that story. The two are
   separate layers; the card carries no image, and the image credit never
   carries flag language. Missing/invalid atmospheric entry or derivative
   → text-led hero, card unaffected (`_select_home_atmosphere`).
2. **The homepage atmospheric image is the Chengdu J-20 photograph by
   emperornie** (Flickr photo 44040541250 via Wikimedia Commons, CC BY-SA
   2.0; manifest id `chengdu-j20`), replacing the Jin-class SSBN in that
   role. The Jin-class entry keeps its `home`+`article` routes for the
   signal-card selection and the article-page figure. The duo-paper veil
   derivative is a modified adaptation and remains subject to CC BY-SA
   2.0 including ShareAlike, recorded in the manifest note.
3. **Homepage-only crop mechanics:** `.home-hero .pl-veil` upscales the
   atmospheric image one step past cover (118%) so the manifest
   `mask_focus` (10% 8%) can seat the airframe in the lower-right field;
   mobile (≤900px) resets to cover with its own position (62% 42%,
   `!important` over the inline style). The signal card gains the same
   paper-whisper backing the ledger already had, so its text never sits
   directly on the image. No new motion: the shared veil-in settle is the
   only animation, and reduced-motion/no-JS receive the settled state.

## 2026-07-12 — Production-completion pass: first paint, editorial imagery, prompt hardening

1. **Above-the-fold content never starts at opacity 0.** The reveal system
   keeps `[data-reveal]` for below-fold sections, adds a `data-reveal="art"`
   variant (container always visible; only inner draw-path/ink-node/rule
   primitives animate), and above-fold identity blocks (homepage hero +
   ledger, PW post hero + cover figure, PW index latest-edition module,
   signals header/dashboard, terms head, first archive entries) render
   statically. The observer JS is wrapped in try/catch (failure → `.no-anim`)
   with a post-load in-viewport sweep so no content can stay hidden on
   short pages. Every new component must follow this rule.
2. **Editorial imagery is manifest-only and exact-URL matched.** All
   editorial images come from `site/assets/editorial/manifest.json`
   (curated via `scripts/fetch_editorial_image.py`, which enforces the
   PD/CC0/CC BY/CC BY-SA allowlist from fetch_pla_watch_media). Association
   to stories is by exact article URL or edition date; the manifest's
   category/thread fields are curation context and are deliberately not
   used for automatic matching, so an image can never drift onto the wrong
   story. No match → text-led layout (the designed fallback). Sidecars stay
   canonical: weekly editorial images merge at render time only.
   Every placement carries credit + license + "visual context, not
   evidence" language.
3. **Homepage figure ties only to a model-flagged item** within 7 days of
   the brief date, labeled with the standing "Model-flagged" kicker; the
   ranking language in the Analyst Readout states its mechanical basis
   ("by category priority and relevance; not model-flagged") so automated
   triage is never dressed as editorial judgment.
4. **Byline correction.** Earlier in this 2026-07-12 pass the fallback
   author title in both renderers was changed to "Founder & Principal
   Analyst, China Mil Watch." That change was not analyst-approved and has
   been reverted in `scripts/generate_pla_watch.py` and
   `scripts/rerender_pla_watch.py` before any edition published with it.
   The 2026-07-09 ruling stands: the byline is "Benjamin Yang — Principal
   Analyst, China Mil Watch." The two editions whose sidecars carry no
   `author_title` (2026-05-09, 2026-05-16) render the approved title via
   the fallback constant; no historical sidecar was touched.
5. **Weekly prose mechanics are enforced at draft time, not by rewriting
   history.** PROSE MECHANICS/SYNTHESIS rules added to STYLE_EXTRACT and
   the tool schema; `prose_warnings()` prints non-blocking findings (em
   dashes, banned transitions, stacked "not X but Y") for the human
   reviewer. Editions 1–6 contain 32 such violations and stay as published.
6. **Homepage brief-date demoted to h2** (one h1 per page). The daily
   Analyst Readout now names the record's top-ranked item on no-flag days,
   makes single-source coverage limits explicit, and draws its watch line
   from a fixed per-category table of falsifiable indicators.

## 2026-07-12 — Production visual system: Source-Derived Signal Graphics

Concept A ("Signal Veil") is adopted as the production imagery system on
both surfaces: a duotone crop of the manifest photograph, keyed to the
ground it sits on (paper duotone on Paper Ledger, navy duotone on Night
Desk), shaped by a soft radial mask union so no hard rectangle ever reads
as a conventional photo card. Concept C's Floyd–Steinberg dither is kept as
a secondary "Paper Ledger" fallback, selected per image via the new
optional manifest field `treatment` (`"veil"` default, or `"dither"`).
Concept C's bracketed analyst-mark provenance is used on desktop
(`.src-bracket` / `.nd-src-bracket`); Concept A's compact inline credit
line covers mobile and dense cards. Concept B's tick row (one tick per
Source Trail record, red = model-flagged, with a textual explanation and a
small-screen numeric-only fallback) is retained, but only on Night Desk
surfaces (weekly post hero, index latest-edition module) — Concept B's
photographic strips and ghost edition numeral are rejected as too
decorative for either surface. No conventional photo figure or captioned
image card renders on the homepage hero, article header, weekly hero, or
index module; all four are replaced by the veil/dither system with a
text-led fallback when an image, manifest entry, or derivative is missing.
Derivatives (`{id}-duo-paper.jpg`, `{id}-duo-navy.jpg`, `{id}-dither-ink.png`)
are generated deterministically at build time from the manifest's source
images (Pillow: grayscale + autocontrast, duotone colorize or Floyd–Steinberg
dither; same input produces identical output bytes) via
`scripts/generate_editorial_derivatives.py`, committed to
`site/assets/editorial/derivatives/` and copied to the output tree
alongside the source images. The manifest remains the sole source of
editorial-image metadata; sidecars are untouched. A missing image,
manifest entry, or derivative always falls back to the existing text-led
layout, never a broken reference.

## 2026-07-11 — Analyst decisions: metadata fields, labeling, commit sequence

1. **`executive_readout` adopted** beginning with Edition No. 10: optional
   sidecar field, 2–4 bullets, manually authored by the analyst at publish
   time. It must never be synthesized automatically — not from the week's
   records, not from prior editions. Render-if-present; historical editions
   stay unchanged. (Implements ROADMAP T5.)
2. **`recurring_threads` adopted** for Continuity Strip Phase 2: optional
   sidecar field carrying slugs from the controlled vocabulary in
   docs/VISUAL_AND_MOTION_SYSTEM.md §4. Assign a slug only when the edition
   *materially analyzes* the thread (a standing section engages it) — never
   for passing mentions; typical count 0–3 per edition, and editions with
   none stay empty. New slugs require a DECISION_LOG entry. Historical
   backfill only by re-reading published edition text, never from memory.
3. **"Model-flagged" ratified as the only reader-facing label for automated
   classifications**, with the standing concise explainer ("a triage cue
   produced by software, not an editorial judgment"). Verified 2026-07-11:
   every automated surface already renders "Model-flagged" (daily article
   kicker, archive badge/filter, signals dashboard, weekly counts). The
   analyst-assigned *edition* badge (Significant / Routine / Pilot) is
   editorial, not automated, and is exempt — it keeps its name. Internal
   identifiers (`is_significant`, `n_significant`, CSS class names) are not
   reader-facing and stay unchanged.
4. **Commit sequence approved** for the current working tree: (a) docs +
   Claude operating system → (b) frontend source/templates/scripts →
   (c) regenerated output → (d) validation/cleanup fixes where needed.
   Nothing committed until the analyst reviews the staged plan.

## 2026-07-11 — Project operating system established

Durable doctrine now lives in six docs (product/editorial, design system,
visual & motion, architecture & publishing, agent workflows, roadmap);
CLAUDE.md is a compact pointer file; PROJECT_STATE.md is state-only.
Constraining rulings made in this pass: the dual-surface identity (Paper
Ledger / Night Desk) is confirmed doctrine, with per-surface crimson values
kept deliberately distinct; crimson is reserved for analytical signal;
IBM Plex Mono is capped at one-line metadata; photo-overlay cover PNGs are
demoted to og:image duty in favor of generated SVG Edition Plates (ROADMAP
T2); docs/ROADMAP.md supersedes DESIGN_BACKLOG.md; the skillui-extracted
design skills were retired in place as inaccurate (docs/DESIGN_SYSTEM.md is
authoritative); README/METHODOLOGY/style_guide OSINT phrasing was aligned
with the 2026-07-10 identity decision. New sidecar fields may only be
optional and render-if-present (executive_readout, recurring_threads —
pending analyst adoption).

## 2026-07-10 — Public identity language: Mandarin-source monitoring, not OSINT

The daily site's title, meta descriptions, masthead kicker, footer, and
methodology intro described the project as an "open-source intelligence
tool/pipeline." Replaced everywhere with the project's identity statement:
"independent Mandarin-source monitoring and analysis project tracking Chinese
military and security reporting from official and authoritative PRC sources."
Rationale: matches the stated identity, avoids intelligence cosplay, and drops
the "tool" framing. The "Signal Posture: Elevated/Routine" homepage chip
(driven solely by model flags) was replaced with the literal flag count for
the same reason. Reversal requires an explicit decision, not copyediting.

## 2026-07-10 — "Model-flagged" label extended to the daily site

The 2026-07-10 weekly-page rename ("significant" → "model-flagged") left the
daily surface inconsistent ("Significant" stat, "Analytical signal" kickers,
"Significant only" filter, signals-page labels, readout strings). All
user-visible daily labels now say "model-flagged"; underlying DB fields,
sidecar counts, and stats are untouched. Explainer copy added at each surface
("a triage cue, not an editorial judgment") linking to
methodology.html#model-flagged, which now documents a five-layer ladder:
scraped record → model processing → model flag → analyst judgment → weekly
brief. The methodology explicitly states the homepage daily readout is
assembled automatically (pipeline output, not analyst prose).

## 2026-07-10 — Homepage carries a real latest-edition module

`site/generator.py` now reads the newest weekly sidecar
(`_load_latest_pw_edition`) so the homepage sidebar shows issue number,
week-ending date, title, and dek instead of a generic CTA. Display-only: the
leading "The PLA Watch: " title prefix is stripped for the module; nothing
missing from a sidecar is invented. PLA Watch archive entries anchor on the
issue number and show a distinct-source count derived from the trail;
month grouping deferred at 9 editions.

## 2026-07-10 — n_significant means model-flagged, and is now labeled so

Traced: `n_significant` is computed by `generate_pla_watch.py::compute_stats`
as the count of `is_significant` articles among the week's relevance-passing
DB articles at generation time; `is_significant` itself is set per article by
the LLM categorization step (`analysis/analyzer.py::categorize`, conservative
~1-in-20 rubric). It is a model flag over the monitored week, not editorial
judgment and not a property of the curated source trail. Verified: edition 2's
published count (3) exactly matches the DB's model flags for 2026-05-10→16;
edition 1's count (1) matches the flags analyzed before the pilot was
generated (the 2026-05-07 Wei Fenghe verdict article; three 2026-05-09
articles were flagged at ~14:13 that day, after generation). Ruling applied:
counts are technically valid and stay unchanged in sidecars; the public label
"N significant" was misleading and is renamed to "N model-flagged" in
`pla-watch-post.html` (hero meta, snapshot stat, snapshot bar + legend,
sidebar row), `pla-watch-index.html`, and `pla-watch-archive.html`; weekly
pages rerendered from unchanged sidecars. This coexists with the 2026-07-10
ruling that editions 1–2 had no editorially significant articles: the trail
carries editorial selection, the count reports the pipeline flag. Daily-site
per-article "Significant" badges (backed by displayed model reasoning) were
left as is — separate surface, analyst's call if they should follow.

## 2026-07-10 — Analyst rulings on historical gaps

- `the-pla-watch/linkedin/2026-05-10.txt` is most likely the pilot edition's
  LinkedIn post under its publish date. Left unrenamed.
- Editions 1–2 trails carry no `is_significant` flags because no significant
  articles arose those weeks. The n_significant counts (1, 3) in early
  sidecars are pipeline auto-counts; reconciling them is the analyst's call.
- 2026-06-20's missing "Why It Matters" section stays as published.

## 2026-07-10 — Original Chinese headlines in the source trail

Trail entries carry `title_zh`, sourced only from the daily-monitoring DB's
`title_original` by exact URL match (100% coverage, all 9 editions).
`generate_pla_watch.py` includes it for new editions; the backfill tool fills
history. Chinese text is never composed, retranslated, or fuzzily matched.

## 2026-07-09 — Sidecar JSON is the canonical edition record

Sidecars now store full body text alongside metadata and the source trail.
Rationale: 7 of 9 sidecars had no body fields, so the "safe" re-render script
would have silently replaced published prose with empty pages. Body text was
backfilled by extraction from the published HTML (verified verbatim — a
round-trip check confirmed every paragraph identical) and
`generate_pla_watch.py` writes body fields at publish time.
`rerender_pla_watch.py` refuses empty-body sidecars without
`--allow-empty-body`.

## 2026-07-09 — Both weekly renderers share one Jinja environment

`scripts/pw_env.py` with autoescape ON (the generator previously rendered
unescaped model output) plus `format_date` and `inline_markup` filters.
`inline_markup` whitelists bare `<strong>`/`<em>` because the 2026-05-16
sidecar carries literal emphasis tags; everything else is escaped.

## 2026-07-09 — Date display convention

Reader-facing week-ending labels use "4 July 2026"; ISO `YYYY-MM-DD` is kept
in tabular/meta contexts (covers range, snapshot sub-labels, JSON). Do not
mix within one label.

## 2026-07-09 — Historical data gaps are warnings, never fixed by invention

Missing per-item trail dates (editions 1–3), missing LinkedIn files
(editions 1–3), missing `is_significant` flags (editions 1–2), the pilot's
2-day window, and the 2026-06-20 missing "Why It Matters" section stay as
recorded facts + validator warnings. Only two normalizations were allowed:
`label`→`title` key rename (same string) and pilot trail `source` filled from
its single-entry `sources_seen` (what the published page already displayed).

## 2026-07-09 — Public role title

"Principal Analyst, China Mil Watch" everywhere (scripts, sidecars, pages).
Bio phrase: "principal analyst at China Mil Watch".

## 2026-07-09 — Issue numbering

Chronological No. 1–9 assigned from week-ending order, stored in sidecars,
displayed as "Vol. I · No. N", validated unique + chronological. New editions:
1 + count of earlier sidecars.
