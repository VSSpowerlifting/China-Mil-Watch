# Korea DAPA — one exact first-party original article identity check

**Status: one authorized, bounded first-party article observation succeeded on 2026-10-17; strengthened date binding is not yet live-verified. No source admission.**

[Owner-dispatched run 39042839823](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39042839823) returned `DAPA_ONE_OFFICIAL_DOCUMENT_ROUTE_AND_DATE_MARKER_OBSERVED` for article `59180` (SHA-256 `94bdbabc7e1bfb19aadd8cc8f0bc8f80d8096c967e0c5e88e75bc3ff48274807`), with exactly two requests, no original retained and all issuer, listing-linkage and rights flags false. **Its earlier implementation tested for a date anywhere in visible text plus a posting label anywhere else, so the green result must not be described as proof of the adjacent posting-date field.** The hardening below requires a new, separately owner-authorized exact-URL run after merge to prove the stronger condition on live HTML.

The source is the actual DAPA website, `www.dapa.go.kr`, not the distinct annual `data.go.kr` catalogue and not the `korea.kr` republisher. Prior DAPA listing permission covered at most one first-party listing GET, NOT an original article GET.

## Grounded public indexed article lead

An official first-party article is independently linked by the public search index:
- `https://www.dapa.go.kr/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=59180&menuSeq=3069`
- `bbsSeq=326`, `docSeq=59180`, `menuSeq=3069`
- publisher-displayed date, as publicly indexed: `2026-09-18`
- subject: industrial technology development and DAPA support for small firms

This is a **source-specific example**, not a currently live new release, not proof of an October 2026 listing-row link, not a general parser for DAPA's JavaScript navigation, and not an assertion that every release on this government site is DAPA-authored (joint/affiliated issuers occur).

## Exact two-request operator-authorized probe

`.github/workflows/korea_dapa_single_article_canary.yml` has a NEW manual operator switch, `authorize_one_item_official_article_get`. The checkbox must be explicitly enabled from `main` by `VSSpowerlifting` independently of prior host/listing permissions.

1. One `GET https://www.dapa.go.kr/robots.txt` (15s, 32KiB, text/plain, exact URL, no redirects), then fail closed if unavailable or the exact article route is disallowed.
2. Only if that rule permits the article route, sleep two seconds and issue ONE strict GET of the **sole allowlisted** full URL with docSeq `59180` (15s, 800KiB, exact URL, text/html, no redirect, no session/cookie/retry or alternate endpoints).
3. Inspect Korean publisher HTML in memory only. Require **exactly one** visible posting-date label `게시일` with its immediately adjacent, valid date matching `2026-09-18`; matching dates elsewhere in the body, a competing posting label, JavaScript-only dates, and challenge/error markup must fail closed. Emit only fixed access/identity statuses, response SHA256 and metadata booleans. The untrusted body, original Korean prose, title, HTML/JS, attachments and full URL are **not logged or preserved**.

Even after a successful check the following explicitly remain **false**: `article_linked_to_live_listing_row`, `individual_dapa_issuer_verified`, `source_content_licensed`, `article_text_captured`, `collection_enabled`, `production_published`.

No article/press text is stored to the production database or public Git. No attachments, original HWPX, PDF, photographs, model translations or editor-approved analyses are accessed or created.

## Next gates after any verified readback

- Confirm the literal dynamic list-row-to-`docSeq` mapping from an independently observed source version with a separately reviewed permission gate; list item **ordinal is not docSeq**.
- Validate the observed date/issuer on a reviewed original per item and preserve an authenticated private source hash and provenance.
- Separately review rights for exact text use, attachments and third-party material. This single example cannot bootstrap a blanket DAPA license or historical backfill.
- Only then construct a bounded, disabled DAPA shadow collector with idempotent canonical identifiers, same-source drift and no-publication tests, and a separate initial release decision. DAPA production is not declared ready by one green article readback.

**A RED result must not trigger alternate hosts, repeated requests, hidden API guessing or source reclassification.**
