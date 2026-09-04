# DECISION_LOG — Indo-Pacific Record

Newest first. Record decisions that constrain future work. Entries below
2026-08-27 were written under the predecessor name, China Mil Watch, and are
preserved as written.

## 2026-09-04 — No. 14 is drafted, not published

The authoring blocker recorded on 2026-09-03 is resolved. PR #44 supplied the
edition-identity contract, the `publication_timing` field and the corrected
cover path, so a retrospective edition can now be authored and rendered without
the model API and without the generator's `output/`-writing publish path.

1. **No. 14 (w/e 2026-08-15) exists as a draft.** Sidecar, page, deterministic
   gradient cover, thumbnail and LinkedIn companion are prepared on
   `editorial/pla-watch-no-14-retrospective`. It is the first edition published
   under Indo-Pacific Record and the first carrying
   `publication_timing: retrospective`.

2. **It is not approved and not published.** No human editorial checklist item
   is complete, and none may be marked on Benjamin's behalf. The draft is
   evidence of preparation, not of review.

3. **The prose was written in-session, not generated.** `generate_pla_watch.py`
   was not run and no model API was called, so the edition carries no
   machine-generated text. Every claim traces to a stored record in the source
   trail.

4. **`edition_type` was chosen independently of timing.** It is `significant`
   because of what the week held, not because the edition is retrospective. The
   two fields answer different questions and neither may be read off the other.

5. **The cover took the deterministic gradient**, with the network fetch and the
   curated fallback proven unreached and `background_image_source` recorded as
   `retrospective_gradient`.

## 2026-09-03 — Editions keep the name they were published under

**Owner ruling.** Preparing the first post-rename edition surfaced that the
authoring pipeline had no concept of *which publication published an edition*.
These rulings constrain future work.

1. **Editions 1–13 retain the China Mil Watch masthead, citation, parent links
   and stored author identity** when displayed or re-rendered. An edition is a
   dated artifact of record; a re-render reproduces the published page rather
   than restating it under the current name.

2. **Editions 14 onward are published by Indo-Pacific Record.** *The PLA Watch*
   remains the series name and is unchanged by the rename.

3. **The boundary is the issue number, not the covered week.** Edition 14 covers
   the week ending 2026-08-15, which precedes the 2026-08-27 rename, yet is
   published now. The parent publication of an edition is the one that publishes
   it. A `week_ending < RENAME_DATE` test would have put No. 14 under the
   retired name, and a retrospective edition is precisely where the two diverge.

4. **Identity is resolved centrally in `core/edition_identity.py`**, not by
   module constants and not by date conditionals in templates. This closes a
   real trap: editions 1 and 2 store no author fields at all and rendered
   historically only because the generator's constants were still stale.
   Correcting those constants would have silently rebranded two published
   editions with no test failing. Correctness by coincidence is not correctness.

5. **`rerender_pla_watch.py` carries no duplicate identity.** Its
   `except ImportError` fallback re-declared the predecessor identity, so an
   import failure would have rebranded every edition it touched. One source of
   truth, stdlib-only, with nothing to guard against.

6. **`publication_timing` is `regular` or `retrospective`, and is independent of
   `edition_type`.** Timing says when the edition was written; `edition_type`
   says what the week held. Overloading either onto the other would destroy a
   distinction the archive needs. Absent means `regular`, so every historical
   sidecar stays valid; an unrecognised value is refused.

7. **A retrospective edition is visibly labelled** on the post page and on its
   index and archive cards, so it cannot read as the current week's brief. The
   label is not applied to editions 1–13, none of which is retrospective.

8. **Retrospective covers use the deterministic gradient.** No source-image
   fetch and no curated stock asset: the edition is written weeks after its
   week, so there is no contemporaneous image, and stock imagery would dress a
   back-dated edition in a look it never had. A human-approved edition-specific
   image still wins.

9. **Source concentration is standing methodology**, stated once, not injected
   as a repeated per-edition disclaimer.
## 2026-09-03 — Cadence recovery: two retrospective editions, one ruled gap

**Owner ruling, Benjamin Yang.** The analytical cadence lapsed after No. 13
(w/e 2026-08-08). Three windows passed unpublished. This entry rules on all
three and constrains future work; it authorizes *preparation and
documentation only, and is not an authorization to publish.*

1. **w/e 2026-08-15 and w/e 2026-08-22 will be prepared as retrospective
   editions**, each subject individually to full human editorial review. No
   draft carries approval from this ruling.

2. **w/e 2026-08-29 is an explicit disclosed gap.** It is not to be
   reconstructed. At audit (2026-09-03, corpus 3,802) 107 of its 244 records
   had never been relevance-screened; re-measured against corpus 3,838 later
   the same day the figure is **89 of 244 (36%)**, because the daily pipeline
   continued screening in the interval. Either way, an edition drawn from the
   screened remainder would rest on an unrepresentative slice, and no analyst
   could honestly say what the unscreened remainder held. The ground is
   **editorial representativeness and evidentiary integrity, not convenience** —
   the week is analytically interesting, which is why publishing it on partial
   screening would be the wrong call rather than a cheap one.

3. **Normal cadence resumes with w/e 2026-09-05.**

4. **No edition may be presented as contemporaneous when it was prepared
   retrospectively.** Each retrospective edition states its retrospective
   status, is written in past tense, and does not imply live watchfulness it
   did not have.

5. **A ruled gap is a disposition, not a defect.** The week ending 2026-07-25
   was ruled and disclosed the same way. The validator's resulting cadence
   warning at `2026-08-22 → 2026-09-05` is the record of this ruling and is
   never suppressed; when it appears, the governed baseline in
   `PROJECT_STATE.md` is updated to explain it, not to hide it.

6. **w/e 2026-08-29 may still be published later** if the owner funds a scoped
   screening pass — as an addition to a restored cadence, never as a
   precondition for it.

7. **This ruling pre-approves neither draft.** Each must clear
   `EDITORIAL_QA_CHECKLIST.md` in full, including the source-to-claim trace and
   the rendered-page review that editions No. 12 and No. 13 skipped.

## 2026-09-03 — A shadow run's date is its scheduled slot, not its execution date

Two completed Singapore checkpoint reviews (Day 7 `403df921…3c3d89`, Day 14
`10a28df1…e7b756`, both `pass_with_findings`, preserved on
`review/singapore-mindef`) each disposed of a missing-day anomaly with the same
root cause. The rulings that follow constrain future work.

1. **`target_date` is the logical collection date.** It names the day a run was
   scheduled to cover. `started_utc` and `finished_utc` name when it actually
   ran. Deriving the first from the second — which both collectors did —
   silently reassigns a run to the wrong day whenever Actions starts it after
   UTC midnight. Observed twice on Singapore: run 33027905549 (created
   2026-08-27T00:45:40Z, nominal 2026-08-26) and run 33455386368 (created
   2026-09-01T00:35:45Z, nominal 2026-08-31). Each left its nominal day with no
   ledger and made the next on-time run the second ledger carrying that date.
   On Japan it is not occasional but universal — see ruling 10.

2. **A scheduled first attempt belongs to its nominal slot**: the most recent
   occurrence of the cron's time-of-day at or before it started, boundary
   inclusive. `core/shadow_schedule.py` is the single implementation, and a
   test holds each workflow's `--cron-utc` equal to its own cron so the two
   copies of that fact cannot drift. Ruling 5 covers re-runs; ruling 7 states
   what this convention does and does not reconstruct.

3. **A manual dispatch may not borrow a slot.** It records the UTC date it
   actually ran on, or an explicit `--target-date`, and the ledger says which
   through `target_date_source`. A hand-started run that could claim a
   scheduled run's date would make the ledger unable to distinguish the two.

4. **A scheduled run with no cron time is refused, not defaulted.** Falling
   back to the execution date is the original defect; a workflow that forgets
   to pass its cron must fail on its first run rather than quietly two months
   later inside a checkpoint review.

5. **A re-run is refused, not re-dated, unless it names its date.**
   `GITHUB_RUN_ATTEMPT` begins at 1 and increments on each re-run; a re-run
   keeps the original run id, ref, commit and triggering event, but not the
   original moment. A scheduled job re-run from the UI a day later therefore
   arrives indistinguishable from a first attempt while the clock names a
   different slot, and a re-run dispatch is simply re-dated. Neither category
   is unambiguous, so both are refused: any attempt above 1 without an explicit
   `--target-date` is fatal, and an attempt number that cannot be read as a
   positive integer is fatal too, because a caller that cannot tell a first run
   from a re-run must not infer a date. Both workflows pass
   `GITHUB_RUN_ATTEMPT` explicitly; a direct local call defaults to 1.

6. **The recovery path is a deliberate dispatch, never a UI re-run.** Both
   shadow workflows take an optional `target_date` dispatch input, passed to
   the collector only when non-empty. A failed scheduled run is recovered by
   dispatching the desk's workflow with the day it was meant to cover; the
   procedure is in `docs/SHADOW_REVIEW.md`. The refusal message names it, so an
   operator meeting this for the first time is not left guessing.

7. **The schedule-slot rule is this repository's convention, not GitHub's.**
   A runner is never told the nominal time its schedule fired; only the event
   name and the moment the job started are available. The rule therefore
   assumes a delay shorter than one cron period, which every observed delay
   here has been, and a longer delay would resolve to the wrong slot
   undetectably. That residual is accepted deliberately and stated in
   `core/shadow_schedule.py` rather than papered over with a claim of
   exactness.

8. **`target_date_source` is optional in the ledger contract, and its value is
   not.** Every historical ledger predates the field, so requiring it would
   make the review kit refuse the corpus it exists to review. A ledger that
   *does* carry it must name one of `explicit`, `schedule-slot` or
   `manual-utc-date`; anything else is refused, because an unreadable
   provenance is worse than an absent one — it looks like an answer. The kit
   re-declares that tuple rather than importing it: its runtime imports are
   pinned to an allowlist by
   `tests/test_shadow_review_kit.py::test_the_kit_imports_nothing_network_capable`,
   and spending a real guard on three strings is the worse trade. An
   equivalence test holds the two copies equal, exactly as `KINDS` and
   `RELEASE_RE` are already held.

9. **Historical ledgers are immutable, and the review tool's missing-day
   detection was not changed.** No ledger is renamed, edited, backfilled or
   squashed: two completed human reviews reason about them and a rewrite would
   invalidate both. The missing-day anomaly stays in `review_shadow_state.py`
   because it is a true statement about the ledgers it reads — suppressing it
   would have removed the signal that found this bug. Ledgers written before
   the fix keep their execution-date stamps, and their anomalies still require
   disposition.

   The review reader is not otherwise frozen, and this change does alter it in
   one backward-compatible respect: the optional `target_date_source`
   validation of ruling 8. That addition refuses a ledger naming a provenance
   this repository cannot explain, and accepts every ledger that omits the
   field — which is all of them to date. No detection, anomaly, disposition or
   report content changes for any existing ledger.

10. **Japan was fixed in the same change, where the defect is total.** Its
    cron sits at 22:40 UTC, eighty minutes from midnight, and Actions has
    started every scheduled Japan run late enough to cross it — observed
    lateness 1h50m to 7h38m. Verified 2026-09-03 against `shadow/jp-mod`
    `35f9b9c3`: **all 9 Japan ledgers are stamped one day after the slot they
    belong to**, most recently run `33700195896`, which started
    2026-09-03T00:36:36Z, stamped 2026-09-03 and belongs to 2026-09-02. Japan's
    mis-attribution is systemic where Singapore's was occasional, so fixing one
    collector and not the other was never an option.

    Two consequences at the changeover, both accepted rather than smoothed. The
    first slot-dated Japan run records 2026-09-03, a date the last
    execution-dated ledger already carries, so one duplicate-date pair appears
    and nominal 2026-09-02 acquires no Japan ledger; no ledger is rewritten to
    hide it, and the review tool will report it truthfully. And the
    qualification clock does not move: `shadow_day` is derived from
    `finished_utc` against day zero, never from `target_date`.

