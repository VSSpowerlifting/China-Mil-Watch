# Indonesia Desk — working private Kemhan Berita reader (October 11, 2026)

**Engineering scope:** extend the existing Philippines/Vietnam/Korea local metadata research reader to the already-running Indonesia *Berita* shadow branch. This is private research functionality only. There is **no** new collector, source expansion, live publication, registry declaration, editorial approval, production record, model input, public desk page, or deployment.

## Exact existing source and fresh observation

- Source family: `id_kemhan_news`, official Kemhan `Berita` listing only (`https://www.kemhan.go.id/category/berita`), collected by the existing identified, robots-gated isolated collector.
- Git source-state branch: `shadow/indonesia-kemhan`; the command fetches its current existing tip, resolves a literal immutable commit, then reads only Git objects from that exact commit. It does not request the publisher.
- **Observed on October 11:** state branch `17dfae7e6e1e9e1142d81c89764f022ebf03552f`; saved Day-0 clock `local-native-20261006-indonesia`; October 11 ledger run `38174376601-1`, logical date 2026-10-11, `health=ok`, `result=ok_all_duplicates`, **24 stored records**, 15 duplicates, 0 inserts, and no recorded fetch/access/extraction failures. State database digest in that ledger: `97adcbac44b626bdf36a5e66ae3315df7b3bcc340575d0e78c0d0bfc1e05cd74`. This is a **read-only Git observation**, not an exhaustive independent authenticated Actions history, source license, or original-language review. Counts will change.
- This first family is **ministry institutional news**. It is not Siaran Pers, a TNI feed, all Indonesian defense publication, or evidence of 30-day qualification. The separate offline Siaran Pers prototype remains unregistered and inactive.

## Private, one-command analyst use

From an IPR source checkout with Python 3.9 and Git, using an absolute **new** destination outside the checkout:

```bash
python -m scripts.launch_private_country_desks \
  --desk indonesia --approve-github-shadow-fetch \
  --format html --output "$HOME/Downloads/ipr-indonesia-private.html"
```

Original-language title and **preserved body** are searchable privately at command time, without emitting source-body text:

```bash
python -m scripts.launch_private_country_desks \
  --desk indonesia --approve-github-shadow-fetch \
  --query pertahanan --format html \
  --output "$HOME/Downloads/ipr-indonesia-pertahanan-private.html"
```

`--format json` outputs source metadata to stdout only; redirect into a trusted private path. HTML contains publisher links, original-language titles, publication dates, institution, source identities and pinned Git commits. The HTML's later on-page filter searches its **displayed metadata only**, not withheld original body. No excerpt, publisher capture, PDF, article text, or model synopsis is exported. Existing `--desk both` retains its Philippines/Vietnam meaning; `--desk all` now includes Korea and Indonesia as well.

## Admission and custody constraints

The reader refuses any absent/malformed source family, nonliteral commit, mismatched source desk, malformed clock, unrecognized official host, changed canonical Berita URL/date/identity, unapproved source category, non-Indonesian language label, missing/changed saved-body hash, invalid capture reference, or source rows from another family. It opens the exact pinned Git SQLite bytes in a disposable local immutable/read-only DB, enforces a fixed size and row cap, and discards the extracted body data after building the metadata result.

A successful reader means *research access to preserved source material*, **not** that a human compared 24 original articles or that IPR can publish their text. Specifically unapproved: shadow-body redistribution, copyrighted media and attachments, English translations, AI/editorial use, public-source links, production source registration, and source qualification.

## Verification and downstream gates

Focused deterministic local tests:

```bash
python -m unittest tests.test_private_country_desk_reader tests.test_launch_private_country_desks -v
```

On an exact PR head, require green CI, DB/output preservation and an isolated Git state reader check before owner review. The tests use offline **synthetic** Git/SQLite originals; the real October 11 Git source branch was observed for metadata but the new reader has **not** yet been run against a live clone. Do not imply that a passing fixture substitutes for an original-language article comparison or source-rights review.

**Next separate phase:** run the new read-only command against the actual pinned Indonesia shadow head; sample the full Indonesian originals against publisher captures, reconcile the October 6–11 schedule and missing/failed attempts from independently authenticated GitHub Actions data, and complete the actual Day 7/14/30 human checkpoints (earliest Day 7 October 13, subject to measured schedule continuity). Only after rights and named human sign-off should Indonesia be proposed for a bounded public metadata-reference page. Public corpus admission and full desk promotion are later and independent decisions.
