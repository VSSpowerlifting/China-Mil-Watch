# DECISION_LOG — China Mil Watch

Newest first. Record decisions that constrain future work.

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
