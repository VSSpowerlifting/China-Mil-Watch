# AFP Actions gate — 2026-10-06

Owner's continuation brief authorizes reviewed Japan/AFP merges and one bounded,
artifact-only AFP GitHub-hosted rehearsal. It explicitly requires stopping before
merge if CI fails. This is the rehearsal checkpoint. Recurring shadow collection was subsequently
owner-authorized below; production activation, DB/output generation and
deployment remain unapproved.

## Authorized geometry repair and current gate

Ben's subsequent continuation authorizes diagnosing and repairing the failed
geometry contract, obtaining fresh green exact-head CI, then guarded merge and
one bounded artifact-only rehearsal. Scheduled collection was unapproved at that gate; see the later owner decision below.

The original phone test was run twice against a scratch copy of current main's
corpus: both stacks failed on both repetitions. The complete headline was at
822.46875–850.734375px, entirely inside the 900px viewport. Computed CSS
line-height was 28.272px; both its actual height and a natural one-line clone
were 28.265625px. Fonts were loaded, and waiting another second changed nothing.
Changing only diagnostic line-height to 28px made computed/rendered heights
agree; restoring 28.272px restored the mismatch. This identifies a comparison
between nominal CSS and actual browser layout geometry, not viewport clipping.

The test-only repair measures a hidden natural one-line clone in the same style
context, outside document flow, and compares visible height with that rendered
height. It adds no numerical tolerance and changes no CSS or collection code.
A new real-browser regression failed before the repair, then passed: a complete
line is accepted, but one CSS pixel of viewport clipping or constrained-element
clipping is rejected. All 17 viewport, structural-spacing and page-shape tests
passed against current main's scratch corpus in 24.644 seconds; the same 17
checks passed against the branch's original corpus in 28.203 seconds. Diagnostic logs
are under `/tmp/ipr-desk-audit-20261006/`; no debug instrumentation is retained
in source. Fresh exact-head PR CI subsequently passed before the guarded merge.

The original AFP preparation receipt remains a historical receipt; its pinned
home-test hash precedes this authorized repair. The nine AFP-specific source
hashes remain unchanged. Tracked production DB/output were not modified.
Repaired `tests/test_home_paired_records.py` SHA-256:
`a20b1773b33d8535d48c2385fe301bf94294509d61389ce87ce9cf044bb65ebb`.

## Final observed GitHub outcome

1. **Japan #108:** exact head `f1127619218eb9dd2db9a79074193fd4e2828d8c`
   passed [CI 37496649400](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37496649400):
   3,205 tests, two skips, validator with ten warnings and DB/output immutability.
   Merged as `ef89d5f3d11bf5a8ebb7e6be2c73785c6f10fb5c`. Japan's measured
   1.49% full-text coverage limitation remains unresolved.
2. **AFP #109:** fresh [CI 37524618783](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37524618783)
   passed on exact head `31719bed3d5b4c5de0b248a8d2b9b1be06e66e2c`:
   3,436 tests, two skips, validator with ten governed warnings, DB/output
   immutability. The new clipping regression ran and passed. Exact-head guarded
   repository-standard merge commit:
   `cc8d36646af1e2eb6026a17eaefd20378585faac`, merged at 20:38:04 UTC.
   All nine AFP-specific pinned source hashes remained unchanged.
3. **Ready-triggered CI:** marking ready triggered run `37518285261` on original
   head `42a7466a8`. Existing concurrency cancelled it after deliberate conflict
   follow-up `0ab1eccf5`. That follow-up's run `37518846754` failed the two phone
   geometry subtests; merge and live dispatch stopped. Ben subsequently
   authorized the diagnosed repair. The final fresh run above replaced that
   failed gate; no incomplete or failed check was bypassed.
4. **Manual rehearsal:** [run 37527985057](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37527985057),
   attempt 1; `workflow_dispatch` on main, `publish_state=false`, no target-date
   override. Actual collector commit and run head both match the merge SHA.
5. **Conclusion:** success. Collection ran 20:39:05–20:39:41 UTC, target date
   `2026-10-06` from `manual-utc-date`. Collector cleanliness and completed-attempt
   verification passed. State-publication and incomplete-collection steps skipped.
6. **Listing:** 1,090 unique rows; eleven pages (ten × 100, then 90), stable
   reported count 1,090, terminal `next:null`, no count mismatch. Listed publisher
   dates span 2021-01-21–2026-10-06. Compared with retained preparation originals,
   only IDs 1397 and 1398 were added: no rows removed or existing slug/publication
   timestamp changed. Thirteen recent eligible items were discovered; eleven
   were explicitly `sample_unselected`. Two category rejections and 1,075
   outside-window rejections were recorded. No cap overflow or silent truncation.
