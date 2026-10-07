# PR offline-check efficiency — 2026-10-07

## Scope and base

Fresh managed worktree and branch `codex/pr-offline-efficiency-20261007`, based
on remotely verified main `9b475d0d578f93e6d4b9dc7cc90d3ad38c627b10`.
The owner checkpoint was `5ccc20ff94131f63d639aed840633776b829ef60`;
main advanced before this work. Existing worktrees and changes were preserved.
No dependent PR. Only PR offline scheduling, its contract tests and this receipt
are changed. No production data, generated output or other workflow is changed.

## Behavior and exact-head review requirement

`offline-checks` now has the job-level condition
`${{ github.event.pull_request.draft == false }}`. GitHub evaluates this before
allocating a runner. The trigger remains `pull_request` to main with exactly
`opened`, `synchronize`, `reopened`, `ready_for_review`:

| Event | Draft | Runner/full gate |
|---|---|---|
| opened, synchronize, reopened | true | skipped / none |
| opened, synchronize, reopened | false | complete existing gate |
| ready_for_review (including no intervening push) | false | complete existing gate |
| subsequent synchronize | false | complete existing gate on the new head |

Returning to draft skips subsequent draft pushes; readying again runs the gate.
No path filter or docs exception exists. Job ID/name, merge-ref checkout (no
`ref` override), read-only token, no persisted credentials, browser installation
and launch assertion, serial complete unittest discovery, output validator,
DB/output preservation assertions, timeout and per-PR cancellation are unchanged.
Every step is byte-identical to main; only the job condition was added.

**A skipped draft check never authorizes a merge.** Owner review must establish
that the PR is non-draft and the latest offline-checks run for its exact current
head actually ran the entire suite, validator and preservation step successfully.
An older head, cancelled run, skipped job or green workflow summary alone is
insufficient. Ready-for-review must be awaited, even if the head did not change.

