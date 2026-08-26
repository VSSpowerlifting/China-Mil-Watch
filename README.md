# PLA Watch

An independent Mandarin-source monitoring and analysis project that tracks
Chinese military and security reporting from official and authoritative PRC
sources, translates and summarizes daily reporting, and publishes a
structured brief to a static website updated on a 24-hour cycle.

This is an academic portfolio project.  It does not use or claim access to any
classified information.  All source material is publicly available.

---

## What It Does

China Mil Watch currently monitors PLA Daily and is configured for expansion
across additional official and state-linked sources including MND, China Military
Online, Global Times Military, and Xinhua Military. It filters content for
relevance, translates Chinese-language articles to English, generates analytic
summaries, and marks model-flagged items (a software triage cue, not an editorial judgment).
Results are stored in a local SQLite database and published as a static site
suitable for hosting on GitHub Pages. Some sources may return zero articles on
a given day; Xinhua Military remains in development because its listings are
JavaScript/API-rendered.

The tool is designed to reduce the friction of monitoring official Chinese
military media for analysts, researchers, and students who cannot read
Chinese at speed, while preserving the original source text for those who can.

---

## Sources

| Source | Language | Coverage |
|--------|----------|---------|
| PLA Daily (`81.cn`) | Chinese | CMC-attributed statements; official PLA narrative |
| Ministry of National Defense (`mod.gov.cn`) | Chinese | MND press releases; spokesperson statements |
| Xinhua Military (`xinhuanet.com`) | Chinese | Amplified PLA/MND items |
| Global Times Defense (`globaltimes.cn`) | English | Official-line commentary for foreign audiences |
| China Military Online (`english.chinamil.com.cn`) | English | English mirror of PLA Daily ecosystem |

All sources are organs of the Chinese state.  See [METHODOLOGY.md](METHODOLOGY.md)
for a full discussion of source biases and what these outlets do and do not
report.

---

## Methodology

The relevance filter, translation approach, analytic summary framework, and
significance flag criteria are documented in detail in [METHODOLOGY.md](METHODOLOGY.md).

Short version: keyword pre-filter → LLM relevance scoring → LLM
translation and summary → category tagging → significance flag.
Everything is stored; thresholds are tunable.

---

## Limitations

- **Public sources only.**  This project does not surface anything the PLA
  has not chosen to publicize.
- **Machine translation.**  Chinese military and doctrinal terminology does not
  always translate cleanly.  Original text is preserved; treat translations
  as assistive, not authoritative.
- **LLM errors.**  Relevance scores, summaries, and significance flags can be
  wrong.  Review the source before acting on a flag.
- **Scraper fragility.**  CSS selectors break when sites redesign.  Check the
  run log if articles stop appearing.
- No historical data prior to first deployment.

---

## Project Structure

```
pla-watch/
├── scraper/            # Source-specific scrapers (one class per source)
│   └── sources/
├── processing/         # Dedup, keyword filter, metadata normalization
├── analysis/           # LLM translation, summary, categorization (prompts.py)
├── storage/            # SQLite schema and data access layer
├── site/               # Jinja2 static site generator
├── .github/workflows/  # GitHub Actions daily scheduler
├── cache/              # Raw HTML cache (gitignored)
├── output/             # Generated static site (published to gh-pages)
├── pipeline.py         # Main pipeline runner
├── config.py           # All tunables and keyword lists
├── METHODOLOGY.md      # Sourcing rationale, caveats, analytical framework
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.9 — the version every workflow pins. `docs/ARCHITECTURE_AND_PUBLISHING.md`
  §4 is the governing statement: keep the validator and the site generator
  3.9-compatible, or CI cannot run them.
- An [Anthropic API key](https://console.anthropic.com/)
- A GitHub account

### Local installation

```bash
git clone https://github.com/VSSpowerlifting/China-Mil-Watch.git
cd China-Mil-Watch
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=your_key_here
```

### Initialize the database and run a test scrape

```bash
# Scrape PLA Daily only, no DB writes (for testing)
python pipeline.py --source pla_daily --dry-run

# Full run against all sources
python pipeline.py
```

### Generate the site

`pipeline.py` renders the site itself at the end of a successful run, so this
is only needed to re-render from the database without collecting.

```bash
python site/generator.py
```

`site/render.py` is the mode switch that decides which frontend gets built; it
defaults to the legacy site, which is the one that is published. See
`docs/SITE_MODES.md`.

Validate before trusting any output change — this is the same gate CI applies
before it deploys:

```bash
python scripts/validate_output.py
```

---

## Deployment (GitHub Pages + GitHub Actions)

### 1. Create the repository

Create a new **public** repository named `pla-watch` on GitHub.
Push your local code to the `main` branch.

### 2. Add the API key as a secret

In your repository: **Settings → Secrets and variables → Actions → New repository secret**

- Name: `ANTHROPIC_API_KEY`
- Value: your Anthropic API key

### 3. Enable GitHub Pages

In your repository: **Settings → Pages**
- Source: `Deploy from a branch`
- Branch: `gh-pages` / `/ (root)`

GitHub will create the `gh-pages` branch automatically on first workflow run.

### 4. The workflow

The file at `.github/workflows/daily_update.yml` schedules five windows
between 12:23 and 14:23 UTC and lets a scheduling guard admit **one** of them
per New York day; the other four exit immediately. The one that runs collects,
regenerates the site, commits `pla_watch.db` and `output/` to `main`, and
deploys `output/` to `gh-pages`.

Because the four skipped runs also report success, **a green check is not
evidence that the pipeline executed.** To tell the two apart, open the run and
look at the `Scheduling guard` step: it prints `should_run=true` or
`should_run=false`, and every later step is skipped when it is false.

This deployment serves:

```
https://chinamilwatch.org
```

---

## Contributing

This is a portfolio project, but issues and pull requests are welcome.
If you find a scraper is broken due to a site redesign, open an issue with
the new HTML structure.  If you improve a prompt, open a PR with before/after
examples showing the change in output quality.

---

## License

The repository holds material under different terms, so one line cannot cover it.

* **Software** — MIT. Full text in [`LICENSE`](LICENSE).
* **Original editorial analysis, issue text and site copy** — copyright
  Benjamin Yang, all rights reserved.
* **Official source documents and quotations** — remain under the terms of the
  institutions that published them. This project does not relicense them.
* **Underlying public facts** — claimed by nobody, including this project.

[`CONTENT_AND_DATA_RIGHTS.md`](CONTENT_AND_DATA_RIGHTS.md) sets out the scope
of each in full. The MIT grant covers the machinery, not the journalism and not
the ministries' documents.

---

*This project is independent academic work.  It is not affiliated with any
government agency, research institution, or think tank.  It does not use
classified information.*
