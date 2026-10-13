# Country desk checkpoint intake — AFP and Vietnam

**Status: private operator scaffold, not desk/source admission.** This integrates existing machine reports. It does not run source collectors, query publishers, generate a new reviewer signature, enable production, change rights or deploy the website.

## What this fixes

AFP already has an immutable seven-slot audit, an independent Actions metadata checker and an original-source packet preflight. Vietnam has three source-specific formal packets, a GitHub Actions attempt-reconciliation bridge and a three-source rollup. The inputs can be individually valid while referring to **different Git commits or calendar windows**. The new offline composer (scripts/compose_country_desk_checkpoint.py) checks their shared identities and produces a compact operator report. All production, human signoff, source rights and AI eligibility booleans remain false, even if the evidence is mechanically consistent.

The composer does **not** repeat the original reviewers' work, authenticate human signatures, provide an exhaustive independent workflow audit, or validate publishers.

## Checkpoints and boundaries

| Family | Earliest first checkpoint | Separate remaining hold |
| --- | --- | --- |
| Philippines AFP | Oct 13, if all seven scheduled Oct 7–13 UTC slots are genuine successes | Per-original fidelity, complete Actions attempt inventory, rights, Day 7/14/30 and 30-day maturity |
| Philippines NSC | Independent schedule, excluded from AFP intake | Zero stored articles does not prove article extraction, source coverage or rights |
| Vietnam MPS | Oct 14 after scheduled run | Vietnamese publisher originals, complete Actions failures/reruns, rights, human checkpoint |
| Vietnam MOIT Energy | Oct 14 after scheduled run | Robots MIME warning and prior-written-consent question, source-specific review |
| Vietnam MOIT Foundational | Oct 14 after scheduled run | Same independent robots and rights constraints |

Vietnam's Oct 7 bootstrap **attempt 2 was manually dispatched**, with older historical publication-target dates; this cannot be counted as a historical scheduled collection run. The shadow_day counter measures elapsed whole days and is not proof of consecutive scheduled calendar slots.

### AFP operator sequence (after Oct 13)

Use an authorized local state Git checkout and pin AFP_SHA to the **literal 40-character SHA** of the post-checkpoint shadow/ph-afp source commit. Set SECURE_DIR to an access-controlled local directory outside the working checkout. Prepare actual original-source review decisions via docs/PH_AFP_PER_RUN_REVIEW.md and docs/PH_AFP_ADMISSION_PREFLIGHT.md; a machine-generated unsigned review packet is not human approval.

Generate the existing two reports (the Actions export must satisfy the existing complete-pagination contract):

~~~sh
python -m scripts.assess_ph_afp_activation \
  --state-repo "$AFP_STATE_REPO" --state-commit "$AFP_SHA" \
  --as-of 2026-10-13 > "$SECURE_DIR/afp-preflight.json"

python -m scripts.audit_ph_afp_actions_provenance \
  --state-repo "$AFP_STATE_REPO" --state-commit "$AFP_SHA" \
  --as-of 2026-10-13 \
  --actions-export "$SECURE_DIR/complete-afp-actions-pages.json" \
  > "$SECURE_DIR/afp-actions.json"

python -m scripts.compose_country_desk_checkpoint philippines \
  --preflight "$SECURE_DIR/afp-preflight.json" \
  --actions "$SECURE_DIR/afp-actions.json"
~~~

The preflight above intentionally defaults to **no reviewed original-source decisions**. To include genuinely completed decisions, follow the existing tool's --manifest and --review-dir contract and human checklist. Never claim a complete review merely because the seven-slot machine audit passes. A positive seven-slot match does **not** establish absence of failed, cancelled or rerun attempts beyond the exported window.

### Vietnam operator sequence (after Oct 14)

The existing authenticated bridge makes only bounded GitHub REST metadata GETs, not publisher HTTP requests, and needs a scoped GITHUB_TOKEN:

~~~sh
python -m scripts.bridge_vietnam_actions_reconciliation \
  --through 2026-10-14 --approve-github-read \
  > "$SECURE_DIR/vietnam-attempts.json"
~~~

