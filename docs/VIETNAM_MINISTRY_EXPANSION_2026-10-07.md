# Vietnam ministry continuation — 2026-10-07 UTC

Ben requested continuation after the earlier agent's usage limit. The recovered
branch was `feat/vietnam-shadow-pilot`, head `31ffe31b`, draft PR #107. This pass
completes local ministry collection and rehearsal review; it does not launch a
remote collector or merge the PR. Government News and `chinhphu.vn` research are
retained. The supplied Finance Google redirect is normalized to its direct
destination, `https://www.mof.gov.vn/`.

## Requested sources

| Institution | Evidence and result | Implemented scope |
|---|---|---|
| National Defence, `https://bqp.vn/`; `mod.gov.vn` alias | October 6 robots returned script/cookie challenge markup. No ministry listing or body was reached. Not retried October 7. | Blocker recorded; no adapter admitted |
| Public Security, `https://bocongan.gov.vn/` | October 6 first-party RSS/category/articles captured; October 7 live adapter passed body, repeat and quiet runs. | Vietnamese **Thông tin Đối ngoại**, published RSS 34 and linked portal articles |
| Industry and Trade, `https://moit.gov.vn/` | October 6 category/article captures; October 7 both live adapters passed body, repeat and quiet runs. | Separate Vietnamese **Phát triển năng lượng** and **Công nghiệp nền tảng** families |
| Finance, `https://www.mof.gov.vn/` | October 6 robots returned an HTML app shell instead of rules. No ministry listing/body requested. Not retried October 7. | Blocker recorded; no adapter admitted |

MOIT's linked `vntr.moit.gov.vn` trade-remedies estate disallows collection in
robots and is excluded. Nothing substitutes another estate, private endpoint or
language for an unreached source. These outcomes are bounded access/extraction
measurements, not general institutional silence, reliability or archive coverage.

## Implementation and attribution

`VNMinistryAdapter` implements discover/fetch/extract/offline healthcheck for the
three measured profiles in `core/collection/vietnam_sources.py`. Its page rules
are independent of VGP; the text-block walker and screened transport are shared.
The transport preserves the prior complete collector identity and bounded
UTF-8 response bytes, with verified TLS, no redirects, returned cookies, retries
or script execution. A 429, 503 or Retry-After stops the remaining host window.

The runner now actually supplies `HostGate` to VGP as well as the new adapters.
Exclusive host locks cover the whole request and its end time, so the two MOIT
categories cannot overlap a request. Validated Crawl-delay is recorded while the
robots slot is held and in the request ledger, and can be seeded on a fresh
machine. Damaged/nonfinite timing records fail closed. Every source gets its own
external directory, ledger, database and clock; a different source's existing
state is rejected before collection. No ministry workflow or remote publication
path is added.

Windows use only a published first page/feed and require its oldest item to
precede the start. Unproven history fails without references; an oversized window
fails without sampling. Public Security RSS's declared UTC instant selects the
Hanoi calendar window and is stored separately; the article's visible date is
cross-checked. MOIT listing order was measured against printed article dates,
including the January 2022 article whose metadata says August 2022. Its printed
date remains the publication date; metadata stays separate as an anomaly.
Visible stamps carry no assumed timezone or invented UTC instant.

Publisher and individual byline are distinct. A generic MOIT `Author` value is
not promoted into a person's name. Issuer and legal effective date remain unset:
the captured items are ministry portal reports, not inferred legal instruments.
Vietnamese Unicode, inline text, short bodies, tables and captions survive
storage; no translation, model or keyword gate changes the selected set.

## Bounded local live rehearsal

Budget committed before requests in `shadow/vietnam_ministries/BUDGET_2026-10-07.md`.
Collector commit **`d603d27`**. All nine runs succeeded on October 7 UTC:

This is the local collector SHA retained in immutable rehearsal ledgers. CLI
credentials were unavailable, so the connected GitHub app publishes the
identical collector tree under its own commit metadata. The raw local commit
object, published counterpart and identical tree are preserved in
`shadow/vietnam_ministries/COLLECTOR_PROVENANCE_2026-10-07.json`; the local SHA
can be reconstructed from that object. No rehearsal ledger is rewritten.

