# Exact owner-reviewed Sunday Briefs attachment handoff

## Why this exists

IPR's Sunday workflow generates an unapproved source-cited private thematic
manuscript. For the first October 10 reporting week, the owner must inspect
that exact manuscript **before** Dylan receives it. Merely approving the
reporting week cannot authorize a later model regeneration, because the
narrative or citations may have changed.

This local manual handoff uses the **same original reviewed .txt file**. It
NEVER calls Anthropic, composes a new article, reads a production database,
updates the archive or publishes a Brief. The CLI is dry-run by default.

## Recommended first-pilot sequence

1. After the **October 11, 2026 production update** succeeds, generate the
   private owner-only Sunday preview via the already gated workflow. The owner
   receives the unapproved full-week manuscript attached as a `.txt` file.
   The preview must not be delivered to Dylan automatically.
2. Download and personally review that attachment. Inspect the one-theme
   argument, all production record IDs, typed Japan/Vietnam source notes and
   the immutable source-use receipt. Check original official wording and
   source rights where relevant. Do not approve a draft merely because it
   contains citation IDs.
3. Run the **offline receipt** on the same saved attachment:

   `python -m scripts.sunday_send_reviewed_packet --packet /path/to/owner-reviewed.txt --week-ending 2026-10-10`

   This prints its attachment SHA-256 and length, but never a body excerpt,
   original publisher URL, SMTP recipient or protected environment variable.
   Compare the digest to the checksum reported in the owner-preview message.
4. **Only after owner review**, set these GitHub Actions repository variables
   (or equivalent local environment variables for this manual CLI):

   - `IPR_SUNDAY_OWNER_REVIEWED_WEEK` to `2026-10-10`
   - `IPR_SUNDAY_OWNER_REVIEWED_SHA256` to the exact 64-character lowercase
     digest of the reviewed attachment

   These variables attest **owner intent**; they do not independently prove
   that factual/source-language/source-reuse review actually occurred.
5. With your existing SMTP secrets safely configured in your local
   environment and only after you explicitly want to deliver that version,
   run:

   `python -m scripts.sunday_send_reviewed_packet --packet /path/to/owner-reviewed.txt --week-ending 2026-10-10 --send --confirm-owner-reviewed`

   The command compares the exact source file with the human-approved digest,
   freezes the validated bytes in a private temporary copy and supplies
   **those same bytes** to `send_packet` for direct editor-only delivery.
   The copy is deleted after the attempt. No fresh LLM call is made.
   No repository/artifact is written or uploaded.
6. If the manuscript has been edited, regenerated, reencoded, or altered,
   rerun the offline receipt and **review the new exact attachment again**
   before changing the approved digest. Never adjust approval merely to
   bypass a mismatch.

On later days, an October 10 handoff requires an additional explicit
`--allow-historical-send` flag. This prevents an accidental outdated send.
Dates older than the bounded historical review window are refused.

## Security and editorial boundaries

- A local `.txt` with the exact week/header/status and one complete immutable
  source-use appendix is required; symlinks, malformed, duplicate/fake
  boundaries, invalid UTF-8, incomplete Saturdays, large files and an invalid
  reporting date are rejected.
- The command defaults to **no-send**. Sending requires both `--send` and
  `--confirm-owner-reviewed`, matching exact-week/digest approvals and an
  eligible reporting Saturday. There is no scheduled action for this tool.
- An actual manual delivery also refuses local
  `IPR_EDITOR_DELIVERY_ENABLED=true` (old Friday service) or
  `IPR_SUNDAY_EDITOR_DELIVERY_ENABLED=true` (scheduled Sunday service), and
  requires that `IPR_PREVIEW_TO` be a configured owner address **different**
  from `IPR_EDITOR_TO`. This local tool cannot inspect live repository
  variables: before sending, the operator must separately confirm **both**
  GitHub Actions scheduled-delivery settings are disabled. Local unset flags
  are **not proof** that remote scheduling is disabled. The script does not
  configure recipients or disable any workflow.
- The new wrapper uses IPR's existing `send_packet`, including its separate
  recipient check, SMTP credential validation and first-pilot owner/digest
  controls once #262 merges. The direct wrapper does **not** turn on scheduled
  Sunday or the legacy Friday email service.
- SHA-256 pins exact attachment identity, **not** truthfulness, rights,
  source-body fidelity, coherent analysis or the owner's real review actions.
  It never grants publication approval or an issue number.
- CI tests mock SMTP fully, use fixture prose and never contact Claude,
  access email secrets or send any editorial packet.

This delivery mode is a manual bridge for the first Sunday pilot, not a
replacement for a future proper owner-review artifact retention workflow.
