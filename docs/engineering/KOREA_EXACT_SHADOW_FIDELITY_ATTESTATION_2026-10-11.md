# Korea Desk — exact Git-source original-HWPX attestation

**October 11, 2026.** PR-only read of existing `shadow/korea-policy-briefing` preserved Git objects. **Not** publication approval or source-license clearance.

## What is being independently rechecked

The existing `scripts/audit_korea_source_fidelity.py` is already capable of re-extracting Korean HWPX text from the actual captured original bytes, testing archived original HTML/HWPX SHA-256 parity, Korean body parity, issuer, article identity and source-URL correctness, and examining chronological published shadow ledgers. The previous human handoff from PR #218 was a **blank** reviewer worksheet, not an editorial or legal signoff.

This PR adds a **PR-only** read-only GitHub Actions execution of that existing real-source audit, rather than another synthetic parser. The audit copies the literal current shadow Git branch to a runner temp directory (no publisher requests, no source branch write), checks that the fetched commit matches the GitHub branch at clone time, then validates the SHA-bound records. CI fails if any preserved HWPX cannot be reconstructed, any body differs, any successful day in the declared window is missing, or checksum continuity fails. It verifies that every human and rights approval flag remains unset. The console prints a bounded summary and exact Git commit. Raw HWPX/body captures and blank worksheets are **not uploaded** to a publicly accessible artifact.

Source-attributed identities on `www.korea.kr` remain Korean Ministry of National Defense (국방부) **republications by Policy Briefing**, not direct requests to `mnd.go.kr`. DAPA `B00008` is a separate unapproved source with a separate robots-first manual canary; it is not included in this read.

## Operational distinction

A published success ledger captures only a successful shadow state publication. **An Actions job that fails before state publication may be absent**, so `scheduled_continuity=PASS` never implies complete delivery reliability or a clean Actions run history. That remains a separate API-run reconciliation. Also, HWPX XML extraction and SHA parity do not prove Korean-language semantic correctness, table ordering, technical terminology, or distribution versus portal posting dates; a real Korean reviewer must inspect the actual original per article and record the source SHA, date, identity and specific rights assessment.

## Trust boundary / stop

This checks existing archived bytes **only**. No live publisher requests, new captures, schedule changes, state mutation, registry, production DB, output, HTML site, briefs admission, LLM input, SMTP or deployment.

The workflow only runs on PR changes to this audit surface. Current `main` contains a separate **manual** source-fidelity reviewer workflow; this PR does not dispatch, change or bypass the human reviewer requirements. The new CI check is a machine-only attestation of the current shadow state. If its full byte audit passes, **the next gate remains** a Korean-language human verification and source-specific KOGL/attachment scope review, followed by an explicit owner decision for bounded synopsis publication, not bulk document reuse.