11. **What the evidence supports, stated at its actual strength.** The
    Singapore corpus — the only one either checkpoint review has read — shows a
    coherent state-hash chain across both boundaries, zero recorded fetch,
    extraction and access failures, continued insertions afterwards, and
    overlapping 30-day lookbacks covering both nominal days. That supports one
    claim: *no collection loss is observable in the reviewed Singapore corpus.*

    It does not support *nothing was lost.* Every one of those facts describes
    what the desk observed and stored, and a document the ministry published
    but the desk never discovered would leave no trace in any of them. **No
    document in this repository may assert that a ministry published nothing
    that escaped observation**: that negative is not provable from inside a
    corpus, and asserting it would trade real evidence for a stronger-sounding
    sentence.

    Nor does it extend to Japan, which has had **no checkpoint review at all**.
    Japan's ledgers are healthy on their own counters, and that is the whole of
    what is known; the same claim may not be made for it until a human review
    has read it.

Neither review qualifies or promotes Singapore. Day 30, 30 consecutive
collecting days, and an owner sign-off recorded here all remain outstanding.

## 2026-09-02 — One documentation hierarchy, and PROJECT_STATE is a snapshot

Governance reset. No code, data, output, workflow, shadow state, collection,
publication or deployment changed; this entry records what the documentation is
now required to be, which constrains future sessions.

1. **There is one hierarchy, and each document has one job.** A fact belongs in
   exactly one of these, and the others link to it rather than restating it.

   | Document | Governs |
   |---|---|
   | `README.md` | public and contributor overview |
   | `PROJECT_STATE.md` | current operational snapshot and immediate handoff |
   | `docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md` | identity, editorial standard, provenance, publication principles |
   | `docs/ARCHITECTURE_AND_PUBLISHING.md` | technical layer map, commands, publishing and deployment |
   | `docs/AGENT_WORKFLOWS.md` | agent operating constraints and model routing |
   | `docs/ROADMAP.md` | current priority order |
   | `DECISION_LOG.md` | durable decisions that constrain future work |
   | Git history | superseded state and incident history |

2. **`PROJECT_STATE.md` is a snapshot, not a diary.** It had grown to 740 lines
   spanning six weeks of incident narrative, and the top of the file disagreed
   with the middle about the corpus, the renderer and the warning baseline. It
   is now rewritten in place at each update and kept under roughly 250 lines.
   Nothing was preserved by copying it into another file: Git already holds
   every prior version, and duplicating superseded state is what produced the
   contradictions in the first place.

3. **Detailed history goes to Git, not to a second document.** An incident
   worth remembering earns a `DECISION_LOG` entry stating what it constrains.
   The narrative of how it was found belongs in the commit that fixed it.

4. **Current-state assertions carry their verification date.** A figure copied
   out of the database, a ledger or the Actions API is stale the next day.
   Either date it, or name the authoritative source and do not restate the
   number — the pattern `desks/registry.json` already uses for shadow-day
   counts.

5. **Stale assertions corrected in this pass, and now prohibited as current
   claims:** `site/generator.py` presented as the production renderer (it is
   the `legacy` rollback path; `site/render.py` is production and its
   `DEFAULT_SITE_MODE` is `indo-pacific-record`); a nine-warning validator
   baseline (it is **ten**, verified 2026-09-02); `chinamilwatch.org` as the
   deploy CNAME (both deploy workflows name `indopacificrecord.org`); China Mil
   Watch as the current public identity (it is the retired predecessor name;
   *The PLA Watch* is current and is not a legacy term); one shadow desk (there
   are two, Singapore and Japan, neither qualified); licensing undecided
   (`LICENSE` is MIT and `CONTENT_AND_DATA_RIGHTS.md` covers the rest); and the
   retired `declared-record` mode string.

6. **Nothing in this reset relaxes a gate.** Both shadow desks remain
   unqualified and unpromoted, human checkpoint reviews remain required, no
   access challenge may be bypassed, and no desk is promoted without 30
   consecutive collecting days, completed reviews and an owner sign-off
   recorded here.

## 2026-08-28 — The declared snapshot is a release pin, not the daily corpus identity

Owner decision: **do not advance `DECLARED_SNAPSHOT`.** It stays at the accepted
launch values — 2026-08-26, 3,574 records, `d5b897cd…` — permanently.

The launch made `indo-pacific-record` the default mode, and `render_site()`
defaulted its snapshot to `DECLARED_SNAPSHOT`. Under `legacy` that could not
matter, because the legacy renderer has no snapshot guard. Under the new
default it meant the daily build asserted a frozen corpus identity against a
corpus that grows every morning. The first collection after launch took the
corpus to 3,611 and every subsequent render aborted with `SnapshotMismatch`.

The second-order failure is the one that made this P0. `daily_update.yml` runs
`Run offline test suite` **before** `Run pipeline`, with no `continue-on-error`.
Three of the tests that failed were assertions about the snapshot matching the
corpus, so the red suite would have stopped the run before it collected
anything. A rendering contract defect had become a collection outage.

What is now true, and constrains future work:

1. **Omitted snapshot means "describe what you are rendering".** `render_site()`
   selects the database first, derives the identity once with
   `snapshot_from_corpus(selected_db)`, and passes it explicitly. The check is
   `is not None`, not truthiness: an empty declaration is a caller naming a
   corpus, and answering it with the launch pin would render a different
   identity than the one asked for.
2. **Explicit snapshot still means "this corpus or nothing".** Date, count and
   logical fingerprint are all still enforced, still before any write. A
   matching count with a different fingerprint is still refused.
3. **Derivation and build read the database twice on purpose.** The identity is
   taken once and handed to the builder, which re-reads the corpus and checks
   what it loaded against what it was given. A corpus that changes in between
   aborts rather than producing a tree that describes neither state.
4. **The frozen-count guard tests context, not equality.** It compared every
   integer literal in the suite against every moving corpus figure, and when
   `global_times_mil` reached exactly 100 records it began failing on
   percentages, byte slices, day counts, fixture ids, a cap argument, an
   authority tier score and a `<h[123]>` regex character class — nine files,
   nine false positives, zero real ones. It now matches the two shapes a frozen
   total actually takes: comma-grouped numerals, and bare integers in a
   statement that names a corpus metric. `FLOOR` is unchanged and nothing is
   exempted by value — 100, 123 and 365 are still caught when they *are* corpus
   totals.
5. **The truth guarantee is now made positively as well.**
   `tests/test_daily_corpus_advance.py` renders against a temporary corpus that
   differs from the tracked one and asserts the public metric surfaces state
   that corpus and not the launch pin. A literal frozen into a template cannot
   survive it.

## 2026-08-27 — Indo-Pacific Record is the published identity, and chinamilwatch.org keeps resolving

Owner sign-off given 2026-08-27, closing gate 5 of
`docs/LAUNCH_AND_REDIRECT_READINESS.md`. The launch is one commit against
`origin/main` `ecfb828`, and the parts of it that constrain future work are
these.

1. **The switch is still one constant, and rollback is still changing it back.**
   `DEFAULT_SITE_MODE` in `site/render.py`. What moved is that `config.py` now
   carries `SITE_ORIGIN`, and a rollback has to change **both** — the mode back
   to `LEGACY` and the origin back to `https://chinamilwatch.org`. Two
   constants, and they move together. `site/generator.py` deliberately does not
   read `SITE_ORIGIN`: it still writes the predecessor's own addresses, so a
   rollback re-renders exactly the site that was there before rather than a
   hybrid of the two.

2. **Publishing is an exchange, not an overwrite.** `generate_preview.build()`
   still refuses to write inside `output/` — that guard was not removed, and a
   test holds it. `render_site()` builds into a scratch tree and swaps it in,
   lifting `the-pla-watch/`, `assets/`, `data/`, the predecessor marks and
   `CNAME` out first and putting them back after. The renderer is forbidden
   from the predecessor namespace, so a straight replacement of `output/` would
   have deleted thirteen editions, their sidecar records, their covers, their
   media and the feed. Anything added to the published tree that the renderer
   does not itself emit must be added to `CARRIED_FORWARD` or it will be
   deleted by the next daily run.

3. **`/article/<id>.html` covers what was public, not what is stored.** One
   stub per *analyzed* record — the rule the legacy renderer used — so the
   compatibility namespace neither loses a cited address nor invents one. The
   earlier behaviour, a stub per record, minted 2,239 addresses that had never
   existed and made the deploy gate report thousands of rendered pages with no
   analyzed article behind them.

4. **The carried pages are put back into the sitemap by the publish step.** The
   renderer cannot list pages it is forbidden to see. Without that step the
   launch would silently have dropped sixteen indexable pages — the weekly
   index, its archive, its glossary and the thirteen editions — from the map
   crawlers read, while leaving them resolving so that nothing reported it.

5. **The predecessor's route list is frozen, not derived.**
   `site/predecessor_routes.txt`, taken from `gh-pages` `099b7b41`. `output/`
   was the right source for "what did China Mil Watch serve" only while it held
   China Mil Watch. `production_routes()` still exists and still reads a tree;
   `predecessor_routes()` answers the historical question.

6. **A deploy workflow that names the predecessor domain would undo the
   redirects.** `chinamilwatch.org` is served by a separate redirect-only Pages
   site, and a domain can be held by one Pages site at a time. Both workflows
   now publish `cname: indopacificrecord.org`; a revert of either would reclaim
   the old domain on the next scheduled run and turn every preserved legacy
   address back into the predecessor's site. Pinned by test.

7. **Editions keep their masthead and their paths.** The thirteen issues are
   still labelled as published under China Mil Watch, still carry their issue
   numbers, titles, deks, bylines and dates, and still live at
   `/the-pla-watch/posts/<date>.html`. Their canonicals were re-rendered onto
   the new origin because the alternative — carrying them across with
   canonicals pointing at a domain that redirects back — would have left the
   new site's own archive declaring itself elsewhere. The sidecar JSON was not
   touched: it records what was published, including a `cover_image_url` on the
   predecessor's domain, and the renderer rewrites that at render time rather
   than editing the record.

8. **Snapshot accepted: 2026-08-26, 3,574 records, `d5b897cd…`.** Derived from
   the tracked corpus in one operation. Immediately after an advance the stored
   record count equals the declared count, so `moving_figures()` drops it from
   the frozen-count guard for as long as the corpus sits where the snapshot
   froze it. That is the documented behaviour, not a hole.

## 2026-08-17 — MOD China: canonical choice is an authority judgement, and discovery needs a window

MOD China stored nothing between 2026-07-10 and 2026-08-17 — 38 days against its
21-day threshold — while publishing on cadence throughout. The adapter was never
broken. Two defects, both ours.

1. **Cross-source dedup silently reassigned MOD China's copy to PLA Daily.**
   `dedup_articles()` chose the survivor of a same-title group using
   `source_priority(url)`, a map of 81.cn *section* names keyed off the first
   path segment. A MOD URL (`/gfbw/…`) parsed as section `gfbw`, missed the map
   and scored 70 — below PLA Daily's 要闻 at 100. The Tier A ministry therefore
   lost every head-to-head to a Tier B newspaper reprinting the same
   spokesperson text, and the surviving row was stored under an 81.cn URL
   against `pla_daily`. A representative run recorded `mod_china` as 7
   discovered, 7 fetched, 7 extracted, **7 duplicates, 0 new**, and reported
   success.

2. **Canonical selection is a five-part total ordering.** Governed authority
   tier → source identity → 81.cn section priority → shorter URL → the URL
   itself. **Only the first is an editorial judgement.** Identity and URL are
   lexical comparisons — determinism devices, not claims that one source or one
   URL is better. A three-part key without them tied at the top on 16 of the 17
   duplicate groups then present in the corpus, which meant input order decided
   the winner of a function that both stores documents and drives deletion.
   Where a real ranking between equal-tier sources is wanted, it belongs in the
   manifest as an authority distinction, not in a tie-break.

3. **Section priority cannot cross a source boundary.** Section is the third
   component and identity the second, so two candidates from different sources
   are always separated before section is consulted. That is a property of the
   key's shape, not a convention.

