# AFP shadow integration — 2026-10-06

**AFP shadow evaluation only; manual rehearsal plumbing is owner-approved.**
No Philippine production desk, new institution adapter, production collection,
deployment or scheduled run is created. NSC remains supplemental. Japan source
research is outside this integration.

## Japan correctness checkpoint

Commit `22bf87bd78dcc3f73e6a1e3767401a56b9c06ba0` on
`codex/jp-ph-desk-assessment-20261006` removes Japan's hard-coded policy
assumption, checks current robots rules before requests, and records refusals
without advancing the success clock. Its 17 files comprise two runtime files,
their regression tests/fixtures, and assessment documentation/evidence.

Checkpoint review ran 496 focused tests successfully, including the final
UTF-8 decoding regression. The earlier full run passed 3,204 tests with two
skips before that decoding correction; the validator passed with 10 governed
warnings. Production DB and all 7,410 output files were hash-identical, and
remote main/Japan/NSC heads were unchanged. The exact commit is pushed and open as
[PR #108](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/108); it remains
separate from this AFP branch and unmerged. Japan’s measured 1.49% full-text
coverage problem remains unresolved. No live collection is claimed by the PR.

## PR #79 assessment and resolution

Reviewed [PR #79](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/79),
still open/draft at `b29e7edb047c30c8b878bca0069ba183424e2478`, against live
main `a259ee6d2e42d90ade1cb0b51fab41a71ce3b430`. Their merge base is
`60a6c1cc2a4550a1e48353f9aea43dd427b47423`.

The only overlapping changed path is `PROJECT_STATE.md`. A three-way scratch
merge confirms its textual conflict. The AFP adapter, runner, manifest and
tests are additions; the shared collection contract, manifest loader and
logical-date resolver have not changed since that base. Current-main NSC
activation, Japan selection repair, offline CI and unrelated product work
therefore need no architectural merge decision.

The state conflict is mechanical, but its text is semantically stale: it says
NSC is merely an unassessed candidate and describes a discarded local AFP
corpus as if it were current readiness evidence. The implementation also
allowed cap-limited windows and malformed listing metadata to return success,
ignored broader named-agent policy matches/delays, and lacked a source-disabled
CLI guard and exclusive attempt writes. Those assumptions were corrected.

The resolution plan was presented before edits: branch from verified main,
port only AFP source/runner/manifest/fixtures/tests, retain current-main state,
repair those bounded contract gaps, and prepare isolated manual-only workflow plumbing.
No merge or rebase of the draft branch was performed. The new branch is
`codex/ph-afp-integration-20261006`, based directly on the main SHA above.
The replacement draft PR supersedes #79 only after its contents are verified;
the old branch is retained. Delivery status is recorded in GitHub.

## What is retained and strengthened

| Contract | Integration behavior |
|---|---|
| First-party provenance | Official AFP frontend/backend route; institution attribution distinct from NSC, DND and Coast Guard |
| Identity and duplicates | Integer id cross-checked with slug; different ids stay distinct; original records immutable; revisions append linked captures; view counters do not invent revisions |
| Publisher dates | Source offset/local date/original timestamp/exact fractional UTC instant retained; unknown offset and calendar overflow refused; migration limits and listing/detail disagreements disclosed |
| Complete discovery | Every returned page walked to explicit `next:null`, stable count reconciled, page/content/id/slug repetition and missing/malformed pages fail; no hard-coded 1,088 count |
| Complete window | Cap overflow or malformed identity/title/date metadata fails before detail requests; rejection reasons remain visible |
| Current policy | Both hosts checked, bounded plain-text UTF-8 policy required, applicable named/wildcard groups combined with precedence, supported delays observed, unsupported patterns/delays fail closed |
| Access failures | Challenges including HTTP 200 and 401/403 stop requests; redirects checked before requesting a hop; HTTP auto-follow disabled; bounded transport retries |
| Exact originals | Detail captures preserve UTF-8 bytes; bounded robots/listing/refusal payloads and all attempt receipts appended by hash; oversized payloads have receipts without retained bodies |
| Failure/clock | Completed failure/partial attempts exit nonzero and cannot start/advance the success clock; exclusive ledger/clock writes and duplicate attempt preflight |
| Isolation | Manifest outside `desks/`; disabled CLI gate; state outside every checkout; internal symlinks and unsafe run ids refused; no production pipeline/renderer registration |
| Publication gate | Immutable historical files and DB rows, payload hashes, attempt/collector identity, exactly one completed ledger and closed DB hash checked; crash/unverified state cannot be pushed |
| Workflow | Manual-only GitHub-hosted rehearsal; full listing then at most two recent samples; artifact-only by default; optional isolated append-only state; completed failures remain job failures |
| Owner access decision | Direct AFP infrastructure only, proxy inheritance disabled, public first-party API approved for shadow evaluation, honest IPR identity uses the existing About contact route |
| Policy change gate | Fresh robots fetched and dynamically enforced; reviewed hashes/statuses and API indexing header pinned; changes stop for owner review with evidence |
| Rehearsal scope | Explicit sample counts, at most 14 lookback days, no success-clock start/advance; empty or incomplete sample retrieval fails |

The adapter/runner are ported from PR #79 with these corrections; the new
publisher verifier and prepared workflow are local integration additions.
The manifest retains `enabled:false` and `active:false`. No source enters the
production registry. No existing workflow schedule changes.

## Captured evidence and verification

All 15 original responses from the prior October 6 identified bounded
rehearsal were recovered from its retained scratch captures and hash-verified:
two robots responses, 11 complete listing pages, and two detail responses.
They total 1,376,445 bytes and are now durable fixtures under
`tests/fixtures/ph_afp/live_20261006/`, with exact URLs, retrieval times,
statuses and hashes in `requests.json`. There were **zero new live AFP requests**
in this integration. This does not refresh access or prove Actions egress.

Offline replay walks/reconciles **1,088 rows over 11 pages**, obtains 11 recent
references for September 22–October 6, and replays both sampled bodies:
`afp:1396` (October 6, 1,481 characters) and `afp:1395` (October 5, 1,291).
A repeated two-body runner rehearsal confirms exact originals, duplicates,
immutable history and publisher verification. No full-history body corpus is
created. The September 26 pilot's discarded full-corpus counts remain
producer-reported and unverified, as recorded in
[the pinned historical repair receipt](https://github.com/VSSpowerlifting/China-Mil-Watch/blob/b29e7edb047c30c8b878bca0069ba183424e2478/docs/AFP_PR79_OFFLINE_REPAIR_2026-10-01.md).

| Local check | Result |
|---|---|
| AFP, current contract, NSC, manifest, logical-date and isolation checks | 538 tests passed after manual rehearsal and fractional-timestamp corrections (the preceding candidate passed 529) |
| Workflow definition | Parsed with system Ruby YAML; workflow_dispatch only, sample limit two, publication default false |
| Workflow shell | All block scripts pass `bash -n` |
| Publication rehearsal | Exact prepared shell block against an isolated local bare remote: only `shadow/ph-afp` created; competing writer rejected, remote head preserved |
| Full repository suite | Preceding candidate: **3,410 tests passed, two skips, exit 0**, 1,105 s. **Final continuation full run: 3,419 passed, two skipped, exit 0, 974.566 s**, after UTC/font corrections and before the final ID guard; 538 focused contract tests passed after that narrow guard |
| Deploy validator | Passed with exactly 10 governed warnings; no output regeneration |
| Production preservation | DB hash unchanged, all 7,410 output files byte-identical, no SQLite sidecars |
| Structural map | `graphify update .` passed; ignored code AST map only, no tracked generated-output changes |

Source and transcript hashes are in
[verification.json](research/afp-integration-20261006/verification.json).
Checks use the existing same-repository environment at
`/Users/benjaminyang/pla-watch/.venv/bin/python`, with bytecode writes disabled.
No dependencies were installed. No passing GitHub CI, deployment, scheduled workflow
or periodic reliability result is claimed.

## Owner decisions and remaining evidence gates

Ben authorized direct official AFP infrastructure only, public first-party API
use for shadow evaluation, honest IPR identification using the existing public
contact route, and public isolated `shadow/ph-afp` state on October 6. Those
constraints are recorded in `DECISION_LOG.md`. The existing canonical IPR domain
and About page with editor email were inspected before changing the identity.
The original captured responses used the old identity; replay with the new one
is offline verification, not proof of live acceptance.

The workflow is technically prepared for a manual GitHub-hosted rehearsal.
It traverses the full listing before selecting at most two recent bodies, fails
on access/policy/metadata/pagination/retrieval errors, retains request evidence,
and never advances the reliability clock. Artifact-only state is the default;
optional public state publication requires append-only verification and an
explicit non-force state ref. No actual state branch has been created or changed.

The workflow must exist on the default branch for dispatch, per
[GitHub documentation](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).
Required sequence:

`review draft PR → explicitly authorize and merge shadow-only plumbing → manually dispatch rehearsal → inspect evidence → separately decide whether to enable recurring schedule`

No merge is authorized here, and no branch-dispatch workaround is attempted.
The exact next action is review of the replacement draft PR and explicit owner
merge authorization. After that merge, the artifact-only dispatch command is in
`shadow/ph_afp/README.md`. Live Actions egress still requires verification.

The captured listing has no 2025 rows and none dated November 1, 2024 through
June 11, 2026. These are listing gaps, not institutional silence. Publisher
API dates may reflect migration, so historical dates remain caveated. No OCR,
transcription, invented dates or full-history body adequacy claim is introduced.
Graduation still requires sustained collecting-date reliability, substantive
body sampling, migration/date assessment, Philippines review tools, completed
human checkpoints and owner sign-off. Neither AFP nor AFP+NSC is qualified.
DND/Coast Guard expansion and Japan's coverage repair are outside this PR.

## Shared validation fixture correction

The first continuation full run completed 3,418 tests with one failure and two
skips. Japan PR #108 CI independently failed the same existing
`test_terrain_motion_is_decorative_and_has_static_fallbacks` assertion: the
Analysis title moved by 23.984375px while decorative motion was inspected.
Eight instrumented private page loads reproduced that position change as fonts
changed from loading to loaded, with masthead/navigation geometry unchanged.
This is a fixture race, independent of both collector implementations.

The geometry test now waits for used fonts to settle, with a 30-second failure
timeout. Its exact box equality and animation/fallback assertions are unchanged;
no frontend source or production output changes. All 11 page-shape tests pass.
The correction is a separate test-only checkpoint so it can also accompany
Japan's preserved correctness commit without rewriting history. The complete rerun passed 3,419 tests with two skips after this correction
and the fractional-date regression. A subsequent ASCII-decimal ID guard
rejects digit-like non-decimal characters instead of crashing integer
conversion; all 538 focused contracts pass after that narrow change. Both
verification scopes and source hashes are retained in the JSON receipt.

## Exact changed-file inventory

- `.github/workflows/ph_afp_shadow.yml`
- `DECISION_LOG.md`
- `PROJECT_STATE.md`
- `docs/AFP_SHADOW_INTEGRATION_2026-10-06.md`
- `docs/research/afp-integration-20261006/verification.json`
- `scraper/sources/ph_afp.py`
- `scripts/check_ph_afp_state.py`
- `scripts/shadow_collect_ph.py`
- `shadow/ph_afp/README.md`
- `shadow/ph_afp/manifest.json`
- `tests/fixtures/ph_afp/detail_1211.json`
- `tests/fixtures/ph_afp/detail_1312.json`
- `tests/fixtures/ph_afp/detail_1330.json`
- `tests/fixtures/ph_afp/detail_1331.json`
- `tests/fixtures/ph_afp/detail_1365.json`
- `tests/fixtures/ph_afp/detail_1378.json`
- `tests/fixtures/ph_afp/detail_1384.json`
- `tests/fixtures/ph_afp/detail_834.json`
- `tests/fixtures/ph_afp/detail_949.json`
- `tests/fixtures/ph_afp/list_page_default.json`
- `tests/fixtures/ph_afp/list_page_invalid.json`
- `tests/fixtures/ph_afp/list_page_last.json`
- `tests/fixtures/ph_afp/live_20261006/.gitattributes`
- `tests/fixtures/ph_afp/live_20261006/01.bin`
- `tests/fixtures/ph_afp/live_20261006/02.bin`
- `tests/fixtures/ph_afp/live_20261006/03.bin`
- `tests/fixtures/ph_afp/live_20261006/04.bin`
- `tests/fixtures/ph_afp/live_20261006/05.bin`
- `tests/fixtures/ph_afp/live_20261006/06.bin`
- `tests/fixtures/ph_afp/live_20261006/07.bin`
- `tests/fixtures/ph_afp/live_20261006/08.bin`
- `tests/fixtures/ph_afp/live_20261006/09.bin`
- `tests/fixtures/ph_afp/live_20261006/10.bin`
- `tests/fixtures/ph_afp/live_20261006/11.bin`
- `tests/fixtures/ph_afp/live_20261006/12.bin`
- `tests/fixtures/ph_afp/live_20261006/13.bin`
- `tests/fixtures/ph_afp/live_20261006/14.bin`
- `tests/fixtures/ph_afp/live_20261006/15.bin`
- `tests/fixtures/ph_afp/live_20261006/requests.json`
- `tests/fixtures/ph_afp/robots_api_404.html`
- `tests/fixtures/ph_afp/robots_www.txt`
- `tests/ph_afp_support.py`
- `tests/test_home_paired_records.py`
- `tests/test_ph_afp_adapter.py`
- `tests/test_ph_afp_readiness.py`
- `tests/test_ph_shadow_runner.py`
