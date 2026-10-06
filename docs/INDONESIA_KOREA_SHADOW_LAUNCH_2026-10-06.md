# Indonesia and South Korea — durable shadow state, 2026-10-06

Ben authorized the implementation commit/PR followed by durable shadow collection
in this Codex chat, then instructed continuation. The authorization is recorded
in DECISION_LOG.md. [Draft PR #110](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/110)
contains the collectors, fixtures, review tooling and prepared manual workflow.
No main merge, schedule, deployment, public desk declaration or promotion occurred.

## Published initial state

Fresh native-client collections used immutable collector
`5ddca377edb7572018bccdafcc7f00bc729427d0`, with a clean collector worktree,
six lookback days and a cap of forty. The logical date is 2026-10-06, resolved as
`manual-utc-date`; actual execution timestamps remain in each ledger. No rehearsal
record, ledger or clock was transferred. Robots were reread and permitted both
seed sources. MND publication paths remained unrequested.

| Measure | Indonesia | South Korea |
|---|---|---|
| Source | Kemhan Berita institutional news | Policy Briefing's MND-labeled republications and linked HWPX |
| State branch | `shadow/indonesia-kemhan` | `shadow/korea-policy-briefing` |
| Initial state commit | [`8e9ee2e846a3fc99b339f41442dcb78d62c21d26`](https://github.com/VSSpowerlifting/China-Mil-Watch/commit/8e9ee2e846a3fc99b339f41442dcb78d62c21d26) | [`bbe2c8a25d55b18c55c74b499cd0525b5107c7f3`](https://github.com/VSSpowerlifting/China-Mil-Watch/commit/bbe2c8a25d55b18c55c74b499cd0525b5107c7f3) |
| Run ID | `local-native-20261006-indonesia` | `local-native-20261006-korea` |
| Selected / retrieved / extracted / inserted | 14 / 14 / 14 / 14 | 4 / 4 / 4 / 4 |
| Captured responses | 17 | 10 |
| Fetch / extraction / access failures | 0 / 0 / 0 | 0 / 0 / 0 |
| Result / health | `ok` / `ok` | `ok` / `ok` |
| First-success clock, UTC | `2026-10-06T16:52:15.008737+00:00` | `2026-10-06T16:52:01.420713+00:00` |
| Files verified from fresh remote clone | 20 | 13 |

Each repository was initialized on its fixed orphan branch. Before publication,
the committed tree contained only `state/`, all paths were regular recognized
files, capture and DB hashes matched the ledger, and the clock matched the actual
first successful finish. Each branch has one parentless initial commit and no
workflow or deployment content. Pushes named their explicit destinations and
used no force. No state PR was created and neither branch is merged to main.

Fresh remote clones resolved to the published commits above. The pinned-state
reader exported each commit and found zero machine integrity findings. Every
state-file hash matched the pre-publication packet. These are launch integrity
audits, not Day 7/14/30 human checkpoint reviews; human sign-off and promotion
remain false. The clock records one successful execution, not periodic reliability.

## Verification and limits

The [source-commit PR CI run](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37498909083)
passed **3,229 tests, two skipped**, launched Chromium, passed the output validator
with ten governed warnings and verified the tracked DB/output stayed unchanged.
It tested collector commit `5ddca377edb7572018bccdafcc7f00bc729427d0` in the PR's
merge checkout. The focused local regression group separately passed 330 tests.

The full local sandbox run reported **3,112 tests, 31 errors, two skipped**.
All 31 errors were existing server/browser setup paths failing with
`PermissionError: [Errno 1] Operation not permitted` because local port binding
was denied. That run is not reported as green; the full CI run above supplies
the successful browser/server verification. No implementation repair or isolated
test rerun was used to conceal it.

A final hash and complete output-file-list comparison confirms all **7,411**
production DB/output files unchanged. No production render, production collection,
paid model call, Pages deployment or live-site verification was performed.
The follow-up changes recording this launch touch documentation only; any new
CI run belongs to that later PR head and is distinct from the verified source run.

Local audit evidence is preserved in
`/private/tmp/ipr-indonesia-korea-durable-evidence-20261006.tar.gz`, including the
fresh state and clean remote-clone packets, source CI and full local suite logs, validator
log, launch metadata and source snapshot. Its local storage is supplementary;
the two published orphan commits are the durable collection evidence.

## CI repair after the receipt update

[Receipt-update CI](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37518846526)
tested merge `071dd4faba1ef0ac777ffbaf16be498d4c591a1f` against newer main
`ef89d5f3d11bf5a8ebb7e6be2c73785c6f10fb5c`: 3,245 tests, two failures,
two skipped. Both failures were the existing phone headline assertion, on native
and wide font stacks; the desk tests and production-preservation check passed.
The validator step did not run after that failure.

A minimal Chromium reproduction drove the exact assertion and failed identically
with the whole headline visible at y=100 through y=128.265625: its measured line
height was 28.265625px, while computed CSS returned 28.272px. Settling fonts and
disabling motion did not change it; an integer line height passed. A title clipped
by the viewport still failed. This isolates a measurement-precision mismatch,
not a product layout change.

`tests/test_home_paired_records.py` now allows one 1/64px layout unit in that
comparison, consistent with [Chromium's six-bit layout representation](https://chromium.googlesource.com/chromium/src/+/96b04b8744c3300c980cd87bc41cc3444d463fb0/third_party/blink/renderer/platform/geometry/layout_unit.h).
New real-browser cases prove that a fully visible fractional line passes and a
clipped fractional line is rejected. The positive regression was observed red
before the correction; the minimal repro and all 18 first-viewport, opening-space
and page-shape browser checks pass after it. Production styling, the collectors,
captured source bytes and both published state commits are unchanged.

The current full check on [PR #110](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/110)
is the corrected-head verification gate; the older successful source run is not
substituted for it. Repair evidence is in
`/private/tmp/ipr-indonesia-korea-ci-repair-20261006.tar.gz`.

## Remaining action

Owner review and an authorized merge of PR #110 are required before its prepared
main-only manual workflow can run on GitHub Actions. Scheduling remains off; no
recurring run or automatic continuation has been configured. Any future schedule
needs its own authorization and logical-date slot, followed by real Actions
egress/persistence verification. This local native launch does not establish that
egress. Durable state survives independently of that later integration.

The bounded seed scopes, unsupported document formats, unresolved reuse terms,
cadence thresholds, historical completeness and human source/document comparisons
remain as documented in the candidate READMEs and initial execution receipt.
Days 7, 14 and 30 require actual human checkpoints. Thirty consecutive collecting
days, sufficient corpus and owner sign-off remain prerequisites to any separate
production promotion; none is supplied by this launch.
