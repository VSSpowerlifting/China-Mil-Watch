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
Git runs through argument arrays, never a shell string — and an argument array
is not enough on its own: a remote beginning with `-` is refused, because Git
would read it as an option and `--upload-pack=` is a command it executes. The
Git environment is scrubbed of variables that redirect a command elsewhere. The
source repository's own worktree and branch are never checked out or moved.
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

#: The only provenance a publishable packet may claim. A packet whose inputs
#: came from an unverified working copy names a commit it cannot demonstrate it
#: was built from, and preserving that would record evidence about a tree
#: nobody checked.
VERIFIED_PROVENANCE = "git-verified-tree/1"
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

#: Generated beside the packet and deliberately not preserved: the sign-off
#: template is a form, and the generation context is wall-clock and local
#: paths. Naming them is what makes anything *else* in the directory a refusal.
PACKET_SIDECARS = ("signoff_template.json", "signoff.json",
                   "generation_context.json")
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

def _no_duplicate_keys(pairs):
    """
    `json.loads` keeps the last value for a repeated key. A sign-off reading
    `"verdict": "fail"` on one line and `"verdict": "pass"` on another
    therefore publishes as a pass, and the preserved copy is re-serialised so
    the contradiction disappears. Refuse the file instead of picking a side.
    """
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise ValueError("duplicate key %r — a document that says two "
                             "things cannot be evidence of either" % key)
        seen.add(key)
    return dict(pairs)


def strict_loads(text: str, what: str):
    """No duplicate keys, and no NaN/Infinity: neither survives a round trip."""
    try:
        return json.loads(text, object_pairs_hook=_no_duplicate_keys,
                          parse_constant=_refuse_constant)
    except ValueError as exc:
        raise PublishError("%s is not valid JSON: %s" % (what, exc))


def _refuse_constant(name):
    raise ValueError("%s is not a JSON value that can be preserved" % name)


def load_json(path: Path, what: str) -> dict:
    if not path.is_file():
        raise PublishError("no %s at %s" % (what, path))
    return strict_loads(path.read_text(encoding="utf-8"), what)


def assert_packet_clean(packet: Path) -> None:
    for p in sorted(packet.rglob("*")):
        rel = p.relative_to(packet)
        # Checked before anything follows the entry. A symlink is read as its
        # target, so a packet file replaced by one preserves whatever it points
        # at — content nobody reviewed, from outside the packet entirely.
        if p.is_symlink():
            raise PublishError(
                "packet entry %s is a symlink to %s. Preserving it would "
                "record content from outside the packet as the evidence that "
                "was reviewed." % (rel, os.readlink(str(p))))
        if p.is_dir():
            if p.name == ".github" or p.name == "workflows":
                raise PublishError("packet contains %s/ — review evidence "
                                   "carries no workflows" % p.name)
            continue
        if not p.is_file():
            raise PublishError("packet entry %s is not a regular file" % rel)
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
        name = rel.as_posix()
        if name not in PACKET_FILES and name not in PACKET_SIDECARS:
            raise PublishError(
                "packet contains %s, which is neither preserved nor expected. "
                "A file the reviewer read but the branch would not keep makes "
                "the preserved evidence a subset of what was reviewed." % rel)


#: Fields the package id is computed *without*: they are written after it, or
#: they are not content. Re-derived here rather than imported, because the kit
#: and the publisher are separate tools; `tests/test_shadow_review_kit.py` pins
#: them together so drift is caught.
PACKAGE_ID_EXCLUDES = ("deterministic_sha256", "artifact_sha256", "generated")


