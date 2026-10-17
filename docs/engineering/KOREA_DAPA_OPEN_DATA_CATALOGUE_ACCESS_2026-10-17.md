# Korea DAPA catalogue — operator-authorized metadata-only access gate

**Created:** 2026-10-17. **Status:** Offline tests and operator-gated probe only. Not a collector, rights clearance, source-text mirror or production bridge.

The earlier owner-authorized [DAPA first-party list canary](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39031062944) used `www.dapa.go.kr`. Its approval does **not** carry over to the distinct South Korean official public-data portal, `www.data.go.kr`.

Official DAPA open-data catalogue **15118819** is a *separate annual snapshot lead*, identified by the metadata-only offline qualification in PR #773:
- `https://www.data.go.kr/data/15118819/fileData.do` (catalogue description, NOT an HWPX download)
- `https://www.data.go.kr/catalog/15118819/fileData.json` (exact machine-readable public metadata record)
- Claimed DAPA publisher; version `방위사업청_보도자료_20260910`; HWPX *format metadata*; attributed Type 1 *licence metadata*; annual update; reported **699 rows** (not verified article count).

## Exact opt-in test

Workflow `.github/workflows/korea_dapa_catalogue_metadata_access.yml` allows **offline synthetic tests for pull requests** and one *independently owner-approved* live dispatch only from `main`:

1. Owner manually checks `approve_one_time_data_go_kr_metadata` for this NEW hostname and scope.
2. One `GET https://www.data.go.kr/robots.txt`. HTTP 200, exact destination, text/plain, 32KiB limit, 15s deadline, no redirects, cookie handling or retry. Stop on challenge/denial/robots-unreadable.
3. If robots allows the *exact* metadata JSON route, pause two seconds; fetch only `https://www.data.go.kr/catalog/15118819/fileData.json` with a hard 64KiB cap, JSON content-type and 15s timeout. No other URL.
4. Parse JSON only in memory. Reuse the strict source-identity/version/date/issuer/format/licence *claim* validator from PR #773. If qualified, report the exact JSON SHA-256 plus a metadata-only, no-article, no-rights receipt. If anything differs, HOLD on a fixed reason without printing the source JSON.

At most two allowed requests. Never follow an HWPX link, fetch a press article, scrape the portal, store source bytes in GitHub artifacts, create a DB record, email a draft, publish or change Pages. No 699 article count is credited from the metadata alone. Only the pre-existing public dataset name/version is logged, not arbitrary official-page text.

## Further independent gates

A green probe would establish live exact-source provenance for one catalogue **metadata version**, NOT the resource file contents. A separately reviewed decision would then be needed for any binary download, private custody and bounded extraction. Verify each row's document nature, DAPA issuer/date and stable first-party identity and content rights; dedupe with the interactive DAPA press list and current MND. **Annual snapshot coverage is not current-day DAPA coverage** and cannot replace the separate feed.

A RED probe can signify denial, host unavailability, unexpected type or metadata drift; it must not trigger automatic alternate host/API/redirects or increased privileges.
