"""
Private regional-IA prototype. Renders to an ignored directory; never to
production `output/`.

WHY THIS IS NOT A FLAG ON site/generator.py
-------------------------------------------
The production generator renders the *current* product: a China-only daily brief
plus the weekly. This prototype renders a *different information architecture* —
parent brand, desk directory, source universe, coverage health — for a product
that does not exist publicly yet. Those are different page sets, not different
settings, and threading a `--regional` flag through `generate_site()` would put
unshipped IA inside the function that writes production output on every CI run.
The constraint that matters more than code reuse is that `output/` cannot
change; a separate entry point makes that structural rather than careful.

What IS shared, deliberately: the database (read-only), the real corpus, the
design tokens, and the evidence vocabulary. Nothing is duplicated that could be
imported.

SAFETY
------
  * The database is read through `reconcile_db._read_only`, which works on a
    scratch copy. The tracked `pla_watch.db` cannot be modified by this script
    even by accident — it is WAL-mode, so a plain connect() would be a write
    (DECISION_LOG 2026-08-14).
  * The output directory defaults to `preview/`, which is gitignored. Writing
    into `output/` is refused outright.
  * No network. No model calls. No collection.
  * Deterministic: two consecutive builds produce byte-identical files. There is
    no wall-clock timestamp anywhere in the rendered output — a "generated at"
    line would make determinism untestable, and the corpus date is the honest
    thing to show anyway.

USAGE
-----
    .venv/bin/python site/preview/generate_preview.py
    .venv/bin/python site/preview/generate_preview.py --serve      # localhost:8770
    .venv/bin/python site/preview/generate_preview.py --title "Some Other Name"

The working title is configuration, not a literal, so an approved name is
applied in exactly one place. It is NOT a public name and NOTHING here is
deployed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from jinja2 import Environment, FileSystemLoader                    # noqa: E402
from scripts.reconcile_db import _read_only                         # noqa: E402

TEMPLATES = Path(__file__).parent / "templates"
DEFAULT_OUT = REPO_ROOT / "preview"
PRODUCTION_OUT = (REPO_ROOT / "output").resolve()
TRACKED_DB = REPO_ROOT / "pla_watch.db"

#: Preferred WORKING name. Approved 2026-08-15 as the preferred candidate,
#: pending USPTO/EUIPO trademark clearance and reader testing
#: (docs/transition/FRONTEND_AND_BRAND_REVISION_BRIEF.md §1). NOT adopted, NOT
#: public, NOT registered. It occupies the codename slot `Western Pacific
#: Record` previously held.
WORKING_TITLE = "The Declared Record"

#: Approved 2026-08-15. US spelling ("defense") is the ruling; the prototype's
#: earlier British spelling is corrected throughout to match.
TAGLINE = ("Official defense and security texts, preserved as published and "
           "analyzed in context.")

#: Used ONLY as an eyebrow above corpus and record surfaces. It is not the
#: tagline, not a subtitle, and never appears in the masthead.
CORPUS_EYEBROW = "As published."

#: Maintainer. Name, role, contact and biography are owner-approved
#: (2026-08-15). The historical sidecar `author_bio` and `author_title` values
#: are NOT changed by this — they are the canonical record of what each
#: published edition said at the time.
MAINTAINER = {
    "name": "Benjamin Yang",
    "role": "Creator and Editor",
    "bio": ("Benjamin Yang studies International Affairs at George Washington "
            "University’s Elliott School, with interests in U.S.–China "
            "relations, public diplomacy, and security affairs. He writes "
            "The PLA Watch and maintains the project’s collection pipeline."),
    "email": "ben.yang@gwmail.gwu.edu",
    "linkedin": "https://www.linkedin.com/in/benjamin-yang-42b525294",
}

#: Desks the prototype displays. `live` is the only one with data; the others
#: exist to show the shape of the future product WITHOUT inventing activity.
#: Any count, chart or sample item for a non-live desk would be fabrication.
DESKS = [
    {
        "id": "china", "name": "China Desk", "state": "live",
        "state_label": "Live — collecting",
        "note": "Collecting since 2026. The corpus below is real.",
    },
    {
        "id": "japan", "name": "Japan Desk", "state": "scoped",
        "state_label": "Pre-registered scope — not yet collecting",
        "note": "Two source families have been researched and are documented "
                "below. No source is enabled and no records have been "
                "collected.",
    },
    {
        "id": "us-indopacific", "name": "US Indo-Pacific Reference Desk",
        "state": "development",
        "state_label": "In development — not yet scoped",
        "note": "Scope deliberately bounded to a reference desk. Its source "
                "universe has not been researched to the standard applied to "
                "Japan, so none is claimed here.",
    },
]

#: Japan pre-registered scope. Every figure below is carried from
#: docs/transition/SECOND_DESK_SOURCE_UNIVERSE.md, where it is marked
#: `verified`. Nothing is estimated, and no field is filled in that the
#: research left deliberately unset.
JAPAN_SCOPE = {
    "sources": [
        {"name": "Ministry of Defense — press releases",
         "format": "HTML — 21 HTML links, 0 PDFs on the listing",
         "note": "Listing verified; item format verified."},
        {"name": "Joint Staff — press releases",
         "format": "PDF only — 895 PDF links, 10 HTML links on the page",
         "note": "One page holds the entire 2014–2026 archive; the year "
                 "“tabs” are in-page anchors, not separate pages, so "
                 "no pagination or year-walking is required."},
    ],
    "volume": [
        ("2026, to mid-August", "135"),
        ("2025, full year", "214"),
        ("2014–2026, whole archive", "895"),
    ],
    # Reader-facing wording. No raw field names, no repository language.
    "blockers": [
        ("PDF extraction is required.",
         "Joint Staff releases are published as PDFs. The current pipeline "
         "does not extract them, so a working collector must be built and "
         "tested before collection begins."),
        ("Repeated titles require a different deduplication rule.",
         "On the 2026 listing, “Japan-U.S. Bilateral Exercise” appears 27 "
         "times for distinct events. A title-only rule would collapse 26 of "
         "those 27 records."),
        ("Collection-health thresholds remain unset.",
         "Publication cadence and silence thresholds will be calibrated only "
         "after 30 days of shadow collection; guessing now could create false "
         "alarms or hide real silence."),
    ],
}

#: Plain-language explanations of the stored status vocabulary
#: (core/collection/status.py). Wording is reader-facing, meaning is not
#: reinterpreted.
#: Short note for the per-run results table. Kept separate from STATUS_PROSE so
#: the run table stays terse while the meanings table can be fuller. The stored
#: `error_detail` is only shown for genuine failures — for `not_implemented` it
#: carries an internal phrase ("adapter is a documented stub") that is
#: repository language, not reader language.
STATUS_RUN_NOTE = {
    "not_implemented": "Configured, but no working collector exists.",
}

#: Reader-facing labels for the stored `sources.source_type` enum. The stored
#: values are never changed — this is display only, and an unknown value falls
#: back to its raw form rather than being silently dropped.
SOURCE_TYPE_LABELS = {
    "armed_forces_newspaper": "Armed forces newspaper",
    "ministry_website": "Ministry website",
    "state_news_agency": "State news agency",
    "state_linked_newspaper": "State-linked newspaper",
    "armed_forces_english_portal": "Armed forces English-language portal",
}

STATUS_PROSE = {
    "ok": ("Collected", "Reached the listing and stored new items."),
    "ok_no_publications": ("Nothing published",
                           "Reached the listing; it carried nothing new. "
                           "This is healthy."),
    "ok_all_duplicates": ("Nothing new",
                          "Reached the listing; everything it offered was "
                          "already in the archive. This is healthy."),
    "ok_all_filtered": ("Nothing relevant",
                        "Collected fine; nothing met the topic filter."),
    "not_implemented": ("Not implemented",
                        "Configured, but no working collector exists yet. It "
                        "contributes nothing by design — and is reported every "
                        "run so it cannot be mistaken for a healthy source."),
    "skipped_disabled": ("Disabled", "Configured but switched off."),
    "listing_failure": ("Could not reach",
                        "The listing could not be retrieved or parsed. The "
                        "empty result is a fault, not silence."),
    "extraction_failure": ("Could not read",
                           "Pages were fetched but nothing usable was parsed — "
                           "usually the source changed its markup."),
}

#: Declared snapshot identity. Ruled 2026-08-16: this is *editorial metadata*,
#: deliberately declared — NOT inferred from `MAX(published_date)`, which is how
#: an earlier draft derived it. Inferring it means a changed corpus silently
#: republishes under an unchanged snapshot date.
#:
#: `expected_records` is asserted against the database at build time. A real
#: build against a database holding a different number of records FAILS rather
#: than retaining this date. Advancing either field is a deliberate act that
#: requires a changelog entry.
#:
#: Tests pass their own `Snapshot(...)` for fixtures. The default below is the
#: production-preview assertion and is never relaxed to accommodate a fixture.
#: Stored and joined values that can affect the reader-facing snapshot. The
#: fingerprint covers all of them, so a corpus cannot change while keeping the
#: same identity. Derived display labels, record paths and week groupings are
#: deliberately excluded — they are functions of these values, and hashing them
#: would make a presentation change look like a corpus change.
#:
#: `content_hash` is included but never relied on alone: it is computed once at
#: insert and never recomputed, so a corrected body would leave it stale. The
#: raw `text_original` and titles are hashed alongside it for that reason.
LOGICAL_FIELDS = (
    "id", "url", "title_original", "title_english", "published_date",
    "summary_english", "analyzed_at", "model_id", "prompt_version",
    "is_significant", "content_hash", "scraped_at", "scrape_run_id",
    "text_original", "passed_relevance", "source_slug", "source_name",
    "language_tag", "institution_id", "institution",
)


def corpus_fingerprint(corpus) -> str:
    """SHA-256 over a canonical serialization of the whole corpus.

    Records are sorted by database id ascending, so display order cannot move
    the result. Keys are sorted, separators are fixed, `ensure_ascii` is off and
    the blob is encoded UTF-8, so Chinese text hashes identically everywhere.
    Missing values serialize as JSON `null`, which is distinct from `""`.
    """
    rows = [{field: record.get(field) for field in LOGICAL_FIELDS}
            for record in sorted(corpus, key=lambda r: r["id"])]
    blob = json.dumps(rows, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


#: Declared snapshot identity. Ruled 2026-08-16: editorial metadata, declared
#: rather than inferred.
#:
#: `logical_sha256` binds the identity to the corpus CONTENT. Date and row count
#: alone cannot: a record could be replaced, or a body corrected, while the
#: count stayed at 3,250 and the snapshot silently kept its name. This is an
#: INTERNAL BUILD-INTEGRITY GUARD only — it is not a DOI, not a public version,
#: and never appears in a citation.
#:
#: A fixture may set `logical_sha256` to None to opt out explicitly; the real
#: default carries a literal digest and is never relaxed.
DECLARED_SNAPSHOT = {
    "date": "2026-08-19",
    "expected_records": 3388,
    "logical_sha256":
        "cab9b24c8283749439068af206a79eaf163add2a91d17aebe8e1c192d4da583c",
}

#: The four reader-facing processing states (DECISION_LOG 2026-08-16 §2).
#: Mutually exclusive and exhaustive over `articles`, in reader-facing order.
#: Codes are internal; labels are the only strings a reader sees.
#:
#: `model_flagged` marks the ONE state in which the article-level machine flag
#: (`is_significant`) carries meaning. That column is NOT NULL DEFAULT 0, so its
#: zero conflates "assessed and not flagged" with "never assessed" — exposing it
#: outside the analyzed set would assert a judgement that was never made.
PROCESSING_STATES = [
    {"code": "analyzed", "label": "Analyzed", "model_flagged": True,
     "definition": "Passed relevance screening and completed analysis. "
                   "English title and summary are machine-generated."},
    {"code": "not_selected", "label": "Not selected for analysis",
     "model_flagged": False,
     "definition": "Screened and not selected for analysis. The original "
                   "record is stored; no translation or summary was produced."},
    {"code": "awaiting_screening", "label": "Awaiting screening",
     "model_flagged": False,
     "definition": "Stored but not yet screened for relevance. No judgment "
                   "of any kind has been made about this record."},
    {"code": "analysis_incomplete", "label": "Analysis incomplete",
     "model_flagged": False,
     "definition": "Passed relevance screening, but analysis did not "
                   "complete. The original record remains stored; no "
                   "completed analysis is claimed."},
]

STATE_LABELS = {s["code"]: s["label"] for s in PROCESSING_STATES}
STATE_ORDER = [s["code"] for s in PROCESSING_STATES]

#: Single source of truth for the state derivation. Used identically by the
#: query layer and by the tests, so the two cannot drift apart.
STATE_CASE_SQL = (
    "CASE WHEN a.passed_relevance IS NULL      THEN 'awaiting_screening' "
    "     WHEN a.passed_relevance = 0          THEN 'not_selected' "
    "     WHEN a.analyzed_at IS NOT NULL       THEN 'analyzed' "
    "     ELSE 'analysis_incomplete' END"
)


class SnapshotMismatch(SystemExit):
    """The corpus does not match the declared snapshot.

    Raised when any governed value disagrees with the database: the record
    count, or the logical fingerprint over the corpus content. Also raised when
    a snapshot declaration is itself incomplete — an omitted `logical_sha256`
    is a malformed declaration, not a request to skip the content check.
    """


def assert_snapshot(corpus, snapshot: dict) -> None:
    """Fail loudly when the corpus is not the declared snapshot.

    Two independent checks. The count catches records added or removed; the
    logical fingerprint catches everything the count cannot — a record replaced
    one-for-one, a corrected body, a re-analysis, a changed source name.
    Silently publishing a changed corpus under an unchanged snapshot date is
    the failure this exists to prevent, so it raises rather than warns.
    """
    actual_records = len(corpus)
    expected = snapshot["expected_records"]
    if actual_records != expected:
        raise SnapshotMismatch(
            "snapshot mismatch: declared '%s' expects %d records, database "
            "holds %d.\nThe build is refusing to publish a changed corpus "
            "under an unchanged snapshot date. Advance the declared snapshot "
            "deliberately — date, record count AND logical fingerprint — and "
            "record it in the changelog."
            % (snapshot["date"], expected, actual_records))

    # Opting out of the content check must be a deliberate, visible act. A
    # missing key is a malformed declaration: `.get()` would have turned every
    # typo and every forgotten field into a silent bypass of the one guard that
    # catches a changed corpus at a stable count.
    if "logical_sha256" not in snapshot:
        raise SnapshotMismatch(
            "snapshot declaration '%s' omits 'logical_sha256'.\nThe key is "
            "required. Declare the 64-character digest, or set it explicitly "
            "to None in a controlled test fixture. An omitted key is a "
            "malformed declaration, not an opt-out."
            % snapshot.get("date", "<no date>"))

    declared = snapshot["logical_sha256"]
    if declared is None:
        return
    actual = corpus_fingerprint(corpus)
    if actual != declared:
        raise SnapshotMismatch(
            "snapshot mismatch: declared '%s' expects logical fingerprint\n"
            "  %s\nbut the corpus hashes to\n  %s\n"
            "The record count is unchanged, so content changed underneath a "
            "stable count — a replaced record, a corrected body, a "
            "re-analysis, or changed source metadata. Advance the declared "
            "snapshot deliberately and record it in the changelog."
            % (snapshot["date"], declared, actual))


# ── Data (read-only, from a scratch copy) ─────────────────────────────────────

def load_corpus(db_path: Path) -> dict:
    """Everything the prototype renders. One pass, read-only, no mutation."""
    with _read_only(str(db_path)) as con:
        con.row_factory = _dict_row

        sources = con.execute(
            "SELECT s.slug, s.display_name, s.language, s.language_tag, "
            "       s.desk_id, s.institution_id, s.authority_tier, "
            "       s.source_type, s.base_url, s.enabled, "
            "       i.display_name AS institution, i.name_original "
            "  FROM sources s "
            "  LEFT JOIN institutions i ON i.institution_id = s.institution_id "
            " ORDER BY s.id"
        ).fetchall()

        counts = {r["source_slug"]: r["n"] for r in con.execute(
            "SELECT sr.slug AS source_slug, COUNT(a.id) AS n "
            "  FROM sources sr LEFT JOIN articles a ON a.source_id = sr.id "
            " GROUP BY sr.slug").fetchall()}

        last_pub = {r["source_slug"]: r["d"] for r in con.execute(
            "SELECT sr.slug AS source_slug, MAX(a.published_date) AS d "
            "  FROM sources sr LEFT JOIN articles a ON a.source_id = sr.id "
            " GROUP BY sr.slug").fetchall()}

        latest_run = con.execute(
            "SELECT id, started_at, completed_at, status, articles_scraped, "
            "       articles_new, articles_analyzed "
            "  FROM scrape_runs ORDER BY id DESC LIMIT 1").fetchone()

        run_results = con.execute(
            "SELECT source_slug, status, is_failure, references_discovered, "
            "       fetched, extracted, duplicates, new_documents, "
            "       relevance_rejected, error_detail "
            "  FROM source_run_results WHERE scrape_run_id = ? "
            " ORDER BY source_slug", (latest_run["id"],)).fetchall()

        # Desks that actually collected in this run, derived from the persisted
        # source -> desk mapping rather than from the DESKS presentation
        # constant. `not_implemented` / `skipped_disabled` never counted: a
        # configured source that did not run is not a collecting desk.
        collecting_desks = [r["desk_id"] for r in con.execute(
            "SELECT DISTINCT s.desk_id AS desk_id "
            "  FROM source_run_results r "
            "  JOIN sources s ON s.slug = r.source_slug "
            " WHERE r.scrape_run_id = ? "
            "   AND r.status NOT IN ('not_implemented','skipped_disabled') "
            "   AND s.desk_id IS NOT NULL "
            " ORDER BY s.desk_id", (latest_run["id"],)).fetchall()]

        # Executed sources whose desk cannot be established from stored data.
        # If this is non-zero the desk count is withheld rather than guessed.
        unmapped_executed = con.execute(
            "SELECT COUNT(*) AS n FROM source_run_results r "
            "  LEFT JOIN sources s ON s.slug = r.source_slug "
            " WHERE r.scrape_run_id = ? "
            "   AND r.status NOT IN ('not_implemented','skipped_disabled') "
            "   AND (s.slug IS NULL OR s.desk_id IS NULL)",
            (latest_run["id"],)).fetchone()["n"]

        institutions = con.execute(
            "SELECT COUNT(DISTINCT institution_id) AS n FROM sources "
            " WHERE institution_id IS NOT NULL").fetchone()["n"]

        totals = con.execute(
            "SELECT (SELECT COUNT(*) FROM articles) AS articles, "
            "       (SELECT COUNT(*) FROM articles WHERE analyzed_at IS NOT NULL) AS analyzed, "
            "       (SELECT COUNT(*) FROM scrape_runs) AS runs, "
            "       (SELECT MIN(published_date) FROM articles) AS first_date, "
            "       (SELECT MAX(published_date) FROM articles) AS last_date"
        ).fetchone()

        # Recent analyzed articles for the archive surface. Bounded: the
        # prototype is a design artifact, not the production archive.
        recent = con.execute(
            "SELECT a.id, a.url, a.title_original, a.title_english, "
            "       a.published_date, a.summary_english, a.analyzed_at, "
            "       a.model_id, a.prompt_version, a.is_significant, "
            "       a.content_hash, a.scraped_at, a.scrape_run_id, "
            "       s.slug AS source_slug, s.display_name AS source_name, "
            "       s.language_tag, i.display_name AS institution "
            "  FROM articles a "
            "  JOIN sources s ON s.id = a.source_id "
            "  LEFT JOIN institutions i ON i.institution_id = s.institution_id "
            " WHERE a.analyzed_at IS NOT NULL "
            " ORDER BY a.published_date DESC, a.id DESC LIMIT 60").fetchall()

        # Collection continuity: which calendar days have a run. The published
        # gap record, not a marketing number.
        #
        # NOTE (2026-08-16 trace): `started_at` is UTC — `start_scrape_run()`
        # inserts only `status`, so the value is the schema default
        # `datetime('now')`. Publication dates are Beijing-stated. These are
        # DIFFERENT CALENDARS and this list is never used as a denominator for
        # publication-date buckets.
        run_days = [r["d"] for r in con.execute(
            "SELECT DISTINCT substr(started_at,1,10) AS d FROM scrape_runs "
            " ORDER BY d").fetchall()]

        # ── Full corpus ──────────────────────────────────────────────────────
        # Every stored record, not only the analyzed ones. Ordering is
        # deterministic and total: publication date descending, then record id
        # descending as a stable tiebreak. Ids are read as stored — the six
        # gaps between COUNT(*) and MAX(id) are preserved by never enumerating
        # a range and never synthesising a missing row.
        corpus = con.execute(
            "SELECT a.id, a.url, a.title_original, a.title_english, "
            "       a.published_date, a.summary_english, a.analyzed_at, "
            "       a.model_id, a.prompt_version, a.is_significant, "
            "       a.content_hash, a.scraped_at, a.scrape_run_id, "
            "       a.text_original, a.passed_relevance, "
            "       s.slug AS source_slug, s.display_name AS source_name, "
            "       s.language_tag, s.institution_id, "
            "       i.display_name AS institution, "
            "       " + STATE_CASE_SQL + " AS state "
            "  FROM articles a "
            "  JOIN sources s ON s.id = a.source_id "
            "  LEFT JOIN institutions i ON i.institution_id = s.institution_id "
            " ORDER BY a.published_date DESC, a.id DESC").fetchall()

    for rec in corpus:
        rec["state_label"] = STATE_LABELS[rec["state"]]
        # The machine flag is surfaced ONLY where it was actually computed.
        # Everywhere else it is None — not False, which would read as
        # "assessed and not flagged".
        rec["model_flagged"] = (bool(rec["is_significant"])
                                if rec["state"] == "analyzed" else None)
        rec["has_text"] = bool((rec["text_original"] or "").strip())
        rec["record_path"] = "record/%d.html" % rec["id"]

    for s in sources:
        s["article_count"] = counts.get(s["slug"], 0)
        s["last_published"] = last_pub.get(s["slug"])

    return {
        "sources": sources, "latest_run": latest_run,
        "run_results": run_results, "totals": totals,
        "recent": recent, "run_days": run_days,
        "collecting_desks": collecting_desks,
        "unmapped_executed": unmapped_executed,
        "institutions": institutions,
        "corpus": corpus,
        "state_counts": corpus_state_counts(corpus),
        "facets": corpus_facets(corpus),
        "weeks": corpus_weeks(corpus, run_days),
    }


def corpus_state_counts(corpus: list) -> list:
    """The four processing states with counts, in reader-facing order.

    Every state is reported even at zero, so a state never silently vanishes
    from the vocabulary because this snapshot happens not to contain one.
    """
    seen = Counter(r["state"] for r in corpus)
    return [{"code": s["code"], "label": s["label"],
             "definition": s["definition"], "count": seen.get(s["code"], 0)}
            for s in PROCESSING_STATES]


def corpus_facets(corpus: list) -> dict:
    """Facet values that actually have records. Nothing else is offered.

    A facet value with zero records is an invitation to an empty result and,
    worse, implies coverage that does not exist — `xinhua_mil` is configured
    and holds nothing, so it must not appear here.

    Source and institution stay SEPARATE dimensions. They are not
    interchangeable: two sources share `cn_cmc_political_work`, so selecting
    that institution returns records from more than one outlet.
    """
    def tally(key_field, label_field):
        pairs = {}
        for r in corpus:
            key = r.get(key_field)
            if key is None:
                continue
            label = r.get(label_field) or key
            entry = pairs.setdefault(key, {"key": key, "label": label,
                                           "count": 0})
            entry["count"] += 1
        return sorted(pairs.values(), key=lambda e: (-e["count"], e["key"]))

    return {
        "source": tally("source_slug", "source_name"),
        "institution": tally("institution_id", "institution"),
        "language": tally("language_tag", "language_tag"),
        "state": [s for s in corpus_state_counts(corpus) if s["count"]],
    }


#: Reader-facing names for the stored BCP 47 tags. ONE controlled mapping: the
#: label is resolved here, shipped once per language in the index dictionary,
#: and never re-derived in the browser or repeated per record. Stored and index
#: CODES are unchanged — `zh-Hans` and `en` remain the filter values — because
#: the code is the datum and the label is presentation.
#:
#: Record-page provenance deliberately keeps the raw tag alongside its
#: methodological note; that surface is about precision, this one is about
#: reading.
LANGUAGE_LABELS = {
    "zh-Hans": "Simplified Chinese",
    "en": "English",
}


def language_label(tag):
    """Editorial name for a stored language tag.

    An unmapped tag falls back to the tag itself rather than to a guess — a
    wrong language name is worse than a technical one, and a test asserts every
    tag the corpus actually holds is mapped.
    """
    return LANGUAGE_LABELS.get(tag, tag)


#: Fields the compact index may never carry. The index exists to drive search,
#: result rows, routing and the approved facets — nothing else. Stored bodies,
#: model output, URLs, hashes and timestamps belong on the record page, where
#: they are labelled; shipping them to every reader as a bulk download would
#: turn a browse aid into an undeclared corpus export.
INDEX_FORBIDDEN_FIELDS = (
    "text_original", "summary_english", "url", "content_hash", "model_id",
    "prompt_version", "scraped_at", "analyzed_at", "scrape_run_id",
    "is_significant", "passed_relevance", "relevance_score",
)


def corpus_index(corpus, sources, snapshot: dict) -> dict:
    """The compact external index behind the browser.

    Two economies, both structural rather than lossy:

    * Records are positional arrays, so 3,250 rows do not repeat six key names.
    * Institution and language are attributes OF THE SOURCE, so a record stores
      one source index and the reader resolves the rest. Repeating an
      institution label on every record would be duplicating a join.

    No title is truncated and no methodological field is dropped to hit a size
    target. What is absent is absent by rule, not by squeeze.
    """
    src_order = [s["slug"] for s in sources
                 if any(r["source_slug"] == s["slug"] for r in corpus)]
    src_pos = {slug: i for i, slug in enumerate(src_order)}
    by_slug = {s["slug"]: s for s in sources}

    inst_order, lang_order = [], []
    for slug in src_order:
        source = by_slug[slug]
        if source.get("institution_id") and source["institution_id"] not in inst_order:
            inst_order.append(source["institution_id"])
        if source.get("language_tag") and source["language_tag"] not in lang_order:
            lang_order.append(source["language_tag"])
    inst_pos = {code: i for i, code in enumerate(inst_order)}
    lang_pos = {code: i for i, code in enumerate(lang_order)}
    state_pos = {code: i for i, code in enumerate(STATE_ORDER)}

    counts = {"source": Counter(), "institution": Counter(),
              "language": Counter(), "state": Counter()}
    rows = []
    for record in corpus:
        source = by_slug[record["source_slug"]]
        counts["source"][record["source_slug"]] += 1
        counts["state"][record["state"]] += 1
        if source.get("institution_id"):
            counts["institution"][source["institution_id"]] += 1
        if source.get("language_tag"):
            counts["language"][source["language_tag"]] += 1
        rows.append([
            record["id"],
            record["published_date"],
            src_pos[record["source_slug"]],
            state_pos[record["state"]],
            record["title_english"] or "",
            record["title_original"] or "",
        ])

    inst_label = {s["institution_id"]: s.get("institution")
                  for s in sources if s.get("institution_id")}
    return {
        # The PUBLIC snapshot facts only. The logical fingerprint is an
        # internal build-integrity guard and is never shipped to a reader.
        "snapshot": {"date": snapshot["date"], "records": len(corpus)},
        "fields": ["id", "date", "source", "state", "title_en", "title_orig"],
        "sources": [
            {"code": slug,
             "label": by_slug[slug]["display_name"],
             "institution": inst_pos.get(by_slug[slug].get("institution_id")),
             "language": lang_pos.get(by_slug[slug].get("language_tag")),
             "count": counts["source"][slug]}
            for slug in src_order],
        "institutions": [
            {"code": code, "label": inst_label.get(code) or code,
             "count": counts["institution"][code]} for code in inst_order],
        "languages": [
            {"code": code, "label": language_label(code),
             "count": counts["language"][code]} for code in lang_order],
        "states": [
            {"code": code, "label": STATE_LABELS[code],
             "count": counts["state"][code]}
            for code in STATE_ORDER if counts["state"][code]],
        "records": rows,
    }


def week_start(iso_date: str) -> str:
    """Monday of the publication week containing `iso_date`."""
    from datetime import date, timedelta
    y, m, d = (int(p) for p in iso_date.split("-"))
    day = date(y, m, d)
    return (day - timedelta(days=day.weekday())).isoformat()


#: The one governed collection outage (PROJECT_STATE.md). Publication weeks
#: overlapping it may carry a named annotation. Nothing else may.
OUTAGE_START, OUTAGE_END = "2026-07-17", "2026-07-24"

#: Shard budget, DESIGN_SYSTEM §8's "≤ 120 KB per page" read strictly as
#: 120,000 bytes rather than 120 KiB. The stricter reading is deliberate: the
#: largest week measures 121,779 bytes unpaginated, which passes on the binary
#: reading and fails on the decimal one, and a budget that depends on which
#: kilobyte you mean is not a budget. Shards carry external CSS, never inlined,
#: so this measures markup alone.
#:
#: A week exceeding this is paginated deterministically — never truncated.
SHARD_BUDGET_BYTES = 120_000

#: Usability ceiling, independent of bytes. The byte budget alone let a 266-record
#: week render 59,196px tall on a 320px viewport — inside the budget and still
#: unusable. Both limits must hold.
SHARD_MAX_RECORDS = 50


def week_annotation(week: dict, first_start: str, last_start: str):
    """The only two annotations a week may carry.

    Ruled 2026-08-16 §6a: no generic "Partial" label, and run-date counts are
    never a coverage denominator. A week is annotated only when the reason is
    independently governed — it is the edge of the snapshot, or it overlaps the
    recorded outage.
    """
    if week["start"] <= OUTAGE_END and week["end"] >= OUTAGE_START:
        return ("Known collection interruption",
                "This week overlaps the recorded collection interruption of "
                "17–24 July 2026. Records for those dates are absent from this "
                "snapshot; they were not collected, and their absence is not "
                "evidence that nothing was published.")
    if week["start"] in (first_start, last_start):
        return ("Snapshot boundary",
                "This week sits at the edge of the snapshot, so it covers only "
                "part of its seven days.")
    return None


def corpus_weeks(corpus: list, run_days: list) -> list:
    """Monday-starting publication weeks, newest first.

    `run_dates` counts UTC calendar dates carrying at least one recorded
    pipeline run whose date falls inside the week. Ruled 2026-08-16 §6a: this
    is OPERATIONAL CONTEXT, never a coverage denominator. Run records preserve
    no target publication date and no historical source-level outcome, so a run
    date proves that the pipeline ran — not that any source was observed.
    """
    from datetime import date, timedelta
    buckets = defaultdict(list)
    for r in corpus:
        buckets[week_start(r["published_date"])].append(r)

    run_day_set = set(run_days)
    weeks = []
    for start in sorted(buckets, reverse=True):
        y, m, d = (int(p) for p in start.split("-"))
        first = date(y, m, d)
        days = [(first + timedelta(days=i)).isoformat() for i in range(7)]
        # Records arrive already ordered (published_date DESC, id DESC) and
        # bucketing preserves that order, so within-week ordering is
        # deterministic without a second sort.
        weeks.append({
            "start": start,
            "end": days[-1],
            "records": buckets[start],
            "count": len(buckets[start]),
            "run_dates": sum(1 for day in days if day in run_day_set),
            "path": "week-%s.html" % start,
        })

    if weeks:
        first_start, last_start = weeks[-1]["start"], weeks[0]["start"]
        for week in weeks:
            annotation = week_annotation(week, first_start, last_start)
            week["annotation"] = annotation[0] if annotation else None
            week["annotation_note"] = annotation[1] if annotation else None
    return weeks


def _dict_row(cursor, row):
    return {d[0]: row[i] for i, d in enumerate(cursor.description)}


#: The live site. Editions are linked, never copied: the sidecars under
#: `output/the-pla-watch/posts/` are the canonical edition record, and a second
#: rendered copy inside a prototype would be a second source of truth that
#: silently drifts.
LIVE_BASE = "https://chinamilwatch.org"


def load_editions(repo_root: Path):
    """
    The real PLA Watch editions, read from their canonical sidecars.

    Only fields the sidecar actually carries are used — nothing is synthesised,
    and an edition missing a field renders without it rather than acquiring an
    invented one.
    """
    posts = repo_root / "output" / "the-pla-watch" / "posts"
    if not posts.is_dir():
        return []
    editions = []
    for sidecar in sorted(posts.glob("*.json"), reverse=True):
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        slug = sidecar.stem
        rendered = posts / (slug + ".html")
        editions.append({
            "slug": slug,
            "date": data.get("date") or slug,
            "issue": data.get("issue_number"),
            "title": data.get("title") or "",
            "dek": data.get("dek") or "",
            "articles": data.get("n_articles"),
            "flagged": data.get("n_significant"),
            "label": data.get("edition_label") or "",
            "url": "%s/the-pla-watch/posts/%s.html" % (LIVE_BASE, slug),
            "rendered_locally": rendered.is_file(),
        })
    return editions


def run_status_summary(latest_run, run_results, collecting_desks,
                       unmapped_executed=0):
    """
    The four states the status strip must keep apart (revision brief §3):
    collectors executed, execution failures, unimplemented adapters, and desks
    that actually collected.

    PROVENANCE — the values do NOT all come from one place, and the earlier
    docstring was wrong to imply they did:

      * run id and run date        -> `scrape_runs`
      * executed / failed /
        unimplemented / disabled   -> `source_run_results` for that run
      * collecting desk count      -> `sources.desk_id` joined to the executed
                                      rows of that run. It is a persisted
                                      relationship, NOT the DESKS presentation
                                      constant, and NOT a count of sources.

    No configured-source total is exposed as a collector denominator. Four
    working collectors executed and a fifth configured source has no adapter;
    "4 of 5 collectors" would assert five collectors exist, which is false in
    this project's own vocabulary (`not_implemented` = "no working collector").

    Returns None when there is no run, so the strip renders nothing rather than
    a zero that would read as "all clear". `desks` is None — and omitted by the
    template — when any executed source cannot be mapped to a desk from stored
    data, because a partial count would understate coverage silently.
    """
    if not latest_run or not run_results:
        return None

    not_run = ("not_implemented", "skipped_disabled")
    executed = [r for r in run_results if r["status"] not in not_run]
    failures = [r for r in executed if r["is_failure"]]
    unimplemented = [r for r in run_results if r["status"] == "not_implemented"]
    disabled = [r for r in run_results if r["status"] == "skipped_disabled"]

    return {
        "run_id": latest_run["id"],
        # The run's own date, not a wall clock — determinism, and the corpus
        # date is the honest thing to show anyway.
        "run_date": (latest_run["started_at"] or "")[:10] or None,
        "executed": len(executed),
        "failed": len(failures),
        "unimplemented": len(unimplemented),
        "disabled": len(disabled),
        "desks": None if unmapped_executed else len(collecting_desks),
        "desks_unmapped": unmapped_executed,
    }


def collection_gaps(run_days, min_gap=2):
    """
    Consecutive calendar days with no scrape run.

    Published rather than smoothed over. The 2026-07-17→24 outage is the single
    most credibility-relevant fact about this corpus and it has never appeared
    on a public surface (PROJECT_STATE.md, Known issues).
    """
    from datetime import date, timedelta
    days = sorted({d for d in run_days if d})
    gaps = []
    for a, b in zip(days, days[1:]):
        try:
            da = date.fromisoformat(a)
            db = date.fromisoformat(b)
        except ValueError:
            continue
        missing = (db - da).days - 1
        if missing >= min_gap:
            gaps.append({
                "from": (da + timedelta(days=1)).isoformat(),
                "to": (db - timedelta(days=1)).isoformat(),
                "days": missing,
            })
    return gaps


#: Corpus Guide data dictionary. Reader-facing labels are primary; `stored` is
#: the database column, shown in monospace as a secondary aid. Every entry maps
#: to a real column, and a test proves it.
#:
#: `absent` prose carries counts that are INJECTED from a direct query
#: (`corpus_guide_stats`), never typed in. A field whose prose claims it is
#: never absent is checked against the corpus, so the claim cannot rot.
#:
#: Machine assessment deliberately shows NO stored column name. The column is
#: called `is_significant`, and "significant" is the one word the public label
#: may never use (DECISION_LOG 2026-07-10); printing the raw name on a reader
#: surface would reintroduce it as prose.
DICTIONARY_FIELDS = [
    {
        "label": "Record ID", "stored": "id", "origin": "Stored",
        "check": "id",
        "meaning": "The identifier of a stored record inside this snapshot.",
        "absent": "Never absent.",
        "limitation": "A locator inside this snapshot, not a permanent public "
                      "identifier. Identifiers are not contiguous — the "
                      "highest is {max_id} across {total} records — so a range "
                      "of identifiers never describes the corpus.",
    },
    {
        "label": "Source-stated publication date", "stored": "published_date",
        "origin": "Stored", "check": "published_date",
        "meaning": "The publication date as the source itself stated it.",
        "absent": "Never absent.",
        "limitation": "Source-stated and collection-bounded. It records what "
                      "the source said, and it can only fall inside the window "
                      "collection actually reached. Nothing verifies it "
                      "against another authority.",
    },
    {
        "label": "Source outlet", "stored": "sources.display_name",
        "origin": "Stored", "check": "source_name",
        "meaning": "The outlet that published the item, taken from the "
                   "configured source that collected it.",
        "absent": "Never absent.",
        "limitation": "De-duplication across sources is first-writer-wins, so "
                      "an item carried by several outlets is held once, under "
                      "whichever source stored it first. Outlet totals are "
                      "counts of stored records, not of publication volume.",
    },
    {
        "label": "Publishing institution", "stored": "institutions.display_name",
        "origin": "Stored", "check": "institution",
        "meaning": "The institution behind the outlet.",
        "absent": "Never absent in this snapshot. A source configured without "
                  "an institution would leave it empty.",
        "limitation": "The corpus is heavily concentrated: {top_institution} "
                      "accounts for {top_institution_count} of {total} records "
                      "({top_institution_pct}%). Institution totals describe "
                      "this collection, not the wider field.",
    },
    {
        "label": "Original language", "stored": "sources.language_tag",
        "origin": "Stored", "check": "language_tag",
        "meaning": "The language of the original item. It is an attribute of "
                   "the source, inherited by every record collected from it.",
        "absent": "Never absent.",
        "limitation": "Inherited from the configured source and never detected "
                      "on the record itself. A source that published in a "
                      "second language would still report its configured one.",
    },
    {
        "label": "Original title", "stored": "title_original",
        "origin": "Stored", "check": "title_original",
        "meaning": "The item's title as published, stored as captured.",
        "absent": "Never absent.",
        "limitation": "Held as captured and never edited, translated in place, "
                      "or normalized. It is the authoritative title for this "
                      "record.",
    },
    {
        "label": "Stored source text", "stored": "text_original",
        "origin": "Stored", "check": "text_original",
        "meaning": "Body text captured from the source page.",
        "absent": "Empty in {empty_text} records.",
        "limitation": "Extraction can omit material or pull in unrelated page "
                      "furniture, so no capture is a facsimile. An empty "
                      "capture is a stored defect, not evidence that the page "
                      "carried nothing.",
    },
    {
        "label": "Machine-translated English title", "stored": "title_english",
        "origin": "Stored", "check": "title_english",
        "meaning": "A model's English rendering of the original title.",
        "absent": "Absent for {no_english} records.",
        "limitation": "Unreviewed machine output. No human has checked it "
                      "against the original title.",
    },
    {
        "label": "Machine summary", "stored": "summary_english",
        "origin": "Stored", "check": "summary_english",
        "meaning": "A model's summary of the stored source text.",
        "absent": "Absent for {no_summary} records.",
        "limitation": "Unreviewed machine output, and a reading of what was "
                      "published rather than a verification of it.",
    },
    {
        "label": "Processing state",
        "stored": "passed_relevance, analyzed_at", "origin": "Derived",
        "check": None,
        "meaning": "How far a record traveled through screening and analysis. "
                   "Every record is in exactly one of the four states above.",
        "absent": "Never absent; it is computed for every record.",
        "limitation": "Processing has four states, not two. Reading the corpus "
                      "as analyzed-or-not merges records that were screened "
                      "and set aside with records never screened at all.",
    },
    {
        "label": "Machine assessment", "stored": None, "origin": "Stored",
        "check": None,
        "meaning": "A software triage cue marking a record for closer review.",
        "absent": "Shown only for records in the Analyzed state.",
        "limitation": "Meaningful only inside the Analyzed state. The stored "
                      "column defaults to a negative value, so a negative "
                      "reading cannot tell an assessed record from one that "
                      "was never assessed — and must never be read as evidence "
                      "that an unscreened record was assessed and cleared.",
    },
    {
        "label": "Analysis model", "stored": "model_id", "origin": "Stored",
        "check": "model_id",
        "meaning": "The model that produced the English title and summary.",
        "absent": "Absent for {no_model} records.",
        "limitation": "Names the model only. It does not record the model's "
                      "configuration or how it behaved on this record.",
    },
    {
        "label": "Prompt version", "stored": "prompt_version",
        "origin": "Stored", "check": "prompt_version",
        "meaning": "The analysis prompt in force when the record was analyzed.",
        "absent": "Absent for {prompt_version_missing} of the {analyzed} "
                  "analyzed records.",
        "limitation": "Where it is absent, the exact prompt behind that "
                      "record's English output cannot be established "
                      "afterward.",
    },
    {
        "label": "Capture fingerprint", "stored": "content_hash",
        "origin": "Stored", "check": "content_hash",
        "meaning": "A hash taken once, at capture, over the stored original "
                   "title and text.",
        "absent": "Never absent.",
        "limitation": "A capture-time fingerprint that is never recomputed. It "
                      "records what arrived; it is not a continuing integrity "
                      "guarantee, and a later correction to the stored text "
                      "would leave it stale.",
    },
    {
        "label": "Collection run", "stored": "scrape_run_id",
        "origin": "Stored", "check": "scrape_run_id",
        "meaning": "The pipeline run that stored the record.",
        "absent": "Never absent.",
        "limitation": "Run history preserves no target publication date and no "
                      "historical source-level outcome, so a run identifier "
                      "does not establish which sources were reached or which "
                      "dates were sought.",
    },
    {
        "label": "Collection timestamp", "stored": "scraped_at",
        "origin": "Stored", "check": "scraped_at",
        "meaning": "When the pipeline stored the record.",
        "absent": "Never absent.",
        "limitation": "A pipeline collection timestamp in UTC — not a reader "
                      "access date and not a publication time. Publication "
                      "dates are stated on the source's own calendar, so the "
                      "two do not align.",
    },
    {
        "label": "Original URL", "stored": "url", "origin": "Stored",
        "check": "url",
        "meaning": "The address the item was collected from.",
        "absent": "Never absent.",
        "limitation": "Recorded as collected. Whether it still resolves is not "
                      "checked when this page is built.",
    },
]


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def english_output_sets(corpus: list) -> dict:
    """The three machine-output fields, derived separately and then compared.

    Reporting one number for all three is only honest when the three are the
    same SET — not merely the same size. Three fields can each be empty on 2,140
    records while disagreeing about which 2,140, and a single count would hide
    that completely. Each is derived on its own here; `identical` is what earns
    the combined sentence, and when it is false the guide states three separate
    counts instead.

    The fourth set is the records outside the Analyzed state, because the claim
    the guide actually wants to make is that machine output tracks the
    processing state rather than appearing at random.
    """
    empty_title = {r["id"] for r in corpus if _blank(r.get("title_english"))}
    empty_summary = {r["id"] for r in corpus
                     if _blank(r.get("summary_english"))}
    empty_model = {r["id"] for r in corpus if _blank(r.get("model_id"))}
    non_analyzed = {r["id"] for r in corpus if r["state"] != "analyzed"}
    return {
        "empty_title": empty_title,
        "empty_summary": empty_summary,
        "empty_model": empty_model,
        "non_analyzed": non_analyzed,
        "identical": (empty_title == empty_summary == empty_model
                      == non_analyzed),
    }


def corpus_guide_stats(corpus: list, run_days: list) -> dict:
    """Every number the Corpus Guide and its changelog display.

    Derived here from the loaded corpus so that no figure is ever typed into
    prose. The changelog is editorial in its wording and arithmetical in its
    numbers: the sentences are written by hand, the counts are not.
    """
    states = Counter(r["state"] for r in corpus)
    analyzed = [r for r in corpus if r["state"] == "analyzed"]
    institutions = Counter(r["institution"] for r in corpus
                           if r.get("institution"))
    top_institution, top_count = (institutions.most_common(1)[0]
                                  if institutions else ("—", 0))
    gaps = collection_gaps(run_days)
    total = len(corpus)
    english = english_output_sets(corpus)
    # Records carrying a source-stated publication date inside the recorded
    # interruption. The changelog claims material from that window is absent;
    # this is the number that claim stands or falls on, so it is measured
    # rather than assumed.
    outage_records = sum(1 for r in corpus
                         if OUTAGE_START <= r["published_date"] <= OUTAGE_END)
    return {
        "total": total,
        "max_id": max((r["id"] for r in corpus), default=0),
        "awaiting_screening": states.get("awaiting_screening", 0),
        "analysis_incomplete": states.get("analysis_incomplete", 0),
        "not_selected": states.get("not_selected", 0),
        "analyzed": len(analyzed),
        # Records that have not completed analysis and are not settled as
        # out of scope — the backlog, stated as its two parts as well.
        "backlog": (states.get("awaiting_screening", 0)
                    + states.get("analysis_incomplete", 0)),
        # Three machine-output fields, each measured on its own. They are not
        # collapsed into one figure unless `english_sets_identical` proves the
        # three sets hold the same record ids.
        "no_english": len(english["empty_title"]),
        "no_summary": len(english["empty_summary"]),
        "no_model": len(english["empty_model"]),
        "non_analyzed": len(english["non_analyzed"]),
        "english_sets_identical": english["identical"],
        "outage_records": outage_records,
        "empty_text": sum(1 for r in corpus if _blank(r.get("text_original"))),
        "prompt_version_missing": sum(1 for r in analyzed
                                      if _blank(r.get("prompt_version"))),
        "top_institution": top_institution,
        "top_institution_count": top_count,
        "top_institution_pct": round(100.0 * top_count / total, 1) if total
                               else 0.0,
        "institutions": len(institutions),
        "outlets": len({r["source_name"] for r in corpus}),
        # The one governed interruption, read from the run record rather than
        # restated. `None` if it ever stops being derivable, so the changelog
        # cannot keep asserting an outage the data no longer shows.
        "outage": gaps[0] if gaps else None,
        "first_date": min((r["published_date"] for r in corpus), default=None),
        "last_date": max((r["published_date"] for r in corpus), default=None),
    }


def _display_stats(stats: dict) -> dict:
    """`stats` with integers rendered as reader-facing figures.

    Prose needs "3,250"; tests need 3250. Keeping the raw dict authoritative and
    formatting only at the point of substitution means a test can recompute
    every displayed number from the corpus without parsing separators back out.
    Identifiers are not counts, so `max_id` keeps its bare form.
    """
    out = {}
    for key, value in stats.items():
        if isinstance(value, int) and key != "max_id":
            out[key] = "{:,}".format(value)
        else:
            out[key] = value
    return out


def dictionary_rows(stats: dict) -> list:
    """The dictionary with its counts filled in from the stats."""
    display = _display_stats(stats)
    rows = []
    for field in DICTIONARY_FIELDS:
        rows.append(dict(field,
                         absent=field["absent"].format(**display),
                         limitation=field["limitation"].format(**display)))
    return rows


#: The corpus changelog. MANUALLY EDITORIAL: written by hand, entry by entry.
#: It is not generated from git history and it is not collection-health
#: history — Coverage carries the operational result vocabulary and the current
#: run evidence, and this does not duplicate or summarize it.
#:
#: Limitations lead. Growth is subordinate, because a first entry that opened
#: with "3,250 records" would advertise size before disclosing what is missing
#: from it. Counts are injected from `corpus_guide_stats`; the sentences are
#: not generated.
def changelog_entries(stats: dict) -> list:
    identical = stats["english_sets_identical"]
    outage_records = stats["outage_records"]
    stats = _display_stats(stats)
    outage = stats["outage"]
    if not outage:
        interruption = ("No collection interruption is derivable from the "
                        "stored run record.")
    else:
        window = {"from": outage["from"], "to": outage["to"]}
        # The absence claim is measured, not assumed. If the window ever holds
        # records, saying they are absent would be false, so the sentence
        # reports what is actually there instead.
        interruption = (
            "No pipeline run is recorded on the UTC dates {from} through {to}, "
            "and no record in this snapshot carries a source-stated "
            "publication date inside that window.".format(**window)
            if outage_records == 0 else
            "No pipeline run is recorded on the UTC dates {from} through {to}. "
            "This snapshot nonetheless holds {n} records with source-stated "
            "publication dates inside that window, collected outside it."
            .format(n="{:,}".format(outage_records), **window))

    # One number covers three fields only when the three hold the same record
    # ids. Otherwise each is stated separately rather than averaged into a
    # claim none of them supports.
    if identical:
        english = ("{no_english} of {total} records hold no machine-translated "
                   "title. The same records — the same identifiers, not merely "
                   "the same total — also hold no machine summary and no "
                   "analysis-model record, and they are exactly the records "
                   "outside the Analyzed state. English coverage is a property "
                   "of the analyzed subset, not of the corpus.".format(**stats))
    else:
        english = ("Of {total} records, {no_english} hold no "
                   "machine-translated title, {no_summary} hold no machine "
                   "summary, and {no_model} hold no analysis-model record. "
                   "These are not the same records, so no single figure "
                   "describes English coverage.".format(**stats))
    return [{
        "id": "entry-2026-08-19",
        "title": "Initial documented prototype snapshot",
        "date": stats["last_date"],
        "summary": "The first snapshot of this corpus to be documented for "
                   "readers. What follows begins with what is missing from it.",
        # Not "items": Jinja resolves `entry.items` to the dict method first.
        "points": [
            ("A recorded collection interruption", interruption),
            ("The interruption cannot be quantified",
             "What those dates would have held is not recoverable from stored "
             "data. Run records preserve no target publication date and no "
             "source-level outcome, so the volume missed can be neither "
             "reconstructed nor estimated. It is not counted, and its absence "
             "is not evidence that nothing was published."),
            ("A processing backlog",
             "{backlog} records have not completed analysis and are not "
             "settled as out of scope: {awaiting_screening} are awaiting "
             "screening and {analysis_incomplete} passed screening without a "
             "completed analysis.".format(**stats)),
            ("Most records carry no English rendering", english),
            ("Some captures stored no source text",
             "{empty_text} records hold an empty body capture. The original "
             "URL remains recorded for each; the empty value is a stored "
             "capture defect, not evidence that the page was "
             "blank.".format(**stats)),
            ("Repeats across outlets are held once",
             "De-duplication across sources is first-writer-wins. An item "
             "carried by more than one outlet is stored under whichever source "
             "reached it first, so per-outlet totals count stored records "
             "rather than how often something was published."),
            ("Snapshot and size",
             "This snapshot is dated {last_date} and holds {total} records "
             "from {outlets} outlets and {institutions} institutions, with "
             "source-stated publication dates from {first_date} "
             "onward.".format(**stats)),
        ],
    }]


# ── Citations ────────────────────────────────────────────────────────────────
#
# Three surfaces, all snapshot-scoped. A citation is the one place where a
# wrong value is copied out of the prototype and into someone else's work, so
# every input is a stored or governed value and an absent one stops the build.
#
# The record id is a locator INSIDE the declared snapshot. It is never called a
# permanent identifier, a DOI, an accession number or a public permalink, and
# the private preview route never appears in a citation.

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


def reader_date(iso: str) -> str:
    """`2026-08-08` -> `8 August 2026`.

    Day–month–year, per the standing reader-facing date convention
    (`DECISION_LOG.md` 2026-07-09): week-ending labels read "4 July 2026", and
    ISO `YYYY-MM-DD` is kept for tabular and metadata contexts. The convention
    governs date FORM; the American-English ruling of 2026-08-16 governs
    spelling, and does not reach it.

    An explicit month table rather than `strftime`, so the rendered string is
    identical on every machine regardless of locale — determinism is a tested
    property of this build.
    """
    year, month, day = (int(part) for part in iso.split("-"))
    return "%d %s %d" % (day, MONTHS[month - 1], year)


class CitationDataMissing(SystemExit):
    """A value a citation requires is absent.

    The build stops. The alternative is a citation that silently substitutes
    another field — an English title standing in for an original, a slug for an
    outlet — which is the one failure mode a citation must not have.
    """


def _require(value, field: str, subject: str):
    if value is None or (isinstance(value, str) and not value.strip()):
        raise CitationDataMissing(
            "cannot build a citation for %s: %s is absent.\n"
            "No other field is substituted and nothing is invented. Fix the "
            "stored record, or exclude it deliberately." % (subject, field))
    return value


def corpus_citation(title: str, snapshot: dict, maintainer=MAINTAINER) -> str:
    """The corpus snapshot citation.

    Date and count come from the declared snapshot object, which
    `assert_snapshot` has already proved against the database. Reading the
    count from the corpus as well would create a second source of truth for a
    value that is governed in exactly one place.
    """
    return ("{title}. China Desk Corpus. Prototype snapshot — {date}. "
            "{records:,} records. {name}, {role}.").format(
                title=title, date=snapshot["date"],
                records=snapshot["expected_records"],
                name=maintainer["name"], role=maintainer["role"])


#: One note per processing state. A single blanket machine-output sentence
#: applied to all four would assert machine output for records that have none,
#: and would claim a screening judgment for records never screened.
CITATION_PROCESSING_NOTES = {
    "analyzed":
        "The English title and summary held for this record are "
        "machine-generated and have not been reviewed by a human.",
    "not_selected":
        "This record was screened and not selected for analysis. No "
        "translation and no summary were produced.",
    "awaiting_screening":
        "This record has not been screened. No judgment of any kind has been "
        "made about it.",
    "analysis_incomplete":
        "This record passed relevance screening, but analysis did not "
        "complete. No completed analysis is claimed for it.",
}


def record_citation(record: dict, title: str, snapshot: dict) -> dict:
    """Two separate claims, kept separate.

    "Source text" cites the item as its publisher issued it; "As held" cites
    the record as this corpus holds it. They rest on different evidence and are
    rendered as two blocks so neither can be mistaken for the other.

    The source-text block uses the ORIGINAL title, always. The machine
    translation is never substituted for it — that is the substitution this
    function exists to make impossible.
    """
    subject = "record %s" % record.get("id")
    return {
        "source_text":
            'Source text. {institution}. "{original}." {outlet}, {date}. '
            '{url}.'.format(
                institution=_require(record.get("institution"),
                                     "publishing institution", subject),
                original=_require(record.get("title_original"),
                                  "original title", subject),
                outlet=_require(record.get("source_name"), "source outlet",
                                subject),
                date=_require(record.get("published_date"),
                              "source-stated publication date", subject),
                url=_require(record.get("url"), "original URL", subject)),
        "as_held":
            "As held. {work}, China Desk Corpus, Record {id}, Prototype "
            "snapshot — {date} ({records:,} records).".format(
                work=title,
                id=_require(record.get("id"), "record id", subject),
                date=snapshot["date"],
                records=snapshot["expected_records"]),
        "note": CITATION_PROCESSING_NOTES[record["state"]],
    }


def edition_citation(edition: dict, maintainer=MAINTAINER) -> str:
    """A published artifact's citation.

    Author named, NO role title appended (DECISION_LOG 2026-08-16). The
    citation identifies who wrote the edition; it does not retroactively
    rewrite the role under which the edition was originally published, and the
    historical sidecars are not edited to match a newer role.
    """
    subject = "edition %s" % (edition.get("slug") or "unknown")
    return ('{author}. "{title}." The PLA Watch, No. {issue}, week ending '
            '{date}. {url}.').format(
                author=maintainer["name"],
                title=_require(edition.get("title"), "edition title", subject),
                issue=_require(edition.get("issue"), "issue number", subject),
                date=reader_date(_require(edition.get("date"),
                                          "week ending date", subject)),
                url=_require(edition.get("url"), "canonical URL", subject))


def _week_page_path(week: dict, page_no: int, page_total: int) -> str:
    """Page 1 keeps the week's plain path so links stay stable when a week
    later grows past the budget and gains further pages."""
    if page_no == 1:
        return week["path"]
    return "week-%s-%d.html" % (week["start"], page_no)


def _render_week_pages(week: dict, tmpl, ctx: dict, per_page: int):
    chunks = [week["records"][i:i + per_page]
              for i in range(0, len(week["records"]), per_page)] or [[]]
    total = len(chunks)
    pages = []
    for index, chunk in enumerate(chunks, start=1):
        path = _week_page_path(week, index, total)
        pages.append((path, tmpl.render(
            page="corpus.html", week=week, records=chunk,
            page_count=len(chunk), paginated=total > 1,
            page_no=index, page_total=total,
            prev_path=(_week_page_path(week, index - 1, total)
                       if index > 1 else None),
            next_path=(_week_page_path(week, index + 1, total)
                       if index < total else None),
            **ctx)))
    return pages


def _paginate_week(week: dict, env, tmpl, ctx: dict):
    """Render a week, splitting it so BOTH limits hold.

    The record ceiling applies first, then the byte budget shrinks the page
    further if it still does not fit. Truncation is never an option. The split
    is a pure function of the record count, so two builds always agree.
    """
    per_page = min(len(week["records"]) or 1, SHARD_MAX_RECORDS)
    while True:
        pages = _render_week_pages(week, tmpl, ctx, per_page)
        largest = max(len(html.encode("utf-8")) for _, html in pages)
        if largest <= SHARD_BUDGET_BYTES or per_page <= 1:
            return pages
        per_page = max(1, per_page // 2)


# ── Rendering ────────────────────────────────────────────────────────────────

def snapshot_from_corpus(db_path) -> dict:
    """
    A declared snapshot describing the corpus as it actually is.

    `DECLARED_SNAPSHOT` is hand-advanced release metadata naming one frozen
    corpus, and `assert_snapshot` refuses to build any other under that name.
    Callers that legitimately want to render whatever corpus they are handed —
    tests, and anyone inspecting a build before advancing the release — pass the
    result of this instead. It is not a way around the guard: it states plainly
    which corpus is being described, rather than mislabelling one as another.
    """
    corpus = load_corpus(Path(db_path))["corpus"]
    return {
        "date": max(r["published_date"] for r in corpus),
        "expected_records": len(corpus),
        "logical_sha256": corpus_fingerprint(corpus),
    }


#: Legacy record redirect. A meta refresh plus a real link, and
#: `noindex` so the compatibility route never competes with the record page
#: it points at. Deterministic: no timestamp, no build id, no ordering.
LEGACY_REDIRECT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Moved</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="%(target)s">
<meta http-equiv="refresh" content="0; url=%(target)s">
</head>
<body>
<p>This record has moved to <a href="%(target)s">its record page</a>.</p>
</body>
</html>
"""


