# Regional thematic proposals — private model-assisted editorial slate

**Stage 3B of #256.** Experimental, opt-in and owner-only. This is a
private *alternative-theme research suggestion* product, not a published IPR
Brief, an all-desk model report, a replacement for Sunday's writer, or a new
source-rights authorization.

## What the engine can and cannot infer

1. It requires the complete exact-week (Sunday–Saturday) read-only production
   inventory with the successful **following-Sunday daily-update marker**. An
   incomplete week or failed collector-health gate cannot produce suggestions.
2. It requires the **separately signed manual source-review docket** from
   `scripts/regional_reviewed_evidence.py`. It rechecks that owner's HMAC
   against the *freshly re-inspected* SQLite inventory before any model call.
   That docket authorizes only a bounded set of human-written, source-attributed
   **private analyst synopses**. An unsigned JSON file or a source ID is not
   permission to transmit publisher body text.
3. It transmits at most **20** explicitly reviewed source synopses. Original
   article bodies, machine-translated full text, unverified Japan/Vietnam
   shadow synopses, and any unreviewed production records are excluded.
   The model sees which declared desks were not supplied with reviewed notes,
   but no source can be fabricated, promoted, or described as institutionally
   inactive because a desk did not contribute.
4. A single bounded model tool call requests **zero to three** defensible
   thematic alternatives. Each candidate must identify actual reviewed
   numeric record IDs, the thesis, what happened this week, limitations,
   counterinterpretations, related topic threads, and five transparent
   *nonbinding* 0–5 rubric assessments. A provisional best option can be
   ranked, but choosing **no lead** is valid when evidence is weak. No forced
   country quotas or artificial regional coordination.
5. The program, not Claude, assembles desk coverage and the allowed source
   manifest. It then validates the entire proposal against the strict
   `ipr-regional-editorial-slate/1` schema; invented source IDs, unreviewed
   desks, more than three themes, changed authority flags, or a malformed
   result **fail closed**. Source-ID and structural validity do not independently
   verify a model's factual interpretation.
6. Results include every model-eligible numeric ID and a reviewer-facing
   candidate map with represented desks, heuristic score, and a flag when
   a **single-desk theme would need the separate numbered-Brief exception**.
   Publication approval, Dylan email, issue numbering, scheduled delivery,
   canonical Brief output and production SQLite are **not performed**.

## Manual private operator path

Prerequisite: complete the review steps in
`docs/REGIONAL_PRIVATE_SOURCE_REVIEW.md` and keep the owner-held HMAC key
outside GitHub, CI and all tracked files.

To inspect what a model *would* receive (no network or billable call):

```bash
python scripts/regional_theme_proposals.py prompt-review \
  --week-ending 2026-10-10 --as-of 2026-10-10 \
  --review-local-day 2026-10-11 \
  --signed-review /private/editor-signed-docket.json \
  --out /private/editor-prompt-review.json
```

Only after independently reviewing that prompt, use an interactive private
terminal with an explicitly configured `ANTHROPIC_API_KEY` to authorize
**one** paid model call (no retries, one typed approval phrase):

```bash
python scripts/regional_theme_proposals.py model-propose \
  --week-ending 2026-10-10 --as-of 2026-10-10 \
  --review-local-day 2026-10-11 \
  --signed-review /private/editor-signed-docket.json \
  --allow-private-paid-model \
  --out /private/editor-thematic-slate.json
```

The paths `/private/` are placeholders for an existing **private** directory
outside the repository. Both output modes refuse an existing file and create
mode 0600 files, without uploading artifacts. Neither may run unattended:
each prompts for the owner review key; `model-propose` additionally requires
an exact confirmation phrase. Both will **refuse** operation before the
successful October 11 production collection marker has been verified.
No actual source has been reviewed or privately transmitted as part of this PR.

## Important research limits

- An official announcement is evidence that an issuer *said something*;
  not proof the initiative happened, procurement was completed, or purported
  coordination occurred. Publication dates are not event dates.
- Cross-desk conclusions require human reading of original documents and
  editorial rebuttal of plausible alternative explanations.
- Publisher version checks and source-use boundaries depend on actual human
  review. The HMAC binds the reviewed packet, but is not third-party attestation
  or independent fact-checking.
- Japan and Vietnam stay unapproved research-lane candidates until independent
  shadow collection integrity/source-use checks are verified. They are not
  quietly reclassified as production by the regional selector.
- This selector cannot write a standalone or numbered Brief, or override
  Sunday's current two-desk rule. The later **Phase 3C** integration must
  explicitly reconcile one-desk exceptions and compare the chosen theme against
  the Sunday full-text record selection and cited source-use receipts.
- The complete all-desk inventory remains a separate *internal research
  review*; at most 20 synopses are offered to the selector. This distinction
  must remain visible to an editor reviewing apparent omissions.

No model secret is present in the GitHub Actions focused tests; all model
interactions in tests are injected mocks, with explicit failure-path assertions.
