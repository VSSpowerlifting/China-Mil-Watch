# Vietnam first remote shadow activation proposal — 2026-10-07

Prepared for owner review only. PR #107 merged as
`5ccc20ff94131f63d639aed840633776b829ef60` (reviewed head
`ef4aedfc8cba45dc1ce2d1e1fe19497c72e9f46e`). This readiness branch starts at
that main boundary; this finalization integrates current main
`9b475d0d578f93e6d4b9dc7cc90d3ad38c627b10` without rewriting branch history. GitHub verification found no `shadow/vietnam`
branch. Existing worktrees are preserved. No source requests were made in this
session; Defence, Finance and the excluded trade-remedies estate remain
unreached/excluded. Vietnam stays research with no production records or schedule.

## Owner decisions — finalization authority

1. **MPS/MOIT retention.** The owner approves successful shadow state and original
   response bytes on this existing public repository's three ministry orphan
   branches and associated Actions evidence for the shadow reliability period.
   This covers only `vn_mps_foreign_affairs_vi`, `vn_moit_energy_vi` and
   `vn_moit_foundational_industry_vi`. It is not blanket Vietnam permission or
   a production retention policy. No private state repository is needed.
2. **Government News remains unapproved.** Remote dispatch of
   `vn_vgp_defense_en` / `vietnam_shadow.yml` and creation of `shadow/vietnam`
   are not authorized. Its source-byte/public-retention question remains a
   separate owner decision because of its documented rights notice.
3. **Future Vietnam identity.** The owner selects exactly
   `IndoPacificRecord-ShadowCollector/0.1 (+https://indopacificrecord.org; research archive; contact via site)`.
   `core/collection/vietnam_identity.py` is the sole current identity constant,
   imported by the shared transport and formal reviewer. Government News also
   inherits this constant but stays offline and unapproved for remote dispatch.
   Historical probe/ledger identities remain immutable evidence; no request is
   made to validate the new identity. Both new named robots rules and legacy
   named refusals remain binding, without sending the legacy identity.
4. **Exactly one ministry batch after separate owner merge.** The command below
   is approved with an aggregate ceiling of 12 requests. In this finalization
   session it is documentation only and MUST NOT be executed. Approval covers
   no retry, second dispatch, schedule, production admission or Government News
   collection. A separate owner merge is still required.

## Exact approved first operation — after owner merge only

After a separate owner merge, verify
main contains the reviewed implementation, record that main SHA, verify all
three proposed ministry branches are absent (if they exist unexpectedly, stop
for owner review), and ensure no ministry collection is queued. Then:

```sh
gh workflow run vietnam_ministry_shadow.yml \
  --repo VSSpowerlifting/China-Mil-Watch --ref main \
  -f mps_target=2026-10-05 -f moit_target=2026-09-30 -f lookback=0 -f cap=2
```

The main-only workflow checks out the event's immutable `github.sha`. Ledgers
and state commit messages record the actual full collector SHA and Actions
`run_id-run_attempt`; the run URL binds to its event SHA. Record and compare
these identities during verification. No workflow has been dispatched here.

| Source / first published discovery surface | Logical Hanoi calendar window (inclusive) | Article cap | Request ceiling | Fresh orphan branch |
|---|---|---:|---:|---|
| `vn_mps_foreign_affairs_vi`, `https://bocongan.gov.vn/api/rss/34.xml` — Thông tin Đối ngoại | 2026-10-05 only | 2 | 4 | `shadow/vietnam-mps-foreign-affairs` |
| `vn_moit_energy_vi`, `https://moit.gov.vn/tin-tuc/phat-trien-nang-luong` — Phát triển năng lượng | 2026-09-30 only | 2 | 4 | `shadow/vietnam-moit-energy` |
| `vn_moit_foundational_industry_vi`, `https://moit.gov.vn/tin-tuc/phat-trien-cong-nghiep/cong-nghiep-nen-tang` — Công nghiệp nền tảng | 2026-09-30 only | 2 | 4 | `shadow/vietnam-moit-foundational-industry` |

One serial job: MPS, energy, foundational industry. Each family makes one robots
request and one first-feed/listing request, then at most two article requests;
no pagination, retries, redirects, returned cookies, script execution or inferred
endpoints. Aggregate ceiling **12 requests**, MPS **4**, MOIT **8**; at most six
article bodies. The local measurements suggest five articles and 11 requests,
but the first page may have changed: this is an expectation, not a guarantee.
An unproven historical window or more than two selected items refuses the whole
family without sampling or expanding scope. No fallback date is authorized.

Accepted response budgets: robots **524,288 bytes** each; listing/feed and each
article **2,000,000 bytes** each. Maximum accepted body bytes **6,524,288** per
source and **19,572,864** for the batch (MOIT combined **13,048,576**).
Transport timeout remains 30 seconds, maximum Crawl-delay 120 seconds, and the
job timeout is 30 minutes. Verified TLS and robots rules remain binding.

Every source state checkout is at
`${RUNNER_TEMP}/vn-ministry-state/<source_slug>/state/`, outside the collector
checkout. Each has its own `shadow.db`, `clock.json`, `ledger/` and `captures/`.
Bootstrap accepts no imported directory, database, ledger or rehearsal clock.
First successful remote completion creates that source's day zero; historical
publication targets never become day zero. A common
`${RUNNER_TEMP}/vn-ministry-host-gate` seeds request-end timings and validated
Crawl-delay from **all three** existing source ledgers before any new request.
Exclusive host locks cover requests and end times; at least two seconds from
request end to next start, or the larger validated Crawl-delay, applies across
both MOIT families and processes. Workflow concurrency serializes batches.

