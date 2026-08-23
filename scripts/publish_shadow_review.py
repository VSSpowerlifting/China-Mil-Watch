#!/usr/bin/env python3
"""
Preserve a completed Singapore shadow review on the orphan review branch.

Four things are kept strictly apart, because collapsing any two of them would
destroy the audit:

  1. the shadow state that was reviewed — lives on `shadow/singapore-mindef`
     and is never touched here
  2. the deterministic automated package — what was *presented* for review
  3. the reviewer's structured sign-off — what a person *concluded*
  4. this Git commit — *when and by whom* that conclusion was preserved

The automated package id names (2). The completed-review id names (3) bound to
(2). The commit names (4). None of them is a cryptographic signature and none
establishes the reviewer's legal identity: they establish that a specific set of
answers was recorded against a specific corpus, nothing more.

Refusals over convenience
-------------------------
A packet is publishable only if it is formal (names a checkpoint and a
40-character shadow-state commit), its sign-off binds to it exactly, every
required record carries explicit boolean answers, every anomaly has a
disposition, and the verdict is consistent with the answers. A `fail` verdict is
publishable — an audit that only preserves successes is not an audit.

Safety
------
Dry-run is the default; `--publish` is required to touch a remote. The target
branch is a constant, not an argument. Pushes are ordinary fast-forward pushes:
no force, no lease, no ref deletion, and never any ref but the review branch.
Git runs through argument arrays, never a shell string. The source repository's
own worktree and branch are never checked out or moved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PUBLISHER_VERSION = "1.0.0"

#: Part of the safety contract, deliberately not a CLI argument. A publisher
#: that can be pointed at any branch is one typo away from writing review
#: output onto main.
REVIEW_BRANCH = "review/singapore-mindef"
DESK_IDENTITY = "singapore-mindef"
SIGNOFF_SCHEMA = "shadow-review-signoff/1"
CHECKPOINTS = {"day-07": 7, "day-14": 14, "day-30": 30}
CHECK_FIELDS = (
    "source_page_opened", "title_matches", "publication_date_matches",
    "canonical_url_matches", "body_appears_complete", "kind_is_reasonable",
    "no_denial_or_template_stored",
)
VERDICTS = ("pass", "pass_with_findings", "fail")

#: Exactly what may be preserved. Anything else in the packet is a refusal
#: rather than something to skip quietly.
PACKET_FILES = ("review_manifest.json", "review_report.md",
                "record_inventory.jsonl")
FORBIDDEN_SUFFIXES = (".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3",
                      ".pem", ".key", ".env", ".pyc", ".so", ".dylib")
FORBIDDEN_NAMES = (".env", "pla_watch.db", "shadow.db", "id_rsa", ".netrc")
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"x-access-token:"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


class PublishError(RuntimeError):
    """Refused. The remote is left exactly as it was."""


# ── canonical identity ───────────────────────────────────────────────────────

def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def completed_review_id(manifest: dict, signoff: dict) -> str:
    """
    Identity of the review ANSWERS, bound to the package they answer.

    Key order in the sign-off file cannot change it — the payload is
    canonicalised. Git commit time and filesystem metadata are excluded, so the
    same review preserved twice is the same review.
    """
    payload = canonical({
        "signoff_schema": signoff.get("signoff_schema"),
        "automated_package_id": manifest["deterministic_sha256"],
        "signoff": signoff,
    })
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ── validation ───────────────────────────────────────────────────────────────

def load_json(path: Path, what: str) -> dict:
    if not path.is_file():
        raise PublishError("no %s at %s" % (what, path))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise PublishError("%s is not valid JSON: %s" % (what, exc))


def assert_packet_clean(packet: Path) -> None:
    for p in sorted(packet.rglob("*")):
        if p.is_dir():
            if p.name == ".github" or p.name == "workflows":
                raise PublishError("packet contains %s/ — review evidence "
                                   "carries no workflows" % p.name)
            continue
        rel = p.relative_to(packet)
        if p.name in FORBIDDEN_NAMES or p.suffix in FORBIDDEN_SUFFIXES:
            raise PublishError("packet contains %s, which may never be "
                               "preserved on the review branch" % rel)
        if os.access(p, os.X_OK):
            raise PublishError("packet contains an executable file: %s" % rel)
        if ".github" in rel.parts or rel.suffix in (".yml", ".yaml"):
            raise PublishError("packet contains a workflow-shaped file: %s" % rel)
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            raise PublishError("packet contains a non-text file: %s" % rel)
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                raise PublishError("possible credential in %s — refusing to "
                                   "preserve it" % rel)


def _is_bool(v) -> bool:
    return isinstance(v, bool)


def validate(manifest: dict, signoff: dict, inventory: list,
             checkpoint: str) -> dict:
    """Every refusal reason, gathered before anything touches a remote."""
    if not manifest.get("formal"):
        raise PublishError(
            "packet is a rehearsal, not a formal checkpoint: it names no "
            "checkpoint and no shadow-state commit. Re-generate it with "
            "--checkpoint and --state-commit.")
    if manifest.get("desk") != DESK_IDENTITY:
        raise PublishError("packet desk is %r, expected %r"
                           % (manifest.get("desk"), DESK_IDENTITY))
    if checkpoint not in CHECKPOINTS:
        raise PublishError("unknown checkpoint %r" % checkpoint)
    if manifest.get("checkpoint") != checkpoint:
        raise PublishError("packet is for checkpoint %r but %r was requested"
                           % (manifest.get("checkpoint"), checkpoint))

    if signoff.get("signoff_schema") != SIGNOFF_SCHEMA:
        raise PublishError("sign-off schema is %r, expected %r"
                           % (signoff.get("signoff_schema"), SIGNOFF_SCHEMA))
    for field, want in (("automated_package_id", manifest["deterministic_sha256"]),
                        ("state_commit", manifest["state_commit"]),
                        ("checkpoint", checkpoint),
                        ("desk", DESK_IDENTITY),
                        ("latest_shadow_day", manifest["latest_shadow_day"]),
                        ("review_mode", manifest["review_mode"]),
                        ("queue_algorithm", manifest["queue_algorithm"])):
        if signoff.get(field) != want:
            raise PublishError(
                "sign-off %s is %r but the package says %r — the sign-off does "
                "not belong to this package" % (field, signoff.get(field), want))

    day = manifest["latest_shadow_day"]
    need = CHECKPOINTS[checkpoint]
    if day is None or day < need:
        raise PublishError(
            "checkpoint %s needs shadow_day >= %d; the packet's latest ledger "
            "records shadow_day %r" % (checkpoint, need, day))

    for field in ("reviewer", "attestation"):
        if not str(signoff.get(field) or "").strip():
            raise PublishError("sign-off %s is empty — an unfilled form is not "
                               "evidence of a completed review" % field)
    started = _parse_ts(signoff.get("review_started_utc"), "review_started_utc")
    finished = _parse_ts(signoff.get("review_completed_utc"),
                         "review_completed_utc")
    if finished < started:
        raise PublishError("review_completed_utc precedes review_started_utc")

    verdict = signoff.get("verdict")
    if verdict not in VERDICTS:
        raise PublishError("verdict is %r; expected one of %s"
                           % (verdict, ", ".join(VERDICTS)))

    # -- record completeness --------------------------------------------------
    required = list(manifest["required_review_records"])
    results = signoff.get("records")
    if not isinstance(results, list):
        raise PublishError("sign-off records must be a list")
    seen = []
    for r in results:
        ident = r.get("identity")
        if ident in seen:
            raise PublishError("duplicate review result for %s" % ident)
        seen.append(ident)
    missing = [x for x in required if x not in seen]
    extra = [x for x in seen if x not in required]
    if missing:
        raise PublishError(
            "%d required record(s) have no review result, e.g. %s"
            % (len(missing), missing[0]))
    if extra:
        raise PublishError(
            "%d review result(s) are for records that were not required, "
            "e.g. %s" % (len(extra), extra[0]))

    if signoff["review_mode"] == "focused-queue":
        inv_all = {e["identity"] for e in inventory}
        if set(required) == inv_all and len(inv_all) > len(required):
            raise PublishError("a focused review may not claim whole-corpus "
                               "coverage")
    claimed = signoff.get("records_required")
    if claimed is not None and claimed != len(required):
        raise PublishError("sign-off claims %r required records; the package "
                           "requires %d" % (claimed, len(required)))

    false_checks = []
    for r in results:
        for field in CHECK_FIELDS:
            v = r.get(field)
            if not _is_bool(v):
                raise PublishError(
                    "record %s field %s is %r — every check must be an explicit "
                    "true or false, not a free-text answer"
                    % (r.get("identity"), field, v))
            if v is False:
                false_checks.append("%s.%s" % (r.get("identity"), field))
        if "note" not in r or not isinstance(r["note"], str):
            raise PublishError("record %s has no note field (use \"\" when "
                               "there is nothing to say)" % r.get("identity"))

    # -- anomalies ------------------------------------------------------------
    packet_anomalies = list(manifest.get("anomalies", []))
    disposed = {}
    for item in signoff.get("anomalies", []):
        if not isinstance(item, dict):
            raise PublishError("each anomaly entry must be an object")
        disposed[item.get("anomaly")] = str(item.get("disposition") or "").strip()
    undisposed = [x for x in packet_anomalies if not disposed.get(x)]
    unknown = [x for x in disposed if x not in packet_anomalies]
    if unknown:
        raise PublishError("sign-off disposes anomalies that are not in the "
                           "package, e.g. %r" % unknown[0])
    if len(disposed) < len(packet_anomalies):
        raise PublishError("%d package anomaly/anomalies are absent from the "
                           "sign-off" % (len(packet_anomalies) - len(disposed)))

    # -- verdict consistency --------------------------------------------------
    if verdict == "pass":
        if false_checks:
            raise PublishError(
                "verdict is 'pass' but %d check(s) are false, e.g. %s. Use "
                "'pass_with_findings' or 'fail'."
                % (len(false_checks), false_checks[0]))
        if undisposed:
            raise PublishError(
                "verdict is 'pass' but %d anomaly/anomalies have no "
                "disposition, e.g. %r" % (len(undisposed), undisposed[0]))
    elif verdict == "pass_with_findings":
        if undisposed:
            raise PublishError(
                "verdict is 'pass_with_findings' but %d anomaly/anomalies have "
                "no disposition, e.g. %r" % (len(undisposed), undisposed[0]))
    # 'fail' is publishable as-is: an honest failing review is evidence.

    return {
        "false_checks": len(false_checks),
        "anomalies": len(packet_anomalies),
        "records_reviewed": len(results),
        "verdict": verdict,
    }


def _parse_ts(value, field):
    if not value:
        raise PublishError("sign-off %s is empty" % field)
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        raise PublishError("sign-off %s is not an ISO-8601 timestamp: %r"
                           % (field, value))


# ── git, through argument arrays only ────────────────────────────────────────

def git(args, cwd=None, check=True):
    proc = subprocess.run(["git"] + list(args), cwd=str(cwd) if cwd else None,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True)
    if check and proc.returncode != 0:
        raise PublishError("git %s failed:\n%s"
                           % (" ".join(args[:2]), proc.stdout.strip()))
    return proc


def remote_head(remote: str) -> str:
    proc = git(["ls-remote", "--heads", remote, REVIEW_BRANCH], check=False)
    if proc.returncode != 0:
        raise PublishError("cannot read %s from %s:\n%s"
                           % (REVIEW_BRANCH, remote, proc.stdout.strip()))
    line = proc.stdout.strip()
    return line.split()[0] if line else None


def build_index_line(receipt: dict) -> str:
    return canonical({
        "checkpoint": receipt["checkpoint"],
        "completed_review_id": receipt["completed_review_id"],
        "automated_package_id": receipt["automated_package_id"],
        "state_commit": receipt["state_commit"],
        "latest_ledger_run_id": receipt["latest_ledger_run_id"],
        "latest_shadow_day": receipt["latest_shadow_day"],
        "verdict": receipt["verdict"],
        "reviewer": receipt["reviewer"],
        "review_completed_utc": receipt["review_completed_utc"],
        "corpus_count": receipt["corpus_count"],
    }) + "\n"


README = """# Singapore shadow review evidence

