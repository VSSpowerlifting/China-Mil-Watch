# Optional Sunday scheduled owner-only manuscript preview

## Purpose and operating sequence

An automated Saturday-ending AI Brief should be reviewed by the IPR owner **before**
Dylan sees it. Previously the Sunday cron job executed only when editor
delivery was enabled. For the first reporting week ending **October 10, 2026**,
the new edition-specific reviewer-signoff and SHA-256 gates would correctly
refuse a fresh scheduled editor send **before** a private owner draft existed.
The only preview path was a manual `workflow_dispatch`.

This change adds a separate **opt-in** scheduled **owner-only** preview. It
does not grant Dylan, the publisher, any shadow desk or the public permission
to use the manuscript.

The job still runs on Sundays at 19:17 UTC (~3:17 p.m. EDT). Its model call
continues to require the completed Saturday window, Sunday's actual daily
successful collection marker, usable China and Singapore full text, permitted
bounded private research, the refreshed Vietnam roster and the three pinned
Japan MOD offer candidates for the October 10 pilot.

## Operator setup

- Ensure repository secret `IPR_PREVIEW_TO` points to **your** private
  address, which must be different from `IPR_EDITOR_TO`.
- In GitHub repository Settings → Secrets and variables → Actions →
  Variables, set **`IPR_SUNDAY_OWNER_PREVIEW_ENABLED=true`** only when
  you explicitly want the scheduled private preview. The code does **not**
  configure it and it defaults to disabled.
- **Do not enable `IPR_SUNDAY_EDITOR_DELIVERY_ENABLED=true` at the same time.**
  The Sunday job fails before any model call if both automated modes are
  enabled. Leave `IPR_EDITOR_DELIVERY_ENABLED` (legacy Friday email) disabled
  if you plan subsequent Sunday editorial delivery.
- On October 11, the scheduled job (if enabled) generates and emails the
  **unapproved .txt manuscript to the owner only**; it does not set
  `IPR_SUNDAY_OWNER_REVIEWED_WEEK` or
  `IPR_SUNDAY_OWNER_REVIEWED_SHA256`, email Dylan or publish anything.
- Review the exact attached argument, record citations, Japan/Vietnam
  source-language notes and source-use receipts. After real review, use the
  separate exact-manuscript manual handoff process (#267) to send Dylan the
  same reviewed bytes. A second model generation is not identical approval.
- `workflow_dispatch` remains available for owner-only private previews and
  historical checks; no scheduled preview setting can bypass its explicit
  manual inputs.

## Fail-closed behavior

If the Sunday production marker has not been committed before cron fires,
the job refuses to generate or send anything. It does **not** retry itself
later or treat a Saturday snapshot as completed Sunday data. An operator may
use the manual owner-only preview after the daily collector succeeds.

If both scheduled editor delivery and owner preview flags are true, the
preflight refuses both modes, regardless of preview/recipient secrets.
The scheduled preview route has no editor-send intent and the window resolver
returns `IPR_SUNDAY_SHOULD_SEND=false`. The final CLI runs with
`--preview-to-owner`, never `--send`.

GitHub Actions logs and PR tests contain no model output, owner manuscript,
SMTP password, archived publisher text or attachment. The workflow remains
read-only; it creates no persistent public artifacts.

**This is a routing safeguard, not proof of source accuracy or publication
authorization.** Real email occurs only when the owner preview flag has been
explicitly enabled and the Sunday model/source checks pass.
