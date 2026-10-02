# AFP PR #79 — offline repair receipt

## Authorized PR update preparation — 2026-10-01

This preparation supersedes the earlier uncommitted-only status below. The
owner authorized committing the nine reviewed repair files, a normal push to
existing draft PR #79, and its description update; CI and remote state are to
be checked afterwards. No live AFP access or production action is authorized.

PR head was freshly reverified at `916c7a340feeafa37e52cf6f4c12dbf1956fe7cb`.
Main advanced only through a daily database/generated-output update to
`60a6c1cc2a4550a1e48353f9aea43dd427b47423`; no source/test/status changes were
introduced by that update. It was integrated without conflicts in local merge
`3c291d83feed38cc67778a007413eb4abc39793e`, preserving merge `1b8df3086af9e9770efb85e8b316b043be718890`.
All 281 targeted tests pass again with socket connections prohibited. The repair
commit is restricted to the same nine files, with no production delta against
integrated main. All 29 original research hashes still match. The earlier
receipts and red/green transcripts below are retained as historical evidence.

---


## Review follow-up and local integration — 2026-10-01

This section supersedes the earlier readiness and conflict statements below;
the original receipt and transcripts remain as evidence of the first repair.
Offline repair verified; **not collection-ready**. No live AFP requests, pushes,
GitHub mutations, merges into main, schedules, renders or attestations occurred.

- Six new public-interface tests reproduced the three reviewer findings:
  **13 failing cases, no errors**, before the focused fixes. An additional HTML
  challenge-script regression failed before widening structural detection to
  include inline scripts. Those red transcripts are appended to the original
  evidence file.
- Robots groups matching the collector product token are combined before
  longest-path evaluation; Allow wins equal specificity. All wildcard groups
  are combined only as fallback when no collector-specific group matches.
  Per-request and redirect guards continue to stop before a denied request.
  Unsupported path-pattern syntax remains a conservative stop condition.
- Required pages are checked for repeated content and duplicate article id/slug
  before raw-row count reconciliation. Duplicates within a page also fail;
  silent deduplication cannot establish coverage. Incomplete discovery returns
  zero references, failed health and unchanged database/clock bytes.
- Explicit challenge headers still stop access. Body detection requires an HTML
  document and a challenge title or script route; valid article JSON containing
  “Just a moment” in title/body passes retrieval and extraction.
- Existing positive tests were corrected to exercise their intended conditions:
  the page-cap fixture uses distinct entries, rather than ending earlier on
  repeated identities; the longest article-path Allow case keeps the mandatory
  listing path permitted. The old duplicate-list test now expects failure.
  No stored fixture payload was changed.
- **281 targeted tests pass** in the actual registered combined checkout with
  socket `connect`/`connect_ex` prohibited, including its real worktree guard.
  This is a fresh combined-branch result, not a temporary archive assertion.

Fresh read-only GitHub verification before integration confirmed PR head
`916c7a340feeafa37e52cf6f4c12dbf1956fe7cb`, existing PR branch
`claude/ipr-backend-coverage-expansion-7d2d6a`, and main
`729857a681aa469882494f41cc832c8bec512aaa`. The PR is still open/draft/conflicted.

Combined checkout:
`/Users/benjaminyang/pla-watch/.worktrees/afp-pr79-combined-20261001`, branch
`codex/afp-pr79-combined-20261001`. Authorized local integration merge commit:
`1b8df3086af9e9770efb85e8b316b043be718890`, with parents the verified PR head
and main above. It contains only integration and the original AFP paragraph
resolution. All repair changes and this follow-up remain **uncommitted**.

The sole merge conflict was `PROJECT_STATE.md`. Its resolved integration
version equals current main exactly plus the original AFP paragraph; the
uncommitted repair adds the accurate offline status and evidence limitations.
Current main's Signal Veil text is preserved. Main changes were inherited by
integration; production paths have no changes relative to that main. A staged
whitespace check relative to the old PR head noted an existing trailing blank
line in main's consolidation document; it was left intact. The staged AFP delta
against main and the uncommitted repair both pass `git diff --check`.

The previous repair checkout retains all original changes plus the focused
source/test fixes; no existing change was discarded. Research captures remain
at their original location. All 29 research paths match the pre-repair SHA-256
inventory. Singapore's review and generated report remain separate and untouched.

The focused uncommitted files are the same six tracked files listed below,
this receipt, `regressions-before-fix.txt` and `final-checks.txt`. Final focused installed review: Standards has no blocking findings; Spec has
zero findings and independently reran the 281-test suite and preservation checks.
The review used this task brief because issue-tracker configuration is absent.
Serena is unavailable in this session; navigation used targeted searches.

Remaining gates:
owner authorization to update the existing PR, identity/proxy handling, periodic
access, reuse conditions and a permitted identified-client live rehearsal.
Historical full-corpus claims remain unverified. No AFP inquiry was sent.

---


Offline repair verified; **not collection-ready**. No AFP requests were made
during this repair. No commit, push, PR mutation, merge, scheduling, promotion,
production regeneration or publication occurred.

## Checkout and scope

