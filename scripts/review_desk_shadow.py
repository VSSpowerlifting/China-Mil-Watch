#!/usr/bin/env python3
"""Make an evidence packet; a machine report never supplies human sign-off."""
import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCHES = {"indonesia": "shadow/indonesia-kemhan", "korea": "shadow/korea-policy-briefing"}
STATE_PATH = re.compile(r"state/(shadow\.db|clock\.json|ledger/[A-Za-z0-9_.+-]+\.json|captures/[0-9a-f]{64}\.bin)$")


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def hash_files(state):
    if state.is_symlink() or any(p.is_symlink() for p in state.rglob("*")):
        raise ValueError("symlink state refused")
    result = {}
    for p in sorted(state.rglob("*")):
        if p.is_file():
            key = "state/" + p.relative_to(state).as_posix()
            if not STATE_PATH.fullmatch(key):
                raise ValueError("unrecognized state file: " + key)
            result[key] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def export_commit(repo, commit, desk, destination):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("full state commit SHA required")
    git(repo, "cat-file", "-e", commit + "^{commit}")
    git(repo, "merge-base", "--is-ancestor", commit, "refs/heads/" + BRANCHES[desk])
    if git(repo, "ls-tree", "--name-only", commit).decode().splitlines() != ["state"]:
        raise ValueError("state commit contains content outside state/")
    entries = git(repo, "ls-tree", "-r", "-z", commit, "state/").split(b"\0")
    if not any(entries):
        raise ValueError("state tree is absent")
    for entry in entries:
        if not entry:
            continue
        meta, raw_path = entry.split(b"\t", 1)
        mode, kind, blob = meta.decode().split()
        path = raw_path.decode("utf-8")
        if mode != "100644" or kind != "blob" or not STATE_PATH.fullmatch(path):
            raise ValueError("unrecognized or nonregular state tree entry")
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git(repo, "cat-file", "blob", blob))
    return git(repo, "rev-parse", commit + ":state").decode().strip()


