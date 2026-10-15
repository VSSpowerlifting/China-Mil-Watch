# Published Brief claim review: proposed No. 12 wording and No. 10 source-trail check

**15 October 2026 · PRIVATE PROPOSAL ONLY · NO OWNER APPROVAL · NO PUBLIC EDIT.**

Related: [China archive curation #605](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/605),
[published source-trail audit PR #626](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/626),
[No. 12 correction review #627](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/627),
and [No. 10 historical record correction #623](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/623).

## No. 12: a narrowly scoped proposed wording change

The [August 1, 2026 issue](https://indopacificrecord.org/the-pla-watch/posts/2026-08-01.html)
includes in its `opening_note` an equipment-disclosure list mentioning
**“the Atlas drone swarm system's live-fire debut”** as part of the days
around Army Day.

The issue cites [Global Times, July 31: armed reconnaissance drones
striking a moving vessel](https://www.globaltimes.cn/page/202607/1367264.shtml).
That original describes the PLA Army's **KVD002** armed reconnaissance
drone, a CCTV documentary, a moving unmanned maritime target, and the
operator switching to **manual guidance** after automatic target-locking
problems. It attributes broader readiness inferences to a commentator.

A separate [CCTV Plus original record on March 25](https://www.cctvplus.com/archive/20260325/8471877.shtml)
specifically identifies **Atlas** as a **Swarm-2** drone system and dates
its full-process demonstration to **March 25, 2026**. The March
demonstration and July KVD002 footage cannot be treated as one August debut.

**Original published excerpt** (exact-match anchor; not currently edited):
`the Atlas drone swarm system's live-fire debut`

**Proposed replacement excerpt** (for owner review, not applied):
`CCTV footage of a KVD002 armed reconnaissance drone striking a moving maritime target`

This keeps the current paragraph's structure and the issue's July 31
publisher citation. It does **not** imply an autonomously guided strike,
a large-scale swarm debut, independent authentication of the CCTV
footage, or any demonstrated wartime combat readiness. Before approval,
an editor should independently check the CCTV original video and decide
whether the sentence should instead be shortened or removed altogether.

A separate **possible** correction notice is saved in
`research/china/brief-claim-review-proposals-2026-10-15.json` with no
date, author signoff, or publication authorization. Whether to amend the
source trail to add the March background evidence is a separate editorial
decision subject to attribution and media rights.

## No. 10: archive machine-summary repair is NOT automatically a Brief edit

The [July 11 issue](https://indopacificrecord.org/the-pla-watch/posts/2026-07-11.html)
already identifies **Joint Sea-2026** and its routine crew exchanges.
But cited historical [IPR record #2265](https://indopacificrecord.org/record/2265.html)
mistakenly interprets unrelated **2025** link teasers as the content of a
July 8, 2026 [Global Times article](https://www.globaltimes.cn/page/202607/1365501.shtml).
The existing record machine summary should eventually be corrected or
visibly caveated through the **preservation-first historical capture
correction process**.

The unsigned packet therefore includes No. 10 as a
`claim_check_only_not_a_proposed_edit` item with
`proposed_exact_text: null` and `possible_correction_notice: null`.
The editor still needs to check source custody and the crew-exchange
sentence, but this avoids falsely labeling a correctly dated Brief as
incorrect because its archive URL is damaged.

## No. 13: earlier Y-20B WS-20 operational chronology

The [August 8 issue](https://indopacificrecord.org/the-pla-watch/posts/2026-08-08.html)
states in its `why_it_matters` that the **Y-20B's first confirmed
operational use with domestic WS-20 engines** is a new achievement and
the engine's operational use had not previously been officially confirmed.

This appears to overstate chronology. The [20 April Global Times
report](https://www.globaltimes.cn/page/202604/1359334.shtml) already
reported the WS-20-powered Y-20B's **first overseas service mission**
carrying home Chinese soldiers' remains from South Korea. [April 22
Xinhua-attributed reporting](https://www.globaltimes.cn/page/202604/1359495.shtml)
further documented that mission. The source cited by No. 13,
[6 August Global Times](https://www.globaltimes.cn/page/202608/1367662.shtml),
concerns CCTV's discussion of **transport/refueling adaptation** and
potential additional roles, not an August first deployment.

**Research qualification:** an official repatriation/airlift mission is
an **operational service use** but is not demonstrated combat employment,
mass fielding or proof that hypothetical bomber/AEW/EW adaptations are
already in service. The Aug. 8 wording requires a source-and-chronology
editorial check, [issue #630](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/630).
The historical first-claim string is exact-matched to the published
issue in the validator. **No replacement is proposed or authorized yet**;
the packet uses `claim_check_only_not_a_proposed_edit`.

## CI and custody guarantees

The review data has **three** issue-linked cases and pins their exact source
record IDs, original source-stated date and title, original publisher URL
and the issue/field/excerpt where review is required. The no-write
validator `scripts/audit_brief_claim_correction_proposals.py` independently
reads existing public corpus-index, recorded HTML and published issue
JSON. It verifies:

- Protected source trails and unique original record identities;
- The **old phrase appears exactly once** in the untouched published
  issue's correct paragraph;
- The original publisher URL is present in both the archived record's
  provenance and issue's source-trail list;
- Research evidence URLs are distinct from authenticated human source
  verification;
- Future collected source records do not auto-extend a correction review;
- Every approval/review flag remains `false`; an automated packet never
  claims that editor or owner has authorized publication;
- The No. 10 and No. 13 claim checks never supply replacement text.

```sh
python3 -m unittest -v tests.test_brief_claim_correction_proposals
python3 scripts/audit_brief_claim_correction_proposals.py

# Optional private report outside the repository, new filename each run:
python3 scripts/audit_brief_claim_correction_proposals.py \
  --private-json /private/tmp/ipr-brief-claim-review-20261015-unused.json
```

The optional report includes the complete **private comparison paragraph**
and source metadata so a reviewer can understand the proposed change.
It is **not** a deployable corrected Brief, not an owner-approved manifest,
and not a postpublication patch. No public `output/`, SQLite database,
source-trail link, recorded HTML or Brief is touched or rewritten. The
focused offline CI exercises this exact private packet only in GitHub
runner scratch, without uploading it as an artifact.

**Release stop:** independently verify the issuer footage and claims,
obtain actual human reviewer and owner approval, preserve issue chronology,
choose exact correction notice wording, and then use a **separate guarded
production release PR**. Merely merging this QA tool could not publish it.