def build(out_dir: Path, title: str, db_path: Path,
          snapshot: dict = DECLARED_SNAPSHOT,
          legacy_routes: bool = False) -> dict:
    out_dir = Path(out_dir).resolve()
    if out_dir == PRODUCTION_OUT or PRODUCTION_OUT in out_dir.parents:
        raise SystemExit(
            "refusing to write inside production output/: %s\n"
            "The prototype must never alter the published site." % out_dir)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    data = load_corpus(db_path)

    # Declared, not inferred. Fixtures pass their own snapshot; the default is
    # the production-preview assertion and is never relaxed for a fixture.
    assert_snapshot(data["corpus"], snapshot)
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                      autoescape=True, trim_blocks=True, lstrip_blocks=True)
    env.filters["status_label"] = lambda s: STATUS_PROSE.get(s, (s, ""))[0]
    env.filters["status_prose"] = lambda s: STATUS_PROSE.get(s, ("", s))[1]
    env.filters["source_type_label"] = (
        lambda v: SOURCE_TYPE_LABELS.get(v, v or "—"))
    # Thousands separators for reader-facing counts. Never applied to ids,
    # dates, hashes, run numbers or source codes.
    env.filters["count"] = (
        lambda n: "{:,}".format(n) if isinstance(n, int) else n)

    gaps = collection_gaps(data["run_days"])
    editions = load_editions(REPO_ROOT)
    live_desks = [d for d in DESKS if d["state"] == "live"]

    # Corpus Guide figures. Derived once, from the same loaded corpus the pages
    # render, so the guide cannot describe a different snapshot than the one
    # `assert_snapshot` just approved.
    guide_stats = corpus_guide_stats(data["corpus"], data["run_days"])

    by_source = Counter(a["source_slug"] for a in data["recent"])

    # Snapshot identity is DECLARED editorial metadata, never a wall clock,
    # never a semantic version, and — since 2026-08-16 — never inferred from
    # `MAX(published_date)`. Inference lets a changed corpus republish under an
    # unchanged snapshot date; `assert_snapshot` above makes that a build
    # failure instead.
    snapshot_date = snapshot["date"]
    snapshot_label = "Prototype snapshot — %s" % snapshot_date
    # Citation carries the snapshot date and the total record count. It must
    # never assert an id range: ids are not contiguous (3,250 records against a
    # max id of 3,256), so "records 1–3250" would be false. Both values come
    # from the declared snapshot, which is the single governed source.
    citation = corpus_citation(title, snapshot)

    ctx = {
        "title": title,
        "tagline": TAGLINE,
        "corpus_eyebrow": CORPUS_EYEBROW,
        "maintainer": MAINTAINER,
        "snapshot_label": snapshot_label,
        "citation": citation,
        "japan_scope": JAPAN_SCOPE,
        "institutions": data["institutions"],
        "run_status": run_status_summary(
            data["latest_run"], data["run_results"],
            data["collecting_desks"], data["unmapped_executed"]),
        "status_run_note": STATUS_RUN_NOTE,
        "lead_edition": editions[0] if editions else None,
        "desks": DESKS,
        "live_desk_count": len(live_desks),
        "developing_desk_count": len(DESKS) - len(live_desks),
        "sources": data["sources"],
        "totals": data["totals"],
        "latest_run": data["latest_run"],
        "run_results": data["run_results"],
        "articles": data["recent"],
        "gaps": gaps,
        "source_facets": sorted(by_source.items()),
        "status_prose": STATUS_PROSE,
        "editions": editions,
        # Every published edition, cited from its own sidecar values. Built
        # here rather than in the template so an absent title, issue, date or
        # canonical URL fails the build instead of rendering a gap.
        "edition_citations": [
            {"edition": edition, "citation": edition_citation(edition),
             "anchor": "cite-edition-%s" % edition["slug"]}
            for edition in editions],
        "live_base": LIVE_BASE,
        "snapshot": snapshot,
        "corpus_total": len(data["corpus"]),
        "state_counts": data["state_counts"],
        "corpus_facets": data["facets"],
        "weeks": data["weeks"],
        "guide_stats": guide_stats,
        "dictionary": dictionary_rows(guide_stats),
        "changelog": changelog_entries(guide_stats),
        # Bars are scaled to the largest week's RECORD COUNT.
        # Never a run-date normalisation: that would render a
        # rate the data cannot support.
        "volume_max": max((w["count"] for w in data["weeks"]),
                          default=1),
    }

    pages = {
        "index.html": "home.html",
        "desks.html": "desks.html",
        "china.html": "desk_china.html",
        "japan.html": "desk_japan.html",
        "archive.html": "archive.html",
        "corpus-guide.html": "corpus_guide.html",
        "coverage.html": "coverage.html",
        "sources.html": "sources.html",
        "weekly.html": "weekly.html",
        "methodology.html": "methodology.html",
        "about.html": "about.html",
    }
    written = []
    for target, template in pages.items():
        (out_dir / target).write_text(
            env.get_template(template).render(page=target, **ctx),
            encoding="utf-8")
        written.append(target)

    # ── record/{id}.html — one page per stored record ────────────────────────
    # `record/`, deliberately NOT `article/`: the production namespace holds
    # 1,110 analyzed articles and is live and canonical, while this holds all
    # 3,250 stored records and is a prototype path. Ids are taken as stored, so
    # the six gaps below MAX(id) stay absent rather than being enumerated.
    (out_dir / "record").mkdir(parents=True)
    record_tmpl = env.get_template("record.html")
    definitions = {s["code"]: s["definition"] for s in PROCESSING_STATES}
    for rec in data["corpus"]:
        (out_dir / "record" / ("%d.html" % rec["id"])).write_text(
            record_tmpl.render(page="archive.html", record=rec,
                               state_definition=definitions[rec["state"]],
                               cite=record_citation(rec, title, snapshot),
                               **ctx),
            encoding="utf-8")
        written.append("record/%d.html" % rec["id"])

    # ── Week shards ──────────────────────────────────────────────────────────
    # Ordinary static pages. Every record is reachable from corpus.html through
    # plain links with JavaScript disabled — no facets, no result-count script,
    # no compact index and no volume bars at this checkpoint.
    week_tmpl = env.get_template("corpus_week.html")
    shard_sizes = {}
    for week in data["weeks"]:
        pages = _paginate_week(week, env, week_tmpl, ctx)
        for path, html in pages:
            (out_dir / path).write_text(html, encoding="utf-8")
            written.append(path)
            shard_sizes[path] = len(html.encode("utf-8"))

    # ── Compact query index ──────────────────────────────────────────────────
    # External and fetched, never inlined: production's archive is 1.79 MB
    # precisely because it embeds the corpus twice. Emitted only after
    # assert_snapshot() has passed, so an index can never describe a corpus the
    # build refused to publish. Sorted keys and fixed separators keep it
    # byte-deterministic.
    index = corpus_index(data["corpus"], data["sources"], snapshot)
    (out_dir / "corpus-index.json").write_text(
        json.dumps(index, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")) + "\n",
        encoding="utf-8")
    written.append("corpus-index.json")

    (out_dir / "browse.js").write_text(
        (Path(__file__).parent / "browse.js").read_text(encoding="utf-8"),
        encoding="utf-8")
    written.append("browse.js")

    # Citation copy controls. Loaded only by the Corpus Guide, the record pages
    # and Analysis — never by Archive, where browse.js already sits close to
    # the 10 KB per-page script budget.
    (out_dir / "citation.js").write_text(
        (Path(__file__).parent / "citation.js").read_text(encoding="utf-8"),
        encoding="utf-8")
    written.append("citation.js")

    (out_dir / "corpus.html").write_text(
        env.get_template("corpus_weeks.html").render(page="corpus.html", **ctx),
        encoding="utf-8")
    written.append("corpus.html")

    (out_dir / "styles.css").write_text(
        (Path(__file__).parent / "styles.css").read_text(encoding="utf-8"),
        encoding="utf-8")
    written.append("styles.css")

    # ── Legacy route continuity ──────────────────────────────────────────
    # Off by default, so the prototype build keeps its guarantee of never
    # creating the production `article/` namespace — the preview is built
    # inside the repo and a collision there would be indistinguishable from
    # the published site.
    #
    # A production-capable Declared Record build turns it on, because
    # /article/<id>.html is a live URL today: 1,216 of them are public and
    # some are cited. Losing them at launch would break the one promise this
    # project makes about its own record. Each becomes a deterministic
    # redirect to the record page holding the same article, written from the
    # corpus rather than from a directory listing, so an id that is not in
    # this snapshot does not silently acquire a redirect to nothing.
    redirects = 0
    if legacy_routes:
        legacy_dir = out_dir / "article"
        legacy_dir.mkdir(parents=True, exist_ok=True)
        for rec in sorted(data["corpus"], key=lambda r: r["id"]):
            target = "../record/%d.html" % rec["id"]
            (legacy_dir / ("%d.html" % rec["id"])).write_text(
                LEGACY_REDIRECT % {"target": target}, encoding="utf-8")
            redirects += 1
        written.append("article/*.html")

    return {"out_dir": out_dir, "files": written,
            "articles": len(data["recent"]), "editions": len(editions),
            "records": len(data["corpus"]), "weeks": len(data["weeks"]),
            "legacy_redirects": redirects}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--title", default=WORKING_TITLE,
                    help="working title; NOT a public name")
    ap.add_argument("--db", default=str(TRACKED_DB))
    ap.add_argument("--serve", action="store_true",
                    help="serve the result on localhost:8770")
    args = ap.parse_args(argv)

    result = build(Path(args.out), args.title, Path(args.db))
    print("preview: %d files -> %s" % (len(result["files"]), result["out_dir"]))
    print("title  : %s (working title, not adopted)" % args.title)
    print("data   : %d real articles; no desk other than China shows any data"
          % result["articles"])
    print("corpus : %d record pages across %d publication weeks"
          % (result["records"], result["weeks"]))
    print("weekly : %d real editions linked to the live archive (never copied)"
          % result["editions"])

    if args.serve:
        import http.server, socketserver, functools
        handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                    directory=str(result["out_dir"]))
        with socketserver.TCPServer(("127.0.0.1", 8770), handler) as httpd:
            print("serving http://127.0.0.1:8770/  (ctrl-c to stop)")
            httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
