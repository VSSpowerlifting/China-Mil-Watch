# No. 14 correction preparation — 3 October 2026

**Release follow-up:** Ben approved No. 14 and publication of these corrections
on 3 October 2026. See `DECISION_LOG.md` and the separate release record.
The preparation below preserves the evidence and state before approval.

**Recommendation: review and approve the corrected version, retaining No. 14.**
This is a prepared correction, not owner approval or a published update.

Repository: `VSSpowerlifting/China-Mil-Watch`.
Current main was checked at the start and closeout:
`937734925b3503961b798ae40c940b83e4cebf76`.

The saved `IPR_No14_Editorial_Review_2026-10-03.md` was recovered and its
findings were checked against the current canonical sidecar and original
database bodies. The later local review named in the handoff was not present
on GitHub; this preparation independently checks its four reported major
findings. No approval is inferred from either review.

## Proposed changes

| Finding | Correction in the candidate |
|---|---|
| Unsupported classification of Honghe | “Chinese Navy ship Honghe”; the Indonesian designation remains the source's Chinese wording |
| Untraced duration, routine baseline and exercise taxonomy | Describe the activities in this encounter; retain the existing English rendering without general definitions or claims about a wider relationship |
| Footage-release attribution | Treat the two 9 August Global Times titles as captured-title observations; neither defective body establishes who released footage or demonstrated capability |
| One-source snapshot | Supply the four sources derived from the preserved trail; the existing template already renders that count correctly |
| Blanket claim that no source addresses intent | Attribute the Chinese ministry's stated aims; distinguish them from independently established intent and coordination |
| Incomplete Global Times exercise capture | Disclose the capture defect and limit the comparison to preserved titles; do not replace historical source text |
| Ambiguous corpus scope | Explicitly label the 229/137/zero-unscreened figures as China Desk counts |
| Unverified English vessel proper name | Remove `(Lái)` from the existing English trail title for record 3172; retain its original Chinese title verbatim |
| Companion text repeats old claims | Prepare the matching LinkedIn text, including the correction note and standing corrections invitation |

A dated correction paragraph appears in the existing Opening Note, requiring
no new template, CSS or field contract. The headline comparison remains:
five selected captured titles, three outlets, three publication dates and one
China–Indonesia encounter. The proposed dek and signal now describe that
metadata observation without an untraced characterization of the activities.

The correction date in the preview is **3 October 2026**, the preparation
date. If applied later, regenerate the proposal with the actual correction
date; do not backdate either correction or approval.

## Evidence checks

All twelve trail entries were resolved to the current preserved records.
The substantive original bodies used for the correction were read directly;
model summaries were not accepted as vessel, service or capability evidence.

- Records 3125, 3172 and 3226: original Chinese announcement and completion
  reports. They name Honghe, the Indonesian frigate and reported drill
  activities. The reports do not support the removed vessel classification,
  generic duration or exercise taxonomy.
- Record 3144: English Xinhua copy attributed to China's defence ministry.
  It states aims of enhancing joint operational capabilities, practical
  cooperation and regional peace and stability. It is not independent
  corroboration or an Indonesian account.
- Records 3084, 3085 and 3145: stored Global Times bodies contain unrelated
  snippets. They remain preserved; title observations are disclosed as such.
- Records 3177, 3211, 3245 and 3354: the other cited stories were checked
  against original bodies. The revised pilot paragraph avoids relying on
  model metadata alone for service attribution.
- China Desk window: 229 records; 137 analyzed; zero awaiting screening.
  Analyzed counts: PLA Daily 111, CMO 14, Global Times 10, MOD China 2.
  Model category assignments: political work 65, exercises 49, doctrine 39;
  the revised prose labels them as overlapping automated classifications.

## Reproducible correction mechanism

`scripts/correct_no14.py` prepares the proposed canonical sidecar, companion
and unified diff outside production `output/`. It is stdlib-only, performs no
network or database operations, and renders no HTML. Its two-file migration
uses exact original SHA-256 guards, checks both inputs before writing, stages
both replacements, and restores the first original if the second replacement
fails. It has no force bypass; changed files require a fresh review. It also
refuses a proposal destination overlapping either canonical file.

Reviewed original SHA-256 values:

| File | SHA-256 |
|---|---|
| `output/the-pla-watch/posts/2026-08-15.json` | `f5aa239888821a3279916ddc4387198eefc3620e62341f18421296410cb7baa0` |
| `the-pla-watch/linkedin/2026-08-15.txt` | `44488f0ca0f6f0ebf20fb1d0b277157b254da5a2dbd0dfdb0ea67e709a254b2c` |

Preparation and focused checks:

```bash
python3 scripts/correct_no14.py --correction-date 2026-10-03
.venv/bin/python -m unittest tests.test_no14_correction tests.test_pla_watch_historical_reader -q
.venv/bin/python scripts/validate_output.py
git diff --check
```

Only after owner review and explicit authorization to apply and regenerate:

```bash
# Replace the date with the actual correction date if it differs.
python3 scripts/correct_no14.py --correction-date 2026-10-03 --apply
.venv/bin/python scripts/rerender_pla_watch.py --no-covers
.venv/bin/python site/render.py
.venv/bin/python scripts/validate_output.py
git diff --check
```

These commands do not record owner approval. Record the real ruling and
actual approval date separately; then make the bounded numbering-contract
change and its tests. Do not paste a suggested ruling as if Ben made it.
Commit, push and deployment remain separate explicit actions.

## Completed validation

- **11 targeted tests pass**: six migration safety tests and five historical
  reader tests. They cover provenance preservation, stale-file refusal,
  invalid dates, changes between preparation and application, two-file failure
  recovery and successful migration in a temporary test repository.
- **Original production snapshot passes the validator with 10 governed
  warnings.** The disposable corrected preview also passes with the same ten
  warnings. No warning was suppressed or repaired by invention.
- Eight browser route/viewport checks pass: edition, preserved series index,
  archive and unified Analysis at **1280 and 375 pixels**. Full-page
  screenshots and focused correction/snapshot/glossary captures are supplied.
- No horizontal overflow or JavaScript page errors observed. Index, archive
  and Analysis lead links open the corrected edition at both widths. The
  four-source card, visible correction note, keyboard-focus traversal sample
  and normal-motion reveal behavior were checked. This is not a full
  accessibility or contrast audit.
- Pages were generated through the real renderers into disposable directories.
  The agent-browser daemon could not bind its socket here; direct Playwright
  verified the rendered files through local response interception. No external
  page was fetched. The same English font families and a Noto CJK fallback
  were supplied locally for screenshots; this is not a live CDN/font test.
- SHA-256 comparison confirms **all 7,308 protected database/output files
  remain unchanged**. No stored source, canonical edition, shadow state,
  numbering gate, approval record or published page was modified.

## Remaining human gate

Ben should review the proposed prose, the retained Chinese designation and
English terminology, and choose correction-and-retention or another
disposition. The [editorial checklist](https://github.com/VSSpowerlifting/China-Mil-Watch/blob/937734925b3503961b798ae40c940b83e4cebf76/EDITORIAL_QA_CHECKLIST.md) states:
“Final analytical judgment and published prose remain human-controlled.”

`UNRECONCILED_ISSUES = {14}` remains unchanged. No new Brief has been numbered,
approved or published. The 22 August disposition is still a separate question.
Stay in this chat for No. 14's ruling; the China–Singapore Brief is the next
editorial task after reconciliation.
