# Site modes and the launch switch

This repository builds two frontends from one corpus. This document is the
operator's reference for which one runs, how to select the other, and how a
future launch and rollback would work.

Nothing here changes what is published today. The public site is China Mil
Watch, legacy mode is the default, and the second renderer is dormant.

---

## The two modes

| Mode | Renderer | Writes to | Status |
|---|---|---|---|
| `legacy` | `site/generator.py` | `output/`, committed and deployed daily | **default, live** |
| `declared-record` | `site/preview/generate_preview.py` | an explicit disposable directory | dormant, not public |

`legacy` produces the site at chinamilwatch.org exactly as it has. Routing it
through the seam below changed no behaviour: re-rendering into a copy of
`output/` reproduces the committed tree in 1,330 of its 1,331 files.

`declared-record` produces the desk architecture — a parent publication with a
live China Desk and a planned, non-collecting Japan Desk. It is complete and
tested. It is not published, and this repository contains no mechanism that
publishes it.

## Selecting a mode

`site/render.py` is the only place a mode is chosen. Precedence:

```
explicit argument  >  PLA_WATCH_SITE_MODE  >  DEFAULT_SITE_MODE
```

```bash
# the live site, into a scratch directory
python site/render.py --mode legacy --out /tmp/legacy

# the desk architecture, into a scratch directory
python site/render.py --mode declared-record --out /tmp/declared-record
```

`pipeline.py` calls `render_site()` with no mode, so the daily run resolves to
`DEFAULT_SITE_MODE`. No workflow sets `PLA_WATCH_SITE_MODE`, and a test asserts
none does.

## Fail-closed rules

These are contract, not convention. Each is covered by
`tests/test_site_mode_contract.py`.

* **An unrecognised mode raises.** There is no fallback to legacy. A typo that
  quietly published the wrong site is the failure this seam exists to prevent.
* **`declared-record` requires an explicit destination.** It cannot inherit the
  production `output/` default.
* **`declared-record` refuses to write inside `output/`**, and the underlying
  `build()` refuses independently. Two guards, because one of them is the one
  that fails.
* **The snapshot guard aborts before writing** when the corpus does not match
  the declared snapshot — the build will not publish a changed corpus under an
  unchanged snapshot identity.
* **The renderer reads the database through `reconcile_db._read_only`**, which
  works on a scratch copy. It never opens the tracked file.

## The launch switch

`DEFAULT_SITE_MODE` in `site/render.py`. One constant.

Launching The Declared Record would be changing it to `DECLARED_RECORD` and
removing the guard that refuses production `output/` — a deliberate, reviewed
change, not a configuration accident. Rolling back is changing it back and
re-running the daily workflow, which rewrites `output/` from the legacy
renderer.

There is no automatic launch condition anywhere in this repository. No date, no
counter, and no collection milestone flips this switch.

## Legacy route continuity

`/article/<id>.html` is a live URL today and some of those URLs are cited.
`declared-record` mode emits a redirect for every record in the snapshot,
generated from the corpus rather than from a directory listing, so an id outside
the snapshot cannot acquire a redirect to nothing. Each carries `noindex` so the
compatibility route never competes with the record page it points at.

This is off by default, so the in-repo preview build never creates the
production `article/` namespace.

## Determinism

`declared-record` builds are byte-identical across runs.

`legacy` builds are byte-identical **except `og-image.png`**, which is a
Playwright screenshot of the rendered homepage. Screenshot rasterisation is not
reproducible run to run. This predates the seam and is not concealing anything:
the HTML, JSON, sitemap and routing are all deterministic, and `generated_at` is
tied to the data date rather than the wall clock precisely so that a re-run over
an unchanged database produces an unchanged page.

## Printing

Print styles expand only absolute URLs. An earlier rule expanded every `href`,
which put a parenthesised path after all 80 links on the archive and 13 of the
14 on a record page — the record text competed with its own internal plumbing.
Absolute URLs are kept because a source record or a published edition is the
citation a printed page cannot otherwise carry.

The legacy site has its own stylesheet and still prints its archive at 56 pages
with clipped table content. That is a separate, pre-existing defect; fixing it
changes tracked `output/` and is tracked as follow-up.

## Evidence hierarchy — what the renderer actually implements

Every analytical surface must let a reader tell these apart at a glance, by
text label and never by colour alone. Eight levels are specified.

**Three of these eight are implemented in the prototype. Five are specified for
future editorial implementation and are not demonstrated** — the data or the
human editorial step they depend on does not exist yet, and rendering an empty
badge to satisfy a checklist would be exactly the faux-precision this hierarchy
exists to prevent. The status column is the honest state, not the intention.

| Level | Meaning | Status |
|---|---|---|
| Source record | The item as published | **implemented** — every archive and record page |
| Official claim | The institution asserted it; never rendered as fact | **implemented** — record pages |
| Model-flagged | A machine classification, labelled "not reviewed by a human" | **implemented** — record summaries |
| Verified fact | Corroborated across two or more independent sources | **not demonstrated** — needs cross-source corroboration one desk cannot perform |
| Analyst interpretation | A human read, labelled and attributed | **not demonstrated** — exists in the weekly brief, not the archive |
| Inference / hypothesis | Reasoning beyond evidence, with what would falsify it | **not demonstrated** — no stored inference records |
| Change from baseline | New vs. repetition | **not demonstrated** — needs repetition analysis that does not exist |
| Unknown / unverified | A gap, stated rather than omitted | partial — stated at corpus level on the coverage page, not per statement |

The renderer implements **Model-flagged**, which an earlier draft of this table
omitted, and does not implement **Verified fact**, which it listed. That is the
right way round for what the corpus can support: it can say what a machine
concluded and that no human checked it; it cannot yet say a fact is
corroborated.

**Rule: no confidence percentages on qualitative judgments.**

## Provenance of the Japan desk figures

The Japan Desk page states a pre-registered source universe. Those figures are
research findings, not collection, and the page says so. For the record, they
were measured directly from the issuing institutions' own listings:

| Figure | Meaning |
|---|---|
| 21 HTML links, 0 PDFs | Ministry of Defense press-release listing, item format |
| 895 PDF links, 10 HTML links | Joint Staff press releases, whole 2014–2026 archive on one page |
| 135 | Joint Staff press releases, 2026 to mid-August |
| 214 | Joint Staff press releases, 2025 full year |
| 27 occurrences / would collapse 26 | Repeated title on the 2026 listing, which is why a title-only
  deduplication rule is unsafe for that source |

No Japan source is enabled, no Japan manifest is discoverable by the loader, and
the desk holds zero records.
