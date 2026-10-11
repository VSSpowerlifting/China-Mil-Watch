# IPR convergence and release gates — next-stage engineering framework

**Prepared:** 2026-10-10 (America/New_York)  
**Starting main:** 51769ae3e82e038be1853fa15a55dc2840941fc7 (after documentation-only frontend Phase 0 PR #371).  
**Nature:** planning and engineering handoff only; not a new production authority, new editorial format, deployment request, implementation PR, or replacement for existing project doctrine.  
**Decision standard:** preserve the current publication and source record while turning already-created work into a small number of independently reviewable, verifiable releases.

## 0. Executive architectural ruling

**Converge before expanding.** IPR's principal risk is no longer a shortage of implementations. Multiple partially integrated or stacked workstreams target adjacent trust boundaries: Sunday Brief selection and delivery; archival evidence custody; output/public projection; Pages deployment; frontend design; country-source admission; and private research formats.

Do not implement a second framework for a capability already tracked in a specific issue. This file is an **integration and sequence map**, not a runtime controller. Truthful state remains in Git refs, exact PR heads, CI run and job receipts, source manifests, DECISION_LOG.md, PROJECT_STATE.md, and issue-specific reviews.

The three independent authorizations are:

1. **Implementation verified:** exact-head code and synthetic/offline tests passed within a declared scope.
2. **Operationally qualified:** the intended real pathway and failures were observed/rehearsed against its proper infrastructure and custody receipts; a green guard-skip, mock provider, or fictional store does not qualify.
3. **Owner/editorially authorized:** actual source-use, manuscript, visibility, budget, account and release decisions are separately recorded. The former two never imply the third.

Every phase must declare all three states separately. Null/unknown is a hold, not an implicit pass.

## 1. Live workstream registry and ownership

| Lane | Existing authority | Current engineering situation as inspected | Boundary and next action |
| --- | --- | --- | --- |
| Maintenance audit | #333; PR #370 | Two-file void-element audit parser fix; full PR offline workflow #38098487334 still running when inspected | Review its final exact-head test, validator and DB/output preservation receipts; do not merge based on isolated cases alone |
| Sunday Brief operations | #366, #355, #353; merged #365/#368 | Readable prose handoff and owner-reviewed manual exact-file replay exist; scheduled reviewed-artifact reuse/exactly-once remains unresolved | One approved manuscript / one immutable attachment; original-source review; no second LLM after signoff; no forced source or SMTP send |
| Evidence custody | #332, #342, #326; C1 #356 and C2-A #359 merged; C2-B–G #360–#367 open/stacked | Rehearsal and fictional spend/source fences, not live secure storage | Integrate stack serially only after independent tests; keep private mode disabled, source rights unresolved and actual storage provider unselected |
| Cutover and Pages release QA | #343, #345–#351, particularly #346 and #351 | Potential cross-workflow stale Pages deployment and recoverability failures documented; no verified historic incident asserted | Model and test full-output assembly, rollback, freshness fencing and both Daily/manual deploy paths before any evidence cutover |
| Country desk capability | #373 and PR #372; #186/#196/#205/#221/#236/#250 | Separate 20-task disabled dependency/source qualification framework | Reuse that DAG, manifest and tests. No new overlapping country program here; source family is the unit of review |
| Frontend | PR #371 merged; DECISION_LOG 2026-10-10; older #314/#323 remain open | Phase 0 decisions and evidence landed, not a deploy; Phase 1 remains separately governed | Design infrastructure from fresh main in its own lane; no shared renderer/deploy edits while public-projection integration is under review |
| Analytical formats | #318–#322; Timeline PR #181; Dossier PR #347; Briefs audit PR #325 | Private/draft-only or review-gated integration, with outstanding rights and content authorization | Integrate under Analysis only after real source/use, source-identity and publication gates; no automatic public route |
| Operations/backlog | #268/#250 and merged #305/#309–#315 | Retry and telemetry fixes have merged; cost/backlog and Oct 7 cancellations still need real-run evidence | Re-measure from one pinned executed Daily, not an old selection estimate or skipped scheduling wrapper |

This matrix is a **dated inventory**, not an automatic status feed. At the beginning of each implementation session, refresh every relevant head, base, merged flag, workflow attempt, and linked issue. PR #372 is the desk program's own planning authority and must not be transplanted into this file.

## 2. Dependency structure: critical path versus parallel work

The only critical release path for changing how IPR publishes archival evidence is:

    Independent source-use and retention decision (#326)
       + custody/projection integration reviewed (#332/#342, C2 disabled until separately authorized)
       + recoverable final output assembly and full artifact validation (#351/#343)
       + fenced, attestable Pages publication across all writers (#346)
       + historical/canonical-route and source-provenance parity
       + owner exact-generation release approval
          -> controlled production cutover (separate authorization, PR and rollback plan)

A successful C2 fictional exercise alone **cannot** enter that final arrow. A change to record.html alone **cannot** make source text private: source bodies are also present in the public tracked SQLite database and old public outputs/history. No legal conclusion is inferred from a read-only technical audit.

Other useful work can proceed **without being on that critical path**, provided file ownership is disjoint:

- Sunday manuscript selection, readable handoff and no-model replay remain in existing Sunday modules; do not unlock scheduled send by changing the same templates or workflow concurrently.
- Country-specific candidate source qualification proceeds under #373/PR #372 and each source-family issue. No automatic status promotion.
- Frontend Phase 1 may produce reusable isolated CSS/assets/tests, but must not merge public-record template/output substitutions over public-projection or publication contracts.
- Read-only editorial source checking and paused Dossier/Timeline content preparation may occur, but no public approval is inherited from another format.

## 3. Recommended work packages and stop conditions

### M0 — immediate operational and branch hygiene (highest priority; small)

**Owner:** repo/engineering management; no authoring-system rewrite.

Inputs: open PR ledger, relevant historical base/commit, CI jobs, issue comments. Deliver a single state reconciliation and at most one distinct fix per PR. Start with PR #370, whose isolated parser regressions passed but full CI was still running as this plan was written. The required final artifact is the exact tested SHA, changed-file list, test totals/skips, validator result, DB/output SHA/parity evidence, and whether a review/merge has actually occurred. Do not close #333 until the fix has merged and issue resolution is verified.

Also retire only genuinely superseded PRs whose unique content, source-use, human-review queues, and dependencies have been accounted for. Do not merge or close #133, #325, #324, #327 or #347 simply to reduce PR counts. Archive/close actions must cite replacement and retained unique artifacts. No Git history rewrite.

**Stop condition:** a complete authoritative status memo exists; blockers are isolated. No additional maintenance issue or framework unless a real defect emerges.

### M1 — First-Sunday evidence and human handoff (time-sensitive, separate from permanent automation)

**Owner:** Briefs editorial + Sunday pipeline. Relevant: #353, #355, #366; merged #365/#368. Do not conflate authoring with delivery.

1. Freeze source-eligible weekly evidence using the actual reporting-window and collection-success receipts; distinguish production screened/unscreened, research-only typed source, shadow source and human-approved citation rights.
2. Inspect the exact top-ten/default source selection and omission notes. The pivotal Singapore record 4911 and Chinese record 4937 in #355 must not be claimed available to a model merely because they are stored. If the selected slate cannot support the proposed two-institution argument, abstain from that theme or use only the existing separately owner-signed thematic rehearsal pathway. No silent MAX_RECORDS change.
3. Enforce original-language factual direction on record 5039 (#353): October 10 announcement of an October 13 China–Laos exchange is **not** a completed October 13 event. This is a source-to-machine-summary correction concern, not an excuse to edit preserved original text or invent future completion.
4. Separate (a) frozen model draft, (b) readable prose rendering for Dylan, (c) source and fact-check receipt, (d) exact owner-reviewed SHA, (e) transport/replay receipt. Only (b) should be the editor's primary writing experience; other artifacts support QA without making Dylan administer a machine proof packet.
5. If no safe owner-reviewed exact attachment exists, **no editor send**. Manual #368 replay is opt-in, locally approved and no-model; do not turn on scheduled send as a workaround.

**Future M1b, not a first-Sunday emergency patch:** durable private reviewed-file store plus idempotent transport/send-attempt journal, no second model after author approval, interruption/lost-ack synthetic tests and manual recovery. Keep this as one coherent post-pilot engineering objective under #366, not an additional parallel writer.

**Stop condition:** source-checked private editorial candidate or documented abstention; an editor delivery requires a separately recorded matching content digest and explicit send approval. No automatic publication follows.

### M2 — Finish and verify the existing C2 fictional custody chain (no production activation)

**Owner:** custody engineer/independent reviewer under #342. Start by reading **actual current PR bases**; stacked branches may be both feature-based and main-based. C1 #356 and C2-A #359 were reported merged, while #360–#367 are still open and not equivalent to a final integrated test. Reconcile one PR at a time. Do not merge stacked descendants out of order just because CI is green against their feature parents.

The minimum closure proof for the cohesive C2 phase is:

- One native execution/run mapping and sealed **collected** generation; immutable expected-source manifest, source outcomes, and publisher-version identity without invented success.
- Valid paid-analysis intent **before** fictional charge, per-task admission fence under cooperating workers, monotonic revisions and idempotency under interrupted/lost acknowledgements.
- All unknown-charge states explicitly accounted for. A token estimate, a reservation and an actual measured call receipt are different states; no unsupported “$0” or “paid successfully” inferred.
- Deterministic restore across new processes; CAS contention/refusal, stale pointer, edited source, missing body, partial collection, duplicate intent, lost receipt, old task and new worker all fail closed.
- No use of production DB, public Git source bodies, Anthropic, real secure store, schedule, editorial mail, deployed output or source collection in the test harness.
- Python 3.9-focused and exact-head full suite; DB/output preservation; no hidden provider calls, fabricated approval or changing defaults.

**Stop condition:** independent evidence-review packet plus serialized PR integration or isolated blockers; **private runtime remains disabled**. A later provider-selection/secret-management/cutover phase must be fresh work, not folded into the same agent session.

### M3 — Release engineering, proof of final artifacts and disaster recovery

**Owner:** release/cutover engineer. This begins with offline code/tests, *not* changing active Pages deployment. Issues #351, #343 and #346 define the coupled acceptance surface.

The target transaction has five logical phases:

    read immutable approved inputs
      -> construct complete candidate public tree away from output/
      -> source-use/public-leak and content-parity check of final candidate
      -> immutable generation digest + approved deployment fence
      -> one safe publish action + verified postpublish identity

The complete candidate must include **carried-forward historical pages/data/assets**, redirects, feed, index, JS/CSS, sitemap, Briefs, Timeline eligibility and legacy routes. A green test of a partial staged tree is insufficient.

Synthetic release QA must include:
- failure at **every** destructive filesystem/rename/carry-forward transition; retry must preserve both previous valid output and sole recoverable carried files (#351);
- preserved immutable record URLs, original citation references and site text after authorized rendering;
- body/metadata/link/quotation/image exposure **separately** scoped by approved source-use policy; all public outputs and exports scanned, no raw protected body in static/JSON/search/feeds/logs;
- two concurrently eligible Pages publishers: older manual checkout A must not overwrite newer Daily B (#346); an *intentional* rollback needs a fresh approved receipt;
- failure **after** gh-pages write but **before** success marker, plus crash during network/transient delivery;
- exact generated-source, policy, output and deployed-generation digests, verified against the actual published revision;
- failure-salvage commits and normal success commits protected equally (no bypass of private custody or final public projection).

**Stop condition:** evidence from complete synthetic integration and independently reviewed rollback runbook. No new live store, public DB removal, secrets, deployment, rewrite or production switch without a separate owner-approved release phase.

### M4 — Integrate research and design surfaces only after trust gates

**Owner:** dedicated workstream per family, not omnibus website PR.

- **Frontend:** Phase 0 rulings in merged #371 are authoritative for proposed Phase 1 shared design infrastructure, not a blanket acceptance of 45 study screenshots. Honor media classifications, rights restrictions and existing generated output rules. Review against current main, not stale #314/#323 CI.
- **Timelines:** keep #181's private Maritime Cooperation content unpublished pending source/edition-specific signoff. Integrate versioned sidecar validator/UI only after base/PR conflicts resolved and own noindex/no-public-output tests.
- **Living Dossiers:** #347's private B1/B2.2 stack is a different code path than the public B2 format. Do not infer readiness from the fictional HTML preview or from the B0 Singapore source list. Existing #319/#321/#322 rights, human original review and digest approvals must precede a public route.
- **Brief editorial quality:** PR #325 is a one-file C1 audit that may inform editing without imposing additional forms or workflows on Dylan. Focus on strongest source-to-claim checks and documented abstention rather than expanding word count or approval bureaucracy.
- **Regional topic labels:** v2 vocabulary may exist, but unratified pilot labels and #133's remaining owner queue are not approved public classifications.
- **Country desks:** inherit #373's exact per-family wave plan; the mere presence of Vietnam MOD robots-first observation or Korea HWPX proof does not imply new source admission, full-body rights or desk promotion.

**Stop condition:** one reviewed component and its preservation evidence per PR; no format becomes public due to adjacent PR merge.

## 4. Git branch, CI, ownership and change protocol

1. **One phase / one code owner / one branch.** Name branch for the actual objective, never “finish IPR” or “all cleanup.” Adjacent phases use new coding sessions after the commit/PR/verification boundary.
2. **Read main and its file ledger at session start.** Explicitly write baseline SHA, actual target PR head/base, already merged dependencies and potentially concurrent paths. No speculative branch transplants or merging a PR built against a feature parent as though it landed on main.
3. **Path-level exclusive ownership:** custody owns storage/evidence_*, source/run identity/DAO interfaces; Sunday owns scripts/sunday_* and its mail workflow; release owns site/render.py, scripts/validate_output.py and deployment/workflow exchange; frontend owns isolated CSS/assets/macros; desks own source-family shadow code/manifests. Cross-lane shared-file edits pause until owner coordination.
4. **Change contract for every PR:** intent, protected invariants, exact changed paths, no-go mutations, causal defect/requirement, evidence/negative tests, full workflow run IDs (including skips), source/rights assumption disclosures, rollback, owner gate and explicit stop criterion.
5. **Test ladder:** local syntax/focused unit; realistic synthetic negative control; exact-head Python 3.9 offline/Chromium if path relevant; full rendered-output validation; hashed DB/output and SQLite WAL/SHM preservation; actual path-specific release receipt when required. “CI skipped due to path filter” is **skipped**, not passed. Baseline warning deltas should be explained, not frozen as a magic ten forever.
6. **Publication safety:** no direct edits to generated output except through existing deliberate guarded publication/build steps; no preview into output; no auto-activation via commit, no unsigned reviewer decisions; source originals never pasted into issue comments or logs.
7. **Spend safety:** no raising DAILY_ANALYSIS_CAP, provider/model swap, automatic reruns, real LLM analysis, replay send or cloud purchase within an infrastructure cleanup PR.
8. **Human decisions:** separately identify editorial source truth, source-use permissions (links, metadata, quotations, body display, photos, private retention), public-release identity and financial authorization. No synthetic “approval” JSON substitutes for any human decision.
9. **Fail and stop:** unexpected main drift, missing source digest, incomplete CI, rights ambiguity, unreviewed 81.cn image, undeployed or mismatched published tree, conflicting writers, or missing transport receipt are blockers. Document and stop; do not route around them.

## 5. Minimal evidence receipt each reviewer should require

A reviewer-friendly completion packet should contain:

| Field | Required content |
| --- | --- |
| Identity | Issue, branch, immutable head, base and merge target, exact changed paths |
| Claims | One-sentence change and directly observed behavior, separated from hypothetical benefit |
| Dependency check | Merged upstream exact commits and unresolved human gates |
| Tests | Focused case count and failure cases; actual full CI run/job conclusion; skipped paths; validation warning delta |
| Preservation | Archive and output digests before/after, sidecar residue, source/citation/route invariants |
| Actions | Explicit list: no real scrape, no provider charge, no SMTP, no access/policy change, no public deploy—unless separately approved and proven |
| Recovery | Fault-injection or rollback proof appropriate to the changed boundary |
| Decision | ACCEPT FOR REVIEW, HOLD, or REJECT with blocker; **never auto-merge** from a machine score |

Do not produce dozens of redundant narrative packets for routine editorial edits. For Dylan, the primary artifact should remain clean prose with links; evidence/receipts belong to the owner and QA operators.

## 6. Capacity and sequencing rule

Until the trust boundaries settle, limit simultaneous implementation to **one active release/custody code integration and one disjoint editorial or source-specific work package**. Read-only review and design exploration can continue independently. If two PRs touch the same underlying renderer, workflow, SQLite lineage, citation model or source-use gate, serialize them even if their filenames differ.

Recommended order of *engineering acceptance* is M0 hygiene, M1 human Sunday handoff, M2 fictional C2 integration, M3 offline release/cutover safety, and only then M4 public integration where its independent approvals exist. These are dependency priorities, **not promised calendar dates**. Desk checkpoints are governed by real October 14/21 and November 6 observations, not artificial advancement of maturity clocks.

## 7. Session handoffs / exact future agent tasks

Keep engineering continuity in branches, commits, issues, PRs and test logs. At a clean boundary, a new coding agent starts from repository truth. Use a narrow charter:

**Session A — audit closure:** Inspect #370 exact head and latest full CI job steps; verify change scope and actual per-test results; correct only a directly blocking fault. Stop at verified PR and review decision; do not touch renderer, rights or C2.

**Session B — Sunday reviewed-artifact transport:** Under #366, design one durable review-file intake and idempotent no-second-model send, with false-send and lost-ack tests. No editorial rewriting, new sources, provider costs or scheduled enabling. Stop at disabled, test-proven PR.

**Session C — C2 reviewed integration:** Under #342, reconcile stack #360–#367 sequentially against actual main; demand native lineage, immutable source set, paid-intent replay correctness and fail-closed unknown-charge recovery. No real provider calls, new private service, C3/Pages or activation. Stop after integration and independent acceptance evidence.

**Session D — release recovery and cross-writer fencing:** Under #351/#343/#346, implement synthetic fully assembled output transaction and shared release-identity / stale-deploy refusal tests. No deployment or storage migration. Stop at isolated offline release contract, independent review and documented remaining owner choices.

**Session E — separate design/country issue:** Continue actual #371 Phase 1 implementation *or* #373 desk source-family work in its existing dedicated branch, never both within one session. Do not duplicate the desk program DAG.

## 8. Deferred decisions that cannot be answered by code

- Which publisher actions are licensed, exempt, prohibited or require permission (#326), with actual reviewer and dated evidence; no admission of infringement is implied.
- Which private provider, account credentials, secrets policy, backup/retention and operating budget the owner is prepared to authorize (#332/#342).
- Whether and when existing published source text, historical Git data or public record routes are altered. Historical Git and caches cannot be assumed erasable.
- Which exact manuscript and source list to send to Dylan, and when an editor's text is publishable (#355/#366).
- Whether to approve public Timelines, Dossiers, or a frontend release, based on their own versioned source/visual gates.
- Whether to increase model spend or prioritize screening backlogs based on a **fresh executed** Daily run (#268).

## 9. Definition of completion

This framework is delivered when it is reviewable as a **documentation-only PR** with an exact main base and no changed production assets. It is not itself a release. Engineering program success will mean: one trustworthy source-identity system, repeatable editorial handoff, deterministic and recoverable publishable output, explicit source-use decisions, safely fenced deployment, and honest country/source status—all supported by specific receipts, not by the number of PRs opened.

**Non-goals:** new country declarations, new collectors, new analysis service, new research format, new cost center, generic workflow platform, automatic editor approvals, public source migration, frontend redesign implementation, production release or deployment.
