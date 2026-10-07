# Singapore September 22 recovery — 2026-10-07

Owner-authorized one-source recovery, after PR #85 merged. Base and freshly fetched reconciliation main: `9b475d0d578f93e6d4b9dc7cc90d3ad38c627b10`; reviewed head `bfc899e603f300f47f6da186009963ef0a9ea3da` is a direct merge parent. PR #85 offline-checks passed. Existing worktrees were preserved; recovery ran in an isolated branch.

## Scope and live evidence

Before execution, the current DB held 4,927 articles, including 76 Singapore records. DB SHA-256: `b10890ddac59538b66041b10d13d08199f20be2279efa9bcb03a2d991d17decc`. The identifiable adapter reread robots and the official sitemap; both returned HTTP 200. Policy allowed the sitemap and all eleven selected release URLs. Selection remained slug dates September 22–28, canonical MINDEF latest-release URLs only. The three missing URLs were confirmed before insertion; the eight others were duplicates. Both governed holds (`15aug26-speech`, `16sep26-speech`) remain excluded and absent from the DB.

Executed once live, 2026-10-07 15:58:54–15:59:24 UTC:

```sh
.venv/bin/python pipeline.py --date 2026-09-28 --source sg_mindef_releases --no-analysis
```

Temporary transport instrumentation recorded responses without changing collector source, identity, timeout or pacing; it rejected requests outside MINDEF. The preflight requested robots and sitemap only; recovery requested those plus eleven pages. No images were fetched. Responses are retained locally at `/tmp/sg-recovery-20261007/responses/` for this review, not committed fixtures or a durable archive.

| Live source-run 162 / result 267 | Actual |
|---|---:|
| Discovered / fetched / extracted | 11 / 11 / 11 |
| New / duplicate / rejected | 3 / 8 / 0 |
| Usable text / unavailable text | 10 / 1 |
| Failed fetches | 0 |

Status `ok`, aggregate `completed`; error detail: “1 of 11 parsed page(s) carried no usable text; their titles, URLs and dates were kept”. The pipeline constructed a backlog queue but skipped analysis under `--no-analysis`; no model call or stored verdict changed.

## Recovered records

| ID | Official URL slug | Original-text characters | SHA-256 of stored original text |
|---|---|---:|---|
| 4934 | `22sep26-speech` | 13417 | `0c40feac81025aa6557128ac84a256bfc05792f3efd5d73945d94425c630db74` |
| 4935 | `22sep26-nr` | 4165 | `10866200805dcb0d67974d98e34e12400c4dfd179ffdfb5bcd3408d493f21177` |
| 4936 | `22sep26-infographic` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

All three retain the official title and September 22 slug date, with `passed_relevance`, analysis time, model id and machine prose NULL. Each stored title, body, date and content hash matches the real adapter extraction plus production normalization from the captured live response. Both prose pages have structural prose and no replacement characters; their openings and endings were inspected. Existing extraction includes date/resource/button furniture and news-release image captions; this recovery does not alter that reviewed behavior. The infographic container has one image and zero prose: `text_original` is exactly empty, not the incidental date/resource/button text. Its image contents were not read. No durable per-record media-only field exists; unavailable text is recorded by the empty body and run count.

## Verification and reconciliation

- Every pre-existing row across all tables was preserved; all 4,927 existing articles (including the eight duplicates and every verdict) compare field-for-field equal. Only three articles, one scrape run and one source result were added. No category/analysis changes.
- Offline replay served all thirteen captured responses through the same adapter and real pipeline on a scratch copy. Actual repeat: zero inserts, eleven duplicates, one unavailable text, status `ok_all_duplicates`. All article rows and all tables except the two run-accounting tables remained identical. The offline repeat is not in the committed DB, and no second live collection was run.
- 118 focused offline tests passed: `tests.test_singapore_image_only_release`, `tests.test_singapore_scheduled_production`, `tests.test_singapore_production_window`, `tests.test_reconcile`.
- `scripts/verify_db_current.py` passed: schema current, complete ledger, integrity `ok`, empty foreign-key check.
- Established `scripts/reconcile_db.py --base ... --origin ... --local ... --out ...` procedure used immutable pre-run base, freshly fetched main DB and recovered DB. Origin identity was authoritative. Report: three inserts, one remapped local scrape run, one source result merged, zero analysis backfills; all gates passed. Main had not advanced, so reconciled logical tables equal the recovered DB exactly. The verified reconciled result was landed, not a wholesale choice of the local side.
- The first local file transfer failed final verification (copy I/O error and differing bytes). The independently verified reconciled scratch DB remained intact. Archived stale SQLite sidecars (WAL was zero bytes), reinstalled exact reconciled bytes, and verified byte equality plus schema/integrity/FK checks again. Final DB SHA-256: `712fa29a5f0356a216d47cd05f69839da757e806d42d04ff7be8d449f8f9f63b`; no tracked DB sidecars remain.
- Source, collector, manifests, shadow state, output and sidecars are unchanged. No render, deployment or merge. This DB-only recovery does not update the public site.

Raw response SHA-256 (live recovery captures):

| Response | HTTP / bytes | SHA-256 |
|---|---|---|
| `robots.txt` | 200 / 89 | `ed806e2d4efd2394315984db1b334ae93d571957110fdbbe974b45191562d96b` |
| `sitemap.xml` | 200 / 818531 | `39f12303e9de8e32d3e750a6ad9835500db8500158779bbb5c8ff3429cdf39b7` |
| `22sep26-speech` | 200 / 513532 | `9e210eae345d8ac13ffbb657e5418322ddbf73d0a09b830d209e1fb0c534026c` |
| `22sep26-nr` | 200 / 481466 | `c8cf1fc3b68cadaa55ddc2f83486fcb9fb9c3cc2e2ee6b27c2d62e415fa0dc2e` |
| `22sep26-infographic` | 200 / 451556 | `922a97372c7ca2d9a7d5b91eea5de8c105e0a71ee6c1b5d808dd47adbaed1646` |

Next action: review the draft recovery PR and its CI on the exact head. If main advances before landing, rerun established reconciliation against that newer main and reverify origin-row preservation. Rendering/deployment and merge require separate authorization.
