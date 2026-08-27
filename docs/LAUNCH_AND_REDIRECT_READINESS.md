# Launch and redirect readiness

What has to be true before Indo-Pacific Record replaces China Mil Watch as the
public identity, what the launch mechanically does, and how to roll it back.

**Executed 2026-08-27.** `DEFAULT_SITE_MODE` is `INDO_PACIFIC_RECORD`,
`DECLARED_SNAPSHOT` is `2026-08-26` / 3,574 / `d5b897cd…`, `output/CNAME` is
`indopacificrecord.org`, and `chinamilwatch.org` is served by a separate
redirect-only Pages site that sends each of its 1,451 published addresses to
its counterpart here. `DECISION_LOG.md` 2026-08-27 records what the launch
constrains; this document is kept as the plan it followed, corrected below
where the plan and the execution differed.

Two things the plan did not anticipate, both found by building it:

* The renderer is forbidden from the predecessor namespace, so it emits none of
  it. Replacing `output/` with its output would have deleted the thirteen
  editions and the cited assets. The publish is an exchange — see
  `CARRIED_FORWARD` in `site/render.py`.
* `/signals.html` moves, but the renderer emits no legacy route outside
  `/article/`. The publish writes that stub.

---

## 1. Gates — all owner-owned, none met by this branch

| # | Gate | State |
|---|---|---|
| 1 | One non-China desk collecting 30 consecutive days | **Not met.** Singapore is in shadow. The ledger holds the elapsed count; this document deliberately does not restate it. |
| 2 | That desk's source universe published | Scope is written down (`shadow/singapore_mindef/README.md`, and the registry entry). Publishing it is part of the launch, not of shadow. |
| 3 | Coverage health public | **Ready.** The candidate's Coverage page renders every stored outcome per source per run. |
| 4 | The 2026-07-17→24 collection outage disclosed | **Ready.** It renders on Coverage as a recorded gap, and on the legacy series page as the reason an edition is missing. |
| 5 | Owner sign-off recorded in `DECISION_LOG.md` | **Done**, 2026-08-27. |
| 6 | Trademark screening for "Indo-Pacific Record" | **Not performed.** A lawyer's job. |
| 7 | Domain, DNS, social handles, organization naming | **Domain and DNS done**: `indopacificrecord.org`, apex A/AAAA and `www` CNAME on Namecheap BasicDNS, account domain verified. Handles and organization naming remain open. |
| 8 | License | **Not chosen.** |

Gates 5 and 7 were closed at the launch. **Gates 1, 6 and 8 remain open**:
no second desk has thirty consecutive collecting days, no trademark screening
has been performed, and no licence has been chosen. The launch proceeded on the
owner's explicit instruction with those three outstanding, which is a decision
rather than an oversight, and none of the published pages claims otherwise —
the desk directory still shows one collecting desk of four.

---

## 2. What the launch mechanically is

Six changes, in this order. Each is reversible on its own. The first four are
as planned; the last two were found while executing it.

1. **Advance `DECLARED_SNAPSHOT`** in `site/preview/generate_preview.py` — date,
   record count **and** logical fingerprint, together, deliberately, with a
   changelog entry. The build refuses to publish a corpus that does not match
   it, which is the point.
2. **Flip `DEFAULT_SITE_MODE`** in `site/render.py` from `LEGACY` to
   `INDO_PACIFIC_RECORD`. One constant, one file. Nothing else in the tree
   selects a mode, and a contract test asserts no workflow sets the override.
3. **Turn on legacy routes** for the production build so `/article/<id>.html`
   emits its redirect stub. `render_site()` already passes `legacy_routes=True`
   on the non-legacy path.
4. **Regenerate `sitemap.xml` and `robots.txt`** so the sitemap lists
   destinations rather than redirects.

5. **Carry the predecessor namespace across.** `the-pla-watch/`, `assets/`,
   `data/`, the predecessor marks and `CNAME` are lifted out of `output/`
   before the new tree replaces it and put back after. The weekly pages are
   re-rendered against the new origin so the archive does not canonicalise
   itself onto a domain that redirects back to it.