Accessible GitHub APIs on 2026-10-07: branch protection returned HTTP 404,
`Branch not protected`; repository rulesets and effective main branch rules
both returned `[]`. No GitHub-enforced exact-head rule was observed. External
owner tooling/organization policy not exposed by these responses is unknown.
No settings were changed. GitHub treats skipped jobs as successful for required
checks, so merely adding a required status-check name would not prove execution.
See [GitHub status-check semantics](https://docs.github.com/en/pull-requests/reference/status-checks).
The existing owner exact-head requirement above remains mandatory.

## Before/after cost

Owner-supplied October 1–7 baseline: 1,495 runner minutes / 73 runs =
20.479 min/run (20m29s), 27 PRs = 2.70 runs/PR. Existing successful suite times:

| Run | Tests | Serial suite seconds |
|---|---:|---:|
| 37539081142 | 3,478 | 920.415 |
| 37540091500 | 3,486 | 1,194.855 |
| 37552932009 | 3,495 | 1,245.833 |
| 37558189901 | 3,713 | 1,549.210 |

Before: each draft event can allocate the full runner and gate.
After: each draft event allocates **zero runners and zero runner minutes**.
Expected saving per otherwise-completed draft iteration: about **20.48 minutes**
using the supplied mean; the two profiled suites alone cost 20.76 and 25.82
minutes, plus setup/validator. If D of the historical 73 runs were avoidable
draft iterations, estimated savings = D × 20.479 minutes. Historical event draft
flags were not measured; 2.7 runs/PR does not establish an avoidable fraction.
Ready/non-draft runs retain their prior cost; no serial-runtime saving is claimed.
Actual draft/ready Actions receipts are recorded in the PR review body, using the
same head for the transition. Final state must be draft; nothing is merged.

## Ranked timing diagnosis from existing logs

Downloaded existing successful logs with `gh run view RUN --log`; no Actions
run was spent to collect profiling data. Log headers reconcile exactly with
3,495 and 3,713 reported tests; first-to-last test-header spans are 1,245.833
and 1,549.210 seconds, matching the unittest totals to rounding.

Method: parse timestamped `test_NAME (tests.MODULE.CLASS)` headers; sum
successive timestamp differences, assigning each gap to the **following**
header's module/class. Most one-line verbose entries reach Actions with their
result, while multiline docstrings can arrive at start. These are boundary
estimates including fixture setup/teardown, logging and browser waits, not
instrumented per-test CPU times. Setup at a class boundary can dominate a gap.
No timing claim is made for a single function based on these intervals alone.

| Module (ranked by combined interval time) | 37552932009 seconds | 37558189901 seconds |
|---|---:|---:|
| `test_preview_prototype` | 244.1 | 297.8 |
| `test_home_paired_records` | 209.8 | 259.3 |
| `test_homepage_intro` | 142.5 | 160.1 |
| `test_pla_watch_veil_contrast` | 137.7 | 161.0 |
| `test_home_briefs_band_veil` | 44.2 | 51.3 |
| `test_identity_assets` | 43.9 | 50.5 |
| `test_briefs_collection` | 39.7 | 43.5 |
| `test_homepage_veil_contract` | 31.7 | 37.4 |

The first four consume approximately 59% and 57% of suite time respectively.
Class-level hot spots, under the same boundary-estimate method:

| Class | 37552932009 seconds | 37558189901 seconds |
|---|---:|---:|
| `test_homepage_intro.TestTheCompositionFits` | 89.9 | 101.2 |
| `test_pla_watch_veil_contrast.TestVeilTextMeetsAA` | 64.1 | 71.8 |
| `test_home_briefs_band_veil.TestTheBandVeilInTheBrowser` | 43.1 | 50.6 |
| `test_pla_watch_veil_contrast.TestTreatmentMovesNothing` | 37.6 | 44.3 |
| `test_home_paired_records.TestProvenanceSurvivesAHeterogeneousRegister` | 32.5 | 38.4 |
| `test_palette_and_accessibility.TestKeyboardAndMotionRules` | 28.4 | 30.6 |

Inspection confirms `PreviewCase.setUpClass` performs a complete corpus build
for each inheriting class; `HomeCase`, `BrowserCase`, and `IntroCase` likewise
build per concrete class. Controlled paired-record cases also build full trees
for changed fixtures. Composition tests exercise four viewports using software
WebGL and Playwright clock advancement; veil tests measure actual glyph contrast
across editions/viewports. The 78.3/88.4s interval ends at the composition test,
and the 64.1/71.8s interval ends at the veil contrast test; these gaps must not
be blamed on the preceding fonts-failure/no-motion test.

No runtime optimization is adopted: sharing rendered fixtures needs proof of
mutation/isolation safety; reducing these browser cases or waits needs proof
that the same geometry, timing and contrast contracts remain tested. Neither
is a one-line proven-safe change. No parallel execution, new jobs, test-corpus
reduction or dependency/browser cache change is introduced.

## Verification

- Baseline: `python -m unittest tests.test_pr_workflow_contract -v`: 56 pass,
  0.019s. After: 62 pass, 0.027s (timing includes only contract tests).
- Event-table and lifecycle tests explicitly exercise draft opened/push/reopen,
  skipped draft → ready without a push → every non-draft push, and redraft.
- `python -m unittest tests.test_cleanliness_gate_contract
  tests.test_pr_workflow_contract tests.test_us_shadow_workflow
  tests.test_workflow_contract tests.test_workflow_day_contract
  tests.test_workflow_failure_paths tests.test_workflow_yaml_shape -v`:
  all 178 tests pass in 3.593s.
- Official actionlint 1.7.12:
  `actionlint -shellcheck= -pyflakes= .github/workflows/pr_offline_checks.yml`
  passes, including expression validation; optional shell/Python linters disabled.
- Python 3.9 environment: existing `/Users/benjaminyang/pla-watch/.venv` reused
  read-only as an interpreter; new worktree has no dependency mutation.
- `python scripts/validate_output.py`: passes with the same 10 governed warnings.
- SHA-256 before/after comparison of all 7,451 tracked DB/output files, Git diff,
  untracked-file check and SQLite sidecar absence: all pass locally.
- GitHub lifecycle verification: open draft, observe skipped/no runner; mark
  ready on identical head, observe full existing gate; return to draft after
  completion. A real synchronize while draft is also observed before ready.

## Remaining opportunities, ranked by likely runner-minute savings

1. Eliminate avoidable draft full runs (this change): ~20.48 min per full run
   avoided. Benefit scales directly with draft iterations, not test count.
2. Review repeated full-corpus fixture builds in preview/paired-record modules
   (~454–557s combined): potential several minutes per ready run. Preserve
   independent changed-input/determinism cases; do not share writable state.
3. Investigate software-WebGL composition and glyph-contrast cases
   (~154–173s for the two leading classes): possible minutes per ready run,
   but measured geometry and contrast coverage must remain identical.
4. Bounded intra-runner process parallelism: potentially large overlap of the
   above work, but unknown benefit under CPU/software-rendering contention.
   First prove identical test IDs/counts and repeat runs for shared-state races;
   extra Actions jobs would multiply setup and may not reduce billed minutes.
5. Chromium/dependency caching: at most about 23–25s browser install and 8–10s
   dependencies per full run under the supplied baseline. Much smaller than
   avoiding full-suite runs; browser revision and OS libraries still need proof.
