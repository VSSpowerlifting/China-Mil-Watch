# Singapore screening repair and re-screening plan — 2026-09-29

This change repairs how Singapore MINDEF records are judged for relevance. It
does **not** change any stored verdict, screen any record, or enable
Singapore analysis. Every measurement here is from `pla_watch.db` at `main`
`d17646aef` (sha256 `42f4e5a9…b501c`), read-only.

## 1. The defect, in both stages

Every record goes through two stages (`processing/relevance.py`). Both were
written for the China Desk and applied to every desk.

**Stage 1, the keyword pre-filter** (`config.RELEVANCE_KEYWORDS_ZH/EN`).
- The English list is PLA vocabulary plus "defense" and "military".
- Singapore writes "defence", so an SAF release that happens not to say
  "military" fails.
- Record 4721, an SAF discipline notice, was stored as `failed keyword
  pre-filter`.

**Stage 2, the model screen** (`analysis/prompts.py`,
`build_relevance_messages` under `SYSTEM_PROMPT`).
- The prompt asks how substantively "a Chinese-language article" covers
  "Chinese military or security topics".
- The system prompt defines the domain as the PLA, PAP, CCG and Chinese
  defence industry, for a US audience.
- A MINDEF release can only fail that question.

**The stored explanations show it.** Of the 14 Singapore records screened
(stored score in brackets):

| id | published | stage | stored score | title (abridged) |
|---|---|---|---|---|
| 4421 | 09-12 | model | 0.0 | 219 Cadets Commissioned as SAF Officers |
| 4422 | 09-12 | model | 0.15 | Speech by Mrs Josephine Teo … |
| 4425 | 09-14 | model | 0.4 | Minister for Defence to Visit China for the 13th Beijing Xiangshan Forum |
| 4426 | 09-16 | model | 0.4 | Minister for Defence Speaks at 13th Beijing Xiangshan Forum and Meets … |
| 4427 | 09-18 | model | 0.15 | Singapore and Vietnam Reaffirm Defence Relations … |
| 4428 | 09-18 | model | 0.2 | Singapore and Australia Navies Mark Completion of … Exercise Singaroo |
| 4429 | 09-19 | model | 0.0 | SAF Open Mobilisation Exercise |
| 4561 | 09-23 | model | 0.1 | Minister of State for Defence Desmond Choo Visits SAF's Artillery … |
| 4609 | 09-24 | model | 0.1 | SAF Strengthened International Partnerships at Exercise Suman Warrior 2026 |
| 4631 | 09-25 | model | 0.0 | Speech by Coordinating Minister for Public Services … |
| 4679 | 09-27 | model | 0.1 | Minister for Defence Chan Chun Sing to Visit France and Germany … |
| 4680 | 09-27 | model | 0.15 | Singapore and United States Hold 16th Strategic Security Policy Dialogue |
| 4720 | 09-28 | model | 0.1 | Speech by Minister of State for Defence Desmond Choo at the 27th … |
| 4721 | 09-28 | keyword | 0.0 | Media Reply on 1SG N M Pranesh |

- **10 of the 13 model rejections** give the absence of Chinese military
  content as the reason. For example, 4421: *"concerns the Singapore Armed
  Forces, not Chinese military or security organizations"*.
- **4425 and 4426**, the two Xiangshan Forum releases, name PLA officials. They
  scored 0.4 for lacking substantive PLA *activity*. That is the China rubric's
  bar applied to a Singapore minister's visit.
- **4631** is a speech at a hospital's 30th anniversary about ageing. It would
  be rejected under any defence scope.

**What happens after a pass is also China-only.** In `Analyzer.analyze()`, a
record that passed would go on to:
- translation "from Chinese";
- a summary;
- the PLA category taxonomy (`VALID_CATEGORIES`).

So fixing stage 2 alone would send English MINDEF releases through a
Chinese-to-English translation and PLA categories.

## 2. The fix

**`processing/screening.py`** gives each desk a `ScreeningProfile`:
- **China, and any record with no desk:**
  - the shared keyword lists;
  - `build_relevance_messages` under the existing system prompt;
  - in the daily queue.
  - These are the same objects as before.
- **Singapore:**
  - **Stage 1** is skipped for Singapore. The source is the declared scope,
    since every official MINDEF release is inside it. Nearly every release
    names MINDEF or the Minister for Defence, so a keyword list would filter
    nothing.
  - **Stage 2** uses `build_singapore_relevance_messages` under
    `build_singapore_system_prompt(<scope>)`. The scope sentence is read from
    `desks/registry.json` at runtime, not restated in code.
  - **Not in the daily queue.**

**The gate** (`pipeline.py`, and `scripts/backfill_unscored.py`, which runs
the same China-only `analyze()` path).
- Records of a desk whose profile is not in the daily queue are left out of
  all three parts of the analysis queue (new, pending and unscored) and out
  of the backfill.
- On the pinned database, the backfill skips exactly the 50 Singapore records
  and keeps all 566 China ones.
- They stay `passed_relevance IS NULL`, "awaiting screening".
- One log line per run counts them.
- Merging this therefore:
  - stops further China-rule rejections of Singapore records;
  - screens none of the 50;
  - never runs translation or PLA categorisation on a MINDEF release.
- The cost is that no Singapore record is selected for analysis until the
  owner enables it. Enabling it needs a Singapore-appropriate
  post-relevance step first (§5).

**The Singapore rubric is new editorial policy and needs the owner's review.**
- The question it asks: how substantively does the release concern defence or
  security matters? Those are defined as:
  - the SAF and MINDEF's defence agencies (operations, exercises, training,
    readiness, personnel, discipline, capability development, procurement);
  - national service;
  - Singapore's defence policy;
  - Singapore's defence relations (visits, dialogues, agreements, combined
    exercises).
