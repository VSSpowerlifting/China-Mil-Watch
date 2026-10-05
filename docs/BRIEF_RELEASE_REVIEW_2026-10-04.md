# China–Singapore Brief release candidate — 4 October 2026

**Status: prepared and reviewed locally; unapproved, unnumbered, unpublished.**
This record replaces the current-status claims in the recovered October 1
review packet. It does not replace that packet's dated evidence or imply a
human sign-off. No merge, deployment or live publication is claimed.

## Candidate and authorization recovery

Canonical source: `briefs/maritime-cooperation-2026.json`.
Title: **Maritime Cooperation 2026: One Exercise, Two Official Accounts**.
SHA256: `5d5044314674861fd56c522ee572597d090062a9b0ef5cb879bb427fa692e096`.
China and Singapore; retrospective; Routine; reporting window September 3–19,
2026 (Saturday endpoint), with five selected statements dated September 5–14.
The draft byline explicitly says it was prepared for Benjamin Yang and awaits
editor review. Final public byline and approval metadata must reflect his actual
authorization before publication.

Recovered only the draft, source photograph, derivative and provenance from
`codex/first-brief-review-20261001` at `61b96cdce597236036988c4c60fe8f7b15f97f78`,
in the existing `ipr-first-brief-20261001` worktree. That worktree and its other
uncommitted changes were preserved. No historical edition or old cover was
imported. The new release branch is `codex/briefs-release-20261004`, based on
origin/main `37dd981886a32b9f6d85c124a170569cfcb33275`.

The October 3 owner instruction in ChatGPT **Review No 14 Corrections**,
conversation `6ac18364-c1b4-83e9-921a-ffc65b441e68`, at 21:29:08 CDT, says:
“brief looks great. fully see it throguh.” The immediately preceding artifact
was a **fourteen-source** cloud draft, titled **Exercise Maritime Cooperation
2026: One Exercise, Two Institutional Frames**, linked as
`sandbox:/root/pla-watch/briefs/maritime-cooperation-2026-china-singapore.json`.
The accessible conversation supplies the description and link, not its source
bytes; local worktrees/downloads did not contain it. That artifact remains
unrecovered. This five-source host candidate is distinct and does not inherit
the other artifact's approval.

No. 14's correction ruling and merged PR #98 independently cleared its numbering
hold. No. 15 is available; it is not assigned to this draft. The exact remaining
release gate is the human's approval of this candidate, including its public
editor attribution. The next command records actual evidence with
`author_brief.py approve`; no approval date/reference is fabricated here.

## Editorial trace and finished writing

The finding is about published context: MINDEF's opening release places the
exercise within Steadfast's engagements with several partners; its closing
release and China's ministry both emphasize bilateral cooperation and trust.
The policy implication and limits are explicit. The comparison establishes
differences in official accounts, without inferring intent, independent
performance, coordinated messaging or an explanation for September 3.

| Record | Evidence used | Constraint retained |
|---|---|---|
| 4466, MINDEF, September 5 | Zhanjiang; ships; planned shore/sea phases; wider deployment; sea riders; fifth iteration | Official participant account; not an independent performance record |
| 4472, MINDEF, September 9 | Closing dates, activity list, competencies and bilateral trust | Participant assessment, attributed |
| 4164, China's defense ministry, September 14 | September 3–9; activities; fifth iteration; cooperation and regional-stability assertion | Starting date unresolved; 实弹射击 is described as live-fire shooting |
| 3924, PLA Daily, September 6 | September 5 opening; September 4 preparatory meetings | Does not explain the ministry's September 3 date |
| 4102, PLA Daily, September 12 | Five-day exercise ending September 9; replenishment positioning and line handling | No established transfer of fuel or stores |

The read-only editorial-integrity reviewer passed the final prose, companion
copy, source trail, provenance and templates. All five records retain exact
stored originals, outlets, dates, URLs, language and screening states. Chinese
text and stored machine title translations were not rewritten. Machine
translations are labeled and originals remain authoritative. Two Singapore
records still say awaiting screening; human use of those official sources does
not invent software analysis or promote a shadow desk.

The full editorial checklist was applied: title/dek/finding; attributed claims;
cross-desk citations; unresolved date discrepancy; continuity baseline and
limits; Routine as proposed editorial judgment; useful terminology; specific
future evidence; restrained paragraphs; original-language fidelity; no invented
Chinese, attribution or source facts. The LinkedIn companion is expressly a
review draft, with a proposed address, five sources and corrections invitation;
it has not been posted.