Any failed collection stops all remaining families, including the other MOIT
family after a MOIT refusal. This deliberately conservative batch stop preserves
429/503/Retry-After and access-challenge host-stop behavior. No partial collection
batch is published. A failure after a successful family can leave its new local
clock in the attempt artifact; it is discarded with the runner and never adopted
by a later bootstrap. No automatic retry or UI re-run is proposed.

After all three families succeed and the collector checkout is unchanged, the
workflow pushes only `state/` to the three fixed branches using explicit ordinary
fast-forward refs. Prior ledgers, captures and clocks must survive byte for byte;
foreign source state, unexpected files, symlinks and database sidecars refuse
publication. Every successful run adds a new ledger; content versions and
observations remain append-only. The database may change with observations.

The three pushes are **not a cross-branch transaction**: a push/auth/race failure
can leave an earlier source published while later sources remain unpublished.
Stop and report that exact boundary; preserve the artifact and compare remote
heads before proposing a new owner-approved action. Do not force-push, delete,
rewrite evidence, or import unpublished attempt state.

The always-run artifact `vietnam-ministry-shadow-<run_id>-<attempt>` contains all
attempt state (including original bytes), ledgers and `vn-ministry-run.log`, kept
90 days. Credentials and `.git` directories are excluded. Branches/artifacts in
this public repository must be treated as public. Durable successful state is
on Git; failed attempts exist only in artifacts and need preservation for later
checkpoint comparison before expiration, subject to the same visibility decision.

## Original Government News pilot — remote action unapproved

`vn_vgp_defense_en` is the English defense tag at
`https://en.baochinhphu.vn/defense.html`, Tier B newsroom reporting, distinct from
ministry reports. It remains built and tested offline, with no remote state,
dispatch or collection approved. Do not dispatch `vietnam_shadow.yml` or create
`shadow/vietnam`. The shared identity change is verified offline only; it grants
no collection or source-byte/public-retention permission for Government News.
That retention decision remains separate because of the documented rights notice.

## Post-run verification and formal review

Record run URL, event and collector SHA, exact inputs, health, request counts,
body bytes and stop status; inspect each ledger and the original-byte artifact.
Clone each successful branch into a clean external directory, record HEAD and
`HEAD:state`, compare capture/database hashes, append-only history, source
ownership and newly initialized clock. Confirm DB/output preservation in the
collector checkout and no production records/counts. A quiet result verifies
listing egress only; the proposed body windows measure article egress if still
provable. None of this completes human checkpoint review or establishes multi-day
reliability. A failed branch is not institutional silence.

Day 7, 14 and 30 are elapsed remote-clock checkpoints, separately for each
family. The packet reads only objects from the named commit reachable from its
fixed source branch; a modified checkout cannot substitute input bytes:

```sh
python scripts/review_vietnam_ministry_state.py \
  --source vn_mps_foreign_affairs_vi --state-repo <external-clone> \
  --state-commit <full-40-hex-source-state-SHA> --checkpoint day-07 \
  --as-of YYYY-MM-DD --out-dir <empty-external-packet-dir>
python scripts/review_vietnam_ministry_state.py \
  --out-dir <packet-dir> --check-signoff <external-filled-signoff.json>
```

Use the corresponding source slug and clone for each MOIT family, and day-14 /
day-30 at those checkpoints. Government News retains its existing formal kit.
Identical commit/source/checkpoint/as-of inputs produce byte-identical ministry
packets. Packets carry commit/tree, collector provenance, hashed full evidence,
complete record/version/observation/metadata inventories, date anomalies,
collecting-day gaps, window coverage, and blank structured signoff. Quiet corpora
cannot receive a plain pass, and early packets cannot complete a checkpoint.
Visible publication stamps remain authoritative; raw metadata, RSS instants,
anomalies and Vietnamese prose remain distinct and unchanged. Publisher/byline
checks do not invent issuer or legal effective date.

The reviewer must compare every record/version against its page, review failed
attempt artifacts and dispose every anomaly. Signoff validation does not publish
anything. Durable completed-review preservation remains a separate owner-approved
step; there is no ministry review publisher. An incomplete template is not human
review. Thirty consecutive collecting days, all three completed human reviews,
desk-strength criteria and owner signoff are still required for any promotion.

## Finalization verification

Current main `9b475d0d578f93e6d4b9dc7cc90d3ad38c627b10` is integrated by
ordinary merge, preserving Singapore image-only changes and Vietnam readiness.
The only additional runtime behavior is the shared owner-selected identity and
conservative new/legacy robots recognition; historical captures remain unchanged.

Native Python 3.9 focused checks passed **255 tests**: ministry adapters,
remote batch/packet tests, original VGP adapter/runner/reviewer, screened HTTP,
cross-process host gate and the integrated Singapore image-only contracts. The
first run failed one import allowlist for the new dependency-free identity module;
that guard was updated and the entire focused group passed on rerun.

Output validation passed with **10 governed warnings**. Chromium
**147.0.7727.15** launched locally. `git diff --check` passes. Required
`graphify update .` completed; its ignored graph output is not part of the PR.

Preservation compared every **7,451 tracked DB/output files** directly to current
main above, all byte-identical, with no WAL/SHM/journal residue. Database SHA-256:
`b10890ddac59538b66041b10d13d08199f20be2279efa9bcb03a2d991d17decc`.
No production content or generated-output change is included.

The final integrated-head required PR check (full Python 3.9 offline suite,
Chromium launch, output validation and preservation) is authoritative; its run
URL, tested SHA and results are recorded in draft PR #114 after completion.
Local focused success does not establish that the broader suite passed.

No source collection, remote dispatch, schedule, main merge, regeneration,
deployment or promotion occurred. Only the exact ministry first batch after
separate owner merge is approved; this session performs no remote activation.
