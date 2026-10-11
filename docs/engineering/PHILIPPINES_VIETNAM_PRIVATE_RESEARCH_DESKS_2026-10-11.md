# Two usable private country desks: Philippines and Vietnam

**October 11, 2026.** Status: implemented offline analyst-facing research reader. **Neither country is production-admitted or publicly collecting through this feature.** The reader processes already-preserved immutable shadow records and exports only metadata and official source links. No publisher network access, model, tokens, SMTP, writing to source state, DB migration or public release.

## What the operator can do now

The command `scripts/private_country_desk_reader.py` works with the **actual existing SQLite schemas** of five independent collecting families:

| Desk | Original official source | Shadow source slug | Source branch |
|---|---|---|---|
| Philippines | Armed Forces of the Philippines, original AFP Public Affairs Office news | `ph_afp_articles` | `shadow/ph-afp` |
| Philippines | Philippine National Security Council's Official Statements category (site host is not always original issuing office) | `ph_nsc_official_statements` | `shadow/ph-nsc` |
| Vietnam | Ministry of Public Security, foreign-affairs section | `vn_mps_foreign_affairs_vi` | `shadow/vietnam-mps-foreign-affairs` |
| Vietnam | Ministry of Industry and Trade, energy | `vn_moit_energy_vi` | `shadow/vietnam-moit-energy` |
| Vietnam | Ministry of Industry and Trade, foundational industry | `vn_moit_foundational_industry_vi` | `shadow/vietnam-moit-foundational-industry` |

This is a **real reader**, not another status-only roadmap. An analyst may search text **privately in memory** and receive the matching source identity, institution, original-language title, publication date, first-seen run, pinned Git SHA and original government publisher link. For Vietnam, the reader joins each stored record to its currently referenced immutable body **version**; a partial version join is refused rather than hiding records. AFP and NSC have different SQLite row schemas and are never conflated.

For a private browser view, the command renders a self-contained HTML file with a search input, country filter and source-linked result cards. **The file does not embed source bodies, extracts, summaries, captured JSON, attachments or model outputs**. The client-side search filters only source metadata already in the page; CLI `--query` can search the privately held source body without including that text in output. Links go to the official issuer/publisher, not mirrored copies. Every record is prominently marked **PUBLIC REVIEW PENDING**.

### How to use it

First fetch or maintain each source's existing isolated Git branch into a **local trusted repository** outside the production checkout. Pin the *actual 40-character commit* you intend to read. The tool never fetches, follows or updates any branch itself and rejects names like `main`, unpinned `HEAD`, nonexistent commits, wrong issuer/slugs, wrong official-host URLs and missing Day 0 provenance.

For the Philippines sources, a sample command using placeholder **local** paths and real SHA-format inputs:

```bash
python -m scripts.private_country_desk_reader \
  --source ph_afp_articles,/absolute/local/private-ph-state-repository,EXACT_AFP_40_CHAR_SHA \
  --source ph_nsc_official_statements,/absolute/local/private-ph-state-repository,EXACT_NSC_40_CHAR_SHA \
  --country philippines --query maritime --limit 80 --format json > /private/philippines-search.json
```

For both desks and a local private browser page:

```bash
python -m scripts.private_country_desk_reader \
  --source ph_afp_articles,/absolute/local/private-state-repository,EXACT_AFP_40_CHAR_SHA \
  --source vn_mps_foreign_affairs_vi,/absolute/local/private-state-repository,EXACT_MPS_40_CHAR_SHA \
  --format html --limit 200 \
  --output /absolute/private/location/ipr-research-desks.html
```

Supply more `--source` values for the remaining NSC/MOIT family states. A single local repository may contain all fetched orphan branch commits, but each input needs its correct **individual SHA**. HTML output must be explicitly requested to a nonexisting destination outside the repository; it will not silently overwrite an existing file. JSON defaults to stdout so the user can redirect privately. **Do not upload or commit the generated report to IPR's public repository or output directory.**

## Trust, legal and editorial boundaries

An immutable *Git object identity* proves exactly which local snapshot is being read, **not** that the article was correct, that GitHub Actions ran reliably on every logical day, or that the source's licensing permits additional storage/translation. This reader cannot substitute for AFP seven-slot source/Actions provenance, Vietnam Day 7/14/30 reviews, original-language fidelity checks, rights decisions, full text completeness or owner production approval.

- AFP and NSC remain **separate institutional families** with separate clocks. NSC site byline may be a host rather than the original asserting authority; the reader labels it **publisher**.
- MPS and both MOIT sections are different families with distinct clock and robots records. Existing MOIT robots MIME anomalies must remain under review outside this UI; this reader does not erase them.
- Title/body searching reads **already preserved source bytes** only in local memory. No copied source body is rendered or saved; metadata still requires responsible private handling until source terms/human review are complete.
- A result matched by a full-text query means only that the literal text was preserved in the shadow store. It is **not a verified statement, corroborating source, analytical interpretation, citation license or public archive record**.
- The program never changes `desks/registry.json`, reads/writes `pla_watch.db`, enables any collector, schedules a run or exposes a public country route. The two countries have a practical private research workflow **now**, while separately governed production promotion remains later.

## Tests and next gate

```bash
python -m unittest tests.test_private_country_desk_reader -v
```

Tests create actual isolated synthetic Git commits and SQLite snapshots in a temporary directory, verify body-query matching without body disclosure, two different countries and source schemas, valid/invalid issuer links, immutable commit enforcement, HTML escaping/injection protection, strict output destination and no overwritten reports.

The next step toward **public functionality** is **not another metadata reader**. It is a source-specific admission PR when the real AFP and/or ministry evidence supports it: independently verified collection continuity, source/rights and original text review, bounded source scope, owner signoff, then safe production sync and public rendering. Until then, this provides tangible analyst use without misrepresenting a shadow feed as publicly live.
