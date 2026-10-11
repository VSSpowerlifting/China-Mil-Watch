# Sunday C1–C4 interface and acceptance contract
**IPR / Issue #366 · 2026-10-11 · Planning-only · Not approved for production**

**Governing context:** `SUNDAY_CUSTODY_AND_DELIVERY_EXECUTION_PLAN_2026-10-11.md` (C0–C6), master convergence plan in PR #375. This companion translates only the next implementation seams into reviewable software contracts. It does **not** supersede the governing docs, resolve source rights (#326), grant owner approval, create a new sender, or authorize merging PRs.

## 1. Engineering ruling: small editorial product, not a new workflow engine

The user-facing objective remains simple: **one source-linked Sunday manuscript for the owner to review, and—only if approved—one readable article-first email for Dylan's prose edits, with the exact source-rich TXT attached**. Dylan should not be asked to complete fact-check ledgers, dossiers or elaborate packets as a routine weekly task. Internal source checking and owner decisions remain private. A source-receipt checksum is not a human fact-check or grant of source-use rights.

Only one model-generation event should be needed for an approved draft. **Preview approval never authorizes regeneration.** Deterministic email formatting must consume the *same original bytes*. A week can be held without generating or sending anything; do not force publication cadence or invent a contributing desk.

**Avoid:** a new scheduler, generic job engine, second database, redundant evidence format, new account/provider, direct recurring SMTP wiring, additional country desks, public-site output, expensive model calls for tests, or duplicated `#377/#382/#385/#387` code.

## 2. Verified architecture boundary (at this writing)

| Piece | Reality | Required next action |
| --- | --- | --- |
| Main replay & email | `scripts/sunday_first_pilot_reviewed_replay.py` and `scripts/sunday_editorial_handoff.py::send_packet` already exist; manual replay can email, but reopens path and offers no cross-worker durable send fence | **Do not** reuse `send_packet` as the future C3 pure renderer; keep live sender unchanged |
| Readable email | `scripts/sunday_editor_readable.py` produces article-first text/HTML; full provenance in original TXT attachment only | Reuse these functions, not a second prose extraction implementation |
| #377 | Head `6ebdfabee05ebc564df7420c89a7a9e42d68f1f0`; independent full Python CI success, 5,714 tests / nine skips; no live integration | Code/owner review; preserve one-week/recipient collision and ambiguous-attempt hold |
| #382 | Head `a49a584a971cef5afdf271c5594272498026a598`; full CI success, 5,730 tests / nine skips; child of #377 | Preserve fictional-only replay and fail-closed journal states |
| #385 | Head `70e34c0c4655eda0e48e5aa77b4ba11b2ae86e4f`; previous head passed but **latest-head CI #38151970378 was still running at review**; standalone private snapshot with lexical/resolved Git exclusion | Verify the *new* exact head's tests (15 authored), validator and tracked-DB/output preservation |
| #387 | Head `907f21122f41cd900166603e5d3419e06150cd58`; **draft, no executed exact-head CI**; 24 authored C1 tests; child of #382 with three copied #385 files | Owner-authorized ordinary CI/review; don't relabel static test count as a pass |

All four implementation PRs remain **unmerged** as observed. These hashes are an inventory, not evergreen truth; refresh GitHub before implementation or merger. Previous green heads do not certify changed heads. The #387 draft/checks restriction must not be bypassed by altering workflow permissions or misreporting a skipped job.

## 3. Architecture / explicit ports

```text
SATURDAY EVIDENCE + MANUSCRIPT GENERATION (existing, owner-only, once)
      |
      v
C1  validate original bytes -> private frozen copy -> compare digest/receipt
      |             └-> fictional-only metadata journal registration during tests
      v
C2  verify explicit human decision on THIS week + byte SHA + sources + recipient
      |             └-> separate revocation/expiry and rights status; no mail side effect
      v
C3  pure MIME builder(exact verified bytes, approval, recipient)
      |             └-> prose-only text/HTML + EXACT source-rich TXT attachment
      v
C4  disabled adapter: reverify -> atomic pre-contact reservation -> fake transport
      |                                                └-> unknown = MANUAL HOLD
      v
C5  owner-chosen private custody and recovery drill (no external email)
      |
      v
C6  separately authorized one-off real pilot (NOT part of this contract)
```

