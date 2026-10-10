# Living Dossiers B2.2b — Standalone Fictional HTML Review Prototype

**Engineering state:** private, fictional, nonpublishing proof of presentation. Branch is stacked on [draft B2.2a PR #339](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/339), which itself depends on #335 → #330 → #329 → #328. Do not merge out of order, publish the demo, or use it with real records.

## Implementation

- `core/dossier_private_html.py` renders an **HTML string only**, from the actual B2.2a `build_private_dossier_view()` call. It never accepts a caller-supplied view blob in lieu of the gated source, and never writes to disk, registers a route, accesses a source DB, reads files or renders any site template.
- `tests/test_dossier_private_html.py` contains 21 synthetic tests, including actual B1.2 fictional SQLite → B2.1 gate → B2.2a projection → B2.2b HTML string with unchanged DB bytes.
- This scope document.

The prototype presents a clearly watermarked invented title/dek, bounded research question, scope and explicitly disclosed collection limitations, editorial claim/issuer distinctions, source-level supporting and counterevidence links, unresolved disagreements, dated revisions and language-aware source ledger. It includes a responsive two-column/one-column layout, keyboard-visible focus, a skip link, no JavaScript and a print stylesheet.

## Safety architecture

The renderer is gated by the **current** fictional preview evaluator. It refuses real source record IDs/hostnames, drafts, stale evidence, an unverified screening hold, changed original body or a B1.3 review-diagnostic shape masquerading as a B1.2 source report. It also refuses any projection that suddenly advertises public publication, indexing, canonical, feed, sitemap or route eligibility.

Every source citation is an **internal same-page fragment anchor**, never a link to an IPR record page, the invented source URL or a live publisher. The model's fictional source URLs are not emitted, even as text. All variable titles, prose, notes and HTML attributes pass through `html.escape`.

The page has a prominent fictional private-review watermark, `robots=noindex,nofollow,noarchive,nosnippet`, a no-referrer instruction and strict default-deny Content Security Policy (inline CSS only, no scripts, images, forms, external assets or network requests). The output does not contain the original publisher body, model findings, permission correspondence, public sitemap, live analytics or cross-publication backlinks.

**Security caveat:** An HTML string and robots meta tag do not create access control. No demo file may enter `output/`, a static host, a deployment artifact, a published pull request preview, or a web-accessible bucket. The future private preview runner needs separate auth/access restriction, filesystem output safeguards and an explicit end-to-end review before HTML may be delivered to a browser. The current function has **no output path**, so it cannot perform such a delivery on its own.

## Interface ownership

This branch does **not** touch `site/render.py`, production `site/preview/` Jinja templates, `analysis.html`, `brief.html`, `timeline.html`, site CSS, `output/`, `pla_watch.db`, source manifests, workflows, or deployment settings. It does not reconcile #181 or #323 or claim adoption of the current settled Paper Ledger design. This is an inert illustration of the content anatomy and interaction-free information architecture that can be handed to the eventual single frontend owner.

## Testing and integration gates

Run the synthetic dependency chain:

```bash
python -m unittest tests.test_dossier_contract tests.test_dossier_sources \
  tests.test_validate_dossiers tests.test_dossier_publication \
  tests.test_dossier_private_view tests.test_dossier_private_html -v
```

Acceptance: the full synthetic stack passes on real repository modules, stable HTML output for identical inputs, all fragment links resolve, zero external sources, no escaped text becoming markup, no publisher originals or private receipt fields, no tracked DB or `output/` mutation, and a separate full offline repository CI run on the eventual merged/rebased exact head.

**Current publication state remains impossible.** No authenticated editor receipt, independently adjudicated publisher rights, private retention/public permission, approved real Dossier, or production renderer is implemented here. Source admission #319 and rights scope #326 are independent human gates.

## October 10 focused integration receipt

[GitHub Actions run #38065127259](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38065127259) completed with **207/207 synthetic tests passing** on Python 3.9: 67 B1.1, 23 B1.2, 21 B1.3, 33 B2.1, 42 B2.2a, and 21 B2.2b tests. It compiled the actual six-slice stack and confirmed tracked SQLite/output/Briefs/Timelines were unchanged. The one-time workflow was deleted in commit `6a1fc177740a5e07395e20bc32dddd4491cac51a` after success, leaving only the three source/test/documentation files in the PR. This receipt applies to the **temporary testing commit** and is not exact-final-head full repository CI after the upstream stack is integrated.

Separately, the parent reader's [canonical full offline Actions #38063789367](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38063789367) succeeded with **5,462 discovered tests, nine skips**, actual Chromium launch, rendered-output validation (ten nonfatal warnings), and unchanged tracked SQLite and output. It covered the **earlier** parent revision, before its two claim-relocation regressions. The completed 207-test six-slice focused run includes those regressions but is not a full-suite substitute.
