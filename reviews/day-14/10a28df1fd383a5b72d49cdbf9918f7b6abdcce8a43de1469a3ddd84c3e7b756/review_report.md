# Singapore shadow review — day-14 — shadow_day 14 (as of 2026-09-02)

> **An unfilled report is not evidence of a completed review.** The
> automated checks below establish that the state is internally
> consistent. They do not establish that the stored records match what
> the ministry published. Only the reviewer sign-off section does that,
> and only once every field in it is filled in by a person.

| | |
|---|---|
| Deterministic package id | `724a8a2457c8cda92df8ed04b8547f086d448bda55e8e6ac87d366cd64524042` |
| Tool | `scripts/review_shadow_state.py` v1.1.0 |
| State commit (verified) | `5fa49c81b9250b7723eb5f707f8c71d86d051903` |
| State tree | `ea29908033de29afeba03d318217d6bc6abb3bfd` |
| Reachable from | `shadow/singapore-mindef` |
| Provenance | git-verified-tree/1 |
| Collector commit (latest ledger) | `767adf5e745727ef890d90f63223671f562ff38e` |
| Day zero | `2026-08-19T23:03:09+00:00` (run `32311419939`) |
| Latest ledger | `20260902T231841+0000-33694377692.json` |
| Latest shadow_day | **14** |
| Ledgers | 15 |
| Corpus | 40 records, 2026-07-21 → 2026-09-01 |
| Database integrity | ok |
| Foreign keys | clean |
| State-hash chain | coherent |
| Anomalies | 2 |

## Automated integrity

**2 anomaly/anomalies. Each must be explained before this checkpoint can pass.**

- no ledger for 2026-08-26, inside the observed collection period
- no ledger for 2026-08-31, inside the observed collection period

## Run chronology

| Ledger | Run | Finished (UTC) | Day | Result | Health | Disc | Sel | Retr | Ins | Dup | Fetch✗ | Extr✗ | Acc✗ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `20260819T230309+0000-32311419939.json` | 32311419939 | 2026-08-19T23:03:09 | 0 | `ok` | ok | 30 | 30 | 30 | 30 | 0 | 0 | 0 | 0 |
| `20260820T214150+0000-32420519429.json` | 32420519429 | 2026-08-20T21:41:50 | 0 | `ok` | ok | 32 | 32 | 32 | 2 | 30 | 0 | 0 | 0 |
| `20260821T213745+0000-32529241923.json` | 32529241923 | 2026-08-21T21:37:45 | 1 | `ok_all_duplicates` | ok | 27 | 27 | 27 | 0 | 27 | 0 | 0 | 0 |
| `20260822T213501+0000-32599922013.json` | 32599922013 | 2026-08-22T21:35:01 | 2 | `ok_all_duplicates` | ok | 27 | 27 | 27 | 0 | 27 | 0 | 0 | 0 |
| `20260823T213528+0000-32667896409.json` | 32667896409 | 2026-08-23T21:35:28 | 3 | `ok_all_duplicates` | ok | 23 | 23 | 23 | 0 | 23 | 0 | 0 | 0 |
| `20260824T214310+0000-32780829454.json` | 32780829454 | 2026-08-24T21:43:10 | 4 | `ok` | ok | 24 | 24 | 24 | 1 | 23 | 0 | 0 | 0 |
| `20260825T214204+0000-32902223353.json` | 32902223353 | 2026-08-25T21:42:04 | 5 | `ok` | ok | 25 | 25 | 25 | 2 | 23 | 0 | 0 | 0 |
| `20260827T004724+0000-33027905549.json` | 33027905549 | 2026-08-27T00:47:24 | 7 | `ok` | ok | 24 | 24 | 24 | 2 | 22 | 0 | 0 | 0 |
| `20260828T052246+0000-33144486791.json` | 33144486791 | 2026-08-28T05:22:46 | 8 | `ok` | ok | 25 | 25 | 25 | 1 | 24 | 0 | 0 | 0 |
| `20260829T031047+0000-33230667685.json` | 33230667685 | 2026-08-29T03:10:47 | 9 | `ok` | ok | 26 | 26 | 26 | 1 | 25 | 0 | 0 | 0 |
| `20260829T231734+0000-33280560119.json` | 33280560119 | 2026-08-29T23:17:34 | 10 | `ok_all_duplicates` | ok | 26 | 26 | 26 | 0 | 26 | 0 | 0 | 0 |
| `20260830T232846+0000-33341845783.json` | 33341845783 | 2026-08-30T23:28:46 | 11 | `ok_all_duplicates` | ok | 24 | 24 | 24 | 0 | 24 | 0 | 0 | 0 |
| `20260901T003717+0000-33455386368.json` | 33455386368 | 2026-09-01T00:37:17 | 12 | `ok_all_duplicates` | ok | 22 | 22 | 22 | 0 | 22 | 0 | 0 | 0 |
| `20260901T231800+0000-33570252031.json` | 33570252031 | 2026-09-01T23:18:00 | 13 | `ok` | ok | 23 | 23 | 23 | 1 | 22 | 0 | 0 | 0 |
| `20260902T231841+0000-33694377692.json` | 33694377692 | 2026-09-02T23:18:41 | 14 | `ok_all_duplicates` | ok | 23 | 23 | 23 | 0 | 23 | 0 | 0 | 0 |

