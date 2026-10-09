# Sunday Japan research must actually reach the unified AI writer

## Problem

The merged Sunday workflow refreshes Vietnam MPS evidence from the latest verified
shadow state before calling Anthropic, and it strictly enforces October 10
Vietnam archived-source completeness. Until this change, however, **the same
workflow could still run with zero Japan sources** if the Japan rows disappeared
from the scratch private research packet. Merely validating the static JSON
schema does not establish that Japan was truly offered to the model.

## Solution

Immediately after Vietnam refreshes the temporary exact-week private packet and
before the one-theme manuscript scaffold and Anthropic call, a read-only
`scripts.sunday_japan_offer_gate` preflight re-reads that **actual selected
scratch packet** through the existing `load_editorial_evidence` validator.

For the first week ending **Saturday October 10, 2026**, require all three
expected Japan MOD research identifiers (`JP-W41-01`, `JP-W41-02`,
`JP-W41-06`) AND at least one Vietnam MPS research candidate. Missing, changed,
duplicate, wrong-week, malformed or falsely authorized records stop the workflow
before LLM or SMTP. The separate current MPS validator still enforces full
first-week Vietnam archival parity. The separate Japan immutable-source
attestation (#242) concerns original shadow-source verification and is **not
replaced** by this simpler model-offer check.

For subsequent Saturdays, an empty Japan packet does not block a China/Singapore
or Vietnam-supported Brief, but it emits an explicit
`no_japan_candidate_available_not_official_silence` statement and GitHub
warning. Future-week Japan absence cannot be represented as positive proof that
Japan had no official activity. The author can still choose a coherent single
theme and can legitimately cite none of the offered Japan sources if irrelevant:
**offering evidence is not forcing model citation**.

The preflight prints only typed IDs/counts/status, never original bodies,
Vietnamese or Japanese research synopsis text, official publisher URLs or
editorial approval. It does not enable production eligibility of Japan,
source-use rights, independent human translation verification, editor sending,
numbering or publication.

## Checks and relationship to open branches

Focused tests exercise the exact real October 10 six-source JSON fixture and
simulate omitted Japan, omitted Vietnam, duplicate/approved/faulty packet,
wrong-week input and valid later-week zero-Japan research. They also inspect the
live workflow for correct ordering and forbid Anthropic/SMTP secrets in the
pre-model step. Full offline CI remains a merge prerequisite.

The change intentionally avoids source-use receipt (#246, merged),
production-corpus gate (#252, open), model composer, publishing and external
source review (#241/#242). The one shared edit to
`.github/workflows/sunday_briefs_editorial_handoff.yml` must be reconciled with
#252 prior to merging if it lands first.

First real owner-only preview still requires the Sunday October 11 successful
production update, generated manuscript and source-by-source human review. No
mail to Dylan is authorized by this milestone.
