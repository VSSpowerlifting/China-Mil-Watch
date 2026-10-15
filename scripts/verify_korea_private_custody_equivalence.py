"""Read-only byte/Git-equivalence gate for a PROPOSED private Korea archive.

Compare two already-provisioned local clones of the Korea shadow state. This
NEVER migrates, fetches, clones, pushes, deletes, provisions access, authorizes
source reuse, or verifies repository visibility. No raw evidence is printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
from pathlib import Path

FROZEN_14 = "0595f0fd29b769cbab5dd57c2ef57af174237a67"
FROZEN_CLOCK_UTC = "2026-10-06T16:52:01.420713+00:00"
FROZEN_DAY_ZERO_RUN = "local-native-20261006-korea"
MISS = "2026-10-12"
SUCCESS = {"ok", "ok_all_duplicates", "ok_no_publications", "ok_all_filtered"}
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
LEDGER_NAME = re.compile(r"[0-9]{8}T[0-9]{6}\.[0-9]{6}\+0000-[A-Za-z0-9-]+\.json\Z")
MAX_FILES = 8000
MAX_BYTES = 250_000_000


class CustodyHold(ValueError):
    """Hold cutover on any unmatched, incomplete or unsafe local evidence."""


def demand(condition, reason):
    if not condition:
        raise CustodyHold(reason)


def git(repo, *args, check=True):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True,
        timeout=15, check=False,
    )
    if check:
        demand(result.returncode == 0, "Git identity/ancestry check failed")
    return result


def read_json(path, max_size):
    demand(path.is_file() and not path.is_symlink()
           and 0 < path.stat().st_size <= max_size, "missing or unsafe JSON")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CustodyHold("malformed evidence JSON") from exc


def inventory(repo, *, frozen_commit=FROZEN_14):
    """Inspect only the full Git-pinned state root; never expose contents."""
    repo = Path(repo).resolve(strict=True)
    demand(repo.is_dir() and not repo.is_symlink(), "invalid state repository")
    demand(git(repo, "rev-parse", "--show-toplevel").stdout.strip() == str(repo),
           "state path must be Git checkout root")
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    demand(SHA40.fullmatch(head) is not None
           and SHA40.fullmatch(frozen_commit) is not None,
           "invalid Git state identity")
    demand(git(repo, "merge-base", "--is-ancestor", frozen_commit, head,
               check=False).returncode == 0,
           "frozen 14-source history is absent or rewritten")
    demand(git(repo, "status", "--porcelain", "--untracked-files=all").stdout.strip() == "",
           "dirty working tree or untracked original files")
    demand(git(repo, "ls-tree", "--name-only", "HEAD").stdout.splitlines() == ["state"],
           "unexpected top-level Git evidence files")
    state = repo / "state"
    demand(state.is_dir() and not state.is_symlink(), "missing state directory")
    demand({x.name for x in state.iterdir()} ==
           {"captures", "ledger", "clock.json", "shadow.db"},
           "unexpected or missing Korea state components")
    files = {}
    total = 0
    for folder, pattern, limit in (("captures", SHA64, 20_000_000),
                                   ("ledger", LEDGER_NAME, 2_000_000)):
        path = state / folder
        demand(path.is_dir() and not path.is_symlink(), "missing evidence folder")
        for item in path.iterdir():
            demand(item.is_file() and not item.is_symlink(),
                   "unexpected evidence folder entry")
            if folder == "captures":
                demand(item.name.endswith(".bin") and
                       SHA64.fullmatch(item.stem) is not None,
                       "non-content-addressed capture")
            else:
                demand(pattern.fullmatch(item.name) is not None,
                       "unexpected ledger file")
            size = item.stat().st_size
            demand(0 < size <= limit, "unsafe evidence file size")
            total += size
            demand(total <= MAX_BYTES and len(files) < MAX_FILES,
                   "evidence budget exceeded")
            digest = hash_file(item)
            if folder == "captures":
                demand(digest == item.stem,
                       "capture bytes disagree with immutable filename")
            files[f"{folder}/{item.name}"] = digest
    for name, cap in (("clock.json", 10000), ("shadow.db", 25_000_000)):
        path = state / name
        demand(path.is_file() and not path.is_symlink()
               and 0 < path.stat().st_size <= cap, "missing or unsafe core state")
        total += path.stat().st_size
        demand(total <= MAX_BYTES, "evidence budget exceeded")
        files[name] = hash_file(path)
    demand(any(x.startswith("captures/") for x in files) and
           any(x.startswith("ledger/") for x in files), "empty archived state")
    clock = read_json(state / "clock.json", 10000)
    demand(type(clock) is dict and set(clock) ==
           {"desk", "day_zero_utc", "day_zero_run_id"}
           and clock["desk"] == "korea"
           and clock["day_zero_utc"] == FROZEN_CLOCK_UTC
           and clock["day_zero_run_id"] == FROZEN_DAY_ZERO_RUN,
           "Korea original day-zero timestamp or run identity changed")
    ledgers = []
    for rel in sorted(files):
        if rel.startswith("ledger/"):
            row = read_json(state / rel, 2_000_000)
            demand(type(row) is dict and row.get("desk") == "korea"
                   and type(row.get("run_id")) is str
                   and type(row.get("target_date")) is str,
                   "foreign or malformed Korea ledger")
            ledgers.append(row)
    scheduled_oct12 = any(
        x["target_date"] == MISS
        and x.get("target_date_source") == "schedule-slot"
        and x.get("health") == "ok" and x.get("result") in SUCCESS
        for x in ledgers
    )
    # Actual failed Oct12 action is not a successful scheduled receipt.
    demand(not scheduled_oct12, "historical October 12 gap misrepresented")
    count = _check_originals(state / "shadow.db", files)
    return {
        "head": head,
        "files": files,
        "capture_count": sum(x.startswith("captures/") for x in files),
        "ledger_count": len(ledgers),
        "original_count": count,
        "clock_day_zero": clock["day_zero_utc"],
        "october_12_scheduled_success_observed": scheduled_oct12,
    }


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _check_originals(path, indexed):
    """Read source content privately for SHA checks; never print original bodies."""
    try:
        con = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
        con.row_factory = sqlite3.Row
        try:
            demand(con.execute("PRAGMA quick_check").fetchone()[0] == "ok",
                   "shadow database integrity failed")
            desk = con.execute("SELECT desk FROM shadow_meta").fetchall()
            demand([x[0] for x in desk] == ["korea"], "wrong issuer desk database")
            rows = con.execute(
                "SELECT source_identity, url, source_slug, text_original, "
                "content_sha256, capture_sha256, metadata_json "
                "FROM shadow_records ORDER BY source_identity"
            ).fetchall()
            demand(5 <= len(rows) <= 5000, "unexpected Korea original count")
            ids = set()
            for x in rows:
                ident = x["source_identity"]
                demand(type(ident) is str and ident.startswith("korea-policy:")
                       and ident not in ids, "wrong or duplicate original identity")
                ids.add(ident)
                demand(x["url"] == (
                    "https://www.korea.kr/briefing/pressReleaseView.do?newsId="
                    + ident.partition(":")[2])
                       and x["source_slug"] == "kr_policy_mnd_releases",
                       "wrong article URL or source family")
                content_hash = hashlib.sha256(x["text_original"].encode("utf-8")).hexdigest()
                demand(content_hash == x["content_sha256"], "Korean original text drift")
                m = json.loads(x["metadata_json"])
                demand(type(m) is dict, "unsafe original metadata")
                for sha in (x["capture_sha256"], m.get("document_capture_sha256")):
                    demand(type(sha) is str and SHA64.fullmatch(sha) is not None
                           and "captures/" + sha + ".bin" in indexed,
                           "original HWPX/page capture absent from Git")
            return len(rows)
        finally:
            con.close()
    except sqlite3.Error as exc:
        raise CustodyHold("invalid read-only Korea shadow database") from exc


def compare(source, candidate, *, frozen_commit=FROZEN_14):
    """Evidence equality only, NOT permission, privacy or cutover readiness."""
    a, b = Path(source).resolve(strict=True), Path(candidate).resolve(strict=True)
    demand(a != b and a not in b.parents and b not in a.parents,
           "source and destination must be separate checkouts")
    before = inventory(a, frozen_commit=frozen_commit)
    after = inventory(b, frozen_commit=frozen_commit)
    demand(before["head"] == after["head"],
           "target has not preserved exact source Git tip")
    demand(before["files"] == after["files"],
           "target differs in filename, HWPX, page, ledger, clock or database bytes")
    return {
        "schema": "ipr-korea-private-custody-byte-equivalence/1",
        "preserved_git_commit": before["head"],
        "preserved_frozen_14_source_ancestor": frozen_commit,
        "compared_evidence_file_count": len(before["files"]),
        "capture_count": before["capture_count"],
        "ledger_count": before["ledger_count"],
        "original_count": before["original_count"],
        "day_zero_utc": before["clock_day_zero"],
        "october_12_historical_gap_remains": not before["october_12_scheduled_success_observed"],
        "source_and_candidate_bytes_identical": True,
        "candidate_repository_privacy_verified": False,
        "credential_scope_verified": False,
        "restore_tested": False,
        "scheduled_collector_switched": False,
        "migration_performed_by_this_tool": False,
        "public_history_or_artifacts_deleted": False,
        "source_rights_approved": False,
        "sunday_or_ai_or_email_authorized": False,
        "production_promotion_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-checkout", required=True)
    parser.add_argument("--candidate-checkout", required=True)
    parser.add_argument("--explicit-local-read-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.explicit_local_read_only:
        parser.error("explicit local-only, read-only acknowledgement required")
    receipt = compare(args.source_checkout, args.candidate_checkout)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
