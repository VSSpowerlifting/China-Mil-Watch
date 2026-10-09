# Mixed regional theme choice: owner-controlled private manuscript planning

This feature turns an evidence-grounded mixed numeric/typed thematic
candidate into a specific owner-selected **private planning focus**. It does
not add another publication series; all eventual work remains within IPR
Briefs' unified editorial system.

This PR is stacked on #306, after #304 and #303. It does not alter the
existing numeric-only Sunday owner-handoff or the scheduled Sunday writer.

## Exact inputs and signing

The pure make_unsigned_theme_choice function takes a fresh regional
source inventory and two independent owner-HMAC source review envelopes,
a separately signed owner-run thematic model request, a previously
validated candidate preview and the current exact official-publisher
capture receipts. All publisher bytes must still match the human-reviewed
digest and the historic machine receipt must reconcile.

checked_mixed_proposal recomputes the entire proposed slate from source
identities, HMACs and current publisher capture bytes rather than trusting
a saved model preview's candidate list, evidence, rankings or flags. It
verifies those candidate claims against the source-bounded slate again.

This proves the supplied proposal matches the reviewed corpus and signed
model-run context, **NOT that the model genuinely produced those bytes**.
The provider result has no separately signed, provider-attested output
receipt; only the editor's explicit choice is authenticated here.

An acceptable owner selection requires exactly one existing proposal slug,
2–10 distinct reviewed source IDs, and source representation from at
least two desks. A single-desk idea needs a separately controlled public
exception and cannot use this default Sunday manuscript planning path.
The signed owner focus contains the thesis, IDs, typed/production lanes,
represented desks, date, upstream model-run HMAC, entire proposal
SHA-256 and original exact weekly + synopsis + source-review digests.

The owner operates sign_owner_mixed_theme_choice in a separate secure
offline context, with owner_confirms_focus=True, using a **fourth**
32-byte-or-longer independent HMAC secret different from the production
source, typed research and model-run signing keys.

verify_owner_mixed_theme_choice rechecks every upstream source, exact
owner-reviewed analyst synopsis, separately signed model request,
candidate structure, selected source and owner choice HMAC before any
private handoff is permitted.

private_manuscript_planning_receipt yields only a metadata-only
planning record with focus, IDs, desk/lane citations and the source/proposal
digests. No raw publisher article, source capture, rights document,
unreviewed research note, or manuscript is copied. No source bodies or
private HMAC secrets should ever enter CI or public issue comments.

## Trust boundaries not solved here

- **No live model or manuscript generation.** This PR does not invoke a
  paid provider or connect the old Sunday writer. Manuscript model use
  would require a *separate* explicitly owner-authorized, source-bounded
  call with a durable replay-and-budget ledger.
- **No Dylan email, publication, production desk promotion, or automatic
  public single-desk exception.**
- Source authenticity and reuse permission still require independent
  original-language human review; HMACs verify owner assertions, not
  legal rights, publisher honesty or edition history.
- The model proposal origin is not cryptographically attested: the owner
  choice explicitly acknowledges this rather than silently equating
  an internally consistent preview with vendor-signed model output.
- An owner choice signature is a signed thematic *planning decision*,
  not an authorization to call AI, prepare/send an attachment or publish.
  A future manuscript handoff requires independent explicit authorization,
  exact attachment SHA, pre-send review and owner approval.
- No new scheduled jobs, network fetch, service account privileges,
  DB/site/output mutations, SMTP or provider API dependencies exist.

Tests use only synthetic captures, source rights claims and mock model
callbacks; no real user signed an editorial selection.
