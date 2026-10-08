"""Build Sunday's *private* Vietnam model research from a verified shadow state.

The only automatic new-source evidence is METADATA-ONLY; a headline is not
proof of the article's claims. Source-specific editorial synopses may be
carried forward only when their pinned version matches a fully validated
current shadow record. Neither kind is approval for a numbered public Brief.

This program never opens official URLs, calls an LLM, sends email, modifies
a shadow clone, archives source text, or changes production SQLite/output.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

from core.brief_editorial_evidence import (
    COPY_SCOPE, MAX_ITEMS, SCHEMA, STATUS, load_editorial_evidence,
    metadata_only_summary,
)
from core.collection.vietnam_sources import SOURCES
from scripts import review_vietnam_ministry_state as ministry
from scripts import review_vietnam_shadow_state as formal
from scripts.prepare_vietnam_mps_review_queue import compile_queue
from scripts.shadow_collect_vietnam_ministry import load_source

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "vn_mps_foreign_affairs_vi"
STATE_BRANCH = SOURCES[SOURCE].state_branch
MAX_MPS_ITEMS = 5
MPS_ID = re.compile(r"mps-vi:([0-9]{10})\Z")
CAUTIONS = [
    "Source metadata confirms a published ministry portal item, not the truth of the events implied by its title.",
    "Only the official original and independently checked content may support substantive final-publication claims.",
]


class VietnamFeedRefused(ValueError):
    """A source packet would falsely describe current or reviewed evidence."""


def require(ok, reason):
    if not ok:
        raise VietnamFeedRefused(reason)


def exact_day(value):
    require(isinstance(value, str), "calendar date required")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise VietnamFeedRefused("invalid calendar date") from exc
    require(result.isoformat() == value, "date must be ISO YYYY-MM-DD")
    return result


def _publication_window(week_ending):
    saturday = exact_day(week_ending)
    require(saturday.weekday() == 5, "editorial week must end Saturday")
    return saturday - timedelta(days=6), saturday


def metadata_card(record, commit):
    """Safe if source only appears in validated shadow state; no body claims."""
    ident = record["source_identity"]
    match = MPS_ID.fullmatch(ident) if isinstance(ident, str) else None
    require(match is not None, "unrecognized MPS source identity")
    return {
        "id": "VN-MPS-" + match.group(1),
        "desk": "vietnam",
        "source_name": "Vietnam Ministry of Public Security",
        "source_url": record["canonical_url"],
        "published_date": record["published_date"],
        "language": "vi",
        "title_original": record["title_original"],
        "source_kind": "shadow-metadata-only",
        "state_commit": commit,
        "source_content_sha256": record["content_sha256"],
        "hash_rule": SOURCES[SOURCE].hash_rule,
        "summary": metadata_only_summary(record["published_date"]),
        "caveats": list(CAUTIONS),
        "topics": ["source_discovery"],
        "status": STATUS,
        "copy_scope": COPY_SCOPE,
    }


def assemble(queue, curated, current_commit, week_ending):
    """Use only current, anomaly-free MPS state plus pre-existing Japan notes.

    Nothing newly published receives an invented analytical synopsis. Curated
    source-specific descriptions survive only exact current-version parity.
    A changed current version is downgraded to publication-metadata discovery.
    """
    start, cutoff = _publication_window(week_ending)
    require(queue.get("schema") == "vietnam-mps-pilot-review-queue/1"
            and queue.get("source_slug") == SOURCE
            and queue.get("state_branch") == STATE_BRANCH
            and queue.get("state_commit") == current_commit,
            "unverified or wrong-source MPS candidate queue")
    require(queue.get("human_approvals") == 0 and queue.get("rights_approvals") == 0
            and queue.get("automatic_production_admission") is False
            and queue.get("full_desk_qualification") is False,
            "machine queue cannot claim source rights, publication or desk approval")
    require(isinstance(curated, list), "curated research input must be a list")
    japan = [dict(x) for x in curated if x.get("desk") == "japan"]
    existing_vn = [x for x in curated if x.get("desk") == "vietnam"]
    require(len(existing_vn) + len(japan) == len(curated),
            "foreign research source appeared in Japan/Vietnam feeder")
    current_ids = set()
    candidates = []
    seen_seed = {x["id"]: x for x in existing_vn}
    require(len(seen_seed) == len(existing_vn), "duplicate curated MPS IDs")
    for record in queue["records"]:
        ident = record["source_identity"]
        match = MPS_ID.fullmatch(ident) if isinstance(ident, str) else None
        require(match is not None, "unexpected ministry identity in validated queue")
        identity = "VN-MPS-" + match.group(1)
        current_ids.add(identity)
        day = exact_day(record["published_date"])
        if not start <= day <= cutoff:
            continue
        if not record["machine_review_candidate"] or record["machine_blockers"]:
            continue
        require(record["source_slug"] == SOURCE
                and SOURCES[SOURCE].identity(record["canonical_url"]) == ident
                and record["body_status"] == "text"
                and record["body_character_count"] > 0,
                "candidate lost MPS source identity or captured text")
        card = metadata_card(record, current_commit)
        old = seen_seed.get(identity)
        if old:
            require(old["source_url"] == card["source_url"]
                    and old["title_original"] == card["title_original"]
                    and old["published_date"] == card["published_date"]
                    and old["language"] == "vi",
                    "curated source metadata drifted from verified state")
            if old["source_content_sha256"] == card["source_content_sha256"]:
                # The short original editorial synopsis can be reused because
                # the exact current version has been validated; no new review
                # or body reproduction is inferred by this replacement.
                require(old["source_kind"] == "shadow-extracted-original"
                        and old["hash_rule"] == card["hash_rule"],
                        "curated source has different hash rule/role")
                card = dict(old, state_commit=current_commit)
            # Else exact source content changed: the old synopsis is not usable.
        candidates.append(card)
    # Do not drop a previously curated source silently when it disappears from
    # the verified inventory or is now blocked; the operator needs to inspect.
    require(all(identity in current_ids for identity in seen_seed),
            "curated MPS source missing from the verified state inventory")
    candidates.sort(key=lambda x: (x["published_date"], x["id"]), reverse=True)
    max_vn = min(MAX_MPS_ITEMS, MAX_ITEMS - len(japan))
    require(max_vn >= 0, "Japan input alone exceeds research evidence capacity")
    chosen = candidates[:max_vn]
    ids = [x["id"] for x in japan + chosen]
    urls = [x["source_url"] for x in japan + chosen]
    require(len(set(ids)) == len(ids) and len(set(urls)) == len(urls),
            "duplicate combined Japan/Vietnam source identity or URL")
    result = {
        "schema": SCHEMA,
        "week_ending": week_ending,
        "status": STATUS,
        "items": japan + chosen,
    }
    return result, {
        "japan_research_items": len(japan),
        "vietnam_shadow_candidates_in_week": len(candidates),
        "vietnam_items_merged": len(chosen),
        "vietnam_original_synopses_retained": sum(
            x["source_kind"] == "shadow-extracted-original" for x in chosen),
        "vietnam_metadata_only": sum(
            x["source_kind"] == "shadow-metadata-only" for x in chosen),
        "public_records_admitted": 0,
        "human_approvals_granted": 0,
    }


def prepare(state_repo, state_commit, week_ending, out_path, *,
            curated_dir=None, japan_packet=None):
    """Export immutable MPS source-state and prepare exact-week private packet."""
    start, cutoff = _publication_window(week_ending)
    del start, cutoff
    require(isinstance(state_commit, str) and
            re.fullmatch(r"[0-9a-f]{40}", state_commit) is not None,
            "exact 40-character remote state commit required")
    out = Path(out_path)
    require(out.name == week_ending + ".json", "output must name exact Saturday")
    require(not out.is_symlink() and not out.exists(),
            "private output must not already exist or be a symlink")
    require(not out.parent.is_symlink(), "private output parent cannot be linked")
    target = out.resolve()
    require(target != ROOT and ROOT not in target.parents,
            "private model research packet must stay outside public checkout")
    state_repo = formal.resolve_state_repo(state_repo)
    provenance = formal.verify_state_commit(state_repo, state_commit, STATE_BRANCH)
    # The job must use the exact current state branch tip, not a past SHA:
    # a new source version cannot be bypassed with a stale verified state.
    require(provenance["state_ref_tip"] == state_commit,
            "MPS feed must use current remote branch tip")
    seed_dir = (Path(curated_dir) if curated_dir is not None else
                ROOT / "research" / "briefs_editorial_evidence")
    curated = load_editorial_evidence(week_ending, week_ending,
                                     directory=seed_dir)
    if japan_packet is not None:
        independent = Path(japan_packet)
        require(independent.name == week_ending + ".json"
                and independent.is_file() and not independent.is_symlink(),
                "Japan export must be an existing exact-week regular JSON packet")
        independently_validated = load_editorial_evidence(
            week_ending, week_ending, directory=independent.parent)
        require(all(item["desk"] == "japan"
                    for item in independently_validated),
                "Japan packet cannot overwrite or inject Vietnam state")
        curated = [item for item in curated if item["desk"] == "vietnam"] + independently_validated
    # Assert the pinned curated MPS history really belongs to the same
    # immutable branch. An unrelated valid-looking SHA is not evidence.
    for item in curated:
        if item["desk"] == "vietnam":
            old = formal.verify_state_commit(
                state_repo, item["state_commit"], STATE_BRANCH)
            require(old["state_ref_tip"] == state_commit,
                    "curated Vietnam SHA not reachable from current remote state")
    with tempfile.TemporaryDirectory(prefix="ipr-vn-sunday-source-") as tmp:
        state = formal.export_state_tree(
            state_repo, state_commit, Path(tmp) / "state")
        reviewed = ministry.review(state, SOURCE)
        queue = compile_queue(
            reviewed, state_commit, provenance["state_tree"])
        packet, stats = assemble(queue, curated, state_commit, week_ending)
    # Validate the EXACT packet with the ordinary model-scope contract, then
    # write it atomically outside repo checkout; no source article body copied.
    with tempfile.TemporaryDirectory(prefix="ipr-vn-model-packet-") as tmp:
        validation_dir = Path(tmp)
        validation_path = validation_dir / (week_ending + ".json")
        encoded = json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        validation_path.write_text(encoded, encoding="utf-8")
        validated = load_editorial_evidence(
            week_ending, week_ending, directory=validation_dir)
        require(len(validated) == len(packet["items"]),
                "combined research packet failed exact-week schema")
    out.parent.mkdir(parents=True, exist_ok=True)
    require(not out.exists(), "private output already exists")
    out.write_text(encoded, encoding="utf-8")
    return dict(stats, source_commit=state_commit, state_tree=provenance["state_tree"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state-repo", type=Path, required=True)
    ap.add_argument("--state-commit", required=True)
    ap.add_argument("--week-ending", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--curated-dir", type=Path)
    ap.add_argument("--japan-packet", type=Path,
                    help="optional independently source-validated exact-week Japan JSON")
    args = ap.parse_args(argv)
    try:
        summary = prepare(args.state_repo, args.state_commit,
                          args.week_ending, args.out,
                          curated_dir=args.curated_dir,
                          japan_packet=args.japan_packet)
    except (VietnamFeedRefused, ValueError, OSError, formal.ReviewError) as exc:
        print("Vietnam Sunday research refused: " + str(exc), file=sys.stderr)
        return 2
    # Only counts and pinned source commit; no article prose in public logs.
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
