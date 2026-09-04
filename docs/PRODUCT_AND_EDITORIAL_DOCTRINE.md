# Product & Editorial Doctrine — Indo-Pacific Record

Durable. Change only by deliberate decision (record in DECISION_LOG.md).
Design tokens and components live in docs/DESIGN_SYSTEM.md; visual/motion
specs in docs/VISUAL_AND_MOTION_SYSTEM.md. Current operational state lives in
PROJECT_STATE.md and is deliberately not restated here.

## 1. What this publication is

**Indo-Pacific Record** is an independent, source-grounded publication that
preserves official defense and security texts from the Indo-Pacific as
published, and analyzes them in context. Its value is archival preservation of
the original-language record, institutional context, and the explicit
separation of evidence from inference — not story collection.

**Naming.** The public identity is *Indo-Pacific Record*. "China Mil Watch" is
the **retired predecessor name** (renamed 2026-08-27) and is correct only in
historical statements — including on the thirteen editions published under it,
which keep their original masthead. **"The PLA Watch" is current**: it is the
name of the China Desk's analytical series and is not a legacy term.

Two layers, one masthead:

- **The record** — automated preservation and rendering: scraped originals held
  verbatim, model translation/summaries/categorization, model flags. Every
  automatically assembled readout is labeled as pipeline output, never as
  analyst prose.
- **The PLA Watch** — the *analysis*. The China Desk's weekly human-controlled
  editorial brief (Vol. I, numbered editions, week ending Saturday, published
  Sunday). Every claim traces to a source-trail record.

The project publishes through **desks**. A desk's status and public
presentation are declared in `desks/registry.json`; its sources come from its
own manifest. A desk under shadow evaluation is never presented as coverage,
never counted publicly, and never promoted automatically — see
docs/SHADOW_COLLECTION.md.

The identity phrase is "independent, source-grounded monitoring and analysis."
Never "OSINT tool," never "intelligence platform" (decision 2026-07-10). The
publication must feel like a serious analytical journal run by a working
analyst — never an intelligence-agency imitation, a SaaS product, or a
dashboard aesthetic. No intelligence cosplay, and no claim the record does not
support.

## 2. Audiences

1. **Primary — policy professionals and analysts** who cannot monitor official
   Indo-Pacific defense publication in its own languages at speed. They need:
   what mattered, what was routine, what not to overread, with the original
   sources one click away.
2. **Researchers** — durable, citable editions; a source trail with original
   Chinese headlines; methodology they can evaluate.
3. **Journalists** — fast source discovery: the original URL, the Chinese
   headline, the date, the outlet, and honest framing of what it shows.
4. **Students / informed general readers** — terminology (Terms), plain
   explanation of institutions, and the trust ladder in Methodology.
5. **Returning readers** — week-over-week continuity: prev/next editions,
   recurring threads, the watchlist.