## Count reconciliation

| Ledger | inserted | cumulative | stored_total | agrees |
|---|---|---|---|---|
| `20260819T230309+0000-32311419939.json` | 30 | 30 | 30 | yes |
| `20260820T214150+0000-32420519429.json` | 2 | 32 | 32 | yes |
| `20260821T213745+0000-32529241923.json` | 0 | 32 | 32 | yes |
| `20260822T213501+0000-32599922013.json` | 0 | 32 | 32 | yes |
| `20260823T213528+0000-32667896409.json` | 0 | 32 | 32 | yes |
| `20260824T214310+0000-32780829454.json` | 1 | 33 | 33 | yes |
| `20260825T214204+0000-32902223353.json` | 2 | 35 | 35 | yes |
| `20260827T004724+0000-33027905549.json` | 2 | 37 | 37 | yes |
| `20260828T052246+0000-33144486791.json` | 1 | 38 | 38 | yes |
| `20260829T031047+0000-33230667685.json` | 1 | 39 | 39 | yes |
| `20260829T231734+0000-33280560119.json` | 0 | 39 | 39 | yes |
| `20260830T232846+0000-33341845783.json` | 0 | 39 | 39 | yes |
| `20260901T003717+0000-33455386368.json` | 0 | 39 | 39 | yes |
| `20260901T231800+0000-33570252031.json` | 1 | 40 | 40 | yes |
| `20260902T231841+0000-33694377692.json` | 0 | 40 | 40 | yes |

Corpus in database: **40**. Sum of insertions: **40**.

## Corpus overview

| Publication kind | Records |
|---|---|
| news release | 21 |
| speech | 10 |
| parliamentary question | 4 |
| fact sheet | 2 |
| ministerial question | 2 |
| other | 1 |
| **total** | **40** |

Body length (characters): min **608**, p25 2571, median 3522, p75 5510, max **19766**.

The collector refuses a body under 200 characters, so a shorter body here would contradict the collector that wrote it. No length is treated as proof of completeness — that is a reviewer judgement.

## Title collisions

None. Every stored title is unique in this corpus.

## Content-change history

Records are first-writer-wins on canonical URL, so the collector never rewrites a stored body. Insertions by run:

- `20260819T230309+0000-32311419939.json` — 30 inserted
- `20260820T214150+0000-32420519429.json` — 2 inserted
- `20260824T214310+0000-32780829454.json` — 1 inserted
- `20260825T214204+0000-32902223353.json` — 2 inserted
- `20260827T004724+0000-33027905549.json` — 2 inserted
- `20260828T052246+0000-33144486791.json` — 1 inserted
- `20260829T031047+0000-33230667685.json` — 1 inserted
- `20260901T231800+0000-33570252031.json` — 1 inserted

## Human review queue — 16 of 40 records

Selection: `shadow-review-queue/1`. Every reason is a property of the data, so the same state always produces the same queue. This is a targeted queue, **not a statistically representative sample**, and no inference about unreviewed records follows from it.

### `https://www.mindef.gov.sg/news-and-events/latest-releases/12aug26-fs/`

- **Title:** Fact Sheet: The Defence Scholarships and Profiles of Scholarship Recipients
- **Stored date:** 2026-08-12 · **kind:** fact sheet · **body:** 5510 chars
- **Content sha256:** `f9be1045cfd9759753faac9b9ec775348eef5ecb79e6e0869eaac3b1b8368d47`
- **First seen in run:** 32311419939
- **Queued because:** kind-representative:fact sheet

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

