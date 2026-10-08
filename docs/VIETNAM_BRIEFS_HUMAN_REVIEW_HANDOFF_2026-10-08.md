# Vietnam MPS → October 10 Briefs editorial handoff

## Status: private human review candidate; NOT production admission

The Vietnam ministry shadow runner has verifiable October 7 collection receipts,
but Vietnam remains a research desk without production records. Our Friday
automated Briefs writer builds its model prompt from **live, production-backed
full-text records only**. This change does not weaken that rule or create fake
production IDs.

Instead, the existing Friday private editorial worksheet can append a small
bounded set of *unapproved* MPS links for Dylan to inspect and potentially
recommend to the Editor. This is a source-discovery aid, not a machine-generated
Vietnam claim, published analysis, or approved brief citation.

## Real October 10 packet

`research/vietnam_briefs_candidates/2026-10-10.json` pins two official MPS
articles published October 5:

- `mps-vi:1791199100`: technology and security-industry discussions with
  Turkish partners — official source URL:
  https://bocongan.gov.vn/bai-viet/mo-rong-hop-tac-cong-nghe-cong-nghiep-an-ninh-voi-cac-doi-tac-tho-nhi-ky-1791199100
- `mps-vi:1791199677`: meeting about training and security-technology
  research with Concordia University — official source URL:
  https://bocongan.gov.vn/bai-viet/cu-the-hoa-hop-tac-dao-tao-nghien-cuu-cong-nghe-an-ninh-voi-dai-hoc-concordia-1791199677

Both were identified in the successful MPS Oct 7 state ledger and the separate
Oct 8 metadata-only candidate review. Pinned state commit:
`46f6a0e59e25b03868bf7ad600963d6921ee5124`.
Original Vietnamese titles, publication dates and corresponding current
version content hashes are retained for comparison. See
`docs/VIETNAM_MPS_FIRST_REVIEW_QUEUE_EVIDENCE_2026-10-08.md` and
`docs/VIETNAM_MPS_OCT10_EDITORIAL_CANDIDATES_2026-10-08.md` in PR #195.

The October 2 Myanmar item is *outside* the October 4–10 publication week,
regardless of its later capture date, and is intentionally absent.

## Fail-closed rules

- Only the exact Saturday-specific JSON file is read; no file means zero
  candidates, not a reason to fabricate or backdate evidence.
- One to five MPS article URLs, HTTPS-only exact publisher hostname and article
  identity, pinned full shadow state Git commit and SHA-256 content version.
- The candidate date must lie Sunday through Friday, **not Saturday or a
  previous week**, and `review_status` must always say that independent
  human review is still required.
- The candidate file cannot contain source article bodies, machine
  translations, invented English titles, rights grants, signoffs, or records
  for disabled sources.
- No new network fetch, model call, production DB/output/manifest mutation,
  shadow clock, or production collection is introduced.
- This extra material appears **after** the production source appendix in the
  existing private attachment, kept in its immutable section. Dylan's returned
  file must preserve it byte-for-byte; the Saturday audit still counts only
  production record IDs from the original source appendix.
- The automatic model sees **none** of these candidate metadata notes. The
  packet must never imply that Vietnam satisfies the ordinary two-live-desk
  Briefs requirement.

## How it runs

The existing Friday scheduled or manual
`weekly_briefs_editorial_handoff.yml` invokes
`python -m scripts.weekly_editorial_handoff --write-automatic --as-of <FRIDAY>`.
The script now looks for the file matching the scaffold's exact Saturday
identity and appends the verified-format candidates **only after successful
automatic production-backed composition**, before the optional SMTP send.
No workflow secrets, scheduled triggers or recipients change.

A dry-run tests the exact handoff path without sending email:

`python -m unittest tests.test_vietnam_briefs_handoff tests.test_weekly_editorial_handoff tests.test_editorial_return_validation tests.test_weekly_briefs_saturday_audit`

## Actual next editorial decision

A human must open each URL, independently verify the full Vietnamese article
against the pinned archived original, date, institution, version and factual
meaning. Assess whether its substance belongs in the week's analysis:
MPS security-industrial contacts are **not** defence ministry procurement;
exploratory meetings are **not** signed contracts. Dylan should flag relevant
sources and return his suggested claims and URLs; Ben makes the publication
decision. The regular `core.brief_contract` still disallows counting a
non-live Vietnam Desk as production coverage; a separately reviewed external
citation lane or an explicit owner-excepted, rights-cleared production pilot
would be necessary to make Vietnam a formal cited desk in a numbered brief.
Neither is granted by this preparatory PR.

This is a deliberately narrow, usable Friday editorial **candidate** lane.
It does not claim Vietnam's desk is ready or that any article is authorized
for public reproduction. Day 7/14/30 source reviews stay scheduled for
October 14, October 21, and November 6.
