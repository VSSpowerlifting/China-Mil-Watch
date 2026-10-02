# Philippines NSC adapter — review receipt

**2026-10-01 · branch `claude/pnsc-adapter-build-eae248` · based on main `61b96cdce` · nothing committed, nothing pushed**

One disabled adapter for the National Security Council's *Official Statements* category, built
offline against four preserved captures. It has never made a request to the live site, and no
production path can reach it. This change closes none of the open gates below.

## Verdict

| Question | Answer |
|---|---|
| Ready to review as a local diff | Yes |
| Safe to commit as an inert module, once authorized | Yes. Nothing imports it, no desk or workflow names it, and tests assert both. |
| Safe to enable, schedule, declare as a desk, or rehearse live | **No.** Seven gates are open (below), and gates 6 and 7 come first. |
| Source status | Unqualified. No shadow collecting day exists for it (DECISION_LOG). |

## Scope and checkout

- Worktree `/Users/benjaminyang/pla-watch/.claude/worktrees/pnsc-adapter-build-eae248`, branch
  `claude/pnsc-adapter-build-eae248`, HEAD `61b96cdce` (merge of PR #91). That is `origin/main`,
  fetched 16:17 EDT and re-read with `git ls-remote` at 17:07 EDT: still `61b96cdce`. **Diff
  against `origin/main`, not `main`:** the local `main` branch is stale (`e309ce79b`, 2026-09-05,
  191 commits behind).
- Input: `IPR-Philippines-Alternate-Source-Evaluation-2026-10-01.zip`, sha256
  `880e330b594709fe722d952abb2a6b7ce150b83dcd7cf5fbe8dbc4b06e237b54`, 420181 bytes (hash
  re-checked at the end of the work). Used: the four NSC captures, the three NSC diagnostic JSON
  files and the packet's ten-row request ledger. The WPS Transparency and FSI captures were not
  copied.
- **Not touched:** draft PR #79 (AFP; its branch commit `b29e7edb0` was read with `git show` and
  nothing else), `scraper/sources/ph_afp.py`, `shadow/ph_afp/`, the Singapore desk and its review,
  `desks/` (still `china`, `singapore`, `registry.json`), `output/`, `pla_watch.db`, every
  workflow, `pipeline.py` and `core/`. No request was made to nsc.gov.ph or any collection host;
  the only network traffic was `git` against origin, to verify the base. No schedule, desk
  registration, commit or push.
