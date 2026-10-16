# BIS metadata-only U.S. Desk — genuine scheduled-source Pages release candidate

Status: implementation PR, not activated.

This extends the merged BIS collector (#693), typed scratch staging (#702),
independent scheduled receipt attestation (#704), authenticated importer (#705)
and conditionally rendered U.S. Desk bridge (#708).

The owner has authorized verified official URL/date/issuer metadata only. No
source headlines, full texts, photographs, PDFs, translations, substantive
analysis or claims of complete publisher history are collected or republished.

## Provenance and authentication gates

A production job runs only on a successful real scheduled GitHub Actions event
from the exact BIS homepage shadow workflow on main. No PR, manual dispatch,
push or time-based reconciliation can trigger production. The job independently
fetches run JSON from authenticated GitHub REST and pins the shadow branch
head, then verifies the run, attempt, Git receipt, digest, issuer and URLs
before touching SQLite. A genuine event does not itself prove an independently
rehashable publisher HTML original.

## Database, output and publishing gates

- Serialize in the existing daily-update concurrency group.
- Preserve the original main SHA, shadow source SHA and SQLite checksum.
- Reject dirty checkouts and unexpected WAL or SHM sidecars.
- Snapshot row counts for every non-BIS SQLite table, require them unchanged.
- Admit only idempotent authenticated BIS metadata in separate BIS-specific
  tables. Do not inflate source-body article counts.
- Render and inspect only the existing U.S. Desk metadata presentation:
  typed BIS URL/date links, 10+ existing USCC, 10+ Treasury, nine PACOM links.
  PACOM is access blocked; DVIDS is paused.
- Reject moving source or main before pushing, and stage only pla_watch.db
  and output/us-indopacific.html to main.
- Check out existing gh-pages, stage only us-indopacific.html, reject remote
  Pages movement, and verify the exact file SHA in Git after publication.

No genuine scheduled BIS receipt has been verified at the time of this PR.
A metadata-only reference feed is not a complete BIS archive, policy-subject
relevance determination, source-body reuse license, or editorial judgment.

## Recovery and future proof

A failed Pages publication after a successful DB commit leaves a recoverable
DB/page mismatch, not a verified live publication. This first release candidate
does not yet implement independent scheduled reconciliation or CDN readback;
those need subsequent engineering work and checks before claiming resilient
fully operational publication. Do not fake a scheduled observation or count a
PR or manual read as genuine collecting evidence.
