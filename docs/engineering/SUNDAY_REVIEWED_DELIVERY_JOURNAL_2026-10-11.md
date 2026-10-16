# Sunday editor delivery — disabled private send-intent journal

**Issue:** #366. **Scope:** fictional/private local admission-and-recovery proof only; no email, model, scheduling, or production changes. This code is NOT imported by an active script, sender or workflow.

## Why

The existing scripts/sunday_first_pilot_reviewed_replay.py can manually replay the owner-reviewed October 10 TXT with a separate local opt-in and without regenerating AI text. It explicitly warns that SMTP may be ambiguous and does not prevent duplicate sends across restarts. A reviewed file's SHA only binds bytes; it cannot prove the human actually approved those claims or licensed source use.

This package adds core/sunday_delivery_journal.py: an opt-in, fail-closed SQLite **send-attempt reservation fence**, plus synthetic tests. It stores metadata only: week, SHA-256 of the original reviewed manuscript, SHA-256 of its independently verified source-use receipt, a recipient address fingerprint, SHA-256 of genuine externally verified owner approval and a hashed SMTP-server acceptance receipt. It **never stores article/source prose, email address, credentials, or email message**.

The module has no CLI, network calls, SMTP imports, env activation, or background task. No Sunday workflow or live sender invokes it. **This is not an email service or a release-ready integration.**

## Intended future sequence

1. A trusted operator freezes exact owner-preview bytes **outside public Git** and independently confirms the original-language sources, permission scope, recipient and genuine dated owner approval. The journal is incapable of verifying legal permission or authenticating an owner.
2. A future separately reviewed adapter computes and validates the manuscript, source, owner and recipient identities; register(...) records their digests. Identical registration never resets state; conflicting receipt/approval for the same week/recipient/manuscript is refused.
3. reserve_attempt(intent_id) acquires SQLite's immediate write transaction. Only one cooperating local worker may transition registered to attempt_reserved. A crash after reservation leaves an **uncertain, non-retryable** state even if actual SMTP contact never occurred.
4. A future adapter can record smtp_accepted only after real SMTP server acceptance. Acceptance **is not recipient delivery**, nor evidence Dylan read it.
5. A timeout or ambiguous SMTP error can be recorded outcome_unknown, which is permanently held from automatic retry. There is **no reset/retry method**; operator review of the account Sent items and other provider evidence would require a separately approved reconciliation procedure.
6. A prior reservation is never blindly rearmed, regardless of restarting the process, a renewed approval hash, or an altered source-use receipt.

**Exactly-once SMTP is NOT promised.** A local journal and an SMTP service cannot commit atomically. This is an *at-most-one automatic admission attempt per reporting Saturday and normalized recipient* within one private, trusted store. A revised manuscript with a new digest for that same week/recipient is held; corrections and second editions require a separately reviewed operator procedure. A new recipient constitutes a different identity and still requires independently authenticated approval. It is not multi-host distributed consensus, transport receipt verification, cloud encryption, secure backup, or an auth system.

## Private storage requirements

The first installation must use **DeliveryJournal(path, initialize_new=True)** after a separate trusted operator decision; all subsequent opens must use **DeliveryJournal(path)** without that flag. An absent, empty, hardlinked or structurally invalid prior database is a **recovery hold**, never automatically replaced with a pristine journal. Older files that have all expected columns but lack the database-enforced unique (reporting_week, recipient_sha256) index are also refused: silently accepting them would bypass the new per-week duplicate fence. A new empty journal cannot prove that older emails were not attempted; creating one after data loss requires independent recovery and reconciliation. The constructor requires an **explicit absolute path in an existing caller-owned 0700 directory**, creates a new file at mode 0600 only under the deliberate initial mode, and refuses file symlinks and hardlinks. Do not store it in this public repository, in output/, a public artifact, or on an ephemeral Actions runner. SQLite journals and backups need the same private controls. Trusted local filesystem, trusted cooperating processes and external owner approval are assumptions, not guarantees this module can itself establish.

## Verification and release blockers

Synthetic-only test module: python -m unittest tests.test_sunday_delivery_journal -v (stdlib, Python 3.9 compatible). Covers Saturday/recipient validation, symlink/hardlink and directory permission refusal, absent approval digest, immutable source/approval identity, revised-manuscript same-week refusal, a distinct-recipient boundary, missing legacy uniqueness index, competing SQLite workers, crash/reopen, lost/empty/invalid journal refusal, ambiguous SMTP, no pre-send acceptance, metadata-only storage and no duplicate automatic reservation. An earlier head (16 tests) passed full CI with 5,663 Python tests/9 skips. **This revised 20-test exact head has changed since that receipt and needs fresh CI; do not reuse the earlier run.**

Before any merge: independent code review; exact-head offline tests; rendered-output validation; tracked database/output preservation. Before any live integration: secure non-ephemeral private storage selected by owner, safe authentic review/permissions source, exact attached-byte handoff, SMTP fault injection around pre-send/post-acceptance lost acknowledgment, operator reconciliation for unknown attempts, explicit owner approval and separate weekend scope. Do not enable Sunday sending, change the workflow or send Dylan anything from this PR.
