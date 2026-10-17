# Korea DAPA: offline, private dated-row ↔ original-article evidence bridge

**Status 2026-10-17:** held identity-reconciliation groundwork only. This does NOT fetch government pages, schedule a collector, create an original-source record, certify the actual DAPA website JavaScript handler, or approve text reuse, translation or public publication.

## Production blocker and verified evidence

- [DAPA official press list](https://www.dapa.go.kr/dapa/doc/selectDocList.do?bbsSeq=326&menuSeq=3069): owner-authorized live run [39031062944](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39031062944) verified publisher robots and one HTML listing request; detected **10 date-bearing table rows** with interactive anchors, but **zero statically qualified article hrefs/docSeq IDs**.
- [PR #779](https://github.com/VSSpowerlifting/IndoPacificRecord/pull/779) added count-only classification of single-numeric versus complex navigation handlers. It was merged, but the enhanced live diagnostic has **not** been dispatched. Raw argument values remain unobserved by the official live canary.
- [PR #778](https://github.com/VSSpowerlifting/IndoPacificRecord/pull/778) installed a separately owner-gated one-off article GET probe. A successful *synthetic* PR test does not verify that live original article's contents, publisher issuance or rights; owner has not dispatched that separate live action.
- The official indexed press pages use stable `https://www.dapa.go.kr/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=...&menuSeq=3069` routes; some add read-only navigation query fields, which are removed to canonicalize. These URLs are an identity *format*, not evidence that any particular listing-row numeric argument equals an article ID.

## Offline reconciliation contract

`core/korea_dapa_private_identity_bridge.py` exposes **only** `reconcile(listing_raw_bytes, article_raw_bytes, article_url)`.

Both raw HTML byte sequences must be separately obtained and held **outside the public repository**, under explicitly approved future source requests. The module itself **has no HTTP client, CLI, file open/write, SQL, model, permissions, or production publication entry point**.

For a hypothetical matching input, the module:
1. Requires bounded HTML and exact UTF-8 decoding, rejects challenges, invalid source URL origins, duplicate/unknown query parameters and inconsistent docSeq.
2. Inspects table **date-bearing** rows; recognizes a *single literal numeric function argument* in one direct row click, never assuming displayed row order/ordinal is `docSeq`. Multicall/complex or duplicate rows HOLD.
3. Requires exactly one private row candidate with the same provisional numeric value as the exact DAPA article URL; requires the row's publisher date to match a separately visible article **게시일** date field. A mere date in embedded JavaScript or an unrelated article paragraph cannot satisfy this check.
4. Returns SHA-256 fingerprints and a **`PRIVATE_SELF_CONSISTENT_UNVERIFIED` receipt**, NOT a publication claim. Even in this success state the *real handler semantics, publisher-capture authentication, item-local issuer, original document bytes, third-party rights, editorial approval and production/public release authority are explicitly false*.
5. Never emits full HTML, Korean titles, article body, original HWPX/PDF, publisher JavaScript or unverified model-generated analysis. Private operator must keep returned provisional IDs/version hashes in private custody and out of public logs.

### Adversarial proof

Synthetic CI tests real date-label alignment, unrelated event dates, ambiguous duplicate numeric calls, two rows pointing to one number, different article date, displayed list ordinal confusion, off-domain origin, malformed query, redirects/unknown nav fields, challenge pages, bad Unicode, oversized pages, and all rights/publication booleans.

## Next actual production step (separate operator decisions)

After a *new owner-approved* [enhanced DAPA listing canary](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/workflows/korea_dapa_native_access_canary.yml) confirms that the actual dated rows exhibit an identifiable handler **shape**, and a separately approved [article canary](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/workflows/korea_dapa_single_article_canary.yml) proves one actual URL/date/response SHA, propose a bounded, **private-custody** evidence capture/review workflow. It must tie exact legitimate source bytes to their GitHub run/version, establish row-to-docSeq semantics and per-item issuer through authentic first-party evidence, preserve rights exceptions, and withstand drift/pagination before admitting a DAPA shadow collector.

Do not use this synthetic bridge to label the current 701 portal-list rows or 699 catalogue rows as 701/699 captured, authenticated, licensed original records. Annual `data.go.kr` catalogue and live `dapa.go.kr` list remain separate sources.
