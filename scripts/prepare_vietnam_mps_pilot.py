#!/usr/bin/env python3
"""Prepare a commit-bound Vietnam MPS production pilot on a disposable DB.

This does NOT authorize a live desk, an automatic collector, source retention
rights, or a write to the tracked database. Every proposed publication is
explicitly reviewed by a person against the named immutable shadow commit.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.collection.vietnam_sources import SOURCES
from scripts import review_vietnam_shadow_state as formal
from scripts import review_vietnam_ministry_state as ministry

SCHEMA = "vietnam-mps-pilot-authorization/1"
PILOT_SOURCE = "vn_mps_foreign_affairs_vi"
MAX_RECORDS = 10
CHECKS = ("source_page_opened", "title_matches", "date_matches",
          "body_matches", "publisher_matches", "no_challenge_text")
AUDIT_SQL = """
CREATE TABLE IF NOT EXISTS vietnam_pilot_imports (
    url TEXT PRIMARY KEY,
    source_slug TEXT NOT NULL,
    source_identity TEXT NOT NULL UNIQUE,
    content_sha256 TEXT NOT NULL,
    capture_sha256 TEXT NOT NULL,
    state_commit TEXT NOT NULL,
    state_tree TEXT NOT NULL,
    approval_reviewer TEXT NOT NULL,
    approval_at_utc TEXT NOT NULL,
    rights_basis TEXT NOT NULL,
    published_date TEXT NOT NULL
)
"""


class Refused(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def iso_instant(value):
    require(isinstance(value, str), "approval instant missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Refused("invalid approval instant") from exc
    require(parsed.utcoffset() is not None, "approval instant lacks timezone")
    return value


def read_approval(path, state_commit):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    require(isinstance(data, dict), "approval must be an object")
    require(data.get("schema") == SCHEMA, "unrecognized approval schema")
    require(data.get("source_slug") == PILOT_SOURCE, "pilot limited to MPS foreign affairs")
    require(data.get("state_commit") == state_commit, "approval belongs to another state commit")
    reviewer = data.get("reviewer")
    require(isinstance(reviewer, str) and len(reviewer.strip()) >= 3,
            "named human reviewer required")
    iso_instant(data.get("reviewed_at_utc"))
    items = data.get("records")
    require(isinstance(items, list) and 0 < len(items) <= MAX_RECORDS,
            "approval must select 1–10 individual records")
    identities = set()
    for item in items:
        require(isinstance(item, dict), "approval record must be an object")
        ident, digest = item.get("source_identity"), item.get("content_sha256")
        require(isinstance(ident, str) and SOURCES[PILOT_SOURCE].prefix in ident,
                "missing MPS record identity")
        require(ident.startswith(SOURCES[PILOT_SOURCE].prefix),
                "foreign source identity")
        require(ident not in identities, "duplicate approval identity")
        identities.add(ident)
        require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest),
                "version sha256 required")
        checks = item.get("checks")
        require(isinstance(checks, dict) and all(checks.get(k) is True for k in CHECKS),
                "all six human source-integrity checks must be explicitly true")
        require(item.get("reuse_approved") is True,
                "explicit rights/reuse approval required for each record")
        basis = item.get("rights_basis")
        require(isinstance(basis, str) and len(basis.strip()) >= 20,
                "specific per-record rights basis required")
    return data


def candidates(evidence, approval):
    require(evidence["source_slug"] == PILOT_SOURCE, "foreign ministry evidence")
    require(evidence["clock"] is not None and evidence["successes"] > 0,
            "no durable successful remote collection")
    require(evidence["runs"][-1]["health"] == "ok", "last stored run is not healthy")
    records = {r["source_identity"]: r for r in evidence["records"]}
    versions = {(v["source_identity"], v["content_sha256"]): v
                for v in evidence["versions"]}
    observations = {(o["run_id"], o["source_identity"]): o
                    for o in evidence["observations"]}
    planned = []
    for choice in approval["records"]:
        ident, digest = choice["source_identity"], choice["content_sha256"]
        record = records.get(ident)
        version = versions.get((ident, digest))
        require(record is not None and version is not None, "approved record/version not in state")
        require(record["current_content_sha256"] == digest,
                "approved version is no longer current in pinned state")
        require(version["body_status"] == "text" and bool(version["text_original"].strip()),
                "non-text or empty body cannot enter pilot")
        obs = observations.get((version["first_seen_run"], ident))
        require(obs is not None and obs["content_sha256"] == digest
                and obs["capture_sha256"] == version["first_capture_sha256"],
                "version has no matching first capture observation")
        require(not json.loads(obs["anomalies_json"]), "unresolved article anomaly")
        require(record["url"] == record["canonical_url"]
                and SOURCES[PILOT_SOURCE].identity(record["url"]) == ident,
                "invalid source identity")
        planned.append({"record": record, "version": version, "observation": obs,
                        "approval": choice})
    return sorted(planned, key=lambda p: p["record"]["url"])


def apply_to_copy(db_path, planned, authorization, provenance):
    target = Path(db_path).resolve()
    require(target.is_file(), "target must be an existing migrated disposable DB")
    require(target != (ROOT / "pla_watch.db").resolve()
            and ROOT not in target.parents, "refusing any in-repository database")
    require(not target.is_symlink(), "refusing a symlink target")
    inserted = already = 0
    con = sqlite3.connect(str(target))
    try:
        con.execute("PRAGMA foreign_keys=ON")
        require(con.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                "destination database failed integrity check")
        require({"articles", "sources", "desks", "institutions"} <=
                {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")},
                "destination has not been migrated")
        con.execute("BEGIN IMMEDIATE")
        con.execute(AUDIT_SQL)
        desk = con.execute("SELECT public_status FROM desks WHERE desk_id='vietnam'").fetchone()
        if desk is None:
            con.execute("INSERT INTO desks (desk_id,display_name,jurisdiction_code,"
                        "default_timezone,default_calendar,supported_language_tags,"
                        "active,public_status) VALUES (?,?,?,?,?,?,?,?)",
                        ("vietnam", "Vietnam ministry pilot (not live)", "VN",
                         "Asia/Ho_Chi_Minh", "gregorian", '["vi"]', 0, "shadow"))
        else:
            require(desk[0] == "shadow", "destination Vietnam desk already public")
        inst = con.execute("SELECT desk_id FROM institutions WHERE institution_id='vn_mps'").fetchone()
        if inst is None:
            con.execute("INSERT INTO institutions "
                        "(institution_id,desk_id,display_name,name_original,institution_type)"
                        " VALUES (?,?,?,?,?)",
                        ("vn_mps", "vietnam", "Ministry of Public Security", "Bộ Công an", "other"))
        else:
            require(inst[0] == "vietnam", "institution belongs to another desk")
        src = con.execute("SELECT id,desk_id,enabled,is_active FROM sources "
                          "WHERE slug=?", (PILOT_SOURCE,)).fetchone()
        if src is None:
            cur = con.execute("INSERT INTO sources "
                "(slug,display_name,base_url,language,is_active,desk_id,institution_id,"
                "language_tag,authority_tier,enabled,listing_endpoints,notes)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (PILOT_SOURCE, "Bộ Công an — Thông tin Đối ngoại",
                 "https://bocongan.gov.vn", "vi", 0, "vietnam", "vn_mps",
                 "vi", "A", 0, json.dumps([SOURCES[PILOT_SOURCE].listing]),
                 "Staged human-reviewed pilot; no production collector enabled"))
            source_id = cur.lastrowid
        else:
            require(src[1:] == ("vietnam", 0, 0), "existing source is active or mismatched")
            source_id = src[0]
        for row in planned:
            record, version, obs, choice = (row[k] for k in
                                            ("record", "version", "observation", "approval"))
            url = record["url"]
            expected = (version["content_sha256"], version["title_original"],
                        version["text_original"], record["published_date"], source_id)
            existing = con.execute("SELECT content_hash,title_original,text_original,"
                                   "published_date,source_id FROM articles WHERE url=?", (url,)).fetchone()
            if existing is not None:
                audit = con.execute("SELECT state_commit,content_sha256,source_identity "
                                    "FROM vietnam_pilot_imports WHERE url=?", (url,)).fetchone()
                require(tuple(existing) == expected
                        and audit == (provenance["state_commit"],
                                      version["content_sha256"], record["source_identity"]),
                        "existing URL is different or lacks matching pilot audit")
                already += 1
                continue
            con.execute("INSERT INTO articles "
                        "(url,content_hash,source_id,title_original,text_original,"
                        "published_date,scraped_at) VALUES (?,?,?,?,?,?,?)",
                        (url, *expected[:1], source_id, version["title_original"],
                         version["text_original"], record["published_date"], obs["retrieved_at"]))
            con.execute("INSERT INTO vietnam_pilot_imports VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (url, PILOT_SOURCE, record["source_identity"],
                         version["content_sha256"], obs["capture_sha256"],
                         provenance["state_commit"], provenance["state_tree"],
                         authorization["reviewer"], authorization["reviewed_at_utc"],
                         choice["rights_basis"].strip(), record["published_date"]))
            inserted += 1
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return {"inserted": inserted, "already_present": already}


def prepare(state_repo, state_commit, approval_path, into=None):
    require(re.fullmatch(r"[0-9a-f]{40}", state_commit) is not None,
            "full commit SHA required")
    source = SOURCES[PILOT_SOURCE]
    repo = formal.resolve_state_repo(state_repo)
    bound = formal.verify_state_commit(repo, state_commit, source.state_branch)
    approval = read_approval(approval_path, state_commit)
    with tempfile.TemporaryDirectory(prefix="ipr-vn-mps-pilot-") as tmp:
        state = formal.export_state_tree(repo, state_commit, Path(tmp) / "state")
        evidence = ministry.review(state, PILOT_SOURCE)
        planned = candidates(evidence, approval)
    report = {"kind": "vietnam-mps-accelerated-pilot/1", "source": PILOT_SOURCE,
              "state_commit": state_commit, "state_tree": bound["state_tree"],
              "approved_records": len(planned), "approved_urls":
              [p["record"]["url"] for p in planned],
              "production_write_authorized": False,
              "full_desk_qualified": False, "daily_collection_enabled": False}
    if into is not None:
        report.update(apply_to_copy(into, planned, approval, bound))
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-repo", type=Path, required=True)
    ap.add_argument("--state-commit", required=True)
    ap.add_argument("--approval", type=Path, required=True)
    ap.add_argument("--into-disposable-db", type=Path)
    args = ap.parse_args(argv)
    try:
        print(json.dumps(prepare(args.state_repo, args.state_commit, args.approval,
                                 args.into_disposable_db), indent=2, ensure_ascii=False))
        return 0
    except (Refused, ValueError, OSError, sqlite3.Error, formal.ReviewError) as exc:
        print("Vietnam pilot refused: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
