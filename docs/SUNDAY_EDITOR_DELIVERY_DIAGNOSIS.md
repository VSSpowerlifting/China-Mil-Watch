# Sunday editorial delivery diagnosis (read-only)

This operator check addresses the October 11, 2026 failure in which the
GitHub Actions list contained NO Sunday editorial handoff run, despite the
production success marker and a successful independent Vietnam research audit.

## Proven, not inferred

- The existing production marker for October 11 and Vietnam audit success
  do NOT establish that the Sunday editor workflow was invoked.
- No `sunday_briefs_editorial_handoff.yml` run appeared in Actions during the
  observed period after its 19:17 UTC cron. Whether its workflow was disabled
  or GitHub simply did not dispatch it remains UNVERIFIED.
- The first October 10 reporting edition was delivered by a separate
  owner-directed Gmail send. Never retry that edition automatically.
- PR #397 changes future scheduled dispatch intent; no YAML edit can
  guarantee GitHub schedules are invoked or that SMTP receipts exist.

## Run read-only diagnosis

After the observing script is merged, select **Actions →
IPR Sunday Editorial — Read-Only Delivery Diagnosis → Run workflow**.
It checks GitHub's official workflow state and the latest 30 scheduled run
metadata records, along with the checked-out main daily marker.

Equivalent command from a repository checkout:

    GITHUB_TOKEN=<private Actions read-only token> \
      python -m scripts.audit_sunday_editor_delivery --live \
        --repo VSSpowerlifting/China-Mil-Watch \
        --marker-file .github/state/last_daily_run_date.txt

The token is NEVER printed, sent to any non-GitHub host or persisted.
The GitHub Actions manual diagnostic uses its limited `actions: read`
and `contents: read` token. It does not call Anthropic, modify files,
trigger a workflow or send email.

For deterministic offline regression:

    python -m unittest tests.test_sunday_editor_delivery_audit -v

The CLI also accepts `--runs-json /private/github-snapshot.json` plus
an offset-aware `--now-utc 2026-10-11T21:00:00Z`. Do NOT pass an
unsupported source transcript or public/private manuscript as the input.

## Interpret the result

- `WORKFLOW_DISABLED`: GitHub explicitly says workflow isn't active.
  Re-enable in GitHub Actions settings and independently validate the
  intended schedule. Never silently flip it in code.
- `NOT_DUE` or `WITHIN_SCHEDULER_GRACE`: the expected scheduled UTC
  trigger has not arrived or is within 90 minutes. No send action justified.
- `MISSING_SCHEDULED_RUN`: no Sunday `schedule` event appears after
  the 90-minute grace. GitHub may have delayed/dropped dispatch; the
  diagnostic cannot prove why. Check Actions UI and account/workflow state.
- `WORKFLOW_IN_PROGRESS`: there is a Sunday run but no completion yet.
- `RUN_SKIPPED`: inspect job-level condition and workflow settings.
- `RUN_FAILED_OR_CANCELLED`: inspect the failed job step and source,
  LLM or SMTP gates, without copying any unpublished manuscript into logs.
- `MULTIPLE_SCHEDULED_RUNS_NEED_REVIEW`: potential duplicate; inspect
  job history and actual Gmail Sent mailbox before authorizing any retry.
- `RUN_SUCCEEDED_EMAIL_UNCONFIRMED`: GitHub reports success ONLY. Read
  the actual owner sending mailbox's Sent folder to establish the exact
  reporting week, editor and attachment; not a confirmed delivery receipt.

The `collection_marker_verdict` checks same-Sunday source freshness only
when the audit runs on that same New York-local Sunday. On later days, the
current tracked daily marker cannot attest to historical Sunday collection.
The scheduled cron is permanently 19:17 UTC; it shifts from roughly
3:17 p.m. EDT to 2:17 p.m. EST. The expected reporting week ends Saturday.

## Safe recovery, not blind retries

If the Sunday run is missing or failed, DO NOT introduce a second send cron,
retrigger model generation blindly, or assume a successful Actions workflow
proves Gmail accepted the message. A previous attempt may have reached SMTP
but crashed before GitHub recorded its result. The owner's separate Sunday
delivery watch can independently inspect connected Gmail and alert. Check
the Sent receipt first. If it is absent or ambiguous, mark delivery
uncertain; prepare a deliberate owner-approved replacement, with a
week-specific idempotency ledger, as a later reliability phase.

This R1 check has **no SMTP/Gmail connection**. It does not implement exact
mail-delivery semantics or claim publication approval; both remain separate
in issue #399. No source, model, desk or publication permission changes.
