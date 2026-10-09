# Daily browser prerequisite — bounded fail-closed setup

## Incident and reason

The original [October 7 Daily run #37671050416](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37671050416) passed its scheduling guard with `should_run=true`, installed Python dependencies, then entered `playwright install chromium --with-deps` at **19:00:17 UTC**. Its Ubuntu APT mirror requests produced `Ign:`/retry observations until **19:01:12**, after which the job produced no more browser-install output until an operation cancellation at **23:37:21 UTC**. The pipeline, migrations, rendered output, commit, Pages deploy and successful-day marker **all skipped**. This is a system-package/browser prerequisite stall, not evidence of official-site silence, model failure, or a completed collection.

## Change

Set a **15-minute GitHub Actions step timeout** on `Install Playwright browser`, retaining its original `playwright install chromium --with-deps` command, `should_run=true` scheduling guard, job privileges, and prerequisite position **before** migrations, offline tests, collection, analysis and publication.

The timeout is intentionally a **failure**, not a successful no-op or silent fallback. Downstream publish-path steps retain their implicit GitHub Actions `success()` gate: if the browser setup fails or times out, collection and deployment do not run, the successful-day marker is not written, and no partial site output is published.

It does **not** adjust the five Daily schedule windows, the `daily-update` concurrency policy, model/analysis cap, sources, traffic, archive DB, or billing cost. The change limits a recurrence of one known stall; it does not prove APT mirror reliability or identify the person/system that ultimately cancelled October 7's job.

## Verification

```sh
python -m unittest tests.test_daily_browser_preflight_timeout -v
python -m unittest tests.test_workflow_contract -v
```

The first suite statically enforces browser command + bounded timeout, step ordering, scheduling guard and continued fail-closed publication gates. These are **offline source contracts**, not proof of a live timeout firing on GitHub's runners. The dedicated CI also checks tracked `pla_watch.db` and `output/` are unchanged. Before merging, require the full repository PR offline suite (Chromium, offline tests, rendered-output validator, tracked database/output preservation) on current main.

The first live production execution after merge will establish the actual runner behavior. If a future timeout occurs, inspect its Actions run/job receipt, keep the run red, and do not automatically rerun or mark the day complete. See [Issue #268](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/268).
