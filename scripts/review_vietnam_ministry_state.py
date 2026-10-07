#!/usr/bin/env python3
"""Read-only ministry rehearsal evidence and commit-bound Day 7/14/30 packets.

Formal inputs come only from the named source branch commit, never its checkout.
Automated packets do not complete human review or qualify the desk.
"""
import argparse
import hashlib
import json
import sqlite3
import re
import tempfile
from datetime import date, datetime
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from core.collection.vietnam_sources import SOURCES, content_sha256, visible_date
from scripts import review_vietnam_shadow_state as formal
from scripts.shadow_collect_vietnam_ministry import load_source
from scripts.publish_shadow_review import strict_loads, PublishError


def loads(text):
    return strict_loads(text, "ministry evidence")


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def external(path):
    path = Path(path)
    require(not path.is_symlink(), "symlink directory refused")
    resolved = path.resolve()
    require(resolved != REPO and REPO not in resolved.parents, "directory must be outside checkout")
    return resolved


def inventory(state):
    result = {}
    for path in sorted(state.rglob("*")):
        require(not path.is_symlink(), "symlink in state refused")
        if path.is_file():
            name = path.relative_to(state).as_posix()
            require(name in ("clock.json", "shadow.db") or name.startswith("ledger/")
                    or name.startswith("captures/"), "unexpected state file: " + name)
            result[name] = sha(path.read_bytes())
    return result


