# Private human source-review worksheets — research HOLD only

This is a deliberately **UNSIGNED, non-operative human review worksheet** for
the typed Japan/Vietnam research records of [Issue #271](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/271).
It supplements the all-desk HOLD inventory and machine-receipt reconciliation;
it is not a source attestation, legal clearance, editorial signoff or
automation interface. **Editing or filling out this file cannot grant
authorization to any IPR model, email workflow or publisher.**

## Operator use

Only after the reporting week has ended and the successful Sunday
daily-collection marker exists, create the metadata-only worksheet:

```bash
python -m scripts.regional_typed_human_review_prep \
  --week-ending 2026-10-10 --as-of 2026-10-10 \
  --review-local-day 2026-10-11 \
  --research-directory research/briefs_editorial_evidence \
  --out /private/unsigned-source-review.json
```

The `/private` path represents a directory **already present outside the
repository**. The tool creates a new mode-0600 JSON file and never replaces
an earlier source review or writes to GitHub. Run it locally; it performs
no HTTP requests, AI calls, SMTP sends or shadow collection changes.

The sheet contains each held source's original issuer URL, title, language,
date, typed ID and historical commit/content hash if one exists. All six
current records start as `UNREVIEWED_UNSIGNED_TEMPLATE_ONLY`. Required
checks are initially `null` (not false confirmations) and include:

- Check issuing body and visible publication date at the **current official
  publisher original**, identifying changes from the historical capture.
- Compare the complete original-language article/PDF against its historical
  version, not merely a title or translation. Record limitations or
  original PDF bytes that were never preserved.
- Check translation integrity, omissions, evidence boundaries and source
  attribution; compare claims against what the source actually establishes.
- Independently check terms of reuse/retention and the exact proposed private
  model synopsis scope, with a documented rights basis. Do not infer rights
  from public URL accessibility or an archived SHA-256.
- Record reviewer identity, edition/capture, discrepancies, limitations and
  reasoning for any future permitted source-use decision.

For the October 10 packet, the two Japan HTML pages lack archived original
bodies; the Japan PDF has historically checked extracted text but lacks
full original-PDF bytes and fidelity review; Vietnam notes carry older/current
state-version identifiers that must be compared per record. These omissions
are surfaced as work items, **not** as evidence of publisher inactivity.

## Strict non-approval boundary

The generated worksheet contains **no original full text, copied PDF or
article bodies, analyst-written research synopses or final analysis**.
It is private metadata for a human editor. An editable form isn't a
cryptographic signature; the worksheet's SHA-256 is only a reproducible
checksum over unsigned data, and can be recomputed by anyone editing it.
All model, publisher-body-copy, production, editorial email and public
publication permissions stay false, no matter what the user types.

If the editor later wishes to make notes usable for one private thematic
manuscript, that requires a separate purpose-built human source-use attestation
and fresh independent version checks. **This PR intentionally contains no
validator or signer capable of promoting the filled worksheet.** The live
October 11 exact-owner-reviewed attachment approval remains a different gate.
