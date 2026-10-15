# Treasury isolated official metadata SQLite admission

Exact publisher `shadow/us-treasury-press` observation receipts are not source articles. Admission must match issuer `us_department_treasury`, source identity `us-treasury-press:sbNNNN`, canonical first-party link, date and original listing digest. Unsupported fields and mutated existing IDs must halt. Separate `treasury_official_source_records` and `treasury_official_observations` tables do not alter main `articles`, PACOM, DVIDS or congressional USCC records.

Only source URL/date/issuer metadata qualifies under standing owner permission. No headline/body/attachment, translated text, media, summary or categorical Indo-Pacific claim is imported. All source cards may concern other Treasury work; readers should see them as a broad official department listing, not a selectively screened topical feed.

This PR is an implementation scaffold with **synthetic admission tests only** until its upstream real daily shadow collection is merged and the recorded observation branch is independently read back. A live production release must prove real observation and file-scoped Pages readback, separately.