The **port boundary is bytes, not mutable paths**. Store an immutable in-memory byte buffer or a pinned descriptor plus identity checks for the duration of C2/C3 preparation. A previously checked pathname alone is never evidence that the bytes used in MIME and attached are those approved.

### Suggested Python interfaces (names provisional; minimal, no implementation here)

```python
@dataclass(frozen=True)
class ReviewedArtifact:
    week: str
    original_bytes: bytes            # private; never print or log
    sha256: str
    byte_length: int
    source_receipt_sha256: str
    custody_ref: str                 # opaque private ID; not a public path

@dataclass(frozen=True)
class AuthorizedEditorialRelease:
    artifact_sha256: str
    week: str
    recipient_id: str                # privately resolved and bound
    approval_id: str
    purpose: str                     # "editor_language_review_only"
    expires_at: str
    source_review_id: str
    rights_decision_id: str

def verify_private_artifact(raw: bytes, pins: object) -> ReviewedArtifact: ...
def verify_owner_release(artifact: ReviewedArtifact, receipt: object,
                         policy: object) -> AuthorizedEditorialRelease: ...
def compose_editor_mime(artifact: ReviewedArtifact,
                        release: AuthorizedEditorialRelease) -> EmailMessage: ...
def rehearse_delivery(message: EmailMessage, release: AuthorizedEditorialRelease,
                      journal: object, fake_transport: object) -> object: ...
```

These are *type contracts*, not a demand to implement an abstraction hierarchy or keep manuscript bytes in long-lived memory. No public JSON serialization, journal table migration, CLI, SMTP import or secrets are created by this document.

## 4. C1 closeout: current task, not a new subsystem

**Input:** one synthetic `2026-10-10` manuscript fixture, expected exact SHA, original source-use subsection digest, private source/snapshot/journal paths, fictional `@example.invalid` recipient.

**Expected behavior:** reject public-Git or symlink-routed custody; require caller-owned non-group-readable original; reject missing/journal rollback; freeze without overwrite; independently validate bytes and source subsection; register **fictional only**, not `reserve_attempt`.

**Reviewer test matrix:**
- All 24 C1 tests genuinely execute against **the exact final head** under supported Python; neither Python import nor an unexecuted test count is a CI result.
- #385's latest private snapshot tests execute, including symlink-parent and original-digest changes; C1's copies match parent reviewed blobs.
- Simulate source mutation, frozen-file swap, same-length changes, missing/replaced journal, same-week revised SHA, concurrent workers, old/lost history and failed private copy.
- Full read-only suite, output validator warning delta, tracked DB/output equality and no WAL/SHM residues; no secret, model, external source fetch, actual recipient or SMTP.
- **Hold** until independent approval of #377/#382/#385 and C1, a clean rebased merge tree, and no blocked/skipped test receipt.

**Additional known hold:** journal's raw SHA-256 recipient fingerprint is guessable and cannot be a production privacy identity; a green C1 test does not cure this.

## 5. C2: specific owner/editorial consent, not a paper mountain

**Scope of the next small PR:** an **offline validator** for a versioned, signed or independently authenticated approval of one exact manuscript. The owner should perform one straightforward explicit action per approved edition; the editor should not see an internal approval worksheet. Reuse trusted signing helpers only if scope is authenticated; thematic-focus signature PR #307 is *not* permission to send a finished manuscript.

**Minimum consent record**, private and protected:

| Field | Contract |
| --- | --- |
| `schema`, `decision_id` | Canonical version and unique decision reference |
| `week`, `manuscript_sha256`, `length`, `source_use_sha256` | Bind **precisely** the reviewed original; any changed byte requires new owner action |
| `recipient_id`, `purpose` | One privately resolved editor, purpose `language_review_only` (not publication); reject multi-recipient and preview/editor conflation |
| `source_review_id`, `rights_decision_id` | Refer to distinct dated human fact/source and reuse-rights decisions; empty/hold/unknown does not pass |
| `approved_at`, `expires_at`, `revocation_reference` | Bounded consent and an independently checked revocation status |
| `approval_authenticator` | Independently verifiable signer or owner-controlled protected receipt. A simple SHA of a user-supplied statement is **not** authentic approval |

