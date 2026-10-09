# Offline reviewed mixed-desk regional slate (stacked after #303)

**Purpose:** connect the existing owner-HMAC-reviewed numeric production synopsis lane
to independently owner-HMAC-reviewed typed Japan/Vietnam **analyst synopses**, to
prepare a single evidence-grounded *manual* thematic slate.

This feature is **not** enabled in the live Sunday writer or any external-model
interface. It uses the existing validated regional editorial slate contract,
which already supports typed research IDs. It does not add a new journal or a
second published Brief.

## Exact admission preflight for an offline human slate

The function `build_reviewed_mixed_context(...)` performs these checks before
building the evidence manifest:

1. Current full-Saturday regional inventory and existing separately signed,
   numeric production-source review must pass the unchanged
   `core.regional_theme_selector.fixed_context` gate.
2. All typed sources must match the regional HOLD inventory and fresh
   Japan/Vietnam machine historical-state receipts. Source identities,
   preserved historic text commit/digest pins and metadata roster must match.
   An October 6 MOD HTML source is correctly characterized as **metadata only**
   without a preserved publication-day HTML body.
3. The explicit purpose-specific owner decision from #303 must verify with an
   independent owner secret and same fresh source-roster/inventory hash.
4. The caller supplies bytes freshly obtained from each exact approved
   **official publisher source**, and the program checks their SHA-256 against
   the human-signed observed current-edition digest. It refuses a missing,
   extra, changed, non-byte or oversized source. It does **not** capture URLs or
   independently prove the caller obtained authentic publisher bytes: source
   provenance is still a human/operator responsibility.
5. Only the selected, human-written, bounded source synopses and limitations
   join the numeric production evidence. Held sources stay excluded. Mixed
   numeric and typed citation IDs retain their separate lanes, and country
   coverage changes to `reviewable` only for this *private* editorial slate,
   expressly **not** for the production desk registry.

The manual candidate validator intentionally takes the original fresh inventory,
owner-signed review envelopes, machine receipts and operator-provided publisher
bytes again and **recomputes** the reviewed context on each call. It does not
accept a previously generated mutable slate as admission proof.

The result is a strictly validated empty thematic slate, with no AI proposed
themes and no approved lead. The independent
`validate_manual_mixed_theme(context, candidate)` function can test a
human-authored alternative that cites only admitted numeric/typed IDs. It
cannot generate a manuscript, select a theme automatically or change owner
approval status. Single-desk drafts are tagged as requiring a separate public
exception.


## Handoff replay protection

The mixed manual preview now includes the exact SHA-256 of all verified
reviewed synopsis entries (including source-identifying metadata, wording and
accuracy limitations) and both distinct owner-review HMAC digests, plus the
weekly source snapshot and typed HOLD roster hashes. The separately callable
`verify_manual_mixed_preview` **recomputes** the entire candidate preview
against fresh owner-secret verification, source inventory and current publisher
capture bytes. An edited thesis, inserted held source, changed analyst synopsis,
re-sealed owner decision or swapped capture is not silently accepted as the
same editorial evidence packet. A digest is for replay detection only;
**it is not a cryptographic signature or an authorization to dispatch**.

## Security and rights boundaries

This is a source selection and **human brainstorming** boundary. It never
returns raw source capture bytes or publisher article bodies. It does return
the explicit human-reviewed brief synopses, official URLs and source titles
in an **in-memory private context**, so operators must never print it in
public Actions logs or commit it. No private file writer is provided.

A valid owner HMAC authenticates the owner's declaration, not the legal
license or the factual meaning of a publisher's words. Current source captures
do not prove what appeared on publication day. The absence of retrospective
Japan HTML custody and Vietnam MPS's attribution-only footer are not waived.

**Every result has** `model_input_authorized=false`,
`editor_email_authorized=false`, `publication_authorized=false` and
`japan_vietnam_production_activated=false`. No live publisher GET,
scheduled job, SMTP, Anthropic model call, model callback, public page,
source promotion or SQLite mutation is included.

Only after separately reviewing human evidence and source rights should a
future explicitly owner-approved phase consider a single model call on this
reviewed synopsis packet. This PR deliberately has **no dispatch API**.

## Change/merge dependencies

This PR is **stacked on #303**, which introduces the typed owner-decision
HMAC contract. It must not be merged before #303 has passed exact-head
full repository CI and merged into main. #295/#298/#302 source continuity
and human review progress have separate user-controlled merge decisions.
After #303 is merged, retarget/recheck this PR against main, obtain exact-head
focused + full offline CI, and recheck mergeability. No automatic merging.
