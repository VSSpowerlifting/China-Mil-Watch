# Indonesia Ministry of Defense — Siaran Pers parser pilot

**8 October 2026 · Unregistered source, research stage**

This branch is deliberately separate from the October 9 editorial bridge, PR #215. It develops only the first engineering slice for a second Kemhan publication family: **offline parser shape, deterministic source identity, and refusal tests**. Nothing collects on a schedule, touches production or shadow data, changes `desks/registry.json`, sends an editorial email, or declares successful extraction from native press-release bytes.

## Why this family matters

The ministry's [Siaran Pers category](https://www.kemhan.go.id/category/siaran-pers) is visibly different from its routine [Berita category](https://www.kemhan.go.id/category/berita). The page includes ministerial communications and statements, including [the August 20, 2024 Australia–Indonesia ministerial statement](https://www.kemhan.go.id/2024/08/20/pernyataan-bersama-tingkat-menteri-tentang-kerja-sama-pertahanan-australia-indonesia.html). That statement discusses concluding negotiations for a treaty-level defense-cooperation agreement, **subject to domestic approval**, not evidence of completed implementation.

The most recent item visibly listed on October 8 was published **August 23, 2026**. The previous visible release is dated **March 23, 2026**. Thus automatic daily news expectations would be misleading. The value lies in higher-formality primary texts and historical dossiers, not numerical velocity.

Metadata-only leads are pinned to `research/indonesia/source_expansion/press_source_preflight.json`; they are not captured original HTML, not complete historical coverage, and not in any corpus.

## Implemented offline prototype

`scraper/sources/id_kemhan_press.py` provides pure HTML parsers for the specific listing family and for canonical linked articles. It reuses the existing Kemhan hostname, URL-date and Indonesian publication-date rules while insisting on category ownership, publisher masthead, expected pagination, canonical URL, date agreement, exact title continuity, bounded article container, and nonempty article text.

A second offline-only utility, `scripts/audit_indonesia_press_fixture.py`, accepts two locally supplied HTML files and a canonical article URL. It refuses unlisted articles or source-family/date/title drift, reports capture and extracted-text SHA-256 hashes, and marks **every** permission, authenticity and human-review approval field false. The validator authenticates neither source bytes nor transport identity; a future source-replay reviewer still needs real captured responses and an independently inspected original.

**Critical non-activation:** The module defines *no SourceAdapter subclass*. It is not referenced from any manifest, source registry, production pipeline, or `scripts/shadow_collect_desk.py` dispatcher. The parsers perform zero networking and database I/O. They intentionally cannot become a scheduled collector from this branch.

`tests/test_indonesia_press_parser.py` exercises the same core shape against **synthetically modified copies of immutable real Berita fixtures**. Those inputs are **not** real Siaran Pers captures. Tests cover family-label refusal, date and URL identity, page number, missing continuation, canonical/title disagreement, empty text and rejection of sidebar-only content. They guard against false readiness, not prove the live category's DOM matches the assumed shape.

## Why native collection is still blocked

1. **Native source policy:** The existing collector read robots successfully for the Berita seed, but this exact source family still needs an explicit native identified robots/listing preflight. Browser or search access alone is not that evidence. An unreadable robots policy or disallow blocks further requests.
2. **Real fixtures:** Capture original bytes with the existing named collector identity, no redirects/proxies/identities/challenge solving. Save listing first and second page if linked; capture at least one full ministerial statement and one recent release, plus exact response SHA-256, dates, URL and content type.
3. **Fidelity:** Compare extracted original-language text, paragraph boundaries, press-number and signatory lines against complete source bodies. The shared article design can contain nested markup; synthetic shape tests are insufficient.
4. **Cross-family deduplication:** Use canonical URLs and body hashes, not titles or the page where the URL was listed. A record appearing under Berita and Siaran Pers must not be stored twice as independent publications.
5. **Source-specific health:** If the category has been dormant since August, a healthy October listing may produce zero date-matched items. This is not source access failure or permission to claim complete coverage. A known old listing with valid pagination is a different condition than broken HTML, blocked access or a missing page.
6. **Data rights and authorization:** Obtain applicable publication/reuse assessment and explicit authorization for any separate shadow collector, remote state, schedule, or production addition. Do not reuse the first Berita shadow clock to certify this new family.

### Verification and stop condition

Before merge, run this new offline parser suite, the existing Indonesia/Korea shadow tests and the full PR CI including DB/output preservation. A green result proves offline code quality only. **Stop at the parser prototype; do not activate this source in the same PR.**

**Next engineering phase, after PR review:** native byte/policy source preflight with capped URLs and a new isolated fixture set; then adapt the parsed release types to a separate disabled shadow source with its own evidence. Source collection and promotion should each receive independent authorization.
