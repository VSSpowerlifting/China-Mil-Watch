# IPR Briefs — C1 editorial quality audit and review standard

**Prepared 2026-10-09 · Status: internal editor working standard (not an enacted doctrine change)**  
**Parent:** [Research program #318](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/318) · **C1 ticket:** [#320](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/320)  
**Inputs inspected:** published native Brief No. 15, `briefs/maritime-cooperation-2026.json`; restored historical Brief No. 14, `output/the-pla-watch/posts/2026-08-15.json`; `EDITORIAL_QA_CHECKLIST.md`; `docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md` §5b; `docs/REGIONAL_EDITORIAL_INTELLIGENCE.md`. Neither canonical sidecar is modified.

## Decision

**Improve source-to-argument review, not length or format.** The two editions already show the central intellectual strength that should be carried forward: a single exercise can produce many publications without furnishing independent corroboration; official claims about operational effectiveness are claims by the participants, not independently measured outcomes. We should standardize how the analyst and editor check those distinctions, without generating a new Research Papers category, extra weekly publication, numerical “insight score,” or an automated source-admission decision.

Keep **one coherent development-based Brief** and one existing numbered series. Private Sunday candidate selection and Dylan's editorial review stay inside the existing #251/#256 and Brief approval architecture. Ben remains the person authorizing each exact editorial version.

## Sample audit: two different publication generations

| Question | No. 14 — historical, retrospective publication | No. 15 — native IPR Brief |
| --- | --- | --- |
| Reader question | What do repeated official headlines concerning the China–Indonesia east-of-Taiwan passage exercise establish? | How do China and Singapore officially describe Maritime Cooperation 2026, including unresolved starting dates? |
| Evidence | Five selected headlines, three outlets and three publication dates; three Global Times full-body captures explicitly flagged as unreliable for substantive claims | Five exact numbered records: Singapore 4466/4472 and China 4164/3924/4102 |
| Critical provenance distinction | Five reports of **one** exercise; Xinhua/MND content republished elsewhere is not independent verification | Singapore states 5–9 September while China's ministry states 3–9; later reports document other stages without resolving the earlier date |
| Proper inference | Repeated **headline/location framing** within the captured record; no coordination or operational-performance conclusion | Different official framing and detailed activity lists; no inference that corresponding actors held opposite strategic positions or proved effectiveness |
| Reproducibility caveat | Incomplete stored Global Times body text constrains what analysis can say; historic sidecar lacks new numeric cross-desk source IDs | Native source trail, desk and original-language fields, plus explicit claim citation arrays, are stronger mechanically but still require human reading |
| Example caution | A copied official story appearing across outlets is not separate confirmation | Ministries' asserted benefits and sea-phase reports are not verified performance measures |

This comparison is **editorial**, not a rerun of published approval or comprehensive original-source verification. The published historical article and No. 15 remain fixed; no corrections are proposed or implied.

## Private editorial return card — six practical questions

Writers should complete this *while drafting* and editors should use it only for claims material to the thesis. Store it in the internal review packet or human review notes, **not** as public mandatory filler.

1. **Development and thesis.** What specific documentable development anchors this Brief, and what is the most defensible, *contestable* point about how governments describe or respond to it? If the angle is “a lot was published,” reconsider the theme.
2. **Exact cited evidence.** For each high-stakes clause (date, institution, unit, comparison, quotation), what specific source ID and original wording support it? Quote only as the governing rights allow. A numeric ID is not enough if the stored body is incomplete, screened out without review, shadow-only, or from an unapproved source.
3. **Publisher lineage.** Are two records independent issuers, copies of the same article, or separate stages of the same event? Counting several titles does not establish several events or independently corroborated accounts.
4. **Alternative and contrary reading.** What is the strongest reasonable interpretation of the same evidence that would weaken our thesis? Consider source selection, differences in the *genre of the releases*, and the possibility that governments discuss different slices of one event rather than contradict each other.
5. **Evidence boundary.** Is a claim about what an institution *said*, what *occurred*, or *why it happened*? Event occurrence, operational effectiveness and intent demand evidence beyond publicity. Are collection gaps, pending screening and source permissions visible?
6. **Next verification.** What document or concrete later observation would support, revise or defeat the interpretation? This becomes the “what I’m watching” section only if an answer is specific, not merely “monitor developments.”

**Return format (internal, optional):** 
`Thesis -> 1–3 pivotal claims -> exact source ID(s)/desk -> interpretation/alternative -> unresolved gap -> editor disposition`.

A packet can state **“no defensible lead; abstain”** rather than constructing a weak theme. Multiple desks are not compulsory for a single-desk exception; the existing exception and source admission gates still apply.

## Worked example: No. 15, without altering the published Brief

- **Proposed claim to challenge:** "China and Singapore disagree about the start date of Maritime Cooperation 2026."
- **Source basis:** Singapore MINDEF records 4466/4472 report 5–9 September; China MOD record 4164 reports 3–9 September; PLA Daily 3924/4102 refer to preparatory meetings and the opening.
- **Better analytical statement:** "The ministries **report different starting boundaries**. These records do not explain whether the earlier date counts preparation differently, so IPR cannot determine a single shared official start date from these sources."
- **Alternative reading to record:** The reported time windows may use different definitions; difference does not itself demonstrate factual deception, operational disagreement or conflicting policy intent.
- **Reviewer gate:** Exact original-language record citations, classification of planned vs retrospectively reported activity, human interpretation of Chinese terms, approved source-use permissions. The copy is already published; this is an illustrative review card, **not a newly approved amendment**.

## Worked abstention example

A weekly inventory finds five article titles mentioning one exercise, two of them copies of another publisher, one with a malformed body capture, and one from a shadow source not admitted for public use. It cannot substantiate a multi-issuer trend or strategic shift. **No public Brief should assert escalation merely because five titles exist.** The private slate may record the candidate as a lead with holds, pick a different documented development, or abstain.

## Split mechanical tests from judgment

**Already objectively enforceable:** allowed schema, live/source identity, exact record references, per-desk citation to cross-desk comparison, distinct event/source dates, stale approval digests, draft exclusion, URL/parity checks, original-language attribution, known gaps recorded. Use the existing `scripts/author_brief.py`, `core/brief_contract.py`, `scripts/validate_output.py`, and Sunday evidence inventory. Do not reimplement them here.

**Potential incremental mechanical checks, only after separate engineering authorization:** detect reused IDs incorrectly presented as multiple distinct events; report missing/ambiguous publisher lineage where canonical metadata proves it; emit a private warning for missing alternative-reading note in a high-stakes comparative review *without blocking publication*. Any such check must be proven against synthetic fixtures and exact existing source contracts before inclusion.

**Never fake-automate:** significance, novelty, strength of alternatives, correctness of paraphrases, unstated strategic intent, and whether a human analyst is persuaded. Model heuristics can propose review questions but cannot self-certify credibility, approve a screened-out publisher record or publish a Brief.

## Roles and work order

- **Research/author:** read the source original, formulate and falsify the thesis, attach exact source references and caveats.
- **Editorial reviewer (Dylan, when acting in the role):** challenge unsupported claims, publisher lineage, alternative readings and readability; return a targeted correction list without granting approval.
- **Editor-in-chief (Benjamin Yang):** approve *the exact final manuscript/source trail* and its published state under the existing numbered Brief contract.
- **Automated checks:** validate fields and provable relationships only; a green build is not a finding of editorial truth.

**C1 completion condition:** the editor can apply this six-question return card to the next private Sunday candidate without changing old issues, modifying a pipeline or generating a new publication. No further code is essential unless an observed repeatable mechanical failure warrants a narrowly scoped C2 ticket. In particular, do not make the return card another mandatory public prose section.

## Risks and evidence limitations

The historical sidecar is not structurally interchangeable with the modern native Brief schema. No false parity test is made across both formats, and no new metadata is retrofitted to historical pages. This is a *two-edition illustrative editorial audit*, not a claim to have sampled or re-reviewed every published IPR Brief. Its principal evidence is the existing, already-reviewed publication text and declared source trail, not independent publisher-site retesting.

**No changes authorized:** Sunday writer cadence and model budget, Dylan's SMTP controls, approval/numbering, `output/`, `pla_watch.db`, any `briefs/*.json`, or regional topic/timeline/dossier approval status.
