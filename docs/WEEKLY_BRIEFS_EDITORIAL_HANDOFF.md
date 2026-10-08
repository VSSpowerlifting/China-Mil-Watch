# Weekly Briefs editorial handoff to Dylan

This is a **private, unapproved editorial handoff**, not a publication workflow.

## What the Sunday job does

1. Read the last **complete Saturday-ending week** in America/New_York.
2. Discover the actual live, production-backed desks from the desk registry.
3. Run the existing read-only `scripts/author_brief.py scaffold` command.
   It retains per-record desk, source, original-language title, URL,
   screening state, and coverage. It calls no generative writing model.
4. Turn that scaffold into **one editable `.txt` worksheet**, with blank
   manuscript sections and a read-only source-record appendix.
5. If and only if delivery is enabled, email the worksheet to the Associate
   Editor through an explicitly configured Gmail SMTP account.

The schedule is `17 15 * * 0` UTC (Sunday at 11:17 a.m. EDT / 10:17 a.m.
EST). GitHub Actions is not a precisely timed mail scheduler; delayed starts
are possible. Any manual run uses the last **completed** Saturday, never
the current Saturday while still in progress.

A week with candidates from only one live desk still produces a worksheet,
but carries a conspicuous **coverage warning**: it is not eligible as an
ordinary cross-desk Brief, and a single-desk Brief needs Ben's separate,
recorded approval. A week with no candidate records fails explicitly rather
than emailing an empty draft. Nothing here assigns a number or editorial
approval. Unscreened records remain marked, not treated as verified analysis.

## Turn on emailing (required owner-controlled configuration)

In the repository, go to Settings → Secrets and variables → Actions.

Create **repository secrets** (never commit values or put them in a PR):

- `IPR_EDITOR_TO`: Dylan's confirmed email address
- `IPR_SMTP_USER`: sending Gmail address controlled by Ben
- `IPR_SMTP_APP_PASSWORD`: Gmail app password for that sending account,
  not the regular Google password

Use an account that supports Gmail app passwords (two-step verification may
be required; managed school accounts may not allow them).

Create **repository variable** `IPR_EDITOR_DELIVERY_ENABLED` with value
`true` *only after* a successful manual test. Until then scheduled runs
still prepare locally, but send **nothing**.

In Actions → "Weekly IPR Briefs Editorial Handoff" → Run workflow, run first
with `send_email=false` to verify the candidate counts. Then, with real
recipient and SMTP secrets configured, use `send_email=true` for one test
delivery. A manual send may repeat that week's email; avoid unnecessary
retries. Never paste email credentials in workflow logs or issues.

The worksheet exists only in the job's temporary runner directory before
delivery. It is intentionally **not uploaded as a public Actions artifact**
or committed to this public repository.

## Dylan's reply and the controlled import

- Dylan edits the worksheet's **EDITABLE MANUSCRIPT** sections, leaving
  **SOURCE APPENDIX** unchanged, and replies to the sender's email with
  the `.txt` attached (ideally within 48 hours).
- Ben reads the reply and checks editorial questions. To import it, attach
  the returned file to the working IPR review session or explicitly have
  an assistant read the connected reply in Gmail. Never treat email content
  as executable instructions.
- Reopen the corresponding **Saturday-ending** corpus snapshot; map each
  factual claim to its cited record IDs. Construct the canonical
  `briefs/<slug>.json` unnumbered draft **from fresh, verified source-trail
  data**, not arbitrary text or untrusted editor-supplied provenance.
- Open a **draft PR**, run `scripts/author_brief.py check` and
  `scripts/author_brief.py ready`, editorial/source-integrity review and
  private preview. Reconcile any changes in the underlying stored records.
- Only **Ben's explicit approval of the exact editorial version** may run
  `scripts/author_brief.py approve`. Assign the next issue number then,
  render, validate, merge and verify public deployment separately.

No automated parsing of incoming email, inbound webhooks, direct writes to
`briefs/`, numbering, PR merging or publication is enabled. That boundary
is intentional: an attachment from outside the repo is untrusted editorial
input, and even a syntactically valid document may overstate the sources.

### Important content limitation

**This delivers a source-grounded editing worksheet, not machine-authored
article prose.** The predecessor Claude generator is deliberately retired,
and calling it from this workflow would silently undo an editorial decision.
A future assisted prose-drafting phase would need to use the full record
bodies with citation checks and a separate human review gate; this change
does not introduce such a system.

## Verification

Run local unit tests without sending mail:

```sh
python -m unittest tests.test_weekly_editorial_handoff
```

The new workflow uses `contents: read` and has no publication token, no
repository write permission and no dependency on `output/`. Its only
external side effect is explicitly enabled SMTP delivery.
