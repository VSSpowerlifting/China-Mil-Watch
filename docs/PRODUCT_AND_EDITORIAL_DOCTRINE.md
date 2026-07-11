# Product & Editorial Doctrine — China Mil Watch

Durable. Change only by deliberate decision (record in DECISION_LOG.md).
Design tokens and components live in docs/DESIGN_SYSTEM.md; visual/motion
specs in docs/VISUAL_AND_MOTION_SYSTEM.md.

## 1. What this publication is

China Mil Watch is an independent, source-grounded analytical publication
monitoring Mandarin-language Chinese military and security reporting from
official and authoritative PRC sources. Its value is pattern recognition
across the original-language record, institutional context, and explicit
separation of evidence from inference — not story collection.

Two layers, one masthead:

- **China Mil Watch (Daily Brief)** — the *record*. Automated pipeline:
  scraped Chinese originals, model translation/summaries/categorization,
  model flags. The homepage daily readout is assembled automatically and is
  labeled as pipeline output, never as analyst prose.
- **The PLA Watch** — the *analysis*. Weekly human-controlled editorial
  brief (Vol. I, numbered editions, week ending Saturday, published Sunday).
  Every claim traces to a source-trail record.

The identity phrase is "independent Mandarin-source monitoring and analysis
project." Never "OSINT tool," never "intelligence platform" (decision
2026-07-10). The publication must feel like a serious analytical journal run
by a working analyst — never an intelligence-agency imitation, a SaaS
product, or a dashboard aesthetic.

## 2. Audiences

1. **Primary — policy professionals and analysts** who cannot monitor PLA
   Daily in Mandarin at speed. They need: what mattered, what was routine,
   what not to overread, with the original sources one click away.
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
  precision, source diversity, or liveness the pipeline does not have
  (current reality: coverage is overwhelmingly PLA Daily; other outlets are
  "configured / expanding" and must be shown that way).

## 5. Page roles and required anatomy

### Homepage (Paper Ledger surface)
Order of communication: identity (masthead + hero) → today's record ledger →
how the record is built (Signal Field) → latest PLA Watch edition (Night Desk
band) → today's daily brief with analyst readout → sidebar (brief stats,
source status, recent model-flagged with explainer) → footer colophon.
The hero must answer "what is this and why Mandarin sources" inside one
viewport. Depth is progressive; no overlong hero.

### PLA Watch edition (Night Desk surface)
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
- Daily archive: the searchable corpus record. Currently a flat all-articles
  page (~800 KB) — the known IA/performance defect; roadmap ticket T1.
- PLA Watch archive: issue-anchored list with distinct-source counts and an
  honest limitations footnote. At ~20+ editions, add month grouping.

### Methodology
The credibility centerpiece: pipeline description, five-layer ladder,
role of automation, "what the pipeline is not," limitations (Party-controlled
sources; model error modes), corrections policy, operator identity. Written
in plain prose; never marketing.

## 6. Voice

See style_guide.md for the full editorial voice. Summary: serious but
readable, human, concrete before abstract, willing to call a week routine,
careful about suggests-vs-proves. Banned unless the data explicitly supports
them: unprecedented, historic, largest, first, turning point.
