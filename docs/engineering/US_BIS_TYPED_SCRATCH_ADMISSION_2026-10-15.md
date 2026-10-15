# BIS source metadata — held typed SQLite staging rehearsal

**State: code review only. Never a live importer, public feed, or source approval.**

This independently scoped follow-on to BIS shadow collector PR #693 builds a typed,
idempotent BIS-only SQLite *scratch* admission function and neutral readback.
It deliberately does not modify the production SQLite schema, register with
the U.S. Desk renderer, schedule a publisher task, write to main, or touch
\`output/us-indopacific.html\` / \`gh-pages\`. Existing USCC and Treasury live
feeds and nine PACOM static links remain unaffected. DVIDS remains paused.

The source packet must match the exact verified BIS homepage metadata-only
schema: first-party canonical press release URLs, publisher dates, Commerce/BIS
issuer, listing digest and fixed row structure. Headlines, articles, abstracts,
PDFs, photographs, translations and AI analysis are never admitted. The
staging SQLite tables are BIS-typed and separate from article counts. Duplicate
observations and identity conflicts fail closed; a savepoint guarantees no
partial write following an observation conflict.

The CLI demands an explicit acknowledgment that these are **unauthenticated
rehearsal inputs**, rejects the production database and *all* paths inside
the repository, requires a NEW absolute scratch DB outside the worktree, and
accepts only a bounded YYYY-MM-DD.json packet. Source-revision SHA parameters
are **syntactic references**, not proof of a legitimate scheduled source run.

Before a production importer can exist: PR #693 must merge, the genuine
\`schedule\` event and immutable \`shadow/us-bis-homepage\` receipt must be
verified against GitHub run logs and source digest, exact official content
and reuse permission must be accepted, and the owner must separately authorize
a narrowly limited official-link admission. Only then should the verified
source lineage gate be wired into a controlled SQLite → U.S.-desk-only Pages
workflow, with independent deployed readback and preserved article counts.

For this PR: \`python -m unittest tests.test_us_bis_official_metadata_admission
tests.test_us_bis_homepage_receipt -v\`. The dedicated PR check is
read-only relative to production and needs no network calls.
