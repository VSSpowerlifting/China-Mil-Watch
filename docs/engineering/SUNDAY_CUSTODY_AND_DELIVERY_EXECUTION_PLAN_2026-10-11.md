# IPR Sunday custody and reviewed-delivery integration — execution plan

**Prepared:** 2026-10-11, America/New_York.
**Program authority:** issue #366; companion to docs/engineering/IPR_CONVERGENCE_AND_RELEASE_GATES_2026-10-10.md in planning PR #375.
**Status:** engineering planning only. Not a sender implementation, human approval, source-rights determination, merge instruction, budget authorization, schedule or production activation.
**Implementation companion:** `SUNDAY_C1_TO_C4_INTERFACE_AND_ACCEPTANCE_2026-10-11.md` specifies the current C1 closeout, narrow C2 owner-release verifier, pure C3 byte-preserving MIME interface, disabled C4 adapter and concrete negative-test/stop gates. It refines this plan rather than creating another program; the companion's dated PR/CI references must be refreshed before work.
**Core invariant:** The specific private TXT the owner reviewed is the only attachment that could eventually be delivered to Dylan. Review, source-use permission, artifact custody, delivery identity and sender authorization are distinct decisions; no newly generated manuscript may inherit approval from earlier bytes.

## A. Verified starting state and exact dependency graph

Use GitHub refs and run IDs, not this dated snapshot, to verify heads again before any code integration.

| Object | Observed head or evidence | Contract / disposition |
| --- | --- | --- |
| Existing first-pilot reader | scripts/sunday_first_pilot_reviewed_replay.py on main | October 10-only manual operator fallback: full worksheet, owner week, exact SHA and explicit local send opt-in. It can call real SMTP when authorized; it is not idempotent. Do not modify in a planning PR. |
| Existing readable mail view | scripts/sunday_editor_readable.py on main; PR #365 merged | Derives Dylan-facing prose from the same reviewed TXT. Do not ask a model for another draft. |
| Existing mail path | scripts/sunday_editorial_handoff.py; .github/workflows/sunday_briefs_editorial_handoff.yml | Scheduled writer may generate a fresh draft, not reuse the owner's previous exact attachment. Do not enable automated editor delivery as a shortcut. |
| #377: fictional send journal | head 6ebdfabee05ebc564df7420c89a7a9e42d68f1f0 | Standalone SQLite metadata-only, no sender. CI #38114030442 SUCCESS: 5,714 tests, nine skips, 10 governed output warnings, DB/output preserved. Open/unmerged. |
| #382: disabled replay rehearsal | head a49a584a971cef5afdf271c5594272498026a598, based on #377 | Sixteen fictional replay tests; true incremental PR scope three additions-only files. Exact-head CI #38146369254 SUCCESS: 5,730 tests, nine skips, 10 warnings, DB/output preserved. Open/unmerged. |
| #385: private snapshot helper | head 8334cebb22b491df0260a7c926500f0819c1db4a | Separate three-file main-based PR; snapshot outside public Git, bounded file read and no-overwrite 0400 file. Exact-head CI #38146986228 was IN PROGRESS when checked. Open/unmerged. |
| #307: mixed-regional theme approval | open branch-based research PR | Signed *theme selection* does not grant SMTP permission or owner review of a specific full manuscript. Avoid conflating or silently coupling its signatures to an exact-file send. |
| #355 and #353 | human editorial/source issues | Unscreened source-ranking and event-timing errors still require original-record checking; no hash proves fact checking. |
| #326 | source rights decision | Links, original bodies, private retention, quotations, translations and images have different permissions. No engineering receipt is itself legal/owner approval. |
| #375 | this overall planning PR | Phase and ownership map; companion here must not spawn a second universal IPR engineering program. |