**Verification invariants:** no self-attested delivery approval by the sender code; no reusing week-only environment flag or a theme-choice token; every field matches frozen bytes and explicit recipient; stale/expired/withdrawn decisions fail closed; signer/verification material never enters Git/CI; private addresses use protected opaque ID or keyed pseudonym (not public raw SHA). Source-review status is a human decision and never inferred from model-provided citation counts.

**C2 tests:** wrong digest, wrong week, wrong purpose, spoofed signer, replayed theme token, revoked/expired consent, signer-key rollover, mismatched recipient, missing source/rights decision, fabricated model-source approval, unsafe logs, and re-approval after a textual correction.

**Acceptance:** the validator can affirm or reject *fictional signed receipts* with no private key provisioning and **zero** SMTP or paid model calls. Actual owner authentication method, source use, retention policy and destination contact are owner decisions; don't invent them in code.

## 6. C3: one deterministic MIME builder

**Single input:** the reviewed original `bytes` returned by C1 and an *independently authenticated* C2 scope decision. Do not reopen `path` between approval, body rendering and attachment construction.

**Contract:**
- Decode UTF-8 strictly and run the existing article extraction functions. Plain and HTML are article-first, easy for Dylan to edit; source/use ledger, IDs, internal hashes and research worksheet are **not in the body**.
- Exact original TXT bytes remain in one attachment as the owner-reviewed reference. Validate the MIME attachment decoded payload SHA and byte length equal the approved digest; no newline normalization.
- Exactly one allowed `To`; no unapproved CC/BCC, no owner preview sent to editor, no CRLF/header injection, no HTML external resource fetching or unescaped text.
- `From` and `Reply-To` come from separately validated operator configuration; subject clearly says **unapproved Sunday draft for language edits**, not published Brief.
- Renderer is pure: **no** SMTP, filesystem writes, model, source collection, template regeneration, journal mutations or preview dispatch. Varying MIME multipart boundaries may mean total MIME byte equality is unnecessary; invariants concern body semantics and decoded attachment bytes.
- Preserve existing article-first formatting behavior and add regression coverage for Unicode, minimal valid sections, markup escaping, duplicate headers, source-appendix leakage, and empty/corrupt content.

**Acceptance:** every MIME case runs offline; byte-identical reference attachment verified; no actual mailbox contact. Do **not** fold into current `send_packet` until a separate adapter gate exists.

## 7. C4: disabled adapter and ambiguity recovery

**Start only after accepted C1–C3.** Verify external approval/custody again immediately before admission. The adapter must have **no real transport available by default**. Use a separate injected fake transport interface in tests, without weakening #382's closed fictional scenarios.

**State transition:** `preflight -> registered -> attempt_reserved -> fake SMTP acceptance | outcome_unknown | held`; `attempt_reserved` is a durable boundary **before** the first transport contact. No exception handler may silently retry after a crash/timeout/lost acknowledgment. Fake SMTP acceptance is not proof of mailbox receipt or reading.

**Failure cases:** duplicate worker, changed digest/recipient, revoked approval after preview, untrusted recipient pseudonym, journal deletion/stale restore, missing independent checkpoint, source or private snapshot rewrite, failure before reservation, crash right after reservation, transport timeout, accepted-but-ACK-lost, SMTP rejection and operator restart. All uncertain outcomes must resolve to no automatic retry and a documented manual Sent-folder reconciliation path.

**Hard stop:** local SQLite atomicity does **not** prove exactly-once SMTP; private database restore can erase earlier attempts. Independent rollback-detecting checkpoint/storage and a human re-send policy are necessary before even one live adapter run. Do not activate the existing Sunday cron or enable `IPR_SUNDAY_EDITOR_DELIVERY_ENABLED` in this phase.

## 8. Weekly evolution and practical operating model

The current inspection and #385/C1 snapshot paths are intentionally locked to `2026-10-10`. **Do not simply delete that guard**. Once a single reviewed pilot is accepted, a *new scoped PR* may generalize date/schema eligibility while retaining explicit Saturday-close, full production-backed evidence, no duplicate weekly intent, exact approved bytes and source-rights review.