The bridge may exit nonzero on a legitimate review warning; do not change its source evidence to make it green. Freeze the three literal state_head_shas from that exact report. Use an authorized local source-state Git checkout that contains the appropriate immutable histories.

~~~sh
python -m scripts.review_vietnam_ministry_state \
  --source vn_mps_foreign_affairs_vi \
  --state-repo "$VN_STATE_REPO" --state-commit "$VN_MPS_SHA" \
  --checkpoint day-07 --as-of 2026-10-14 --out-dir "$SECURE_DIR/vn-mps"

python -m scripts.review_vietnam_ministry_state \
  --source vn_moit_energy_vi \
  --state-repo "$VN_STATE_REPO" --state-commit "$VN_ENERGY_SHA" \
  --checkpoint day-07 --as-of 2026-10-14 --out-dir "$SECURE_DIR/vn-energy"

python -m scripts.review_vietnam_ministry_state \
  --source vn_moit_foundational_industry_vi \
  --state-repo "$VN_STATE_REPO" --state-commit "$VN_FOUNDATIONAL_SHA" \
  --checkpoint day-07 --as-of 2026-10-14 --out-dir "$SECURE_DIR/vn-foundational"

python -m scripts.vietnam_ministry_checkpoint_rollup \
  "$SECURE_DIR/vn-mps" "$SECURE_DIR/vn-energy" "$SECURE_DIR/vn-foundational" \
  > "$SECURE_DIR/vietnam-rollup.json"

python -m scripts.compose_country_desk_checkpoint vietnam \
  --rollup "$SECURE_DIR/vietnam-rollup.json" \
  --actions "$SECURE_DIR/vietnam-attempts.json"
~~~

**Dependency now integrated:** PR #444 (https://github.com/VSSpowerlifting/China-Mil-Watch/pull/444), merged on October 12, preserves `source_anomalies` in Vietnam's formal human-review packet. This composer still checks that each source-specific packet acknowledges **at least** the committed source anomaly count independently observed by the Actions bridge. A missing or mismatched MOIT warning must be refused; **do not relax the comparison** to get green output. Issue #196's MOIT written-consent and robots review remains separate, regardless of any machine score.

Only a fixed, exact commit is acceptable. If a shadow branch advances between independent observations, regenerate and re-review evidence at the new pin rather than combining generations.

### Day 14, Day 30 and admission

For Vietnam, the same producer supports day-14 (earliest Oct 21) and day-30 (earliest Nov 6), with separate human signoff. AFP's seven-slot composer is **Day 7 only**. Its earliest possible thirtieth calendar collecting date is Nov 5, conditional on actual consecutive successes. None of these dates promises admission.

Before even considering live records: source-by-source rights and originals, complete adverse-attempt history, C1–C13 including 30 consecutive collecting days and named Day 7/14/30 reviews, custody/public-projection decisions under #332/#342, and a written owner approval are mandatory. AFP cannot lend qualification to NSC; MPS cannot lend permission or reliability to MOIT. Briefs/AI eligibility and publication require distinct approvals.

## Engineering boundaries and acceptance

- Source reports are explicit regular JSON files with no duplicate keys, symlinks or oversized payloads. Composer emits **only** fixed source names/SHAs, small counts, dates and named machine holds; it does not echo third-party article titles, URLs, text, captures or arbitrary notes.
- No raw state SQLite, publisher original, private capture, token or real human signoff is added to Git, Pages or Actions artifacts. Keep review packets outside the working checkout.
- Mismatched source pins, changed dates or run IDs, missing institutional families, contradictory sums and attempted production/rights assertions fail closed.
- A candidate_for_human_checkpoint classification is **not** human approval, rights approval, full attempt-history certification, 30-day maturity, live desk, production record or release permission.
- Focused Python 3.9 verification: python -m unittest tests.test_country_desk_checkpoint_intake -v; separately run affected existing source/attempt suites and verify tracked database/output/shadow preservation.
- No collection scheduler, site registry, record model, public links, Sunday writer, external model or deployment is changed in this phase.

**Phase boundary:** deliver one reviewed checkpoint-composer PR; wait for actual Oct 13/14 source runs and run the existing operator commands with then-current frozen inputs. Source-specific approval and eventual production promotion are new, independent phases, not extensions of this scaffold.