Completed Day 7 / 14 / 30 checkpoint reviews for the `singapore-mindef` shadow
desk, preserved append-only.

This branch is orphan by design. It shares no history with `main` and none with
`shadow/singapore-mindef`, because the state branch is the artifact these
reviews assess — keeping the audit inside its own evidence would destroy the
distinction a later comparison depends on.

Each directory under `reviews/<checkpoint>/<completed-review-id>/` holds the
automated package that was presented, the reviewer's structured sign-off, and a
receipt binding the two. `index.jsonl` is append-only.

Identities:

* **automated package id** — what was presented for review
* **completed-review id** — the review answers and attestation, bound to that
  package
* **the Git commit** — when and by whom that completed review was preserved

None of these is a cryptographic signature, and none establishes a reviewer's
legal identity.

Nothing here is executable, and nothing here is published to the public site.
"""


def prepare(packet: Path, signoff_path: Path, checkpoint: str) -> tuple:
    manifest = load_json(packet / "review_manifest.json", "review manifest")
    signoff = load_json(signoff_path, "sign-off")
    inv_path = packet / "record_inventory.jsonl"
    if not inv_path.is_file():
        raise PublishError("no record_inventory.jsonl in %s" % packet)
    inventory = [json.loads(l) for l in
                 inv_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    for name in PACKET_FILES:
        if not (packet / name).is_file():
            raise PublishError("packet is missing %s" % name)
    assert_packet_clean(packet)
    summary = validate(manifest, signoff, inventory, checkpoint)
    crid = completed_review_id(manifest, signoff)
    receipt = {
        "publisher_version": PUBLISHER_VERSION,
        "desk": DESK_IDENTITY,
        "checkpoint": checkpoint,
        "completed_review_id": crid,
        "automated_package_id": manifest["deterministic_sha256"],
        "signoff_schema": signoff["signoff_schema"],
        "state_commit": manifest["state_commit"],
        "clock_sha256": manifest.get("clock_sha256"),
        "shadow_db_sha256": manifest.get("shadow_db_sha256"),
        "ledger_set_sha256": manifest.get("ledger_set_sha256"),
        "latest_ledger": manifest["latest_ledger"],
        "latest_ledger_run_id": manifest["latest_run_id"],
        "latest_shadow_day": manifest["latest_shadow_day"],
        "corpus_count": manifest["corpus_count"],
        "corpus_range": manifest["corpus_range"],
        "review_mode": manifest["review_mode"],
        "queue_algorithm": manifest["queue_algorithm"],
        "records_required": len(manifest["required_review_records"]),
        "records_reviewed": summary["records_reviewed"],
        "anomaly_count": summary["anomalies"],
        "false_checks": summary["false_checks"],
        "verdict": summary["verdict"],
        "reviewer": signoff["reviewer"],
        "review_started_utc": signoff["review_started_utc"],
        "review_completed_utc": signoff["review_completed_utc"],
        "artifact_sha256": manifest.get("artifact_sha256", {}),
        "signoff_sha256": hashlib.sha256(
            canonical(signoff).encode("utf-8")).hexdigest(),
        "not_a_signature": (
            "These identifiers bind answers to a corpus. They are not a "
            "cryptographic signature and do not verify the reviewer's identity."),
    }
    return manifest, signoff, crid, receipt


def publish(packet: Path, signoff_path: Path, remote: str, checkpoint: str,
            expected_head: str, bootstrap: bool, do_publish: bool) -> dict:
    manifest, signoff, crid, receipt = prepare(packet, signoff_path, checkpoint)

    head = remote_head(remote)
    if bootstrap:
        if head is not None:
            raise PublishError("--bootstrap given but %s already exists at %s"
                               % (REVIEW_BRANCH, head[:12]))
    else:
        if head is None:
            raise PublishError(
                "%s does not exist on %s. Pass --bootstrap to create it."
                % (REVIEW_BRANCH, remote))
        if expected_head is None:
            raise PublishError("--expected-head is required when the branch "
                               "exists (current head is %s)" % head)
        if expected_head != head:
            raise PublishError(
                "remote head is %s, not the expected %s — another writer moved "
                "the branch. Re-read it and retry." % (head, expected_head))

    result = {
        "completed_review_id": crid,
        "automated_package_id": manifest["deterministic_sha256"],
        "checkpoint": checkpoint,
        "verdict": receipt["verdict"],
        "remote_head_before": head,
        "published": False,
        "action": None,
        "branch": REVIEW_BRANCH,
    }

    tmp = Path(tempfile.mkdtemp(prefix="review-publish-"))
    try:
        work = tmp / "work"
        if bootstrap:
            git(["init", "--quiet", "-b", REVIEW_BRANCH, str(work)])
            git(["remote", "add", "origin", remote], cwd=work)
        else:
            git(["clone", "--quiet", "--branch", REVIEW_BRANCH,
                 "--single-branch", remote, str(work)])
        git(["config", "user.name", "shadow-review-publisher"], cwd=work)
        git(["config", "user.email", "review@localhost"], cwd=work)

        rel = Path("reviews") / checkpoint / crid
        target = work / rel
        if target.exists():
            # Append-only: identical content is a no-op, different content is a
            # refusal. A failed review must never be quietly replaced.
            same = True
            for name in PACKET_FILES:
                if not (target / name).is_file() or \
                        (target / name).read_bytes() != (packet / name).read_bytes():
                    same = False
            if (target / "signoff.json").is_file():
                existing = json.loads(
                    (target / "signoff.json").read_text(encoding="utf-8"))
                if canonical(existing) != canonical(signoff):
                    same = False
            else:
                same = False
            if same:
                result["action"] = "idempotent-no-op"
                result["published"] = True
                return result
            raise PublishError(
                "completed review %s already exists with different content. "
                "Review evidence is append-only; publish a new review under its "
                "own id instead." % crid[:16])

        # Existing evidence must never be rewritten.
        existing_paths = set()
        if not bootstrap:
            for p in (work / "reviews").rglob("*") if (work / "reviews").exists() else []:
                if p.is_file():
                    existing_paths.add((p.relative_to(work),
                                        hashlib.sha256(p.read_bytes()).hexdigest()))
            for p, _ in existing_paths:
                if ".github" in p.parts:
                    raise PublishError("the review branch already contains %s, "
                                       "which it must not" % p)

        target.mkdir(parents=True)
        for name in PACKET_FILES:
            shutil.copyfile(packet / name, target / name)
        (target / "signoff.json").write_text(
            json.dumps(signoff, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        (target / "receipt.json").write_text(
            json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        if not (work / "README.md").exists():
            (work / "README.md").write_text(README, encoding="utf-8")
        index = work / "index.jsonl"
        prior = index.read_text(encoding="utf-8") if index.exists() else ""
        siblings = [json.loads(l) for l in prior.splitlines() if l.strip()]
        same_checkpoint = [s for s in siblings if s["checkpoint"] == checkpoint]
        if same_checkpoint:
            receipt["supersedes_nothing"] = True
            receipt["other_reviews_at_this_checkpoint"] = sorted(
                s["completed_review_id"] for s in same_checkpoint)
            (target / "receipt.json").write_text(
                json.dumps(receipt, indent=1, sort_keys=True) + "\n",
                encoding="utf-8")
        index.write_text(prior + build_index_line(receipt), encoding="utf-8")

        # Nothing outside the allowlist may be committed.
        proc = git(["status", "--porcelain", "--untracked-files=all"], cwd=work)
        for line in proc.stdout.splitlines():
            path = line[3:].strip()
            allowed = (path == "README.md" or path == "index.jsonl"
                       or path.startswith("reviews/"))
            if not allowed:
                raise PublishError("refusing to commit unexpected path: %s" % path)

        git(["add", "--", "README.md", "index.jsonl", "reviews"], cwd=work)
        message = ("review(%s): %s %s\n\n"
                   "completed-review-id %s\n"
                   "automated-package-id %s\n"
                   "state-commit %s\n"
                   "reviewer %s\n"
                   % (checkpoint, receipt["verdict"], crid[:12], crid,
                      receipt["automated_package_id"], receipt["state_commit"],
                      receipt["reviewer"]))
        git(["commit", "--quiet", "-m", message], cwd=work)

        if not do_publish:
            result["action"] = "dry-run"
            result["prepared_commit"] = git(["rev-parse", "HEAD"],
                                            cwd=work).stdout.strip()
            return result

        # Re-read the head immediately before pushing: a writer may have moved
        # it while this packet was being prepared.
        head_now = remote_head(remote)
        if head_now != head:
            raise PublishError(
                "remote head moved from %s to %s while the review was being "
                "prepared — nothing was pushed"
                % ((head or "<none>")[:12], (head_now or "<none>")[:12]))
        push = git(["push", "origin",
                    "%s:refs/heads/%s" % (REVIEW_BRANCH, REVIEW_BRANCH)],
                   cwd=work, check=False)
        if push.returncode != 0:
            raise PublishError("push refused (no force is ever attempted):\n%s"
                               % push.stdout.strip())
        result["published"] = True
        result["action"] = "bootstrap" if bootstrap else "fast-forward"
        result["remote_head_after"] = remote_head(remote)
        return result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument("--packet", required=True)
    p.add_argument("--signoff", required=True)
    p.add_argument("--remote", required=True,
                   help="git remote URL or local bare repository path")
    p.add_argument("--checkpoint", required=True, choices=sorted(CHECKPOINTS))
    p.add_argument("--expected-head", default=None,
                   help="current %s head; required unless --bootstrap"
                        % REVIEW_BRANCH)
    p.add_argument("--bootstrap", action="store_true",
                   help="create the orphan review branch (first publication only)")
    p.add_argument("--publish", action="store_true",
                   help="actually update the remote. Without this the run "
                        "validates and prepares only.")
    args = p.parse_args(argv)

    try:
        r = publish(Path(args.packet), Path(args.signoff), args.remote,
                    args.checkpoint, args.expected_head, args.bootstrap,
                    args.publish)
    except PublishError as exc:
        print("publication refused: %s" % exc, file=sys.stderr)
        return 2

    print("branch              : %s" % r["branch"])
    print("checkpoint          : %s" % r["checkpoint"])
    print("verdict             : %s" % r["verdict"])
    print("completed-review id : %s" % r["completed_review_id"])
    print("automated package id: %s" % r["automated_package_id"])
    print("action              : %s" % r["action"])
    if r["action"] == "dry-run":
        print("\nNothing was pushed. Re-run with --publish to preserve it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
