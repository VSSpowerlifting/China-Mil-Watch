# Singapore shadow review — day-07 — shadow_day 7 (as of 2026-08-27)

> **An unfilled report is not evidence of a completed review.** The
> automated checks below establish that the state is internally
> consistent. They do not establish that the stored records match what
> the ministry published. Only the reviewer sign-off section does that,
> and only once every field in it is filled in by a person.

| | |
|---|---|
| Deterministic package id | `2b58c9b2c1b737cec5a2b1a02926914ce411a7544bb02126ee3b56087e1fbbfd` |
| Tool | `scripts/review_shadow_state.py` v1.1.0 |
| State commit (verified) | `f806335e485959173d9ac6177efc32d5e3052949` |
| State tree | `1f47665e6b314cd84bd34cf07d1ef4f984969f68` |
| Reachable from | `shadow/singapore-mindef` |
| Provenance | git-verified-tree/1 |
| Collector commit (latest ledger) | `c16492c622e0a577a208f44ba15ea723cd069af3` |
| Day zero | `2026-08-19T23:03:09+00:00` (run `32311419939`) |
| Latest ledger | `20260827T004724+0000-33027905549.json` |
| Latest shadow_day | **7** |
| Ledgers | 8 |
| Corpus | 37 records, 2026-07-21 → 2026-08-26 |
| Database integrity | ok |
| Foreign keys | clean |
| State-hash chain | coherent |
| Anomalies | 1 |

## Automated integrity

**1 anomaly/anomalies. Each must be explained before this checkpoint can pass.**

- no ledger for 2026-08-26, inside the observed collection period

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

Corpus in database: **37**. Sum of insertions: **37**.

## Corpus overview

| Publication kind | Records |
|---|---|
| news release | 19 |
| speech | 10 |
| parliamentary question | 4 |
| fact sheet | 2 |
| ministerial question | 1 |
| other | 1 |
| **total** | **37** |

Body length (characters): min **608**, p25 2571, median 3522, p75 5840, max **19766**.

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

## Human review queue — 37 of 37 records

Selection: `shadow-review-queue/1`. Every reason is a property of the data, so the same state always produces the same queue. This is a targeted queue, **not a statistically representative sample**, and no inference about unreviewed records follows from it.

### `https://www.mindef.gov.sg/news-and-events/latest-releases/12aug26-fs/`

- **Title:** Fact Sheet: The Defence Scholarships and Profiles of Scholarship Recipients
- **Stored date:** 2026-08-12 · **kind:** fact sheet · **body:** 5510 chars
- **Content sha256:** `f9be1045cfd9759753faac9b9ec775348eef5ecb79e6e0869eaac3b1b8368d47`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/12aug26-nr2/`

- **Title:** 101 Award Recipients, One Defence Community
- **Stored date:** 2026-08-12 · **kind:** news release · **body:** 3982 chars
- **Content sha256:** `ee1544bccf9c31b965f53f510b4a598a22906df5903249e275116e30f5792a43`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/13aug26-speech/`

- **Title:** Speech by Minister for Defence Chan Chun Sing at the 20th Public Health and Occupational Medicine Conference on 12 August 2026 at Temasek Club
- **Stored date:** 2026-08-13 · **kind:** speech · **body:** 11323 chars
- **Content sha256:** `b2aa14ab4eaa8680060219826972d4cf220fab83a1f3d50b65d5fb736e3bf434`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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
- **Queued because:** review-all

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
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/20aug26-nr/`

- **Title:** 1173 Graduate as SAF Specialists and Military Experts
- **Stored date:** 2026-08-20 · **kind:** news release · **body:** 3032 chars
- **Content sha256:** `80e4f897a084b1596fa90ecfce8920241f3854328877b273c9487607ed77eca1`
- **First seen in run:** 32420519429
- **Queued because:** review-all

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
- **Queued because:** review-all

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
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/21jul26-nr2/`

