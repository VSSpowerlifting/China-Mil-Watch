# C2 — fictional, offline owner-release verification prototype

**Project:** Indo-Pacific Record, [#366](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/366). **Scope:** 2026-10-10 first-Sunday **fixture only**. This is a component review, not consent to send a real edition or reuse source material.

## Narrow contract

`core/sunday_fictional_approval.py` contains a small standard-library HMAC-SHA256 verifier, with *no* signing key, CLI, path/SMTP transport, email dispatch, model call, publisher fetch, repository output write, or scheduler. Signing occurs **inside tests only** with a plainly labeled synthetic key.

`verify_fictional_editor_release(manuscript_bytes, source_use_sha256, signed_receipt, *, verifier_key, now_utc, revoked_decision_ids) -> FictionalRelease`

It binds a canonical, versioned receipt to:
- **Exact bytes:** SHA-256 and bounded byte length, plus an independently supplied source-use fingerprint (not a fact-check).
- **One edition and purpose:** October 10, 2026 reporting Saturday, `language_review_only`—never publication or delivery.
- **One synthetic recipient and signer:** only lowercase single `@example.invalid` mailboxes. Sender/signer cannot be the editor. Header injection and real addresses are refused.
- **Three distinct references:** decision ID, source-review ID, and rights-decision ID. A thematic-choice token cannot be repurposed as delivery approval. The `fictional-` prefixes signify that these IDs do **not** authenticate human activity.
- **Time and revocation:** canonical UTC timestamps, no more than 72 hours validity, explicit time and revocation-set injection; future, expired and revoked receipts fail closed.
- **Signature envelope:** strict claim keys, deterministic JSON and domain-separated HMAC, constant-time comparison. Unknown or forged fields never gain scope.

All successes return a `FictionalRelease` whose `authenticated_owner`, `rights_verified`, and `mail_authorized` fields are permanently **False**. No actual recipient can be returned.

## Test evidence

`tests/test_sunday_fictional_approval.py`: **18 standalone offline Python `unittest` methods** (including subcases), run locally before PR: `Ran 18 tests ... OK`. Cases include byte mutation, wrong source digest, invalid fields, impersonated/replayed signer, recipient/header injection, expired/future timestamp, revoked decision, missing revocation source, weak HMAC verifier, purpose/week drift, insufficient review/rights refs, and wrong key. The tests use synthetic text and an explicitly fake key; no real editorial/source data.

Require **separate exact-head repository Python 3.9 full read-only CI** plus output/DB preservation, and independent code review, before treating this as a validated prototype. A local standalone pass alone is not full-suite evidence.

## Non-goals and limits

This verifier is **not** a secure production signing service. Passing an injected HMAC key and fictitious rights/source references does **not** prove genuine owner consent, independent fact-checking, source rights, fresh revocation, key custody or sender authorization. In a later separately approved design, authentic decision capture, key provisioning/rotation, audited rights and source-review evidence, persistent revocation and private recipient resolution must all be independently established. Never substitute a self-supplied SHA or a thematic focus approval for these controls.

It is **deliberately not connected** to #377 (journal), #382 (fictional replay), #385 (snapshot), draft #387 (C1 custody), #394 (pure MIME), or the scheduled Sunday workflow. A future C4 adapter remains blocked until these pieces are individually accepted and real authority is explicitly decided.

**No merges, real credentials, user decision, SMTP, email, model-generation expense, production workflow activation, public source content or publication is authorized by this file.**
