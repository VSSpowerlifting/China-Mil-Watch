# Indonesia and South Korea — bounded Actions verification, 2026-10-06

Ben authorized commit/PR and durable shadow collection, then reported PR #110
merged. GitHub confirms merge `a8e6d5a266cf6dadc664e899905a4ad9dbf47732`
at 2026-10-06 21:17:26 UTC. Its tree is identical to the reviewed PR head
`80f05b188c41dc9aea85d4ac0d71989cce975e44`; [full CI](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37529546274)
passed 3,478 tests with two skipped, launched Chromium, passed validation with
ten governed warnings and proved DB/output preservation.

Under the existing durable-collection authorization, one manual
`indonesia_korea_shadow.yml` run per desk used that exact merged collector.
Both runs used six lookback days and a forty-record cap. No target-date override
was supplied: each ledger records `manual-utc-date`, October 6, and the actual
execution timestamps. The selected window is September 30 through October 6.
No rehearsal state was transferred and no schedule was enabled.

## Observed runs and published state

| Measure | Indonesia | South Korea |
|---|---|---|
| Actions run | [37533271730](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37533271730) | [37533278839](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37533278839) |
| State branch | `shadow/indonesia-kemhan` | `shadow/korea-policy-briefing` |
| Published state commit | [`9fe9f6fd59c90ee8b01c9e940616828bad7a896c`](https://github.com/VSSpowerlifting/China-Mil-Watch/commit/9fe9f6fd59c90ee8b01c9e940616828bad7a896c) | [`a1088ea1514d0e603d21bb3f83c848c450ac5d85`](https://github.com/VSSpowerlifting/China-Mil-Watch/commit/a1088ea1514d0e603d21bb3f83c848c450ac5d85) |
| Previous state / sole parent | `8e9ee2e846a3fc99b339f41442dcb78d62c21d26` | `bbe2c8a25d55b18c55c74b499cd0525b5107c7f3` |
| Collection start, UTC | `2026-10-06T21:21:50.276764+00:00` | `2026-10-06T21:21:52.379252+00:00` |
| Collection finish, UTC | `2026-10-06T21:22:42.096593+00:00` | `2026-10-06T21:22:25.765638+00:00` |
| Selected / retrieved / extracted | 14 / 14 / 14 | 4 / 4 / 4 |
| Inserted / updated / duplicates | 0 / 0 / 14 | 0 / 0 / 4 |
| Fetch / extraction / access failures | 0 / 0 / 0 | 0 / 0 / 0 |
| Result / health | `ok_all_duplicates` / `ok` | `ok_all_duplicates` / `ok` |
| Listing pages / request captures | 2 / 17 | 1 / 10 |
| Current stored records | 14 | 4 |
| State files matched against artifact | 37 | 19 |
| Historical non-DB files preserved byte-for-byte | 19 | 12 |
| Historical complete DB rows preserved | 14 | 4 |
| Ledgers / distinct successful logical dates | 2 / 1 | 2 / 1 |

Both jobs actually collected and published; they did not stop at a scheduling
guard. Each passed all forty desk contract tests, the collector/historical-state
preservation step, its explicit non-force state-branch push and artifact upload.
Fresh robots were read with the full project collector identity. Requests stayed
within the Kemhan Berita and separate Policy Briefing scopes. MND publication
paths remained unrequested; no proxy, alternate egress or challenge workaround
was used.

## Independent integrity audit

The downloaded artifact ZIPs match their GitHub-reported sizes and SHA-256
digests. Every recognized state-file hash matches a fresh clone of the published
commit. Both clones contain only `state/` in their committed trees, have the
correct branch/origin, and retain their original parentless initial commit.
The new commits each have the prior published head as their sole parent.

Every historical capture, ledger and clock matches the initial Git blob. Every
column of every historical record matches the initial DB snapshot. The SQLite
file hashes themselves are unchanged before/after each collection. Original
first-success clocks remain:

- Indonesia: `2026-10-06T16:52:15.008737+00:00`, run
  `local-native-20261006-indonesia`.
- South Korea: `2026-10-06T16:52:01.420713+00:00`, run
  `local-native-20261006-korea`.

The pinned-state reviewer exported each new commit as of October 6 and found
zero machine integrity findings or missing logical dates. Human review and
promotion fields remain false. These packets supply no source/document
comparison or human checkpoint approval.

Main remained at the owner's merged commit after both runs. The workflow's
preservation checks passed; no production collection, rendering, deployment,
model call or public desk admission occurred in these manual runs.

Complete attempt artifacts are linked from the two Actions runs and retained
for ninety days. Their digests are
`3dd5a1553194349177a628b85b19fc8ad04f2c95ef73c8125d62b8cec28f2dc3`
(Indonesia, artifact `11445535086`) and
`7439e0d5bb4cb77bbfa7deee9efa933fff9f5163d0bbaba76418dea656f56668`
(South Korea, artifact `11444359560`).
Supplementary local evidence, including the audit JSON, downloaded artifacts,
workflow logs and pinned packets, is under
`/private/tmp/ipr-id-kr-actions-37533271730-37533278839/`.
The published orphan commits remain the durable collection evidence after
artifact expiry; neither state branch is merged into main.

## Remaining decisions

This verifies one bounded main-hosted run per desk and append-only persistence
from the existing state. Two successful attempts on October 6 still represent
one logical collecting date. Future access, multi-day reliability, historical
completeness, extraction/document review, source reuse terms and cadence/silence
thresholds remain unproved or unresolved as described in the candidate READMEs.

Scheduling remains off and requires separate owner authorization of cadence and
logical-date slots. Days 7, 14 and 30 require actual human checkpoints. Thirty
consecutive collecting days, sufficient corpus and owner sign-off remain
prerequisites for any separate production promotion. Neither desk is qualified.
