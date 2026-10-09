# Mixed regional Briefs: private manuscript review, not publication

This change is a private editorial-review tool built on the existing Sunday
manuscript structure. It is **stacked after #307**, #306 and #304; it does
not add another public journal, replace the scheduled Sunday editorial
writer, invoke an AI model or send a message.

## Inputs and validation

A caller supplies a structured, already-authored *private* manuscript and
all fresh upstream owner-signed thematic selections and source evidence.

- The owner's exact reviewed mixed-desk thematic choice (2 to 10 sources
  from at least 2 desks) must verify again, including model-run HMAC,
  proposal digest, source synopsis HMACs, week and original publisher
  capture hashes.
- The draft reuses the **existing Sunday PROSE_FIELDS and CITED_FIELDS**
  and `validate_manuscript` source/packet guard, so editorial content
  cannot impersonate an appendix, cite unknown numeric or typed IDs,
  fabricate a cross-desk source basis, or rebrand back to PLA Watch.
- For typed research, the draft's editorial_focus must exactly match the
  original owner-signed focus and fit the established Sunday writer
  length contract (20–200 characters). A longer valid thematic thesis
  requires another explicitly human-approved focus to fit the old
  manuscript contract, rather than silent truncation.
- Section citations contain separate lists of numeric production records
  and typed *private research*, exactly as the existing Sunday writer
  expects. An external ID never becomes a production article ID.
- Every factual section must have at least one offered, admissible cited
  source, and the cross-desk comparison must cite at least two desks.
  Other sections are not forced to reference unrelated sources. Selected
  sources omitted from a draft are reported **uncited**, not described as
  support for its argument.
- An allowed citation can still support a misleading assertion. The
  validator expressly **does not verify claim-level accuracy, independent
  government activity, correct translations, original historical edition
  equivalence or legal reuse permission**. It is a *mechanical and
  structural* evidence check.

## Outputs and confidentiality

`validate_private_mixed_manuscript` returns a metadata-only receipt with
the exact SHA-256 of the supplied draft bytes, an owner-choice HMAC pin,
week, signed source synopsis digest, per-section numeric/typed citations,
represented desks and selected-but-unused source IDs. It does NOT return
any draft prose, official article body, model output, full publisher
capture, HMAC secret or rights declaration.

`render_private_mixed_manuscript_review` returns a **private, in-memory**
human-readable worksheet consisting of the original supplied draft,
section-level citation IDs and **only the selected source metadata,
original titles and official publisher links**. Its source appendix
clearly distinguishes the non-production Japan/Vietnam references from
archived records and flags any selected source that is actually unused.

**Do not print, commit, email or upload this private worksheet to public
GitHub Actions logs, issues, source control or artifacts.** No local
file writer, workflow schedule, email sender, provider API client,
external fetch, production database/site mutation, public issue
publication or manuscript generation routine is provided.

The result is still an **UNNUMBERED PRIVATE DRAFT**, with:
`manuscript_model_authorized=false`,
`editor_email_authorized=false`,
`publication_authorized=false`, and
`production_desk_promotion_authorized=false`.

Future editor delivery requires a separate, owner-explicit release gate
bound to the *exact final manuscript bytes* and its factual/rights
verification. A draft hash is not a signature. The existing Sunday
workflow remains isolated and untouched.

## Test and deployment conditions

All tests use synthetic owner keys, captures and source-use assertions.
Focused offline CI must cover the stacked owner/model choice suites,
the older Sunday writer contract and independent no-SMTP/no-provider/
database-preservation checks. After upstream PRs merge and this PR is
retargeted to main, require **full exact-head repository CI** and
GitHub mergeability before owner-controlled merge.
