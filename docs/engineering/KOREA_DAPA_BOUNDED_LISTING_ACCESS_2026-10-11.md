# Korea DAPA — limited robots-first listing access probe

**Created October 11, 2026. Status: code and synthetic tests; live Actions-runner publisher access NOT YET VERIFIED.** No source admission or legal-use approval is claimed.

## Grounded publisher and rights context

Existing source-family groundwork in [KOREA_DAPA_OFFICIAL_IDENTITY_PILOT_2026-10-11.md](KOREA_DAPA_OFFICIAL_IDENTITY_PILOT_2026-10-11.md) identifies the separate DAPA (방위사업청) portal filter `B00008`, distinct from the existing MND `A00005` government-policy portal lane. The issuer is DAPA; the publisher host is `www.korea.kr`. Its candidate Korean release documents may supply **HWPX and PDF** for the same event, never two independent issuing authorities.

Two official general notices were independently accessible during planning:
- Korea Policy Briefing publisher robots: https://www.korea.kr/robots.txt — observed as readable text/plain with `User-Agent: *`, `Allow: /` from the public research browser **on October 11**. **This does not prove GitHub Actions runner access or a legal reuse right.**
- Government Policy Briefing copyright: https://www.korea.kr/guide/copyRight.do — generally discusses KOGL Type 1 marked text, attribution and third-party media exceptions.
- Official KOGL types: https://www.kogl.or.kr/info/license.do — Type 0 is a real free-use category, distinct from Type 1. **Neither policy page confirms the exact license of a particular DAPA release or its HWPX/PDF attachments.**

The original October 8 DAPA source page was not retrievable through the accessible public-page reader in this session. Consequently, the prototype page markers from PR #378 remain **unverified fixture assumptions**, not server-observed DOM.

## Two-GET maximum protocol

This implementation adds `scripts/probe_korea_dapa_list_access.py`, not a collector. A live run is disabled by default. Only an authorized operator or a **separately manually dispatched GitHub workflow** with its explicit Boolean switch may make any publisher requests.

1. `GET https://www.korea.kr/robots.txt`: one request with a declared project research user agent, HTTP 200, exact URL/no redirect, expected text/plain and at most 32 KiB. A 403, challenge, HTML, empty or disallowing robots **ends the probe**, with **no listing request**.
2. Only if the publisher robots policy allows it, wait at least two seconds then perform one exact `GET` to `https://www.korea.kr/briefing/pressReleaseList.do?pWiseMinistry=ministryNews&repCode=B00008&repCodeType=%EC%A0%95%EB%B6%80%EB%B6%80%EC%B2%98`. Same-host/no-redirect/HTTP 200/text-html, 350 KiB body cap and 15-second timeout. A challenge or malformed listing is rejected.

If access succeeds, the HTML is inspected **in memory only** for publisher `newsId` link *shapes* already controlled by `review_korea_dapa_source_contract.article_identity()`. Output contains counts and at most six provisional numeric identity labels, never full titles, HTML, press-release text, HWPX/PDF bytes, metadata attachments, source documents or translated summaries. The source body is not retained or uploaded as an artifact.

**This filtered GET may be insufficient** if the actual portal requires POST or does not retain the DAPA filter under GET. In that case, report `metadata_access_observed_filter_not_verified`, **not** verified DAPA issuer-specific listing coverage. Zero source IDs means unknown selector/pagination/filter semantics, **not** zero DAPA publications. No automatic POST fallback, session token replay, hidden API guessing, cookies or circumvention is permitted.

## Permission and execution

After a separate deliberate operator decision, the manual Actions entry is `.github/workflows/korea_dapa_listing_access_canary.yml`, with the boolean acknowledgement `approve_one_time_official_listing_access`. The PR path **only executes no-network tests**; the manual run is an independent, later source-access decision.

Local equivalent for a read-only check:

```sh
python -m scripts.probe_korea_dapa_list_access --approve-one-time-access-check
```

A network observation must retain Actions run ID/attempt, original commit, exact UTC date, publisher host/filter, robots and listing access verdict, and whether the DAPA filter was **actually verified**. Keep raw publisher body out of GitHub issues, PRs and CI artifacts. A denial is a useful **blocked** result; do not retry through mirrors or rotating clients.

## Next independent qualification gates

- Source-specific first-party filter and visible issuer/date/title DOM comparison under separately reviewed access/terms; the synthetic prototype alone cannot verify this.
- One original article served from the portal and all HWPX/PDF link identities, original Korean text and document SHA comparisons, and rights per use type. A press-release page text mark is not necessarily an attachment/image license.
- An isolated, **disabled** DAPA adapter/manifest and eventually a separate shadow clock after owner approval; do not merge DAPA into the existing MND state, borrow its day-zero or add Korea to the public desk registry.
- Independent 7/14/30-day source reliability, original-language review, source-use permission and owner adjudication. Actual collecting days, not calendar elapsed time, are required.

**No new model input, scheduled publisher collection, production DB/output mutation, original-source retention, email, deployment or country desk promotion is included in this proposal.**
