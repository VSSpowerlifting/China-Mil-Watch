# Vietnam Briefs — private-draft citation → source-reviewed publication bridge

## Why this exists

The **model-generated Sunday draft** from PR #203 may use short, attributed
official-source research from Japan and Vietnam. It does **not** establish
that a cited source is reviewed for a published Indo-Pacific Record Brief.
Dylan edits **one coherent draft**, not supplements, but Ben still needs a
source-to-claim and source-use review before approving any published article.

The public Briefs contract already supports individually reviewed,
publisher-hosted Vietnam MPS links (PR #199) via
`core.brief_external_evidence`. The missing connector was a **version-bound
bridge** between the private model research input, the final prose actually
citing the Vietnamese source, and a separate human review receipt.

This PR adds `scripts/bridge_vietnam_reviewed_brief_citations.py`.

## Separate, deliberately non-equivalent states

1. **Private model candidate:** `VN-MPS-1791199100` or
   `VN-MPS-1791199677` in `ipr-private-drafting-evidence/1`.
   Publisher metadata and an unapproved research synopsis are available to
   the model for composing a provisional article. Neither is a production
   archive record. Japan uses its separate `JP-W41-...` IDs.
2. **Actually used editorial citation:** When the *revised structured Brief
   draft* makes an assertion using a Vietnamese article, its prose identifies
   `[External mps-vi:1791199100]`. The normalized publisher identity is
   different from the private writer's model-facing `VN-MPS-...` label;
   the bridge explicitly checks this one-to-one mapping. Mere presence in
   the AI prompt or source appendix does **not** count as an actual citation.
3. **Independent human source review:** Only a human who has checked the
   original publisher page, preserved article version, institution,
   publication date, factual scope, original short analyst summary and
   permissible publisher-link/original-summary source use can complete the
   external citation receipt. A form with all checks marked true does not
   itself prove those checks happened; it is a named, reviewable assertion.
4. **Provisional public Brief citation fragment:** Only when the *exact*
   source URL, headline, publication date, archived commit, content-version
   digest and source identity match may the tool emit `external_evidence`
   entries for a draft. It delegates to the **existing public Briefs
   `validate_external_evidence` contract**. This does not approve or
   number the overall Brief.

A normal Brief still needs **two production-backed live desks** in its
source trail, irrespective of the number of Vietnamese external references.
A Japan or Vietnam research candidate cannot silently satisfy that threshold.

## Real October 10 source-review agenda (still unsigned)

The unsigned worksheet is stored at
`research/vietnam_briefs_candidates/unsigned_2026-10-10_publication_review.json`.
It contains exact metadata, **null reviewer/date/summary/source-use basis,
and eight FALSE checkboxes for each source**. It is NOT an authorization.

### MPS 1791199100 — Vietnam–Turkey security-industry talks

Official original:
https://bocongan.gov.vn/bai-viet/mo-rong-hop-tac-cong-nghe-cong-nghiep-an-ninh-voi-cac-doi-tac-tho-nhi-ky-1791199100

Verify the original title, October 5 publisher date, MPS Minister Lương Tam
Quang's meetings with executives of ICT and ANVI, the stated interest in
security technology, data integration, counter-UAV measures and related
capabilities, and the prospective character of cooperation. **Do not report
a contracted arms deal, delivered capability or completed procurement** unless
another cited primary source independently establishes it.

### MPS 1791199677 — Concordia research and training talks

Official original:
https://bocongan.gov.vn/bai-viet/cu-the-hoa-hop-tac-dao-tao-nghien-cuu-cong-nghe-an-ninh-voi-dai-hoc-concordia-1791199677

Verify the original title, October 5 publisher date, the meeting with
Concordia President Graham Carr, and possible cooperation involving AI,
cybersecurity, data management and training. **The previously cited
memorandum of understanding was with Vietnam's Ministry of Education and
Training, NOT the MPS.** Neither the article nor the review worksheet proves
a new signed MPS–Concordia agreement.

The publisher site's copyright/footer asks users reusing information to
credit the Ministry of Public Security's electronic information portal.
**Attribution instructions are not, by themselves, a verified blanket
license for full-text republication or third-party AI processing.** Keep
individual source-use decisions appropriately narrow.

## Editorial procedure (outside repository)

1. Dylan returns the edited **single manuscript**. Ben reviews the claim,
   compares original Vietnamese publications, and builds the normal
   *draft* Brief sidecar. Add `[External mps-vi:<id>]` only in prose passages
   actually supported by verified Vietnamese sources.
2. Make a PRIVATE copy of the unsigned checklist **outside the Git repo**.
   Delete entries that the final article does not cite; the bridge refuses
   decorative or uncited external references. Independently verify each
   remaining article and its retained capture/content digest. Have the named
   reviewer fill eight checks, exact review date, a short original English
   summary actually checked against the source, and an explicit narrowly
   scoped publisher-link/original-summary use rationale.
3. With a validated exact-week private research packet, the draft sidecar
   and the independently completed private review receipt, invoke:

```sh
python -m scripts.bridge_vietnam_reviewed_brief_citations \
  --draft-sidecar /private/ipr-draft.json \
  --private-research-packet /private/2026-10-10.json \
  --human-source-review /private/vietnam-reviewed-citations.json \
  --out /private/vietnam-external-citation-fragment.json
```

4. The tool outputs a **fragment** with `external_evidence`,
   `publication_approved=false`,
   `final_brief_approval_required=true`, and
   `source_full_text_copied=false`. It neither edits the draft sidecar
   nor imports anything into production. Only an editor should decide whether
   to incorporate the fragment.
5. Validate the *entire* prospective Brief through
   `core.brief_contract.validate_brief` and the standard owner-approved
   publish workflow. The external references may not substitute for a live
   production desk, a review of the actual prose, or an issue approval.

## Security / provenance boundaries

- Never treat signed-looking review JSON as proof of an independently
  checked government source without an actual reviewer. The reviewer must
  be accountable for the attestation.
- No automatic `checks=true` filling. The October 10 template defaults to
  all FALSE, and neither PR #211 nor PR #222 creates real editorial or
  source-use approval.
- The version digest pins the MPS `mps-vi-content-v1` current content version
  in the immutable Git state, **not** arbitrary publisher HTML content.
- The editor's model-sourced synopsis is *not* silently converted into
  `original_summary`. A separate reviewed summary is required.
- No full article body/PDF in the output; URLs and short, human-checked,
  originally worded summaries only.
- No phantom Vietnam production record IDs, desk activation, SMTP send, AI
  text generation, status promotion, issue number or publication.
- No writes into the tracked repository; input/output review artifacts live
  in private temporary/editorial locations.
- The mechanism currently supports the Vietnam MPS family only; Japan's
  publisher-review and publication contract remain a separate workstream.

## CI

```sh
python -m unittest tests.test_vietnam_reviewed_brief_citations -v
```

Synthetic-only, no-network fixtures must prove missing human review,
date/title/URL/version mismatch, citation omission, spoofed domain, false
checks, production-desk substitution, and an attempt to overwrite an
existing review are rejected before a fragment is written. Full offline CI
and tracked DB/output preservation must pass on the exact PR head.
