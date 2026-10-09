# Regional Editorial Intelligence — internal slate (Phase 1)

**Status:** internal contract only. No scheduled workflow, model invocation, editor email,
public page, source admission, production archive mutation, or approval path uses this
contract yet. Roadmap: [#251](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/251).

## Product boundary

The Sunday–Saturday **regional editorial review** scans eligible evidence and records
collection gaps. Its task is to propose (ideally) 2–3 substantively distinct themes
and a provisional lead. The **IPR Brief** remains exactly **one source-cited coherent
manuscript**, edited by Dylan and published only after the editor-in-chief's review.
A strong single-country story can be the lead even if other countries supply evidence
that week; cross-desk overlap is *not* presumed causation or coordination. If nothing
meets the bar, a slate must abstain rather than invent a news hook.

Parallel **persistent subject research** (regional topic taxonomy, human-edited
Evidence Timelines, Close Readings, potential Regional Assessments/dossiers)
uses the same underlying source identity and may provide longitudinal context;
it is *not* automatically approved by AI-suggested topic threads. This contract
creates **no** entity registry, taxonomy adjudication, timeline event, or public
journal. Vietnam's National Defence Journal is a *publisher ingestion question*,
not a planned IPR editorial journal.

## Proposed slate structure

`core/regional_editorial_slate.py` enforces:

- `schema = ipr-regional-editorial-slate/1` and exact Sunday–Saturday identity.
- `coverage[]` for every known desk, with one of `reviewable`,
  `no_qualifying_evidence`, `awaiting_validation`, or
  `collector_unavailable`, plus an explicit reason. Use independently
  checked registry `expected_desks` to detect omissions. The absence of a
  qualifying record **never** means the institution was inactive.
- `evidence[]`: exact numeric production IDs versus typed private research
  IDs, desk, upstream trust lane/scope, HTTPS publisher URL, publication date,
  week-new/context role, and **provisional** topic suggestions. No article
  bodies, summaries, model prompts, approval labels, editorial state or
  permission assertions can be attached; extraneous fields refuse.
- `candidates[]`: zero to three grounded theses; each has source IDs,
  rationale for timeliness, counterevidence/alternative interpretation,
  evidence limitations, related provisional topic threads and five
  **nonbinding** 0–5 heuristic scores. At least one cited record must be
  from the reporting week. Mixed sources are permitted; **no quota** demands
  multi-desk representation.
- `provisional_lead` must identify a candidate, or be `null` with an
  explicit abstention reason for an empty slate. Validation does not imply
  any manuscript or publication approval.

Score dimensions start at significance **30%**, primary-source strength **25%**,
analytical novelty **20%**, cross-desk connections **15%**, and timeliness **10%**.
`heuristic_score` is a reference computation (0–5), **not** a sorting gate.
The human editor or writer may recommend a different lead if justified by evidence.
Score inflation, model confidence or number of countries cannot manufacture facts.

### Critical trust boundary

The validator checks only the **form** of offered IDs, not their existence, current
source checksum, institution, legal permission, original-language interpretation or
rights status. Phase 2 must call the independent, fail-closed per-desk collectors,
state attestors and source-use validators **before** constructing or transmitting
any candidate to an external model.

`private_research + private_drafting_candidate` means a separately reviewed,
source-linked synopsis MAY be eligible for internal selection; it means **neither**
production coverage nor consent to copy the publisher's full text, cite the
item in a publicly approved Brief or publish it. Existing Japan/Vietnam typed IDs
must remain separate from the production numeric source-trail IDs.
Do not place private packets in public Action logs or artifacts.

## Implementation sequence

1. **Phase 1 (this PR):** offline schema, validator, synthetic tests and docs
   only. Keep Sunday's existing #237 writer, #240 readiness audit, Dylan SMTP
   switch, Friday compatibility and existing Brief approval gates untouched.
2. **Phase 2:** a read-only full-week inventory from all registered desks,
   validating each source/rights/checksum and showing missing desks honestly.
   Do **not** confuse the existing max-ten writer excerpt with a complete
   regional scan. Human-reviewed candidate research remains separate.
3. **Phase 3:** private AI slate generation, source-grounded alternatives,
   negative evidence and coherent thesis selection. Validate provenance before
   prompt cost; owner-only no-send quality test. Then feed only the lead into
   existing Sunday one-manuscript generation. The current Sunday
   cross-desk-comparison requirement must be reconciled **before** admitting
   high-quality single-desk themes.
4. **Phase 4:** durable source-linked topic threads and dossier/timeline
   handoffs, governed independently from newspaper-like issue cadence.

**Merge gate for Phase 1:** focused offline tests + full exact-head CI and
database/output preservation. **Operational activation requires a separate
explicitly reviewed phase**. No live Sunday or editor email behavior changes.
\n## Phase 2 — read-only weekly evidence inventory (stacked PR)\n\nThe new `core/regional_weekly_inventory.py` reads **all** stored week-dated\nrecords for each **live production-backed** desk from a scratch-copy SQLite\nconnection; it does not apply Sunday's ten-source excerpt cap. The current\nregistered desk roster is authoritative for coverage. Every declared non-live\ndesk also appears, but cannot contribute a numeric production source ID.\n\nThe versioned `ipr-regional-weekly-evidence/1` report includes:\n\n- Every source pointer with numeric ID, institution, publisher URL, date,\n  source language, screening disposition and a SHA-256 digest of the *stored*\n  body representation (English translation or original). This is **not** a\n  checksum attestation against the live publisher. No article prose appears.\n- Record-by-record holds for screened out items, short/incomplete bodies,\n  missing original headlines/languages, URLs needing review, and sources not\n  declared in their owning desk's manifest. Duplicate IDs/URLs or out-of-week\n  records refuse the entire inventory rather than double-count.\n- Country desk coverage statuses, explicit source gaps and the existing\n  independent `sunday_corpus_readiness` result, including partial-week,\n  missing-success-marker and minimum-live-desk gates. `reviewable` means\n  archived source text may be *inspected*, not that publication rights,\n  publisher versions or current collection completeness are verified.\n- A mechanically valid **empty** editorial slate: zero generated themes and\n  no provisional lead. The model has not yet exercised editorial judgment.\n- Optionally, a strictly schema-validated Japan/Vietnam weekly source packet\n  can be represented by **typed IDs and public URLs only** in\n  `pending_private_research`. Nothing from this section becomes eligible\n  slate evidence until the independent exact-state/version/source-use\n  attestation is completed in a separately authorized phase.\n\nUse a local, private, newly created file **outside the repository**:\n\n```bash\npython scripts/regional_weekly_inventory.py \\\n  --week-ending 2026-10-10 --as-of 2026-10-08 \\\n  --review-local-day 2026-10-08 \\\n  --out /tmp/ipr-weekly-inventory-private.json\n```\n\nThis example intentionally yields an incomplete-week hold; the October 11\nSunday success marker must be recorded before the existing real Sunday writer\nmay attempt its normal gated handoff. The optional\n`--private-evidence-directory` is a *research metadata hold* only and must\nnot be mistaken for a publisher-rights grant.\n\nFocused PR CI executes synthetic coverage/hold tests and one real archived\nread-only partial-week rehearsal, with database/output preservation. It never\nuploads the inventory JSON as a public Actions artifact or sends email.\n\n**Still out of scope:** normalized event/entity assertions, validated v2 topic\nassignments, fresh-source re-fetch, shadow publisher attestation, cross-desk\ncausal judgments, theme ranking, model calls, Briefs publication, Dylan\ndelivery or Sunday workflow edits. The next *independent* phase will consume\nthis inventory only after source review and select a provisional thematic slate.\n