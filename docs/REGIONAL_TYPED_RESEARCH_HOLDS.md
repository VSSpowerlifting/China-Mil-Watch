# Regional typed-source holds: Japan and Vietnam (Issue #271)

This is an **offline metadata reconciliation and HOLD report**, not country
desk activation, publisher attestation, AI input permission, or a replacement
for the first-Sunday source-provenance gates.

The program consumes the existing `load_editorial_evidence`-validated
Japan/Vietnam research-note packet and independently rebuilds the exact-week
all-desk `regional_weekly_inventory.inspect` using a disposable read-only
SQLite copy. It cross-checks each typed shadow/research pointer against the
inventory's pending lane, rejects duplicate publisher URLs and cross-lane
source identities, and reports the *structure* of historical immutable source
pins separately from live authenticity.

A version string, Git commit or SHA-256 displayed in this HOLD report means
**only** that such metadata was present in the existing private note. It is
not proof that the current shadow collector still contains those exact bytes,
that a public PDF matches the captured extraction, that the article's original
language was verified by a human, or that a publisher authorized reuse.
A public webpage note with no preserved body is explicitly listed as
`publisher_page_immutable_original_missing_requires_review`.

For the October 10, 2026 reporting Saturday, the report flags missing exact
Japan MOD IDs and absence of any Vietnam MPS research note. It does not
fabricate missing sources or claim publishing institutions were inactive.
The live Sunday `sunday_japan_offer_gate` and Vietnam's source-verification
checks remain **separate and authoritative**. On subsequent weeks an empty
research packet is recorded as no evidence reviewed, never official silence.

Run locally with a private, existing output directory (example path is a
placeholder; no directory is created by the tool):

```bash
python -m scripts.regional_typed_research_holds \
  --week-ending 2026-10-10 \
  --as-of 2026-10-10 \
  --review-local-day 2026-10-11 \
  --research-directory research/briefs_editorial_evidence \
  --out /private/held-japan-vietnam-evidence.json
```

The output is new, outside the repository, exclusive mode 0600. It contains
typed IDs, desk/date, historical publisher URL *digests* (not URLs or bodies),
the stated archival digest/commit, reasons for holding the record, and
hardcoded **false** publication/model/email/production authorization.
No source titles, analyst synopses, URL strings or original article bodies
appear. The script does not invoke a model, SMTP, collector or publisher API.

The **next independently scoped work** under #271 is actually re-verifying
current Japan/Vietnam original source state and machine-read rights, followed
by human original-language/source-use reviews. Until then none of these
source IDs may be passed into regional model selector #263 or handoff #266.
This PR is not a source-use mechanism and does not change Sunday's running
writer or its exact-manuscript first-pilot owner release.
