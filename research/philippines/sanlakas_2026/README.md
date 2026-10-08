# Philippines Desk: Sanlakas 2026 and JPSCC — provisional source-event dossier

**Research status: pending independent human editorial review. No production event, entity, timeline, topic assignment, publication or approval is created by this packet.**

This is a narrowly sourced preparation for Indo-Pacific Record's eventual cross-desk event timelines. The key engineering goal is to separate an event's **actual reported occurrence date** from the **date on which an agency published an article**, while ensuring that multiple posts about one exercise do not appear as unrelated security events.

## Source basis and fixed archival provenance

The dossier is pinned to the October 7 AFP Day-0 historical shadow state:

- State branch: `shadow/ph-afp`, *literal* immutable commit `492001f34ba6176169b6acc96a237f05592a3395`
- Corpus: `state/shadow.db`, Git blob `e42f8f0dde480a99452d89bcfc7ee84b5aa55f13`
- Ledger: run `37631681338-1`, successful scheduled shadow run
- Sources: four original AFP PAO English-language releases, each with preserved original-text SHA-256, API capture SHA-256, and stable AFP article identity

The JSON sidecar `source_event_candidates.json` holds **four distinct source-record references**, **two separate proposed events**, **eleven claim-and-excerpt links**, and **six unresolved editorial warnings**. It does **not** duplicate complete publisher articles or grant republication rights.

### Proposed timeline — source-stated, not independently corroborated

| Reported event date | Provisional occurrence | Preserved AFP record | AFP publication timestamp |
|---|---|---|---|
| September 29, 2026 | **Separate sixth JPSCC coordination meeting** in Malate, Manila; AFP reports signing of a National JPSCC Cyber Plan | `afp:1390` | Sep 30, 12:22 Philippine time |
| September 30, 2026 | **Opening ceremony** for AFP–PNP–PCG 2026 Inter-Agency Exercise; **venue not yet reconciled** (the AFP release has a Camp Aguinaldo dateline) | `afp:1391` | Oct 1, 12:24 Philippine time |
| October 1, 2026 | **Exercise field-training stage** at HNTCEN-NCR, Intramuros, Manila | `afp:1393` | Oct 2, 12:39 Philippine time |
| October 2, 2026 | **Exercise closing ceremony** at Eva Macapagal Super Terminal, Pier 15, Manila | `afp:1394` | Oct 3, 12:42 Philippine time |

The AFP's October 3 closing release describes a **September 30–October 2**, PCG-led exercise named **IAX 02-2026 / Pagsasanay Sanlakas**. AFP reports more than **530 personnel** trained through an earthquake scenario, including search and rescue, humanitarian assistance, triage and maritime casualty evacuation. That reported scope supports treating the three exercise source records as *stages of the same proposed event*. These are AFP publisher claims, not three independent confirmations from AFP, PNP and PCG.

The separate **September 29 JPSCC meeting** involved overlapping AFP–PNP–PCG institutions but is **not** an exercise opening, field stage or closing ceremony. Its reported National JPSCC Cyber Plan and West Philippine Sea security-coordination language warrant an independently traceable occurrence candidate. The fact that the two proposed events share institutional participants is **not sufficient evidence that they should be merged**.

## Entity-reconciliation warning

The two preserved AFP releases spell the PCG commandant's surname differently: **`Galvan`** in `afp:1390` and **`Gavan`** in `afp:1394`, with similar initials and the same stated office. Do **not** silently normalize these publisher strings to one person or assert an identity merge. A later human editor must compare authoritative original-language institutional records and decide which string, if any, is canonical. The discrepancy is tracked as unresolved flag F02.

## External primary-source discovery requiring separate admission

These findings came from **public source discovery**, NOT from new pinned IPR archive captures. They are hypotheses for a future independent reviewer, and they do **not** expand the four-source immutable packet:

