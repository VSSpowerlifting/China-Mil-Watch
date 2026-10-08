# Japan Coast Guard: first formal shadow run and review handoff

**Not a production activation instruction.** This checklist governs a manual-only first collection of the Japan Coast Guard English press release source; it does not activate MOD or the wider Japan Desk. Owner review/merge of each PR and source-use constraints remain prerequisites.

## 0. Stack verification before any state write

1. [PR #206](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/206) was squash-merged into `main` with successful source-access and full offline checks.
2. Stacked [PR #208](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/208) and [PR #209](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/209) were merged into **intermediate branches**, not `main`. A GitHub "merged" status on those PRs is not evidence of mainline installation. Do **not** merge or cherry-pick those branches wholesale.
3. [PR #212](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/212) consolidates the exact required adapter, shadow runner, pinned reviewer and test files into a single clean branch off the post-#206 `main`. Review its own full main-target PR checks and source boundary before squash-merging.
4. For #212, explicitly inspect and approve first-party text reuse and document-specific exclusions under the publisher's usage terms. Confirm that no PDF attachment, photo or logo is intended to be copied or represented as collected. Confirm the observed stale `datetime=2021-3-1` discrepancy is documented and acceptable *only with original index/visible-date equality*.
5. Verify there is **no new production Japan manifest**, no changed production DB or public output, no cron, and the workflow is guarded by `github.ref == 'refs/heads/main'`. Do not merge any `shadow/japan-jcg` branch into `main`.

## 1. First owner-authorized manual collection

Only after all prior source PRs have merged and full CI passes:

GitHub repository → **Actions** → *Japan Coast Guard — Manual Isolated Shadow Pilot* → **Run workflow**, choose `main`, set logical `target_date` to the intended UTC day (for initial verification, `2026-10-08` if running on that day). Leave the workflow **unscheduled**.

The runner checks out the approved collector, executes its tests, then uses an isolated `shadow/japan-jcg` state branch. It aborts on an unreadable/disallowed robots policy, access challenge, unexpected publication family, malformed date, title/date mismatch, too many source items for its cap, failed body extraction, changed archival text, or other incomplete batch.

**Expected on an eligible 2026-10-08 initial run:** the 9-day lookback can discover three original English HTML release documents (two from October 6 and one from September 29), assuming the official archive has not changed. The current live proof established these three, not all possible future publications. Never hard-code a "three successes" criterion for later dates.

## 2. Freeze and audit the first state

From the Actions run evidence, record: exact reviewed collector SHA, exact state commit SHA, target-date source, completed/health status, robots verdict, index count, selected/fetched/extracted/inserted/duplicate counts, source identity list, per-request capture hashes, content hashes, exclusion count, and any errors.

**Do not call a failed or partially populated attempt a first successful shadow day.** The shadow clock starts only when the runner records a genuinely successful attempt.

For a pinned state-branch commit, use the existing reviewer with the new desk identity, exporting outside all collector worktrees:

```bash
python scripts/review_desk_shadow.py \
  --desk japan_jcg \
  --state-repo /path/to/trusted-clone-containing-shadow-branch \
  --state-commit EXACT_FULL_40_CHARACTER_STATE_SHA \
  --as-of 2026-10-08 \
  --out /path/outside-repo/japan-jcg-day0-review
```

The formal reviewer refuses mutable state alone as a commit-backed checkpoint and rejects unrelated branch ancestry or unexpected files. It never supplies a human signature.

Compare each exported English original to the live publisher HTML and capture bytes. Audit dates, URL identities, duplicates, attachments excluded, original text boundaries, issuer attribution and the stale `2021-3-1` machine attribute. Preserve an independent, signed record of reviewer, exact state SHA, actual timestamp, sources reviewed, discrepancies, decisions and any holds.

## 3. Shadow qualification and future promotion

The Day 7/14/30 checks and 30 consecutive collecting days remain mandatory under `docs/DESK_STRENGTH_CRITERIA.md`. This narrow source is Japan **Coast Guard** coverage, not comprehensive MOD/JCS defense coverage. A daily schedule, additional publisher sources, official-capture archiving, production manifest, existing-db migration, registry promotion or automatic weekly-writer inclusion all require separate review and approval.

The temporary Japan editorial-source bridge (#202) is independent. It should be retired only after native, full-text production records have proven normal weekly-writer selection and citation behavior.