def recompute_package_id(manifest: dict, inventory: list) -> str:
    """
    The package id over the manifest and inventory as preserved.

    This is what makes a preserved review checkable: the id feeds the
    completed-review id, which is the directory name, so a manifest edited
    after preservation cannot keep the name it is filed under.
    """
    content = {k: v for k, v in manifest.items() if k not in PACKAGE_ID_EXCLUDES}
    payload = json.dumps({"manifest": content, "inventory": inventory},
                         sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assert_packet_matches_its_manifest(packet: Path, manifest: dict,
                                       names=None) -> None:
    """
    The manifest already records what each artifact hashed to when it was
    generated. Nothing checked it, so a packet could be edited after generation
    and still name the original digests. Check it.
    """
    declared = manifest.get("artifact_sha256")
    if not isinstance(declared, dict) or not declared:
        raise PublishError("packet manifest carries no artifact_sha256 — there "
                           "is nothing to verify its own files against")
    wanted = sorted(declared) if names is None else sorted(
        n for n in declared if n in names)
    for name in wanted:
        want = declared[name]
        path = packet / name
        if not path.is_file():
            raise PublishError("manifest names %s, which the packet does not "
                               "contain" % name)
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != want:
            raise PublishError(
                "%s does not match the manifest that describes it (%s, "
                "expected %s) — the packet was altered after it was generated"
                % (name, got[:16], want[:16]))


#: Reviewer-controlled strings that end up in the Git commit message. A newline
#: there forges a trailer: `reviewer` containing "x\nstate-commit <sha>" makes
#: `git log` show a state commit the receipt never named.
COMMIT_MESSAGE_FIELDS = ("reviewer",)


def assert_single_line(value, field: str) -> str:
    text = str(value)
    bad = [c for c in text if c == "\n" or c == "\r" or ord(c) < 0x20
           or ord(c) == 0x7f]
    if bad:
        raise PublishError(
            "sign-off %s contains a control character (%r). It is written into "
            "the preserved commit message, where a newline forges a trailer "
            "line that contradicts the receipt." % (field, bad[0]))
    return text


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
    if manifest.get("provenance") != VERIFIED_PROVENANCE:
        raise PublishError(
            "packet provenance is %r, expected %r. The packet names a state "
            "commit its inputs were never checked against — re-generate it "
            "with --state-repo so the reviewed bytes come from the committed "
            "tree." % (manifest.get("provenance"), VERIFIED_PROVENANCE))
    for field in ("state_commit", "state_tree"):
        if not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get(field) or "")):
            raise PublishError(
                "packet %s is %r; a verified packet carries the full 40-"
                "character object name" % (field, manifest.get(field)))
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
    for field in COMMIT_MESSAGE_FIELDS:
        assert_single_line(signoff.get(field), field)
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
        ts = datetime.fromisoformat(str(value))
    except ValueError:
        raise PublishError("sign-off %s is not an ISO-8601 timestamp: %r"
                           % (field, value))
    if ts.tzinfo is None:
        raise PublishError(
            "sign-off %s has no timezone: %r. The field is named _utc and is "
            "preserved verbatim, so a naive timestamp records a moment nobody "
            "can place. Write it as ...+00:00." % (field, value))
    return ts


# ── git, through argument arrays only ────────────────────────────────────────

#: Git environment that would silently redirect a command somewhere else. The
#: publisher builds its own repository in a temporary directory; an inherited
#: GIT_DIR or a hooks path from the caller's environment has no business
#: reaching it.
UNSAFE_GIT_ENV = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE",
    "GIT_CONFIG", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS", "GIT_SSH", "GIT_SSH_COMMAND",
    "GIT_EXTERNAL_DIFF", "GIT_PROXY_COMMAND", "GIT_ASKPASS",
)


def assert_not_an_option(value: str, what: str) -> str:
    """
    An argument array is not enough on its own.

    Git parses a leading `-` as an option wherever it appears, so a remote
    named `--upload-pack=...` is a command Git runs, not a place it fetches
    from. That is arbitrary execution reached through an ordinary-looking
    argument, and no `--` separator helps: `ls-remote` takes the remote before
    any separator would apply.
    """
    if str(value).startswith("-"):
        raise PublishError(
            "%s may not begin with '-': %r would be read by git as an option, "
            "not a %s. Use an absolute path or a full URL."
            % (what, value, what))
    return value