- Its bands match the China rubric's shape:
  - 0.9–1.0: specific facts;
  - 0.6–0.8: ceremonial or general;
  - 0.3–0.5: secondary;
  - 0.0–0.2: not defence, "for example, a minister's speech on another
    portfolio at a non-defence event".
- It says outright that China or PLA involvement is neither required nor a
  reason to score higher.
- The threshold stays `RELEVANCE_THRESHOLD` = 0.60. By design, the ceremonial
  0.6–0.8 band passes.
- Full text: `analysis/prompts.py`.

**Stored verdicts.** None change. Future Singapore records are no longer
written as `failed keyword pre-filter`; they are stored NULL (awaiting
screening).

## 3. Tests

`tests/test_desk_scoped_screening.py` has 14 tests, all offline; the model is
mocked. 12 fail on `main`. The two China invariants pass on `main` by design.

**China is unchanged** in its prompts, its system object, its keyword verdicts
and its backlog order. Slot allocation does change: on a day with more new
records than the cap, Singapore inserts no longer take new-article slots, so
China gets them. The tests check:
- the relevance messages, the system payload and `SYSTEM_PROMPT` match
  SHA-256 hashes recorded on `89e48a2fe`;
- a China call sends the *same* system object;
- keyword verdicts on stored China records are reproduced.

**Singapore uses its own scope:**
- 4721 fails the China keyword list and passes the Singapore stage 1;
- the prompt contains the registry scope and none of the China-only phrases;
- a Singapore call sends the desk system prompt.

**The gate:**
- the real `pipeline.run()` on a temporary database queues the China record;
- it holds both Singapore records, which stay NULL;
- the backfill is offered China records only.

**Re-screening tool:**
- the plan groups records by stage and prices them;
- a proposal calls relevance only (never `analyze()`), leaves the database
  byte-identical, and refuses another desk's ids.

**Fixtures** (`tests/fixtures/screening/desk_screening_records.json`).
- These are 900-character excerpts of stored records, labelled from their
  text:
  - relevant: 4466, 4472, 4425, 4426, 4721;
  - irrelevant: 4631;
  - China: 4708, 4686, 4719.
- **What the tests cannot show:** a mocked model can't prove the rubric
  selects the right releases. That is what the reviewed proposal in §4
  measures.

## 4. Re-screening plan (not run)

`scripts/rescreen_desk.py plan --desk singapore --db <snapshot>` produced the
figures below offline.

**Affected: 64 records.**
- **Never screened (50):** 4417–4420, 4423, 4424, 4430–4473.
- **Model-rejected (13):** 4421, 4422, 4425–4429, 4561, 4609, 4631, 4679,
  4680, 4720.
- **Keyword-rejected (1):** 4721.

**Cost.** One Haiku relevance call per record (`claude-haiku-4-5-20251001`,
$1 / $5 per million tokens as recorded in `scripts/spend_guard.py` on
2026-07-31; re-verify before spending).
- **Input:** 373,019 characters of prompt plus a 457-character system prompt
  per call, about **115k input tokens** at 3.5 characters per token.
- **Output:** 80 tokens per call typical, 500 at the ceiling.
- **Estimate:** **about $0.14 typical and $0.27 at the output ceiling** for
  all 64, with no cache discount assumed. There are no translation, summary
  or analysis calls.

**The list moves until this merges.**
- Every scheduled run screens its **new** Singapore inserts first, under the
  China rules.
- The 2026-09-29 run's window (09-23 → 09-29) should insert `23sep26-mq` and
  any 09-29 releases, so the rejected list will grow.
- The 50 unscreened records are not at risk yet. They sit at positions
  567–616 of the archive backlog, behind all 566 unscreened China records,
  and a daily run takes about 16 backlog records.
- Refresh the plan against the database at merge time.

**Review before any database change:**
1. **Plan.** Run `plan` against a pinned snapshot, and record the snapshot
   sha256.
2. **Propose.** Run `propose --ids … --confirm-spend` with the owner's
   authorization. It calls only the Singapore relevance stage and writes a
   JSON sidecar: stored verdict beside proposed score and reasoning, with an
   empty `review` block for each record. It cannot write the database.
3. **Review.** A human reads each proposed verdict against the record text,
   and fills in `decision` and `note`. Look first at:
   - the 0.6–0.8 band;
   - any reversal of 4631;
   - held and short records (4429 has 258 characters).
4. **Apply.** `update_relevance` stores no prompt version, so an applied row
   cannot show which rules produced it. The apply must therefore record each
   id's `model` and `prompt_version` (`sg-relevance-v1`), through the
   committed, reviewed sidecar and the DECISION_LOG entry.

   The apply itself is a separate, owner-approved change: an update-only delta
   to `passed_relevance`, `relevance_score` and `relevance_reasoning` for
   the approved ids. Check it the way PR #66 checked its insert-only delta:
   - no other column or row changes;
   - the database hash is taken before and after;
   - it is recorded in `DECISION_LOG.md`.

   No apply tool exists yet, by design.

## 5. Decisions for the owner

1. **The Singapore rubric** (§2): accept or amend it.
2. **Re-screening:** whether to authorize `propose` for the 64 (about $0.27
   at most), and who reviews the result.
3. **After a pass.** What Singapore analysis should be: no translation, a
   Singapore summary, and which categories. Until that is decided, Singapore
   stays out of the daily queue.
4. **Sequencing:** merge before or after the 2026-09-29 run. Each run before
   merge adds new China-rule rejections for Singapore.
