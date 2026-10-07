# Vietnam ministry shadow research

This manifest stays outside `desks/`. Vietnam remains `research`; the original
Government News English pilot is retained in `shadow/vietnam/`. The prepared
`vietnam_ministry_shadow.yml` is dispatch-only and main-only, using one serial
batch and separate source branches. It has not been activated; no ministry
remote state branch or production registration is created by this readiness work.
The exact first-run proposal and owner decisions are in
`docs/VIETNAM_REMOTE_ACTIVATION_PROPOSAL_2026-10-07.md`.

| Institution | Bounded surface | Engineering result |
|---|---|---|
| Public Security (`bocongan.gov.vn`) | Vietnamese Thông tin Đối ngoại, published RSS 34 | Adapter and isolated local runner |
| Industry and Trade (`moit.gov.vn`) | Vietnamese Phát triển năng lượng | Adapter and isolated local runner |
| Industry and Trade (`moit.gov.vn`) | Vietnamese Công nghiệp nền tảng | Adapter and isolated local runner |
| National Defence (`bqp.vn`, `mod.gov.vn` alias) | Robots | Script/cookie challenge; no body/listing reached |
| Finance (`www.mof.gov.vn`) | Robots | App shell, not rules; no collection basis |
| MOIT trade remedies (`vntr.moit.gov.vn`) | Robots | Disallowed; excluded |

The exact October 6 request inventory is
`tests/fixtures/vn_ministries/requests.json`. MPS article fixtures preserve the
portal's attribution. MOIT fixtures replace prose and preserve measured DOM,
identifiers and dates, with original and derived hashes recorded separately.
They test structure and date handling, not MOIT source-text fidelity. Original
live bytes may be retained in external rehearsal state under the existing
unresolved state-visibility/reuse decisions; they are not published by this tool.

Each source requires a different external state directory and has its own clock.
The default external host gate directory is shared across local processes;
MOIT's two categories share one host gate. Previous request ends and longer gate
intervals are seeded from preserved ledgers. Parallel hosts are independent.

Example (only after recording an appropriate request budget):

```sh
.venv/bin/python scripts/shadow_collect_vietnam_ministry.py \
  --source vn_mps_foreign_affairs_vi --state-dir /tmp/vn-mps-rehearsal \
  --target-date 2026-10-05 --lookback-days 0 --cap 2 \
  --run-id body --commit "$(git rev-parse HEAD)"
.venv/bin/python scripts/review_vietnam_ministry_state.py \
  --source vn_mps_foreign_affairs_vi --state-dir /tmp/vn-mps-rehearsal \
  --out-dir /tmp/vn-mps-review
```

The `--state-dir` review is deterministic, read-only and bound to one source. It verifies
input/capture hashes, database integrity, versions, original-text assembly,
observations, source metadata and clock ownership. It explicitly labels itself
**local rehearsal only**: it verifies no remote commit or checkpoint and gives
no signoff or qualification. The Government News formal review path is unchanged.
Formal mode uses `--state-repo`, `--state-commit`, `--checkpoint` and `--as-of`
instead of `--state-dir`. It exports only the named commit's objects, verifies
reachability from the selected source's fixed branch, and emits deterministic
Day 7/14/30 complete-corpus packets with a blank structured signoff. Early packets
cannot complete a checkpoint. `--check-signoff` validates a human's answers;
it publishes nothing and qualifies nothing. See the activation proposal for
commands, budgets, state/artifact visibility and publication failure behavior.
Remote activation still requires owner decisions on visibility, rights, identity
and dispatch; local rehearsal clocks are never transferred.

Only the published first page/feed is requested. The oldest item must precede
the window start, otherwise discovery fails without fetching. Quiet means an
empty proven window, not an unreachable feed or a truncated archive. A window
larger than the cap is never sampled into success. The body is accepted on
structure, preserving Vietnamese characters, short paragraphs and captions;
no translation or model/keyword gate changes the selected set.

The visible article stamp supplies the publication date; no timezone is invented
for that stamp. MPS's explicitly offset RSS instant is separately stored. MOIT
article metadata timestamps are kept separately and date conflicts are anomalies.
Publisher, byline, unspecified issuer and unspecified legal effective date are
separate fields. These are ministry portal reports, not inferred legal instruments.