### `https://www.mindef.gov.sg/news-and-events/latest-releases/12aug26-nr1/`

- **Title:** Chief of Staff, Japan Joint Staff Makes Introductory Visit to Singapore
- **Stored date:** 2026-08-12 · **kind:** news release · **body:** 1856 chars
- **Content sha256:** `681b6f44d4158ef8bef329b1145396fe22769e300d58878923266f1603708c24`
- **First seen in run:** 32311419939
- **Queued because:** kind-representative:news release

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

### `https://www.mindef.gov.sg/news-and-events/latest-releases/12aug26-speech/`

- **Title:** Speech by Minister for Defence Chan Chun Sing at the Defence Scholarship Awards Ceremony at Temasek Club on 12 August 2026
- **Stored date:** 2026-08-12 · **kind:** speech · **body:** 5932 chars
- **Content sha256:** `f6de1e4337ed85f23f372d5d925e09590b231d45981532227bcc433f6c0f34bb`
- **First seen in run:** 32311419939
- **Queued because:** kind-representative:speech

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

### `https://www.mindef.gov.sg/news-and-events/latest-releases/14aug26-mq/`

- **Title:** Media Reply on Charging of ME1 Tay Yi Cong
- **Stored date:** 2026-08-14 · **kind:** ministerial question · **body:** 608 chars
- **Content sha256:** `6de3c44d47ab65fc650eaf64203bb1601d117c7d573dadf24ec7e1ccfe895eb3`
- **First seen in run:** 32311419939
- **Queued because:** kind-representative:ministerial question; shortest-substantive-body

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

### `https://www.mindef.gov.sg/news-and-events/latest-releases/15aug26-speech/`

- **Title:** Speech by Minister for Defence Chan Chun Sing at the Tanjong Pagar GRC, Queenstown and Radin Mas SMCsâ 61st National Day Dinner on 15 Aug 2026 at Tanjong Pagar Community Club
- **Stored date:** 2026-08-15 · **kind:** speech · **body:** 19766 chars
- **Content sha256:** `0f51eca7930a5b5f9421a190d64f01c104d76200a03560429ece705aa8d62389`
- **First seen in run:** 32311419939
- **Queued because:** longest-body

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

### `https://www.mindef.gov.sg/news-and-events/latest-releases/1sep26-mq/`

- **Title:** Reply to Media Query on NS60 Commemorative and Recognition Efforts
- **Stored date:** 2026-09-01 · **kind:** ministerial question · **body:** 2632 chars
- **Content sha256:** `99c8b918117e05c719a1e3973a21df27e62abec249133a21c3febe6a9d1b8bc8`
- **First seen in run:** 33570252031
- **Queued because:** new-since-20260827T004724+0000-33027905549.json; newest

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

### `https://www.mindef.gov.sg/news-and-events/latest-releases/20aug26-speech/`

- **Title:** Speech by Minister of State, Ministry of Digital Development and Information and Ministry of Health, Ms Rahayu Mahzam at the 68/26 Specialist Cadet Graduation Parade on 20 Aug 2026
- **Stored date:** 2026-08-20 · **kind:** speech · **body:** 8166 chars
- **Content sha256:** `13c8a712d151a8b965e9b0a7d24ed1c6ae5fdf95d9361680e6455211cd76524e`
- **First seen in run:** 32420519429
- **Queued because:** hash-selected-remainder

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

### `https://www.mindef.gov.sg/news-and-events/latest-releases/21jul26-nr/`

- **Title:** DIS and DSTA Collaborate with IBM to Explore Quantum Computing for Mission Planning, Logistics Optimisation
- **Stored date:** 2026-07-21 · **kind:** news release · **body:** 3677 chars
- **Content sha256:** `3c0399f3eb78b74da46aa63048ef92b14cc65129425331379523eecbc7311261`
- **First seen in run:** 32311419939
- **Queued because:** oldest

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

### `https://www.mindef.gov.sg/news-and-events/latest-releases/21jul26-nr3/`

- **Title:** 202 Appointed as Senior Military Experts
- **Stored date:** 2026-07-21 · **kind:** news release · **body:** 3392 chars
- **Content sha256:** `0fc547dfc165daa04ceb2e682cd0f81f20d3a6db5115c1d37c26bd878f413ab2`
- **First seen in run:** 32311419939
- **Queued because:** hash-selected-remainder

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

### `https://www.mindef.gov.sg/news-and-events/latest-releases/25aug26-speech/`

