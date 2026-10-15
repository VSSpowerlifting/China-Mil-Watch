# China archive — original-source research checkpoints (15 October 2026)

**Research status: preliminary assistant source inspection, not human editorial
verification or public admission.** This complements [PR #603](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/603)
(initial candidate stratification), [PR #612](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/612)
(republications and legacy extraction cues), [PR #615](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/615)
(unsigned decision ledger and private preview), and [issue #613](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/613)
(historical Global Times capture repair). All remain separate from the
eventual [public archive release issue #605](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/605).

## Why check the original publication, not just the IPR stored record?

The same source may be a **publisher outlet**, **original issuing agency**,
**reprinting channel**, or **attributor of someone else's claim**. A record on
PLA Daily is not necessarily a statement by the PLA; a Chinese Foreign
Ministry document published there remains a Foreign Ministry statement.
Likewise, a newspaper reprinting a ministry statement is **not independent
corroboration** of the statement's contested assertions.

The archive can legitimately preserve such statements as *official positions*
without ratifying the maritime or military claims they contain.

## Eighteen evidence-bound starting cases

The review record is in
`research/china/original-source-review-2026-10-15.json`, keyed to the
**October 14, 2026, 5,230-record public compact index** and the existing
individual `output/record/{id}.html` pages.

| IPR ID | Original publisher/source looked up | Preliminary observation | Required next move |
|---|---|---|---|
| [#2849](https://indopacificrecord.org/record/2849.html) | [Chinese MFA, 31 July](https://www.fmprc.gov.cn/wjbxw_new/202607/t20260731_11996501.shtml) | The Foreign Ministry's official statement about Philippine maritime baselines around Scarborough Shoal is substantially represented in the captured PLA Daily republication. That supports **official statement identity**, not the statement's underlying legal claims. | Recheck Chinese original/source custody and editorial salience, then consider primary retain |
| [#2391](https://indopacificrecord.org/record/2391.html) | [Chinese MFA, 12 July](https://www.mfa.gov.cn/wjbxw_new/202607/t20260712_11980339.shtml) | The MFA published an extended official declaration about the South China Sea arbitration anniversary; PLA Daily stored a republication. Its numbered structure aligns with the research source. | Recheck completeness, institution, cross-link related statements, then consider primary retain |
| [#2180](https://indopacificrecord.org/record/2180.html) | [Global Times, 6 July](https://www.globaltimes.cn/page/202607/1365233.shtml) | Source page contains actual submarine-launched missile-test coverage, but IPR's historical captured text starts with unrelated article teasers. The scraper gained a later fix (16 September); old captures were not retroactively repaired. | **Hold** until documented correction process |
| [#2265](https://indopacificrecord.org/record/2265.html) | [Global Times, 8 July](https://www.globaltimes.cn/page/202607/1365501.shtml) | Original article covers ship visits during Joint Sea-2026, while IPR's stored body consists of misleading Joint Sea-2025 and other exercise teasers. | **Hold**; source-text restoration would require distinct authorization and old-hash preservation |
| [#4348](https://indopacificrecord.org/record/4348.html) | [Global Times, 18 September](https://www.globaltimes.cn/page/202609/1370832.shtml) | Original publication and IPR body materially align in the reporting of a China Coast Guard–Philippine vessel encounter. Claims about collision responsibility and footage **remain attributed and contested**, not verified operational facts. | Editorial review and counterpart-source context before inclusion |
| [#4346](https://indopacificrecord.org/record/4346.html) | [Global Times original also underlying this China Military Online copy](https://www.globaltimes.cn/page/202609/1370832.shtml) | China Military Online text carries the Global Times byline and has near-identical body wording. This looks like **syndicated republication**, not an independent second account. | Review representative choice; **preserve both outlet URLs** |
| [#170](https://indopacificrecord.org/record/170.html) | [Global Times, 11 May](https://www.globaltimes.cn/page/202605/1360610.shtml) | A substantive Ministry of National Defense spokesperson article exists at the original outlet, while the historical stored text contains unrelated navigation/news teaser excerpts. **This record escaped the initial warning heuristic**—a real false negative, so cue counts cannot be treated as exhaustive. | **Quality hold** and include in heuristic counterexample checks |
| [#419](https://indopacificrecord.org/record/419.html) | [Global Times, 18 May](https://www.globaltimes.cn/page/202605/1361278.shtml) | Original article contains actual Chinese MND comments on military-to-military relations with the United States. The preserved IPR record has **no readable original-text block**. | **Missing-body quality hold**, no fabricated text anchor |
| [#905](https://indopacificrecord.org/record/905.html) | [Global Times, 31 May source-stated date](https://www.globaltimes.cn/page/202605/1362339.shtml) | Original publisher page discusses China–Mongolia Steppe Partner training with Xinhua-sourced media, but IPR stored no readable text body. The source-stated date on IPR may differ from a publisher article or exercise event date and should be adjudicated explicitly. | **Missing-body quality hold**, inspect Xinhua original/rights |

| [#946](https://indopacificrecord.org/record/946.html) | **Original publisher body not independently retrieved** | Historical stored Global Times body begins with an unrelated Japanese-politics teaser despite a China Coast Guard title. **No positive source-body match is claimed.** | **Quality hold**; obtain primary article before source signoff |

Even for #2849/#2391, a manual editorial source check should compare the
entire Chinese original and archived text, confirm date/issuer/wording and
the exact article trail. An assistant research observation is an input to
that review, not its completion.

## Full negative-control calibration, not just the flagged examples

The original historical quality scan inspected **120** Global Times records
collected before the September 16 extractor repair, flagging **111** for
one or more suspicious-text cues. The other **nine** were deliberately held
out as *unflagged controls*. We investigated their preserved bodies against available source material
as a separate editorial **research** check. The exact publisher original
for #792 could not be retrieved, so that case explicitly remains a source
fidelity **unknown**, even though the capture appears substantive. They are not an automated accuracy estimate or owner signoffs.

| Control record | First scanner result | Publisher/body spot check | Preliminary custody outcome |
|---|---|---|---|
| #170 | Unflagged | Publisher [original](https://www.globaltimes.cn/page/202605/1360610.shtml) contains MND/PLA naval aviation material; captured body is two unrelated truncated teasers | Contaminated-text hold |
| #792 | Unflagged | Preserved article coherently discusses the Dutch De Ruyter helicopter incident; independent reporting corroborates the dispute but **direct publisher text could not be retrieved** | **Unverified publisher-text fidelity; hold** |
| #793 | Unflagged | [Publisher](https://www.globaltimes.cn/page/202605/1362170.shtml) carries the MND spokesperson's Air Force One honor guard comments; preserved page contains unrelated snippets | Contaminated-text hold |
| #1246 | Unflagged | [Publisher](https://www.globaltimes.cn/page/202606/1363127.shtml) reports Foreign Ministry Lin Jian's comments on Japan–Philippines maritime negotiations; captured body holds other-article teasers | Contaminated-text hold |
| #1630 | Unflagged | [Publisher](https://www.globaltimes.cn/page/202606/1364038.shtml) details DF-17 footage and reports military-commentator inferences; stored body materially tracks the story | Appears substantive; do not treat inferred specifications as confirmed |
| #1954 | Unflagged | [Publisher](https://www.globaltimes.cn/page/202606/1364766.shtml) reports distinct PLA STC and CCG patrol accounts; captured body holds unrelated marine-science teasers | Contaminated-text hold |
| #2753 | Unflagged | [Publisher](https://www.globaltimes.cn/page/202608/1367303.shtml) reports Defense Minister Dong Jun's anniversary reception speech; stored text has unrelated recommendation snippets | Contaminated-text hold |
| #3180 | Unflagged | [Publisher](https://www.globaltimes.cn/page/202608/1368066.shtml) contains China–Indonesia exercise and DPP reaction framing; captured body repeats CCG/Liaoning teasers | Contaminated-text hold |
| #3181 | Unflagged | [Publisher](https://www.globaltimes.cn/page/202608/1368067.shtml) provides the Chinese/Indonesian frigate exercise narrative; its stored body has the same unrelated CCG/Liaoning snippet cluster as #3180 | Contaminated-text hold |

**Outcome:** seven of nine originally unflagged controls revealed apparent body
contamination, one contained a source-matched substantive body (#1630), while one (#792) had plausible substantive text whose exact publisher original remains unverified. This is a
case-level observation, **not** a general classifier precision or recall
estimate. It also demonstrates that a text extractor can be corrupted in
multiple ways: missing bodies, a single unrelated teaser, or a repeated
short two-teaser rail. The source publisher being relevant does not make
its old captured IPR body accurate.

The quality-audit heuristic now adds a
`short_multi_teaser_capture_review` cue for a pre-fix body shorter than
500 characters with exactly two ellipsis-style truncations. That recovers
the seven observed false negatives **as review candidates only**, while
the nine original control observations remain permanently documented.
It is not a rule for deletion, suppression, retroactive factual correction,
or public selection. A genuine short article containing two ellipses may
still trigger the review cue.

**Next calibration:** obtain a verified set of both flagged and unflagged
source originals, with human fidelity judgments and captured HTML fixtures.
Then inspect whether the remaining short/recommendation-rail heuristics
over-flag true originals and miss additional bad captures. Do not present
the large warning fraction as confirmed extraction failure prevalence.

## Validation contract

Run without database reads, web calls or output changes:

```sh
python3 -m unittest -v tests.test_china_original_source_notes
python3 scripts/audit_china_original_source_notes.py
```

The validator independently checks:

1. The compact index's exact `snapshot`, positional field schema, unique
   source-record IDs and protected published Brief citation IDs.
2. Every case's ID, title, source slug and source-stated date against the
   October 14 compact index; Singapore/non-China cannot enter the China packet.
3. **Missing-body cases** may carry a `null` source-text anchor ONLY when the
   archival `.original-text` section is actually absent, the original
   publisher URL remains preserved, and the case is a mandatory quality hold.
   It cannot be simulated by deleting words from a valid capture or used for
   editorial selection.
4. Each captured URL against its preserved `output/record/{id}.html`
   provenance table and one exact text anchor against the record's
   `.original-text` section. This catches a changing stored capture.
5. Source-research URL form, research date after publication, explicit source
   confidence, next-stage choices, and a mandatory hold for contaminated text.
6. `owner_approved: false`, `publication_enabled: false` and
   `human_original_review_required: true` for every source case.

The validation can prove *the notes still refer to the same stored source
evidence*. It **cannot independently fetch or certify the external publisher
page**, validate the truth of government or newspaper claims, authenticate
the researcher's identity, or create any approved publication manifest.
The reviewed source URLs and observations are inspection leads, not machine
confirmation of real-world military events.

### Workflow boundary

An offline pull-request workflow tests both real archived record HTML and
negative fixtures, protecting the database and output bytes. It never
collects a publisher page, repairs a capture, calls an LLM, generates the
site, exports a human approval, or uploads a review artifact. There is no
UI or production index integration.

## Scaled legacy-capture triage (not a source-correction pass)

`scripts/audit_china_legacy_capture_quality.py` now checks all stored
`global_times_mil` source records whose **preserved collection timestamp precedes
September 16, 2026**, using only the published compact index and local
`output/record/{id}.html` historical captures. The original scraper received
its markup and related-rail correction on September 16. This audit must not be
misreported as evidence that its **current** extraction is defective.

Signals are deliberately narrow, imperfect, and **nonbinding**:

- A **missing/unreadable** historical stored-text block receives its own
  `unreadable_or_missing_stored_text` cue. The original record URL and
  collection timestamp must still be present; no replacement prose is
  invented.
- A very short captured text (fewer than 60 characters), or short article
  body (fewer than 180 characters), merits review; legitimate terse releases
  can qualify.
- Three or more ellipsis-style truncations may indicate unrelated homepage,
  navigation or recommended-article teasers; genuine quotes can qualify too.

**Measured October 14 corpus baseline** (focused CI
[38697717558](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38697717558)):
158 Global Times records exist in the published index. **120** were actually
collected before September 16, **38** on/after. Of the 120, **111** have one
or more heuristic review cues: **80** multiple ellipses, **18**
missing/unreadable text blocks, **18** very-short captures, and **13**
short captures (categories overlap). This is a **review workload measure**,
not an audited defect count. The scan now also returns the **unflagged
control IDs** and small per-cue example-ID sets, allowing both flagged and
unflagged samples to receive direct publisher comparison.

The report returns per-record **review IDs only** plus counts. It cannot
supply a restored article body, determine that text is truly corrupted,
verify a publisher response, calculate reliable fault prevalence from
heuristics alone, or authorize exclusion and corrections. Non-China sources and captures collected on/after September 16 remain
outside this historical diagnosis, **even when their source publication date
is earlier**. If a record lacks a trustworthy collected-at timestamp, the
scan fails closed rather than guessing its extraction vintage. Every source ID and cited Brief trail stays intact.

```sh
python3 -m unittest -v tests.test_china_legacy_capture_quality
python3 scripts/audit_china_legacy_capture_quality.py
python3 scripts/audit_china_legacy_capture_quality.py \
  --out /tmp/ipr-china-legacy-capture-review-20261015.json
```

The optional full review report must be a **new** path outside the repo. The
CI gate performs the same complete historical scan, prints aggregate
metrics, and confirms the live DB and generated output remain byte-unchanged.
This scales issue #613 from three anecdotal cases to a bounded read-only
historical-quality docket, pending manual comparisons with original pages.

## Next substantive editorial work

- Expand first to a bounded sample of screened-out consequential primary
  documents, *plus* analyzed routine controls. Do not select by keyword alone.
- Use recurring-patrol **event dates**, not normalized title equality, to
  distinguish separate operations across months.
- Review secondary source clusters for actual content differences, original
  issuing agency, and rights limitations before proposing representative
  choices.
- Correct old Global Times captures only after approved correction
  protocol: original body/hash and metadata remain recoverable, corrected
  text separately versioned, affected Brief trails reviewed explicitly.
- Only after signed editorial selection and separate guarded release should
  the production archive give selected documents prominence. The unchanged
  corpus, legacy record/article links, chronology, source statistics, and
  full-corpus browse remain first-class research surfaces.