- Repository: `VSSpowerlifting/China-Mil-Watch`; existing draft
  [PR #79](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/79).
- PR head and repair branch base/HEAD:
  `916c7a340feeafa37e52cf6f4c12dbf1956fe7cb`.
- Reported PR base: `043d0fe712ac047650bcfa756c87893e1a6317d0`.
- Current main assessed: `e1593eab127df0dfbe34ef3a8908b48912279906`.
- Local repair branch: `codex/afp-pr79-offline-repair-20261001`, in
  `/Users/benjaminyang/pla-watch/.worktrees/afp-pr79-offline-repair-20261001`.
- Original research branch remains at
  `d812ca3dc9b4c84217532f0f80eb17085c4eb046`. SHA-256 comparison confirms all
  29 preexisting modified/untracked files remain unchanged in
  `/Users/benjaminyang/pla-watch/.worktrees/philippines-pia-feasibility-20261001`.
  Captures were neither copied into the repair nor reattributed.

The existing adapter, contract, fixture set, disabled manifest, state schema,
identity checks and isolation guards are reused. Shared collection code and
production files were not changed. API robots 404 remains an absent rules file
under current doctrine, not institutional endorsement; refusals and policy
errors still stop collection.

## Repairs and regression evidence

| Reproduced blocker | Before fix | Verified behavior |
|---|---|---|
| Challenges on HTTP 200 | 4 new tests: 11 failing cases | Transport identifies challenges before parsing or redirects, including policy, listing and article responses. Both contract and runner return `access_challenged`; subsequent articles are never requested. |
| Specifically disallowed paths | 3 new tests: 7 failing cases | Cached host rules are checked before each content request and redirect hop; canonical website article policy also applies. Longest matching path wins over a broad `Allow: /`. A denied article is never requested. |
| Incomplete pagination | 3 new tests: 10 failures and 2 diagnostic errors | Required pages must succeed and parse, retain a stable count, terminate with explicit `next: null`, and reconcile the total. Missing routes, invalid-page 404, server errors, malformed fields, changed counts and loops fail discovery with zero references. |

The pagination diagnostic errors before repair were missing observation fields,
not passing cases. A further one-test regression reproduced two unsafe
stdlib pattern cases. Wildcard or end-anchor path rules now stop collection
until a parser supporting those patterns is available; they are never silently
treated as literal prefixes. Full red transcripts are retained in
[regressions-before-fix.txt](research/afp-pr79-offline-repair-20261001/regressions-before-fix.txt).

An incomplete discovery leaves existing shadow database and successful-run
clock bytes unchanged and records failure diagnostics in the ledger. An
article refusal can retain earlier safe records, but fails the run and does
not advance the clock. Challenge bodies are not stored as articles.

Two older positive listing tests had treated nonadjacent retained pages as a
complete corpus, and another treated a required 404 as normal completion.
Those assumptions were corrected. Positive tests explicitly derive small
complete listings in memory from the retained payloads; stored fixture bytes
are unchanged. These tests do not verify historical full-corpus claims.
Standalone fetch now reads host policy, so three transport assertions count
the actual detail URL rather than including robots requests.

## Final verification

The six modules below passed **274 tests, zero failures/errors/skips** in the
registered repair checkout. A disposable archive of current main with the
working PR files overlaid passed **273 tests, zero failures/errors/skips**.
The archive excludes only
`test_worktree_discovery_asks_git_from_the_real_repository_root`: an archive is
not a registered Git worktree. That test passed in the actual repair checkout.
Socket `connect` and `connect_ex` were patched to raise throughout both runs.

```text
tests.test_ph_afp_adapter
tests.test_ph_shadow_runner
tests.test_adapter_contract
tests.test_user_agent_identity
tests.test_manifest_note_sync
tests.test_manifests
```

To rerun the fixture checks in this checkout:

```sh
/Users/benjaminyang/pla-watch/.venv/bin/python -m unittest tests.test_ph_afp_adapter tests.test_ph_shadow_runner tests.test_adapter_contract tests.test_user_agent_identity tests.test_manifest_note_sync tests.test_manifests
```

These cover challenge/access policy, valid and complete pagination, ordinary
article retrieval/extraction, identity/manifest contracts and shadow isolation.
`git diff --check` passed. Production database, generated output, desk registry,
workflows, shared core, retained fixtures and disabled AFP manifest remain
unchanged from repair HEAD. The environment emits its existing urllib3/LibreSSL
warning; no TLS/network call was needed. No CI or live collection was verified.
See [final-checks.txt](research/afp-pr79-offline-repair-20261001/final-checks.txt).

## Conflict assessment

Only `PROJECT_STATE.md` overlaps between the PR delta and changes on current
main. A file-level three-way comparison reproduced one adjacent insertion
conflict between the AFP paragraph and main's newer Japan status. Its local
resolution preserves main's status file byte-for-byte apart from inserting the
original AFP paragraph and the offline repair note. No Git merge was performed;
HEAD remains the inspected PR head. No unresolved local file conflict remains.
The remote PR remains draft/conflicted and untouched; this local resolution
does not change GitHub's mergeability status.

## Changed files and remaining action

- `scraper/sources/ph_afp.py`: central access stop, per-request robots checks,
  pagination completeness and diagnostic observations.
- `scripts/shadow_collect_ph.py`: preserve challenge status and refusal details.
- `tests/test_ph_afp_adapter.py`, `tests/test_ph_shadow_runner.py`: regression
  cases and corrected fixture assumptions.
- `PROJECT_STATE.md`: routine local conflict resolution and repair status.
- `shadow/ph_afp/README.md`: corrected behavior and historical-evidence limit.
- This receipt and its two evidence transcripts.

The smallest next engineering action is review of this local diff, followed by
an explicitly authorized update of the existing PR. Historical full-corpus
claims remain unsupported. Identity/proxy handling, periodic access, reuse
conditions and a clean identified-client live rehearsal remain separate gates
before collection readiness. No new live permission is inferred from fixtures,
API absence of robots, or successful offline tests.

Singapore's retrospective Day 30 human review remains separate and unchanged.
No attestation or generated review report was modified. The AFP inquiry was
not sent.
