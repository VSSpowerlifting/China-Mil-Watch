# Source readiness preflight for IPR Friday Briefs

This is an inexpensive, **manual-only read-only** preflight for the weekly
Indo-Pacific Record Briefs source packet. It does not generate prose and does
not need Anthropic or SMTP secrets.

## Use

1. Open the GitHub Actions workflow named
   **IPR Briefs Source Readiness Preflight (No Model, No Send)**.
2. Choose Run workflow on main and enter a reporting Friday date in strict
   YYYY-MM-DD format (for example 2026-10-02).
3. Read the job log's final aggregate report. A green result means at least
   two distinct production-backed desks contributed records selected under
   the same full-text/source-trail gate as the automatic writer.

Local equivalent from repository root:

    python -m scripts.weekly_briefs_source_preflight --friday 2026-10-02

## Report fields

The report names the Sunday-Friday evidence boundary, Saturday identity,
total stored records in the source window, offered source candidates, number
of usable full-text bodies, total chosen bodies for the model, and per-desk
counts. A candidate is deemed full-text eligible only if its original
source-trail entry still matches the stored record and its stored English
or original-language body contains at least 250 characters.

The preflight calls the **same deterministic evidence chooser** as the
Friday writer. It neither prints nor uploads the selected bodies, source
URLs, article titles, credentials, nor unpublished editorial prose.

An insufficient cross-desk source packet produces a blocked report and a
nonzero exit status. Unexpected provenance problems are not swallowed.
A model can still time out, return invalid citations, or write weak prose
even after the preflight is green. This is a *readiness* check, not an
automatic editorial approval.

## Data and security boundaries

All database connections use the repository's established read-only SQLite
accessor. The workflow token has contents: read; there is no write
permission, schedule, GitHub artifact, email recipient, SMTP operation,
API key or LLM request. The source data remains within the GitHub runner,
and only aggregate counts are shown in workflow logs. This tool does
not authorize numbering, deploying, emailing Dylan, or publishing a Brief.

Leave IPR_EDITOR_DELIVERY_ENABLED disabled until the governed writer,
Gmail authentication preflight, and recipient-facing owner-approved email
test succeed. Source-readiness success alone is insufficient to activate
scheduled delivery.
