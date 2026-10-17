# Korea DAPA official open-data catalogue — distinct metadata-only source lead

**Status: held for source qualification, not a collector or publishing licence.**
Tracked separately under issue #772. The source is the South Korean
Public Data Portal, `www.data.go.kr`, not DAPA's separately observed
`www.dapa.go.kr` dynamic release listing and not the `korea.kr` MND feed.

## Official publisher catalogue (observed October 16, 2026)

- Publisher: 방위사업청 (Defense Acquisition Program Administration)
- Catalogue: https://www.data.go.kr/data/15118819/fileData.do
- Published structured metadata: https://www.data.go.kr/catalog/15118819/fileData.json
- Catalogue name/version: `방위사업청_보도자료`, `방위사업청_보도자료_20260910`
- HWPX **format claim**, declared Type 1 attribution **licence claim**
- Registered, last modified and published September 12, 2026; **annual** update
- Portal page lists **699 rows**, but no individual file contents,
  article IDs, item-level copyright boundaries, verified source text, or
  validated record total have been inspected. Do **not** advertise 699
  new archival documents or equate it to 699 dated original releases.
- The data portal has a separate host and access rules from DAPA's
  first-party press list; previous DAPA canary approvals don't
  authorize downloading the portal's file.

## Safe offline qualification

`python -m scripts.qualify_korea_dapa_official_catalogue --metadata-file /path/to/owner-provided-official-schemaorg.json`

This command reads a **local file only** (at most 64 KiB), checks exact
publisher/domain/version/date/license/format/cadence metadata and emits
a small source-lead receipt with explicit `false` publication flags.
It never accesses the network, reads HWPX, writes an archive, interprets
"rows" as article identities, or acquires permission to use content.
Any variation in the publisher's metadata requires requalification.

The offline verifier is only the first step. It does **not**
independently authenticate the bytes as having come from the portal:
a verified origin, source-version SHA, robots policy and genuine
publisher data still require a separately owner-approved retrieval lane.

## Next evidence gates

1. Using a **separately authorized, robots-first**, bounded retrieval
   of `www.data.go.kr`, verify the exact schema.org JSON and the actual
   official HWPX download URL and size without fetching attachments
   indiscriminately; no redirects or hosts not previously authorized.
2. Preserve the exact authorized source snapshot and hash in private
   versioned custody, not public Git or broad Actions artifacts.
3. Inspect actual content offline to determine whether the "699 rows"
   represent separate documents, a catalogue count, or some other
   quantity. If the portal file contains only one compiled HWPX, do
   not invent records from the metadata label.
4. Independently verify each document's DAPA issuer, title, posted date,
   stable official identity and specific rights/third-party exceptions.
   Deduplicate the historical snapshot against the first-party live
   listing and existing Korea MND records. **List ordinal is not docSeq**.
5. Human-review qualified original text eligibility and keep HWPX,
   photos, external contributions, translations and analysis on
   distinct rights/editorial paths. No automatic public backfill.
6. DAPA live feed remains separate: a snapshot with annual cadence
   cannot prove continuous October 2026 production.

This change affects no collector, SQLite DB, original-text register,
English registry, translation or deployed Pages route.
