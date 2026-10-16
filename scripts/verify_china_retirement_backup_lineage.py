"""Verify a private China backup still covers the exact live pre-retirement DB.

The backup source may predate *code-only* desk merges. It is reusable only
when it is an ancestor of the current Git checkout and its tracked SQLite Git
blob and SHA-256 are exactly identical to the current live corpus. A different
corpus or diverged history always fails closed.

Called before any China retirement scratch staging or publication.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess


SHA = re.compile(r"^[a-f0-9]{40}$")
DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _git(repo, *args, check=True):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if check and result.returncode:
        raise ValueError("Git verification failed: " + " ".join(args) +
                         ": " + result.stderr.strip()[:160])
    return result


def verify(repo, backup_source_sha, expected_db_sha256):
    repo = Path(repo).resolve(strict=True)
    if not SHA.fullmatch(backup_source_sha):
        raise ValueError("backup source must be an exact 40-character Git SHA")
    if not DIGEST.fullmatch(expected_db_sha256):
        raise ValueError("backup DB digest must be an exact SHA-256")
    current_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    if not SHA.fullmatch(current_sha):
        raise ValueError("could not pin current release Git SHA")
    ancestry = _git(repo, "merge-base", "--is-ancestor",
                    backup_source_sha, current_sha, check=False)
    if ancestry.returncode != 0:
        raise ValueError("backup source is not an ancestor of current main")
    backup_blob = _git(repo, "rev-parse",
                       backup_source_sha + ":pla_watch.db").stdout.strip()
    current_blob = _git(repo, "rev-parse", "HEAD:pla_watch.db").stdout.strip()
    if backup_blob != current_blob:
        raise ValueError("tracked SQLite Git blob changed since private backup")
    db = repo / "pla_watch.db"
    if not db.is_file():
        raise ValueError("missing tracked production SQLite")
    digest = sha256(db.read_bytes()).hexdigest()
    if digest != expected_db_sha256:
        raise ValueError("live SQLite bytes differ from verified private backup")
    # The current commit, not the historical backup commit, must remain the
    # sole allowed parent for the subsequent atomic production release.
    return {"backup_source_sha": backup_source_sha,
            "release_main_sha": current_sha,
            "db_git_blob_sha1": current_blob,
            "db_sha256": digest, "live_db_exactly_backed_up": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--backup-source-sha", required=True)
    parser.add_argument("--expected-db-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.repo, args.backup_source_sha,
                            args.expected_db_sha256), sort_keys=True))


if __name__ == "__main__":
    main()
