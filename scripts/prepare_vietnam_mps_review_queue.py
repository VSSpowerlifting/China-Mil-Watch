#!/usr/bin/env python3
"""Export an *unsigned* MPS pilot review queue from one verified shadow commit.

This is metadata-only preparation for the separately human-approved,
disposable-DB path in scripts/prepare_vietnam_mps_pilot.py. It does not
approve records, decide source-use rights, store article bodies, ingest,
alter any record, or advance Vietnam's reliability clock.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.collection.vietnam_sources import SOURCES
from scripts import prepare_vietnam_mps_pilot as pilot
from scripts import review_vietnam_ministry_state as ministry
from scripts import review_vietnam_shadow_state as formal

QUEUE_SCHEMA = "vietnam-mps-pilot-review-queue/1"
FILES = ("review_queue.json", "approval_template.json", "REVIEW.md")


def require(condition, reason):
    if not condition:
        raise pilot.Refused(reason)


def _json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def compile_queue(evidence, commit, state_tree):
    """Full machine inventory; *review candidate* is not editorial approval."""
    require(evidence.get("source_slug") == pilot.PILOT_SOURCE,
            "only the MPS foreign-affairs source may enter this queue")
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None
            and re.fullmatch(r"[0-9a-f]{40}", state_tree) is not None,
            "exact commit/tree identities are required")
    require(evidence.get("clock") and evidence.get("successes", 0) > 0,
            "no successful, durable remote clock")
    runs = evidence.get("runs") or []
    require(runs and runs[-1].get("health") == "ok", "latest stored run is not healthy")
    versions = {(v["source_identity"], v["content_sha256"]): v
                for v in evidence["versions"]}
    observations = {}
    for o in evidence["observations"]:
        observations.setdefault(o["source_identity"], []).append(o)
    rows = []
    for record in evidence["records"]:
        identity = record["source_identity"]
        url = record["url"]
        digest = record["current_content_sha256"]
        version = versions.get((identity, digest))
        reasons = []
        if (record["source_slug"] != pilot.PILOT_SOURCE
                or record["canonical_url"] != url
                or SOURCES[pilot.PILOT_SOURCE].identity(url) != identity):
            reasons.append("foreign_or_noncanonical_identity")
        if version is None:
            reasons.append("current_content_version_missing")
        elif version["body_status"] != "text" or not version["text_original"].strip():
            reasons.append("body_not_complete_text")
        observed = observations.get(identity, [])
        for o in observed:
            if json.loads(o["anomalies_json"]):
                reasons.append("unresolved_observation_anomaly")
                break
        first = None
        if version is not None:
            first = next((o for o in observed
                          if o["run_id"] == version["first_seen_run"]
                          and o["content_sha256"] == digest
                          and o["capture_sha256"] == version["first_capture_sha256"]), None)
            if first is None:
                reasons.append("current_version_capture_unverified")
        row = {
            "source_slug": pilot.PILOT_SOURCE,
            "source_identity": identity,
            "canonical_url": url,
            "published_date": record["published_date"],
            "published_at_original": record.get("published_at_original"),
            "title_original": version["title_original"] if version else None,
            "content_sha256": digest,
            "first_capture_sha256": version["first_capture_sha256"] if version else None,
            "first_seen_run": version["first_seen_run"] if version else None,
            "last_seen_run": record.get("last_seen_run"),
            "body_status": version["body_status"] if version else None,
            "body_character_count": len(version["text_original"]) if version else None,
            "version_count": record.get("version_count"),
            "observation_count": len(observed),
            "machine_review_candidate": not reasons,
            "machine_blockers": sorted(set(reasons)),
            "human_source_reviewed": False,
            "reuse_rights_reviewed": False,
            "production_publication_authorized": False,
        }
        rows.append(row)
    rows.sort(key=lambda r: (r["published_date"], r["canonical_url"]), reverse=True)
    require(len({r["source_identity"] for r in rows}) == len(rows),
            "duplicate record identity in queue")
    eligible = sum(x["machine_review_candidate"] for x in rows)
    queue = {
        "schema": QUEUE_SCHEMA,
        "source_slug": pilot.PILOT_SOURCE,
        "source_family": "Ministry of Public Security — Thông tin Đối ngoại",
        "state_branch": SOURCES[pilot.PILOT_SOURCE].state_branch,
        "state_commit": commit,
        "state_tree": state_tree,
        "day_zero_utc": evidence["clock"]["day_zero_utc"],
        "run_count": len(runs),
        "successful_run_count": evidence["successes"],
        "record_count": len(rows),
        "machine_review_candidate_count": eligible,
        "machine_hold_count": len(rows) - eligible,
        "human_approvals": 0,
        "rights_approvals": 0,
        "automatic_production_admission": False,
        "full_desk_qualification": False,
        "original_article_bodies_in_packet": False,
        "records": rows,
    }
    queue["queue_sha256"] = hashlib.sha256(_json(queue).encode("utf-8")).hexdigest()
    return queue


def unsigned_template(queue):
    """A deliberately unusable approval until a human selects and signs rows."""
    return {
        "schema": pilot.SCHEMA,
        "source_slug": pilot.PILOT_SOURCE,
        "state_commit": queue["state_commit"],
        "reviewer": None,
        "reviewed_at_utc": None,
        "records": [],
        "_instructions": (
            "UNSIGNED. A human must verify each source page and full body, "
            "explicitly approve reproduction/retention rights and add 1–10 "
            "current-version records with every required check true. "
            "Do not bulk-copy queue rows or infer authorization."
        ),
        "_record_shape": {
            "source_identity": None,
            "content_sha256": None,
            "checks": {key: None for key in pilot.CHECKS},
            "reuse_approved": None,
            "rights_basis": None,
        },
    }


def review_markdown(queue):
    out = [
        "# Vietnam MPS — unsigned accelerated-pilot review queue",
        "",
        "This document reports machine-verifiable candidates only. "
        "No article is approved, no copyright/reuse rights are established, "
        "and Vietnam is not admitted to production.",
        "",
        f"Source: \`{queue['source_slug']}\` (Vietnamese ministry foreign-affairs reports).",
        f"State branch: \`{queue['state_branch']}\`.",
        f"Pinned commit: \`{queue['state_commit']}\`.",
        f"Pinned tree: \`{queue['state_tree']}\`.",
        f"Day zero: \`{queue['day_zero_utc']}\`.",
        f"Machine candidates: {queue['machine_review_candidate_count']} / "
        f"{queue['record_count']}; machine holds: {queue['machine_hold_count']}.",
        f"Queue hash: \`{queue['queue_sha256']}\`.",
        "",
        "For each candidate, independently open the original ministry URL, "
        "compare complete Vietnamese title, body and visible date, check "
        "the issuing institution and challenge/template status, "
        "and document an actual reuse/retention rights basis. "
        "The first capture SHA and current content SHA bind the review "
        "to a particular observed version. Do not approve a changed record "
        "using an old commit.",
        "",
    ]
    for row in queue["records"]:
        out.extend([
            f"## {row['source_identity']} — "
            f"{'MACHINE CANDIDATE' if row['machine_review_candidate'] else 'HOLD'}",
            "",
            f"- Source: {row['canonical_url']}",
            f"- Published date (source-stated): {row['published_date']}",
            f"- Source title: {row['title_original'] or '(unavailable)'}",
            f"- Current SHA-256: \`{row['content_sha256']}\`",
            f"- First raw capture SHA-256: "
            f"\`{row['first_capture_sha256'] or 'UNAVAILABLE'}\`",
            f"- First run: \`{row['first_seen_run'] or 'UNAVAILABLE'}\`",
            f"- Body state: {row['body_status'] or 'UNAVAILABLE'}; "
            f"characters: {row['body_character_count']}",
            f"- Machine blockers: {', '.join(row['machine_blockers']) or 'none'}",
            "- Human checks: **NOT REVIEWED**; reuse rights: **NOT APPROVED**",
            "",
        ])
    out.extend([
        "## Next gate",
        "",
        "The empty \`approval_template.json\` cannot pass the existing "
        "\`scripts/prepare_vietnam_mps_pilot.py\` approval validator. "
        "A reviewer must select at most ten source-verifiable records, "
        "name themselves, supply a UTC signoff and complete the per-record "
        "integrity and rights decisions. Even a valid authorization "
        "permits **disposable staging only**, never a live production write.",
        "",
    ])
    return "\n".join(out)


def prepare(state_repo, state_commit, out_dir):
    """Read-only Git export and review. Create output only after checks pass."""
    require(re.fullmatch(r"[0-9a-f]{40}", state_commit) is not None,
            "full state SHA required")
    folder = Path(out_dir)
    require(not folder.is_symlink(), "output symlink refused")
    target = folder.resolve()
    require(target != ROOT and ROOT not in target.parents,
            "review files cannot be written inside a repository checkout")
    require(not folder.exists(), "output directory must not already exist")
    repo = formal.resolve_state_repo(state_repo)
    profile = SOURCES[pilot.PILOT_SOURCE]
    provenance = formal.verify_state_commit(repo, state_commit, profile.state_branch)
    with tempfile.TemporaryDirectory(prefix="vn-mps-queue-") as temp:
        state = formal.export_state_tree(repo, state_commit, Path(temp) / "state")
        evidence = ministry.review(state, pilot.PILOT_SOURCE)
        queue = compile_queue(evidence, state_commit, provenance["state_tree"])
    template = unsigned_template(queue)
    require(template["reviewer"] is None and not template["records"],
            "generated template must be unsigned")
    markdown = review_markdown(queue)
    target.mkdir(parents=True, exist_ok=False)
    (target / FILES[0]).write_text(_json(queue), encoding="utf-8")
    (target / FILES[1]).write_text(_json(template), encoding="utf-8")
    (target / FILES[2]).write_text(markdown, encoding="utf-8")
    return {key: queue[key] for key in ("source_slug", "state_commit", "state_tree",
                                       "record_count", "machine_review_candidate_count",
                                       "machine_hold_count", "queue_sha256")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-repo", type=Path, required=True)
    ap.add_argument("--state-commit", required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        print(_json(prepare(args.state_repo, args.state_commit, args.out_dir)), end="")
        return 0
    except (pilot.Refused, ValueError, OSError, formal.ReviewError) as exc:
        print("MPS review queue refused: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
