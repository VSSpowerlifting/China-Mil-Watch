# China active-corpus retirement: permanent URL re-ingestion block

**15 October 2026 · engineering phase only; no records retired or published by this PR.**

The owner authorized retiring **4,300–4,500 China records** from the *active* SQLite database after exact citation/dependency checking. A 600-record browse view is only an interim presentation change. Physical deletion is a separate, higher-risk operation: the next daily collector or a DB rebase must not undo it.

## Durable tombstone contract

Migration **0009** creates the **empty** `retired_article_urls` ledger. It has unique SHA-256 of the exact stored canonical URL (UTF-8), unique positive original record ID, issuing source slug, retirement date and exact selection-manifest digest. It has **no foreign key** to `articles`, whose historical row is the object being retired. The migration does not delete, relabel, hide, or insert any records; the table remains empty until a separately approved production cull.

`core/retired_article_urls.py` computes exact URL hashes, checks membership and rejects any database containing a retained article whose URL is simultaneously tombstoned. An intentionally retired URL is not a new collectable document. This status is about retention, not source authenticity, quality or political value.

Three actual ingestion boundaries are covered:
1. `storage.db.url_exists` treats a previously retired URL as a duplicate so normal dedup catches it early.
2. Both `insert_article` and `insert_articles_atomic` repeat the check inside their actual SQLite write transaction, including keyword-rejected articles.
3. `scripts/reconcile_db.py` skips locally reintroduced tombstoned URLs, preserves the published-origin ledger, fails if local carries retirement entries absent from published origin, and treats deliberately retired local URLs as protected from reinsertion rather than an unreported loss.

The DB schema verifier requires migration 0009 and checks that no active article matches a retired URL hash **or reuses its original numeric article ID**. Because SQLite `INTEGER PRIMARY KEY` can otherwise reuse the highest deleted ID, both ingestion paths and the reconciler now allocate above the high-water mark across active and retired IDs. A SQLite trigger independently rejects a reused retired ID even from direct SQL. A missing or inconsistent ledger fails database verification.

## Scope and real remaining release gates

- The work is inert with an empty ledger: existing articles and routine collection remain unchanged.
- **Production purge is NOT authorized by merging this PR.** The separately developed scratch retirement planner in [#653](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/653) must be integrated to write ledger entries *in the same transaction* as physical deletions, rather than publishing a list of hashes without a verifiable DB-side receipt.
- That release must freeze an exact `main` + source/index snapshot, confirm the **4,300–4,500** target, enumerate indirect Brief/timeline/record citations, verify private backup restoration, fully regenerate the site from the reduced DB, and review retired route behavior. No public historical evidence or private backup is silently thrown away.
- A Git rebase from a pre-retirement branch must not resurrect the old article bytes. Published-origin tombstones are authoritative and an independently edited local ledger stops reconciliation rather than guessing.
- Test coverage: single insert, atomic pass/reject, early dedup, corrupted active-row detection, migration, stale-local merge skip and conflicting local tombstones. Focused workflow runs the real migration and reconciliation suites.

**No production article or output file is changed by this PR.**