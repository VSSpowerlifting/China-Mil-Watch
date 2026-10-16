# C3 pilot: pure, unsent reviewed-manuscript MIME

**Issue:** #366. **Execution plan:** draft #375, C1–C4 contract. **Status:** an independent, additive-only, no-send engineering experiment from main, not authorization to merge parents or email Dylan.

## Why this is deliberately separate

`scripts/sunday_editorial_handoff.py::send_packet` currently combines message creation with actual SMTP. It rereads a mutable file path, checks environment credentials and can contact a real mail provider. It is **not** the right unit to call from a future reviewed-artifact pipeline before C1 and C2 are independently accepted.

The new `core/sunday_reviewed_mime.py::compose_fictional_reviewed_editor_mime` instead accepts **original TXT bytes**, the separately supplied lower-case SHA-256, the explicit first-pilot reporting Saturday, and **only two `@example.invalid` fixture addresses**. It returns a standard-library `EmailMessage` object and does not send it. It imports no path, email delivery transport, credentials, network, Anthropic, databases or production workflow.

It reuses the **existing** `sunday_editor_readable.prose_only_text/html` renderers, which already give Dylan only readable article prose, not the internal source ledger or technical appendix in the body. Exactly one attachment contains **byte-for-byte original reviewed TXT**; a MIME payload self-check before return asserts this. The subject marks the article an **unapproved** language-editing draft. No second model generation or new source selection.

## Pure input/output contract

`compose_fictional_reviewed_editor_mime(original_bytes, *, week, reviewed_sha256, recipient, sender) -> EmailMessage`

- The exact reporting Saturday is `2026-10-10`; refusing every future week prevents this rehearsal from quietly creating a recurring live sender.
- Require bounded strict UTF-8 bytes, no NUL or CR normalization, an exact raw SHA pin, one reporting identity and complete unique source-use and appendix markers with the original unapproved footer.
- Require simple canonical single fixture mailboxes under `example.invalid`. Reject real addresses, sender=recipient, commas, display names, CRLF injection, multiline values and malformed identities.
- Body is a **presentation** of the reviewed bytes, never a new model-authored article; renderers escape HTML and exclude structural source-workbook sections.
- The exact original bytes, not re-encoded Unicode, are attached. The MIME part payload is checked before return; tests also parse a serialized MIME message and compare bytes.
- No `smtplib`, `send_packet`, model API, journal registration, private-file access, output migration or scheduled workflow is imported or invoked.

**Verification limitation:** A caller-supplied SHA proves byte equality, not actual human review. This code does not verify the source-use citations against original-language government records, publisher rights, sender ownership, editor destination or expiry/revocation. It is **not** C2 approval and must not be called by C4 until C1/C2 pass their own gates. It does not protect arbitrary sensitive text intentionally placed by a model inside article-prose fields; human/source review remains necessary.

## Offline tests (14 synthetic methods)

`python -m unittest tests.test_sunday_reviewed_mime -v`

Tests cover: exact attachment through MIME serialize/parse, article-first prose/HTML and source-appendix exclusion, unapproved headers/no CC/BCC, wrong SHA or changed bytes, wrong week, canonical recipient and sender separation, NUL/invalid UTF-8, CRLF normalization, missing/duplicated source-use markers, missing unapproved footer, too-large/non-bytes input, malicious article HTML escaping, and no live transport/imports.

The fixture comes from the existing synthetic `tests.test_sunday_editor_readable.reviewed_packet`. No real editor address or private publisher material is used.

## Integration and review gates

- This branch is **independent** of the unmerged #377/#382/#385/#387 stack; only three new files on main. It must not change the live sender to use this builder in the same PR.
- Require exact-head read-only Python 3.9 full-suite CI (including all 14 methods), rendered-output validation, tracked SQLite/output preserved, and a distinct independent source/recipient risk review before accepting code.
- After C1 is accepted and a **real, separately scoped owner-approval verifier** exists in C2, a later adapter may pass verified bytes/release identity through a production-qualified builder. This fictional one currently refuses all real addresses.
- Do not add SMTP, secrets, cloud storage, scheduled triggers, source collection, another model call, live publication, or operator release in this phase. No merge/activation is authorized by passing tests.