- **Title:** Speech by Minister for Defence Chan Chun Sing at the NDP 2026 Appreciation Function on 25 Aug 2026
- **Stored date:** 2026-08-25 · **kind:** speech · **body:** 6423 chars
- **Content sha256:** `2f6a20b9b6398602ef250feecb7d57f5bc4f765e974d47ddbbbe66bc6455c6f9`
- **First seen in run:** 32902223353
- **Queued because:** hash-selected-remainder

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

### `https://www.mindef.gov.sg/news-and-events/latest-releases/27aug26-nr/`

- **Title:** RSIS 7th Trilateral Exchange 2026 Examines the  Next Phase of US-China Relations
- **Stored date:** 2026-08-27 · **kind:** news release · **body:** 4302 chars
- **Content sha256:** `52d8f421c0f05e604b242639e69be923a4a3d503397dfdf44c6ad08d1b918894`
- **First seen in run:** 33144486791
- **Queued because:** new-since-20260827T004724+0000-33027905549.json

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

### `https://www.mindef.gov.sg/news-and-events/latest-releases/27jul26-speech/`

- **Title:** Remarks by Minister for Defence Chan Chun Sing at the 15th Singapore-Australia Joint Ministerial Committee Joint Press Conference at Commonwealth Parliament Office, Adelaide
- **Stored date:** 2026-07-27 · **kind:** speech · **body:** 5435 chars
- **Content sha256:** `1aa3b1650d8519d3b316a9df6382eef20421f2a6f0c838a707fd4f70ba614956`
- **First seen in run:** 32311419939
- **Queued because:** hash-selected-remainder

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

### `https://www.mindef.gov.sg/news-and-events/latest-releases/29aug26-nr/`

- **Title:** Singapore Navy and Japan Maritime Self-Defense Force Successfully Conclude Exercise Singapan
- **Stored date:** 2026-08-29 · **kind:** news release · **body:** 1973 chars
- **Content sha256:** `ece7e2c934045b7f5c5593f546022254d75363be68792747e677d6c3e29a8976`
- **First seen in run:** 33230667685
- **Queued because:** new-since-20260827T004724+0000-33027905549.json

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

### `https://www.mindef.gov.sg/news-and-events/latest-releases/30jul26-nr2/`

- **Title:** RSN Participates in Largest Edition of Multinational Naval Exercise RIMPAC 2026
- **Stored date:** 2026-07-30 · **kind:** news release · **body:** 5065 chars
- **Content sha256:** `0200826799a7a1581d79be18d96480165aa3ddf50c5da666f3597edde7c53bbf`
- **First seen in run:** 32311419939
- **Queued because:** hash-selected-remainder

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

### `https://www.mindef.gov.sg/news-and-events/latest-releases/31jul26-fr/`

- **Title:** MINDEFâs Reply to STâs Forum Letter: &quot;MINDEF should pay artistes for their work&quot;
- **Stored date:** 2026-07-31 · **kind:** other · **body:** 1529 chars
- **Content sha256:** `5cc8e7a6c537ad584dfc94dc9debcb5dabbe37560335e91c6d573a68100af357`
- **First seen in run:** 32311419939
- **Queued because:** kind-representative:other

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

### `https://www.mindef.gov.sg/news-and-events/latest-releases/4aug26-pq/`

- **Title:** Written Reply by Minister for Defence Chan Chun Sing to Parliamentary Question on NDP Balloting System on 4 Aug 2026
- **Stored date:** 2026-08-04 · **kind:** parliamentary question · **body:** 1687 chars
- **Content sha256:** `ddb1f02e251165eccbd4908074492dab71d2609c4ead10fad3917e92fc30db7f`
- **First seen in run:** 32311419939
- **Queued because:** kind-representative:parliamentary question

| Check | Reviewer entry |
|---|---|
| Source page opened | |
| Title matches the page | |
| Publication date matches the page | |
| Stored body is the complete document | |
| Canonical URL is correct | |
| Publication kind is reasonable | |
| No access-denial or template text stored | |
| Notes | |

## Reviewer sign-off

This checkpoint is complete only when every row above is filled in and this block is signed. Until then the package is a request for a review, not a record of one.

| Field | Entry |
|---|---|
| Checkpoint | day-14 — shadow_day 14 (as of 2026-09-02) |
| Reviewer identity | |
| Review completion timestamp (UTC) | |
| Records reviewed against source | |
| Anomalies accepted, with reasons | |
| Verdict (continue / pause / stop) | |

