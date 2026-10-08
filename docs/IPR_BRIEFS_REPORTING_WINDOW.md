# Friday Briefs reporting-week protection

The IPR Friday Briefs workflow now resolves its evidence window in
**America/New_York**, not simply by picking the last Friday on every run.
This prevents a GitHub Actions job that begins late on a Saturday from
unintentionally sending the *previous* week's provisional manuscript.

## Regular scheduled dispatch

At 20:17 UTC each Friday (~4:17 p.m. Eastern daylight time or ~3:17 p.m.
Eastern standard time), the schedule uses the current New York-local Friday
as its source cutoff. The body and source appendix include candidate records
from the prior Sunday through Friday, and the issue identity remains the
following Saturday. This is a **provisional** manuscript, not full-week
source verification or publication authorization.

A scheduled job that starts **after the end of Friday in New York** refuses
the run before creating a source scaffold, calling Claude, or sending email.
The owner may assess a manual replay later. GitHub can delay scheduled
workflow triggers, and we prefer a visible missed delivery over a silently
misdated delivery.

## Manual dispatch

The Actions "Run workflow" form offers three options:

- **Email Dylan?** Default is unchecked. Checking it is necessary but not
  sufficient for delivery: repository variable
  IPR_EDITOR_DELIVERY_ENABLED must also be set to true.
- **Optional reporting Friday (YYYY-MM-DD).** Leave blank for the most
  recently reached New York-local Friday. To test an older Friday's evidence,
  enter its exact date, such as 2026-10-02. Future dates, non-Friday dates,
  and dates more than about 13 weeks old are refused.
- **Authorize earlier-Friday email.** Default is unchecked. If a manual
  dispatch would email a previous Friday's packet, this must be checked
  **in addition to** Email Dylan and the delivery variable. Preview-only
  tests do not need this permission.

For example, manually testing from Thursday, October 8, 2026 would
naturally select Friday, October 2 as the latest complete cutoff. A
no-email preview is fine. Sending that old packet now requires the explicit
historical-send checkbox. On Friday, October 9, the current-Friday manual
email does not need the historical override.

## What this does not do

It does not automatically recover delayed scheduled runs, deduplicate
manual sends, prove SMTP delivery, certify source content, or validate
Dylan's edits. Repeated manual sends for the same Friday may still deliver
duplicate messages. No tracked source database, Brief sidecar, rendered
output, publication controls, SMTP credentials, or recipient settings are
modified.

The reporting-window check runs **before** reading the source scaffold or
calling Claude. The editor retains authority over source verification,
approval, numbering, and publication. Keep automatic delivery disabled until
the other citation and SMTP validation gates have been tested successfully.