Dependency DAG (implementation qualification, not calendar prediction):

  independent source-rights / editorial fact review
                     |
             owner decision on private storage
                     |
         (#377 verified journal)        (#385 verified private snapshot)
                     |                              |
         (#382 fictional replay)                     |
                     +--------------+---------------+
                                    |
                  C1: isolated custody-binding contract
                                    |
                  C2: actual owner approval identity contract
                                    |
                  C3: deterministic message builder, disabled transport
                                    |
                  C4: fictional transport fault and recovery integration
                                    |
                  C5: private operator acceptance and explicit no-send release
                                    |
                  C6: separately authorized limited real pilot, if ever approved

Do not interpret arrows as authority to merge PRs, send mail or create accounts. Parent #377 must be independently reviewed before #382 is retargeted and merged; #385 is disjoint and can receive its own review.

## B. State model and data ownership

Do not build a generic workflow engine. Define *one* private editorial artifact and *one* delivery identity.

### Inputs requiring distinct attestation

| Identity | Canonical representation | Verified by | What it does NOT prove |
| --- | --- | --- | --- |
| Original reviewed bytes | exact UTF-8 TXT, raw SHA-256, byte length, reporting Saturday, canonical packet boundary | Existing inspect_file plus bounded private snapshot (#385) | Actual owner reviewed it, human semantic approval, license |
| Source-use evidence | exact source-use subsection SHA, typed record/source IDs, original URL pointers, independent human source-verdict receipt | Human editor/source reviewer and a future verifier | All claims true solely because a model described citations |
| Owner manuscript approval | approval version, date, editor recipient, exact document hash, source-review reference, purpose and revocation state | Separate explicit owner action with authenticator/recorded durable receipt | Consent to real SMTP unless it says so |
| Delivery permission | explicit, non-expired send decision bound to artifact SHA, recipient, week, channel and allowed attempt count | Owner-controlled operator gate, independently recorded | Actual delivery or authorization of public publication |
| Journal history | one reserved attempt maximum for (week, protected recipient identity), terminal outcomes and non-resettable uncertainty | #377 SQLite unique constraint + separately protected rollback checkpoint | Exactly-once SMTP, remote receipt, immutable database |
| Private custody | no-overwrite canonical TXT in a restricted location outside Git plus protected backups and retention policy | #385-style snapshot + external storage controls | Legal permission, cryptographic immutability |

**Privacy:** raw SHA-256(email) is guessable by dictionary. Do not put personal recipient hashes in public CI, documents or logs. Before any real persisted journal, adopt keyed HMAC or a private random recipient ID with owner-controlled key management; schema change and rotation must be explicit and tested. The current #377 pseudo-identity is fictional and must not be quietly promoted.

**Resend policy:** changed prose, modified citations, newly signed digest, alternate model output or another editor identity must not silently reset an attempted delivery for the same week/recipient. An operator-driven resend or correction must be documented separately, with evidence that the prior state was reconciled and actual new owner permission; never reuse stale journal approval.

### Minimal proposed private records (NOT a ready schema)

- artifact_identity: editorial_week, immutable_bytes_sha256, original_length, private_object_id, source_use_receipt_sha256, artifact_validation_version.
- owner_review: owner_decision_id, exact_artifact_sha256, human_review_reference, original_language_source_status, rights_status_reference, recipient_id, approval_time, expiry, explicit revocation, review_scope.
- delivery_intent: week, artifact_sha256, recipient_id, channel, approval_id, journal_identity, required preflight version, reserved_at, status and reconciling operator.
- transport_attestation: attempted_at, SMTP server acceptance *only when observed*, blinded receipt reference, ambiguous outcome, transport account identity, explicit no-retry flag.
- checkpoint: protected journal generation/hash and last verified restoration proof, external to the mutable local SQLite file.

This is the smallest plausible contract. Do NOT create these tables or store private originals as a consequence of adding this planning document.

## C. Phased implementation work packages and stop gates

Each numbered work package should be one engineering PR with an independent contract test. Prefer existing modules; never duplicate the core journal/snapshot implementation.

### C0 — Review, evidence receipts and convergence hygiene

**Scope:** no new runtime code. Refresh the exact heads, CI job logs, warnings, and branch bases of #377, #382 and #385. Review the parent-child correctness and rights/editorial blockers.

Required:
- Confirm all expected focused tests really executed, not merely a successful job wrapper or path skip.
- Confirm #377 one-week/recipient unique index and legacy-schema rejection actually run; verify no public artifacts or source text in test logs.
- Confirm #382 is three files on top of #377 and its latest head is validated; only retarget after an owner-approved #377 merge.
- Confirm #385 stores only approved-format Oct 10 TXT and refuses Git worktree paths; separately scrutinize TOCTOU/atomic file opening, symlinked ancestors, filesystem crash recovery and 0400 metadata durability.
- Decide whether #377, #382 and #385 require code changes before any approved merge; no automatic cascading merges or issue closure.

**Acceptance:** exact-head status ledger with tests/job IDs, focused negatives, unchanged DB/output and unresolved findings. **STOP** for any failed or incomplete CI or uncertain branch ancestry.

### C1 — Offline custody-binding integration (new isolated PR; default disabled)

**Input:** a fictional exact-reviewed test fixture, a fictional approved digest, a temporary 0700 private directory and the independently reviewed journal. **No production data.**

Proposed pure boundary:
1. Freeze via a descriptor-based snapshot with expected SHA and full original worksheet validation.
2. Validate the frozen copy *again* and compare raw bytes/hash to the exact approval candidate and source-use receipt.
3. Bind the frozen canonical file identity, approval placeholder and recipient identity to the correct journal record.
4. Return a machine-readable **preflight-only verdict** without reserving or sending; no real SMTP or call to a new LLM.
5. Refuse if the frozen copy has changed, disappeared, been replaced, has wrong recipient/week, or any source-use checksum differs.

Test mutation **between every step**, including rename/unlink, same-length byte rewrite, symlink swap, stale SHA, wrong weekend, unknown/canceled approval, missing source receipt, concurrent freezer and journal worker, and no-write failure paths.

**Acceptance:** separately bounded pure/isolated API, test-only inputs, no provider/network/model/sender import, no new scheduled cron, no public artifact. **STOP:** a verified file path must never be treated as equivalent to a pinned/open descriptor if content can be swapped later. Prefer original bytes or descriptor with rechecked identity to re-reading the caller's mutable path.

### C2 — Authenticated human approval receipt (new isolated offline PR)

Use the existing repo's scoped canonicalization/HMAC patterns only after confirming their actual authority and format. **PR #307 signs a thematic focus, NOT a Sunday send.** Do not import its authorization scope by name alone.

Proposed review decision must state:
- Exact week and manuscript digest/length.
- Recipient(s) and delivery purpose (editing only, not publication).
- Human source checking record and rights/retention reference, with unavailable/negative decisions surfaced.
- Expiry/revocation, key identity and operator who performed the action.
- Independent explicit affirmative owner action; signature/checksum verification occurs before mail composition or reservation.
- Required handling of stale approvals after source corrections, revocation or changed recipient.

Threat tests: fake "approval" hash supplied by code, unsigned or wrong-scope signature, replay of #307 theme token, self-signed review by sender process, changed source-use receipt, key rotation/revocation, time-skew or expired consent, wrong editor, accidental multi-recipient addresses, unsafe logs.

**Acceptance:** non-sending signer/verifier contract and deterministic fixture receipts; real signing keys must not be created or added to Git. **STOP:** a true approval channel, key custody and source-rights policies remain unresolved owner decisions.

### C3 — Deterministic MIME builder separated from live SMTP (new isolated PR)

The current send_packet(path, week_ending) reopens a path internally and conditionally contacts real SMTP. A future adapter must avoid treating a prior path-only hash check as proof the bytes actually attached.

Create a **pure builder** for one canonical byte buffer or verified read-only file descriptor:
- Plain-text and HTML article body are mechanically derived from the same reviewed manuscript with scripts/sunday_editor_readable.py; exact original TXT is attached with unchanged bytes.
- No second LLM, mutation, newly fetched record, changed citations, extra dossier/historical appendix in body, new numbering or publication.
- Single authorized recipient; reject owner preview mixing, duplicate To/Cc/Bcc, multiline header injection, MIME mismatch, corrupt UTF-8 or hidden external-resource HTML.
- Same frozen SHA must match the actual MIME attachment payload and the approval receipt. SMTP credentials and side effects belong **outside** this function.
- Define deterministic content semantics (not necessarily byte-identical MIME boundary formatting) and an auditable message ID policy if transport supports it.

**Acceptance:** offline MIME fixture inspection with exact payload SHA; all legacy readable-email tests retain behavior. **STOP:** no real mail transport or scheduled writer integration in this PR.

### C4 — Disabled sender adapter and fault recovery (separate gated PR)

Only after C1–C3 decisions and PR integration are independently accepted:
- Preflight authentication, current unrevoked approval, source/rights status, recipient identity, journal integrity and private artifact bytes **before** reserving a send.
- Durable reservation/compare-and-swap must precede the first contact with a transport. A crash immediately afterward stays in an ambiguous/manual state.
- Adapter must route an injected fake transport in tests; production implementation/default remains explicitly **off**.
- Observe SMTP server acceptance as a narrow state: NOT final recipient delivery, acceptance by a mailbox provider, or proof that Dylan read it.
- A failure after contacting SMTP, lost ACK, process kill, timeout, network retry or reboot is UNKNOWN/HOLD. No automatic resend, even if the call might not have sent anything.
- A database lost, restored or rolled back to an older valid schema requires external journal-checkpoint comparison. Never initialize a replacement and proceed as though the first send never happened.
- Keep private corpus/source text out of traces, Actions, error logs and PR review artifacts; redact/harden any provider error.

**Acceptance fault matrix:** dry-run, disapproved hash, unverified source, unavailable journal, stale checkpoint, duplicate worker, same-week revised draft, cross-recipient drift, pre-reservation error, crash after reservation, fake accepted then lost-ack, wrong mail body, SMTP rejects, ambiguous remote timeout, missing Sent evidence, protected backup restore. **STOP:** no real transport invocation and no automatic conditional watch/cron activation.

### C5 — Operational qualification with no external mail

Owner must choose a genuine durable storage/backup/retention location and an actual identity/signing approach. Stage only synthetic or suitably authorized private rehearsal data.

Prove:
- A real durable **private** artifact can be recovered exactly after restart without crossing into Git, output/, public Actions artifacts, email-body logs or an insecure temporary runner.
- Journal survives process crash; an older backup cannot silently manufacture a new send allowance.
- Operator can distinguish no-attempt, reserved, accepted, ambiguous and deliberately held, and has a manual incident playbook to check Sent records before approving any reconciliation.
- One-manuscript/one-recipient/final attachment identity holds through the actual composer boundary, even when the sender process restarts or the editor address changes.
- Source-original review and permission decisions are linked to the correct versioned manuscript, and the owner can revoke before transport.

**Acceptance:** independent tester signs a synthetic operational drill receipt; negative-case CI plus no live provider call. **STOP:** storage rights, credentials, backups, mailbox reconciliation, support operator and owner acceptance must be explicit, not inferred from CI.

### C6 — Separate owner-controlled real pilot (NOT part of this plan)

Only propose once all prior gates are accepted. The owner must separately authorize the **exact** manuscript, recipient, reporting week, explicit run window, delivery account, costs, source-use, private retention, and rollback/recovery protocol.

Do NOT silently migrate the scheduled Sunday writer, move a feature flag to true, trigger real SMTP, broaden from October 10 to future weeks, or commit a new public Brief. One real manual send, if approved, is a separate operator action, not proof that scheduled recurring delivery is safe. Schedule activation and automated owner/editor notifications would require their own later review.

## D. Hard ownership boundaries and integration sequence

| Scope owner | Files currently owned / examples | Do not overlap with |
| --- | --- | --- |
| Journal owner | core/sunday_delivery_journal.py and tests; PR #377 | Snapshot private filesystem work, SMTP, another local database schema |
| Replay harness owner | core/sunday_delivery_replay_rehearsal.py and tests; PR #382 based on #377 | Parent journal edits, real sender, workflows |
| Snapshot owner | core/sunday_private_reviewed_snapshot.py and tests; PR #385 | Workflow, journal, public DB/output and source records |
| Editorial/source reviewer | First-Sunday exact manuscript, original-language citations, publisher reuse decision #326, #355/#353 | Engineering mock approval or unsigned source report |
| Integration engineer (future) | New small C1 module/tests, after parents accepted | No copy-paste reimplementation of journal, snapshot or existing prose renderer |
| Mail adapter engineer (future) | Pure C3 builder, subsequently separate C4 adapter | No preview writer/model generation, no public publication or schedule |
| Release/operations reviewer | protected external journal checkpoint, owner runbook, negative drills | #343/#346 separate public Pages release engineering |

**Preferred approval order:** independently review/accept #377 -> retarget/review #382 against merged exact parent -> independently review/accept #385 -> C1 -> C2 -> C3 -> C4 -> C5 -> separately requested C6. C1 may be drafted in a disabled review branch while C2 owner decisions are pending, but **must not** bypass C2 or drift into live integration.

If #385 cannot satisfy a safe frozen artifact contract, HOLD; do not weaken #377 journal safety to compensate. If #382's parent base changes, compare exact 3-file delta against that parent and revalidate on the final merge head. Merge order and actual main commits must be recorded, not guessed.

## E. Required verification evidence for every engineering PR

- Single objective, named issue/parent, base and immutable head, exact path diff and no-go boundaries.
- Unit test command and tested source blob; edge-case result including injected adversarial errors.
- Python 3.9 exact-head full offline run and job log, actual counts and nine or other *measured* skips; path-filtered/skipped is not a pass.
- Rendered-output validator and warning delta; archived DB and output hash preservation; WAL/SHM residue check.
- No external email/model/scrape/paid provider or real production storage actions, evidenced by isolated mocks/import scan rather than merely claimed.
- Source-rights and original-language factual approvals explicitly marked unresolved when not completed.
- What would break in a crash, how to detect and reconcile, and what concrete human decision remains.
- Reviewer disposition: ACCEPT FOR REVIEW, HOLD, or REJECT; do not auto-merge or imply scheduled delivery has been enabled.

## F. Token-efficient agent execution

Use the already connected GitHub and available repository/test tools as the source of truth. Do not repeatedly paste 5,000-test logs or 250-line docs into every model context; pass exact ref, changed paths, failing lines, relevant log summaries and a short acceptance ledger.

- **Fast/lightweight model:** inventory Git refs, file ownership, diff-only summary, fixture variations, docs cross-links, baseline checks, updating test matrix and PR status (read-only or on a dedicated task branch).
- **High-reasoning model:** approval-boundary threat modeling, atomic file/journal and rollback analysis, security code review, design of races/failure recovery, any proposal involving real SMTP/secrets/rights.
- **Coding agent:** one small objective at a time; read the linked specs and current Git head first, write tests before implementation for risky boundaries, stop at a scoped PR and CI receipt.
- **Independent reviewer:** examine actual diff/test output and original source/permission decisions. The implementing agent cannot grant editorial, legal or release approval by marking tests green.

Avoid speculative plugin proliferation or unrelated services. Inspect available connectors/skills when a *specific* authorized task needs them; no actual email, private source import, cloud provisioning or automation is justified by this plan. Do not swap to a more expensive model, raise any analysis cap or repeatedly execute paid LLM drafting for integration testing.

## G. Hand-off prompts (one objective per session)

**Agent S1 / PR reconciliation:** "Review current main and PRs #377/#382/#385 under #366. Confirm head/base, tested exact-head artifacts, skipped checks, modified file paths and actual remaining issues. Run no model, SMTP, publisher fetch, merge or deployment. Report an evidence-only ACCEPT/HOLD table."

**Agent S2 / private custody C1:** "Implement only a disabled offline integration binding the existing #385 exact-reviewed snapshot, #377 week-recipient journal, and #382 fictional replay, using mock owner approvals and private temporary test files. Pin actual source checksum; fail closed on source path mutation, wrong week, altered bytes, missing receipt, dead journal, multi-worker contention and repo-path leakage. Do not implement authorization or SMTP. Deliver one small PR with negative tests."

**Agent S3 / owner receipt C2:** "Design and test a separate, versioned genuine owner-review and rights-receipt verifier for a specific manuscript week/SHA/recipient. Compare but do not reuse thematic focus approval PR #307 as delivery authority. All fixture signing offline; real keys and owner decision remain external. Stop at disabled validation code, tests and explicit unresolved choices."

**Agent S4 / MIME C3:** "Refactor a purely deterministic MIME builder using reviewed original bytes, the existing Sunday editorial prose renderer and attachment SHA assertions. No SMTP connection, credentials, LLM or schedule; retain the exact source-rich TXT only as attachment. Test header injection, recipient drift, payload SHA, mutable path races and source appendix leakage into body. Stop at independent PR."

**Agent S5 / transport C4:** "After reviewed C1–C3 are integrated, build only a disabled transport adapter with a fault-injected mock channel and #377-style pre-SMTP durable reservation, including unknown-outcome manual hold. Do not send real mail, open a provider account or activate workflow. Test accept-then-ack-lost, crash, stale journal restore and duplicate workers; stop for owner review."

## H. Stop conditions and definition of completion

Immediate HOLD if any of these is true: source-use or rights uncertain for intended real text; owner signature or approved recipient unresolved; a private original enters public Git/output/Actions/logs; preflight may reread a mutable file without verification; a revised draft obtains a second same-week send; SQLite rollback can silently erase a reservation; unknown SMTP outcome triggers automatic retry; transport can be activated by default; a green CI job skipped its relevant tests; merge parent changes unreviewed.

This plan is **complete as a planning artifact** when it is committed only to PR #375 with a current-state CI/evidence snapshot and no runtime edits. The actual engineering program is not complete until each scoped PR's code, failure tests, private storage, source-rights decisions, human review, transport qualification and any *separately requested* real-send authorization have their own receipts.

No time estimate or promise of future delivery is implied. Ownership, source truth, and production permission remain with the user.
