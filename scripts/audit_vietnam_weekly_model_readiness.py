"""Audit Vietnam shadow-to-model readiness without assuming government silence.

A valid archived MPS article may be omitted from the Sunday AI draft because
its source-specific research synopsis is missing or pins an obsolete digest.
Report that omission explicitly; never invent claims, license article bodies,
promote the desk to production, or send email.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path

from scripts.prepare_vietnam_briefs_evidence import (
    SOURCE, VietnamFeederError, canonical_json, load,
    make_packet, verified_queue, window,
)

NOTE_SCHEMA = "vietnam-editorial-notes/1"
NOTE_FIELDS = {"source_identity", "source_url", "published_date",
               "content_sha256", "summary", "caveats", "topics"}
IDENTITY = re.compile(r"mps-vi:[1-9][0-9]{9}\Z")
MAX_ROWS = 500


def require(ok, explanation):
    if not ok:
        raise VietnamFeederError(explanation)


def parse_notes(data):
    require(isinstance(data, dict) and set(data) == {"schema", "entries"}
            and data["schema"] == NOTE_SCHEMA
            and isinstance(data["entries"], list)
            and len(data["entries"]) <= 20, "invalid version-bound note catalog")
    indexed = {}
    for row in data["entries"]:
        require(isinstance(row, dict) and set(row) == NOTE_FIELDS,
                "invalid note fields")
        identity = row["source_identity"]
        require(isinstance(identity, str) and IDENTITY.fullmatch(identity)
                and identity not in indexed, "malformed or duplicate note identity")
        indexed[identity] = row
    return indexed


def audit(queue, notes, week_ending, *, existing=None):
    saturday = window(week_ending)
    start = saturday - timedelta(days=6)
    rows = verified_queue(queue)
    require(len(rows) <= MAX_ROWS, "unexpectedly large MPS inventory")
    indexed = parse_notes(notes)
    seen, selected = set(), []
    metrics = dict(in_window_machine_eligible=0, ready_private_model=0,
                   awaiting_source_specific_synopsis=0,
                   stale_source_version_synopsis=0,
                   machine_held_in_window=0, blocked_source_with_synopsis=0,
                   out_of_window_observations=0, unused_synopses=0,
                   source_quota_excluded=0)
    for row in rows:
        require(isinstance(row, dict) and row.get("source_slug") == SOURCE,
                "foreign source row in MPS review queue")
        ident, published = row.get("source_identity"), row.get("published_date")
        require(isinstance(ident, str) and IDENTITY.fullmatch(ident)
                and ident not in seen, "invalid or duplicate MPS source identity")
        seen.add(ident)
        require(isinstance(published, str), "missing publication date")
        try:
            published_date = date.fromisoformat(published)
        except ValueError as exc:
            raise VietnamFeederError("bad publication calendar date") from exc
        require(published_date.isoformat() == published,
                "noncanonical publication date")
        if not start <= published_date <= saturday:
            metrics["out_of_window_observations"] += 1
            continue
        eligible = row.get("machine_review_candidate")
        blockers = row.get("machine_blockers")
        require(type(eligible) is bool and isinstance(blockers, list) and
                all(isinstance(b, str) for b in blockers),
                "invalid MPS review eligibility fields")
        note = indexed.get(ident)
        if not eligible or blockers:
            metrics["machine_held_in_window"] += 1
            if note is not None:
                metrics["blocked_source_with_synopsis"] += 1
            continue
        metrics["in_window_machine_eligible"] += 1
        if note is None:
            metrics["awaiting_source_specific_synopsis"] += 1
        elif (note["content_sha256"] != row.get("content_sha256")
              or note["source_url"] != row.get("canonical_url")
              or note["published_date"] != published):
            metrics["stale_source_version_synopsis"] += 1
        else:
            selected.append(note)
    metrics["unused_synopses"] = len(set(indexed) - seen)
    filtered_notes = {"schema": NOTE_SCHEMA, "entries": selected}
    # The normal contributor's stricter publisher/schema/identity validator
    # is authoritative for deciding which records reach the model.
    packet = make_packet(queue, filtered_notes, week_ending, previous=existing)
    ready = sum(x["desk"] == "vietnam" for x in packet["items"])
    metrics["ready_private_model"] = ready
    metrics["source_quota_excluded"] = max(0, len(selected) - ready)
    if ready and (metrics["awaiting_source_specific_synopsis"] or
                  metrics["stale_source_version_synopsis"] or
                  metrics["machine_held_in_window"] or
                  metrics["source_quota_excluded"]):
        status = "partial"
    elif ready:
        status = "ready"
    elif metrics["in_window_machine_eligible"]:
        status = "synopsis-gap"
    else:
        status = "no-eligible-in-window"
    return {
        "schema": "vietnam-weekly-private-model-readiness/1",
        "week_ending": week_ending,
        "shadow_state_commit": queue["state_commit"],
        "shadow_state_tree": queue["state_tree"],
        "status": status,
        "source_family": SOURCE,
        "counts": metrics,
        "non_vietnam_sources_preserved": sum(
            x["desk"] != "vietnam" for x in packet["items"]),
        "never_infer_official_silence": True,
        "complete_reporting_week_capture_verified": False,
        "latest_run_covers_reporting_saturday": None,
        "publication_approval": False,
        "desk_qualified": False,
        "editorial_email_sent": False,
    }, packet


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--week-ending", required=True)
    parser.add_argument("--notes", type=Path)
    parser.add_argument("--existing-packet", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)
    current = load(args.queue, 100000)
    authored = (load(args.notes, 30000) if args.notes else
                {"schema": NOTE_SCHEMA, "entries": []})
    previous = load(args.existing_packet, 50000) if args.existing_packet else None
    report, _ = audit(current, authored, args.week_ending, existing=previous)
    if args.out:
        root = Path(__file__).resolve().parents[1].resolve()
        path = args.out
        resolved = path.resolve()
        require(not path.exists() and not path.is_symlink()
                and path.parent.is_dir() and not path.parent.is_symlink()
                and resolved != root and root not in resolved.parents,
                "refusing readiness output inside tracked repository")
        path.write_text(canonical_json(report), encoding="utf-8")
    # Only counts, not source text or URLs, go to runner logs.
    print(json.dumps({
        "week_ending": report["week_ending"],
        "status": report["status"],
        "counts": report["counts"],
        "official_silence_verified": False,
        "complete_reporting_week_capture_verified": False,
        "production_desk_promoted": False,
    }, sort_keys=True))
    if args.require_ready and not report["counts"]["ready_private_model"]:
        raise SystemExit("REFUSED: no current private Vietnam evidence for this week")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