6. **Write the `/signals.html` stub and put the carried pages back into the
   sitemap.** Neither is something the renderer can do: it does not own
   `/signals.html`, and it cannot list pages it is forbidden to see.

**Rollback is step 2 in reverse, plus `SITE_ORIGIN`**: set `DEFAULT_SITE_MODE`
back to `LEGACY` and `config.SITE_ORIGIN` back to `https://chinamilwatch.org`,
then re-run the daily workflow. The legacy renderer is untouched by any of
this and does not read `SITE_ORIGIN`, so it rebuilds exactly the site that was
there before. `output/` is regenerated from the database on every run.

### What the launch is not

It is not a repository migration, a database migration, a schema change, or a
rewrite of any published page. It *is* a domain change — that was decided after
this document was first written, and it is why the predecessor domain now has a
redirect site of its own rather than simply being dropped. The corpus, the record ids,
the source slugs, the content hashes and the thirteen published editions are the
same objects before and after.

---

## 3. Redirects

The full disposition of every currently-published route is
`site/url_transition_map.json`, validated by `tests/test_url_transition_map.py`
against the deployed tree. Summary:

| Category | Routes | Handling |
|---|---|---|
| Preserve unchanged | `/`, `/index.html`, `/archive.html`, `/methodology.html`, `/robots.txt`, `/sitemap.xml`, `/the-pla-watch/feed.xml`, `/the-pla-watch/.gitkeep` | Same address, new content where the page is regenerated. |
| Move with redirect | `/signals.html` → `/methodology.html`; `/article/{id}.html` → `/record/{id}.html` | One hop, canonical tag on the stub, `noindex` on the stub. |
| Preserve as legacy archive | `/the-pla-watch/` and everything under it | Untouched, labelled as published under the predecessor masthead. |
| Retire only with owner approval | `/data/articles.json`, `/favicon.svg`, `/logo-icon.png`, `/logo-wordmark.png`, `/og-image.png`, `/assets/editorial/*`, `/CNAME` | Nothing here removes them. |
| Never delete — cited evidence | `/article/{id}.html`, `/the-pla-watch/archive.html`, `/the-pla-watch/posts/{date}.html`, `/the-pla-watch/posts/{date}.json` | Permanent. |

**`/archive.html` is deliberately not renamed.** The navigation label became
"Record"; the URL did not. It is a live public address, and a label is free to
change while an address is not.

**`/article/<id>.html` may never be mass-redirected to the home page.** Every
stub names the record holding the same article, generated from the corpus rather
than from a directory listing, so an id absent from the snapshot acquires no
redirect to nothing. A test refuses any pattern route whose destination drops
the placeholder.

### Redirect mechanics

GitHub Pages serves static files, so each stub is a meta-refresh page carrying
`<link rel="canonical">` to its destination and `<meta name="robots"
content="noindex">`. That is what the candidate already emits. If the launch
moves to a host that can issue HTTP 301s, the map is the input for it — the
dispositions do not change, only the mechanism.

---

## 4. Verification before flipping the switch

Run in order; every one of these passes today on this branch:

```bash
.venv/bin/python -m unittest discover -s tests -t .
```

```bash
.venv/bin/python scripts/validate_output.py
```

```bash
.venv/bin/python site/preview/generate_preview.py --out /tmp/ipr-check --snapshot-from-corpus --legacy-routes
```

Then confirm, against the built tree:

* every `/article/<id>` stub resolves to an existing record page
* no page carries the predecessor name in its masthead, title or footer
* the About page and the legacy series page still say what the predecessor was
* the desk directory shows one collecting desk and three that are not
* Coverage lists the 2026-07-17→24 gap

---

## 5. After the launch

* Announce the name change on the legacy series page and in the feed, once.
  Subscribers hold `/the-pla-watch/feed.xml`, and it keeps its address.
* Leave the redirects in place permanently. They are cheap and they are the
  only thing standing between an old citation and a dead link.
* Do not delete `/data/articles.json`, the predecessor marks or the editorial
  imagery in the same change. Retiring an asset that published pages still
  reference is a separate, reviewable decision.
