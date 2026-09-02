# Site modes and the launch switch

This repository builds two frontends from one corpus. This document is the
operator's reference for which one runs, how to select the other, and how a
future launch and rollback would work.

**Updated 2026-08-27.** The public site is Indo-Pacific Record at
`https://indopacificrecord.org`; `indo-pacific-record` is the default mode and
`legacy` is the rollback path. The predecessor's domain is served by a separate
redirect-only Pages site. Sections below that still describe the pre-launch
arrangement are marked.

---

## The two modes

| Mode | Constant | Renderer | Writes to | Status |
|---|---|---|---|---|
| `indo-pacific-record` | `INDO_PACIFIC_RECORD` | `site/preview/generate_preview.py` | `output/` via `render_site()`, committed and deployed daily | **default, live** |
| `legacy` | `LEGACY` | `site/generator.py` | `output/` | rollback path only |

`indo-pacific-record` produces the record architecture — the parent publication
with its desks — and is what `https://indopacificrecord.org` serves. It became
the default on 2026-08-27.

`legacy` produces the predecessor's site exactly as it was, and is retained
solely so the launch can be reversed. It does not read `config.SITE_ORIGIN`, so
a rollback rebuilds the site that was there before rather than a hybrid.
**Never call `site/generator.py` as the production build.**

The mode string is `indo-pacific-record`; the earlier working name
`declared-record` is retired and is not accepted by `--mode`.

## Selecting a mode

`site/render.py` is the only place a mode is chosen. Precedence:

```
explicit argument  >  PLA_WATCH_SITE_MODE  >  DEFAULT_SITE_MODE
```

```bash
# the production build, into output/ (no --out needed only for legacy)
python site/render.py

# the record architecture, into a scratch directory
python site/render.py --mode indo-pacific-record --out /tmp/ipr \
  --site-origin https://indopacificrecord.org

# the rollback renderer, into a scratch directory
python site/render.py --mode legacy --out /tmp/legacy
```

`pipeline.py` calls `render_site()` with no mode, so the daily run resolves to
`DEFAULT_SITE_MODE`. No workflow sets `PLA_WATCH_SITE_MODE`, and a test asserts
none does.

## Fail-closed rules

These are contract, not convention. Each is covered by
`tests/test_site_mode_contract.py`.

* **An unrecognised mode raises.** There is no fallback to legacy. A typo that
  quietly published the wrong site is the failure this seam exists to prevent.
* **`indo-pacific-record` requires an explicit destination when not building production.** It cannot inherit the
  production `output/` default.
* **the candidate build refuses to write inside `output/`**, and the underlying
  `build()` refuses independently. Two guards, because one of them is the one
  that fails.
* **The snapshot guard aborts before writing** when the corpus does not match
  the snapshot it was *given* — the build will not publish a changed corpus
  under an unchanged snapshot identity.

  Which snapshot it is given depends on who is asking, and the distinction was
  added on 2026-08-28 after the launch broke production:

  | Caller | Snapshot | Behaviour |
  |---|---|---|
  | daily run — `render_site()` with no snapshot | derived from the corpus being rendered | renders what is there, truthfully |
  | release build — an explicit snapshot | exactly that declaration | renders that corpus or aborts |
  | `DECLARED_SNAPSHOT` | accepted launch metadata, 2026-08-26 / 3,574 | a historical pin, **not** the daily identity |

  Defaulting the daily run to `DECLARED_SNAPSHOT` is what made every render
  after the launch abort once collection passed 3,574 records — and because
  `daily_update.yml` runs the offline suite before the pipeline with no
  `continue-on-error`, that would have stopped collection too. The guard was
  not weakened: an explicit snapshot is still checked on date, count and
  logical fingerprint, and still aborts before anything is written.
* **The renderer reads the database through `reconcile_db._read_only`**, which
  works on a scratch copy. It never opens the tracked file.

## The launch switch

`DEFAULT_SITE_MODE` in `site/render.py`. One constant.

Launched 2026-08-27 by changing that constant to `INDO_PACIFIC_RECORD`. The
guard that refuses production `output/` was **not** removed: `render_site()`
builds into a scratch tree and exchanges it into `output/`, so
`generate_preview.build()` still refuses the destination it always refused, and
the exchange is what preserves the predecessor namespace it cannot render.

Rolling back is changing that constant back to `LEGACY`, changing
`config.SITE_ORIGIN` back to `https://chinamilwatch.org`, and re-running the
daily workflow, which rewrites `output/` from the legacy renderer.

There is no automatic launch condition anywhere in this repository. No date, no
counter, and no collection milestone flips this switch.

## Legacy route continuity

`/article/<id>.html` is a live URL today and some of those URLs are cited.
`indo-pacific-record` mode emits a redirect for every record in the snapshot,
generated from the corpus rather than from a directory listing, so an id outside
the snapshot cannot acquire a redirect to nothing. Each carries `noindex` so the
compatibility route never competes with the record page it points at.

This is off by default, so the in-repo preview build never creates the
production `article/` namespace.

## Determinism

`indo-pacific-record` builds are byte-identical across runs.

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
research findings, not collection, and the page says so.

**The figures and their attribution were re-measured and corrected on
2026-08-26**, and this document deliberately no longer restates them. The
authoritative statements are `desks/registry.json` (the desk's declared
research findings, observed volumes and volume caveat) and
`shadow/jp_mod/README.md` (what each feed actually is, categorised in full).
The correction matters: the earlier scope claim attributed items to the Joint
Staff and to an English estate that neither collected feed carries, and both of
those index pages are challenged and uncollected.

What remains true, and is the point of this section: **no Japan source is
enabled in production, no Japan manifest is discoverable by the desk loader, and
the desk holds zero records in `pla_watch.db` and zero on any public surface.**
Japan collects only into the isolated `shadow/jp-mod` state branch under shadow
evaluation — see `docs/SHADOW_COLLECTION.md`. Retrieval there is partial and
access-constrained, and nothing about it makes the desk qualified.
