# Standing-license fast lane — text first, not seven independent launch projects

**October 15, 2026 — engineering policy, pending production deployment.**

We should **stop treating every government document as requiring a new person to
approve the same publisher-wide license**. For first-party government text
covered by a verified standing reuse policy, software can qualify each new
version against that policy and publish it once its original-byte integrity
checks succeed. This is the immediate route to a functioning text archive.

## Real public reuse terms

- **Japan MOD/SDF** — [official Japanese content use conditions](https://www.mod.go.jp/j/info/contents.html) and [official English terms](https://www.mod.go.jp/en/notice.html): source content can generally be copied, publicly transmitted, translated and modified, including commercially, with attribution and a description of changes. The Japanese notice references PDL1.0. It excludes third-party rights, reserved marks and content subject to other notices. The first automated lane is **first-party MOD original text only**. We do not assume a PDF's embedded photos, commissioned diagrams or logos share the text license.
- **Republic of Korea Policy Briefing** — [copyright policy](https://www.korea.kr/guide/copyRight.do) and [KOGL Type 1 terms](https://www.kogl.or.kr/info/licenseType1.do): **the individual article must bear the permitted Type 1 marking**; attributably licensed text supports reuse and derivative translations. It does not license arbitrary photos or complete HWPX attachments. Korea is **item-mark gated**, not all-`korea.kr` gated.
- Singapore MINDEF, Philippine AFP, Indonesian Kemhan, Vietnamese departments, Japanese Coast Guard, other Chinese agencies and U.S. sources do **not** inherit either policy. Separate standing terms could later be added after documented research. Do not guess public-domain status from a government hostname.

These conditions govern **copyright/license eligibility**, not the source's
factual truth, translator's accuracy or the quality of IPR analysis.

## Implementation

`core/standing_source_rights.py` provides two allowlisted policy definitions
and `qualify_standing_text()`, a deterministic, network-free qualification
function for the two text scopes `original_text` and `translation_en`.

Each eligibility decision requires:

1. An exact first-party government source family, HTTPS publisher origin,
   immutable source Git commit, captured-content SHA256, language and date.
2. An **independently authenticated replay** of the original captured source.
3. An independently authenticated **current publisher policy observation**,
   including real policy URL, SHA, full conditions, no changes/revocations, and
   observation within 7 days of the release attempt. No per-item human
   copyright signoff once this *family* policy is operational.
4. An independently authenticated **item exception scan** confirming original
   first-party text, no third-party wording, alternate terms, media, protected
   personal information or secrets. On Korea, additionally verify the exact
   item's Type 1 license marking from the frozen source capture.
5. For an **original text** public candidate, the exact proposed output
   SHA256 must match the independently authenticated complete text SHA256.
   For translations, the rights lane verifies **derivative-use eligibility
   only** and explicitly leaves bilingual/editor approval FALSE.
6. Appropriate source attribution and an **unofficial translation/change
   notice**. Nothing claims publisher endorsement.

The receipts contain only identities, hashes, dates, explicit license scope,
and HOLD-safe flags; no original source bodies or model outputs.

**Important security constraint:** callbacks supplied as
`source_replay`, `policy_replay`, `exception_replay` and optional
`item_license_replay` are integration points for the already authenticated
source ledger/policy scanner, **not** permissions that a caller may self-declare.
A production writer MUST supply trusted implementations and revalidate the
original source before accepting any receipt. An arbitrary supplied receipt or
fake success callback has no authority on its own. This PR does not install
those production verifiers and cannot deploy a website.

## What changes in the full-content release policy

The earlier full-content [PR #699](https://github.com/VSSpowerlifting/IndoPacificRecord/pull/699)
needs this exception to its overly repetitive **per-record rights reviewer**:

| Output | New standing policy | Keep independent check |
|---|---|---|
| Authentic first-party Japan MOD original text | Family policy plus automatic exact source and exception replay; **no per-item rights signature** | Valid preserved original/complete extraction and metadata |
| Authentic Korea Policy Briefing KOGL Type 1 text | Family policy plus **per-item automated Type 1 mark verification**; **no per-item rights signature** | Original extraction, actual item mark, attribution |
| English translation of either text | Standing **derivative rights** need no separate person checking copyright | Bilingual accuracy/editorial signoff on exact final version |
| Independently authored IPR analysis | No publisher republication rights required to **write original analysis citing facts and links**, provided protected expression is not copied | Actual source-linked factual claims, editor approval, AI-source attribution |
| PDFs, images, attachments, publisher logos | **Not included** in these text grants | Independently cleared asset/full-document permissions, or skip them |

## Fastest real activation sequence

1. Deploy *one* standing MOD policy snapshot validator that monitors only the
   official MOD policy page; log SHA and 7-day freshness. A policy change
   auto-HOLDs all affected source families until reviewed.
2. Use the **existing preserved collector source Git** to produce an exact
   text-only original from a MOD record, and bind its clean body SHA to the
   original capture. No need to build another collector or review the same
   terms 30 times.
3. Admit the text with the verified standing reuse receipt into the **shared**
   production content index. Avoid allocating another migration `0008`;
   Korea's metadata schema already occupies that number.
4. Add one safe page template with original government text, actual license and
   source attribution; omit all images and derivative wording.
5. Release through serialized `main`/Pages writer and prove source Git SHA →
   original bytes → SQLite → published page bytes, including a genuinely new
   scheduled original. A zero-new record scheduled run does not prove a new
   article has automatically gone live.
6. Extend to Korea when actual individual KOGL marks are independently
   captured. Expand country families by adding publisher policies, not by
   inventing more one-off workflow types.

**Do not put translation or unreviewed machine-authored geopolitical analysis on
the fully unattended original-text route.** Producing a draft automatically is
fine; publishing factual claims needs an editor and reliable evidence.
