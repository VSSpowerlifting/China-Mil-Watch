#!/usr/bin/env python3
"""Read-only, source-bound review of a LOCAL ministry shadow rehearsal.

Does not certify a checkpoint, signoff, state commit or qualification. The VGP
formal review tool remains unchanged; ministries have not been dispatched.
"""
import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from core.collection.vietnam_sources import SOURCES, content_sha256, visible_date


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
    ledgers = [json.loads(p.read_text()) for p in sorted((state / "ledger").glob("*.json"))]
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
        if runs:
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
    clock = json.loads(clock_path.read_text()) if clock_path.exists() else None
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
            records = [dict(r) for r in conn.execute("SELECT * FROM shadow_records ORDER BY source_identity")]
            versions = [dict(r) for r in conn.execute("SELECT * FROM shadow_versions ORDER BY source_identity,content_sha256")]
            observations = [dict(r) for r in conn.execute("SELECT * FROM shadow_observations ORDER BY run_id,source_identity")]
            metadata = [dict(r) for r in conn.execute("SELECT * FROM shadow_metadata ORDER BY run_id,source_identity")]
    record_index = {r["source_identity"]: r for r in records}
    version_index = {}
    for v in versions:
        blocks = json.loads(v["blocks_json"])
        digest = content_sha256(profile.hash_rule, v["title_original"], v["lead_original"], blocks)
        require(v["content_hash_rule"] == profile.hash_rule and v["content_sha256"] == digest,
                "content version mismatch")
        text = "\n".join(([v["lead_original"]] if v["lead_original"] else []) + [t for _, t in blocks])
        require(v["text_original"] == text, "assembled text mismatch")
        require(v["source_identity"] in record_index, "orphan version")
        require((v["first_seen_run"], v["first_capture_sha256"]) in capture_index, "version capture missing")
        version_index[(v["source_identity"], digest)] = v
    metadata_index = {(m["run_id"], m["source_identity"]): json.loads(m["metadata_json"]) for m in metadata}
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", required=True, choices=sorted(SOURCES))
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)
    try:
        state, out = external(args.state_dir), external(args.out_dir)
        require(out != state and state not in out.parents and out not in state.parents,
                "output overlaps state")
        result = review(state, args.source)
        out.mkdir(parents=True, exist_ok=True)
        require(not any(out.iterdir()), "output directory must be empty")
        (out / "review.json").write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n")
    except (ValueError, OSError, sqlite3.Error, KeyError) as exc:
        print("review refused: %s" % exc, file=sys.stderr)
        return 2
    print(result["review_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
