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
which keep their original masthead. **Indo-Pacific Record Briefs** is the
continuing collection of analysis (2026-09-23). **"The PLA Watch" is
predecessor attribution**: the name the existing issues (Nos. 1–14) were
published as, which they keep for good. It is not a term to scrub from them,
and no new issue is published under it.

Two layers, one masthead:

- **The record** — automated preservation and rendering: scraped originals held
  verbatim, model translation/summaries/categorization, model flags. Every
  automatically assembled readout is labeled as pipeline output, never as
  analyst prose.
- **Indo-Pacific Record Briefs** — the *analysis*. Numbered, human-controlled
  briefs, each beginning with a concrete development and comparing how the
  relevant institutions officially describe or respond to it (§5b). Every
  claim traces to a source-trail record. The existing issues were published as
  *The PLA Watch*, the China Desk's weekly brief (Vol. I, week ending Saturday,
  published Sunday), and keep that attribution. **Regional Assessments** are a
  separate, longer format (§5c).

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

The page of the existing issues, published as the China Desk's series *The PLA
Watch*; briefs use the same anatomy (§5b). Editions published before 2026-08-27 carry
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

## 5b. Indo-Pacific Record Briefs

Owner direction, 2026-09-23 (`DECISION_LOG.md`). Implemented at source level by
`core/edition_identity.py` (collection and attribution), `core/brief_contract.py`
(the contract and numbering) and `scripts/author_brief.py` (scaffold and check).
The collection and its renderer are `core/brief_collection.py` and
`site/preview/templates/brief.html`: a brief is published at
`briefs/<slug>.html` from a source sidecar in `briefs/<slug>.json`; the Analysis
page is the collection's landing page (no separate `briefs/index.html`); and
`briefs/feed.xml` carries briefs only, while the existing issues keep
`the-pla-watch/feed.xml` and its entry IDs. No real brief exists yet, and none is
published while No. 14 is unreconciled.

**One collection, provenance intact.** *Indo-Pacific Record Briefs* includes the
existing issues and every future issue. Each existing issue keeps its sidecar,
published title, URL, feed entry ID and original *The PLA Watch* attribution —
and editions 1–13 their China Mil Watch masthead (§5a). A unified collection may
display that provenance; it never rewrites it. Membership is not attribution: an
existing issue is *in* the collection and still *published as* The PLA Watch.
No new issue is authored or published as The PLA Watch. A brief says what it is
by recording `collection: "Indo-Pacific Record Briefs"`; a sidecar that looks
like a brief without saying so, or any issue after No. 14 that names no
collection, is refused rather than read as The PLA Watch.

**What a brief is.** It uses the existing article anatomy (§5, edition page) and
begins with a concrete Indo-Pacific development, recorded as `development` with
the trail entries that document it. It compares how the relevant governments or
institutions officially describe or respond to that development. It is not a
digest of a week's volume, and not one desk's round-up.

**Desks.** A brief draws evidence from at least two live desks by default. A
single-desk brief is an explicitly approved exception, recorded in the sidecar
(`single_desk_exception`: who approved it, when, and why). No brief has to
include every desk; a desk in shadow evaluation or access-blocked contributes
nothing; every declared desk contributes at least one trail entry.

**Source trail.** Candidates are selected by the brief's named desks, never by a
query that assumes one corpus. Each entry keeps its record's actual desk and its
source's language: the original title verbatim in `title_original`, its language
in `lang`. Desk and language are independent — the China Desk collects two
English-language sources — so briefs do not use `title_zh`. Screening state is
shown per record, and the model flag only where a record was analyzed.

**Cross-desk claims.** Every claim that compares desks cites at least one trail
entry from each desk it compares. Coordination is never inferred from similar
timing or similar wording: a claim of coordination rests on a cited record that
states it. Coverage is shown per desk and never pooled; desks differ in volume
and in how far their records have been screened.

**Numbers.** Assigned at approval — one more than the highest number already
assigned in the collection — and never reassigned. Not a rank by the week an
issue covers: a retrospective brief approved later takes a later number and
states its week. **No number is assigned while No. 14's publication status is
unreconciled**, because the next number depends on that ruling.

**Titles.** A brief's title does not begin with *The PLA Watch*. The title
format for briefs is decided with their renderer.

## 5c. Regional Assessments — the boundary

A Regional Assessment is a separate, longer editorial format under Indo-Pacific
Record. Only its boundary is defined here; nothing is built for it.

| | Brief | Regional Assessment |
|---|---|---|
| Starts from | one concrete development | a question or pattern across developments |
| Window | the development's week (retrospective allowed, labelled) | a longer, stated period |
| Evidence | trail entries from two or more live desks, or an approved exception | the record across desks and over time; may cite briefs |
| Form | the existing article anatomy | longer, with its own structure |
| Numbering | the collection's single sequence | its own identity; never numbered as a brief |
| Pipeline | `scripts/author_brief.py`, the brief contract, the QA checklist | its own renderer, route and review gate — not built |

A brief that outgrows one development is an Assessment candidate, not a longer
brief. An Assessment keeps the same evidence rules: desk and language preserved,
cross-desk claims cited from each desk, no coordination inferred from timing.

## 6. Voice

See style_guide.md for the full editorial voice. Summary: serious but
readable, human, concrete before abstract, willing to call a week routine,
careful about suggests-vs-proves. Banned unless the data explicitly supports
them: unprecedented, historic, largest, first, turning point.