Photo provenance remains exact: caption
`9月5日，中国和新加坡两国海军参演官兵代表参加开幕式。葛瀚强摄`,
credit 葛瀚强 / PLA Daily via 81.cn. Original SHA256 is
`657bd02c0b783dae00914a88a37481302ef99894cfebb6a2eda83d968b20e4d8`;
derivative `20363d5218d451f489c1c7ed7eec1ff4693f6056a66a22313b4859ddbf8a5cea`.
The 1200 × 675 photograph is visual context and is not used as evidence of
the exercise's program or results.

## Publication implementation and verification

The existing flow now has readiness and explicit approval commands; it checks
native and predecessor numbering, refuses changed repeat approval, serializes
local assignment and replaces source atomically. Readiness checks complete
prose, numeric citation markers throughout every rendered prose field,
comparison/development references and source state against a read-only corpus
copy. An approved edition retains its evidence snapshot on ordinary renders.
The canonical approval command requires the actual human, date and reference.

Private review uses `site/render.py --review-brief` outside `output/`, with
visible notices, no number/approval, no public canonical, `noindex`, and no
native feed or sitemap. Ordinary rendering excludes this draft. The deploy
validator checks approved article title/number/canonical, home/catalog/feed/
sitemap integration and coverage chronology; it refuses stale draft routes.
No replacement collection workflow or model API is needed.

Final focused suite: **86 tests passed**, including twelve publication-flow
regressions. The full offline-suite result is recorded in the PR validation
evidence when complete. The initial full run found one outdated Analysis copy
assertion (compatible wording restored) and two missing-cover errors while a
concurrent production render replaced `output/`. The full suite is rerun with
production rendering stopped; isolated reruns do not supersede that result.
Production render and validator passed with exactly
**10 governed historical warnings**. The database, all fourteen historical
sidecars and historical Atom feed match their pre-work SHA256 baselines.
Historical pages and citations are unchanged. Generated changes are limited
to `output/analysis.html` and `output/styles.css`; the draft article and native
feed remain absent from public output.

Rendered proof: private article and Analysis at **1280 × 900** and **375 × 900**,
actual screenshots visually inspected. Article reading order leads with prose,
with optional comparison and collection coverage below it; citations link to
the unobtrusive trail; native disclosure targets reveal through TOC links.
Analysis has clear browsing, a featured native photograph, concise catalog and
accurate processing/triage labels. Whole-background topographic decoration is
excluded and remains the next separate frontend task.

Independent release QA checked **26 route/viewport combinations** across the
production site and private candidate: no overflow, browser errors, failed
requests, missing images/dimensions/anchors, heading skips or hidden primary
content. Keyboard focus, citation copying, no-JS and reduced motion passed.
Ten internal links and all five exact source URLs returned HTTP 200 in the
independent HEAD sweep. Headline/dek glyph contrast was at least 13.06/9.31:1.
The dark terminology citation contrast defect was fixed using existing band
tokens, including hover and focus states, and re-rendered for final QA.
The independent recheck passed at both widths: 8.97:1 normal/visited/focus,
13.53:1 hover, with a 2px focus outline. Final QA is GO for draft PR preparation;
publication is NO-GO only for approval of this exact candidate.
Private article/Analysis/home HTML sizes are about 29/27/22 KB; the largest
production non-archive page checked is below 99 KB.

Local evidence (temporary host files):

- `/private/tmp/ipr-briefs-proof-20261004/` — refreshed desktop/mobile PNGs and `review.json`.
- `/private/tmp/ipr-independent-releaseqa-20261004/report.json` — independent broad sweep.
- `/private/tmp/ipr-release-final-focused.log` — final affected tests.
- `/private/tmp/ipr-release-offline-final.log` — final full offline suite.
- `/private/tmp/ipr-briefs-validator.log` — governed output gate.
- `/private/tmp/ipr-briefs-preserved-baseline.json` — preserved-content hashes.

Review locally at `http://127.0.0.1:8878/briefs/maritime-cooperation-2026.html`
and `http://127.0.0.1:8878/analysis.html`. Proposed public address (not live):
`https://indopacificrecord.org/briefs/maritime-cooperation-2026.html`.
The remaining authorized execution after exact-candidate approval is final
attribution/approval receipt, number assignment, production render, validator,
PR checks, merge/deploy within that authorization and live verification of all
five publication surfaces, followed by an ordinary render preservation check.