- **Title:** Defence Officials and Experts Discuss Building Digital and Information Resilience at the Fourth Digital Defence Symposium
- **Stored date:** 2026-07-21 · **kind:** news release · **body:** 6090 chars
- **Content sha256:** `9d36a368acd2a07b1e04c8fc7e853c581991a04e61ed68e20ff7ed67ff840329`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/21jul26-speech/`

- **Title:** Opening Remarks by Permanent Secretary (Defence), Mr Joseph Leong, at the 4th Digital Defence Symposium Official Dinner on 20 Jul 2026 at 1900H
- **Stored date:** 2026-07-21 · **kind:** speech · **body:** 10084 chars
- **Content sha256:** `83b8f4a17acbd9ade5b865e96fda0708fe2e3f11df94a60d4f8ddee1ae05935a`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/21jul26-speech2/`

- **Title:** Speech by Minister of State for Defence, Mr Desmond Choo at the 31/26 SAF Senior Military Expert Appointment Ceremony on 21 July 2026 at Temasek Club
- **Stored date:** 2026-07-21 · **kind:** speech · **body:** 9554 chars
- **Content sha256:** `655aeb6731df985ef00a12cf36528cb176b9b4673d3bb046fe536ab329b22a25`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/23jul26-nr/`

- **Title:** Permanent Secretary (Defence) Mr Joseph Leong Visits Indonesia  to Co-Chair the 3rd Defence Cooperation Committee Meeting
- **Stored date:** 2026-07-23 · **kind:** news release · **body:** 2581 chars
- **Content sha256:** `6f9ab978fd6ffd03dead12a892821e518e462056cc5b9fbe87eb8509e68611cd`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/23jul26-nr2/`

- **Title:** Launch of the Singapore Navyâs Second Multi-Role Combat Vessel
- **Stored date:** 2026-07-23 · **kind:** news release · **body:** 3617 chars
- **Content sha256:** `8f10e3f22eab2753e199c12a1bc884b6788eca78ed6dcb0a3ef56470f03ddb6c`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/23jul26-nr3/`

- **Title:** Singapore and Malaysian Air Forces Successfully Concluded Annual Bilateral Search and Rescue Exercise
- **Stored date:** 2026-07-23 · **kind:** news release · **body:** 3357 chars
- **Content sha256:** `70069e337d24392ef20735b515b8cde8456763900da346001293e9dde2c0eb75`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/23jul26-speech/`

- **Title:** Transcript of Speech by Mr K Shanmugam, Coordinating Minister for National Security and Minister for Home Affairs, at the Launch Ceremony of the Republic of Singapore Navy&#x27;s 2nd Multi-Role Combat Vessel, Valour, 23 July 2026
- **Stored date:** 2026-07-23 · **kind:** speech · **body:** 5840 chars
- **Content sha256:** `398eb1f14f6660434005d2cc0b2a4ef7dc0279c3c87616d6a7dc9f9183169a09`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/24aug26-nr/`

- **Title:** Chief of Army of the Malaysian Armed Forces Makes Introductory Visit to Singapore, Reaffirms Warm and Long-standing Defence Ties
- **Stored date:** 2026-08-24 · **kind:** news release · **body:** 2347 chars
- **Content sha256:** `a27e7c1e5a216d6cde24884fdc7b1a62c58265198ae5004baacf4403b46851ef`
- **First seen in run:** 32780829454
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/25aug26-nr/`

- **Title:** Minister for Defence Thanks NDP 2026âs Organisers, Participating Organisations and Sponsors
- **Stored date:** 2026-08-25 · **kind:** news release · **body:** 3522 chars
- **Content sha256:** `6b1e9ec6a78bbfab4bf93652896e046d46de5303000162b89c917e08389b1f78`
- **First seen in run:** 32902223353
- **Queued because:** review-all

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
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/25jul26-nr/`

- **Title:** Singapore&#x27;s Defence is a Shared Responsibility â And More are Answering the Call
- **Stored date:** 2026-07-25 · **kind:** news release · **body:** 6410 chars
- **Content sha256:** `43e3cd39925aac7a26c499821f085a8b85e176a86f7184a32689c2fd77fe8232`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/26aug26-nr/`

- **Title:** From Classroom to Command: NCC Marks 125 Years With Bold Plans for the Future
- **Stored date:** 2026-08-26 · **kind:** news release · **body:** 3477 chars
- **Content sha256:** `8ac62fdd79fdb311577a9269afec12097c1800c3b57c5331b6724987b0bb7cfb`
- **First seen in run:** 33027905549
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/26aug26-speech/`

- **Title:** Speech By Minister For Defence Chan Chun Sing At The 125th National Cadet Corps Anniversary On 26 August 2026 At Central Manpower Base
- **Stored date:** 2026-08-26 · **kind:** speech · **body:** 4854 chars
- **Content sha256:** `e5bb8bc0f69ef382ed6d86c6347a938c224c1e3cf6dc08d5b3349e914dcf3af4`
- **First seen in run:** 33027905549
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/27jul26-fs/`

