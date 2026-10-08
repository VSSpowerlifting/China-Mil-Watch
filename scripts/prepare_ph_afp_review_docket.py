"""Produce a concise metadata-only docket from *pinned* AFP shadow review packets.

This is for assigning real human source-review work, not issuing review
decisions. It never extracts/promotes AFP shadow bodies into weekly AI prompts.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

from scripts import prepare_ph_afp_run_review as review

COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
RUN_RE = re.compile(r"[1-9][0-9]*-[1-9][0-9]*\Z")
SOURCE_RE = re.compile(r"afp:[0-9]+\Z")
URL_RE = re.compile(r"https://www\.afp\.mil\.ph/news/[a-z0-9]+(?:-[a-z0-9]+)*\Z")
DAY_RE = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}\Z")
SHA256_RE = re.compile(r"[a-f0-9]{64}\Z")


class DocketError(ValueError):
    """An incomplete or unpinned human source-review docket."""


def require(condition, why):
    if not condition:
        raise DocketError(why)


def single_line(value):
    require(type(value) is str, "record display text must be UTF-8 text")
    return " ".join(value.split())


def markdown_safe(value):
    """Source-supplied titles must not inject Markdown formatting or links."""
    return re.sub(r"([\\\`*_{}\[\]()#+.!|<>])", r"\\\1", single_line(value))


def parse_batch(value):
    require(type(value) is str and value.count(":") == 1,
            "batch must be the exact COMMIT:RUN_ID pair")
    commit, run = value.split(":")
    require(COMMIT_RE.fullmatch(commit) is not None and
            RUN_RE.fullmatch(run) is not None,
            "batch needs literal historical commit and scheduled numeric run ID")
    return commit, run


def build_docket(packets):
    require(type(packets) is list and bool(packets),
            "at least one real immutable source-review packet required")
    batches = []
    seen_ids = set()
    seen_runs = set()
    total = 0
    for packet in packets:
        require(type(packet) is dict and
                packet.get("protocol") == "ipr_ph_afp_per_run_unsigned_review_v1" and
                packet.get("source_kind") == "AFP_first_party_shadow_not_production" and
                packet.get("review_scope") ==
                "all_new_records_from_exact_scheduled_shadow_run" and
                packet.get("desk_qualified") is False and
                packet.get("human_review_complete") is False and
                packet.get("human_approval") is False and
                packet.get("production_assignments") == 0,
                "packet falsely claims authorization or has unexpected origin")
        run = packet.get("original_run_id")
        commit = packet.get("historical_state_commit")
        require(type(run) is str and RUN_RE.fullmatch(run) is not None and
                type(commit) is str and COMMIT_RE.fullmatch(commit) is not None and
                run not in seen_runs,
                "unbound or duplicate pinned historical run")
        seen_runs.add(run)
        rows = packet.get("records")
        require(type(rows) is list and
                type(packet.get("machine_verified_capture_count")) is int and
                len(rows) == packet["machine_verified_capture_count"],
                "packet record/capture count mismatch")
        require(type(packet.get("target_date")) is str and
                DAY_RE.fullmatch(packet["target_date"]) is not None,
                "missing scheduled logical UTC date")
        import datetime
        try:
            date_ = datetime.date.fromisoformat(packet["target_date"])
            require(date_.isoformat() == packet["target_date"],
                    "noncanonical scheduled UTC date")
        except ValueError as exc:
            raise DocketError("invalid scheduled date") from exc
        index = []
        for row in rows:
            require(type(row) is dict and
                    row.get("decision") == "pending" and
                    row.get("reviewer_name") == "" and
                    row.get("read_original_capture") is False and
                    row.get("reviewed_at_utc") is None and
                    row.get("rationale") == "" and
                    row.get("checks") == dict.fromkeys(review.CHECKS, None),
                    "docket refuses to impersonate or alter review decisions")
            source_id = row.get("source_identity")
            url = row.get("source_url")
            pub = row.get("published_date")
            title = row.get("title_original")
            require(type(source_id) is str and SOURCE_RE.fullmatch(source_id) is not None
                    and source_id not in seen_ids and
                    row.get("first_seen_run") == run and
                    type(url) is str and URL_RE.fullmatch(url) is not None and
                    type(pub) is str and DAY_RE.fullmatch(pub) is not None and
                    type(title) is str and bool(title.strip()) and
                    row.get("text_status") in ("text", "no_text") and
                    type(row.get("body_chars")) is int and
                    ((row["text_status"] == "text" and row["body_chars"] > 0) or
                     (row["text_status"] == "no_text" and row["body_chars"] == 0)),
                    "duplicate, unsupported or contradictory AFP archival identity")
            try:
                pub_day = datetime.date.fromisoformat(pub)
                require(pub_day.isoformat() == pub and pub_day <= date_,
                        "publication date later than scheduled capture date")
            except ValueError as exc:
                raise DocketError("invalid AFP publisher date") from exc
            require(all(type(row.get(k)) is str and SHA256_RE.fullmatch(row[k])
                        is not None for k in ("text_sha256", "capture_sha256")),
                    "missing original evidence hashes")
            seen_ids.add(source_id)
            index.append({
                "source_identity": source_id,
                "title_original": single_line(title),
                "source_url": url,
                "published_date": pub,
                "text_sha256": row["text_sha256"],
                "capture_sha256": row["capture_sha256"],
                "review_status": "not_started",
                "body_status": row["text_status"],
                "extraction_review_priority": (
                    "body_unavailable_requires_human_disposition"
                    if row["text_status"] == "no_text" else "ordinary_fidelity_review"
                ),
                "human_review_authenticated": False,
            })
        batches.append({
            "target_date": packet["target_date"],
            "run_id": run, "historical_state_commit": commit,
            "new_records": len(index), "records": index,
        })
        total += len(index)
    return {
        "protocol": "ipr_ph_afp_metadata_review_docket_v1",
        "source": "philippines_afp_shadow",
        "total_source_records": total,
        "body_unavailable_records": sum(
            r["body_status"] == "no_text"
            for batch in batches for r in batch["records"]
        ),
        "batches": batches,
        "required_fidelity_checks": list(review.CHECKS),
        "source_bodies_or_raw_api_responses_included": False,
        "human_review_completed": False,
        "source_reuse_approved": False,
        "production_eligible": False,
        "weekly_ai_writer_eligible": False,
        "automated_review_decisions": 0,
    }


def markdown_docket(docket):
    lines = [
        "# Philippines AFP — unsigned original-source review docket",
        "",
        "Source-review scheduling only; every entry is PENDING human inspection.",
        "Not a legal reuse ruling, independent event corroboration, production "
        "admission or AI-writer authorization.",
        "",
        "**{} source records across {} original scheduled runs**".format(
            docket["total_source_records"], len(docket["batches"])),
        "**{} archived bodies unavailable: require human extraction disposition.**".format(
            docket["body_unavailable_records"]),
    ]
    for batch in docket["batches"]:
        lines += [
            "",
            "## {} | {} new records".format(batch["target_date"], batch["new_records"]),
            "Pinned state: \x60{}\x60 | run: \x60{}\x60".format(
                batch["historical_state_commit"], batch["run_id"]),
            "",
            "| ID | AFP publication date | Original article | Body | Review |",
            "|---|---|---|---|---|",
        ]
        for r in batch["records"]:
            lines.append("| \x60{}\x60 | {} | [{}]({}) | {} | Pending |".format(
                r["source_identity"], r["published_date"],
                markdown_safe(r["title_original"]), r["source_url"],
                "Full text" if r["body_status"] == "text" else
                "No text — review extraction"))
    lines += [
        "",
        "## Six checks for each original, completed only by a real reviewer",
    ]
    lines += ["- \x60{}\x60".format(s) for s in docket["required_fidelity_checks"]]
    lines += [
        "",
        "For each source, compare the preserved original API response and extracted "
        "body using \x60prepare_ph_afp_run_review.py packet\x60. Enter actual "
        "review decisions only in that private original packet, then validate "
        "with \x60prepare_ph_afp_run_review.py validate\x60.",
        "Do not put preserved full text or original API payloads in this docket.",
        "Do not confuse multiple AFP articles with independently corroborated events.",
        "",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-repo", required=True,
                   help="local repository containing explicitly fetched shadow state history")
    p.add_argument("--batch", action="append", required=True,
                   help="literal 40-char historical commit and numeric run ID as COMMIT:RUN")
    p.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = p.parse_args()
    try:
        batches = [parse_batch(item) for item in args.batch]
        packets = [
            review.make_packet(review.FrozenState(args.state_repo, commit), run)
            for commit, run in batches
        ]
        report = build_docket(packets)
        if args.format == "json":
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(markdown_docket(report))
    except (DocketError, review.AFPReviewError, OSError, TypeError, ValueError,
            UnicodeError) as exc:
        p.exit(1, "AFP review docket: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
