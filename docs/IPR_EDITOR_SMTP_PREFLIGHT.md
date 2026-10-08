# IPR editor email authentication preflight (no send)

Use this manual-only workflow **before** spending another Claude API request
to test delivery of Indo-Pacific Record's Friday Briefs worksheet.

## How to run

1. Keep repository variable `IPR_EDITOR_DELIVERY_ENABLED=false` while the
   editorial-writer validation incident is under investigation.
2. Open **Actions → IPR Editorial SMTP Authentication Preflight (No Send)**.
3. Choose **Run workflow**, branch `main`.
4. Read the job's final line:
   `IPR Gmail SMTP authentication successful. Recipient address syntax valid.`

The workflow reads the existing repository secrets `IPR_EDITOR_TO`,
`IPR_SMTP_USER`, and `IPR_SMTP_APP_PASSWORD`; it requires the Google-generated
16-character app-password format. It validates both email address fields
and opens a secure connection to Gmail SMTP port 465 to authenticate the
sender. It does **not** send a test message, write a draft, access Anthropic,
alter a repository variable, publish, number a Brief, or log identities,
passwords, or draft contents. Nothing is scheduled.

## What this confirms (and does not confirm)

A green result confirms network connectivity to Gmail SMTP, sender
authentication with the configured app password, and the recipient
address's **syntax** at the time of the run. It does not prove Dylan owns
the destination address, that messages from the sender will arrive, or that
the content of a future draft meets editorial checks. Those require a
separate, owner-authorized delivery test.

If SMTP login is refused, verify that `IPR_SMTP_USER` is the same Google
account that generated `IPR_SMTP_APP_PASSWORD`. Never paste the password
in issue comments, chat, or Actions logs. Keep scheduled delivery disabled
until both the live drafting path and the recipient-facing email test pass.