def git(args, cwd=None, check=True):
    env = {k: v for k, v in os.environ.items() if k not in UNSAFE_GIT_ENV}
    env["GIT_TERMINAL_PROMPT"] = "0"
    proc = subprocess.run(["git"] + list(args), cwd=str(cwd) if cwd else None,
                          env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True)
    if check and proc.returncode != 0:
        raise PublishError("git %s failed:\n%s"
                           % (" ".join(args[:2]), proc.stdout.strip()))
    return proc


def remote_head(remote: str) -> str:
    assert_not_an_option(remote, "remote")
    proc = git(["ls-remote", "--heads", "--", remote, REVIEW_BRANCH], check=False)
    if proc.returncode != 0:
        raise PublishError("cannot read %s from %s:\n%s"
                           % (REVIEW_BRANCH, remote, proc.stdout.strip()))
    line = proc.stdout.strip()
    return line.split()[0] if line else None


def snapshot_existing(work: Path) -> dict:
    """Every preserved evidence file, by content, before anything is added."""
    out = {}
    root = work / "reviews"
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            out[p.relative_to(work).as_posix()] = hashlib.sha256(
                p.read_bytes()).hexdigest()
    return out


def assert_existing_evidence_is_intact(work: Path, expected: dict) -> None:
    """
    Preserved reviews are append-only, and `index.jsonl` only ever grows.

    The publisher used to gather these digests and never compare them. A
    review already on the branch could be rewritten — a `fail` receipt edited
    to `pass` — and the next publication would build cheerfully on top of it.
    """
    for rel, want in sorted(expected.items()):
        path = work / rel
        if not path.is_file():
            raise PublishError(
                "%s is preserved on the review branch but is missing from the "
                "tree being published. Review evidence is append-only." % rel)
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != want:
            raise PublishError(
                "%s was rewritten (%s, expected %s). A review already on the "
                "branch may never be edited; publish a correction under its "
                "own id." % (rel, got[:16], want[:16]))


