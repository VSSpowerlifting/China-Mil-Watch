"""Private read-only all-desk weekly evidence inventory for regional editorial review.

NOT a model prompt, external research attestation, collection-success proof,
publisher-rights clearance or public publication eligibility check. The
inventory never sends raw article text or approves a Brief.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from config import DB_PATH
from core.brief_contract import (
    SCREENING_NOT_SELECTED, eligible_desks, screening_state,
)
from core.brief_editorial_evidence import load_editorial_evidence
from core.desk_registry import load_registry
from core.regional_editorial_slate import SCHEMA as SLATE_SCHEMA, validate_slate
from scripts.reconcile_db import read_only
from scripts.sunday_corpus_readiness import evaluate, iso_day
from storage.db import get_articles_for_desks

SCHEMA = "ipr-regional-weekly-evidence/1"
MIN_TEXT = 250


class InventoryError(ValueError):
    """Refuse inconsistent corpus or provenance claims before editorial use."""


def _https_url(value):
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    try:
        u = urlsplit(value)
        return (u.scheme == "https" and bool(u.hostname) and u.port is None
                and u.username is None and u.password is None and not u.fragment)
    except ValueError:
        return False


def _source_record(row, *, known_sources):
    """Produce one metadata-only evidence record or a bounded hold reason."""
    if screening_state(row) == SCREENING_NOT_SELECTED:
        return None, "screened_not_selected"
    if not row["source_slug"] or row["source_slug"] not in known_sources:
        return None, "source_not_in_declared_desk_manifest"
    if not _https_url(row["url"]):
        return None, "publisher_url_requires_review"
    if not isinstance(row["title_original"], str) or not row["title_original"].strip():
        return None, "missing_original_title"
    original = (row["text_original"] or "").strip()
    english = (row["text_english"] or "").strip()
    # Consistent with Sunday's existing full-text threshold. English machine
    # renderings still require original-language checking before publication.
    body = english if len(english) >= MIN_TEXT else original
    if len(body) < MIN_TEXT:
        return None, "insufficient_stored_full_text"
    lang = row["source_language_tag"] or ""
    if not isinstance(lang, str) or not lang.strip():
        return None, "missing_source_language"
    return {
        "id": row["id"],
        "desk": row["desk_id"],
        "lane": "production_record",
        "scope": "production_evidence",
        "source_slug": row["source_slug"],
        "source_name": row["source_name"],
        "title_original": row["title_original"],
        "source_url": row["url"],
        "published_date": row["published_date"],
        "language": lang,
        "screening": screening_state(row),
        "body_basis": ("stored_english_rendering" if body == english and
                       len(english) >= MIN_TEXT else "stored_original"),
        "stored_text_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "stored_text_length": len(body),
        "role": "new_week",
        "topic_suggestions": [],
    }, None


def build_inventory(*, registry, rows, week_ending, as_of, review_day,
                    marker="", research_rows=()):
    """Inventory every declared desk and every in-week live-desk record.

    rows MUST be the complete exact-week selection from
    storage.db.get_articles_for_desks(), never the Sunday's top-ten excerpt.
    research_rows MUST originate from load_editorial_evidence(), whose schema
    alone is not a real shadow-state attestation; every item stays pending.
    """
    saturday = iso_day(week_ending)
    cutoff = iso_day(as_of)
    day = iso_day(review_day)
    if saturday.weekday() != 5 or not saturday - timedelta(days=6) <= cutoff <= saturday:
        raise InventoryError("reporting window must be Sunday through Saturday")
    if cutoff > day:
        raise InventoryError("source cutoff cannot be after review date")
    desks = list(registry)
    if not desks or len({d.slug for d in desks}) != len(desks):
        raise InventoryError("missing or duplicate desk declarations")
    live = eligible_desks(registry)
    if len(live) < 2:
        raise InventoryError("current Sunday readiness requires two live desks")
    # Audit is necessary, but does NOT assert source completeness or publisher
    # rights. Its verdict is retained distinctly from editorial eligibility.
    snapshot = list(rows)
    audit = evaluate(rows=snapshot, desks=live, week_ending=week_ending,
                     as_of=as_of, review_day=review_day, marker=marker)

    ids = set()
    urls = set()
    included = []
    held = []
    stats = {d.slug: Counter() for d in desks}
    manifest_sources = {d.slug: {s.slug for s in d.sources} for d in desks}
    for row in snapshot:
        rid = row["id"]
        desk = row["desk_id"]
        url = row["url"]
        if type(rid) is not int or rid <= 0 or rid in ids:
            raise InventoryError("duplicate or nonnumeric production record ID")
        ids.add(rid)
        if not isinstance(url, str) or url in urls:
            # Cross-institution duplicates must not inflate a region-wide view.
            raise InventoryError("duplicate or malformed stored source URL")
        urls.add(url)
        if desk not in live:
            raise InventoryError("nonproduction desk in live archive selection")
        if not saturday - timedelta(days=6) <= iso_day(row["published_date"]) <= cutoff:
            raise InventoryError("archive row escapes reporting window")
        stats[desk]["stored"] += 1
        pointer, hold = _source_record(row, known_sources=manifest_sources[desk])
        if hold:
            stats[desk]["held"] += 1
            held.append({"record_id": rid, "desk": desk, "reason": hold})
        else:
            stats[desk]["reviewable"] += 1
            included.append(pointer)

    research_pending = []
    seen_research = set()
    for item in research_rows:
        # No raw article bodies or synopsis can cross this handoff. The
        # published corpus and shadow records remain separate trust lanes.
        ident, desk, url = item["id"], item["desk"], item["source_url"]
        if (not isinstance(ident, str) or not ident or ident.isdigit()
                or ident in seen_research or desk not in stats
                or desk in live or not _https_url(url) or url in urls):
            raise InventoryError("untrusted or production-duplicated research candidate")
        if not saturday - timedelta(days=6) <= iso_day(item["published_date"]) <= cutoff:
            raise InventoryError("research candidate outside the reporting window")
        if item.get("status") != "unapproved-source-linked-editorial-candidate":
            raise InventoryError("research candidate falsely claims approval")
        seen_research.add(ident)
        research_pending.append({
            "id": ident, "desk": desk, "source_url": url,
            "published_date": item["published_date"],
            "reason": "independent_shadow_attestation_and_source_use_pending",
        })
        stats[desk]["pending_research"] += 1

    marker_complete = (cutoff == saturday and day > saturday
                       and marker == (saturday + timedelta(days=1)).isoformat())
    coverage = []
    for desk in desks:
        counts = stats[desk.slug]
        if desk.slug in live:
            if counts["reviewable"]:
                state = "reviewable"
                reason = ("Stored in-week full text available for human review; "
                          "originals, source rights and collection completeness not certified")
            elif counts["held"]:
                state = "awaiting_validation"
                reason = "Observed production records are held for content or provenance review"
            elif marker_complete:
                state = "no_qualifying_evidence"
                reason = ("No qualifying stored records observed in this reporting window; "
                          "not a claim of institutional inactivity or exhaustive coverage")
            else:
                state = "awaiting_validation"
                reason = ("No qualifying stored records observed; reporting window or "
                          "Sunday production-success receipt not confirmed")
        elif desk.status in ("research", "shadow"):
            state = "awaiting_validation"
            reason = ("Not a production desk; private research is pending independent "
                      "source attestation, source-use clearance and editorial review")
        else:
            state = "collector_unavailable"
            reason = ("Registry status " + desk.status +
                      "; no eligible production source; publisher activity cannot be inferred")
        coverage.append({
            "desk": desk.slug,
            "registry_status": desk.status,
            "state": state,
            "reason": reason,
            "stored": counts["stored"],
            "reviewable": counts["reviewable"],
            "held": counts["held"],
            "pending_research": counts["pending_research"],
        })

    included.sort(key=lambda x: (x["published_date"], x["desk"], x["id"]), reverse=True)
    held.sort(key=lambda x: (x["desk"], x["record_id"]))
    research_pending.sort(key=lambda x: (x["desk"], x["id"]))
    # A mechanically compatible blank slate. The editorial phase must propose
    # actual themes; this inventory NEVER ranks stories or assigns the lead.
    seed = {
        "schema": SLATE_SCHEMA,
        "week_start": (saturday - timedelta(days=6)).isoformat(),
        "week_ending": week_ending,
        "coverage": [{"desk": x["desk"], "state": x["state"],
                      "reason": x["reason"]} for x in coverage],
        "evidence": [
            {k: entry[k] for k in ("id", "desk", "lane", "scope",
                                  "source_url", "published_date", "role",
                                  "topic_suggestions")}
            for entry in included
        ],
        "candidates": [],
        "provisional_lead": None,
        "lead_rationale": "No candidate theme has been proposed or approved.",
    }
    validate_slate(seed, expected_desks=[d.slug for d in desks])
    snapshot_payload = json.dumps(
        {"evidence": included, "held": held, "pending": research_pending,
         "coverage": coverage}, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")
    return {
        "schema": SCHEMA,
        "week_start": seed["week_start"],
        "week_ending": week_ending,
        "source_as_of": as_of,
        "review_local_day": review_day,
        "source_metadata_digest_sha256": hashlib.sha256(snapshot_payload).hexdigest(),
        "production_preflight": audit["machine_preflight_verdict"],
        "unmet_production_gates": audit["unmet_gates"],
        "coverage": coverage,
        "production_evidence": included,
        "held_production_records": held,
        "pending_private_research": research_pending,
        "empty_editorial_slate": seed,
        "source_trust_status": "inventory_only_not_attested_for_model_or_publication",
        "model_input_authorized": False,
        "editor_email_authorized": False,
        "publication_authorized": False,
    }


def inspect(*, week_ending, as_of, review_day, database=DB_PATH,
            marker_path=Path(".github/state/last_daily_run_date.txt"),
            research_directory=None, registry=None):
    """Read SQLite via disposable scratch copy; no external fetch or writes."""
    saturday, cutoff = iso_day(week_ending), iso_day(as_of)
    if saturday.weekday() != 5 or not saturday - timedelta(days=6) <= cutoff <= saturday:
        raise InventoryError("invalid Saturday reporting window")
    registry = registry if registry is not None else load_registry()
    live = eligible_desks(registry)
    marker_file = Path(marker_path)
    marker = marker_file.read_text(encoding="utf-8").strip() if marker_file.is_file() else ""
    # Inclusion is *not* endorsement: these are unapproved metadata holds.
    research = (load_editorial_evidence(week_ending, as_of,
                                       directory=research_directory)
                if research_directory is not None else [])
    with read_only(Path(database)) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise InventoryError("tracked SQLite integrity check failed")
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise InventoryError("tracked SQLite foreign-key check failed")
        rows = get_articles_for_desks(
            (saturday - timedelta(days=6)).isoformat(), as_of, live, conn=conn)
    return build_inventory(
        registry=registry, rows=rows, week_ending=week_ending, as_of=as_of,
        review_day=review_day, marker=marker, research_rows=research)
