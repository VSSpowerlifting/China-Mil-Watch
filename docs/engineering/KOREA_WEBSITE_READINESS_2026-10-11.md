# Korea Desk website preparation — hidden, site-equivalent review page

**2026-10-11** · This PR adds a private, source-bound prototype of the eventual Korea website page **using the production site's Jinja desk template and CSS**, not another disconnected mockup. It is never written to `output/`, does not modify `desks/registry.json`, and does not publish a Korea page.

## Existing state

Korea is listed **internally** as `status=shadow, public=false, manifest=null, has_production_records=false` (merged PR #415). Existing-Git original source reader and review workbench operate (PRs #410, #413, #414). Exactly five original Korean HWPX documents passed machine SHA parity. AI-assisted Korean reading and KOGL text-only notice observations are **not human approval**.

## Actual website-level prototype

Run:

```sh
python -m scripts.preview_korea_site --out /tmp/ipr-korea-site-review
# Open /tmp/ipr-korea-site-review/korea.html locally.
```

The script generates the real IPR site into a **new, exclusive-use directory outside the repository**, with the exact normal header, navigation, masthead, typography, responsive CSS, and full desk research/blocker sections. It then generates **one extra unlinked `korea.html` page** only for private design review.

The prototype shows official Korean titles linked to the canonical government source, source identity and text hash, **both distribution and posting dates**, MND as issuer and Policy Briefing as publisher, strict context limitations, and explicit record-by-record `HOLD` status. The October 4 versus October 6 date distinction is directly visible. There are **no original HWPX bytes or article bodies, inferred English summaries, images or government seals**.

The page is `noindex` and **not in desk navigation or sitemap**. Passing any `site_origin`, test origin, synthetic brief, other editorial review or gallery flag to this mode raises; the target cannot be an existing directory, symlink, repository directory, or ancestor. No public build calls this flag: the default is `review_korea=False`.

## QA and release control

PR-only Actions builds the same actual site and audits six negative/positive cases. It checks the ordinary public roster still omits Korea, current Korea registry remains non-public, only five known source IDs render, no bodies/media leak, no href to unapproved local archive records, source date distinction survives and production database/output SHA hashes remain untouched.

An eventual **separate public release PR** may change `public` to true and show approved metadata **only after** independent Korean reviewer source/visual HWPX signoff, per-page and per-attachment text-only rights decisions, owner publication approval and exact SHA-bound signoffs for every item. The future public release must use a narrowly curated, separate approved reference manifest, **never `research/korea_reference_candidates.json` as a public source**. No collection, DAPA, RSS, auto-translation or Sunday Brief admission is implied.

Keep this PR disabled and mergeable as rendering infrastructure only. A passing private page build is readiness to review design, **not approval to launch**.
