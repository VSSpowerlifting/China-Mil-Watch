# Japan official-route Actions re-probe — 2026-10-07

## Purpose

Re-test the official Japan defense publication routes that appeared publicly
crawlable on 2026-10-07, using the actual GitHub Actions environment and the
repository's declared collector identity before changing any adapter or source
scope.

The public web surfaces were visibly live on 2026-10-07:

- Joint Staff Japanese press index: `https://www.mod.go.jp/js/press/`
- Joint Staff English press index: `https://www.mod.go.jp/js/press/index-en.html`
- JMSDF English news index: `https://www.mod.go.jp/msdf/en/news/2026.html`
- JASDF English news index: `https://www.mod.go.jp/asdf/en/news/`

Search/crawler visibility is not treated as collector permission or collector
reachability. The decisive check is the same environment IPR actually uses.

## Probe boundary

Temporary draft PR #120, head
`0a697024bbed270246acb2a206891796a39827ea`, added a read-only
pull-request probe and was closed unmerged after evidence capture.

Actions run: `37678838045`
Job: `112989266628`
Artifact: `japan-official-route-probe-37678838045`
Artifact ID: `11508166487`
Artifact digest:
`sha256:85404a821576205e9103919b2a6ee15167de7aca67f533608542bd638246ad52`
Artifact expiry: 2027-01-05.

The probe made at most five GET requests, followed no redirects, fetched no
linked documents, wrote no repository/shadow/production state, and used the
exact declared collector identity:

`ChinaMilWatch/1.0 (non-commercial research; project: https://github.com/VSSpowerlifting/China-Mil-Watch)`

## Results

The policy request succeeded:

| Route | Status | Policy/challenge finding |
|---|---:|---|
| `/robots.txt` | 200 | readable; no challenge |
| `/js/press/` | 403 | robots allowed; `Cf-Mitigated: challenge` |
| `/js/press/index-en.html` | 403 | robots allowed; `Cf-Mitigated: challenge` |
| `/msdf/en/news/2026.html` | 403 | robots allowed; `Cf-Mitigated: challenge` |
| `/asdf/en/news/` | 403 | robots allowed; `Cf-Mitigated: challenge` |

`robots.txt` was 48 bytes, `text/plain`, and allowed all four tested paths.
Each index request was therefore policy-permitted before it was made.

All four HTML indexes were then independently challenged by Cloudflare from
GitHub Actions. No redirect was followed and no linked article or PDF was
requested.

## Interpretation

The August 2026 operational finding remains valid for the environment that
matters: the official HTML index estate is not currently collectible by the
declared GitHub-hosted IPR client without solving or working around an
interactive challenge.

The fact that ordinary web crawlers/search systems can currently read these
pages does not change that result. It establishes public availability, not
reachability for this collector.

This probe does **not** establish a robots refusal. Robots permits the tested
paths. It establishes an edge-policy challenge specific to the request/client
path observed from GitHub Actions.

## Decision

Do not add Joint Staff, JMSDF or JASDF HTML adapters from these indexes at this
time. Do not use a browser identity, challenge solver, cookies, proxy, alternate
host, retry loop or other bypass to make the routes appear collectible.

Keep the current Japan shadow scope unchanged:

- the two official Japanese MOD RSS feeds remain the discovery routes;
- served PDFs may continue to supply bodies under the existing collector;
- challenged HTML remains explicit gap evidence;
- Joint Staff and service HTML indexes remain outside collection.

A future route may be reconsidered only if an official machine-readable feed,
served PDF index, API, or other first-party path is found that is both permitted
and reachable by the declared collector, or if the challenged indexes become
directly reachable in a later bounded re-probe.

## Out of scope

No Japan state mutation, backfill, production admission, rendering, deployment,
challenge bypass, source enablement, cap increase, or schedule change occurred
in this probe.
