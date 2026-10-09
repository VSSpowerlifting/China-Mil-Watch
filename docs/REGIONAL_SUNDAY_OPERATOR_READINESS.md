# Regional Sunday operator readiness (no model, no editor delivery)

This is a **read-only, source-text-free status receipt** for Indo-Pacific
Record's cross-desk weekly review. Its purpose is to make the next operator
decision obvious without encouraging premature manuscript generation.

The report composes the repository's existing independently read-only
`regional_weekly_inventory.inspect`, which already enforces the actual
production SQLite integrity check, desk manifest, full reporting-week
selection and the Sunday successful-daily marker. It does not duplicate the
collector, decide a theme, sign a source or validate publishing rights.

## When to use it

On **Friday, October 9, 2026** (the week ending Saturday October 10 is
unfinished), the safe operation is a held diagnostic, not a manuscript:

```bash
python -m scripts.regional_sunday_operator_readiness \
  --week-ending 2026-10-10 --as-of 2026-10-09 \
  --review-local-day 2026-10-09 \
  --out /private/ipr-regional-sunday-operator.json
```

On Sunday October 11, **after** the daily production job has completed
successfully and recorded its same-Sunday marker, repeat with
`--as-of 2026-10-10 --review-local-day 2026-10-11`. Optionally supply
`--private-evidence-directory research/briefs_editorial_evidence` to include
*counts only* of shadow Japan/Vietnam candidate notes. Their presence remains
a research hold and never boosts production desk coverage.

Replace `/private/` with an existing **private directory outside the
repository**. The command exclusively creates a new mode-0600 JSON file. It
will refuse an existing output, symlink or in-repository destination; no
report is uploaded by CI or written to the repository.

## What the receipt contains

- Exact reporting dates and source-inventory SHA-256 commitment. It recomputes
  that inventory's metadata digest (a **consistency checksum**, not a
  publisher-authenticity proof or cryptographic human signature).
- The upstream Sunday production-corpus gate and individually named blockers:
  unfinished Saturday week, not-yet-due Sunday update, stale/missing marker,
  fewer than two live desks with usable text, or no unscreened production
  records. Unknown gate codes are rejected rather than silently ignored.
- Per-desk **counts only**: stored, reviewable, held, pending private
  research, plus desk registry status and observed evidence status. Held
  records are also grouped by reason, not by title or publisher URL.
- Clear operator next actions, including source-review and exact-attachment
  owner-release requirements. A desk with no qualifying record does **not**
  imply the government or publisher issued nothing.
- Deliberately false `model_called`, `model_input_authorized`,
  `editor_email_authorized` and `publication_authorized` flags. Even a
  complete production machine audit is labelled
  `passed_machine_only_not_model_or_email_approval`.

No record IDs, titles, publisher URLs, original article text, translations,
analyst synopses, source-review signing key, candidate thematic thesis, SMTP
recipient or editorial manuscript is included. The input is rechecked for
source and coverage-count consistency before summarization.

## What must still happen before a Sunday Brief

The **machine corpus** check is necessary, not sufficient. The sources
still require independent current publisher/original-language checks,
source-use scope review and owner-HMAC signoff; a private regional thematic
proposal requires its own owner authorization. The chosen theme is then
subject to a separate signed decision and no-model exact-source audit.
Even a successful owner-reviewed private model rehearsal does **not** authorize
sending Dylan an issue. The existing **exact reviewed manuscript attachment
SHA-256** and the live Sunday/Friday release workflow remain authoritative.

The shadow/research Japan and Vietnam sources are separately held: even if
this diagnostic sees six metadata candidates, that does not prove current
publisher version, original-PDF preservation, reproduction rights or
permission to feed those items into the regional model.

## Guardrails

This feature adds neither GitHub Actions schedules, external model calls,
private publisher-body copying, SMTP sends, country desk activation, release
switches nor public site changes. It does not import the model selector or
writer. Its no-network synthetic tests include an unfinished Friday, complete
Sunday, missing Sunday marker, held source reasons, research pending counts,
forged approval fields, tampered source metadata digest, and an exclusive
private output file. The focused CI verifies production SQLite/site output
preservation. Full exact-head repository CI remains a PR merge prerequisite.
