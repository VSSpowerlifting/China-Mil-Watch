"""Read-only Korean government-republication research feeder for the Sunday writer.

The output contains metadata-only discoveries, never translated Korean source
bodies, source-derived event summaries, production records or human approvals.
It adds to the *one* regional research pool created by Vietnam/Japan feeder.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core.brief_editorial_evidence import (
    COPY_SCOPE, MAX_ITEMS, SCHEMA, STATUS, load_editorial_evidence,
    metadata_only_summary,
)
from scripts import review_desk_shadow as formal

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "shadow/korea-policy-briefing"
KOREA_ID = re.compile(r"korea-policy:([0-9]{6,20})\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
MAX_KOREA = 3
CAUTIONS = [
    "This is a Ministry of National Defense-labeled republication on Korea Policy Briefing, not a directly retrieved ministry publication.",
    "The HWPX original and machine extraction have not received independent language-qualified human review; do not infer events or policy from the headline.",
]


class KoreaFeedRefused(ValueError):
    """The input is not safely usable in the private weekly drafting pool."""


def require(ok, message):
    if not ok:
        raise KoreaFeedRefused(message)


def day(value):
    require(isinstance(value, str), "calendar date required")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise KoreaFeedRefused("invalid date") from exc
    require(parsed.isoformat() == value, "noncanonical date")
    return parsed


def week_range(week_ending):
    saturday = day(week_ending)
    require(saturday.weekday() == 5, "week must end Saturday")
    return saturday - timedelta(days=6), saturday


def git(repo, *argv):
    return subprocess.check_output(["git", "-C", str(repo), *argv], stderr=subprocess.PIPE).decode().strip()


def metadata_card(record, state_commit):
    """The verified portal metadata is all the model may see automatically."""
    source_identity = record.get("source_identity")
    match = KOREA_ID.fullmatch(source_identity) if isinstance(source_identity, str) else None
    require(match is not None, "unexpected Korea republication identity")
    require(record.get("source_slug") == "kr_policy_mnd_releases"
            and record.get("language_tag") == "ko"
            and isinstance(record.get("metadata"), dict)
            and record["metadata"].get("issuer") == "국방부",
            "not an MND-labeled Korean government republication")
    url = "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + match.group(1)
    require(record.get("url") == url, "URL and Korean source identity differ")
    require(isinstance(record.get("content_sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", record["content_sha256"]),
            "missing Korean original-text hash")
    return {
        "id": "KR-PB-" + match.group(1),
        "desk": "korea",
        "source_name": "Korea Policy Briefing (MND-labeled republication)",
        "source_url": url,
        "published_date": record["published_date"],
        "language": "ko",
        "title_original": record["title_original"],
        "source_kind": "shadow-metadata-only",
        "state_commit": state_commit,
        "source_content_sha256": record["content_sha256"],
        "hash_rule": "sha256-text-original-utf8",
        "summary": metadata_only_summary(record["published_date"], desk="korea"),
        "caveats": list(CAUTIONS),
        "topics": ["source_discovery"],
        "status": STATUS,
        "copy_scope": COPY_SCOPE,
    }


def assemble(records, existing, state_commit, week_ending):
    start, cutoff = week_range(week_ending)
    require(all(row["desk"] in ("japan", "vietnam") for row in existing),
            "Korea may only extend an independently validated Japan/Vietnam input")
    candidates = []
    for record in records:
        published = day(record.get("published_date"))
        if start <= published <= cutoff:
            candidates.append(metadata_card(record, state_commit))
    candidates.sort(key=lambda x: (x["published_date"], x["id"]), reverse=True)
    selected = candidates[:min(MAX_KOREA, MAX_ITEMS - len(existing))]
    result = {"schema": SCHEMA, "week_ending": week_ending, "status": STATUS,
              "items": list(existing) + selected}
    return result, {"korea_in_window": len(candidates), "korea_in_model_pool": len(selected),
                    "korea_metadata_only": len(selected), "korea_factual_synopses": 0,
                    "production_records_admitted": 0, "human_approvals_granted": 0}


def prepare(state_repo, state_commit, week_ending, input_path, out_path, *,
            observed_on=None):
    """Use only the newest pinned isolated state and fresh healthy daily run."""
    start, saturday = week_range(week_ending)
    if observed_on is None:
        observed_on = datetime.now(timezone.utc).date()
    require(type(observed_on) is date, "observed_on must be a date")
    require(isinstance(state_commit, str) and SHA.fullmatch(state_commit),
            "literal forty-character state commit required")
    state_repo = Path(state_repo).resolve()
    require(state_repo.is_dir() and not state_repo.is_symlink(),
            "state repo missing or symlinked")
    require(git(state_repo, "rev-parse", "--verify", "refs/heads/" + BRANCH) == state_commit,
            "Korean snapshot must equal current branch tip")
    require(git(state_repo, "ls-tree", "--name-only", state_commit) == "state",
            "Korean state branch contains non-state files")
    input_path, out_path = Path(input_path), Path(out_path)
    require(input_path.name == week_ending + ".json" and input_path.is_file()
            and not input_path.is_symlink(), "validated regional research input missing")
    require(out_path.name == week_ending + ".json" and not out_path.is_symlink()
            and not out_path.exists(), "new exact-week output path required")
    require(not out_path.parent.is_symlink(), "output parent is symlinked")
    resolved = out_path.resolve()
    require(resolved != ROOT and ROOT not in resolved.parents,
            "private Korea research output must remain outside production checkout")
    require(resolved != input_path.resolve(), "input evidence cannot be overwritten")
    existing = load_editorial_evidence(week_ending, week_ending, directory=input_path.parent)
    with tempfile.TemporaryDirectory(prefix="ipr-kr-shadow-review-") as tmp:
        temporary = Path(tmp)
        tree = formal.export_commit(state_repo, state_commit, "korea", temporary)
        review_dir = temporary / "review"
        report = formal.review(temporary / "state", "korea", review_dir, observed_on,
                               commit=state_commit, tree=tree)
        require(not report["findings"] and not report["missing_successful_days"]
                and report["mode"] == "formal_commit_snapshot"
                and report["human_review_completed"] is False
                and report["promotion_authorized"] is False,
                "Korean pinned state has unresolved machine findings or missing days")
        ledgers = [json.loads(p.read_text(encoding="utf-8"))
                   for p in sorted((temporary / "state" / "ledger").glob("*.json"))]
        require(bool(ledgers), "Korean state has no attempt history")
        require(all(row.get("health") == "ok" for row in ledgers),
                "a Korean shadow attempt was unsuccessful")
        targets = sorted(day(row["target_date"]) for row in ledgers)
        last_target = targets[-1]
        require(max(start, observed_on - timedelta(days=1)) <= last_target
                <= min(observed_on, saturday + timedelta(days=1)),
                "Korean source state is stale, from another week or future dated")
        require(report["records"] > 0, "Korean archive is empty")
        records = [json.loads(line) for line in
                   (review_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()]
        require(len(records) == report["records"], "review record count mismatch")
        packet, stats = assemble(records, existing, state_commit, week_ending)
        with tempfile.TemporaryDirectory(prefix="ipr-kr-validate-") as test_dir:
            validation = Path(test_dir) / (week_ending + ".json")
            encoded = json.dumps(packet, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
            validation.write_text(encoded, encoding="utf-8")
            checked = load_editorial_evidence(week_ending, week_ending,
                                               directory=validation.parent)
            require(len(checked) == len(packet["items"]),
                    "combined Korea research packet failed schema validation")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    require(not out_path.exists(), "output already exists")
    out_path.write_text(encoded, encoding="utf-8")
    return dict(stats, state_commit=state_commit, state_tree=tree,
                latest_healthy_target=last_target.isoformat())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state-repo", type=Path, required=True)
    ap.add_argument("--state-commit", required=True)
    ap.add_argument("--week-ending", required=True)
    ap.add_argument("--input-packet", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        result = prepare(args.state_repo, args.state_commit, args.week_ending,
                         args.input_packet, args.out)
    except (KoreaFeedRefused, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print("Korea Sunday model evidence refused: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
