# AFP Actions gate — 2026-10-06

Owner's continuation brief authorizes reviewed Japan/AFP merges and one bounded,
artifact-only AFP GitHub-hosted rehearsal. It explicitly requires stopping before
merge if CI fails. No recurring AFP schedule, production activation, DB/output
generation, or deployment is authorized.

## Authorized geometry repair and current gate

Ben's subsequent continuation authorizes diagnosing and repairing the failed
geometry contract, obtaining fresh green exact-head CI, then guarded merge and
one bounded artifact-only rehearsal. Scheduled collection remains unapproved.

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
in source. Fresh exact-head PR CI is still the merge gate.

The original AFP preparation receipt remains a historical receipt; its pinned
home-test hash precedes this authorized repair. The nine AFP-specific source
hashes remain unchanged. Tracked production DB/output were not modified.
Repaired `tests/test_home_paired_records.py` SHA-256:
`a20b1773b33d8535d48c2385fe301bf94294509d61389ce87ce9cf044bb65ebb`.

## Observed GitHub outcome before repair authorization

1. **Japan #108:** exact head `f1127619218eb9dd2db9a79074193fd4e2828d8c`
   passed [CI 37496649400](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37496649400):
   3,205 tests, two skips, validator passed with ten warnings, tracked DB/output
   unchanged. Merged with the repository's merge-commit method as
   `ef89d5f3d11bf5a8ebb7e6be2c73785c6f10fb5c`. This is a policy correctness
   repair; Japan's 1.49% measured full-text coverage limitation remains unresolved.
2. **AFP #109:** original head `42a7466a801cb81dd8ce8dd282185cc2503bd8a7`
   passed [CI 37496598354](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37496598354)
   with 3,419 tests, two skips and the ten-warning validator baseline. Final
   review confirmed the shadow/manual-only bounds and narrow ASCII ID guard.
   The current PR is ready, open and mergeable, but **not merged**: latest
   exact-head CI failed on `0ab1eccf5c01d9a1227d609beb634765663de609`.
3. Marking AFP ready triggered [run 37518285261](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37518285261).
   Japan's merge exposed the anticipated `PROJECT_STATE.md` insertion conflict.
   Deliberate reviewed follow-up `0ab1eccf5` changes only that document, relocates
   the AFP paragraph, and records Japan's merge and #79's closure. All ten
   reviewed collector/workflow/test source hashes remain unchanged. GitHub
   cancelled the superseded ready run through existing concurrency; the new
   head's [run 37518846754](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37518846754)
   became the merge gate and failed.
4. **Manual AFP rehearsal run ID/URL:** none; no dispatch was performed.
5. **Rehearsal conclusion:** not run.
6. **Live GitHub-hosted listing count:** not observed. The earlier captured
   1,088-row listing is not a result from this task.
7. **Article bodies requested/retrieved by a live rehearsal:** 0 / 0.
8. **Live robots/access result:** not observed; no AFP live requests were made.
9. **Failure:** `Run offline test suite` failed after 3,435 tests with two
   failures and two skips. Both failures are
   `TestTheRecordReachesTheFirstViewport.test_the_headline_is_legible_where_it_starts_on_a_phone`,
   for `native` and `wide` font stacks, at `tests/test_home_paired_records.py:1587`:
   visible headline height `28.265625px` is below computed line height `28.272px`
   (difference `0.006375px`). Root cause is not established by the traceback.
   No test or production layout repair was attempted after this stop.
   Output validation was skipped; the always-run DB/output immutability step
   passed. No live access, challenge, identity or timestamp conclusion follows
   from these offline results.
10. **Rehearsal artifacts:** none. CI traceback and job metadata are available
    in the linked failed Actions run; local copies were recovered under
    `/tmp/ipr-desk-audit-20261006/`.
11. **AFP shadow state:** no `shadow/ph-afp` branch exists; no state publication
    or reliability clock was started by this task.
12. **Scope retained:** no recurring AFP cron, Philippines/Japan production
    activation, production DB/output generation or deployment was performed.
    The existing daily update independently advanced main before the Japan
    merge. GitHub's proposed AFP merge preserved main's DB/output/desks object
    IDs; the local working tree's tracked production files were unchanged.
13. **Remaining gates:** diagnose the phone geometry failure against current
    main without weakening the one-rendered-line contract; review any repair
    and obtain green full CI on the exact AFP merge head; perform a guarded
    merge; then dispatch once with `publish_state=false` and no target-date
    override and inspect actual artifacts. Live GitHub egress remains unproven.
    Recurring shadow collection still needs a separate owner decision and a
    reviewed ongoing-mode workflow, manifest enablement and isolated durable
    state publication. No schedule is enabled here.

The initial stop was recorded locally without committing. The authorized repair
will receive a new reviewed head and fresh CI; the failed check is not bypassed.
The AFP workflow lookup on the default branch returned HTTP 404 while unmerged.
