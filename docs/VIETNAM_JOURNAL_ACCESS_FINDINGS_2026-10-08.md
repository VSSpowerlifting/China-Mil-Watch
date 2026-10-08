# Vietnam National Defence Journal — GitHub Actions access proof (2026-10-08 UTC)

The one-shot, disposable research run
[37712715499](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37712715499)
completed successfully from exact probe head
`4c150bd1ec2bc8f7390077c55ebbb2b1b7371d0b`
(job `113102087188`). The source candidate remains **disabled**.
The disposable experiment lives in PR #130, which targets this source PR
(#129) but is not part of the production source. Its PR workflow and probe
code are *not* being merged or scheduled as part of this decision.

The runtime used the exact `IndoPacificRecord-ShadowCollector/0.1`
identity, from GitHub Actions, no browser identity, proxy, redirects,
retries or retained cookies. It made **four GET requests**, below the
approved six-request maximum. Its only artifact contains structured
metadata, response lengths and hashes, without source HTML or article text.
Nineteen focused offline tests passed immediately before the live probe.

## Measured host results

| Stage | Desktop `tapchiqptd.vn` | Mobile `m.tapchiqptd.vn` |
| --- | --- | --- |
| `/robots.txt` | HTTP 200, `text/plain`, 200 bytes, parsed; both selected article and homepage paths permitted | HTTP 404, `text/html`, 1,245 bytes; **no robots file at that URL**, not an explicit source denial |
| English homepage | HTTP 200, 59,056 bytes; 26 distinct numeric article identities; known article 26936 linked | Not requested (per-host policy gate) |
| Sample 26936 | HTTP 200, 62,437 bytes, `text/html`, stable canonical ID `vndj-en:26936`; no access challenge | Not requested |
| Extracted title | **Unverified**: tested `og:title`/h1/h2 selectors produced no title | Unmeasured |
| Extracted body | **Unverified**: initial article-body CSS selector candidates all returned zero matches | Unmeasured |
| Publication date | Both `2026-09-30` (sample article) and `2026-10-08` (site clock) found. The extractor must **distinguish a page's current time from the article's original publication date** | Unmeasured |

Desktop robots SHA-256:
`b7ce362c27bcac93a9eeecf9e065dd2ae694becde6c66ba1d06c0259c48722a3`.
Desktop listing SHA-256:
`04f3be13a29d61f25db12941fa7d74b7f97ee8d7c0d159d3567fbe1cde6cea38`.
Desktop sample SHA-256:
`c36acbcb24a1d2728962a046fc1051ccfc4c2f13da8fcd5e585560219c4a2be1`.
Mobile robots response SHA-256:
`dc1d54dab6ec8c00f70137927504e4f222c8395f10760b6beecfcfa94e08249f`.

These hashes describe ephemeral responses and do **not** imply that the
response bytes are archived in Git or in the artifact. URLs and timestamps
are metadata, not permission to reproduce article prose.

## Owner decision gate

**Desktop automated access is feasible for the bounded paths measured.**
This is a material change from the earlier browser-only unknown-robots state.
No full-text collector is yet fit for activation: we have not identified a
complete, validated body selector; the first-page homepage is not a proven
complete date-bounded listing; and no rights/reuse approval for long-term
source text has been established. The journal's copyright footer still
states all rights reserved.

The mobile result means *there is no robots policy at that requested URL
(404)*, not that its publisher has explicitly disallowed collection.
The conservative one-shot probe made no subsequent mobile requests; it
cannot claim the mobile path is permitted or equivalent by observation.
Do not use it as a circumvention route. The desktop can independently
be a viable single-host collector after the remaining gates pass.

Recommended next engineering boundary: **offline DOM/body and publication-date
disambiguation** using an explicit ephemeral diagnostic or permission-cleared
retained fixture. The extractor must attribute authors and preserve the
journal's institution as the publisher, not claim formal ministry directives.
Then prove actual listing coverage by date and pagination before any
separate approval for shadow collection.

No public source entry, production records, generated site, schedules,
MPS/MOIT state, Government News gate, Vietnam ministry Day 7/14/30 clock or
shadow source activation was changed by the probe.