4. **The tier table is a constant in `processing/dedup.py`, not a manifest
   read.** `dedup_articles()` is a pure batch transform in the pipeline's hot
   path; giving it manifest or database I/O would invert the layering. The drift
   this risks is covered by a test that compares the constant against every
   `desks/*/manifest.json` and fails the moment they disagree, and by a
   structural test asserting the module performs no configuration I/O.

5. **Title normalization is unchanged, deliberately.** Stripping `【双语】` is
   what makes MOD's bilingual release group with PLA Daily's Chinese reprint,
   which is the grouping we want. No fixture showed it merging two genuinely
   different releases, so it was not touched.

6. **Discovery is a seven-calendar-date window ending on `target_date`.**
   Discovery kept a listing link only when the run date appeared verbatim in its
   text, so an item was collectable on exactly one day and never again. MOD
   routinely posts an item days after the date it stamps on it, and every such
   item was invisible when stamped and ignored afterwards.

7. **The window covers ordinary backdating, not outages.** A run gap wider than
   the window cannot be recovered by widening it; that needs an explicit bounded
   backfill, decided and run once. Widening the daily window to insure against
   arbitrary outages would refetch the whole listing every day to solve a
   problem that should be handled on purpose, when it happens.

8. **The publication date is a terminal metadata stamp, not any date in the
   text.** Each listing link carries its stamp in its own
   `<small class="time hidden-xs">` element, reading `YYYY-MM-DD HH:MM`. That
   element is read directly; only when it is absent does the scraper fall back
   to requiring the same form at the very end of the flattened link text. In a
   flattened link the headline and the stamp are one string, so any rule that
   hunts for a date *somewhere* can be answered by the headline instead of the
   metadata — `回顾2026-08-14演习纪要` carries no stamp at all yet satisfies such
   a rule. A malformed terminal stamp returns nothing and is never repaired from
   an earlier candidate.

   Contract verified across 71 archived listing documents and 2,850 article
   anchors: 1,980 carry the stamp element and all 1,980 read `YYYY-MM-DD HH:MM`;
   no date-only stamp occurs; no anchor has non-whitespace content after its
   stamp; the remaining 870 anchors carry no stamp and were already dropped. Old
   and new rules agree on all 2,850, so nothing MOD published is dropped.
   **A date-only stamp is deliberately unsupported** — it does not occur, and
   accepting it is what let a bare headline date pass as metadata. If MOD ever
   emits one, those items stop being discovered and the liveness gate fires,
   which is the direction to fail in; widen the pattern on evidence, not in
   anticipation.

9. **The destructive cleanup shares the pipeline's ranking and fails closed.**
   `scripts/cleanup_duplicates.py` ranked by `source_priority(url)` alone, so
   under the new policy it would have deleted exactly the Tier A copy the
   pipeline keeps. Both now rank through `processing.dedup.canonical_sort_key`;
   the ordering is not permitted to exist in two files. The script resolves
   source identity through an `articles → sources` join rather than the URL,
   which matters because China Military Online is declared as
   `english.chinamil.com.cn` but serves its stored articles from
   `eng.chinamil.com.cn`.

10. **Deletion refuses on unresolvable identity.** Any duplicate group
    containing a row whose source identity cannot be resolved is reported and
    skipped outright — an empty identity is the absence of an answer, never
    evidence that two rows share a source. A group in which every row carries
    the same explicit slug stays rankable even when that source is not yet in
    the tier table; a group whose identities differ and include an ungoverned
    one stays refused.

11. **`--dry-run` cannot write to its input.** It opened the database with a
    plain `sqlite3.connect()`, which writes to a WAL database merely by opening
    it, so it could check-point the tracked database or leave `-wal`/`-shm`
    beside it while reporting that it changed nothing. It now reads through
    `scripts.reconcile_db.read_only()`, which copies the database and its
    sidecars and reads the copy. `--apply` still opens directly, because it is
    meant to write.

12. **The 21-day alarm stands unchanged, and MOD China stays out of
    `KNOWN_INERT`.** The gate measures `MAX(published_date)` per source; it
    fired correctly and was the only signal that caught this. A source that
    publishes on cadence is not inert because our canonical selection discarded
    it.

13. **Measured 2026-08-17.** Of 52 MOD items published after 2026-07-10 and
    still on page 1 of the six configured sections: **0** stored under
    `mod_china`, **40** stored under `pla_daily` at 81.cn URLs, **12** absent
    from the corpus altogether. Ten of the twelve fall inside a contiguous
    2026-07-17 → 07-24 window in which no run executed at all — wider than the
    seven-date window — and two are backdating losses the window now catches.
    This is a dated measurement, not a standing fact: all three numbers move as
    runs continue. Record any later count separately, with its own date.

14. **Historical re-attribution is deferred and is a separate decision.**
    Rewriting the provenance of the 40 rows already stored under `pla_daily`
    touches published rows and is not a defect fix. Going forward the fix is
    self-limiting: where a PLA Daily copy is already stored, MOD's copy now wins
    the title group but is then dropped by the cumulative content-hash check, so
    no duplicate is created and no history is rewritten.

15. **No backfill has been performed.** The 12 absent articles remain absent. A
    later bounded backfill should take every item actually missing, not an
    editorial selection.

16. **Canonical selection still discards the losing copies' URLs.** The survivor
    is now the most authoritative copy rather than an arbitrary one, but the
    fact that two institutions both carried a release — and at which URLs — is
    recorded nowhere. Representing one release as a document with several
    source-attributed locations is a provenance-model question (capture storage
    / document versioning), not something a title-dedup filter should invent.
    **Unresolved.**

## 2026-08-17 — Correction: `mode=ro` on a WAL database is platform-dependent, not impossible

The 2026-08-14 entry below states that a `mode=ro` URI "cannot open" a WAL
database without a `-shm`. That wording is too absolute, and the entry is left
standing as written — this is a correction to it, not a rewrite.

1. **The claim was disproved by a hosted run.** The first pull-request run of
   the offline-checks workflow (run 32037681525) failed on
   `test_mode_ro_cannot_open_it_without_a_shm` with "OperationalError not
   raised". The Ubuntu runner opened the sidecar-less fixture through `mode=ro`
   perfectly well. The same call raises `OperationalError` on the macOS
   environment where the original conclusion was drawn.

