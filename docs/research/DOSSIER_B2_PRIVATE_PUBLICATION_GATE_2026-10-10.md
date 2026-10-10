# Living Dossiers B2.1 — private publication-boundary prototype

**Status: synthetic engineering implementation only; NOT a release approval.**

## Scope and dependency

Adds core/dossier_publication.py and tests/test_dossier_publication.py on an isolated branch **stacked on B1.3 PR #330**. That branch depends on B1.2 #329 and B1.1 #328. The four layers must be reviewed, retargeted and integrated in order, with fresh exact-head repository CI after each. This branch adds no site, output, Dossier content, source database, scheduler or publisher communication.

The public eligibility result is hard-set to false, and production authority is hard-set to unconfigured. This is deliberate: there is no independently authenticated owner, source-use, or signed-release provider in the repository yet. A B1 content digest, source-use reference inside authored JSON, or a simulated approval cannot authenticate a real editor or publisher permission.

## Implemented prototype

The assess_dossier_release entrypoint uses the authoritative B1.1 strict parser and content digest. It checks a supplied private B1.2 archive report for exact slug, digest, record IDs, reported identity-parity status, and per-record screening evidence. A supplied independent-looking packet is **simulated**, never authenticated; it is inspected only in explicitly enabled private synthetic-preview mode.

Synthetic preview is intentionally limited to fictional-* slugs whose source URLs all use HTTPS and RFC-reserved example.org/example.invalid domains. Even if every fake review condition passes, the response remains eligible_for_publication=false; the only positive status is private_synthetic_preview_ready=true, which is never passed to the public site.

## Separate gates enforced in fictional review

- An eligible source record is not automatically admitted by human editorial review, even if machine relevance is selected. Pending and negatively screened records require an additional explicitly recorded fictional reviewer disposition.
- Metadata use, publisher hyperlink, official-origin review, local record hyperlink, and review of an existing local page that publicly distributes full captured publisher text are distinct booleans. A metadata grant does not authorize quotations, full bodies, images or hyperlinks.
- Every positively cited record must have a cleared navigable citation channel. An uncleared record link cannot be replaced with an uncited material claim.
- The fake owner and claim-review packet must refer to the exact authored Dossier digest and revision. Synthetic revision 2 or later requires a separately asserted predecessor-history check; a change-log entry alone is not proof.
- Diagnostic results carry only approved machine codes, numeric fixture IDs, a slug, a content digest and synthetic link-policy booleans. No original publisher body, source URL, permissions correspondence or unpublished inference is echoed. The synthetic-only preview additionally refuses IDs outside the reserved 900000–999999 fixture range and checks that contrary/counterevidence citations have cleared navigation, not just supporting citations.
- The production path never has a conditional branch that returns publication eligibility true. A real release provider must be designed and approved separately, including trust anchor, signatures/identity, action-specific publisher-use scope, revocation, and incident response.

## Tests

28 focused synthetic tests in tests/test_dossier_publication.py cover valid fake preview, production fail-closed behavior, forged or missing authority, body-use and link disaggregation, author/claim screening, stale digest, report mismatch, input IDs, amendment history, malformed action policies, and body/link nonleakage.

Run with the full dependency stack in a checkout:

    python -m unittest tests.test_dossier_contract tests.test_dossier_sources tests.test_validate_dossiers tests.test_dossier_publication -v

**Verified with real repository B1 sources:** [focused GitHub Actions run #38055640626](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38055640626) completed successfully on Python 3.9: **139/139 tests** (67 B1.1, 23 B1.2, 21 B1.3, 28 B2.1), plus Python compilation and unchanged tracked SQLite, Briefs, Timelines and output. The temporary one-time workflow was removed after the passing run and is not in the lasting PR diff. The resulting no-workflow PR commit needs an independent exact-head full repository CI run after its upstream dependencies are integrated. The earlier local B1 stub run remains preliminary evidence only, superseded by this real-code focused verification.

## Hard stop and future phases

Do not merge B2.1 ahead of #328, #329, #330; do not advertise fake receipt flags as verified rights or human authentication. Actual Dossier sidecars remain gated under B0 #319 and MINDEF rights review #326. Shared frontend owners must first reconcile Timeline #181 and sitewide frontend #323 before work on B2.2 (private view model / Jinja prototype) or B2.3 (Analysis links).

This engineering slice deliberately does **not** create a public Dossier reader, route, renderer, sitemap entry, feed, CLI approval command or deployment path. Its acceptance gate is review of the new pure source and tests, exact-head full CI, source/archive preservation, and explicit human decision on integrating the dependency stack.
