# Japan Coast Guard September source-gap review — before historic backfill

**Status: source feasibility only, not a backfill or human approval.**

The first durable JCG shadow run [#37828199188](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37828199188), state `81558026117067cbcf54bd7a7859a2d9db168a0c`, was healthy: **3 original HTML articles** stored, zero fetch/extraction failures. It used an explicit logical source date **2026-10-08** with a 9-day window beginning September 29.

The archived official JCG publisher index (Git blob `97b1b357f1dab36a667d493424607f37db334b87`) actually lists **five** article releases within the declared September-onward HTML pilot. Two fall outside that 9-day window:

| Original issuer/index date | Exact first-party URL | Topic | Day 0 status |
|---|---|---|---|
| 2026-09-18 | https://www.kaiho.mlit.go.jp/e/topics_archive/article9424.html | 22nd Heads of Asian Coast Guard Agencies Meeting (HACGAM) | Publisher index only; original HTML not captured |
| 2026-09-07 | https://www.kaiho.mlit.go.jp/e/topics_archive/article9399.html | Japan–Philippines Coast Guard capacity building | Publisher index only; original HTML not captured |

These are not scraper failures or source refusals, and the Day 0 ledger accurately states the collection window. They are **historic source-scope omissions** that should be dispositioned before we call the full Sept1-onward English press family archived.

## Read-only proof, deliberately separate from permanent write

`scripts/probe_jcg_early_september_fidelity.py` checks the exact September 1–October 8 official publisher archive index from the existing identified JCG adapter. It requires exactly the five known publisher publication identities and index dates, then fetches **only** September 18 and September 7 originals and verifies each HTML body, publisher/index date, official source identity, text digest, PDF companion exclusion and issuer. Any unexpected publisher index change fails closed and requires review, not adaptive URL guessing.

It emits only source identities, official URLs, dates, capture/text hashes, text lengths and attachment counts. No original article bytes, PDF bytes, text or record state is persisted. The identified JCG client, official publisher robots treatment, no-bypass and no-redirect limits remain those of the already validated source adapter.

**Even a green proof does not itself import those two records or qualify a new successful shadow day.**

## Backfill engineering gate after positive proof

The production shadow runner currently limits collection `lookback` to **30 days**. A September 7 document is older than 30 days relative to October 8. We must **not** forge a September 7 run target just to bypass this limit: that would create synthetic earlier shadow days and corrupt Day 7/14/30 reviewer continuity.

A separately reviewed, **explicitly labeled JCG historical-backfill mode** should:

1. Require the original `shadow/japan-jcg` branch/clock and pinned initial SHA, no initialization or clock reset.
2. Bind historical selection to a fixed Oct8 cutoff and the two verified September article identities. Restrict out-of-scope publisher URLs; no general unbounded historic crawler.
3. Record true execution time and a backfill-only operation type, tied to an append-only provenance ledger. **Do not** claim a successful scheduled collection day for September 7 or September 18.
4. Refuse to rewrite the three already archived original records or overwrite prior capture digests; preserve the original Day 0 ledger and hashes.
5. Conduct a formal, commit-pinned shadow review after the backfill. Keep `published_html_text_only` and PDFs excluded until separately adjudicated.

This later backfill must not enter `desks/japan/manifest.json` or weekly AI-writer production eligibility. JCG is not the Ministry of Defense, and two missing original HTML pages do not establish Japanese defense-service coverage.

The current live review PRs are independent: #224 provides a formal pinned report, while #227 proposes a default-off daily qualification schedule. Both must preserve the true October 8 Day 0 anchor.