def review(state_dir, slug):
    state = external(state_dir)
    profile = SOURCES[slug]
    before = inventory(state)
    ledgers = [loads(p.read_text()) for p in sorted((state / "ledger").glob("*.json"))]
    require(bool(ledgers), "no ledgers")
    runs = {}
    capture_index = {}
    previous = None
    for entry in ledgers:
        require(entry["desk_id"] == "vietnam" and entry["source_slug"] == slug,
                "foreign source ledger")
        require(entry["content_hash_rule"] == profile.hash_rule, "foreign content rule")
        run_id = entry["run_id"]
        require(run_id not in runs, "duplicate run identity")
        require(entry["state_sha256_before"] == previous, "broken database hash chain")
        previous = entry["state_sha256_after"]
        runs[run_id] = entry
        require(len(entry["requests"]) <= entry["request_ceiling"], "request ceiling exceeded")
        for cap in entry["captures"]:
            digest = cap["payload_sha256"]
            require(len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "bad capture identity")
            path = state / "captures" / (digest + ".bin")
            require(path.is_file() and sha(path.read_bytes()) == digest, "capture missing or changed")
            require(path.stat().st_size == cap["payload_bytes"], "capture length mismatch")
            capture_index[(run_id, digest)] = cap
    clock_path = state / "clock.json"
    clock = loads(clock_path.read_text()) if clock_path.exists() else None
    if clock:
        first = runs.get(clock["day_zero_run_id"])
        require(first is not None and first["health"] == "ok", "clock borrows an unsuccessful run")
        require(clock["day_zero_utc"] == first["finished_utc"], "clock date mismatch")
    db = state / "shadow.db"
    require(previous == before.get("shadow.db"), "latest database hash mismatch")
    records, versions, observations, metadata = [], [], [], []
    if db.exists():
        with sqlite3.connect(db.as_uri() + "?mode=ro&immutable=1", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            require(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "database corrupt")
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            require(tables == {"shadow_records", "shadow_versions", "shadow_observations", "shadow_metadata"},
                    "unexpected database schema")
            expected = dict(formal.EXPECTED_COLUMNS, shadow_metadata=("run_id", "source_identity", "metadata_json"))
            for table, columns in expected.items():
                require(tuple(r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)) == columns,
                        "unexpected database columns")
            records = [dict(r) for r in conn.execute("SELECT * FROM shadow_records ORDER BY source_identity")]
            versions = [dict(r) for r in conn.execute("SELECT * FROM shadow_versions ORDER BY source_identity,content_sha256")]
            observations = [dict(r) for r in conn.execute("SELECT * FROM shadow_observations ORDER BY run_id,source_identity")]
            metadata = [dict(r) for r in conn.execute("SELECT * FROM shadow_metadata ORDER BY run_id,source_identity")]
    record_index = {r["source_identity"]: r for r in records}
    version_index = {}
    for v in versions:
        blocks = loads(v["blocks_json"])
        digest = content_sha256(profile.hash_rule, v["title_original"], v["lead_original"], blocks)
        require(v["content_hash_rule"] == profile.hash_rule and v["content_sha256"] == digest,
                "content version mismatch")
        text = "\n".join(([v["lead_original"]] if v["lead_original"] else []) + [t for _, t in blocks])
        require(v["text_original"] == text, "assembled text mismatch")
        require(v["source_identity"] in record_index, "orphan version")
        require((v["first_seen_run"], v["first_capture_sha256"]) in capture_index, "version capture missing")
        version_index[(v["source_identity"], digest)] = v
    metadata_index = {(m["run_id"], m["source_identity"]): loads(m["metadata_json"]) for m in metadata}
    require(set(metadata_index) == {(o["run_id"], o["source_identity"]) for o in observations},
            "missing or orphan source metadata")
    for r in records:
        ident = r["source_identity"]
        require(r["source_slug"] == slug and profile.identity(r["url"]) == ident
                and r["canonical_url"] == r["url"], "record identity mismatch")
        require(r["language_tag"] == "vi" and r["publication_kind"] == profile.publication_kind,
                "language or publication kind mismatch")
        require(r["published_at_utc"] is None and visible_date(r["published_at_original"]) == r["published_date"],
                "publication date or invented instant")
        require((ident, r["current_content_sha256"]) in version_index, "current version missing")
        require(r["version_count"] == sum(i == ident for i, _ in version_index), "version count mismatch")
    for o in observations:
        key = (o["run_id"], o["source_identity"])
        require(o["run_id"] in runs and o["source_identity"] in record_index, "orphan observation")
        require((o["source_identity"], o["content_sha256"]) in version_index, "observation version missing")
        cap = capture_index.get((o["run_id"], o["capture_sha256"]))
        require(cap is not None and cap["url"] == o["requested_url"] and
                o["requested_url"] == o["final_url"] == o["canonical_url"] and
                profile.identity(o["requested_url"]) == o["source_identity"], "observation capture identity mismatch")
        m = metadata_index[key]
        require(m["publisher"] == profile.publisher and m["family"] == profile.family
                and m["language"] == "vi" and m["issuer"] is None and m["legal_effective_date"] is None,
                "source attribution mismatch")
        require(m["visible_publication_stamp"] == o["published_at_original"] and
                o["published_at_utc"] is None, "observation date mismatch")
    for run_id, entry in runs.items():
        own = [o for o in observations if o["run_id"] == run_id]
        require(len(own) == sum(entry[k] for k in ("new_records", "changed", "reverted", "unchanged")),
                "run observation count mismatch")
        for outcome, counter in (("new", "new_records"), ("changed", "changed"),
                                 ("reverted", "reverted"), ("unchanged", "unchanged")):
            require(sum(o["outcome"] == outcome for o in own) == entry[counter], "outcome count mismatch")
    require(inventory(state) == before, "review changed state")
    result = {"review_schema": "vietnam-ministry-rehearsal/1", "source_slug": slug,
              "family": profile.family, "language": "vi", "rehearsal_only": True,
              "qualification": None, "owner_signoff": None, "state_commit": None,
              "clock": clock, "inputs": before, "records": records, "versions": versions,
              "observations": observations, "source_metadata": metadata,
              "runs": ledgers, "successes": sum(e["health"] == "ok" for e in ledgers),
              "failures": sum(e["health"] == "fail" for e in ledgers)}
    result["review_sha256"] = sha(json.dumps(result, sort_keys=True, ensure_ascii=False,
                                             separators=(",", ":")).encode())
    return result


def package_sha256(manifest, texts):
    facts = {k: v for k, v in manifest.items() if k not in ("deterministic_sha256", "artifact_sha256")}
    return sha(json.dumps({"manifest": facts, "artifacts": texts}, sort_keys=True,
                          ensure_ascii=False, separators=(",", ":")).encode())


