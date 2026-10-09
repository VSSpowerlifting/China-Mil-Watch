# First Sunday: owner-reviewed draft before Dylan delivery

## Reason for a separate release control

The original Sunday workflow can be enabled with
`IPR_SUNDAY_EDITOR_DELIVERY_ENABLED=true`. That flag is a broad scheduling
control. On **Sunday October 11, 2026**, if the October 11 production marker
were present, it could directly send the unapproved manuscript for the week
ending **Saturday October 10** to Dylan without evidence that the owner had
seen the private draft first.

The first pilot has an intentional extra owner-review stage. Turning on a
generic schedule must **not** silently act as consent to skip that stage.

## Exact-edition owner acknowledgement

For the reporting Saturday `2026-10-10` only, any automated or manual
**Dylan/editor delivery** requires the additional GitHub Actions repository
variable:

`IPR_SUNDAY_OWNER_REVIEWED_WEEK=2026-10-10`

The value must match byte for byte. Blank, `true`, an earlier week or a
future week does not authorize delivery. This variable is controlled by the
repository owner through GitHub Actions settings after personally inspecting
the source-linked owner-only preview, checking citations, deciding whether the
thematic argument is supportable, and specifically approving **editorial
handoff**. It is a human acknowledgement, **not independent cryptographic
proof of the preview or any source-rights authorization**.

**Exact manuscript identity is a separate, stronger requirement.** The first
October 10 Dylan send also requires GitHub Actions variable
`IPR_SUNDAY_OWNER_REVIEWED_SHA256` to be the **lowercase 64-character SHA-256**
of the precise original `.txt` owner-review attachment. The owner-only preview
email includes that hash for audit. When sending, IPR hashes the exact bytes
it is about to attach and refuses email unless both the week variable and
attachment digest match. The Sunday date resolver first refuses a missing,
uppercase, malformed or unset SHA-256 setting **before the AI request**, so
the system does not spend on a manuscript it already knows cannot be sent.
The final SMTP guard still compares the actual reviewed attachment bytes. A
changed citation, sentence, appended record, research caution or model
regeneration changes the hash and forces review again. This prevents interpreting an approved **week** as approval of a
different **manuscript**. This is not proof that the owner actually performed
the human review; only the owner can affirm that fact.

**Operational note:** triggering the automated writer again generates a
**new draft**, so it should normally fail the exact-file check even after
the preview has been approved. For this first pilot, the safest editor handoff
is for the owner to manually forward the **same reviewed attachment** to Dylan,
rather than ask a second AI run to recreate an already approved text. Do not
enable automated editorial delivery expecting it to reuse the email attachment;
the workflow has no persisted private manuscript artifact and will not
silently treat a different draft as approved.

This exact-edition gate does not itself enable email. The existing
`IPR_SUNDAY_EDITOR_DELIVERY_ENABLED` master switch and the separate Friday
service exclusivity gate remain mandatory. It does not alter publisher reuse
permissions, human accuracy review of Japanese/Vietnamese wording, the
approved/numbered Brief publication process, or downstream editorial review.

## Unsent owner preview still works

On or after October 11, once the same-Sunday production update has succeeded,
run `sunday_briefs_editorial_handoff.yml` manually with:

- `reporting_saturday=2026-10-10`
- `send_email=false`
- `preview_to_owner=true`
- `allow_historical_send=false`

Owner previews use only the separately configured owner address, never Dylan.
They are **not** blocked by the owner-reviewed week or digest variables and do
not set either. Both variables can be set only manually after inspecting the
exact attachment. Never enable either simply because the preview was sent.

If an unreleased send is attempted, `resolve_sunday_handoff` refuses it
before the model call. The handoff CLI separately rejects `--send` before
reading research or writing the attachment. Finally, `send_packet` validates the exact-reviewed SHA-256 and refuses
a direct SMTP call even when another caller bypasses the CLI. A historical
October 10 replay remains subject to the same owner-review requirement plus
the existing historical-send override.

## After the pilot

Other reporting Saturdays retain the existing scheduling model; this change
does not introduce a permanent requirement to manually approve every weekly
editorial draft. Any future owner-first process can be designed separately,
with a clearer per-edition approval log rather than overloading this pilot
exception.

## Evidence

The focused CI suite covers first-Sunday scheduled send rejection, manual
historical replay, valid exact-edition acknowledgement, no-send private
preview, attempted direct `send_packet` bypass, early CLI rejection, and
workflow variable propagation. It makes no live Anthropic or SMTP calls.

This PR overlaps the Sunday workflow updated by #252 and #258; if either
merges first, this branch must be reconciled and its exact-head CI rerun.
