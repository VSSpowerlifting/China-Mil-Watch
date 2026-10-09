# Owner-authorized mixed regional theme proposals — stacked on #304

This is the proposed *private model triage* follow-on to the offline mixed
source-and-manual-slate integration in #304. It is **not** the existing
scheduled Sunday writer and does **not** create another public publication
component.

## Evidence boundaries

The separately reviewed production and typed Japan/Vietnam research
synopses first pass the exact source/HMAC/current publisher-capture
verification implemented in #303/#304. Only those synopses and their
metadata enter the proposed model prompt. Source article bodies, PDFs,
publisher-capture bytes and all held research IDs stay outside.

The reviewed source context keeps original country-desk identities, numeric
production record IDs and string typed research IDs. The strict thematic
tool schema is adapted from the existing numeric-only selector to allow
both types of ID. All model responses still pass the existing human
regional-slate structural validator; an LLM cannot create another source,
assert an undeclared country desk is reviewed, or grant publication rights.

The model prompt:
- explicitly marks every issuer title, URL, source metadata field and
  analyst synopsis as **untrusted data, not instructions**;
- requests 0–3 grounded alternatives with abstention allowed;
- preserves source-attribution, chronological and implementation limits;
- retains the existing five weighted, nonbinding editorial criteria;
- distinguishes private single-desk candidates from publishable Briefs.

## Per-run owner authorization

The **default unsigned request** returned by
\`make_unsigned_model_request\` has
\`owner_approved_private_model_call=false\`. It binds the exact weekly
metadata snapshot, reviewed synopsis packet SHA, separately signed
production and typed review digests, exact prompt SHA, tool schema SHA,
specified model ID, owner identity, approved-on date and a unique
operator-provided 32-hex run ID.

Only an *owner-operated offline signing environment* should invoke
\`sign_explicit_model_request\`, with \`owner_confirms_call=True\` and a
third independent HMAC secret not shared with the production or typed
review signers. The private callback path \`propose_mixed_themes\` then
requires both this HMAC-signed request AND a direct
\`allow_model=True\` plus a separately injected callable.

The caller re-verifies the signed run authorization, its exact prompt and
reviewed source context **after** the injected callback as well, so a callback
cannot silently mutate shared source or permission objects during execution.

The injected callback receives exactly
\`(private_prompt, strict_tool_schema, signed_model_id)\` and can be
invoked only once **per function invocation**. No provider client or
billing credential is included in this PR; all tests inject an in-memory
mock. The model does not decide the allowed sources, supported desks,
private rights scope, or release eligibility.

**Important replay limitation:** An HMAC-signed request can be submitted
more than once across separate invocations. The run ID and HMAC are
provenance/owner-intent evidence, not a durable spent-token ledger.
Any future operational paid-provider wrapper must independently implement
durable single-consumption, budget and rate controls *before* enabling
live calls. Without that follow-on, this module is not a spending-control
system.

\`preview_authorized_prompt\` returns a privately reviewable prompt and
schema after HMAC verification **without invoking any callback**. Never
commit or print the source-bearing preview in public GitHub Actions logs.

## No publication or automatic owner choice

Results are provisional private model suggestions only. They do not
sign an approved editorial focus, create a manuscript, deliver Dylan's
attachment, publish a Brief, activate Japan/Vietnam production desks,
update SQLite, run scheduled jobs, fetch live publisher pages, or trigger
an email. Every returned model result has
\`publication_authorized=false\` and
\`editor_email_authorized=false\`.

A later independent owner-approved theme-selection handoff must ensure
mixed-ID manuscript citation eligibility, verify source-use rights
again and respect the exact-attachment editorial release controls.
This PR does not silently retrofit the existing numeric-only
\`core.regional_theme_handoff\` or the original Sunday authoring path.

## Merge dependencies

This is deliberately a draft stacked on #304. #303 and #304 must
first merge into main under their exact-head full CI and mergeability
requirements. Then retarget this PR to main, rerun focused and full
repository checks on its final exact head, and obtain a separate owner
merge decision. No real user/model source permissions have been signed;
the tests use synthetic rights claims, keys and bytes.
