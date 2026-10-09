# Typed Japan/Vietnam research: unsigned human review progress

Follow-up to [Issue #271](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/271).

The six-source human review worksheet is an *unsigned* operator template.
This new pure offline validator compares a manually edited copy of that
worksheet to an independently regenerated version derived from the **current
read-only weekly inventory** and the exact validated research rows.

It checks that source IDs, URLs, dates, historical state commits, source
digests, roster identity, private-only scope, unsigned template SHA and
authorization fields have **not** changed. Human review fields may be filled
with bounded text and three-state checklist values (true/false/null). It
counts which source checks are missing and whether all entries were filled.
It does not include any user-entered review prose, original article bodies,
publisher URLs, author identities or source synopses in its result.

Call in an operator-controlled private Python process after independently
obtaining fresh inventory and validated research rows:

    from core.regional_typed_review_progress import evaluate_progress
    result = evaluate_progress(edited_worksheet, fresh_inventory, research_rows)

**Interpretation:** "reported_complete_but_unsigned_not_admitted" means the
operator *asserted* completion of every worksheet entry. It is not an
independent factual-source check, a rights grant or a signed use authorization.
An absent historical Japan MOD HTML original cannot be fixed with a checkbox,
nor does a Vietnam MPS attribution instruction settle retention/AI rights.

The existing, bounded Sunday owner-preview writer may separately offer short,
unapproved Japan/Vietnam research notes into its *provisional private* drafting
model under its established explicit research-offer rules. This does not make
those records production sources or authorize Dylan delivery or publication.

The newer **regional thematic selector** instead accepts owner-HMAC-reviewed
**numeric production** analyst synopses. Typed Japan/Vietnam research remains
on HOLD in that regional selector until a later separately approved
publisher-version, rights, reviewer-signature and source-use admission gate.
This progress module cannot sign or bridge to that selector.

No CLI, schedule, publisher fetch, model call, SMTP, new workflow dispatch,
database/site mutation, public numbering or publication action is introduced.
