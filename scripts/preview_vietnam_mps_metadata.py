#!/usr/bin/env python3
"""Vietnam MPS *metadata-only* preview, strictly outside the production corpus.

This is NOT a publication/staging authorization. Re-verifies exact Git shadow
state and writes only identifying metadata plus original IPR draft abstracts
to an isolated SQLite file; the tracked production DB is never opened writable.
No raw capture, publisher article body, or public site output is written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.collection.vietnam_sources import SOURCES
from scripts import prepare_vietnam_mps_review_queue as queue_builder
from scripts import review_vietnam_ministry_state as ministry
from scripts import review_vietnam_shadow_state as formal

SOURCE = "vn_mps_foreign_affairs_vi"
PINNED_COMMIT = "46f6a0e59e25b03868bf7ad600963d6921ee5124"
PINNED_TREE = "9dbc782fd1c36ff3d0374cad7794166c4f21b810"
PINNED_QUEUE = "a32a445f1e6734ca0763ceac30986ce137b305e1130dc447fe40410a2460d582"
SCHEMA = "vietnam-mps-disposable-metadata-preview/1"

# New IPR-authored, deliberately provisional abstracts, never quoted source
# prose. These are editorial drafts, NOT approved public annotations.
DRAFTS = {
    "mps-vi:1791199100": {
        "digest": "dcd9bf2a81c8adab834ae1d1790178b445d67fd6549a2080356cc2444b176b0e",
        "abstract": (
            "Vietnam's public security minister discussed potential security-technology "
            "and industrial cooperation with representatives of two Turkish companies. "
            "The ministry report does not establish a signed procurement or technology-transfer agreement."
        ),
        "review_caution": "Prospective cooperation is not a signed procurement or technology-transfer award.",
    },
    "mps-vi:1791199677": {
        "digest": "c5d67c01fd96a6fb3d453e0d21ada152a69761b8163a512dd27ed8f8b9676691",
        "abstract": (
            "Vietnam's Ministry of Public Security and Concordia University discussed "
            "possible collaboration in training and security-related technology research. "
            "A memorandum mentioned in the report involves Vietnam's education ministry, "
            "not a separately signed MPS-Concordia agreement."
        ),
        "review_caution": "Concordia's education-ministry memorandum must not be attributed to MPS.",
    },
    "mps-vi:1790933646": {
        "digest": "3ba9014700628d467872322bb7182d182f1bee17caea66ecb5e8f9e9ad177726",
        "abstract": (
            "Vietnamese and Myanmar security officials discussed cooperation against "
            "transnational crime. The ministry report describes prior cooperation "
            "agreements separately from proposals for renewed dialogue and additional legal instruments."
        ),
        "review_caution": "Previously signed agreements and proposed new instruments have different status.",
    },
}
INSTITUTION = "vn_mps"
PUBLISHER = "Cổng thông tin điện tử Bộ Công an"
PREVIEW_SQL = """
CREATE TABLE preview_records (
    source_identity TEXT PRIMARY KEY,
    source_slug TEXT NOT NULL,
    canonical_url TEXT NOT NULL UNIQUE,
    title_original TEXT NOT NULL,
    published_date TEXT NOT NULL,
    language_tag TEXT NOT NULL CHECK(language_tag = 'vi'),
    institution_id TEXT NOT NULL CHECK(institution_id = 'vn_mps'),
    publisher TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    capture_sha256 TEXT NOT NULL,
    state_commit TEXT NOT NULL,
    state_tree TEXT NOT NULL,
    draft_abstract TEXT NOT NULL,
    editorial_caution TEXT NOT NULL,
    review_state TEXT NOT NULL CHECK(review_state = 'pending_human_signoff'),
    rights_state TEXT NOT NULL CHECK(rights_state = 'unresolved'),
    production_collision INTEGER NOT NULL CHECK(production_collision IN (0, 1)),
    publication_authorized INTEGER NOT NULL DEFAULT 0 CHECK(publication_authorized = 0),
    original_article_body_retained INTEGER NOT NULL DEFAULT 0 CHECK(original_article_body_retained = 0)
);
"""
ALLOWED_FIELDS = (
    "source_identity", "source_slug", "canonical_url", "title_original",
    "published_date", "language_tag", "institution_id", "publisher",
    "content_sha256", "capture_sha256", "state_commit", "state_tree",
    "draft_abstract", "editorial_caution", "review_state", "rights_state",
    "production_collision", "publication_authorized",
    "original_article_body_retained",
)


class PreviewRefused(ValueError):
    pass


def require(value, message):
    if not value:
        raise PreviewRefused(message)


def digest_bytes(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for piece in iter(lambda: stream.read(64 * 1024), b""):
            h.update(piece)
    return h.hexdigest()


def _outside_repo(path):
    path = Path(path)
    require(not path.is_symlink(), "symbolic link path refused")
    resolved = path.resolve()
    require(resolved != ROOT and ROOT not in resolved.parents,
            "all preview inputs/outputs must be outside repository checkout")
    return resolved


def read_production_snapshot(path):
    path = _outside_repo(path)
    require(path.is_file(), "a distinct, existing production DB snapshot is required")
    old_hash = digest_bytes(path)
    uri = "file:%s?mode=ro&immutable=1" % quote(str(path), safe="/")
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    try:
        require(con.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                "production snapshot integrity check failed")
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        require({"articles", "sources", "desks", "institutions"} <= tables,
                "production snapshot lacks migrated core tables")
        columns = {r[1] for r in con.execute("PRAGMA table_info(articles)")}
        require({"url", "content_hash", "source_id", "title_original", "text_original"} <= columns,
                "production snapshot articles schema differs")
        yield con, old_hash
    finally:
        con.close()
        require(digest_bytes(path) == old_hash, "production snapshot unexpectedly changed")


def verified_queue(state_repo, commit):
    require(commit == PINNED_COMMIT, "preview supports only the pinned three-record pilot")
    repo = formal.resolve_state_repo(state_repo)
    attestation = formal.verify_state_commit(repo, commit, SOURCES[SOURCE].state_branch)
    require(attestation["state_tree"] == PINNED_TREE, "pinned state tree changed")
    with tempfile.TemporaryDirectory(prefix="vn-mps-preview-state-") as temp:
        state = formal.export_state_tree(repo, commit, Path(temp) / "state")
        evidence = ministry.review(state, SOURCE)
        queue = queue_builder.compile_queue(evidence, commit, attestation["state_tree"])
    require(queue["queue_sha256"] == PINNED_QUEUE, "queue proof digest does not match pinned review")
    return queue


def prepare_rows(queue, con):
    require(queue["state_commit"] == PINNED_COMMIT and queue["state_tree"] == PINNED_TREE,
            "source state pin does not match expected review")
    require(queue["queue_sha256"] == PINNED_QUEUE, "queue not independently verified")
    records = queue["records"]
    require(len(records) == 3 and {r["source_identity"] for r in records} == set(DRAFTS),
            "exactly three pinned MPS identities expected")
    require(queue["human_approvals"] == queue["rights_approvals"] == 0
            and not queue["automatic_production_admission"],
            "queue has unexpected automatic approval")
    rows = []
    for r in records:
        ident = r["source_identity"]
        draft = DRAFTS[ident]
        require(r["source_slug"] == SOURCE and r["content_sha256"] == draft["digest"],
                "IPR draft is bound to another source content version")
        require(r["machine_review_candidate"] and not r["machine_blockers"],
                "source record is not mechanically reviewable")
        require(not r["human_source_reviewed"] and not r["reuse_rights_reviewed"]
                and not r["production_publication_authorized"],
                "do not transform an approved record with the unsigned preview")
        require(r["canonical_url"].startswith("https://bocongan.gov.vn/bai-viet/")
                and SOURCES[SOURCE].identity(r["canonical_url"]) == ident,
                "canonical MPS source identity mismatch")
        require(re.fullmatch(r"20\d\d-\d\d-\d\d", r["published_date"]) is not None,
                "source publication date not established")
        require(r["title_original"] and r["first_capture_sha256"],
                "publisher identifying metadata missing")
        collisions = con.execute("SELECT count(*) FROM articles WHERE url = ?",
                                 (r["canonical_url"],)).fetchone()[0]
        require(collisions in (0, 1), "duplicate production URL invariant broken")
        rows.append({
            "source_identity": ident,
            "source_slug": SOURCE,
            "canonical_url": r["canonical_url"],
            "title_original": r["title_original"],
            "published_date": r["published_date"],
            "language_tag": "vi",
            "institution_id": INSTITUTION,
            "publisher": PUBLISHER,
            "content_sha256": r["content_sha256"],
            "capture_sha256": r["first_capture_sha256"],
            "state_commit": PINNED_COMMIT,
            "state_tree": PINNED_TREE,
            "draft_abstract": draft["abstract"],
            "editorial_caution": draft["review_caution"],
            "review_state": "pending_human_signoff",
            "rights_state": "unresolved",
            "production_collision": collisions,
            "publication_authorized": 0,
            "original_article_body_retained": 0,
        })
    return sorted(rows, key=lambda x: (x["published_date"], x["source_identity"]), reverse=True)


def write_preview(path, rows):
    target = _outside_repo(path)
    require(not target.exists(), "preview DB must not already exist")
    require(len(rows) == 3, "three-record exact preview only")
    con = sqlite3.connect(str(target))
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute(PREVIEW_SQL)
        for row in rows:
            require(set(row) == set(ALLOWED_FIELDS), "unknown preview metadata field")
            con.execute("INSERT INTO preview_records (%s) VALUES (%s)" %
                        (",".join(ALLOWED_FIELDS), ",".join("?" for _ in ALLOWED_FIELDS)),
                        tuple(row[k] for k in ALLOWED_FIELDS))
        require(con.execute("SELECT count(*) FROM preview_records").fetchone()[0] == 3,
                "staging preview did not contain three candidates")
        require(con.execute("SELECT count(*) FROM preview_records WHERE "
                            "publication_authorized!=0 OR original_article_body_retained!=0 "
                            "OR rights_state!='unresolved'").fetchone()[0] == 0,
                "unapproved preview contains release or full text")
        require({"preview_records"} ==
                {r[0] for r in con.execute("SELECT name FROM sqlite_master "
                                           "WHERE type='table' AND name NOT LIKE 'sqlite_%'")},
                "preview database must contain only review metadata")
        con.commit()
    except Exception:
        con.rollback()
        con.close()
        target.unlink(missing_ok=True)
        raise
    finally:
        try:
            con.close()
        except Exception:
            pass
    return digest_bytes(target)


def make_preview(state_repo, commit, production_db, out_dir):
    output = _outside_repo(out_dir)
    require(not output.exists(), "output directory must be new")
    queue = verified_queue(state_repo, commit)
    for con, prod_sha in read_production_snapshot(production_db):
        rows = prepare_rows(queue, con)
    output.mkdir(parents=True, exist_ok=False)
    preview = output / "unapproved_metadata_preview.db"
    try:
        db_sha = write_preview(preview, rows)
        report = {
            "schema": SCHEMA,
            "source": SOURCE,
            "source_state_commit": commit,
            "source_state_tree": PINNED_TREE,
            "machine_review_queue_sha256": PINNED_QUEUE,
            "production_snapshot_sha256": prod_sha,
            "isolated_preview_db_sha256": db_sha,
            "records_in_isolated_preview": len(rows),
            "existing_production_url_collisions": sum(x["production_collision"] for x in rows),
            "draft_original_ipr_abstracts": len(rows),
            "human_approvals": 0,
            "rights_approvals": 0,
            "publication_authorizations": 0,
            "full_original_article_bodies_retained": 0,
            "production_articles_inserted": 0,
            "production_database_modified": False,
            "desk_promoted": False,
            "review_status": "blocked_pending_human_rights_and_owner_release",
            "records": [{
                "source_identity": r["source_identity"],
                "canonical_url": r["canonical_url"],
                "published_date": r["published_date"],
                "title_sha256": hashlib.sha256(r["title_original"].encode("utf-8")).hexdigest(),
                "abstract_sha256": hashlib.sha256(r["draft_abstract"].encode("utf-8")).hexdigest(),
                "production_collision": r["production_collision"],
            } for r in rows],
        }
        (output / "preview_manifest.json").write_text(
            json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        return report
    except Exception:
        for child in output.glob("*"):
            if child.is_file():
                child.unlink()
        output.rmdir()
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-repo", type=Path, required=True)
    ap.add_argument("--state-commit", required=True)
    ap.add_argument("--production-snapshot", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        result = make_preview(args.state_repo, args.state_commit,
                              args.production_snapshot, args.out_dir)
        # No publisher article text or even source titles printed.
        print(json.dumps({
            "preview_schema": result["schema"],
            "candidate_count": result["records_in_isolated_preview"],
            "production_collisions": result["existing_production_url_collisions"],
            "production_articles_inserted": 0,
            "human_approvals": 0,
            "rights_approvals": 0,
            "preview_db_sha256": result["isolated_preview_db_sha256"],
        }, sort_keys=True))
        return 0
    except (PreviewRefused, ValueError, OSError, sqlite3.Error, formal.ReviewError) as exc:
        print("Metadata preview refused: %s" % type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
