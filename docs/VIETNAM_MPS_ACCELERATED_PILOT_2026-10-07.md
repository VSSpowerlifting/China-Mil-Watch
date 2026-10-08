# Vietnam MPS accelerated pilot — preparation and boundaries (2026-10-07)

This phase prepares a human-gated import from the Ministry of Public Security's
Vietnamese foreign-affairs RSS source, vn_mps_foreign_affairs_vi. It does NOT
promote Vietnam to live, remove Day 7/14/30 reviews, start a second collector
or publish records. MOIT, Government News and blocked sources are excluded.

## What the command verifies

The command scripts/prepare_vietnam_mps_pilot.py requires a complete immutable
shadow state Git commit reachable from shadow/vietnam-mps-foreign-affairs. It
exports the committed state tree, validates the complete source ledger, capture
bytes, version chain, publisher, dates and clock using the existing formal
Vietnam review code, and matches every selected document to a human approval.

The approval must name a human reviewer, a timezone-aware approval instant, the
exact state commit, source identity and current content digest for each selected
record, six affirmative manual checks (source page opened, title, date, body,
publisher, and no challenge text), and an explicit per-record reuse authorization
with a documented rationale. Accessible source material is not automatically
authorized for public reproduction.

At most ten individually approved documents may be staged. A record with an
empty body, an unreviewed version, capture mismatch, observation anomaly,
unapproved reuse, duplicate selection or malformed approval is refused.

With no destination the command only reports the candidate. When given an
existing migrated database copy outside the source checkout via
--into-disposable-db, it performs a transactional, idempotent staging import.
It creates inactive Vietnam desk/institution/source metadata and imports only
the approved article rows. A provenance table ties every imported article to
the source identity, raw-capture digest, content hash, Git state commit and tree,
reviewer, decision instant, source date and explicit rights rationale.
Existing conflicting URL rows are refused rather than replaced.

## Authorization JSON shape

Placeholders below are NOT approvals and must be replaced with facts verified
against the actual source pages and immutable record inventory.

    {
      "schema": "vietnam-mps-pilot-authorization/1",
      "source_slug": "vn_mps_foreign_affairs_vi",
      "state_commit": "<full 40-character state commit>",
      "reviewer": "<reviewer's name>",
      "reviewed_at_utc": "<timezone-aware ISO 8601 instant>",
      "records": [{
        "source_identity": "<source identity from the review>",
        "content_sha256": "<64-character current version digest>",
        "checks": {
          "source_page_opened": true,
          "title_matches": true,
          "date_matches": true,
          "body_matches": true,
          "publisher_matches": true,
          "no_challenge_text": true
        },
        "reuse_approved": true,
        "rights_basis": "<specific, independently verified reuse basis>"
      }]
    }

## Reproducible rehearsal

First clone the exact MPS state branch with its Git metadata and prepare a
formal Vietnam ministry evidence packet. Review source pages and reuse terms
manually. Place the JSON authorization outside the repository, then execute:

    python scripts/prepare_vietnam_mps_pilot.py \
      --state-repo /tmp/ipr-vietnam-mps-state \
      --state-commit "$MPS_STATE_SHA" \
      --approval /tmp/vietnam-mps-authorization.json

Only after the read-only candidate passes, prepare a clean migrated database
snapshot using SQLite's backup API. Never copy an uncheckpointed live WAL.
The copy must be outside the repository:

    python scripts/prepare_vietnam_mps_pilot.py \
      --state-repo /tmp/ipr-vietnam-mps-state \
      --state-commit "$MPS_STATE_SHA" \
      --approval /tmp/vietnam-mps-authorization.json \
      --into-disposable-db /tmp/ipr-vietnam-mps-pilot.db

Inspect all staged articles and provenance. Compare the database before and
after; the only new rows should be the authorized pilot rows plus the disabled
desk/source/institution and provenance metadata. This phase does not re-render
the public site, alter output/, or write to pla_watch.db.

## Remaining production release gate

A separate owner-reviewed PR is required to move from disposable staging to
a live limited production pilot. It must decide each record's reuse and display
rights, install a production ingestion path with monitored health and clear
ownership of the shadow-versus-production clock, and review a real DB/render
diff. In particular, never run two collectors that silently diverge or write
unbounded data; never expose model processing automatically.

Early public pilot publication also needs an explicit, documented owner
exception to the ordinary 30-day qualification policy. That exception would
permit only specified source-family records and would not count as desk
qualification. Continue Vietnam's October 14, October 21 and November 6
Day 7/14/30 reviews. An offline green test does not confer permission to
republish state or a claim of comprehensive Vietnam coverage.