def review(state, desk, out, as_of, commit=None, tree=None):
    if state.is_symlink():
        raise ValueError("symlink state refused")
    state, out = state.resolve(), out.resolve()
    roots = [ROOT] + [Path(line[len("worktree "):]).resolve()
                      for line in git(ROOT, "worktree", "list", "--porcelain").decode().splitlines()
                      if line.startswith("worktree ")]
    if any(root == p or root in p.parents for root in roots for p in (state, out)):
        raise ValueError("state and review output must be outside collector worktrees")
    if out.exists():
        raise ValueError("review destination exists; do not overwrite a packet")
    before = hash_files(state)
    clock = json.loads((state / "clock.json").read_text())
    if clock.get("desk") != desk:
        raise ValueError("clock desk mismatch")
    findings, ledgers = [], []
    for path in sorted((state / "ledger").glob("*.json")):
        ledger = json.loads(path.read_text())
        if ledger.get("desk") != desk:
            raise ValueError("ledger desk mismatch")
        if ledger.get("target_date_source") not in ("explicit", "schedule-slot", "manual-utc-date"):
            raise ValueError("unknown logical-date provenance")
        target = date.fromisoformat(ledger["target_date"])
        if target <= as_of:
            ledgers.append(ledger)
        if ledger["health"] != "ok":
            findings.append("Failed/skipped attempt: " + ledger["run_id"])
        for request in ledger["requests"]:
            digest = request["capture_sha256"]
            if before.get("state/captures/" + digest + ".bin") != digest:
                findings.append("Missing or changed request capture: " + digest)
    if not ledgers:
        raise ValueError("no ledgers on or before as-of date")
    covered = {l["target_date"] for l in ledgers if l["health"] == "ok"}
    first = min(date.fromisoformat(l["target_date"]) for l in ledgers)
    missing = [str(first + timedelta(days=n)) for n in range((as_of - first).days + 1)
               if str(first + timedelta(days=n)) not in covered]
    if missing:
        findings.append("No successful logical-day ledger: " + ", ".join(missing))
    records = []
    conn = sqlite3.connect((state / "shadow.db").as_uri() + "?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if [r[0] for r in conn.execute("SELECT desk FROM shadow_meta")] != [desk]:
            raise ValueError("database desk mismatch")
        columns = [r[1] for r in conn.execute("PRAGMA table_info(shadow_records)")]
        expected = ["source_identity", "url", "source_slug", "title_original", "text_original", "published_date",
                    "language_tag", "metadata_json", "content_sha256", "capture_sha256", "first_seen_run"]
        if columns != expected:
            raise ValueError("unknown record schema")
        for row in conn.execute("SELECT * FROM shadow_records ORDER BY published_date, source_identity"):
            record = dict(row)
            record["metadata"] = json.loads(record.pop("metadata_json"))
            pattern = (r"https://www\.kemhan\.go\.id/([0-9]{4})/([0-9]{2})/([0-9]{2})/[a-z0-9-]+\.html"
                       if desk == "indonesia" else r"https://www\.korea\.kr/briefing/pressReleaseView\.do\?newsId=([0-9]+)")
            match = re.fullmatch(pattern, record["url"])
            expected_slug = "id_kemhan_news" if desk == "indonesia" else "kr_policy_mnd_releases"
            expected_language = "id" if desk == "indonesia" else "ko"
            if not match or record["source_slug"] != expected_slug or record["language_tag"] != expected_language:
                findings.append("Record outside declared desk scope: " + record["source_identity"])
            elif desk == "indonesia":
                if "-".join(match.groups()) != record["published_date"] or record["source_identity"] != "kemhan:" + record["url"].split(".go.id", 1)[1]:
                    findings.append("Record date/identity mismatch: " + record["source_identity"])
            elif record["source_identity"] != "korea-policy:" + match[1] or record["metadata"].get("issuer") != "국방부":
                findings.append("Release identity/issuer mismatch: " + record["source_identity"])
            if hashlib.sha256(record["text_original"].encode()).hexdigest() != record["content_sha256"]:
                findings.append("Original-text hash mismatch: " + record["source_identity"])
            for digest in (record["capture_sha256"], record["metadata"].get("document_capture_sha256")):
                if digest and before.get("state/captures/" + digest + ".bin") != digest:
                    findings.append("Missing/changed record capture: " + record["source_identity"])
            records.append(record)
    finally:
        conn.close()
    if hash_files(state) != before:
        raise ValueError("state changed during review")
    report = {"desk": desk, "as_of": str(as_of), "mode": "formal_commit_snapshot" if commit else "rehearsal",
              "state_commit": commit, "state_tree": tree, "state_ref": BRANCHES[desk] if commit else None,
              "records": len(records), "ledgers": len(ledgers), "findings": findings,
              "missing_successful_days": missing, "input_hashes": before,
              "human_review_completed": False, "promotion_authorized": False}
    out.mkdir(parents=True)
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    with (out / "records.jsonl").open("w") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    notice = "Formal pinned state; human review remains incomplete." if commit else "REHEARSAL — no state-branch commit is bound; not a formal checkpoint."
    lines = ["# " + desk.title() + " shadow review", "", notice, "",
             "This report does not qualify or promote the desk.", "",
             "Read every exported record against its canonical page and, for Korea, its linked HWPX document.",
             "Confirm identity, title, portal/source date, issuer, complete extraction and capture correspondence.",
             "Distinguish a document's distribution/event date from the portal posting date.", "",
             "Findings: " + ("; ".join(findings) if findings else "No machine integrity findings."), "",
             "Human sign-off (unfilled): reviewer; actual completion timestamp; records reviewed;",
             "source comparisons; anomaly dispositions; verdict. Preserve this packet and the actual sign-off",
             "under a separately authorized durable review commit; no review publisher is invoked here.", ""]
    (out / "report.md").write_text("\n".join(lines))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desk", required=True, choices=BRANCHES)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--state-dir", type=Path)
    group.add_argument("--state-repo", type=Path)
    parser.add_argument("--state-commit")
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.state_repo:
            if not args.state_commit:
                raise ValueError("formal review requires --state-commit")
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                tree = export_commit(args.state_repo, args.state_commit, args.desk, root)
                report = review(root / "state", args.desk, args.out, args.as_of, args.state_commit, tree)
        else:
            if args.state_commit:
                raise ValueError("commit requires a state-repo, not loose state")
            report = review(args.state_dir, args.desk, args.out, args.as_of)
    except (ValueError, OSError, sqlite3.Error, subprocess.CalledProcessError) as exc:
        parser.exit(2, "review refused: " + str(exc) + "\n")
    print(json.dumps({k: report[k] for k in ("mode", "records", "ledgers", "findings")}))
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
