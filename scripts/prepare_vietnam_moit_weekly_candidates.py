"""Verified, metadata-only weekly candidate inventory for Vietnam's MOIT desks.

MOIT Energy and MOIT Foundational Industry are distinct isolated shadow
collectors, not production sources. Their source-specific Git state, capture
ledger, publication dates and content-version digests must be independently
validated before a record may even become an *editorial research lead*.

No captured article text, translated body, model prompt or rights assertion is
exported. A source absent from this bounded inventory means only that the
verified collector has no eligible *observed* item in this selected window.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from datetime import date, timedelta
from pathlib import Path

from core.collection.vietnam_sources import SOURCES
from scripts import review_vietnam_ministry_state as ministry
from scripts import review_vietnam_shadow_state as formal

MOIT_SOURCES = frozenset({
    "vn_moit_energy_vi", "vn_moit_foundational_industry_vi",
})
SCHEMA = "vietnam-moit-weekly-verified-candidates/1"
MAX_RECORDS = 100
MAX_ITEMS_IN_WEEK = 20
MAX_TITLE = 400
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
HEX64 = re.compile(r"[a-f0-9]{64}\Z")


class MOITInventoryRefused(ValueError):
    pass


def require(test, message):
    if not test:
        raise MOITInventoryRefused(message)


def saturday(value):
    require(isinstance(value, str) and
            re.fullmatch(r"\d{4}-\d{2}-\d{2}", value),
            "reporting Saturday must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise MOITInventoryRefused("invalid reporting date") from exc
    require(parsed.isoformat() == value and parsed.weekday() == 5,
            "reporting date must be canonical Saturday")
    return parsed


def canonical(value):
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def summary(evidence, slug, state_commit, state_tree, week_ending):
    """Machine-only inventory of audited observed source records."""
    week_end = saturday(week_ending)
    week_start = week_end - timedelta(days=6)
    require(slug in MOIT_SOURCES and evidence.get("source_slug") == slug,
            "invalid or foreign MOIT source family")
    require(isinstance(state_commit, str) and HEX40.fullmatch(state_commit)
            and isinstance(state_tree, str) and HEX40.fullmatch(state_tree),
            "exact verified source-state commit/tree required")
    profile = SOURCES[slug]
    clock = evidence.get("clock")
    runs = evidence.get("runs")
    require(isinstance(clock, dict) and clock.get("day_zero_utc") and
            isinstance(runs, list) and runs and
            runs[-1].get("health") == "ok",
            "no durable healthy source clock/recent run")
    records, versions, observations = (
        evidence.get(key) for key in ("records", "versions", "observations"))
    require(all(isinstance(x, list) for x in (records, versions, observations))
            and len(records) <= MAX_RECORDS,
            "MOIT inventory unexpectedly malformed or large")
    all_versions = {(v["source_identity"], v["content_sha256"]): v for v in versions}
    by_identity = {}
    for item in observations:
        by_identity.setdefault(item["source_identity"], []).append(item)
    items = []
    identifiers = set()
    machine_holds = 0
    old_records = 0
    for r in records:
        identity, url, digest = (
            r.get("source_identity"), r.get("url"),
            r.get("current_content_sha256"))
        require(isinstance(url, str) and
                profile.identity(url) == identity and
                r.get("canonical_url") == url and
                r.get("source_slug") == slug and
                isinstance(digest, str) and HEX64.fullmatch(digest) and
                isinstance(identity, str) and identity not in identifiers,
                "invalid or duplicate MOIT source identity/digest")
        identifiers.add(identity)
        published = r.get("published_date")
        require(isinstance(published, str), "missing visible publication date")
        try:
            day = date.fromisoformat(published)
        except ValueError as exc:
            raise MOITInventoryRefused("invalid source-stated publication date") from exc
        require(day.isoformat() == published,
                "publication date not canonical")
        if not week_start <= day <= week_end:
            old_records += 1
            continue
        v = all_versions.get((identity, digest))
        source_observations = by_identity.get(identity, [])
        blockers = []
        if v is None or v.get("body_status") != "text":
            blockers.append("current_source_body_not_verified")
        if v is not None and not v.get("text_original", "").strip():
            blockers.append("empty_original_language_capture")
        if v is not None and not any(
            x.get("run_id") == v.get("first_seen_run")
            and x.get("content_sha256") == digest
            and x.get("capture_sha256") == v.get("first_capture_sha256")
            for x in source_observations
        ):
            blockers.append("missing_verified_capture_version")
        if any(json.loads(x.get("anomalies_json", "null"))
               for x in source_observations):
            blockers.append("source_observation_anomaly")
        title = v.get("title_original") if v is not None else None
        if not isinstance(title, str) or not 8 <= len(title.strip()) <= MAX_TITLE:
            blockers.append("missing_original_vietnamese_title")
        if blockers:
            machine_holds += 1
        items.append({
            "source_identity": identity,
            "source_slug": slug,
            "desk": "vietnam",
            "publisher": profile.publisher,
            "source_url": url,
            "published_date": published,
            "title_original": title,
            "language": "vi",
            "source_content_sha256": digest,
            "hash_rule": profile.hash_rule,
            "state_commit": state_commit,
            "machine_eligible": not blockers,
            "machine_blockers": sorted(set(blockers)),
            "human_source_reviewed": False,
            "source_use_authorized": False,
            "model_synopsis_available": False,
            "private_model_contribution_authorized": False,
        })
    items.sort(key=lambda x: (x["published_date"], x["source_identity"]),
               reverse=True)
    require(len(items) <= MAX_ITEMS_IN_WEEK,
            "too many observed records for bounded editorial review")
    # Only a known source collection run is reported, not an assertion that
    # every ministry page/new publication was observed by this limited feed.
    recent = runs[-1]
    last_target = recent.get("target_date")
    require(isinstance(last_target, str) and
            re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_target),
            "last verified source logical target is unknown")
    out = {
        "schema": SCHEMA,
        "source_slug": slug,
        "state_branch": profile.state_branch,
        "state_commit": state_commit,
        "state_tree": state_tree,
        "source_family": profile.family,
        "week_start": week_start.isoformat(),
        "week_ending": week_ending,
        "last_successful_observed_target": last_target,
        "full_week_collection_verified": False,
        "publisher_silence_verified": False,
        "qualified_production_desk": False,
        "original_full_text_included": False,
        "human_approvals": 0,
        "source_use_approvals": 0,
        "total_archived_records": len(records),
        "out_of_window_archived_records": old_records,
        "in_window_record_count": len(items),
        "machine_eligible_in_window": len(items) - machine_holds,
        "machine_held_in_window": machine_holds,
        "items": items,
    }
    out["inventory_sha256"] = hashlib.sha256(canonical(out).encode()).hexdigest()
    return out


def prepare(state_repo, commit, slug, week_ending):
    require(slug in MOIT_SOURCES, "MPS and unapproved sources not accepted")
    require(isinstance(commit, str) and HEX40.fullmatch(commit),
            "full source-state Git commit required")
    saturday(week_ending)
    profile = SOURCES[slug]
    repo = formal.resolve_state_repo(state_repo)
    proven = formal.verify_state_commit(repo, commit, profile.state_branch)
    with tempfile.TemporaryDirectory(prefix="ipr-vn-moit-verified-") as temp:
        state = formal.export_state_tree(repo, commit, Path(temp) / "state")
        evidence = ministry.review(state, slug)
        return summary(evidence, slug, commit, proven["state_tree"], week_ending)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--state-repo", required=True, type=Path)
    p.add_argument("--state-commit", required=True)
    p.add_argument("--source", required=True, choices=sorted(MOIT_SOURCES))
    p.add_argument("--week-ending", required=True)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    target = args.out
    root = Path(__file__).resolve().parents[1].resolve()
    resolved = target.resolve()
    require(not target.exists() and not target.is_symlink()
            and target.parent.is_dir() and not target.parent.is_symlink()
            and resolved != root and root not in resolved.parents,
            "output must be a new private file outside main repository")
    result = prepare(args.state_repo, args.state_commit, args.source,
                     args.week_ending)
    target.write_text(canonical(result))
    print(json.dumps({
        "source": result["source_slug"],
        "week_ending": result["week_ending"],
        "in_window_observed": result["in_window_record_count"],
        "machine_eligible": result["machine_eligible_in_window"],
        "human_approvals": 0,
        "private_model_contribution_authorized": False,
        "publisher_silence_verified": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