7. **Bodies:** two requested, two retrieved and stored with text:

   | Identity | Original publication timestamp | UTC timestamp | Text characters |
   |---|---|---|---:|
   | `afp:1398` | `2026-10-06T13:01:00+08:00` | `2026-10-06T05:01:00+00:00` | 980 |
   | `afp:1397` | `2026-10-06T12:58:00+08:00` | `2026-10-06T04:58:00+00:00` | 1,325 |

   Captured titles: “AFP Chief Visits AMC, Recognizes Role in Sustaining Visayas
   Missions” and “AFP Chief Recognizes Naval Personnel, Underscores Maritime
   Readiness.” Both detail requests and final URLs were identical direct
   `https://api.afp.mil.ph/articles/<slug>/` endpoints, HTTP 200/application-json.
   Canonical URLs use `https://www.afp.mil.ph/news/<slug>`. Original payloads
   (2,484 and 2,593 bytes) are retained in SQLite captures; detail receipt
   `payload_retained=false` means no duplicate evidence-file copy, not loss of
   original bytes. Independently checked SHA-256 values:
   `c4284c9e577878556ff87a0b6aa4c41bd4c03da489cf0419baf22658cd80b34e`
   and `c5b160cba53b9111799268dee6003ec5d539633fcc94b804c82e96c366c3a5bf`.
   Listing/detail IDs, slugs and original/derived timestamps agree. Full extracted
   text was inspected against the captures; no OCR, translation or inferred text.
8. **Robots/access:** fifteen requests total, all requested/final hosts official.
   Fresh www robots: HTTP 200, `User-agent: *`, `Allow: /`, SHA-256
   `befa30284d46cf89ba3ab58ba65af7e987be472e9efcdd368c98cea0530e378b`.
   Fresh API robots: reviewed HTTP 404, SHA-256
   `5547992afdadb59737c5c0feb1a35dff294cd27145bf290c031737ecf8a2577d`,
   `X-Robots-Tag: noindex, nofollow`. Both hashes match the pinned policy;
   API listing/details also retained that header. Collector identity was the
   explicit `IndoPacificRecord-ShadowCollector/0.1` with IPR About-contact URL.
   No proxy, browser impersonation, access-control bypass or policy edit.
9. **Failures/anomalies:** none recorded for access, fetch, extraction, redirect
   refusal or identity collision; audit found none. Nine same-title/date groups
   remain explicit publisher metadata observations, never merged as duplicates.
   Ordinary listing growth is explained above; no material access or identity/date
   change was observed. This proves only the bounded attempt, not full-window body
   coverage, historical completeness, truth of publisher claims or future reliability.
10. **Artifact:** [ph-afp-shadow-37527985057-1](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37527985057/artifacts/11442459154),
    ID `11442459154`, 302,604 bytes, seventeen files, retention 90 days (expires
    2027-01-04). Uploaded ZIP SHA-256:
    `55f830bed29760d9a29523fc061ff9c3cb08df200168706690dec9d6e3c06830`.
    Downloaded and inspected: finished ledger, fifteen request receipts, robots
    and listing originals, closed shadow DB with two exact original detail
    captures, and run log. Local audit re-ran the completed-attempt verifier,
    reconciled raw pages, checked capture hashes/metadata and read both bodies.
    Local evidence is under `/tmp/ipr-desk-audit-20261006/`; the linked Actions
    artifact is the retained live original.
11. **State:** only temporary artifact state was produced. No `shadow/ph-afp`
    branch exists; publication was skipped. Main, gh-pages and every existing
    shadow ref are byte-for-byte unchanged across the rehearsal. No clock file
    exists and `shadow_day` is null; no collection reliability clock advanced.
12. **Production/schedule:** AFP manifest remains disabled outside `desks/`;
    no Philippines/Japan production activation, recurring AFP cron, production
    DB/output generation or deployment. Actual AFP merge DB/output/desks object
    IDs exactly match pre-merge main. The existing daily workflow's earlier
    independent updates are not AFP rehearsal writes.
13. **Subsequent owner decision:** Ben reviewed this live evidence and authorized
    recurring AFP shadow collection at 06:40 UTC with isolated durable state.
    The scheduling PR implements the ongoing/manual distinction and shadow
    manifest enablement; clean exact-head CI, final review and separate merge
    authorization remain required before the cron is live. This two-body rehearsal does not authorize them or qualify
    a desk. Later qualification still requires the collecting period, human
    checkpoints, coverage/date assessment and owner sign-off under shadow doctrine.

## Scheduling continuation and delivery state

The repaired integration head `31719bed` merged via #109 after fresh green CI.
Ben's subsequent scheduling brief authorizes recurring AFP shadow collection
only, durable `shadow/ph-afp` state, first-party access, preservation and reliability
evaluation. It explicitly requires a PR and separate merge decision after clean
CI. The requested branch `codex/ph-afp-scheduled-shadow-20261006` starts from
current main `a8e6d5a266cf6dadc664e899905a4ad9dbf47732`, including the later
#110 merge. The two local post-run checkpoint files were preserved and reconciled
on that branch; no later main documentation was discarded. This checkpoint and
`PROJECT_STATE.md` are included in its documentation commit. Historical captured
originals remain unchanged. No additional live attempt was dispatched.

The proposed cron is exactly `40 6 * * *`; scheduled normal collection passes
`--cron-utc "06:40"` to the shared date resolver, keeps the 14-day/cap-100/revision
watch defaults, and publishes only verified successful state. Manual dispatch
stays a two-body rehearsal with publication false by default; explicit publication
still cannot start its clock. Failed/partial collection blocks durable publication
and retains inspectable artifacts. No production integration, full historical
body backfill or deployment is included. Full operating/review requirements are
in `shadow/ph_afp/README.md`; owner authorization is in `DECISION_LOG.md`.

After a separately authorized merge, seven consecutive terminal-successful
scheduled collection days and durable human sampling precede a new readiness
assessment. Seven days alone never qualify or automatically promote a desk.
