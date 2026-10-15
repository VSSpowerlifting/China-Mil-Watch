#!/usr/bin/env python3
"""Encrypt retained Actions ZIPs, including failed reruns, without unpacking them.

Owner-controlled *offline* shell only. Input is the read-only JSON inventory
from scripts/inventory_ipr_actions_artifact_expiry.py plus owner-downloaded ZIPs
named artifact-<GitHub artifact ID>.zip. No GitHub, publisher or other network
calls, no repo writes, no unencrypted TAR on backup, no raw bodies in output.
The operator still must authenticate downloaded ZIPs/permissions and place
encrypted ciphertext on separately protected off-GitHub storage.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

SCHEMA = "ipr-actions-attempt-encrypted-sidecar/1"
SOURCE_SCHEMA = "ipr-actions-artifact-retention-inventory/1"
REPO = "VSSpowerlifting/China-Mil-Watch"
FPR = re.compile(r"[0-9a-fA-F]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_INVENTORY = 16 * 1024 * 1024
MAX_ARTIFACTS = 100
MAX_ITEM_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 3 * 1024 * 1024 * 1024


class Hold(ValueError):
    """Fixed diagnostic only: no publisher/capture/source content."""


def check(ok, code):
    if not ok:
        raise Hold(code)


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_inventory(path, run_id):
    source = Path(path)
    check(source.is_file() and not source.is_symlink()
          and source.stat().st_size <= MAX_INVENTORY, "inventory_invalid")
    raw = source.read_bytes()
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeError):
        raise Hold("inventory_not_json") from None
    check(type(obj) is dict and obj.get("schema") == SOURCE_SCHEMA
          and obj.get("repo") == REPO
          and obj.get("production_cutover_authorized") is False
          and obj.get("actual_artifact_bytes_downloaded_or_hashed") is False
          and type(obj.get("runs")) is list, "inventory_schema_or_policy_invalid")
    matches = [run for run in obj["runs"]
               if type(run) is dict and run.get("run_id") == run_id]
    check(len(matches) == 1, "run_missing_or_ambiguous_in_inventory")
    run = matches[0]
    attempt_count = run.get("latest_run_attempt")
    check(type(attempt_count) is int and 1 <= attempt_count <= 50
          and type(run.get("artifacts")) is list, "attempt_inventory_invalid")
    items = run["artifacts"]
    check(1 <= len(items) <= MAX_ARTIFACTS, "artifact_count_invalid")
    unique = set()
    for item in items:
        check(type(item) is dict and type(item.get("id")) is int
              and item["id"] > 0 and item["id"] not in unique
              and type(item.get("name")) is str and len(item["name"]) <= 256
              and type(item.get("name_attempt")) is int
              and 1 <= item["name_attempt"] <= attempt_count
              and item.get("expired") is False, "artifact_identity_or_expiry_invalid")
        unique.add(item["id"])
    # For reruns, jobs must be genuinely documented per attempt, rather
    # than trusting a green top-level result and two plausible filenames.
    if attempt_count > 1:
        jobs = run.get("historical_attempt_jobs")
        check(type(jobs) is list and
              sorted(x.get("attempt") for x in jobs if type(x) is dict)
                  == list(range(1, attempt_count + 1)),
              "rerun_job_attempt_inventory_missing")
        for attempt in jobs:
            check(type(attempt.get("jobs")) is list and attempt["jobs"],
                  "rerun_job_rows_missing")
            for job in attempt["jobs"]:
                check(type(job) is dict and type(job.get("job_id")) is int
                      and job.get("status") == "completed"
                      and job.get("conclusion") in ("success", "failure",
                          "cancelled", "skipped", "neutral", "timed_out"),
                      "rerun_job_status_invalid")
        check({x["name_attempt"] for x in items} ==
              set(range(1, attempt_count + 1)),
              "one_or_more_attempt_artifacts_missing")
    return hashlib.sha256(raw).hexdigest(), run


def _stage(directory, items):
    root = Path(directory)
    check(root.is_dir() and not root.is_symlink(),
          "artifact_staging_directory_invalid")
    expected = {"artifact-%d.zip" % art["id"] for art in items}
    filenames = {p.name for p in root.iterdir()}
    check(filenames == expected, "unexpected_or_missing_staged_artifact")
    files, total = [], 0
    for item in sorted(items, key=lambda a: a["id"]):
        path = root / ("artifact-%d.zip" % item["id"])
        check(path.is_file() and not path.is_symlink(),
              "staged_artifact_not_a_regular_file")
        stat = path.stat()
        check(0 < stat.st_size <= MAX_ITEM_BYTES, "staged_artifact_size_invalid")
        # ZIPs are handled as opaque bytes: verify container structure only,
        # without unzipping third-party original content.
        check(zipfile.is_zipfile(path), "staged_file_not_zip")
        total += stat.st_size
        check(total <= MAX_TOTAL_BYTES, "staged_archive_exceeds_limit")
        files.append({"id": item["id"], "attempt": item["name_attempt"],
                      "bytes": stat.st_size, "sha256": digest(path),
                      "path": path, "stat": (stat.st_dev, stat.st_ino,
                      stat.st_size, stat.st_mtime_ns)})
    return files


def _gpg_args(home):
    if home is None:
        return []
    path = Path(home)
    check(path.is_dir() and not path.is_symlink(), "gpg_home_invalid")
    return ["--homedir", str(path)]


def _gpg_key(fingerprint, home):
    check(type(fingerprint) is str and FPR.fullmatch(fingerprint),
          "recipient_fingerprint_invalid")
    try:
        proc = subprocess.run(
            ["gpg", *_gpg_args(home), "--batch", "--no-tty",
             "--with-colons", "--list-keys", fingerprint],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Hold("gpg_unavailable") from None
    check(proc.returncode == 0 and len(proc.stdout) < 1024 * 1024,
          "recipient_key_unavailable")
    keys = [line.split(":")[9].upper() for line in proc.stdout.decode(
        "utf-8", errors="replace").splitlines()
        if line.startswith("fpr:") and len(line.split(":")) > 9]
    check(fingerprint.upper() in keys, "recipient_key_identity_mismatch")
    return fingerprint.upper()


def _backup_target(path):
    target = Path(path)
    check(not target.exists() and not target.is_symlink()
          and target.parent.is_dir() and not target.parent.is_symlink(),
          "encrypted_target_unsafe_or_exists")
    return target


def _manifest(run, inventory_sha, files):
    return {
        "schema": SCHEMA, "run_id": run["run_id"],
        "workflow": run["workflow"], "event": run["event"],
        "latest_run_attempt": run["latest_run_attempt"],
        "source_inventory_sha256": inventory_sha,
        "case_count": len(files),
        "captured_artifacts": [{
            "id": x["id"], "attempt": x["attempt"],
            "bytes": x["bytes"], "sha256": x["sha256"],
            "archive_member": "artifacts/artifact-%d.zip" % x["id"],
        } for x in files],
        "individual_zip_contents_verified": False,
        "source_rights_approved": False,
        "independent_backup_medium_verified": False,
        "production_cutover_authorized": False,
    }


def create(inventory, run_id, staging_dir, output, recipient, *, gpg_home=None):
    check(type(run_id) is int and run_id > 0, "run_id_invalid")
    inv_sha, run = _read_inventory(inventory, run_id)
    files = _stage(staging_dir, run["artifacts"])
    fingerprint = _gpg_key(recipient, gpg_home)
    manifest = _manifest(run, inv_sha, files)
    manifest_bytes = (json.dumps(manifest, sort_keys=True,
                                 separators=(",", ":")) + "\n").encode()
    target = _backup_target(output)
    fd, partial = tempfile.mkstemp(prefix=".ipr-attempt-", suffix=".gpg.part",
                                   dir=str(target.parent))
    os.close(fd)
    os.chmod(partial, 0o600)
    proc = None
    try:
        try:
            proc = subprocess.Popen(
                ["gpg", *_gpg_args(gpg_home), "--batch", "--no-tty",
                 "--yes",  # only overwrites OUR mkstemp .part file
                 "--trust-model", "always", "--recipient", fingerprint,
                 "--output", partial, "--encrypt"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            try:
                with tarfile.open(fileobj=proc.stdin, mode="w|") as bundle:
                    meta = tarfile.TarInfo("manifest.json")
                    meta.size, meta.mode, meta.mtime = len(manifest_bytes), 0o600, 0
                    bundle.addfile(meta, io.BytesIO(manifest_bytes))
                    for item in files:
                        info = tarfile.TarInfo("artifacts/artifact-%d.zip" % item["id"])
                        info.size, info.mode, info.mtime = item["bytes"], 0o600, 0
                        with open(item["path"], "rb") as stream:
                            bundle.addfile(info, stream)
                        current = item["path"].stat()
                        check((current.st_dev, current.st_ino,
                               current.st_size, current.st_mtime_ns) == item["stat"]
                              and digest(item["path"]) == item["sha256"],
                              "staged_artifact_changed_during_export")
                proc.stdin.close()
                check(proc.wait(timeout=180) == 0, "encryption_failed")
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
        except (OSError, BrokenPipeError, subprocess.TimeoutExpired,
                tarfile.TarError):
            raise Hold("encrypted_sidecar_unavailable") from None
        with open(partial, "rb") as ciphertext:
            os.fsync(ciphertext.fileno())
        check(Path(partial).stat().st_size > 0, "empty_encrypted_sidecar")
        encrypted_sha = digest(partial)
        try:
            os.link(partial, target)  # never replace a separately created backup
        except OSError:
            raise Hold("backup_target_race_or_unsafe") from None
        return {
            "schema": SCHEMA, "status": "encrypted_backup_created",
            "run_id": run_id, "attempt_artifact_count": len(files),
            "ciphertext_sha256": encrypted_sha,
            "ciphertext_bytes": target.stat().st_size,
            "source_inventory_sha256": inv_sha,
            "plaintext_tar_written_to_disk": False,
            "independent_backup_medium_verified": False,
            "source_rights_approved": False,
            "production_cutover_authorized": False,
        }
    finally:
        try:
            os.unlink(partial)
        except FileNotFoundError:
            pass


def restore(encrypted, expected_cipher_sha, expected_inventory_sha,
            run_id, *, scratch_dir, gpg_home=None):
    """Verify encrypted ZIP sidecar as a bounded stream; NO plaintext TAR on disk."""
    check(type(run_id) is int and run_id > 0, "run_id_invalid")
    check(type(expected_cipher_sha) is str and SHA256.fullmatch(expected_cipher_sha)
          and type(expected_inventory_sha) is str
          and SHA256.fullmatch(expected_inventory_sha),
          "expected_digest_invalid")
    root, backup = Path(scratch_dir), Path(encrypted)
    check(root.is_dir() and not root.is_symlink()
          and (root.stat().st_mode & 0o077) == 0
          and backup.is_file() and not backup.is_symlink()
          and not backup.resolve().is_relative_to(root.resolve()),
          "restore_paths_unsafe")
    check(digest(backup) == expected_cipher_sha,
          "encrypted_sidecar_checksum_mismatch")
    try:
        proc = subprocess.Popen(
            ["gpg", *_gpg_args(gpg_home), "--batch", "--no-tty",
             "--decrypt", str(backup)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        raise Hold("decryption_unavailable") from None
    try:
        try:
            with tarfile.open(fileobj=proc.stdout, mode="r|") as bundle:
                first = bundle.next()
                check(first is not None and first.name == "manifest.json"
                      and first.isfile() and 0 < first.size <= MAX_INVENTORY,
                      "sidecar_manifest_missing_or_unsafe")
                stream = bundle.extractfile(first)
                check(stream is not None, "sidecar_manifest_missing_or_unsafe")
                with stream:
                    raw_manifest = stream.read(MAX_INVENTORY + 1)
                check(len(raw_manifest) == first.size,
                      "sidecar_manifest_length_invalid")
                manifest = json.loads(raw_manifest)
                check(type(manifest) is dict
                      and manifest.get("schema") == SCHEMA
                      and manifest.get("run_id") == run_id
                      and manifest.get("source_inventory_sha256") == expected_inventory_sha
                      and manifest.get("individual_zip_contents_verified") is False
                      and manifest.get("source_rights_approved") is False
                      and manifest.get("production_cutover_authorized") is False,
                      "sidecar_manifest_mismatch")
                items = manifest.get("captured_artifacts")
                check(type(items) is list and 1 <= len(items) <= MAX_ARTIFACTS,
                      "sidecar_items_invalid")
                expected = {}
                total = 0
                for item in items:
                    check(type(item) is dict and type(item.get("id")) is int
                          and item["id"] > 0 and type(item.get("bytes")) is int
                          and 0 < item["bytes"] <= MAX_ITEM_BYTES and
                          type(item.get("sha256")) is str and
                          SHA256.fullmatch(item["sha256"]) and
                          item.get("archive_member") ==
                          "artifacts/artifact-%d.zip" % item["id"],
                          "sidecar_item_malformed")
                    name = item["archive_member"]
                    check(name not in expected, "sidecar_member_duplicate")
                    expected[name] = item
                    total += item["bytes"]
                    check(total <= MAX_TOTAL_BYTES, "sidecar_total_exceeds_limit")
                actual = set()
                for member in bundle:
                    check(member.isfile() and member.name in expected and
                          member.name not in actual and
                          member.name == member.name.lstrip("/") and
                          ".." not in member.name.split("/"),
                          "sidecar_member_unsafe_or_extra")
                    item = expected[member.name]
                    check(member.size == item["bytes"], "sidecar_item_length_mismatch")
                    stream = bundle.extractfile(member)
                    check(stream is not None, "sidecar_item_unreadable")
                    sha = hashlib.sha256()
                    with stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b""):
                            sha.update(block)
                    check(sha.hexdigest() == item["sha256"],
                          "sidecar_item_checksum_mismatch")
                    actual.add(member.name)
                check(actual == set(expected), "sidecar_members_missing")
            proc.stdout.close()
            check(proc.wait(timeout=180) == 0, "decryption_failed")
        except (tarfile.TarError, UnicodeError, ValueError, TypeError, OSError) as exc:
            if isinstance(exc, Hold):
                raise
            raise Hold("sidecar_stream_invalid") from None
        except subprocess.TimeoutExpired:
            raise Hold("decryption_timeout") from None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        if proc.stdout is not None and not proc.stdout.closed:
            proc.stdout.close()
    return {
        "schema": SCHEMA, "status": "decrypted_sidecar_verified",
        "run_id": run_id, "artifact_count_verified": len(items),
        "encrypted_sha256": expected_cipher_sha,
        "all_opaque_zip_sha256_verified": True,
        "individual_zip_contents_verified": False,
        "plaintext_tar_written_to_disk": False,
        "independent_backup_medium_verified": False,
        "production_cutover_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    create_cmd = actions.add_parser("create")
    create_cmd.add_argument("--inventory", required=True)
    create_cmd.add_argument("--run-id", type=int, required=True)
    create_cmd.add_argument("--zip-dir", required=True)
    create_cmd.add_argument("--encrypted-output", required=True)
    create_cmd.add_argument("--recipient-fingerprint", required=True)
    create_cmd.add_argument("--gpg-home")
    recover = actions.add_parser("restore")
    recover.add_argument("--encrypted-input", required=True)
    recover.add_argument("--expected-cipher-sha256", required=True)
    recover.add_argument("--expected-inventory-sha256", required=True)
    recover.add_argument("--run-id", type=int, required=True)
    recover.add_argument("--scratch-dir", required=True)
    recover.add_argument("--gpg-home")
    args = parser.parse_args(argv)
    try:
        if args.action == "create":
            report = create(args.inventory, args.run_id, args.zip_dir,
                            args.encrypted_output, args.recipient_fingerprint,
                            gpg_home=args.gpg_home)
        else:
            report = restore(args.encrypted_input, args.expected_cipher_sha256,
                             args.expected_inventory_sha256, args.run_id,
                             scratch_dir=args.scratch_dir, gpg_home=args.gpg_home)
    except (Hold, OSError, UnicodeError) as exc:
        print(json.dumps({
            "schema": SCHEMA, "status": "HOLD",
            "reason": str(exc) if isinstance(exc, Hold) else "operator_io_failure",
            "production_cutover_authorized": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