- **Opening venue is not settled.** The archived AFP opening article `afp:1391` uses a `CAMP AGUINALDO, Quezon City` dateline and the word *here*. A publicly indexed September 30, 2026 official Philippine Coast Guard announcement instead describes the inauguration of IAX 02-2026 at **PCG National Headquarters**. The present research does not establish whether the AFP dateline identified where the story was prepared or the precise opening-ceremony venue. **Do not geocode the opening stage** without an authenticated first-party source replay. The PCG's separately hosted social announcement is a discovery lead, not preserved evidence (flag F06).
- **Gavan is externally better supported, but the archived discrepancy remains.** The <https://pco.gov.ph/presidential-speech/speech-by-president-ferdinand-r-marcos-jr-at-the-oath-taking-of-the-newly-promoted-philippine-coast-guard-pcg-flag-officers/> from **September 1, 2026** identifies the PCG commandant as **Admiral Ronnie Gil Gavan**. The <https://www.pna.gov.ph/articles/1212144> October 19, 2023 government news report identifies him as **Ronnie Gil Latorilla Gavan**. Neither external page has been independently admitted to the IPR historical archive in this PR. A human reviewer should determine whether the AFP's `Galvan` is a typo; **do not alter `afp:1390` or auto-merge a person entity** (flag F02).
- A public **Philippine Coast Guard** September/October Sanlakas posting and a **Philippine National Police** public announcement are promising independent institutional sources. Their content access, issuance, publication-time precision, archival suitability and republication rights have **not** passed the source-admission process. Do not count a news article that republishes AFP remarks as independent PCG/PNP corroboration.

These checks are substantive lead discovery, not source acceptance, human adjudication, new event facts in the dossier's claim ledger, or a permission to bypass any social platform's access controls.

## How the packet is engineered

The optional read-only verifier uses the **already merged** Day-0 integrity functions from PR #178 rather than creating a new parser, scraper or Git networking path. With the historical orphan-state commit explicitly present in a local Git object database, run:

    python3 scripts/validate_ph_sanlakas_event_packet.py \
      --state-repo /path/to/checkout-containing-actual-AFP-Day0-Git-objects

The verifier independently reconstructs the exact 13-record Day-0 archived source set. It then checks the four named source identities against the pinned original titles, URLs, publisher date strings, full archived body hashes, and original API capture hashes. Each of the eleven short evidence excerpts must occur verbatim in the **correct** preserved article. It rejects source swapping, event ID/date changes, missing evidence, moved JPSCC records, edited hashes and any attempt to turn on topic/classification/publishing approvals.

**Limit:** a successful machine validation proves only *exact archivally present quoted text and stable source identity*. It does not determine whether the AFP's statements are true, whether the excerpt is representative of the full document, or whether separate PNP/PCG confirmations exist. It also does not establish that the source permits republishing its complete original body. The API's observed `X-Robots-Tag: noindex, nofollow` remains relevant to that separate review.

## Editorial next steps (not performed)

A genuinely independent reviewer should read all four complete original AFP sources, including their full raw captured API JSON, then separately check the associated primary-source announcements of the PNP and PCG when lawfully accessible. Verify event-stage chronology, institution roles, venue names and AFP's reported participation count. Resolve the commandant surname discrepancy by reliable source evidence rather than inference. Decide whether the two event hypotheses should be accepted, revised, or rejected, **without conflating topic review with event-identity adjudication**.

Only after those explicit human decisions may these candidate identifiers be considered for a controlled event registry and eventually the Timeline UI. Nothing in this PR updates the deployed site, production `pla_watch.db`, published records, shadow state, `desks/`, or any `record_topics` row.

## Offline tests

    python3 -m unittest tests.test_ph_sanlakas_event_packet -v

The tests use **synthetic archive rows** constructed solely to verify the validator's contracts. They do not assert that the historical state branch is checked out in CI or that the historical source replay was performed during the test. True historical replay requires the separate command above and a locally present immutable state Git commit. Never mark the editorial hypothesis approved because the synthetic tests pass.