| Family | Body run | Repeat | Quiet October 6 window | Requests |
|---|---|---|---|---:|
| Public Security foreign affairs | October 5: two reports | `ok_all_duplicates` | `ok_no_publications` | 10 |
| MOIT energy | September 30: two reports | `ok_all_duplicates` | `ok_no_publications` | 10 |
| MOIT foundational industry | September 30: one report | `ok_all_duplicates` | `ok_no_publications` | 8 |

Exactly **28 requests**, the written aggregate ceiling. Minimum measured
same-host request-end to next-start gap was **2.000824 seconds**, including
between MOIT categories. Five records, five versions and ten observations were
stored across three independent external states; no remote was written. Each
source's local review reproduced identically, with full input and capture hashes:

| Source | Deterministic rehearsal-review digest |
|---|---|
| Public Security | `80ae9c3bf407` (prefix) |
| MOIT energy | `cb13a7f4fca3` (prefix) |
| MOIT foundational industry | `cd811416d968` (prefix) |

Full digests, counters, request timings and payload hashes are committed in
`shadow/vietnam_ministries/REHEARSAL_2026-10-07.json`. Original article bytes
remain external; they are not committed or published. October 6 evidence remains
in `tests/fixtures/vn_ministries/requests.json`, with first-session lost-capture
limitations preserved. MPS exact fixtures retain attribution. MOIT fixtures are
derived structural examples with separate original and derived hashes; they are
not source prose or proof of byte fidelity.

`review_vietnam_ministry_state.py` reads immutable SQLite state and validates
capture hashes, input inventory, database hash chain/integrity, versions, text
assembly, observations, source metadata and clock ownership. Its deterministic
report explicitly leaves state commit, owner signoff and qualification unset.
It is **local rehearsal evidence**, not a formal Day 7/14/30 packet. The existing
VGP formal reviewer and its packet-reproduction tests remain unchanged.

## Verification and boundaries

Source tests forbid sockets and exercise all measured article structures, RSS
identity/offset checks, missing/truncated/challenged listings, quiet versus
unproven windows, the MOIT metadata discrepancy, canonical conflicts, short
Unicode/table text, cap overflow, duplicate storage, host-stop responses, source
isolation and deterministic/corruption-refusing local review. The original VGP,
shared transport and genuine cross-process host-gate tests also run.

The feature branch integrates main `ba5885c` without rewriting prior collector
commits. Its decision-log conflict retains both histories. Upstream production
updates are inherited from main, not regenerated by Vietnam work. Before that
integration, all **7,411** tracked DB/output files matched the recovered baseline;
after integration a fresh **7,451**-file baseline is used for final preservation.
No production database or output file is edited by the ministry implementation.

Main subsequently advanced to `d0c6dbb` for Indonesia/Korea cadence. That update
is also integrated, retaining its decisions and leaving Vietnam's scope and
source code unchanged. Its affected integration/telemetry modules pass 106 tests.
Vietnam, gate, map, registry and site-mode checks pass 289 tests; the final
ministry suite passes 17 tests after adding a Python 3.9 offset regression.
All six Vietnam transport, gate, adapter, runner and review suites pass **208
tests on native Python 3.9**. Replaying the original live captures on that
interpreter reproduces all five stored reports' dates, hashes and text exactly.
MOIT's declared offset is normalised only for datetime cross-checking; its raw
metadata remains unchanged.

After repairing missing local dependencies, Playwright 1.55.0's Chromium 140
launched successfully. The broader suite ran **3,712 tests** with 18 failures,
one error and two skips. All 13 failed methods were then rerun after correcting
the official ministry name and supplying Google Fonts resources to Chromium
through verified HTTPS downloads. Twelve methods pass; the remaining failure
is the existing Analysis page's responsive topography check at 375 px (9 px
horizontal overflow). No unrelated renderer or test tolerance was changed.
The broader browser gate is therefore **not green**, and latest-head GitHub CI
has not reported a result. This PR stays draft and unmerged.

Output validation passes with the governed **10 warnings**. Final preservation
checks confirm all **7,451** inherited DB/output files remain byte-identical,
with no database sidecar residue.

Remaining work is a separate activation phase: owner decisions on state
visibility/reuse, periodic collector identity, bounded remote dispatch and later
scheduling; ministry commit-bound formal review plumbing before checkpoint use.
Local clocks and rehearsal bytes are not transferred into that phase. Vietnam
stays `research`, manifest null, no production records/counts. No launch,
qualification, main merge, output regeneration or deployment occurred.