Expert density wins ties, but every expert element must carry a plain-English
explainer at first contact (the "model-flagged" pattern: label + one-line
explainer + link to methodology.html#model-flagged).

## 3. Reader journeys (design against these)

| # | Reader | Entry | Needs first | Next action | Known friction |
|---|--------|-------|-------------|-------------|----------------|
| 1 | Policy reader | Homepage | What is this; what mattered this week | Latest PLA Watch edition | Hero→edition band works; keep the band prominent |
| 2 | Researcher | PLA Watch edition (shared link) | Who publishes this; is it credible; sources | Source trail → Methodology → Archive | Edition pages carry identity + sidebar "about"; keep |
| 3 | Journalist | Search / edition | Original Chinese source for a claim | Source-trail record → 81.cn URL | Trail is good; keep title_zh verbatim, exact-URL matched |
| 4 | Student | Terms / edition | What does 战备警巡 mean; context | Term entry → edition where used | Terms is chronological only; categories/relations are future work |
| 5 | Returning reader | PLA Watch index | What changed since last week | Prev/next links, edition list, watchlist | No cross-edition thread visualization yet (roadmap: Continuity Strip) |
| 6 | Skeptic | Methodology | How is this made; what are the limits | Five-layer trust ladder; corrections contact | Strong page; keep limitations explicit |

## 4. Credibility model — the five-layer trust ladder

Documented publicly at methodology.html. Every surface must make clear which
layer the reader is looking at:

1. **Scraped source record** — verbatim Chinese, never edited. The original
   Chinese text is the authoritative record in every case.
2. **Model processing** — translation, summary, categories. Automated, can
   be wrong; labeled as such.
3. **Model flag** — "model-flagged" is a triage cue produced by software,
   not an editorial judgment. Public label for automated classifications is
   always "model-flagged," never "significant," with the concise explainer
   at first contact (decisions 2026-07-10, ratified 2026-07-11). The
   analyst-assigned *edition* badge (Significant/Routine/Pilot) is
   editorial, not automated, and keeps its name.
4. **Analyst judgment** — watchlist, edition framing, what gets weight.
   Human, and labeled human.
5. **The PLA Watch brief** — published analytical prose; every claim traces
   to a trail record.

Editorial-integrity rules (non-negotiable; enforced by
EDITORIAL_QA_CHECKLIST.md and the editorial-integrity-reviewer agent):

- Never invent, retranslate, or fuzzily match Chinese text, translations,
  titles, outlets, dates, units, ranks, or claims. If original wording is
  unavailable, say less.
- Repetition alone is not novelty or escalation. Admissible arguments:
  placement, seniority, terminology shift, source hierarchy.
- Official media shows *messaging*, not intent. "The framing suggests…" not
  "Beijing intends…".
- Historical data gaps are recorded and warned, never fixed by invention.
- Visual design must never distort meaning: no visualization may imply data
  precision, source diversity, or liveness the pipeline does not have.
  Coverage is concentrated in one source, one desk collects into the public
  record, and configured-but-unimplemented sources must be shown as such.
- **Provenance is preserved, never reconstructed.** The original text, its
  canonical URL, its publication date and its institution travel with the
  record. Collection gaps are disclosed as gaps and never backfilled by
  inference or by retro-scraping.
- **Reproducibility is a publication requirement.** Rendered pages are
  regenerated from the database and the sidecar records; nothing is
  hand-edited into `output/`, and any figure on a public surface must be
  derivable from stored data.
- **Access is never taken by force.** No collector defeats an interactive
  challenge, impersonates a browser, or routes around `robots.txt`. An
  institution that wants to refuse this project must be able to recognise it
  and say so. A source we cannot reach honestly is reported as unreachable.

## 5. Page roles and required anatomy

### Homepage (Paper Ledger surface)

Order of communication: identity (masthead + hero) → today's record ledger →
how the record is built (Signal Field) → latest PLA Watch edition (Night Desk
band) → today's daily brief with analyst readout → sidebar (brief stats,
source status, recent model-flagged with explainer) → footer colophon.
The hero must answer "what is this, and why these sources" inside one
viewport. Depth is progressive; no overlong hero.

### PLA Watch edition (Night Desk surface)

The China Desk's analytical series. Editions published before 2026-08-27 carry
the predecessor masthead and keep their addresses; that is a preserved
historical fact, not a naming inconsistency to correct.
Hierarchy: edition identity (No., week ending, badge) → title + dek + byline
→ this week's signal (≤28 words) → coverage snapshot (stats, labeled
model-flagged) → analytical body in the standing sections (opening note →
what stood out → why it matters → what was routine → term to know → what I'm
watching next) → source trail (English title + verbatim 中文 headline + outlet
+ date + URL; flagged items marked) → disclaimer → author block → prev/next.
Evidence (trail, quotes, stats) and analysis (prose, judgments) must remain
visually and semantically distinct: evidence is neutral/ink; analytical
emphasis is the crimson family.

### Signals (Paper Ledger)
A hybrid, in this order: (A) pattern dashboard from the monitoring DB
(volume, categories, source mix — honest about coverage gaps), (B) the
editor's watchlist (explicitly human-maintained, "not predictions"), (C)
methodology-and-limitations digest, (D) how to read this site. It is never a
fake real-time feed; the daily volume chart notes that empty days can be
pipeline gaps.