Keep the human workflow lightweight:
1. Generate **one** provisional Sunday manuscript with existing source evidence; hold if production-backed desk coverage is inadequate.
2. Owner reviews the article and flags source problems; background audits stay private.
3. Owner accepts or holds the exact SHA for the one editor and week.
4. If authorized and safe, Dylan receives prose-first email plus original TXT reference; Dylan edits *language, structure and clarity*, not government-source verification.
5. Return edits to owner for new final-article approval; **editor return does not itself authorize public publication**.

Explicitly out of scope: new dossiers/research papers, complicated weekly editor packets, forced multi-country themes, extra generation/Anthropic calls, repeat SMTP attempts, social-media automation or publication.

## 9. PR sequencing and small acceptance ledger

| Order | New PR / action | Owns | Gate before proceeding |
| --- | --- | --- | --- |
| 0 | Existing #385 exact-head full CI and #387 ordinary owner-authorized C1 CI | existing owner branches | No skipped run or inferred historical pass |
| 1 | Independently review/approve parents #377 then #382; review #385 separately; rebuild #387 on accepted versions | exact established modules only | Recheck full merge tree and original source/SQLite/output |
| 2 | C1 final integration | `core/sunday_c1_custody_binding.py` and its tests | 24 tests executed; all private data safeguards hold |
| 3 | C2 offline approval verifier | new narrowly named verifier/tests only | Human scope and key custody decisions explicitly unresolved or resolved by owner |
| 4 | C3 pure MIME builder | new pure composer/tests only | Attachment hash/recipient/body equality; no provider |
| 5 | C4 disabled adapter | new adapter/tests; no workflow rewiring | Crash/unknown/rollback/resend matrix complete |
| 6 | C5 private operations rehearsal | protected store, runbook, synthetic-only recovery evidence | Separate owner selection of infrastructure and budget |
| 7 | C6 owner-authorized real pilot | **not included** | New explicit authorization naming week, manuscript, source-rights status, recipient and time |

**Required evidence from every implementing agent:** issue; exact base/head and file diff; 3–5 sentence threat/limitation statement; focused tests truly run; full Python 3.9 read-only CI, output and DB preservation; failure/recovery matrix; no secret/model/SMTP; remaining owner decision. Tests and path assertions are not evidence of signed consent or permission to send.

## 10. Efficient next-session handoffs

**C1 reviewer:** “Inspect #377/#382/#385/#387 current refs and CI. Do not change draft status or bypass a blocked action. Obtain normal authorized C1 test receipt; review all new permission and symlink cases; report exact-head pass/hold, parent acceptance order and a six-path diff. No merge or send.”

**C2 engineer:** “Implement *only* an offline authenticated approval-receipt verifier for a specific reviewed Sunday TXT SHA/week/source-receipt/recipient/purpose. Use fictional keys/receipts, no real identity/SMTP/model/source bodies. Explicitly reject reuse of #307 theme approval. Tests first; small review PR, no runtime integration.”

**C3 engineer:** “Implement *only* a pure, byte-preserving MIME composition function reusing `sunday_editor_readable`. Input reviewed bytes and fictional C2 release, output one message, not a send. Assert source appendix absent from body and original attachment digest identical. No SMTP credentials or workflow edits.”

**C4 engineer:** “After independent C1–C3 acceptance, build one disabled fault-injected adapter with #377 reservation and unknown-outcome holds; never connect real SMTP. Test crash-after-reserve, lost acknowledgment and stale journal restore; report blockers rather than bypass them.”

**Editorial owner decisions (not coding tickets):** rights/retention decision for private source material; genuine reviewer identity/signing custody; protected storage and restoration checkpoint; editor address/channel; correction/re-send policy; whether any pilot should be sent. A user approval of a pull-request merge never implicitly approves these separate acts.

**Definition of completion for this document:** it is attached to the existing docs-only draft planning PR #375 with no production edits, and links back to the C0–C6 plan. **No implementation, activation, SMTP, owner signature or PR merge follows automatically.**