2. **SQLite's actual rule.** Since 3.22.0, a read-only WAL database can be
   opened when the `-wal` and `-shm` files already exist, when those files *can
   be created*, or when the database is immutable
   (https://www.sqlite.org/wal.html#read_only_databases). The outcome therefore
   depends on the SQLite build, the VFS and whether the containing directory is
   writable — not on anything this project controls. Where the runner's
   directory was writable, SQLite satisfied the WAL-state requirement and the
   open succeeded.

3. **The scratch-copy decision stands, and for a better-stated reason.** The
   2026-08-14 ruling to read the tracked database through
   `reconcile_db.read_only` is unchanged and remains binding. Its justification
   is not "the direct form cannot work" but that the direct form guarantees
   nothing: on one machine it fails outright, on another it succeeds *by
   creating sidecars next to the tracked file*. Both outcomes are unacceptable
   for a read of a tracked artifact. Copying the database and its sidecars to a
   scratch directory gives what is actually required — a read that is reliable
   on every platform, cannot mutate the input, and leaves no residue in its
   directory. A hot `-wal` is still copied, so committed rows are never hidden
   from validation.

4. **Tests now pin project-controlled behaviour, not a platform's error.** The
   two tests that asserted the `OperationalError` and its disappearance once a
   sidecar existed are removed; asserting either outcome asserts a property of
   one machine, and a test written to accept both would assert nothing. In
   their place, two structural tests parse `validate_output.py` and
   `check_source_liveness.py` with `ast` and require that each imports and
   calls `read_only`, and that neither opens the database directly — through
   `sqlite3.connect`, an aliased module, or `from sqlite3 import connect`. That
   holds identically everywhere. All functional coverage of the helper is
   retained: WAL header, sidecar-less access, `str` and `Path` inputs, input
   byte identity, no sidecars beside the input, hot-WAL recovery, propagated
   errors, the historical alias, liveness execution, check 8 running rather
   than degrading to a warning, an unreadable database becoming an error, and
   analyzed-but-unrendered gating.

Standing rule, restated: **no consumer reads the tracked database directly.**
The reason is portability and isolation, not impossibility.

## 2026-08-14 — Salvage requires proof of collection; a read of the tracked database is not a read

Stabilization of the defect production run 475 exposed on the first scheduled
run after the neutral-foundation release. Local branch
`fix/run475-persistence-gate`; nothing pushed or deployed.

**What happened.** Run 475 passed the guard, migrations, verification, the
221-test offline suite and the reconciliation contract, then failed the
pre-pipeline tracked-database cleanliness gate — correctly, because the suite
had modified `pla_watch.db`. The pipeline was therefore skipped. The
persistence-on-failure step ran anyway and pushed the rejected residue as
`483d154`, captioned *"Persist collection: 2026-08-14 (analysis incomplete)"*,
although no collection had occurred. The residue proved logically neutral (an
identical `sqlite3 .dump`; 39 bytes on one page), and run 476 then succeeded, so
the release stood. The control-flow defect did not.

1. **Job-scoped `failure()` is not evidence that anything was collected.** It is
   equally true for all five pre-pipeline gates. Persistence now additionally
   requires positive proof the pipeline executed —
   `steps.pipeline.outcome == 'success' || steps.pipeline.outcome == 'failure'`
   — which is why `Run pipeline` carries `id: pipeline`. Positive, not a
   negation of `'skipped'`: an id that never ran reports the empty string, and
   `!= 'skipped'` would wave that through.

2. **Ruling on case 7 — pipeline succeeded, a later publication step failed:
   salvage stays eligible.** The day's articles are stored and analyzed; the
   normal commit carries implicit `success()` and is skipped, so without salvage
   the runner is destroyed with the whole day inside — the 2026-07-17→24 loss
   mode. Salvage remains database-only, so an unvalidated render still cannot
   reach production. A test asserts `output/` never enters that commit even when
   it is dirty.

3. **The persistence commit message must state what actually happened.**
   "analysis incomplete" is a claim about the pipeline and is false in case 7.
   The message is now derived from `steps.pipeline.outcome`. A commit that
   announces work nobody did is worse than a terse one.

4. **A plain `sqlite3.connect()` on the tracked database is a write.** The file
   is WAL-mode (header write/read version 2), so opening it read-write creates
   `-wal`/`-shm` and can checkpoint pages back into it. That is what
   `test_production_database_has_only_china_sources` was doing, and it is the
   whole of run 475's residue. **A `mode=ro` URI is not the fix**: SQLite must
   write the WAL index to read a WAL database, so on a fresh clone with no
   `-shm` the connection fails to open outright. Tests read a scratch copy via
   the existing `reconcile_db._read_only`, which already documents this exact
   hazard. Standing rule: **no test may open the tracked database read-write.**
   A test enforces it by scanning `tests/` rather than by convention.

   **That scan must be structural, not textual.** The first version of this
   guard matched the literal string `sqlite3.connect(` — and the line that
   actually caused run 475 was `import sqlite3 as _sq` … `_sq.connect(str(prod))`,
   which it silently missed. A guard aimed at a defect that cannot detect that
   defect is worse than none, because it is believed. It now parses each test
   module with `ast`, resolves whichever local names reach `sqlite3.connect`
   (module alias, `from sqlite3 import connect`, or an aliased import), and
   resolves the connection target through local assignment back to
   `REPO_ROOT / "pla_watch.db"`. The detector carries its own fixtures for
   every import style it claims to cover, and for the safe cases — temporary
   databases, fixtures, `_read_only`, and bare mentions of the filename — it
   must not flag. It is scoped to this one hazard and is not a static analyser.

   Consequence to watch: `validate_output.py` and `check_source_liveness.py` use
   the `mode=ro` idiom against the tracked database and work in CI only because
   an earlier read-write step has left `-shm` beside it. Fragile but currently
   true, and out of scope here — recorded so it is not rediscovered as a mystery.

5. **The collection-health table is printed after attribution, not before.**
   Printed after collection it read `dup=0 new=0` with an unrefined status for
   every source: production run 112 logged `mod_china ok dup=0 new=0` while
   storing `ok_all_duplicates dup=7 new=0`. The stored rows were always right;
   the log was not, and an operator reading it could not tell an all-duplicate
   day from a silent one. Dry runs still print the table, with the counts a dry
   run can honestly know.

6. **Workflow-contract parsing now strips trailing comments, quote-aware.** The
   suite decides whether a step pushes, rebases or verifies by looking for
   command text in its body; a trailing `# git push` put that vocabulary into a
   surviving line. Quote-aware because `echo "### ..."` is data.

Not done, deliberately: MOD China's threshold untouched, Xinhua still
`not_implemented`, no schema migration, no change to `reconcile_db.py`'s merge
algorithm, no new desk made collectible.

## 2026-08-13 — Country-neutral core: configuration over central imports, and migrations that survive the reconciler

Phases 1–2 of the Defense Discourse foundation, implemented on branch
`refactor/defense-discourse-foundation`. Internal architecture only: no public
rename, no route change, no new desk, no deployment. Full rationale in
`docs/ADR_NEUTRAL_CORE.md`.

1. **Sources are configuration, not imports.** `pipeline.py` no longer names a
   scraper class. `desks/china/manifest.json` declares all five sources
   including the dotted adapter path, and `core/registry.py` resolves it at call
   time. A test asserts `pipeline.py` contains none of the five class names and
   that `core/` imports nothing from `scraper.*`. `SCRAPERS` survives as a
   documented dict-like shim for the CLI and scripts; removing it is a later
   approved cleanup.

2. **The existing scrapers were wrapped, not rewritten.** `adapters/legacy.py`
   calls the same methods in the same order as `BaseScraper.scrape()`, and
   `ExtractedDocument.raw` carries the parser's dict verbatim so downstream
   normalization, dedup and the keyword filter receive byte-identical input —
   *including which keys are absent*, which is not the same as
   present-and-`None`. Months of selector and encoding corrections were not put
   at risk to gain reporting.

3. **Standing rule: an empty result must name which empty it is.** The 2026-08-09
   §6 rule now has a vocabulary. `ok_no_publications` (healthy silence) is a
   different value from `listing_failure`, `fetch_failure`,
   `extraction_failure`, and `not_implemented`, each declaring whether it is a
   failure. **One collectible source failing degrades the whole run**, even when
   every other source succeeded — the condition that reported success for four
   weeks while MOD China was dead. Verified by driving the real `pipeline.run()`
   with offline adapters: a simulated MOD listing failure produced
   `aggregate: DEGRADED` while PLA Daily collected normally.

4. **`not_implemented` and `skipped_disabled` are deliberately not failures.**
   Both are acknowledged configuration states. Treating them as failures would
   mark every run degraded for as long as Xinhua remains a stub, and an alarm
   that is always on is not an alarm. They are always *visible* — Xinhua now
   reports `not_implemented` in every run and in the health report instead of
   passing as a source that published nothing.

5. **Migrations run on the write path, because the reconciler reverts schema.**
   `scripts/reconcile_db.py` copies the published side's *file*, so a rebase onto
   an older origin silently restores the older schema — this happened to the
   `'degraded'` constraint on 2026-08-09 and again by the time of the 2026-08-13
   audit. Idempotent migrations now run inside `storage.db.init_db()`, which
   `pipeline.py` calls before any collection, so the schema self-heals instead of
   depending on the standing re-apply rule being remembered.
   `tests/test_migrations.py::TestReconcileReversion` reproduces the exact
   sequence and asserts full recovery.

   **The limit of that protection, stated plainly:** everything migrations create
   is DDL or reconstructible from tracked manifests, so schema and desk config
   recover completely. **Observed data does not.** `source_run_results` rows
   written locally between a reconcile and the next push are lost with the
   reverted file. Ordering the reconcile against CI is a Phase 3 decision and is
   not solved here.

6. **Nothing was dropped.** `sources.language` and `sources.is_active` are still
   present and still written; `language_tag` and `enabled` were added beside
   them with fallback accessors in `storage/db.py`. Config sync touches **only**
   the columns migration 0003 added — it can never rename a live source or
   re-point its `base_url`, which is asserted by test.

7. **Blocker recorded, not worked around: a non-Chinese/English desk cannot be
   synced yet.** `sources.language` carries `CHECK (language IN ('zh','en'))`.
   `core.registry._legacy_language()` raises rather than coercing, because
   silently mapping `ru` to `en` would corrupt the corpus in a way nothing
   downstream could detect. **Relaxing that CHECK is a prerequisite migration for
   the Russia desk.**

8. **Desk taxonomies stay desk-scoped.** The 14 existing China categories are
   recorded verbatim as China-desk configuration and are *not* promoted into the
   universal cross-desk vocabulary. "Taiwan" and "South China Sea" have no
   meaning on another desk; forcing them into a shared taxonomy would distort
   both. The universal layer is genre (`directive_law`, `speech_transcript`, …),
   which means the same thing everywhere.

9. **Authority tier is proximity to an authorized position, not credibility.**
   A Tier A document is not more likely to be true than a Tier D one; it is more
   likely to represent what the institution has formally decided to say. China
   desk assignments: MOD China A, PLA Daily and China Military Online B, Xinhua
   Military C, Global Times D. China Military Online is marked `mirror` and
   Xinhua `syndicated` so their republications cannot inflate institution-level
   message volume once clustering exists.

10. **The GitHub repository rename is hosting-only.** `PLA-Watch` →
    `China-Mil-Watch`; the local `origin` remote was repointed and the single
    stale runs-API example in PROJECT_STATE corrected. No public site name,
    domain, canonical URL, or branding changed, and none may without a separate
    Phase 5 decision.

## 2026-08-12 — Veil images must be provably the cited article's own

Auditing the automatic veils against their sources found four editions whose
image id did not match the article id. Cause: `fetch_article_image.py` takes
the first body image ≥800×400, and 81.cn article pages carry a recommended-
video rail (`jskt_208724`) of `<li><a><img>` thumbnails that pass every size
and path filter. Verified in page HTML: the 06-20 image sat inside a link to
article 16467895, an unrelated 77th Group Army story. Editions 06-20 and
06-27 had resolved to the *same* thumbnail.

1. **Provenance is now enforced at fetch time.** 81.cn embeds the owning
   article's id in every attachment filename; a candidate whose id differs
   from the article's is rejected as another article's asset. URLs carrying
   no id (other CMSes) are not judged by a convention they do not use, and
   fall through to the existing filters. Recorded per image as
   `provenance: og:image | article-id-match | unverifiable-cms`.
2. **An edition with no provable image ships text-led.** 2026-05-30's own
   photograph is 779×1072, below the size floor, and nothing else in its
   trail qualifies — so it carries no veil rather than a borrowed one. Its
   auto `media_items` entry was removed; that is a correction of
   machine-written data, not an editorial sidecar edit.
3. **Corrected: 06-20, 06-27, 07-18 re-fetched** to their real article
   images; all eleven remaining source images now match. The defect predates
   the veil work — these images have been cover-PNG backgrounds since each
   edition shipped — but rendering them on-page with a credit line naming
   the article is what made a wrong image into a false claim.
4. **The cover generator's cross-edition fallback is retired.** Regenerating
   the corrected covers exposed the same defect one layer down: priority 4
   borrowed "prior-week images already in the media dir", which put edition
   1's photograph on No. 4's link preview. Curated assets (priority 3) are
   generic by design and stay; an edition-specific news photo is not, and on
   another week's cover it implies a story that edition never covered. An
   edition with no image of its own now falls through to the abstract
   gradient — 2026-05-30 is the only one affected and now renders it. Its
   stale `background_image_path` was cleared, or priority 1 would have read
   the borrowed photograph straight back out of the sidecar.
5. **Standing rule: a veil is evidence-adjacent and must be traceable.**
   Any future image path — new outlet, new CMS, manual addition — states how
   the image was tied to the article, or the edition renders text-led. The
   2026-07-12 exact-URL rule governs which *story* an image attaches to; this
   governs whether the file is that story's at all.

## 2026-08-12 — Automatic veils render at full curated strength

The damped `--source` treatment introduced with the automatic veil is
withdrawn at analyst direction: the veil is the edition's identity and should
read as photography, not as a watermark. `.card-veil` / `.nd-veil` now apply
identically to curated and automatic images.

The legibility concern that motivated the damping is real but was
misdiagnosed as a treatment problem. It is an image-selection problem: a
dark, low-contrast frame (No. 10's submarine) leaves the dek clean at full
opacity where a bright, signage-heavy briefing frame does not. **Image
choice, not opacity, is the lever.** Where a frame is too busy, route a
curated manifest entry for that edition — it still wins over the automatic
path — rather than reintroducing a per-class opacity rule.

## 2026-08-11 — Signal Veil falls back to the edition's own source photograph

Editions Nos. 11–13 shipped with no in-page imagery at all. Cause: the
2026-07-11 ruling demoted cover PNGs to og:image duty in favour of Edition
Plates (ROADMAP T2), commit `36510bb` executed the removal, T2 was never
built, and curated veil coverage stopped after No. 10 — leaving the identity
slot empty for nine of thirteen editions.

1. **The Signal Veil now resolves in two tiers**, via a single
   `veil_for_edition()` in `scripts/pw_env.py` shared by the generate and
   rerender paths: curated manifest entry first, then the photograph
   `scripts/fetch_article_image.py` already pulled from the edition's own
   cited article, then the text-led fallback. Nine editions gain imagery;
   Nos. 8–10 keep their curated images unchanged.
2. **This is the V&M §2 "source photographs" class, not the curated
   library.** The PD/CC0/CC BY allowlist in `fetch_editorial_image.py`
   governs the curated library and is untouched. Source photographs are
   permitted by policy as in-edition context, verbatim from the cited
   article, and carry the mandatory credit + "context, not evidence" line
   already rendered by the templates.
3. **Association stays exact-URL, never topical.** The image comes from an
   article in the edition's own source trail, matched back to it by
   normalized URL for its credit. The 2026-07-12 prohibition on
   category/thread matching is unaffected — no search, no inference, so an
   image still cannot drift onto the wrong story. A miss at any step
   (no metadata, no derivative, no `article_url`) yields None, not a guess.
4. **Automatic veils render quieter than curated ones**
   (`.card-veil--source`, `.nd-veil--source`). A curated image is chosen for
   composition; an auto-fetched briefing frame carries its own signage and
   captions, which must never compete with the edition's prose. Damped
   opacity and a tighter right-anchored mask are the standing treatment, and
   `mask_focus` stays centre-weighted — per-image focus tuning on uncurated
   photography is how the V&M §2 misleading-crop rule gets broken.
5. **The validator gained a source-veil provenance check** rather than an
   exemption: a `src-*` id must resolve to real fetch metadata, an existing
   derivative, and an `article_url` linked on the page. "Manifest-only" as a
   validation rule is replaced by "provenance-verified", which is stricter
   for this class.
6. **T2 (Edition Plate) is not superseded.** It remains the deterministic
   identity for editions with no usable photograph, and is specified in
   `docs/T2_EDITION_PLATE_SPEC.md`. Open question D2 there — whether the
   plate or the veil owns the index card when both exist — is now answered
   for the veil-present case: the veil wins.

## 2026-08-11 — Sidecar prose may be edited for style, never for substance

Analyst directed an em-dash cleanup and a humanizer pass on No. 13 before
publication. That required editing `output/the-pla-watch/posts/2026-08-08.json`
directly, against the standing "no casual edits, ever" rule for sidecars. The
rule stands; this is the narrow exception and its conditions:

1. **Only on explicit analyst instruction.** Never as cleanup an agent decides
   to do on its own initiative.
2. **Authored prose fields only** — `dek`, `signal`, `opening_note`,
   `what_stood_out`, `why_it_matters`, `what_was_routine`,
   `term_to_know_explanation`, `what_im_watching_next`. **`source_trail` is
   off-limits.** Its em dashes sit inside outlet names and article titles,
   including Chinese, which are source-derived text under the no-invention
   rule. The 08-08 pass left all 8 trail entries byte-identical, deliberately.
3. **Punctuation and sentence boundaries only.** No claim, number, name, date,
   unit, or quoted official language may change. The 08-08 pass preserved
   `"null and void"`, `"Model of the Era"`, `"Most Beautiful Soldiers"` and the
   Junsheng attribution verbatim.
4. **Mechanically verified, not eyeballed.** Every replacement asserts its
   target matches exactly once and aborts otherwise; a sentence-level diff
   against a pre-edit copy confirms only intended fields moved. A partial
   string match silently corrupting the canonical record is the failure mode
   being defended against.
5. **Re-render, then re-run the gate.** The sidecar is the record; the HTML is
   derived and must be regenerated from it.

Method note: fixing em dashes *first* and running the humanizer *second*
introduced a defect the second pass then caught — an em-dash replacement
created the staccato fragment "That caveat matters.", which is itself a
flagged pattern (§31). Run the style passes together, or expect the second to
clean up after the first.

## 2026-08-09 — A run that keeps publishing must still be able to raise an alarm

1. **The 2026-08-07 credit exhaustion published as a clean day.** Run 105 hit
   `invalid_request_error: credit balance is too low` after analyzing 24 of 36
   articles. Because some work landed, `account_block_total_failure` was False,
   the pipeline exited 0, the site deployed, and step 8 committed *"State: mark
   daily run 2026-08-07"*. Nothing in the repo said otherwise until run 106 the
   next day analyzed zero articles and tripped the total-failure path. The
   outage was two days old when found.

2. **Three independent mechanisms each did the right thing and the day still
   went unnoticed.** `pipeline.py` wrote the billing marker (it fires on any
   account block, partial or not). The workflow's marker-commit step was gated
   on `failure()`, so it never ran. Step 6 stages only `pla_watch.db output/`,
   so the marker died with the runner. Each piece was locally correct; the seam
   between them leaked.

3. **Standing rule: partial degradation must be recorded in a place that
   survives the runner, and must be loud.** Publishing through a partial
   failure is correct and stays. But "kept publishing" is not "was fine," and
   the audit trail has to distinguish them. Concretely: `scrape_runs.status`
   gains `'degraded'` and `complete_scrape_run()` is always passed an explicit
   status; the marker-commit step runs on `always()`, guarded by a working-tree
   diff so it is a no-op on clean days.

4. **The alarm runs last, and only notifies.** A new Health gate step sits
   after deploy and after the success marker, so it can never block a publish
   that was otherwise fine. Its sole purpose is to fail the run so GitHub's
   notification reaches a human. Anything that wants to stop a deploy belongs
   in `validate_output.py`, not here.

5. **Corollary: a green run is evidence of nothing unless something is checking
   liveness.** MOD China last produced on 2026-07-10 and was silent for four
   weeks without a single failed run, because PLA Daily supplies ~87% of
   articles and the totals never moved. `scripts/check_source_liveness.py` now
   fails the gate on any active, non-inert source silent past a threshold.
   Acknowledging silence means adding the slug to `KNOWN_INERT` **with a
   reason** — a deliberate, reviewable act, not a config toggle.

6. **An empty scrape had two meanings and recorded neither.** `get_article_urls()`
   catches listing-page fetch failures per section, logs a warning and
   continues, so "published nothing today" and "could not reach the site"
   both produced `[]`. `BaseScraper.failed_fetches` now records URLs whose
   retries were exhausted and the pipeline appends them to
   `scrape_runs.errors`. **Standing rule: when a stage can return empty for
   both a normal and a defective reason, it must record which.**

7. **The DB reconciler merges rows, not schema — a migration does not survive
   a merge from origin.** Found the hard way while landing this work: after
   `scripts/migrate_status_degraded.py` relaxed the `scrape_runs.status` CHECK
   and the change was committed, rebasing onto `origin/main` reverted it. The
   driver reconciles article and run *rows* and takes the published side's
   file, so origin's older schema came back wholesale with no conflict, no
   warning, and a correct-looking row count. Had it gone unnoticed, CI's first
   `'degraded'` write would have thrown `IntegrityError`.

   **Standing rule: a schema migration must be re-applied and re-verified
   AFTER the final rebase, immediately before pushing — never only before.**
   The check is one line:
   `sqlite3 pla_watch.db "SELECT sql FROM sqlite_master WHERE name='<table>';"`
   Migration scripts must be idempotent so this is always safe to repeat.

8. **Liveness thresholds are per-source, and set from the source's own
   publishing rate.** A flat 7-day rule marks a source that genuinely
   publishes twice a month as dead every other week, and an alarm that cries
   wolf is worse than no alarm. `SILENCE_THRESHOLD_DAYS` overrides the
   default per slug; MOD China sits at 21d, measured from 28 distinct publish
   dates across three months on its own listings — deliberately measured from
   the *source*, never from our collection, which is the thing under test.

## 2026-08-04 — A screening decision is data, and the reconciler must carry it

1. **The DB reconciler silently discarded 46 relevance decisions.** Its
   analysis backfill fired only on `l.analyzed_at IS NOT NULL`, but a relevance
   *rejection* writes `passed_relevance` and leaves `analyzed_at` NULL — as do
   translation and summary failures. Merging `origin/main` into a branch that
   had just screened the No. 12 window returned 43 rejections and 3 failures to
   the unscored pool. Caught only because the window was measured immediately
   after the merge and read 46 unscreened where it should have read 0.

2. **Every gate passed while it happened.** The merge kept every article, every
   URL and every id — the existing gates check exactly those. A reverted row is
   byte-indistinguishable from one that was never screened, so nothing could
   see it. **Standing rule: a decision that cost a paid call is data, and the
   reconciler must be gated on decisions, not just on rows and ids.**

3. **Two costs, both silent.** The scores and reasonings are the audit record
   the project preserves verbatim (see `backfill_translations.py`), and the
   articles return to the queue to be screened and paid for a second time, with
   no guarantee the second answer matches the first.

4. **Corollary: verify the domain invariant after any DB merge**, not just that
   the merge exited clean. `passed_relevance IS NULL` counts before and after
   are the cheap check.

## 2026-08-03 — The deploy gate compares the DB to output/, not output/ alone

1. **A site missing a sixth of its analyzed corpus passed the gate four times.**
   The 07-30 translation backfill wrote 117 analyzed articles to
   `pla_watch.db`; the reconcile merge driver carried them onto `main`; nothing
   re-rendered. `validate_output.py` checks 1–7 all read `output/` in
   isolation, so the shortfall was invisible to it and to CI, and 117 articles
   stayed unpublished through every deploy from 07-30 to 08-03. Measured
   2026-08-03: 672 analyzed in the DB, 555 rendered pages, gap constant at 117
   across `a1fff19`, `778d597`, `0f963fa` and `ffb5bf1`.

2. **The gap is structural, not a one-off.** Any path that writes the DB
   without re-rendering reproduces it: the two backfill scripts, a reconcile
   merge, or a hand-merge of two DB lineages. The daily pipeline is not the
   guard — it renders correctly from whatever DB its own runner holds (verified
   in sync at `db71841`: 555 analyzed, 555 pages), so rows arriving by any
   other route are simply never drawn.

3. **Standing rule: a validator that reads only generated output cannot
   certify that output is complete.** `validate_output.py` check 8 now compares
   analyzed articles in the DB against rendered pages. Analyzed-but-unrendered
   is **fatal** (it is always a defect, and `site/generator.py` fixes it in one
   command); rendered-but-not-in-DB is a warning (the generator prunes stale
   pages itself). The check skips when the DB is absent or a non-default output
   dir is passed, so validating a copied or deployed tree still works.

4. **Corollary for backfills: re-render before calling one done.** A backfill
   that only writes the DB has published nothing. Run `site/generator.py` and
   the gate afterwards, in that order.

## 2026-08-02 — The backlog is drained live-window-first, not FIFO

1. **Plain FIFO buries exactly the articles an edition still needs.** Both
   backlog queries in `storage/db.py` ordered by `id`, so a deferred article
   joined the back of a ~1,180-deep queue draining ~18/run. Measured on the
   reconciled database: the recovered 07-30/07-31 articles sat at queue
   position 1,178 — **66 runs**, roughly two months — so they could not be
   screened in time for edition No. 12, the edition covering their own week.
   Meanwhile the whole 30% backlog reserve was spent on May and June material
   that no unwritten edition can use. **Standing rule: recency-critical
   material is screened before archive material.**

2. **`LIVE_BACKLOG_DAYS` (default 14) splits the unscored queue.** Articles
   scraped within the window go first, oldest-first among themselves so a week
   fills chronologically; everything older keeps FIFO behind them. Same
   measurement after the change: position 168, **10 runs**. The archive is
   deferred, never starved — once the live tier drains, FIFO resumes as before.
   14 days covers the current edition window plus a week of slack for a late
   draft.

3. **`pending` (passed relevance, analysis unfinished) keeps absolute
   priority.** It is small — 74 rows — and those articles have already paid for
   a relevance call, so finishing them is the cheapest analytical output
   available. The live/archive split applies only to `unscored`.

4. **The ordering fix does not rescue edition No. 12 by itself.** Ten runs is
   still ten days. 156 articles in the No. 12 window remain unscreened; a
   one-off catch-up run costs ~$2.82 (screen all 156 at Haiku ~$0.30, analyze
   the ~68 expected to pass at Sonnet ~$2.52). **Structural fixes prevent the
   next occurrence; they do not repair the current one.**

## 2026-08-02 — git cannot merge `pla_watch.db`; reconcile by url, with origin authoritative for identity

1. **A diverged `pla_watch.db` must never be resolved by git.** CI writes the
   database to `main` on a schedule while humans work on local branches, so
   both sides routinely advance from one base. Git sees a binary file and can
   only offer "take mine or take theirs" — and either choice silently destroys
   a day of collection. On 07-30→31 both sides had independently allocated
   article ids from 2727, so origin's article 2731 and the branch's 2731 were
   **different articles**; nothing in `git status` shows that, and either
   resolution loses 40 or 80 articles. **Standing rule: reconcile by `url`
   (the table's UNIQUE key), never by id, and never with a merge driver.**
   `scripts/reconcile_db.py --from-git` does this and re-derives its inputs
   from refs, so it stays correct after CI advances `origin/main` again.

2. **Origin is authoritative for identity; local rows are the ones that move.**
   Origin's ids are already published as `output/article/<id>.html` and
   referenced by the sitemap and feed, so renumbering them breaks live URLs.
   Local capture rows have never been rendered — `--no-analysis` does not
   generate the site (07-31 ruling 1) — so they are the safe side to
   renumber. The merge is therefore deliberately asymmetric, and the
   no-id-drift gate enforces it.

3. **A reconciliation is not landed until its gates pass.** The script exits
   non-zero unless foreign keys, integrity, duplicate urls, id drift, and url
   loss *from both sides* all check out. A merged database that loses a row
   from either parent is a failed merge, not a compromise.

4. **The 07-31 coverage disclosure overstated edition completeness.**
   `methodology.html` told readers editions No. 1–11 drew on "about
   three-fifths" of the relevant material. By the method the passage itself
   states — applying the historical relevance-pass rate to what was never
   screened — the figure is 534 analyzed against ~1,184 estimated relevant
   (697 known + 43.5% of 1,119 unscreened), i.e. **a little under half**.
   Three-fifths would require the unscreened backlog to pass relevance at
   ~17% against 43.5% observed. Corrected, and the method is now stated
   explicitly rather than gestured at. **Standing rule: a published
   completeness figure carries its derivation.**

5. **This is the fourth divergence of this shape**, after the 07-12→16
   uncommitted passes, the 07-17 reconcile, and local `main` drifting 10 CI
   commits behind on 07-30. The recurrence is structural, not careless: a
   mutable binary committed to git and written by two authors cannot be
   made safe by discipline alone. **Resolved by ruling 6 rather than by
   asking people to remember.**

6. **The reconciliation runs as a git merge driver.** `.gitattributes` maps
   `pla_watch.db merge=reconcile-db`, and `reconcile_db.py --merge-driver`
   implements it, so `git merge` performs the row-level reconciliation instead
   of raising a binary conflict. Verified by replaying the 07-30→31 merge: the
   driver resolved it unaided, 0 conflicts, and produced digest `b80e813b` —
   identical to the hand-resolved result.

7. **The published side is identified by content, never by ours/theirs.** The
   merge is asymmetric, but git's ours/theirs says nothing about which side is
   published: merging `origin/main` into a branch makes origin *theirs*, and
   merging a branch into `main` makes it *ours*. Reading identity off position
   would, half the time, renumber the published side and silently repoint every
   `output/article/<id>.html`. The driver hashes both candidates against the
   blob at `origin/main` instead — which is also correct under rebase, where
   ours/theirs invert again. **If neither side matches, the driver refuses and
   leaves a normal conflict.** Guessing at identity is worse than conflicting.

8. **`.gitattributes` names a driver but cannot define one**, so every clone and
   every CI runner must run `--install-driver` once or the mapping silently
   degrades to a binary conflict. The daily workflow registers it after Python
   setup (the script imports only the standard library, so it needs no
   dependencies). The interpreter comes from `sys.executable`, not a hardcoded
   `.venv/bin/python` — CI has no `.venv`, and a fixed path would leave the
   unattended case, where a conflict is most expensive, unprotected.

## 2026-07-31 — An uncommitted template is not a publish guard; account-level API failure is not an article-level one

Four rulings from hardening the pipeline after the 07-30 spend incident.

1. **Leaving a template uncommitted does NOT prevent it from publishing.**
   The 07-30 session left the methodology coverage disclosure as an
   uncommitted working-tree diff, reasoning that an uncommitted file cannot
   reach production. That reasoning is wrong. `site/generator.py` renders
   from the **working tree**, and CI commits `output/`. A scrape-only
   capture run on 07-31 rendered the unreviewed draft straight into
   `output/methodology.html`; had that run been CI, the draft would have
   published. **Standing rule: the only thing that keeps unreviewed copy
   off the site is not rendering it.** `--no-analysis` now skips site
   generation entirely, for this reason and because regenerating from a
   knowingly-incomplete DB rewrites the public record from a partial view.

2. **`DAILY_ANALYSIS_CAP` 40 → 55 (analyst-approved).** The sizing rule is
   now explicit: fresh scrapes get `(1 - BACKLOG_RESERVE_FRACTION) × cap`
   slots, so break-even against a scrape rate S requires
   `cap ≥ S / (1 - reserve)`. Measured intake is 32–40/day (avg ~37) over
   07-26→07-31, so at a 0.3 reserve break-even is 37 / 0.7 ≈ 53. **40 was
   still below it** — the 07-30 run deferred 9 fresh articles. At 55 the
   deferral warning goes silent at typical intake and ~18 slots/run drain
   the backlog (~63 days for the current 1,130).

3. **An account-level API failure must abort the run, not iterate.** When
   the spend limit hit on 07-30, nothing distinguished "this article
   failed" from "the account is blocked", so the pipeline made 40 further
   doomed calls and the translation backfill made 60. `FatalAPIError` now
   marks account-level failures (401/402/403, or a message naming a usage
   limit, credit balance, billing, or quota) and every caller aborts the
   batch on it. **429 is deliberately NOT fatal** — rate limits are
   transient, and aborting on them would be a regression. The billing
   marker now keys off this definitive signal rather than inferring
   credit exhaustion from "everything failed".

4. **Never write a record that satisfies the writer but violates the gate.**
   The 07-30 session fixed the blank-summary bug in the backfill scripts
   only; `pipeline.py` still wrote `analyzed_at` on any article with a
   translation, regardless of summary. That is the same defect that
   produced 14 damaged rows. The pipeline now requires a non-empty summary
   before marking an article analyzed; without one it stays pending and
   retries.

**Spend pre-flight (`scripts/spend_guard.py`).** Both backfills now
estimate cost from token arithmetic and current published prices, probe
API access with one cheap call before spawning workers, and require
`--confirm-spend` above $5. **The honest limit: the API exposes no
remaining-balance endpoint, so this checks cost, never headroom.** Only
the Console can answer "can I afford this?" — the guard's job is to make
the number visible and acknowledged instead of felt. Verified live against
the active block: the probe caught it and aborted at zero article calls.
Remaining work is estimated at **~$25** (60 translations ≈ $1.88;
1,130 screenings ≈ $23.47), against the ~$50 that was guessed on 07-30.

## 2026-07-30 — No edition for week ending 2026-07-25; the collection gap is recorded, not filled

**Ruling (analyst-approved 2026-07-30): no edition is published for the week
ending 2026-07-25.** The next edition is **No. 12, week ending 2026-08-01**,
on a full seven-day window. Issue numbering stays sequential; the cadence
breaks, and the break is the honest record.

1. **The window has one observed day of seven.** `scrape_runs` jumps from
   run 90 (2026-07-16) straight to run 91 (2026-07-25) — there are no run
   rows at all for 2026-07-17→07-24. The No. 12 window (07-19→07-25) holds
   only 2026-07-25: 29 articles, 8 relevant, 0 model-flagged.
2. **Correction to the 2026-07-25 entry below.** That entry describes the
   outage as scheduled runs failing at "Commit updated database and site
   output." True as far as it goes, but the consequence was understated:
   the runs' DB writes were never persisted either, so the articles for
   those eight days were never captured. The loss is permanent, not merely
   uncommitted.
3. **Backfill was tested and rejected as unsound.** `pipeline.py --date
   <d> --dry-run` retro-scrapes only what the listing pages still surface,
   and recall decays with age. Control: 2026-07-16 was captured live at
   **33 articles**; retro-scraped on 2026-07-30 it yields **3**. Gap dates
   yield 7 (07-20) and 11 (07-24) against a ~35/day live baseline.
   Recovering a recency-biased 10–30% of each day and presenting it as the
   week's observed record would misstate coverage. Standing rule: the
   scraper is listing-bound and **retro-scrape output is never a
   substitute for live collection** in an edition's evidence base.
4. **The cadence-gap warning from `validate_output.py` is expected and
   correct.** Do not suppress it. It is the artifact that records the
   outage; a future reader must be able to see that the week was
   unobserved rather than uneventful.

## 2026-07-30 — API spend limit reached mid-backfill; collection must survive analysis failure

The backfills exhausted the account's configured API usage limit (access
returns 2026-08-01 00:00 UTC). 131 articles were recovered before it hit;
60 translations and 1,057 screenings remain. Three durable lessons, two of
them fixes.

1. **Cause, recorded plainly.** The backfill was authorized on a ~$50
   estimate that was never checked against the account's *remaining*
   headroom on its monthly cap, and the two backfills were run
   concurrently rather than in sequence, doubling the draw. Estimate the
   spend *and* verify headroom before starting a bulk run; run bulk jobs
   one at a time.
2. **CI discarded collection on any pipeline failure — now fixed.**
   `pipeline.py` stores scraped articles before its first LLM call, then
   `sys.exit(2)` on total analysis failure. The "Commit updated database
   and site output" step carries an `if:` with no status function, so
   GitHub implicitly requires `success()` and skipped it — destroying the
   runner with that day's articles still inside. **This is the same
   mechanism that lost 2026-07-17→24**, reached from a different trigger:
   the earlier fix addressed the rebase and derivative churn, not the
   underlying "analysis failure forfeits collection" behavior. New step
   `Persist scraped articles (if pipeline failed)` commits `pla_watch.db`
   **only** — `output/` is deliberately excluded so this cannot become a
   route around the validator gate that keeps a broken render out of
   production. Unanalyzed articles keep `passed_relevance` NULL and drain
   as backlog.
   **Standing rule: collection and analysis are separate stages, and a
   failure in the second must never forfeit the first.**
3. **`pipeline.py --no-analysis`** scrapes and stores without any LLM call,
   for use during an outage or spend block. Note `ANTHROPIC_API_KEY=""`
   does *not* achieve this — `config.py` pops an empty value and falls
   back to `.env`, so the run attempts analysis anyway. 2026-07-30 was
   captured (40 articles) before this flag existed, via a run that failed
   every analysis call.
4. **A blank summary must block the write, not the deploy.** The first
   backfill run kept translations when `summarize()` failed, on the theory
   that a translation is the expensive part. That produced 14 records that
   read as complete but tripped `validate_output.py` rule 6 ("no analyzed
   article has a blank summary") and **failed the deploy gate**. Both
   backfill scripts now treat a missing summary as a reason not to write
   at all, leaving `analyzed_at` NULL for a clean retry. The 14 were
   repaired by clearing `analyzed_at` (translations preserved), which
   removed them from generated output and re-queued them; validator back
   to green at the 9 historical warnings. Rule: never write a record that
   satisfies a script's notion of "good enough" but violates the deploy
   gate's — the gate is the contract.

## 2026-07-30 — The analysis cap sat below the scrape rate; 41% of the corpus was never screened

**The largest of the three 2026-07-30 findings.** 1,119 of 2,720 articles
(41%) had `passed_relevance IS NULL` — never evaluated for relevance at all,
so invisible to every edition and to every count of what the corpus contains.

1. **Mechanism: a starved queue, not a slow one.** `pipeline.py` built
   `queue = new_queue + pending + unscored` and truncated it to
   `DAILY_ANALYSIS_CAP` (15). Every run inserts ~28–35 fresh articles, so
   `new_queue` alone always overflowed the cap and **the slice never reached
   the backlog** — it received exactly zero slots per run, permanently. The
   comment above that code claimed the backlog "drains every run to fill
   capacity… can't stay invisible forever." That claim was false for the
   entire life of the project, and its presence is why the behavior went
   unexamined. Corrected in place.
2. **Two compounding consequences.** (a) The 163 translation failures were
   never retried even once — `pending` was starved by the same slice, which
   is why article id 3 sat unretried for 83 days despite a retry path that
   looked correct on inspection. (b) The unscored pile grew by
   `inserted − cap` ≈ 17–18/day: 1,119 over 66 days, matching the arithmetic
   almost exactly.
3. **Scale of the editorial gap.** At the historical relevance pass rate of
   **44%** (697 of 1,601 scored), the unscreened 1,119 contain an estimated
   **~487 relevant articles** — against 697 relevant articles known. Taken
   with the translation losses, editions No. 1–11 drew on roughly 60% of the
   relevant material actually scraped. No published claim about weekly
   coverage completeness survives this unqualified.
4. **Fixes (analyst-approved 2026-07-30).**
   - `BACKLOG_RESERVE_FRACTION` (0.3): the backlog now gets a guaranteed
     share of the cap instead of zero, and unused new-article slots spill
     to it. This makes the "can't stay invisible forever" claim true.
   - `DAILY_ANALYSIS_CAP` **15 → 40**, above the ~30/day scrape rate. A cap
     below the scrape rate guarantees unbounded backlog growth regardless of
     any reservation — the reservation controls *who* is starved, not
     *whether*.
   - New warning when the cap defers freshly scraped articles. Sustained
     firing means the cap has fallen below the scrape rate again; treat it
     as a capacity alarm, not noise.
   - `scripts/backfill_unscored.py` clears the 1,119. Unlike
     `backfill_translations.py` it **does** run relevance scoring, since
     these articles have no prior score to preserve.
5. **Standing rule: `DAILY_ANALYSIS_CAP` must exceed the daily scrape rate.**
   It is a cost ceiling, and setting a cost ceiling below the intake rate
   silently converts it into a permanent data-loss mechanism. If cost
   requires a lower cap, reduce intake (narrow sources or the keyword
   filter) rather than letting unprocessed articles accumulate unbounded.

## 2026-07-30 — Translation fix: two independent failures, not one

Correction to the diagnosis entry below, which named only the token cap.
Clearing the backlog surfaced a **second, unrelated** failure; both are now
fixed and the entry below stands as the record of the first.

1. **Unescaped inner quotes (genuine formatting drift).** The translation
   prompt instructs the model to preserve quoted rhetorical language
   ("决不", 「」), and a literal `"` inside a JSON string value terminates
   the string early. Example (article 2624): `the border soldier's "pure
   love."` — parse failed at position 1455 of a **complete, untruncated**
   31,132-character response. This is a different bug from the token cap
   and would have persisted after fixing it alone.
2. **Fix: forced tool use for translation.** `Analyzer.translate()` now
   calls `_call_tool()` with an `emit_translation` tool
   (`title_en` / `body_en`) and `tool_choice` pinned to it. Tool inputs are
   serialized and escaped by the API and arrive pre-parsed, so the entire
   class of escaping failure is gone. The translation prompt no longer
   asks for raw JSON. `_parse_json` now serves only the three short-output
   tasks (relevance, summary, categories), whose outputs rarely carry
   embedded quotes.
3. **The pre-existing `_parse_json` TODO was half right, and credit is
   due.** It correctly identified drift on long translations and correctly
   prescribed tool use. What it got wrong: it treated drift as the *whole*
   problem (truncation caused roughly two-thirds of the losses and is
   deterministic, not intermittent), and its alternative suggestion —
   `output_config.format` structured outputs — is not available on
   `claude-sonnet-4-6` and would have required a model change.
4. **Ruling: the translation contract is the tool schema, not prose.** Do
   not reintroduce "return raw JSON" instructions to the translation
   prompt, and do not loosen `_parse_json` to accommodate translation
   output. If a future task emits long free prose, give it a tool.
5. **`stop_reason` is checked before parsing** in both `_call` and
   `_call_tool`. Truncation now raises a message naming the ceiling
   instead of surfacing as a generic parse error — the misdirection that
   hid the token cap for 83 days.

## 2026-07-30 — Translation token cap has silently excluded every long article since launch

**Diagnosis only; no fix applied.** 163 of 697 relevant articles (23%)
passed the relevance gate but were never translated, and so were invisible
to all 11 published editions.

1. **Root cause: `Analyzer.translate()` calls with `max_tokens=4000`**
   (`analysis/analyzer.py:173`) and asks for both `title_en` and `body_en`
   in one JSON object. A long Chinese body cannot render into English
   inside that ceiling, the response truncates mid-JSON, `_parse_json`
   raises, and `analyze()` returns without `title_english`, so
   `pipeline.py:256` skips the write.
2. **The failure is length-determined**, not random. Failure rate by
   Chinese body length: <1000 chars 7% · 1000–2000 17% · 2000–3000 37% ·
   3000–3800 32% · **3800–5000 95% · 5000+ 100%**. No successfully
   translated article anywhere in the DB exceeds 3807 characters.
3. **The retry path is a no-op for these articles.** `analyzed_at` stays
   NULL, so they re-enter the queue via `get_articles_pending_analysis()`
   every run and fail identically with unchanged parameters. Article id 3
   (scraped 2026-05-08) has been retried on every run since launch. The
   comment at `pipeline.py:277` ("a later run retries it") is true but
   misleading — retry without changed parameters cannot succeed.
4. **Editorial consequence, which is the part that matters.** The excluded
   set is not random noise: it is the *longest* PLA Daily pieces — the
   军营观察 features and long-form policy essays that carry the most
   analytical content. Every edition to date has drawn on a corpus
   systematically truncated against its most substantial material. Any
   claim about weekly coverage completeness made before this is fixed
   should be read with that in mind.

## 2026-07-25 — No. 11 (2026-07-18) editorial corrections before publish

Pre-publish QA (editorial-integrity role) failed the edition; corrected
verbatim-from-source and shipped (analyst-approved). Three findings:

1. **Date: "April 2025" → "April 2026" (CRITICAL).** The Y-20B's first
   international flight is dated by the source (PLA Daily, 81.cn/16473227,
   published 2026-07-12) as "今年4月" — this year, April — i.e. 2026, not
   2025. Corrected across dek/signal/opening_note/what_stood_out/
   what_im_watching_next in the sidecar and the four mirrored spots in the
   LinkedIn file. Standing rule reaffirmed: relative time expressions
   ("今年") resolve against the source's publication date, never guessed.
2. **Engine "WS-20": source-"confirmed" → "widely identified as the WS-20"
   (MAJOR).** The source says only "新型国产发动机" (a new domestically
   produced engine) and never names it. The WS-20 identification is
   analyst/open-source attribution and must be framed as such, not
   attributed to the PLA Daily article.
3. **Routine-Baseline named units now traceable (MAJOR).** The frugality
   essay, 80th GA party-branch compliance piece, and Rocket Force
   governance article named in `what_was_routine` were added to
   `source_trail` (16473917 / 16473559 / 16473317, verbatim DB titles,
   is_significant=false). Rule: any named unit/article in edition prose
   must have a source_trail entry, not merely an untraced DB row.

## 2026-07-25 — Committed editorial derivatives are authoritative; no mtime-based regeneration

1. **`site/assets/editorial/derivatives/*` committed files are the build
   truth.** `generate_editorial_derivatives.py` writes a derivative only
   when the file is missing; intentional regeneration requires `--force`.
   Rationale: mtime staleness is meaningless in fresh git checkouts (git
   does not preserve mtimes), and platform-dependent JPEG encoding meant
   CI rewrites never byte-matched the committed files — which dirtied the
   tracked tree and broke every scheduled daily run 2026-07-18→07-24 at
   the `git pull --rebase` in "Commit updated database and site output."
2. **Workflow rebases use `--autostash`** (`daily_update.yml`, all three
   `git pull --rebase` calls) so a stray tracked-file modification degrades
   to a stash round-trip instead of killing the run.
3. If a source image changes, regenerate its derivatives locally with
   `--force` and commit the new bytes in the same change.

## 2026-07-17 — No. 10 final text: revised package adopted, edition badge ruling

1. **The revised draft package (`pla-watch-draft-2026-07-11-revised.zip`,
   Jul 12) is the final approved text of No. 10**, superseding the earlier
   package published first. All seven prose fields (dek, signal, opening
   note, what stood out, why it matters, routine baseline, term explanation,
   watching next) replaced verbatim via the established extraction path;
   round-trip verified against the package. Title, dates, window,
   issue_number, byline, term name, source trail (13/13), media, and covers
   unchanged. No public correction banner: same facts and sources,
   editorial revision only.
2. **The revised package's `edition_label: "Model-flagged"` is rejected.**
   "Model-flagged" is an article-level mechanical triage state;
   the edition classification ("Significant") is the analyst's human
   editorial judgment and stays. The visible model-flagged article count
   remains a separate surface.
3. **The earlier LinkedIn file (article body pasted in error) is replaced**
   by the revised package's 15-line post. Local file only; never posted
   externally by an agent.

## 2026-07-17 — Session recovery, reconciliation onto origin/main, and No. 10 publication

1. **Recovery mechanics.** The 2026-07-12/13/16 uncommitted passes were
   snapshotted onto local-only branch `rescue/unfinished-pla-watch-2026-07-16`
   (three separated WIP commits; `.claude-flow` excluded) and re-applied onto
   `origin/main` in a clean worktree (branch
   `reconcile/unfinished-pla-watch-2026-07-16`). Local `1f0917c` was verified
   by identical patch-id to be the same change as remote `5e92dc4`
   (cherry-picked); it was not merged. Local `main` was left untouched.
   Output was regenerated fresh from the latest remote DB, never carried
   over from the stale snapshot. Rescue WIP commits are safety history only.
2. **No. 10 (week ending 2026-07-11) integrated from the approved draft
   package** (`pla-watch-draft-29148303565.zip`) via
   `backfill_sidecar_bodies.py`: body fields extracted verbatim from the
   analyst-approved HTML (round-trip verified), issue_number 10 assigned,
   author fields normalized from the package's stale
   "Founder & Principal Analyst" to the ruled public identity, trail
   `title_zh` filled by exact URL match (13/13). No prose was composed.
   The edition ships without `executive_readout` / `recurring_threads`
   by analyst instruction, superseding for this edition the earlier
   adopt-from-No. 10 plan.
3. **No. 10 Night Desk veil = `jin-class-type-094-ssbn`**, routed to
   `pw-post` for edition 2026-07-11 only. Grounded: the manifest entry was
   fetched 2026-07-11 and already tied by exact URL to this edition's lead
   SLBM article (81.cn/16472265); PD (U.S. gov via CRS RL33153); duo-navy
   derivative generated deterministically. Its existing home/article
   routes are unchanged; the J-20 homepage atmosphere is unaffected.
4. **`edition_label: "Significant"` kept for No. 10** as the
   analyst-approved edition classification carried by the approved package,
   consistent with Nos. 5, 6, 8, 9. Reader-facing automated counts remain
   "model-flagged" everywhere.

## 2026-07-16 — Homepage atmospheric image decoupled from the model-flagged story

1. **The homepage veil is an atmospheric publication visual, selected only
   by the explicit manifest field `"placement": "homepage-atmosphere"`** —
   never by the daily model, article matching, or flag status. This
   supersedes the veil half of the 2026-07-12 §3 ruling: the model-flagged
   signal card in the hero's right rail still ties to the most recent
   flagged item by exact URL (`_select_home_editorial`, unchanged), but
   the image behind the hero no longer illustrates that story. The two are
   separate layers; the card carries no image, and the image credit never
   carries flag language. Missing/invalid atmospheric entry or derivative
   → text-led hero, card unaffected (`_select_home_atmosphere`).
2. **The homepage atmospheric image is the Chengdu J-20 photograph by
   emperornie** (Flickr photo 44040541250 via Wikimedia Commons, CC BY-SA
   2.0; manifest id `chengdu-j20`), replacing the Jin-class SSBN in that
   role. The Jin-class entry keeps its `home`+`article` routes for the
   signal-card selection and the article-page figure. The duo-paper veil
   derivative is a modified adaptation and remains subject to CC BY-SA
   2.0 including ShareAlike, recorded in the manifest note.
3. **Homepage-only crop mechanics:** `.home-hero .pl-veil` upscales the
   atmospheric image one step past cover (118%) so the manifest
   `mask_focus` (10% 8%) can seat the airframe in the lower-right field;
   mobile (≤900px) resets to cover with its own position (62% 42%,
   `!important` over the inline style). The signal card gains the same
   paper-whisper backing the ledger already had, so its text never sits
   directly on the image. No new motion: the shared veil-in settle is the
   only animation, and reduced-motion/no-JS receive the settled state.

## 2026-07-12 — Production-completion pass: first paint, editorial imagery, prompt hardening

1. **Above-the-fold content never starts at opacity 0.** The reveal system
   keeps `[data-reveal]` for below-fold sections, adds a `data-reveal="art"`
   variant (container always visible; only inner draw-path/ink-node/rule
   primitives animate), and above-fold identity blocks (homepage hero +
   ledger, PW post hero + cover figure, PW index latest-edition module,
   signals header/dashboard, terms head, first archive entries) render
   statically. The observer JS is wrapped in try/catch (failure → `.no-anim`)
   with a post-load in-viewport sweep so no content can stay hidden on
   short pages. Every new component must follow this rule.
2. **Editorial imagery is manifest-only and exact-URL matched.** All
   editorial images come from `site/assets/editorial/manifest.json`
   (curated via `scripts/fetch_editorial_image.py`, which enforces the
   PD/CC0/CC BY/CC BY-SA allowlist from fetch_pla_watch_media). Association
   to stories is by exact article URL or edition date; the manifest's
   category/thread fields are curation context and are deliberately not
   used for automatic matching, so an image can never drift onto the wrong
   story. No match → text-led layout (the designed fallback). Sidecars stay
   canonical: weekly editorial images merge at render time only.
   Every placement carries credit + license + "visual context, not
   evidence" language.
3. **Homepage figure ties only to a model-flagged item** within 7 days of
   the brief date, labeled with the standing "Model-flagged" kicker; the
   ranking language in the Analyst Readout states its mechanical basis
   ("by category priority and relevance; not model-flagged") so automated
   triage is never dressed as editorial judgment.
4. **Byline correction.** Earlier in this 2026-07-12 pass the fallback
   author title in both renderers was changed to "Founder & Principal
   Analyst, China Mil Watch." That change was not analyst-approved and has
   been reverted in `scripts/generate_pla_watch.py` and
   `scripts/rerender_pla_watch.py` before any edition published with it.
   The 2026-07-09 ruling stands: the byline is "Benjamin Yang — Principal
   Analyst, China Mil Watch." The two editions whose sidecars carry no
   `author_title` (2026-05-09, 2026-05-16) render the approved title via
   the fallback constant; no historical sidecar was touched.
5. **Weekly prose mechanics are enforced at draft time, not by rewriting
   history.** PROSE MECHANICS/SYNTHESIS rules added to STYLE_EXTRACT and
   the tool schema; `prose_warnings()` prints non-blocking findings (em
   dashes, banned transitions, stacked "not X but Y") for the human
   reviewer. Editions 1–6 contain 32 such violations and stay as published.
6. **Homepage brief-date demoted to h2** (one h1 per page). The daily
   Analyst Readout now names the record's top-ranked item on no-flag days,
   makes single-source coverage limits explicit, and draws its watch line
   from a fixed per-category table of falsifiable indicators.

## 2026-07-12 — Production visual system: Source-Derived Signal Graphics

Concept A ("Signal Veil") is adopted as the production imagery system on
both surfaces: a duotone crop of the manifest photograph, keyed to the
ground it sits on (paper duotone on Paper Ledger, navy duotone on Night
Desk), shaped by a soft radial mask union so no hard rectangle ever reads
as a conventional photo card. Concept C's Floyd–Steinberg dither is kept as
a secondary "Paper Ledger" fallback, selected per image via the new
optional manifest field `treatment` (`"veil"` default, or `"dither"`).
Concept C's bracketed analyst-mark provenance is used on desktop
(`.src-bracket` / `.nd-src-bracket`); Concept A's compact inline credit
line covers mobile and dense cards. Concept B's tick row (one tick per
Source Trail record, red = model-flagged, with a textual explanation and a
small-screen numeric-only fallback) is retained, but only on Night Desk
surfaces (weekly post hero, index latest-edition module) — Concept B's
photographic strips and ghost edition numeral are rejected as too
decorative for either surface. No conventional photo figure or captioned
image card renders on the homepage hero, article header, weekly hero, or
index module; all four are replaced by the veil/dither system with a
text-led fallback when an image, manifest entry, or derivative is missing.
Derivatives (`{id}-duo-paper.jpg`, `{id}-duo-navy.jpg`, `{id}-dither-ink.png`)
are generated deterministically at build time from the manifest's source
images (Pillow: grayscale + autocontrast, duotone colorize or Floyd–Steinberg
dither; same input produces identical output bytes) via
`scripts/generate_editorial_derivatives.py`, committed to
`site/assets/editorial/derivatives/` and copied to the output tree
alongside the source images. The manifest remains the sole source of
editorial-image metadata; sidecars are untouched. A missing image,
manifest entry, or derivative always falls back to the existing text-led
layout, never a broken reference.

## 2026-07-11 — Analyst decisions: metadata fields, labeling, commit sequence

1. **`executive_readout` adopted** beginning with Edition No. 10: optional
   sidecar field, 2–4 bullets, manually authored by the analyst at publish
   time. It must never be synthesized automatically — not from the week's
   records, not from prior editions. Render-if-present; historical editions
   stay unchanged. (Implements ROADMAP T5.)
2. **`recurring_threads` adopted** for Continuity Strip Phase 2: optional
   sidecar field carrying slugs from the controlled vocabulary in
   docs/VISUAL_AND_MOTION_SYSTEM.md §4. Assign a slug only when the edition
   *materially analyzes* the thread (a standing section engages it) — never
   for passing mentions; typical count 0–3 per edition, and editions with
   none stay empty. New slugs require a DECISION_LOG entry. Historical
   backfill only by re-reading published edition text, never from memory.
3. **"Model-flagged" ratified as the only reader-facing label for automated
   classifications**, with the standing concise explainer ("a triage cue
   produced by software, not an editorial judgment"). Verified 2026-07-11:
   every automated surface already renders "Model-flagged" (daily article
   kicker, archive badge/filter, signals dashboard, weekly counts). The
   analyst-assigned *edition* badge (Significant / Routine / Pilot) is
   editorial, not automated, and is exempt — it keeps its name. Internal
   identifiers (`is_significant`, `n_significant`, CSS class names) are not
   reader-facing and stay unchanged.
4. **Commit sequence approved** for the current working tree: (a) docs +
   Claude operating system → (b) frontend source/templates/scripts →
   (c) regenerated output → (d) validation/cleanup fixes where needed.
   Nothing committed until the analyst reviews the staged plan.

## 2026-07-11 — Project operating system established

Durable doctrine now lives in six docs (product/editorial, design system,
visual & motion, architecture & publishing, agent workflows, roadmap);
CLAUDE.md is a compact pointer file; PROJECT_STATE.md is state-only.
Constraining rulings made in this pass: the dual-surface identity (Paper
Ledger / Night Desk) is confirmed doctrine, with per-surface crimson values
kept deliberately distinct; crimson is reserved for analytical signal;
IBM Plex Mono is capped at one-line metadata; photo-overlay cover PNGs are
demoted to og:image duty in favor of generated SVG Edition Plates (ROADMAP
T2); docs/ROADMAP.md supersedes DESIGN_BACKLOG.md; the skillui-extracted
design skills were retired in place as inaccurate (docs/DESIGN_SYSTEM.md is
authoritative); README/METHODOLOGY/style_guide OSINT phrasing was aligned
with the 2026-07-10 identity decision. New sidecar fields may only be
optional and render-if-present (executive_readout, recurring_threads —
pending analyst adoption).

## 2026-07-10 — Public identity language: Mandarin-source monitoring, not OSINT

The daily site's title, meta descriptions, masthead kicker, footer, and
methodology intro described the project as an "open-source intelligence
tool/pipeline." Replaced everywhere with the project's identity statement:
"independent Mandarin-source monitoring and analysis project tracking Chinese
military and security reporting from official and authoritative PRC sources."
Rationale: matches the stated identity, avoids intelligence cosplay, and drops
the "tool" framing. The "Signal Posture: Elevated/Routine" homepage chip
(driven solely by model flags) was replaced with the literal flag count for
the same reason. Reversal requires an explicit decision, not copyediting.

## 2026-07-10 — "Model-flagged" label extended to the daily site

The 2026-07-10 weekly-page rename ("significant" → "model-flagged") left the
daily surface inconsistent ("Significant" stat, "Analytical signal" kickers,
"Significant only" filter, signals-page labels, readout strings). All
user-visible daily labels now say "model-flagged"; underlying DB fields,
sidecar counts, and stats are untouched. Explainer copy added at each surface
("a triage cue, not an editorial judgment") linking to
methodology.html#model-flagged, which now documents a five-layer ladder:
scraped record → model processing → model flag → analyst judgment → weekly
brief. The methodology explicitly states the homepage daily readout is
assembled automatically (pipeline output, not analyst prose).

## 2026-07-10 — Homepage carries a real latest-edition module

`site/generator.py` now reads the newest weekly sidecar
(`_load_latest_pw_edition`) so the homepage sidebar shows issue number,
week-ending date, title, and dek instead of a generic CTA. Display-only: the
leading "The PLA Watch: " title prefix is stripped for the module; nothing
missing from a sidecar is invented. PLA Watch archive entries anchor on the
issue number and show a distinct-source count derived from the trail;
month grouping deferred at 9 editions.

## 2026-07-10 — n_significant means model-flagged, and is now labeled so

Traced: `n_significant` is computed by `generate_pla_watch.py::compute_stats`
as the count of `is_significant` articles among the week's relevance-passing
DB articles at generation time; `is_significant` itself is set per article by
the LLM categorization step (`analysis/analyzer.py::categorize`, conservative
~1-in-20 rubric). It is a model flag over the monitored week, not editorial
judgment and not a property of the curated source trail. Verified: edition 2's
published count (3) exactly matches the DB's model flags for 2026-05-10→16;
edition 1's count (1) matches the flags analyzed before the pilot was
generated (the 2026-05-07 Wei Fenghe verdict article; three 2026-05-09
articles were flagged at ~14:13 that day, after generation). Ruling applied:
counts are technically valid and stay unchanged in sidecars; the public label
"N significant" was misleading and is renamed to "N model-flagged" in
`pla-watch-post.html` (hero meta, snapshot stat, snapshot bar + legend,
sidebar row), `pla-watch-index.html`, and `pla-watch-archive.html`; weekly
pages rerendered from unchanged sidecars. This coexists with the 2026-07-10
ruling that editions 1–2 had no editorially significant articles: the trail
carries editorial selection, the count reports the pipeline flag. Daily-site
per-article "Significant" badges (backed by displayed model reasoning) were
left as is — separate surface, analyst's call if they should follow.

## 2026-07-10 — Analyst rulings on historical gaps

- `the-pla-watch/linkedin/2026-05-10.txt` is most likely the pilot edition's
  LinkedIn post under its publish date. Left unrenamed.
- Editions 1–2 trails carry no `is_significant` flags because no significant
  articles arose those weeks. The n_significant counts (1, 3) in early
  sidecars are pipeline auto-counts; reconciling them is the analyst's call.
- 2026-06-20's missing "Why It Matters" section stays as published.

## 2026-07-10 — Original Chinese headlines in the source trail

Trail entries carry `title_zh`, sourced only from the daily-monitoring DB's
`title_original` by exact URL match (100% coverage, all 9 editions).
`generate_pla_watch.py` includes it for new editions; the backfill tool fills
history. Chinese text is never composed, retranslated, or fuzzily matched.

## 2026-07-09 — Sidecar JSON is the canonical edition record

Sidecars now store full body text alongside metadata and the source trail.
Rationale: 7 of 9 sidecars had no body fields, so the "safe" re-render script
would have silently replaced published prose with empty pages. Body text was
backfilled by extraction from the published HTML (verified verbatim — a
round-trip check confirmed every paragraph identical) and
`generate_pla_watch.py` writes body fields at publish time.
`rerender_pla_watch.py` refuses empty-body sidecars without
`--allow-empty-body`.

## 2026-07-09 — Both weekly renderers share one Jinja environment

`scripts/pw_env.py` with autoescape ON (the generator previously rendered
unescaped model output) plus `format_date` and `inline_markup` filters.
`inline_markup` whitelists bare `<strong>`/`<em>` because the 2026-05-16
sidecar carries literal emphasis tags; everything else is escaped.

## 2026-07-09 — Date display convention

Reader-facing week-ending labels use "4 July 2026"; ISO `YYYY-MM-DD` is kept
in tabular/meta contexts (covers range, snapshot sub-labels, JSON). Do not
mix within one label.

## 2026-07-09 — Historical data gaps are warnings, never fixed by invention

Missing per-item trail dates (editions 1–3), missing LinkedIn files
(editions 1–3), missing `is_significant` flags (editions 1–2), the pilot's
2-day window, and the 2026-06-20 missing "Why It Matters" section stay as
recorded facts + validator warnings. Only two normalizations were allowed:
`label`→`title` key rename (same string) and pilot trail `source` filled from
its single-entry `sources_seen` (what the published page already displayed).

## 2026-07-09 — Public role title

"Principal Analyst, China Mil Watch" everywhere (scripts, sidecars, pages).
Bio phrase: "principal analyst at China Mil Watch".

## 2026-07-09 — Issue numbering

Chronological No. 1–9 assigned from week-ending order, stored in sidecars,
displayed as "Vol. I · No. N", validated unique + chronological. New editions:
1 + count of earlier sidecars.