def build(state_repo, state_commit, slug, checkpoint, as_of, out_dir):
    """Export trusted Git objects and package the complete source corpus."""
    require(checkpoint in formal.CHECKPOINTS, "unknown checkpoint")
    date.fromisoformat(as_of)
    out = external(out_dir)
    repo = formal.resolve_state_repo(state_repo)
    require(out != repo and repo not in out.parents and out not in repo.parents,
            "output overlaps state repository")
    source = load_source(slug)
    provenance = formal.verify_state_commit(repo, state_commit, source.state_branch)
    require(not out.exists() or not any(out.iterdir()), "output directory must be empty")
    with tempfile.TemporaryDirectory(prefix="vn-ministry-review-") as temp:
        state = formal.export_state_tree(repo, state_commit, Path(temp) / "state")
        evidence = review(state, slug)
        require(evidence["clock"] is not None, "no successful remote clock")
        ledgers = [dict(e, _filename=p.name) for e, p in zip(
            evidence["runs"], sorted((state / "ledger").glob("*.json")))]
        for e in ledgers:
            require(all(k in e for k in formal.LEDGER_REQUIRED), "incomplete ledger")
            require(re.fullmatch(r"[0-9a-f]{40}", e["collector_commit"]) is not None,
                    "collector commit must be a full SHA")
            require(e["target_date_source"] in formal.TARGET_DATE_SOURCES,
                    "unknown target date provenance")
        anomalies, facts = formal.validate_runs(state, ledgers,
            evidence["inputs"]["shadow.db"], SOURCES[slug].hash_rule)
        anomalies += sorted({json.dumps(a, sort_keys=True, ensure_ascii=False)
                             for e in ledgers for a in e["anomalies"]})
        successes = [e for e in ledgers if e["result"] in formal.TERMINAL_OK]
        require(bool(successes), "no successful collecting run")
        latest_day = (datetime.fromisoformat(successes[-1]["finished_utc"])
                      - datetime.fromisoformat(facts["clock"]["day_zero_utc"])).days
        records = evidence["records"]
        manifest = {
            "tool": "scripts/review_vietnam_ministry_state.py", "tool_version": "2.0.0",
            "signoff_schema": formal.SIGNOFF_SCHEMA, "queue_algorithm": formal.QUEUE_ALGORITHM,
            "desk": "vietnam", "source_slug": slug, "family": SOURCES[slug].family,
            "publisher": SOURCES[slug].publisher, "language": "vi",
            "state_branch": source.state_branch, "state_commit": state_commit,
            "state_tree": provenance["state_tree"], "state_ref": provenance["state_ref"],
            "provenance": "git-verified-tree/1", "formal": True,
            "checkpoint": checkpoint, "as_of": as_of,
            "checkpoint_reached": latest_day is not None and latest_day >= formal.CHECKPOINTS[checkpoint],
            "latest_shadow_day": latest_day, "latest_run_id": ledgers[-1]["run_id"],
            "latest_collector_commit": ledgers[-1]["collector_commit"],
            "day_zero_utc": facts["clock"]["day_zero_utc"],
            "collecting_days": facts["collecting_days"],
            "missing_collecting_days": facts["missing_days"],
            "consecutive_collecting_days": facts["consecutive_collecting_days"],
            "window_coverage": facts["window_coverage"], "uncovered_dates": facts["uncovered_dates"],
            "required_collecting_days": 30, "input_sha256": evidence["inputs"],
            "required_review_records": sorted(r["source_identity"] for r in records),
            "anomalies": anomalies, "allowed_verdicts": list(formal.VERDICTS if records else formal.VERDICTS[1:]),
            "qualification": None, "owner_signoff": None,
        }
        texts = {"record_inventory.jsonl": "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in records),
                 "run_inventory.jsonl": "".join(json.dumps(e, sort_keys=True, ensure_ascii=False) + "\n" for e in ledgers),
                 "corpus_evidence.json": json.dumps(evidence, sort_keys=True, ensure_ascii=False, indent=2) + "\n"}
        manifest["deterministic_sha256"] = package_sha256(manifest, texts)
        signoff = formal.signoff_template(manifest)
        signoff["source_slug"] = slug
        texts["signoff_template.json"] = json.dumps(signoff, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
        texts["review_report.md"] = (
            "# Vietnam ministry complete-corpus review\n\n"
            "Automated evidence only; human review is incomplete. No qualification.\n\n"
            "Source: `%s`; publisher: %s; family: %s; Vietnamese as published.\n\n"
            "State commit: `%s`; tree: `%s`; checkpoint: %s; reached: %s.\n\n"
            "Read every record and every version in corpus_evidence.json against its source page. "
            "Check visible publication dates separately from raw metadata and date anomalies; "
            "verify publisher, byline and unset issuer independently. Dispose every anomaly. "
            "A quiet corpus establishes listing egress only. Failed attempts live in Actions artifacts, "
            "not successful-state history; obtain them for the checkpoint.\n\n"
            "Fill signoff_template.json and validate with --check-signoff. "
            "An early packet is not a completed Day 7/14/30 review. "
            "Preserving completed review evidence needs separate owner approval; no ministry publisher exists.\n"
        ) % (slug, SOURCES[slug].publisher, SOURCES[slug].family, state_commit,
             provenance["state_tree"], checkpoint, manifest["checkpoint_reached"])
        manifest["artifact_sha256"] = {n: sha(t.encode()) for n, t in sorted(texts.items())}
        texts["review_manifest.json"] = json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
        out.mkdir(parents=True, exist_ok=True)
        for name, text in texts.items():
            (out / name).write_text(text, encoding="utf-8")
    return manifest


def check_signoff(packet, signoff_path):
    packet = external(packet)
    require(not any(p.is_symlink() for p in packet.iterdir()), "symlink packet refused")
    manifest = loads((packet / "review_manifest.json").read_text())
    source = load_source(manifest["source_slug"])
    require(manifest["state_branch"] == source.state_branch and manifest["formal"] is True,
            "foreign or rehearsal packet")
    expected_files = {"record_inventory.jsonl", "run_inventory.jsonl", "corpus_evidence.json",
                      "signoff_template.json", "review_report.md"}
    require(set(manifest["artifact_sha256"]) == expected_files, "incomplete artifact inventory")
    require({p.name for p in packet.iterdir()} <= expected_files | {"review_manifest.json", "signoff.json"},
            "unexpected packet file")
    for name, digest in manifest["artifact_sha256"].items():
        require(sha((packet / name).read_bytes()) == digest, "packet artifact changed")
    texts = {n: (packet / n).read_text(encoding="utf-8") for n in
             ("record_inventory.jsonl", "run_inventory.jsonl", "corpus_evidence.json")}
    require(package_sha256(manifest, texts) == manifest["deterministic_sha256"],
            "packet identity changed")
    signoff = loads(Path(signoff_path).read_text())
    problems = formal.validate_signoff(manifest, signoff)
    for field, identity in (("records", "identity"), ("anomalies", "anomaly")):
        rows = signoff.get(field) or []
        if len(rows) != len({row.get(identity) for row in rows}):
            problems.append("duplicate %s answers" % field)
    if any(ord(c) < 32 or ord(c) == 127 for c in str(signoff.get("reviewer", ""))):
        problems.append("reviewer contains control characters")
    if signoff.get("source_slug") != manifest["source_slug"]:
        problems.append("signoff belongs to another source")
    if not manifest["checkpoint_reached"]:
        problems.append("checkpoint not reached")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", choices=sorted(SOURCES))
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--state-dir")
    mode.add_argument("--state-repo")
    ap.add_argument("--state-commit")
    ap.add_argument("--checkpoint", choices=sorted(formal.CHECKPOINTS))
    ap.add_argument("--as-of")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--check-signoff")
    args = ap.parse_args(argv)
    try:
        if args.check_signoff:
            problems = check_signoff(args.out_dir, args.check_signoff)
            require(not problems, "; ".join(problems))
            print("Complete human signoff; no qualification or publication implied.")
            return 0
        require(args.source is not None, "--source required")
        if args.state_repo:
            require(all((args.state_commit, args.checkpoint, args.as_of)),
                    "formal mode needs commit, checkpoint and as-of")
            result = build(args.state_repo, args.state_commit, args.source,
                           args.checkpoint, args.as_of, args.out_dir)
            print(result["deterministic_sha256"])
        else:
            require(args.state_dir is not None and not any((args.state_commit, args.checkpoint, args.as_of)),
                    "rehearsal mode uses only --state-dir")
            state, out = external(args.state_dir), external(args.out_dir)
            require(out != state and state not in out.parents and out not in state.parents,
                    "output overlaps state")
            result = review(state, args.source)
            out.mkdir(parents=True, exist_ok=True)
            require(not any(out.iterdir()), "output directory must be empty")
            (out / "review.json").write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(result["review_sha256"])
    except (ValueError, OSError, sqlite3.Error, KeyError, formal.ReviewError, PublishError) as exc:
        print("review refused: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
