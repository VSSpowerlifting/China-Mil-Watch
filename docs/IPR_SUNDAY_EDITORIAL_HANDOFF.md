# Sunday IPR Briefs — full-week draft to Dylan (staged migration)

## Operating schedule

The new, **separately gated** Sunday workflow is designed for this cycle:

- **Sunday at 19:17 UTC:** approximately 3:17 p.m. EDT or 2:17 p.m.
  EST. This is a best-effort GitHub Actions schedule, not a guaranteed
  clock-time commitment; Actions can start late.
- **Sunday before any Claude call:** require the main branch's existing
  .github/state/last_daily_run_date.txt to equal **today's Sunday date in
  New York**. That state marker is written only after the daily production
  pipeline/validation has succeeded. A green daily workflow that skipped
  collection is NOT sufficient by itself.
- **Sunday afternoon after that gate:** read the stored official-source
  corpus dated Sunday through **Saturday inclusive**, select a maximum of
  10 validated full-text bodies across at least two live desks, compose
  source-cited full prose with Claude Sonnet 4.6, validate the actual
  record IDs and per-section prose, and email Dylan one editable text file.
- **Monday 8 p.m. Eastern:** Dylan replies to the original message with
  his edited text file attached. He may reply early, or tell Ben promptly
  if he cannot meet the deadline. This is a turnaround target, not an
  automatically enforced rejection of late editorial work.
- **Tuesday:** Ben asks ChatGPT to find Dylan's reply in the connected
  Gmail account, inspect the attachment and compare against the original
  (see scripts/validate_editorial_return.py). Ben independently checks
  that cited source bodies support claims and that the week is sufficiently
  covered.
- **Wednesday target:** Ben may authorize final prose, the native
  unnumbered briefs/<slug>.json sidecar, approval, numbering and release
  through the existing governed workflow. Nothing publishes automatically.

## Important: full week != exhaustive source capture

Saturday has elapsed and Saturday-dated archived records may be included.
The daily state marker proves a **successful Sunday production pipeline**,
not that every government website has published and been captured by Sunday.
Late-collected/backdated documents, source outages and unverified
translations require additional human editorial judgment. The system does
not assert a complete global news survey or infer silence from a missing
record.

## Safe migration from the working Friday service

The **existing Friday workflow remains unmodified**. Do not activate both
delivery services at once.

1. Merge this PR only after focused tests and complete PR CI pass.
2. On **Actions**, manually run **Sunday IPR Briefs Full-Week Draft to Dylan**
   on main with **Email Dylan unchecked** and an explicit past Saturday
   (for example 2026-10-03). The Sunday workflow will use the Anthropic
   API for this preview, but will not email Dylan. No public article
   artifact is uploaded.
3. If the preview passes, set existing repository variable
   IPR_EDITOR_DELIVERY_ENABLED to **false**, disabling the Friday
   automatic sends.
4. Set the *new* repository variable
   IPR_SUNDAY_EDITOR_DELIVERY_ENABLED to **true**, enabling the Sunday
   workflow. If the old Friday variable is still true, the new Sunday
   code **refuses email**, even when triggered manually.
5. On the next Sunday, check the daily update and Sunday handoff jobs.
   Do not manually send another copy of the same week unless you
   explicitly want a duplicate and have coordinated with Dylan.

For manual previews, leave the historical date blank to select the latest
reached Saturday. On Sunday, that particular Saturday cannot be previewed
until Sunday's daily success marker exists. Older week previews are allowed
without Sunday's marker, but **manual email** outside the current Sunday
requires both the separate historical-send checkbox and the Sunday delivery
variable. Full-week generation for an unfinished Saturday is refused.

If Sunday collection is incomplete or the GitHub scheduled job starts on
Monday, the automatic job **fails closed**: no Claude cost, no email. The
operator can rerun manually after examining the now-current corpus and
authorizing a historical send. A small missed dispatch is preferable to
sending Dylan a misleading or incomplete edition.

## Gmail reply intake

Dylan's reply goes to the SMTP sending account because the email uses its
address as Reply-To. The ChatGPT Gmail connector can find and read the
reply and attachment **only if that particular mailbox is connected**.
Currently the owner intends to connect benyang0313@gmail.com; do not
assume access or claim an automated inbox listener is active.

Neither this PR nor the Gmail connector automatically polls Dylan's
inbox, imports the reply into GitHub, prepares a final Brief, assigns an
issue number, approves editorial text or publishes the site. Ben must
explicitly request and authorize subsequent actions. The original sent
text file should remain accessible privately, since the return validator
requires both the original and the edited versions.

## Permissions and secrets

This is a **new, manual-disabled-by-default** workflow. The only new
configuration needed for scheduled sending is the repository variable
IPR_SUNDAY_EDITOR_DELIVERY_ENABLED=true. It reuses the existing
ANTHROPIC_API_KEY, IPR_EDITOR_TO, IPR_SMTP_USER and
IPR_SMTP_APP_PASSWORD secrets. No plain passwords, inbox credentials,
unpublished article artifacts, source DB changes, Git writes, or
publication rights are added.

The existing GitHub Actions token is contents: read. Automated writing
uses a private runner temporary directory; invalid model output aborts
without SMTP delivery. No automatic retries are made after network errors;
invalid completed drafts may undergo one bounded correction attempt.
