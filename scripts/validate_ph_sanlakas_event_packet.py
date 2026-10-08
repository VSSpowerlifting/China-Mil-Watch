"""Validate provisional, source-bound AFP event candidates without publication.

The two proposed event IDs are editorial *hypotheses*, not gold labels.
Pinned originals are checked only when the caller explicitly executes CLI
against a local Git checkout containing the historical shadow commit.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_ph_afp_day0_review import (  # noqa: E402
    AFPReviewError,
    SNAPSHOT_BLOBS,
    STATE_COMMIT,
    git_objects,
    make_queue_from_objects,
)

PACKET = ROOT / "research/philippines/sanlakas_2026/source_event_candidates.json"
SOURCE_BY_EVENT = {
    "sanlakas_exercise": ("afp:1391", "afp:1393", "afp:1394"),
    "jpscc_meeting": ("afp:1390",),
}
EVENT_META = {
    "sanlakas_exercise": (
        "ph-2026-iax-02-pagsasanay-sanlakas", "2026-09-30", "2026-10-02",
        ("S03", "S04", "S05"),
    ),
    "jpscc_meeting": (
        "ph-2026-09-29-jpscc-sixth-meeting", "2026-09-29", "2026-09-29",
        ("J01",),
    ),
}
CLAIM_ORIGIN = {
    "S01": ("sanlakas_exercise", "afp:1394"),
    "S02": ("sanlakas_exercise", "afp:1394"),
    "S03": ("sanlakas_exercise", "afp:1391"),
    "S04": ("sanlakas_exercise", "afp:1393"),
    "S05": ("sanlakas_exercise", "afp:1394"),
    "S06": ("sanlakas_exercise", "afp:1394"),
    "S07": ("sanlakas_exercise", "afp:1394"),
    "S08": ("sanlakas_exercise", "afp:1394"),
    "J01": ("jpscc_meeting", "afp:1390"),
    "J02": ("jpscc_meeting", "afp:1390"),
    "J03": ("jpscc_meeting", "afp:1390"),
}
FLAGS = frozenset(("F01", "F02", "F03", "F04", "F05"))
LOCKED_FALSE = (
    "publisher_reuse_review_complete",
    "human_source_review_complete",
    "event_grouping_approved",
    "entity_resolution_approved",
    "topic_classification_approved",
    "timeline_publication_approved",
    "production_writes_authorized",
)
EXPECTED_RECORDS = frozenset(id_ for xs in SOURCE_BY_EVENT.values() for id_ in xs)
SOURCE_FIELDS = (
    ("title", "title_original"),
    ("source_url", "source_url"),
    ("published_at_original", "published_at_original"),
    ("content_sha256", "text_sha256"),
    ("capture_sha256", "capture_sha256"),
)


class EventReviewError(ValueError):
    """An event packet falsely claims provenance or an unauthorized decision."""


def require(ok, explanation):
    if not ok:
        raise EventReviewError(explanation)


def date_str(value):
    from datetime import date
    require(type(value) is str and re.fullmatch(r"\d{4}-\d\d-\d\d", value),
            "event dates must be YYYY-MM-DD")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise EventReviewError("event date invalid") from exc
    require(d.isoformat() == value, "event date not canonical")
    return d


def review_candidate(data, archived_rows):
    """Validate structure and exact evidence excerpts against archived text.

    Caller must supply genuinely verified pinned archive rows. This function
    is not a human reviewer and does not infer that the claims are true.
    """
    require(type(data) is dict and
            data.get("schema") == "ipr_philippines_provisional_source_event_v1" and
            data.get("status") == "unsigned_research_candidate_requires_human_review",
            "unexpected proposal protocol or review status")
    require(type(data.get("permissions")) is dict and
            set(data["permissions"]) == set(LOCKED_FALSE) and
            all(data["permissions"][key] is False for key in LOCKED_FALSE),
            "candidate cannot authorize publication, review or production")
    arc = data.get("archive")
    require(type(arc) is dict and
            arc.get("state_branch") == "shadow/ph-afp" and
            arc.get("state_commit") == STATE_COMMIT and
            arc.get("state_path") == "state/shadow.db" and
            arc.get("state_db_blob") == SNAPSHOT_BLOBS["state/shadow.db"] and
            arc.get("original_run_id") == "37631681338-1",
            "candidate provenance does not match immutable AFP Day-0")
    require(type(archived_rows) is dict and
            EXPECTED_RECORDS.issubset(archived_rows), "source archive packet incomplete")
    sources = data.get("records")
    require(type(sources) is list and len(sources) == 4,
            "exactly four distinct source articles are required")
    records = {}
    for source in sources:
        require(type(source) is dict, "source entry must be an object")
        ident = source.get("id")
        require(type(ident) is str and ident in EXPECTED_RECORDS and
                ident not in records, "unexpected or repeated AFP source ID")
        records[ident] = source
        expected_group = next(k for k, ids in SOURCE_BY_EVENT.items()
                              if ident in ids)
        require(source.get("group") == expected_group,
                "source cannot be reassigned across the two distinct events")
        original = archived_rows[ident]
        for field, archive_field in SOURCE_FIELDS:
            require(source.get(field) == original.get(archive_field),
                    ident + ": source provenance changed: " + field)
        require(original.get("source_identity") == ident and
                original.get("text_status") == "text" and
                type(original.get("text_original")) is str and
                len(original["text_original"]) > 0,
                ident + ": full pinned original text unavailable")
    require(set(records) == EXPECTED_RECORDS,
            "at least one original source is missing")

    events = data.get("event_candidates")
    require(type(events) is list and len(events) == 2,
            "expected two distinct proposed event candidates")
    found = set()
    for event in events:
        require(type(event) is dict and
                event.get("key") in EVENT_META, "unexpected event candidate")
        key = event["key"]
        require(key not in found, "duplicate event candidate")
        found.add(key)
        expected_id, start, end, stage_ids = EVENT_META[key]
        require(event.get("candidate_event_id") == expected_id and
                event.get("event_date_start") == start and
                event.get("event_date_end") == end and
                event.get("record_ids") == list(SOURCE_BY_EVENT[key]) and
                event.get("stage_claim_ids") == list(stage_ids) and
                event.get("status") == "provisional_source_based_grouping" and
                type(event.get("candidate_kind")) is str and
                bool(event["candidate_kind"].strip()),
                key + ": event grouping/date contract changed")
        require(date_str(start) <= date_str(end), "event chronology inverted")
    require(found == set(EVENT_META), "missing independent event candidate")

    claims = data.get("claims")
    require(type(claims) is list and len(claims) == len(CLAIM_ORIGIN),
            "unexpected number of source-grounded claims")
    found = set()
    for claim in claims:
        require(type(claim) is dict and claim.get("id") in CLAIM_ORIGIN,
                "unknown or missing claim ID")
        ident = claim["id"]
        require(ident not in found, "duplicate claim ID")
        found.add(ident)
        group, source_id = CLAIM_ORIGIN[ident]
        require(claim.get("event_key") == group and
                type(claim.get("statement")) is str and
                bool(claim["statement"].strip()),
                ident + ": ungrounded event claim")
        ev = claim.get("evidence")
        require(type(ev) is list and len(ev) == 1 and
                type(ev[0]) is dict and
                ev[0].get("record_id") == source_id,
                ident + ": claim must cite one correct archived article")
        excerpt = ev[0].get("exact_excerpt")
        require(type(excerpt) is str and len(excerpt) >= 15 and
                excerpt in archived_rows[source_id]["text_original"],
                ident + ": exact original-language excerpt is absent")
    require(found == set(CLAIM_ORIGIN), "claim evidence coverage changed")

    flags = data.get("editorial_review_flags")
    require(type(flags) is list and len(flags) == len(FLAGS) and
            {f.get("id") for f in flags if type(f) is dict} == FLAGS and
            all(type(f) is dict and f.get("status") == "requires_human_review"
                and type(f.get("note")) is str and bool(f["note"].strip())
                for f in flags),
            "editorial caveats must remain open")
    require(data.get("verification_scope") ==
            "offline exact pinned historical source and excerpt substring matches; no independent factual corroboration",
            "scope cannot imply independent corroboration")
    return {
        "source_records_verified_against_pin": len(records),
        "provisional_distinct_event_candidates": len(found) if False else len(events),
        "source_grounded_claim_count": len(claims),
        "all_review_flags_still_pending": True,
        "human_review_complete": False,
        "entity_resolution_approved": False,
        "record_topic_assignments": 0,
        "timeline_publication_approved": False,
        "production_writes": 0,
    }


def load_pinned_archive(repo):
    """Verify all three immutable AFP Day-0 objects with the merged gate."""
    try:
        objects = git_objects(Path(repo), STATE_COMMIT, SNAPSHOT_BLOBS)
        packet = make_queue_from_objects(objects)
    except (AFPReviewError, OSError, TypeError) as exc:
        raise EventReviewError("pinned AFP Day-0 evidence unavailable: " + str(exc)) from exc
    return {r["source_identity"]: r for r in packet["records"]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packet", type=Path, default=PACKET)
    p.add_argument("--state-repo", required=True, type=Path,
                   help="local Git checkout already containing pinned Day-0 shadow objects")
    args = p.parse_args()
    try:
        candidate = json.loads(args.packet.read_text(encoding="utf-8"))
        result = review_candidate(candidate, load_pinned_archive(args.state_repo))
        print(json.dumps(result, indent=2, sort_keys=True))
    except (EventReviewError, ValueError, OSError, TypeError) as exc:
        p.exit(1, "Philippines Sanlakas event evidence: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
