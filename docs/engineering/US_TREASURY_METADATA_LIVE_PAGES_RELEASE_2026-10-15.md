# Treasury official metadata U.S. Desk-only production release

A separate, independently attributable U.S. Treasury feed complements the already live **USCC congressional commission** and manually pinned **PACOM** references. Its collector preserves only verified official release URLs, publication dates, fixed issuer and list digest in `shadow/us-treasury-press`. No article bodies, headlines, photographs or translations are retrieved or republished.

The release workflow consumes the immutable source Git observation branch, verifies each exact source record, inserts it idempotently into the typed Treasury-only SQLite metadata tables, renders the existing U.S. Desk, and commits only `pla_watch.db` and `output/us-indopacific.html` to `main`. It then publishes only `us-indopacific.html` to `gh-pages` after checking source and destination refs for advancement. Daily reconciliation retries recover when the database commit succeeds but the Pages step fails.

A source-listing announcement may cover economic, tax, international financial or enforcement subjects unrelated to Indo-Pacific security. These are therefore displayed as a broad **official Treasury reference list**, not a curated policy topic or source-body article archive. IPR's actual researched interpretations require separate human editorial approval.

Existing PACOM access-blocked status, USCC congressional metadata, DVIDS pause, China corpus, original research and all other desk pages remain unchanged. Other site files produced by a full local render are never staged/deployed. The output/source article count excludes Treasury metadata.
