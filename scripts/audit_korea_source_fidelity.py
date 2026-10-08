#!/usr/bin/env python3
"""Audit Korea's archived HWPX originals against stored shadow text, offline.

Produces machine findings and *blank* human source-review assignments. This is
neither a production desk approval nor source permission nor publication review.
It makes no network requests and never writes to shadow or production state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from scraper.sources.kr_policy_briefing import hwpx_text
from scripts import review_desk_shadow as formal

ROOT = Path(__file__).resolve().parents[1]
STATE_BRANCH = "shadow/korea-policy-briefing"
HEX = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
IDENTITY = re.compile(r"korea-policy:([0-9]{6,20})\Z")


class AuditRefused(ValueError):
    """Untrusted or wrongly scoped state cannot be treated as Korean evidence."""


def require(ok, message):
    if not ok:
        raise AuditRefused(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def iso_day(text):
    require(isinstance(text, str), "publication date is not a string")
    try:
        result = date.fromisoformat(text)
    except ValueError as exc:
        raise AuditRefused("invalid publication date") from exc
    require(result.isoformat() == text, "publication date is noncanonical")
    return result


def document_url_ok(url):
    if not isinstance(url, str):
        return False
    p = urlsplit(url)
    qs = parse_qs(p.query)
    return (
        p.scheme == "https" and p.netloc == "www.korea.kr"
        and p.path == "/common/download.do"
        and not p.fragment and not p.username and not p.password
        and set(qs) == {"fileId", "tblKey"}
        and qs["tblKey"] == ["GMN"] and len(qs["fileId"]) == 1
        and bool(re.fullmatch(r"[0-9]+", qs["fileId"][0]))
        and p.query == "fileId=" + qs["fileId"][0] + "&tblKey=GMN"
    )


def source_compare(record, state):
    """Reparse ACTUAL preserved HWPX; stored SHA agreement alone is insufficient."""
    rid = record.get("source_identity", "")
    match = IDENTITY.fullmatch(rid) if isinstance(rid, str) else None
    problems = []
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        problems.append("missing structured original-document metadata")
    try:
        iso_day(record.get("published_date"))
    except AuditRefused:
        problems.append("noncanonical publisher date")
    if not match:
        problems.append("invalid source identity")
    elif record.get("url") != (
        "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + match[1]
    ):
        problems.append("source URL differs from canonical identity")
    if record.get("source_slug") != "kr_policy_mnd_releases":
        problems.append("wrong source family")
    if record.get("language_tag") != "ko":
        problems.append("missing Korean original-language label")
    if not (metadata.get("issuer") == "국방부"
            and metadata.get("publisher") == "대한민국 정책브리핑"
            and metadata.get("publication_kind") == "syndicated_press_release"
            and metadata.get("body_scope") == "published_hwpx_text"
            and metadata.get("attachments_collected") is True):
        problems.append("record metadata does not substantiate MND-labeled republication")
    if not document_url_ok(metadata.get("document_url")):
        problems.append("document URL is not a canonical Policy Briefing HWPX download")

    texts = record.get("text_original")
    if not isinstance(texts, str) or not texts.strip():
        problems.append("no stored original-language text")
    text_sha = record.get("content_sha256")
    if not isinstance(text_sha, str) or not HEX.fullmatch(text_sha):
        problems.append("invalid stored original-text digest")
    elif isinstance(texts, str) and digest(texts.encode("utf-8")) != text_sha:
        problems.append("stored original text does not match recorded digest")

    capture_root = Path(state) / "captures"
    html_sha = record.get("capture_sha256")
    doc_sha = metadata.get("document_capture_sha256")
    captured = {}
    for kind, sha in (("html", html_sha), ("hwpx", doc_sha)):
        if not isinstance(sha, str) or not HEX.fullmatch(sha):
            problems.append(kind + " capture digest is invalid")
            continue
        candidate = capture_root / (sha + ".bin")
        if candidate.is_symlink() or not candidate.is_file():
            problems.append(kind + " capture missing or nonregular")
            continue
        if candidate.stat().st_size > 10_000_000:
            problems.append(kind + " capture exceeds permitted size")
            continue
        content = candidate.read_bytes()
        if digest(content) != sha:
            problems.append(kind + " capture bytes fail SHA-256 parity")
            continue
        captured[kind] = content

    recovered = None
    if "hwpx" in captured:
        try:
            recovered = hwpx_text(captured["hwpx"])
        except (ValueError, OSError, UnicodeError) as exc:
            problems.append("original HWPX re-extraction failed: " + type(exc).__name__)
        else:
            if recovered != texts:
                problems.append("HWPX re-extracted text differs from stored Korean text")
            if text_sha != digest(recovered.encode("utf-8")):
                problems.append("HWPX original does not match recorded text digest")

    return {
        "source_identity": rid if isinstance(rid, str) else "<invalid>",
        "source_url": record.get("url"),
        "original_title": record.get("title_original"),
        "portal_date": record.get("published_date"),
        "original_language": record.get("language_tag"),
        "issuer": metadata.get("issuer"),
        "publisher": metadata.get("publisher"),
        "document_url": metadata.get("document_url"),
        "original_text_sha256": text_sha,
        "hwpx_sha256": doc_sha,
        "extracted_characters": len(recovered) if recovered is not None else None,
        "extracted_paragraphs": len(recovered.splitlines()) if recovered is not None else None,
        "machine_fidelity": "PASS" if not problems else "FAIL",
        "findings": sorted(problems),
    }


def chain_findings(ledgers, state, *, as_of):
    """Correlate success ledgers and final DB without inventing failed Action runs."""
    issues = []
    ordered = sorted(ledgers, key=lambda x: x.get("finished_utc", ""))
    seen = set()
    prior = None
    for run in ordered:
        ident = run.get("run_id")
        if not isinstance(ident, str) or ident in seen:
            issues.append("duplicate or unknown run identity")
        seen.add(ident)
        if run.get("desk") != "korea":
            issues.append("non-Korean ledger")
        try:
            d = iso_day(run.get("target_date"))
            finished = datetime.fromisoformat(run["finished_utc"])
            require(finished.tzinfo is not None
                    and finished.utcoffset() == timedelta(0),
                    "non-UTC finish time")
            require(d <= finished.date(), "future nominal date")
            require(d <= as_of, "run extends beyond requested cutoff")
        except (AuditRefused, ValueError, KeyError, TypeError):
            issues.append("invalid ledger target or completion time")
        if run.get("health") != "ok":
            issues.append("unsuccessful published run " + str(ident))
        before, after = run.get("state_sha256_before"), run.get("state_sha256_after")
        if prior is not None and before != prior:
            issues.append("ledger DB hash chain discontinuity at " + str(ident))
        if not isinstance(after, str) or not HEX.fullmatch(after):
            issues.append("missing final DB checksum at " + str(ident))
        prior = after
    db_path = Path(state) / "shadow.db"
    if prior != digest(db_path.read_bytes()):
        issues.append("last successful state hash differs from current SQLite bytes")
    return sorted(set(issues))


def make_packet(state, review, records, ledgers, as_of, commit, tree):
    checked = [source_compare(r, state) for r in records]
    issues = list(review.get("findings", []))
    issues.extend(chain_findings(ledgers, state, as_of=as_of))
    machine = "PASS" if checked and all(x["machine_fidelity"] == "PASS" for x in checked) else "FAIL"
    continuity = ("PASS" if not issues and not review.get("missing_successful_days")
                  else "FAIL")
    checks = []
    for row in checked:
        checks.append({
            "source_identity": row["source_identity"],
            "original_text_sha256": row["original_text_sha256"],
            "hwpx_sha256": row["hwpx_sha256"],
            "reviewer": None,
            "review_completed_utc": None,
            "publisher_page_compared": None,
            "original_hwpx_visually_compared": None,
            "extracted_korean_text_fidelity_confirmed": None,
            "issuer_title_and_portal_date_confirmed": None,
            "distribution_vs_portal_date_checked": None,
            "translation_or_technical_terms_checked": None,
            "source_reuse_rights_reviewed": None,
            "editorial_summary": None,
            "review_notes": None,
            "source_specific_approved": False,
        })
    report = {
        "schema": "ipr-korea-source-fidelity/1",
        "desk": "korea",
        "as_of": as_of.isoformat(),
        "state_branch": STATE_BRANCH,
        "state_commit": commit,
        "state_tree": tree,
        "source_scope": "Tier B government-republished MND-labeled HWPX; NOT direct MND or whole Korea Desk",
        "records_checked": len(checked),
        "machine_hwp_original_parity": machine,
        "scheduled_continuity": continuity,
        "continuity_findings": sorted(set(issues)),
        "missing_logical_dates": review.get("missing_successful_days", []),
        "actions_failure_inventory": "UNMEASURED — state ledgers omit failed pre-publication GitHub Actions jobs",
        "human_source_review": "UNMEASURED",
        "content_reuse_rights": "UNMEASURED",
        "institutional_breadth": "UNMEASURED — one MND-labeled republication family only",
        "source_eligible_for_substantive_weekly_claims": False,
        "production_promotion_authorized": False,
        "records": checked,
    }
    return report, {
        "schema": "ipr-korea-human-source-review/1",
        "state_commit": commit,
        "state_tree": tree,
        "human_approval_count": 0,
        "editorial_claim_permissions_granted": 0,
        "source_review_assignments": checks,
    }


def run(state_repo, state_commit, as_of, output):
    require(COMMIT.fullmatch(state_commit) is not None, "literal full state commit required")
    require(type(as_of) is date, "exact as-of date required")
    output = Path(output)
    require(not output.is_symlink() and not output.exists(), "new audit output directory required")
    resolved = output.resolve()
    require(resolved != ROOT and ROOT not in resolved.parents,
            "review packet cannot be committed in repository worktrees")
    require(not output.parent.is_symlink(), "output parent symlink refused")
    repo = Path(state_repo)
    require(not repo.is_symlink(), "state-repo symlink refused")
    repo = repo.resolve()
    require(repo.is_dir(), "state repository not found")
    require(formal.git(repo, "rev-parse", "--verify",
                       "refs/heads/" + STATE_BRANCH).decode().strip() == state_commit,
            "must audit current literal South Korea state tip")
    with tempfile.TemporaryDirectory(prefix="ipr-korea-fidelity-") as tmp:
        base = Path(tmp)
        tree = formal.export_commit(repo, state_commit, "korea", base)
        state = base / "state"
        formal_out = base / "formal"
        reviewed = formal.review(state, "korea", formal_out, as_of,
                                 commit=state_commit, tree=tree)
        records = [json.loads(line) for line in
                   (formal_out / "records.jsonl").read_text(encoding="utf-8").splitlines()]
        ledgers = [json.loads(p.read_text(encoding="utf-8"))
                   for p in sorted((state / "ledger").glob("*.json"))]
        report, assignment = make_packet(
            state, reviewed, records, ledgers, as_of, state_commit, tree)
    output.mkdir(parents=True)
    (output / "machine_fidelity.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    (output / "human_source_review_BLANK.json").write_text(
        json.dumps(assignment, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    lines = [
        "# Korea source-fidelity checkpoint (NOT an approval)",
        "",
        "State commit: `" + state_commit + "`",
        "State tree: `" + tree + "`",
        "As of: " + as_of.isoformat(),
        "Machine HWPX/text parity: **" + report["machine_hwp_original_parity"] + "**",
        "Ledger continuity: **" + report["scheduled_continuity"] + "**",
        "",
        "Review *the actual source URL and linked Korean HWPX* for each record.",
        "The machine checks HWPX/XML parity, not Korean interpretation or visual order.",
        "Portal posting dates are not necessarily document distribution or event dates.",
        "Enter real reviewer identity and timestamps only after the comparisons occur.",
        "The blank template is NOT an approval artifact. Do not import it into Briefs.",
        "Check reuse policy separately. No production desk, model facts or public use is authorized.",
        "",
        "Records:",
    ]
    for item in report["records"]:
        lines += ["", "- `" + item["source_identity"] + "` — " +
                  str(item["machine_fidelity"]),
                  "  Publisher: " + str(item["source_url"]),
                  "  Linked original: " + str(item["document_url"])]
    (output / "REVIEW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state-repo", type=Path, required=True)
    ap.add_argument("--state-commit", required=True)
    ap.add_argument("--as-of", required=True, type=date.fromisoformat)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        report = run(args.state_repo, args.state_commit, args.as_of, args.out)
    except (AuditRefused, ValueError, OSError, subprocess.CalledProcessError,
            json.JSONDecodeError) as exc:
        print("Korea source audit refused: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps({
        "state_commit": report["state_commit"],
        "records_checked": report["records_checked"],
        "machine_hwp_original_parity": report["machine_hwp_original_parity"],
        "scheduled_continuity": report["scheduled_continuity"],
        "human_source_review": report["human_source_review"],
        "production_promotion_authorized": False,
    }, sort_keys=True))
    return 0 if report["machine_hwp_original_parity"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