- **Title:** Fact Sheet: Singapore-Australia Industrial Base Resiliency Arrangement
- **Stored date:** 2026-07-27 · **kind:** fact sheet · **body:** 2344 chars
- **Content sha256:** `7b30786a8f4090f85ca36016b9b078ddc7e673b86ee351024b8e992423ea8a49`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/27jul26-nr/`

- **Title:** Signing of Industrial Base Resiliency Arrangement Deepens Defence Relations between Singapore and Australia
- **Stored date:** 2026-07-27 · **kind:** news release · **body:** 4570 chars
- **Content sha256:** `437f21331ed2685473471a64d1e7e2bbb21dcf77396b3cba2f128b704a1bb845`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/30jul26-nr/`

- **Title:** Change in Chief Executive of Defence Science and Technology Agency
- **Stored date:** 2026-07-30 · **kind:** news release · **body:** 2145 chars
- **Content sha256:** `426578274701c40486312b1e7638104c37d005ae288fbac1e52d2c102971b756`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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
- **Queued because:** review-all

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
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/31jul26-nr/`

- **Title:** RSAF Sharpens Combat Readiness at Multinational Exercise Pitch Black in Australia
- **Stored date:** 2026-07-31 · **kind:** news release · **body:** 3337 chars
- **Content sha256:** `a07229d73290f7f804ad4eee12fe838c1d08612b0efcfbcc23b0c6e1c60b2798`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/5aug26-nr/`

- **Title:** Permanent Secretary (Defence) Mr Joseph Leong Visits Malaysia  and Co-Chairs the 63rd FPDA Consultative Council Meeting
- **Stored date:** 2026-08-05 · **kind:** news release · **body:** 2720 chars
- **Content sha256:** `d5b912ca29b9a362897a2b9c6d2208309513453af3ffb12fb5be06265ecdb78a`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/5aug26-pq1/`

- **Title:** Written Reply by Minister for Defence Chan Chun Sing to Parliamentary Question on SAF Innovation Laboratories on 5 Aug 2026
- **Stored date:** 2026-08-05 · **kind:** parliamentary question · **body:** 2571 chars
- **Content sha256:** `7c588a108180ffc95d94041f7fc621308967c7265245fbe49d097706a1ef2614`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/5aug26-pq2/`

- **Title:** Written Reply by Minister for Defence Chan Chun Sing to Parliamentary Question on MINDEF Procurement System on 5 Aug 2026
- **Stored date:** 2026-08-05 · **kind:** parliamentary question · **body:** 3498 chars
- **Content sha256:** `ca87052ff3124c91137d70d2064112ee5c29c221b67cca031fdcde15e53a9c43`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/5aug26-pq3/`

- **Title:** Written Reply by Minister for Defence Chan Chun Sing to Parliamentary Question on Assignment of NSF Vocations and EEDs on 5 Aug 2026
- **Stored date:** 2026-08-05 · **kind:** parliamentary question · **body:** 2057 chars
- **Content sha256:** `f2d3ee254af302f6adf8a902ce0b40f01ef8fd2bb367f471ca60ab41efb14d53`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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

### `https://www.mindef.gov.sg/news-and-events/latest-releases/7aug26-nr/`

- **Title:** MINDEF and the SAF Celebrates Singaporeâs 61st Birthday
- **Stored date:** 2026-08-07 · **kind:** news release · **body:** 1877 chars
- **Content sha256:** `5e50f76e65b1be814b63bfca73404eb13eb301d63548bf89d6746c3a268c1d6e`
- **First seen in run:** 32311419939
- **Queued because:** review-all

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
| Checkpoint | day-07 — shadow_day 7 (as of 2026-08-27) |
| Reviewer identity | |
| Review completion timestamp (UTC) | |
| Records reviewed against source | |
| Anomalies accepted, with reasons | |
| Verdict (continue / pause / stop) | |