### Terms (Night Desk)
A running analytical glossary: one term per edition, Chinese + pinyin +
translation + editorial explanation + link to the edition of first use.
Terms are reproduced verbatim from published editions, never re-derived.
Future (roadmap): category grouping and cross-edition "appears in" links —
only from real sidecar data.

### Archives
- Record archive: the searchable corpus record, and **already a compact weekly
  index**. `archive.html` is a short list of weeks that links out to generated
  per-week surfaces, paginated where a week is large. It is not a flat
  all-records page and carries no known weight or grouping defect; the
  measurement and the threshold for revisiting it are in docs/ROADMAP.md.
- PLA Watch archive: a **separate surface** — the issue-anchored edition list,
  with distinct-source counts and an honest limitations footnote. At ~20+
  editions, month grouping is worth reconsidering. Do not conflate this with
  the record archive above; they have different shapes and different budgets.

### Methodology
The credibility centerpiece: pipeline description, five-layer ladder,
role of automation, "what the pipeline is not," limitations (Party-controlled
sources; model error modes), corrections policy, operator identity. Written
in plain prose; never marketing.

## 5a. Edition identity across the rename

The project was renamed on 2026-08-27: *China Mil Watch* became *Indo-Pacific
Record*. The series name, *The PLA Watch*, did not change. One module,
`core/edition_identity.py`, decides which publication published a given edition;
templates and scripts read it and never hard-code a name.

**Editions 1–13 keep the predecessor identity.** An edition is a dated artifact
of record. Re-rendering one must reproduce the page that was published — its
masthead, its citation, its parent links and its stored author information — not
restate it under whatever the project is called today.

**Editions 14 onward are Indo-Pacific Record.** The boundary is the issue number
(`LAST_HISTORICAL_ISSUE = 13`), not the week the edition covers. Edition 14
covers the week ending 2026-08-15, which precedes the rename, but it is
published now: the parent publication of an edition is the one that publishes
it, not the one that existed during the week it describes. A retrospective
edition is exactly the case where those diverge.

**The site is always Indo-Pacific Record.** The series landing page, the
archive, the terms page, navigation, and site-level metadata carry the current
identity even though the archive lists historical editions. That is a property
of the site the reader is on, not of any edition.

**Author identity.** Stored sidecar fields win. Where a sidecar is silent — as
editions 1 and 2 are — the era supplies the default, so a historical page cannot
inherit the current identity by accident. New editions use the identity on the
About page: Creator and Editor of Indo-Pacific Record, studying International
Affairs at George Washington University's Elliott School. The retired "incoming
student" wording survives only inside historical editions.

### Publication timing

`publication_timing` records **when an edition was written**, and is independent
of `edition_type`, which records **what the week held**. Neither may be read off
the other.

| Value | Meaning |
|---|---|
| `regular` | published in its own week. The default; absent means this. |
| `retrospective` | prepared after its week, for an earlier week. |

A retrospective edition carries a visible, restrained `Retrospective edition`
label on the post page and on its index and archive cards, so it cannot be
mistaken for the current week's brief. Historical sidecars predate the field and
remain valid without it; an unrecognised value is refused rather than guessed.

A retrospective edition takes the deterministic abstract-gradient cover: it is
written weeks after its week, so there is no contemporaneous photograph to
fetch, and a curated stock asset would dress a back-dated edition in imagery it
never had. A human may still supply an approved edition-specific image, which
still wins.

**Source concentration is standing methodology**, documented once in
`METHODOLOGY.md` and on the Methodology page — not a disclaimer repeated in
every edition.

## 6. Voice

See style_guide.md for the full editorial voice. Summary: serious but
readable, human, concrete before abstract, willing to call a week routine,
careful about suggests-vs-proves. Banned unless the data explicitly supports
them: unprecedented, historic, largest, first, turning point.