def assert_branch_is_self_consistent(work: Path) -> None:
    """
    Every review already on the branch still hashes to the id it is filed
    under.

    The directory name is the completed-review id: a hash over the sign-off
    bound to the package it answers. So a preserved sign-off or manifest that
    has been edited no longer names its own directory, and a preserved report
    that has been edited no longer matches the manifest beside it. Checked on
    arrival, because the publisher builds on whatever the remote hands it — and
    a `fail` receipt quietly rewritten to `pass` would otherwise be inherited
    as fact.
    """
    root = work / "reviews"
    seen = {}
    for checkpoint_dir in sorted(
            d for d in (root.iterdir() if root.exists() else []) if d.is_dir()):
        for review in sorted(d for d in checkpoint_dir.iterdir() if d.is_dir()):
            rel = review.relative_to(work).as_posix()
            manifest = load_json(review / "review_manifest.json",
                                 "preserved manifest in %s" % rel)
            signoff = load_json(review / "signoff.json",
                                "preserved sign-off in %s" % rel)
            crid = completed_review_id(manifest, signoff)
            if crid != review.name:
                raise PublishError(
                    "preserved review %s no longer hashes to its own id (%s). "
                    "Its sign-off or manifest was edited after it was "
                    "preserved." % (rel, crid[:16]))
            assert_packet_matches_its_manifest(review, manifest, PACKET_FILES)
            inventory = [strict_loads(l, "preserved inventory in %s" % rel)
                         for l in (review / "record_inventory.jsonl")
                         .read_text(encoding="utf-8").splitlines() if l.strip()]
            if recompute_package_id(manifest, inventory) != \
                    manifest.get("deterministic_sha256"):
                raise PublishError(
                    "preserved review %s no longer hashes to its own package "
                    "id — its manifest or inventory was edited after it was "
                    "preserved." % rel)
            receipt = load_json(review / "receipt.json",
                                "preserved receipt in %s" % rel)
            for field, want in (("completed_review_id", crid),
                                ("automated_package_id",
                                 manifest["deterministic_sha256"]),
                                ("state_commit", manifest["state_commit"]),
                                ("verdict", signoff.get("verdict")),
                                ("reviewer", signoff.get("reviewer"))):
                if receipt.get(field) != want:
                    raise PublishError(
                        "preserved receipt %s/receipt.json disagrees with the "
                        "evidence it describes: %s is %r, the review says %r"
                        % (rel, field, receipt.get(field), want))
            seen[crid] = receipt

    index = work / "index.jsonl"
    if not index.exists():
        if seen:
            raise PublishError("reviews are preserved but index.jsonl is gone")
        return
    for n, line in enumerate(index.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        entry = strict_loads(line, "index.jsonl line %d" % n)
        crid = entry.get("completed_review_id")
        if crid not in seen:
            raise PublishError(
                "index.jsonl line %d names review %r, which is not preserved "
                "on the branch" % (n, crid))
        if line + "\n" != build_index_line(seen[crid]):
            raise PublishError(
                "index.jsonl line %d does not match the receipt it indexes "
                "(review %s)" % (n, str(crid)[:16]))
    if len(seen) != len([l for l in index.read_text(encoding="utf-8")
                         .splitlines() if l.strip()]):
        raise PublishError("index.jsonl and the preserved reviews disagree on "
                           "how many reviews exist")


def assert_index_only_grew(work: Path, prior: str) -> None:
    """`index.jsonl` is append-only: the old bytes must still be its prefix."""
    text = (work / "index.jsonl").read_text(encoding="utf-8")
    if not text.startswith(prior):
        raise PublishError(
            "index.jsonl was rewritten rather than appended to. Existing lines "
            "must survive byte for byte.")


def build_index_line(receipt: dict) -> str:
    return canonical({
        "checkpoint": receipt["checkpoint"],
        "completed_review_id": receipt["completed_review_id"],
        "automated_package_id": receipt["automated_package_id"],
        "state_commit": receipt["state_commit"],
        "state_tree": receipt["state_tree"],
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
    inventory = [strict_loads(l, "record inventory") for l in
                 inv_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    for name in PACKET_FILES:
        if not (packet / name).is_file():
            raise PublishError("packet is missing %s" % name)
    assert_packet_clean(packet)
    assert_packet_matches_its_manifest(packet, manifest)
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
        "state_tree": manifest["state_tree"],
        "state_ref": manifest.get("state_ref"),
        "provenance": manifest["provenance"],
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
    assert_not_an_option(remote, "remote")
    if expected_head is not None:
        assert_not_an_option(expected_head, "--expected-head")
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
            git(["remote", "add", "--", "origin", remote], cwd=work)
        else:
            git(["clone", "--quiet", "--branch", REVIEW_BRANCH,
                 "--single-branch", "--", remote, str(work)])
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

        # Existing evidence must never be rewritten. Recorded before this
        # publication writes anything, and compared again after, so a bug here
        # cannot quietly replace a review that is already preserved.
        if not bootstrap:
            assert_branch_is_self_consistent(work)
        existing_paths = snapshot_existing(work) if not bootstrap else {}
        for rel in existing_paths:
            if ".github" in Path(rel).parts:
                raise PublishError("the review branch already contains %s, "
                                   "which it must not" % rel)
        assert_existing_evidence_is_intact(work, existing_paths)

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
        if prior and not prior.endswith("\n"):
            raise PublishError("index.jsonl does not end in a newline; a "
                               "partial last line cannot be appended to safely")
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

        # Re-checked after this publication wrote its own files: append-only
        # is a property of the tree that leaves, not only of the tree that
        # arrived.
        assert_existing_evidence_is_intact(work, existing_paths)
        assert_index_only_grew(work, prior)

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
                   "state-tree %s\n"
                   "reviewer %s\n"
                   % (checkpoint, receipt["verdict"], crid[:12], crid,
                      receipt["automated_package_id"], receipt["state_commit"],
                      receipt["state_tree"], receipt["reviewer"]))
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
