# BIS genuine scheduled official-link SQLite admission — held engineering candidate

Source collector #693 and independent scheduled run attestor #704 are merged to main.
Separately, scratch-only staging #702 is under review. This PR builds the
**actual strict attested metadata-only SQL admission interface**, but it is
not invoked by production, a scheduled workflow, a renderer or Pages.

The importer accepts only the exact BIS publisher homepage packet verified by
the independent source-branch run/attempt attestor, using authenticated GitHub
REST run metadata and a pinned source branch head supplied by its future
trusted release workflow. Official link URLs, posted date, fixed Commerce/BIS
issuer and first-party listing digest are admitted into separate BIS-specific
typed tables. A missing table returns zero public BIS links. Source identity
collisions or a changed prior-day digest hold transactionally, preserving
USCC/Treasury/PACOM and all other collections. No bodies, headlines, images,
abstracts, translations or AI analysis enter the tables or main article counts.

The CLI requires explicit standing approval for official URL/date/issuer
admission and refuses every missing/invalid source proof. A **caller-controlled
JSON file is not, by itself, an authenticated GitHub response**. The future
scheduled release job MUST obtain run JSON itself through authenticated GitHub
REST, pin the remote shadow branch SHA before/after, call this importer within
the official release window, compare DB counts and render a preview before
any production push. That future release workflow DOES NOT exist here.

The source-free PR CI uses only synthetic packet and Git fixtures plus
temporary SQLite. It never writes the tracked production DB, output directory,
site code or source Git; it requires no live source and cannot create a
qualifying scheduled day. The public BIS display section and U.S.-Desk-only
Pages release require a further separately reviewed phase.

This is a controlled extension of existing live USCC/Treasury metadata-only
practice, **not** a China-style full-document archive, publisher reuse license,
a comprehensive BIS catalog, an Indo-Pacific relevance decision or editorial
approval of analysis.
