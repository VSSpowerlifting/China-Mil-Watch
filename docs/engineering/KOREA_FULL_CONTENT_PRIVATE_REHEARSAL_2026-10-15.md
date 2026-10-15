# Korea: full-content private-source rehearsal (October 15, 2026)

**State:** source-version-bound **private rehearsal only**. This phase is
independent of the metadata-only production release PR #670. It does not
enable new public pages, production original-body rows, PDFs, photographs,
translations or automated analytical publishing.

## What the repository can already prove

The Korea shadow collector captures official Republic of Korea Policy Briefing
republications attributed to the Ministry of National Defense. Its source stage
re-verifies the clean archived Git state, stored HWPX against extracted Korean
text, source identity, publisher HTML digest, HWPX digest, exact original text
digest and posted date. See scripts/stage_korea_production_candidates.py.

The publisher's copyright policy
(https://www.korea.kr/guide/copyRight.do) permits attributable reuse of
qualifying **KOGL Type 1 marked text**, but explicitly distinguishes protected
photographs, images and other third-party media. An HWPX attachment is NOT
itself wholly cleared just because a web page carries a text notice. The
publisher's policy also cautions against modifications distorting the
original meaning. Publisher-specific reuse policy and a particular release
notice must be checked independently; a manually supplied JSON claim or
untrusted website assertion cannot prove those rights.

Korea corpus metadata auto-publication standing approval (October 15) is
restricted to URL/date/issuer. It does not authorize body redistribution,
model processing, translations, analysis, or a revised site writer.

## This engineering phase

The fail-closed module core/korea_full_content_rehearsal.py:

1. Refuses other desks/source families and existing editorial-exception rows.
2. Checks the original Korean title and text hashes against the independently
   HWPX-verified stage candidate. Exact source identity, URL, date and captured
   version are pinned.
3. Requires a source-specific KOGL Type 1 text-only observation tied to the
   same publisher HTML SHA. This is **evidence proposed for a rights review**,
   not independent rights clearance or license authentication. Unreviewed or
   overbroad media/attachment permission claims are rejected.
4. Checks a pre-existing machine draft's exact captured source version,
   paragraph-by-paragraph source Korean hashes, complete order, English
   translation labels, and source paragraph citations in each source note.
   This is structural fidelity only. **It does not establish translation
   meaning, factual support for an inference or claim accuracy.**
5. Produces metadata-only HOLD receipts. The optional HTML reviewer preview
   escapes all model/publisher strings, carries noindex and clear unapproved
   labels, and may only be created as a new 0600 file outside the repository
   within an existing owner-only directory.
6. Makes no model requests, invokes no mail tools, and touches no public
   output directory or production database. CI uses *synthetic* records only.

No private Korean source documents, original translations, model drafts, rights
review secrets or human approvals should be added to the public repository,
Actions artifacts, comments, pull request descriptions or CI logs.

## Operational trial, only after private draft preparation

Provision source checkout and input files in a private operator workspace
(outside the public IPR Git worktree), and protect the directory with mode 0700
and private input files with mode 0600. The source checkout is the preserved
shadow/korea-policy-briefing branch, verified by the existing stage verifier.

The source candidate version and hashes must match the output of
stage_korea_production_candidates.build(source_checkout). The rights observation
JSON uses ipr-korea-source-rights-observation/1; the machine draft uses
ipr-korea-machine-source-draft/1. Consult synthetic examples in
tests/test_korea_full_content_rehearsal.py. Do not fabricate actual license
verification by copying those fixture declarations to real sources.

    python -m scripts.rehearse_korea_full_content \
      --source-checkout /private/korea-shadow \
      --source-identity korea-policy:156784297 \
      --rights-observation /private/review/rights.json \
      --machine-draft /private/review/model-draft.json \
      --private-preview /private/review/korea-review.html \
      --explicit-private-no-publish

This operation emits a metadata-only receipt and an unapproved private
source/translation/note comparison. A successful rehearsal is not a green
publication result.

## Actual full-content production launch requirements

These are **not implemented** or authorized by this change:

- An independently controlled, auditable publisher notice validator tied to
  the exact release and extraction/attachment scope, reviewed for reuse,
  transformations and model-processing terms. The pilot does not declare
  KOGL permission for all future MND releases.
- Actual Korean-language quality review for selected source versions,
  translation semantic audits for numbers, dates, ranks, plans versus completed
  actions, source original and model output safety/format controls.
- A safe bounded model generator, token-cost ceiling, source-version pinning,
  draft retries and queue/hold receipts. Model ingestion is *not* authorized by
  creating this offline validation code.
- Independent authenticated owner decision for controlled **full body and
  machine translation** public release, with publisher attribution and
  retraction/correction procedure. An operator setting a JSON Boolean or
  supplying an HMAC is not itself independent legal/source-language review.
- A production SQLite schema, reserved source-record routes, renderer and
  file-scoped guarded Pages release for only the specifically authorized
  public fields. No approved documents, photographs or media reuse is inferred.
- A separate public format for **labeled automated source notes** with
  provenance, explicit model/official-claim labeling, uncertainty and human
  incident/correction mechanisms. Editorial IPR Briefs keep human approval.

The lowest-risk incremental route is text-only with source-specific rights
clearance, then labeled machine translation, then labeled source notes.
Whole-file HWPX/PDF rehosting and photographs remain withheld unless an
independent, explicit rights decision covers each separate material class.
