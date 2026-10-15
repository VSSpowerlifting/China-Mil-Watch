# USCC exact-source admission — October 15, 2026

Purpose: make the successfully collected, first-party U.S.-China Economic and Security Review Commission daily **official URL, date, issuer and source ID** observations usable as a production metadata record family, without storing publisher originals or claiming PACOM collection works.

- Source input: Git branch `shadow/uscc-press`, only `observations/YYYY-MM-DD.json`. Every packet is checked against the collector's bounded schema and its date, source URL, issuer, publisher host, source-identity relation, prohibited-content flags and per-day listing digest.
- On discrepancy or silent relabeling, stop. Existing official identities cannot be silently redirected, redated or reassigned. A repeat receipt is idempotent.
- Output: `uscc_official_source_records` and `uscc_official_observations` tables only; do not mix congressional commission records with `articles`, PACOM, DVIDS or IPR editorial output. Existing archive record counts are unaffected.
- Standing approval: October 15 permission covers verified **URL/date/issuer metadata**, not external headline/body/media preservation or original analysis.
- Admission code exists on a branch, while CI is a scratch-copy rehearsal. **Nothing is auto-published merely by merging this scaffold.** The independent production and Pages-only publisher is a following integration boundary.
- Official publisher may change its website; collection failures must stop and may not count as successful daily observations. Older collected observations remain source-history receipts, not proof of comprehensive coverage.
