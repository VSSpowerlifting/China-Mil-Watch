"""Offline, read-only three-source Vietnam ministry checkpoint packet rollup.

Input: three *already generated*, pinned, per-source formal review packets.
No Git/network calls, publisher requests, state mutation, publication or
human sign-off. Rechecks packet-file hashes, internal deterministic digest,
source branch identity, checkpoint alignment and claimed day thresholds.
A clean mechanical packet is NOT an approved review or reliable desk.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

from scripts.review_vietnam_ministry_state import package_sha256
from scripts.shadow_collect_vietnam_ministry import load_source
from core.collection.vietnam_sources import SOURCES
from scripts.review_vietnam_shadow_state import CHECKPOINTS, SIGNOFF_SCHEMA, QUEUE_ALGORITHM

SOURCE_SET = frozenset(SOURCES)
ARTIFACT_FILES = frozenset((
    "record_inventory.jsonl", "run_inventory.jsonl", "corpus_evidence.json",
    "signoff_template.json", "review_report.md",
))
CORE_FILES = ("record_inventory.jsonl", "run_inventory.jsonl", "corpus_evidence.json")
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
HEX64 = re.compile(r"[a-f0-9]{64}\Z")
MAX_FILE_BYTES = 8_000_000
MAX_CLOCK_SKEW_SECONDS = 5 * 60


class RollupRefused(ValueError):
    """Packet file, identity, or checkpoint evidence is ambiguous."""


def require(condition, explanation):
    if not condition:
        raise RollupRefused(explanation)


def strict_json(text):
    def unique(pairs):
        value = {}
        for key, val in pairs:
            if key in value:
                raise RollupRefused("duplicate JSON field")
            value[key] = val
        return value
    return json.loads(text, object_pairs_hook=unique)


def read_file(path):
    require(path.is_file() and not path.is_symlink(), "missing or linked packet file")
    require(path.stat().st_size <= MAX_FILE_BYTES, "packet file exceeds bound")
    return path.read_bytes()


def read_packet(directory):
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), "packet directory missing or symlinked")
    files = {p.name for p in directory.iterdir() if p.is_file() and not p.is_symlink()}
    require(files == ARTIFACT_FILES | {"review_manifest.json"},
            "packet must contain exact five source artifacts and review_manifest.json; "
            "signoff is separately reviewed")
    require(all(p.is_file() and not p.is_symlink() for p in directory.iterdir()),
            "unapproved file, folder or symlink in packet")

    blob = read_file(directory / "review_manifest.json")
    manifest = strict_json(blob.decode("utf-8"))
    require(isinstance(manifest, dict), "review manifest is not an object")
    source = manifest.get("source_slug")
    require(source in SOURCE_SET, "unexpected ministry source")
    require(manifest.get("tool") == "scripts/review_vietnam_ministry_state.py"
            and manifest.get("tool_version") == "2.0.0"
            and manifest.get("signoff_schema") == SIGNOFF_SCHEMA
            and manifest.get("queue_algorithm") == QUEUE_ALGORITHM
            and manifest.get("desk") == "vietnam"
            and manifest.get("formal") is True
            and manifest.get("provenance") == "git-verified-tree/1",
            "not a formal ministry checkpoint packet")
    require(manifest.get("language") == "vi"
            and manifest.get("state_branch") == load_source(source).state_branch,
            "source or state branch mismatch")
    require(all(isinstance(manifest.get(k), str) and HEX40.fullmatch(manifest[k])
                for k in ("state_commit", "state_tree", "latest_collector_commit")),
            "unbound state or collector commit")
    require(manifest.get("checkpoint") in CHECKPOINTS, "unknown checkpoint")
    try:
        as_of = date.fromisoformat(manifest["as_of"])
        day_zero = datetime.fromisoformat(manifest["day_zero_utc"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RollupRefused("bad checkpoint/Day 0 dates") from exc
    require(as_of.isoformat() == manifest["as_of"], "noncanonical as-of date")
    require(day_zero.tzinfo is not None and day_zero.utcoffset() == timedelta(0),
            "Day 0 must be explicitly UTC")
    day = manifest.get("latest_shadow_day")
    require(type(day) is int and day >= 0, "missing or invalid elapsed shadow day")
    require(type(manifest.get("checkpoint_reached")) is bool
            and manifest["checkpoint_reached"] == (day >= CHECKPOINTS[manifest["checkpoint"]]),
            "checkpoint threshold flag inconsistent with elapsed shadow days")
    require(manifest.get("qualification") is None and manifest.get("owner_signoff") is None,
            "machine packet may not embed qualification or owner approval")
    require(type(manifest.get("required_collecting_days")) is int
            and manifest["required_collecting_days"] == 30,
            "wrong minimum consecutive collecting-day requirement")
    for key in ("collecting_days", "missing_collecting_days", "consecutive_collecting_days",
                "window_coverage", "uncovered_dates", "anomalies", "required_review_records"):
        require(isinstance(manifest.get(key), list), "missing full machine evidence: " + key)
    require(isinstance(manifest.get("input_sha256"), dict)
            and HEX64.fullmatch(manifest["input_sha256"].get("shadow.db", "")) is not None,
            "absent shadow database evidence digest")

    sha_map = manifest.get("artifact_sha256")
    require(isinstance(sha_map, dict) and set(sha_map) == ARTIFACT_FILES,
            "incomplete source artifact inventory")
    data = {}
    for name in sorted(ARTIFACT_FILES):
        payload = read_file(directory / name)
        actual = hashlib.sha256(payload).hexdigest()
        require(sha_map[name] == actual, "packet artifact digest mismatch: " + name)
        data[name] = payload.decode("utf-8")
    digest = manifest.get("deterministic_sha256")
    require(isinstance(digest, str) and HEX64.fullmatch(digest), "invalid packet identity")
    require(package_sha256(manifest, {name: data[name] for name in CORE_FILES}) == digest,
            "deterministic packet identity mismatch")
    return {
        "source_slug": source,
        "state_branch": manifest["state_branch"],
        "state_commit": manifest["state_commit"],
        "state_tree": manifest["state_tree"],
        "manifest_sha256": hashlib.sha256(blob).hexdigest(),
        "packet_sha256": digest,
        "checkpoint": manifest["checkpoint"],
        "as_of": manifest["as_of"],
        "day_zero_utc": day_zero.isoformat(),
        "latest_shadow_day": day,
        "checkpoint_reached": manifest["checkpoint_reached"],
        "collecting_days_count": len(manifest["collecting_days"]),
        "missing_collecting_days_count": len(manifest["missing_collecting_days"]),
        "consecutive_collecting_days_count": len(manifest["consecutive_collecting_days"]),
        "uncovered_date_count": len(manifest["uncovered_dates"]),
        "anomaly_count": len(manifest["anomalies"]),
        "required_review_record_count": len(manifest["required_review_records"]),
        "human_signoff_complete": False,
        "production_promotion_authorized": False,
    }


def rollup(directories):
    require(isinstance(directories, (list, tuple)) and len(directories) == len(SOURCE_SET),
            "exactly three independent source packet directories required")
    packets = [read_packet(p) for p in directories]
    indexed = {x["source_slug"]: x for x in packets}
    require(len(indexed) == len(packets) and set(indexed) == SOURCE_SET,
            "missing or duplicate ministry source packet")
    require(len({(x["checkpoint"], x["as_of"]) for x in packets}) == 1,
            "mixed checkpoint or as-of date")
    # The three clocks were established within a single successful serial
    # activation batch, seconds apart. Reject borrowed/restarted clock.
    clock_times = [datetime.fromisoformat(x["day_zero_utc"]) for x in packets]
    require((max(clock_times) - min(clock_times)).total_seconds() <= MAX_CLOCK_SKEW_SECONDS,
            "source Day 0 clocks do not form one verified activation batch")
    ordered = [indexed[k] for k in sorted(SOURCE_SET)]
    reached = all(x["checkpoint_reached"] for x in ordered)
    warnings = []
    for p in ordered:
        slug = p["source_slug"]
        if not p["checkpoint_reached"]:
            warnings.append({"source_slug": slug, "kind": "checkpoint_not_reached"})
        for field, kind in (("missing_collecting_days_count", "missing_collecting_days"),
                            ("uncovered_date_count", "uncovered_publication_window"),
                            ("anomaly_count", "unresolved_machine_anomaly")):
            if p[field]:
                warnings.append({"source_slug": slug, "kind": kind, "count": p[field]})
    return {
        "schema": "ipr-vietnam-three-source-checkpoint-rollup/1",
        "desk_id": "vietnam",
        "checkpoint": ordered[0]["checkpoint"],
        "as_of": ordered[0]["as_of"],
        "all_three_machine_checkpoints_reached": reached,
        "all_three_review_packets_integrity_checked": True,
        "source_count": len(ordered),
        "sources": ordered,
        "machine_warnings": warnings,
        "requires_human_complete_corpus_review": True,
        "human_signoff_complete": False,
        "rights_to_publicly_republish_established": False,
        "production_promotion_authorized": False,
        "desk_qualified": False,
        "note": (
            "Read-only reconciliation of three commit-bound per-source packets. "
            "Packet hashes alone do not reverify Git ancestry or independently "
            "review source articles. Failed Actions attempts may be absent from "
            "successful-state branches: obtain separate attempt artifacts. "
            "Checkpoint reached means machine time threshold only, not human "
            "signoff or 30-day consecutive reliability."
        ),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("packets", nargs=3, help="three already generated formal ministry packet directories")
    args = ap.parse_args(argv)
    print(json.dumps(rollup(args.packets), indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
