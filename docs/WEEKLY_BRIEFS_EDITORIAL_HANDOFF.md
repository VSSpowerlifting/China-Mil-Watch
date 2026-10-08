# Friday automatic Indo-Pacific Record Briefs draft → Dylan

This is an **editorial drafting and email handoff**, NOT a publishing workflow.
The archived "The PLA Watch" generator remains retired. This workflow uses a
separate source-bounded assisted writer for **Indo-Pacific Record Briefs**.

## Friday workflow

1. At **20:17 UTC on Friday** (~4:17 p.m. EDT / 3:17 p.m. EST), resolve
   Friday's date in New York, and the **following Saturday** as the normal
   Brief's week-ending identifier. GitHub scheduled jobs may start late.
2. Read **only records dated Sunday through Friday**, using the repository's
   read-only production-DB accessors and eligible production-backed desks.
   This does not include Saturday's unseen publications; later approval
   requires a refreshed, complete-week source-trail and review.
3. Create a temporary *unnumbered* scaffold with per-desk coverage statistics
   and original record-level links. Exclude records explicitly screened
   not-selected (as the governed authoring scaffold already does).
4. From full-text-bearing eligible records, choose up to **14** bodies, with
   up to two per desk before filling by the existing model's triage ranking.
   Each body is capped at 3,800 characters. Short/unavailable bodies are
   not represented as full evidence.
5. With `ANTHROPIC_API_KEY`, request **one** structured Claude draft using
   the existing `claude-sonnet-4-6` model. Return a working title, dek,
   development, flowing article sections, a cross-desk comparison, and
   editorial follow-up questions. Require IDs of actual supplied source
   records for every analytical section, including from **two different
   desks** for the cross-desk section. This proves ID membership only:
   it does NOT mechanically certify a claim's accuracy.
6. Compose a single editable `.txt` with the prose, section-level record
   IDs, source URLs and untouched original source-trail metadata. Every
   packet is conspicuously **PROVISIONAL THROUGH FRIDAY / UNAPPROVED**.
7. If **delivery is enabled**, email Dylan the `.txt` attachment. If the
   API key is missing, evidence is insufficient, the API fails, or source
   IDs/sections fail the schema gate, **no email is sent**.

The scheduled job is skipped entirely until the owner enables the
`IPR_EDITOR_DELIVERY_ENABLED` repository variable; this also avoids paying
for drafts that will not be delivered. Manual runs can still exercise writing
while the variable is disabled, but will **not send an email**.

## Credentials — rotate before enabling

The custom password disclosed in the conversation must NOT be used as an
SMTP credential. In particular, a Gmail app password is a **Google-generated
16-character code**, not an arbitrary string or an account's ordinary password.
If it was an account password, change that account password; revoke and
regenerate any exposed app password. Never place a password in git, ChatGPT
messages, PR comments, issues, workflow logs, or documentation.

In **Settings → Secrets and variables → Actions** create/update secrets:

- `ANTHROPIC_API_KEY` — existing Anthropic key used by the daily analysis;
- `IPR_EDITOR_TO` — Dylan's confirmed recipient email;
- `IPR_SMTP_USER` — a Gmail sender account controlled by Ben;
- `IPR_SMTP_APP_PASSWORD` — freshly generated 16-character **Google app
  password** for that sender account. Some managed school accounts do not
  support app passwords; use an eligible Gmail account if needed.

Do NOT set the ordinary Google account password as the app password.

## One-time activation

1. Merge the reviewed PR with green checks.
2. Rotate the disclosed credential and update the GitHub secret with the
   fresh Google-generated app password. Check that the other secrets exist.
3. In Actions, manually run "Friday IPR Briefs Automatic Draft to Editor" with
   `send_email=false`. Inspect the run for success; this **will use** the
   Anthropic API but will not send email.
4. Create **repository variable** `IPR_EDITOR_DELIVERY_ENABLED=true`
   only after the above checks. Run the workflow manually with
   `send_email=true` for one authorized test delivery. Manual sends for
   the same week can duplicate emails.
5. Leave the variable on for the following Friday cycles. The workflow
   itself neither changes GitHub repository secrets nor enables this variable.

Unapproved manuscript packets are **not uploaded to public Actions artifacts**
or committed to the public repository. The temporary runner directory is
removed after the job completes. The workflow token is `contents: read`.

## Dylan's reply → verified Brief

- Dylan edits the full prose and replies with the `.txt` within the agreed
  editing window. No knowledge of GitHub or Python is necessary.
- Ben can attach the returned document to an IPR review session or request
  review of the connected Gmail reply. Email content is treated as
  **untrusted editorial input**.
- After Saturday, reload the final complete-week corpus and reconcile every
  factual claim and record ID; re-evaluate late Saturday source developments.
  The Friday scaffold is **not** a ready-to-approve Saturday edition.
- Construct the native unnumbered `briefs/<slug>.json` sidecar using fresh
  provenance. Open a draft PR and run
  `scripts/author_brief.py check`, `scripts/author_brief.py ready`,
  source-integrity editorial review, and private preview checks.
- **Only Ben's explicit authorization of the exact resulting prose** can
  trigger `scripts/author_brief.py approve`. Numbering, merge, render and
  actual public deployment verification happen separately.

No incoming-email listener, automated publishing, PR creation from email,
numbering, owner-approval substitution, or automatic deployment is enabled.

## Checks

```sh
python -m unittest tests.test_weekly_editorial_handoff tests.test_weekly_briefs_auto_writer
```

These tests are offline and mock SMTP/API calls. Verify the complete repository
offline checks, source contract and artifact non-mutation before merging.

## Operational limitations

Friday is **early**: Saturday coverage must be reconciled before final
approval. The writer's 14 evidence records and per-record body limits are
a cost/quality guardrail, not an assertion that all relevant publications
were considered. Model-cited record IDs ensure links can be audited but do
not prove the prose faithfully describes the full records. Neither the
automated draft nor the email is an approved IPR Brief.
