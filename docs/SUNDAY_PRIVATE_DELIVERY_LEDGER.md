# IPR Sunday Briefs — private delivery ledger (R2 scaffold)

**Status: implemented offline but DISABLED for production SMTP.** This is a
private, durable, metadata-only prototype for issue #399. No Sunday sender
uses it until an independent reviewed storage/SMTP/Gmail integration phase.
Neither running this CLI nor recording a state sends mail or approves a Brief.

## Why this is needed

On October 11, 2026 the scheduled Sunday editor handoff did not run. The
manuscript was later emailed manually. A naïve retry after a runner timeout
could be worse: Gmail may have accepted a message before GitHub recorded its
success, creating two drafts addressed to Dylan. A GitHub scheduled event,
a successful workflow, SMTP acceptance, the real Gmail Sent record and
publication permission are **five different kinds of evidence**.

A journal entry is keyed by reporting Saturday and a stable HMAC digest
of the editor's single bare mailbox address. It reserves **one original
TXT manuscript SHA-256 per recipient and Saturday**. Reserving another
attachment, or beginning a second attempt, fails closed.

States:

1. `RESERVED_NO_SEND`: no external SMTP attempt has yet been started.
2. `ATTEMPT_STARTED_DELIVERY_UNCERTAIN`: atomically recorded **before**
   entering external SMTP; crash here cannot safely be retried.
3. `SMTP_ACCEPTED_UNCONFIRMED`: operator reported a successful SMTP API
   return, **not** a verified Gmail Sent receipt.
4. `SENT_ATTESTED_BY_OPERATOR`: operator supplied a Sent message reference
   for the exact attempt. This is still **not** independent programmatic
   verification; the journal faithfully reports that limitation.

A correctly functioning independent Gmail reader is needed before any state
can represent programmatically verified Sent mail. ALL states explicitly
set `automatic_retry_authorized=false`. The journal is not a permit to send.

## Private environment only

Create a durable, mode-0700 private directory **outside the repo**, such
as `/private/ipr-editor-ledger`. Configure a stable 32+-character randomly
generated `IPR_DELIVERY_LEDGER_KEY` in the owner's private environment.
Do not store the key in git, workflow variables, Actions logs or an email.
Changing it makes existing recipient identities unrecognizable; the
program refuses changes using a key-commitment check.

The journal file must have the `.sqlite3` suffix, is created mode-0600,
and records only the reporting week, HMAC recipient tag, exact original
attachment hash, state, private attempt token, operator evidence ID and
timestamps. No article text, recipient mailbox, SMTP secret, original
government text, prompt or full email body is written.

An operator example using FAKE identifiers — **do not run this with real
email credentials or mistake it for authorization to send**:

    python -m scripts.sunday_delivery_ledger initialize \
      --ledger /private/ipr-editor-ledger/editions.sqlite3 \
      --week-ending 2026-10-17 --recipient editor@example.invalid

**Initialize exactly once after provisioning secure durable storage.**
All later reserve/start/record operations refuse a missing journal rather
than creating a new blank database when a runner loses its storage.
A missing existing ledger requires forensic recovery, not reinitialization
as a routine automatic fallback. `inspect` on a missing path emits
`LEDGER_MISSING_STOP` and does not create one.

    python -m scripts.sunday_delivery_ledger inspect \
      --ledger /private/ipr-editor-ledger/editions.sqlite3 \
      --week-ending 2026-10-17 --recipient editor@example.invalid

    python -m scripts.sunday_delivery_ledger reserve \
      --ledger /private/ipr-editor-ledger/editions.sqlite3 \
      --week-ending 2026-10-17 --recipient editor@example.invalid \
      --attachment-sha256 <exact-original-txt-sha256>

The `start` action is available ONLY to a future explicitly reviewed
integration that persists the uncertain state **before** calling SMTP.
It returns a private `attempt_token` to bind a subsequent
`smtp-accepted` or `sent-attested` metadata update. Tokens should never
be copied into public Actions logs. A manual operator must separately
verify the actual Gmail Sent item before any attestation.

## Engineering and failure conditions

- The storage location must be truly durable between runner executions.
  `RUNNER_TEMP` is explicitly **not durable** and cannot provide dedupe.
- SQLite uses BEGIN IMMEDIATE and a unique (week, HMAC recipient) index to
  serialize competing reservations and transitions.
- A missing, inaccessible, world-readable, symlinked or lost journal is
  a STOP for any future integrated sender. The parent directory must also
  exclude group/world permissions. Never invent a new blank ledger and send
  another draft.
- Changing a digest, date, recipient identity or stable key refuses a
  repeated attempt. SMTP exceptions/timeouts must remain `UNCERTAIN`,
  including cases where the network may have accepted the payload.
- Even a fully working journal cannot guarantee global exactly-once email:
  SMTP and SQLite are separate systems without one distributed transaction.
  Operator Gmail verification and explicit recovery are necessary.

Offline tests:

    python -m unittest tests.test_sunday_delivery_ledger -v

Coverage includes date/mailbox input validation, key rotation, permissions,
an unchanged Sent-uncertainty boundary, a wrong attachment, two competing
reservation processes, refusal of a second attempt, and the lack of plain
recipient or HMAC secret in the database.

## Future integration gate

Before activating against SMTP, privately provision an access-controlled,
persistent journal and test a real end-to-end **no-email** simulation of
before-SMTP reservation, crash after SMTP acceptance, ambiguous return,
Gmail confirmation and recovery. A historical edition already sent
manually cannot be backfilled as unsent. Keep a separate human approval
for editorial publication and respect source-use/translation gates.

This R2 scaffold deliberately changes **no** production workflow, credential
setting, editor recipient, model invocation, country desk or publication path.
