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

## Seven evidence-bound starting cases

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
| [#946](https://indopacificrecord.org/record/946.html) | **Original publisher body not independently retrieved** | Historical stored Global Times body begins with an unrelated Japanese-politics teaser despite a China Coast Guard title. **No positive source-body match is claimed.** | **Quality hold**; obtain primary article before source signoff |

Even for #2849/#2391, a manual editorial source check should compare the
entire Chinese original and archived text, confirm date/issuer/wording and
the exact article trail. An assistant research observation is an input to
that review, not its completion.

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
3. Each captured URL against its preserved `output/record/{id}.html`
   provenance table and one exact text anchor against the record's
   `.original-text` section. This catches a changing stored capture.
4. Source-research URL form, research date after publication, explicit source
   confidence, next-stage choices, and a mandatory hold for contaminated text.
5. `owner_approved: false`, `publication_enabled: false` and
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