- Changed in the working tree: `PROJECT_STATE.md` (one note, placed at the end of §5, far from the
  AFP paragraph PR #79 inserts), plus the new paths below.

| Path | What | Size |
|---|---|---|
| `scraper/sources/ph_nsc.py` | the adapter, `PHNscAdapter` | 750 lines |
| `shadow/ph_nsc/manifest.json` | shadow manifest, `enabled: false`, deliberately outside `desks/` | 87 lines |
| `shadow/ph_nsc/README.md` | evidence, retrieval order, the seven gates | 166 lines |
| `tests/test_ph_nsc_adapter.py` | offline tests, 16 classes | 89 tests, 1276 lines |
| `tests/fixtures/ph_nsc/` | four captures, three diagnostics, the ledger, `.gitattributes` (`* binary`) | 9 files |
| `docs/PH_NSC_ADAPTER_REVIEW_RECEIPT_2026-10-01.md` | this receipt | |

## Initial verification (Claude-reported; before continuation)

| Check | Result |
|---|---|
| `tests.test_ph_nsc_adapter` | 89 of 89 pass, offline. A socket guard fails any real connection; one test proves the guard is live. |
| Full suite, `unittest discover -s tests -t .` | 3080 tests, `OK (skipped=2)`, exit 0, one run of 810 s, no failures or errors. It started after the last change to the adapter, the tests, the manifest, the README and `PROJECT_STATE.md`; only this receipt changed afterwards. The skips are in other modules, and the NSC module has none: one release-readiness check on a stale corpus snapshot, one home-page check that applies only when a single desk collects. |
| Guard suites run on their own first | `test_user_agent_identity` 9, `test_no_frozen_corpus_counts` 42, `test_adapter_contract` 23, `test_manifests` 31, `test_extraction_interface` 23, `test_desk_rollout_contract` 36, `test_us_dvids_adapter` 67, `test_singapore_shadow` 37, `test_pipeline_compat` 44: all pass |
| Mutation check | 30 deliberately broken copies of the adapter, held in memory and never written, each fail at least one test. None survived. The harness is not in the repo, so this result is reported, not reproducible from the diff. |
| Fixture bytes | All eight data files are byte-identical to the packet's (`cmp`). The four captures match the ledger's sha256 and byte counts. Git applies no filter to any of them (`hash-object --path` equals `--no-filters`). |
| Not run | `scripts/validate_output.py` (no output was changed; the "10 governed warnings" baseline is therefore untouched and unmeasured here). `graphify update .`: `graphify-out/` exists only in the main checkout, untracked and not ignored, so running it here would add an untracked directory to this diff. |

Two real defects were found after the first green run, and both are fixed and guarded:

- A test written to kill the "widget not excluded" mutant exposed that the first version excluded
  the "Latest Post" widget only when its class list held the exact token `wp-block-latest-posts`.
  It now matches the prefix. Two mutants (prefix removed, exact token restored) fail on it.
- Final review found that request spacing was recorded only after a response arrived, so a request
  that failed fast (a reset, a TLS error) let the next one go out at once, which is the moment the
  host is least able to take it. A failed attempt now counts. The new test fails on the old
  ordering, and so does a mutant restoring it.

## Findings

Findings are about this change, ranked by what they block.

**P0: none.** Nothing here can run, import or register itself.

**P1: block any live use**

1. **Repository-client behaviour is unobserved.** The captures came from urllib; the adapter uses
   `requests`. Same `User-Agent`, `Accept-Encoding: identity`, no redirects and no cookies replayed
   narrow the gap, but `requests` still adds its own `Accept` and `Connection` headers, and TLS,
   header order and proxy identity are unmeasured. (gates 1, 7)
2. **Collector identity is undecided.** The captures and the adapter use
   `ChinaMilWatch-ShadowCollector/0.1`. The AFP inquiry sent on October 1 states `ChinaMilWatch/1.0`,
   the identity `tests/test_user_agent_identity.py` pins. The one-line change is `USER_AGENT`, and a
   fixture test fails until the decision is recorded. (gate 6)
3. **Completeness of discovery is unobserved.** The captured category page lists six items and
   publishes no pagination at all. The adapter proves coverage of the requested window or fails
   whole with no references; with the captured page, a window reaching back to 2026-06-03 or
   earlier cannot be proven and fails. How older statements are reached is unknown. (gate 4)

**P2: design choices to confirm**

4. **Window membership uses the date the page states, in the offset it declares** (every captured
   stamp is +08:00), with the UTC instant stored beside it. A stamp without an offset is refused.
   A statement stamped just after midnight in Manila belongs to the Manila date, not the UTC one.
5. **Fail closed on page shape.** A theme change that removes or duplicates any expected element
   stops collection until someone re-reads the page. This is deliberate while the category anomaly
   is unresolved, and the cost is brittleness.
6. **The spam tripwire is weak evidence.** Its two marker strings come from the packet's prose about
   a page that was never captured. The positive structure checks are the real defence.
7. **Two robots matchers will exist** once PR #79 lands. Unify them then; no shared helper was
   created here so that PR is not touched.
8. **The manifest's desk block copies AFP's functional fields.** Which file keeps it once both
   sources are declared is an owner decision, noted in the manifest.
9. **The attribution key differs from its siblings.** The `extra` provenance keys
   (`source_identity`, `published_at_utc`, `published_at_original`, `publication_kind`,
   `content_sha256`, `capture_sha256`, `retrieved_at`) are the ones DVIDS and PR #79's AFP adapter
   use. Both of those store attribution as `byline`; this adapter stores `site_byline` and
   `site_byline_url`, because the NSC byline is always "National Security Council" and names the
   host, not the issuing office, which is the packet's own site-byline-versus-stated-author
   distinction. A consumer reading `byline` across the Philippines desk will find none for NSC.
   Nothing in storage reads these keys today (`insert_article` writes only the URL, content hash,
   title, text and date), so whichever runner comes later decides where provenance lands. Not
   renamed to match an unmerged PR; harmonize when both sources are declared.

**P3: smaller**

10. `Crawl-delay` is not parsed (fixed 2 s spacing); robots paths are compared without percent-decoding.
11. Only a publication time exists on the page, so a later edit is visible only as a changed capture hash.
12. `production_lookback_days` keeps the base default of 0, so a rehearsal window must be explicit.
13. A quiet category returns `OK_NO_PUBLICATIONS`. The newest captured statement is dated 2026-07-08,
    almost three months before the capture.
14. Pagination forms the walker cannot follow (`?paged=`, `?query-N-page=`) are reported, and named
    in the failure only when they are all that stands between the run and coverage.

## What the tests cover, and what they do not

Offline, against the real capture bytes or variants of them built in memory (never written back):

- **Extraction.** Canonical URL, title, publication date with its own offset, byline, and the whole
  `entry-content`, reproducing the packet's body character counts (1272 and 1808) and boundaries;
  the sidebar is excluded, including a widget placed inside the body; a recurring title keeps its
  own identity; the sidebar date and the `<title>` tag are never borrowed; the listing id, URL and
  date are cross-checked.
- **Challenge and anomalous pages.** Challenge on robots, listing and article stops the run with
  no content retained or retried; the passive Cloudflare script alone is not a challenge; spam,
  parked, maintenance and changed-template pages are refused for their own stated reason, and a
  listing with no items is a shape change, not a quiet day.
- **Robots.** The matcher (groups combined, named agent before `*`, longest match, Allow wins ties,
  wildcards, anchors, BOM and CRLF), and the adapter's use of it: robots first, re-read every run,
  every request checked before it is made, and 401/403/5xx/HTML/oversize all stop the run.
- **Pagination.** Window coverage proven or refused; repeated page, overlapping item, duplicate
  within a page, loop, skipped or foreign next link, two different next links, advertised-but-missing
  pages, unsupported forms, wrong order and the page cap each fail the whole run with zero
  references, never a partial list.
- **Transport and isolation.** Headers, spacing (including after a request that failed), cookies,
  redirects, retries, statuses, content types, size limits; `load_all_desks()` still returns only
  `china` and `singapore`; nothing in production code, workflows or `desks/` names the adapter;
  the adapter imports nothing that stores or reaches production.

**Not covered, and not coverable offline:** any real response from nsc.gov.ph through the
repository client; TLS and proxy behaviour; GitHub Actions egress; repeat runs or rate limits; and
the real form of NSC's pagination if it ever has one. The multi-page tests use synthetic pages in
the standard WordPress query-pagination markup, built around the real listing; that NSC would emit
this form is an assumption.

## Open gates

None is closed by this change. Wording and evidence: `shadow/ph_nsc/README.md`.

1. Repository-client compatibility: unmeasured.
2. Reliable periodic access: unmeasured.
3. Reuse permission: not reviewed.
4. Discovery completeness: unobserved.
5. Category anomaly: unresolved. A one-off gambling-content response in the packet is neither
   dismissed nor treated as a compromise.
6. Collector identity: undecided.
7. Live remeasurement with the repository client: not performed. The packet asks for it; the
   brief forbade live requests.

## Remaining action

1. Review this local diff, including the offline continuation below: `git diff PROJECT_STATE.md` for the one tracked change, and for each new
   path above `git diff --no-index /dev/null <path>`, which reads an untracked file without staging it.
2. If it passes, authorize a commit on this branch and a **draft** PR, separate from PR #79.
3. Owner decision on gate 6 (identity). Then, only if authorized, one bounded live rehearsal under
   that identity with the window stated in advance: robots, the listing, two statements. That
   measures gates 1, 4, 5 and 7; gates 2 and 3 need a multi-day observation and a terms review.


## Offline continuation in ChatGPT (2026-10-01 New York)

The owner's exported `pnsc-adapter-build-eae248.zip` was unpacked into an isolated scratch copy.
Its Mac `.git` pointer cannot provide ancestry here and was not reused. Current GitHub main was
read-only verified as `61b96cdce597236036988c4c60fe8f7b15f97f78`, matching the reported base;
no repository or PR state was written. The original Mac worktree remains unchanged.

The export already contained Claude's F1–F3 source fixes, but not their new regressions. This
continuation adds eleven tests (100 NSC tests total) for legitimate challenge-like titles and
quoted text, malformed URLs and timestamp overflow yielding failure statuses, spacing after
slow/failed streamed bodies, and the hosting byline not becoming an inferred issuer/author.

Two further failures were reproduced and repaired:

- A required later page repeated a URL under a changed post ID and returned `ok`. Traversal now
  checks URL overlap as well as post-ID overlap, refusing the whole discovery result.
- A normal-themed page containing an active challenge form or configuration script returned
  `ok` (two failing subcases). These structural indicators now stop access regardless of theme
  classes. Plain quoted phrases and legitimate titles remain accepted.

**Fresh NSC verification:** all 100 tests pass, with socket connections and DNS prohibited by
its module guard. Seven explicit in-memory mutations are detected: unrestricted challenge text
scan (6 failures), whole-document spam scan (2), theme suppressing active challenge structures
(2), missing listing parse boundary (1 error), missing extraction parse boundary (1 error),
spacing from headers only (2 failures), and checking pagination post IDs only (1 failure). These
are deliberately restored behaviors, not a recovered historical Git version of the adapter.
The reproducible harness and transcripts are included in the standalone continuation packet.

**Scope:** five files differ from the exported checkpoint: adapter, test module, PROJECT_STATE,
shadow README and this receipt. The exported manifest and all nine fixture-directory files
remain byte-identical. Before doc edits, 7,683 exported files were compared and only adapter and
tests differed; 7,230 protected files (output, production DB, desks, workflows and NSC fixtures)
were unchanged. Final preservation and broader verification results are in the continuation
packet's verification report.

The standalone patch checks against disposable originals. Its optional application helper
checks all five preimage hashes before writing, backs up originals and is idempotent. It never
stages, commits, pushes, enables collection or contacts collection hosts.

**Limits unchanged:** synthetic pagination and a window-crossing stopping criterion cannot
prove source-wide completeness or listing freshness. No general RFC-conformance claim is made
for the robots matcher: encoded-path normalization remains unverified. All seven live gates
stay open. Collector identity does not block review or an authorized offline draft PR. No live
requests, human attestations, production changes, commits or pushes were made.

**Broader checks are not a clean full-suite result.** The final broad attempt ran 2,995 tests
(15 skips), reporting two failures and two errors. One error was an import of `httpx` before
that dependency was installed; the telemetry module then passed all 57 tests separately with
connections prohibited. The remaining two failures and one error are frontend browser checks
(font fallback, governed contrast, metadata hit-testing). An isolated 91-test browser run
reported those same three plus a homepage resource-load failure. All four browser outcomes
reproduced in a separate, untouched copy of the uploaded export (four tests, three failures and
one error). They are not introduced by this five-file continuation, and no frontend code was
changed to repair them. This Linux/browser result is not equivalent to Claude's reported
3,080-test, two-skip result. Fresh discovery with installed dependencies finds 3,091 cases.
A fully configured local/CI run is still needed before claiming a clean full suite.
