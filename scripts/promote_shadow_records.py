#!/usr/bin/env python3
"""
Promote a verified shadow corpus into a production database.

This is the rehearsal of the step that ends a shadow evaluation: the desk's
records stop being evidence about a candidate source and become part of the
corpus the public surface counts. It is deliberately a separate program from
the correction overlay, because the two answer different questions. The overlay
says what a captured value should have been. Promotion says which records are
fit to leave the shadow desk at all, and those are not the same judgement — a
record can be perfectly corrected and still unfit, which is what a hold is for.

What it will not do
-------------------
It will not promote from an unverified overlay, an overlay bound to a different
database or state commit, or a holds file that describes something else. It
will not promote a held record, and it will not promote silently: every row it
writes carries the capture identity it came from and the digest of the overlay
that produced its text, so a promoted record can always be traced back to the
byte stream it was built on and to the corrections applied to it.

It writes only to the database it is given, which must not be the tracked one.
Promotion into production is an owner decision and a separate, reviewed act;
this program exists so that decision can be taken against a rehearsed, measured
result rather than a description of one.

Determinism and idempotence
---------------------------
Two runs against the same inputs produce the same rows, and a second run over a
database that already holds them inserts nothing. Promotion is identified by
canonical URL, which is the shadow corpus's own identity and is unique within
it; a URL already present is left exactly as it is rather than rewritten, so
re-running can never quietly change a record that is already public.

Usage:
    .venv/bin/python scripts/promote_shadow_records.py \
        --state-dir  <copy of the shadow state/> \
        --state-repo <the state clone, for the commit binding> \
        --manifest   shadow/singapore_mindef/manifest.json \
        --into       /path/to/disposable.db \
        [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.correct_shadow_bodies as cc                      # noqa: E402

PROMOTION_KIND = "shadow-promotion/1"

#: Columns every promoted row fills. `passed_relevance` is left NULL on
#: purpose: promotion moves documents, it does not judge them, and a record
#: arriving with a verdict nobody made would be a lie the analysis queue then
#: believes. They drain as backlog exactly like any other unanalyzed article.
PROMOTED_PROCESSING_STATE = None


class Refused(SystemExit):
    """Promotion refused. Always names the file and the reason."""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ── gates ─────────────────────────────────────────────────────────────────────

def require_verified_overlay(state: Path, state_repo: Optional[Path]) -> str:
    """Refuse unless the overlay verifies against THIS state, and return its
    digest so every promoted row can name the corrections it carries."""
    files = cc.existing_corrections(state)
    if not files:
        raise Refused(
            "refusing to promote: no correction overlay is present. An "
            "uncorrected corpus may be a legitimate thing to promote, but it "
            "is not a thing this program can tell apart from a missing one.")
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cc.verify(state, state_repo)
    if rc != 0:
        sys.stdout.write(buf.getvalue())
        raise Refused("refusing to promote: the correction overlay does not verify.")
    return cc.overlay_digest(state)


def promotable(state: Path, state_repo: Optional[Path]):
    """(rows, holds, overlay_digest, holds_digest) — corrected, minus holds."""
    digest = require_verified_overlay(state, state_repo)
    holds = cc.load_holds(state, state_repo)
    view = cc.corrected_view(state, state_repo)

    con = cc.read_only(state / "shadow.db")
    meta = {r[0]: r for r in con.execute(
        "select url, source_slug, published_date, language_tag, "
        "publication_kind, content_sha256, capture_sha256, retrieved_at, "
        "first_seen_run from shadow_records")}
    con.close()

    rows, incomplete = [], []
    for url in sorted(view):
        if url in holds:
            continue
        _, slug, pub, lang, kind, content_sha, capture_sha, retrieved, run = meta[url]
        # Every promoted row asserts which captured byte stream it came from.
        # A record missing that provenance cannot make the assertion, and
        # promoting it with a null would be the assertion made anyway, in a
        # form nothing downstream can question.
        if not (content_sha and capture_sha and retrieved):
            incomplete.append(url)
            continue
        rows.append({
            "url": url,
            "source_slug": slug,
            "title": view[url]["title"],
            "body": view[url]["body"],
            "published_date": pub,
            "language_tag": lang,
            "publication_kind": kind,
            "capture_content_sha256": content_sha,
            "capture_sha256": capture_sha,
            "captured_at": retrieved,
            "first_seen_run": run,
            "promoted_title_sha256": sha256_text(view[url]["title"]),
            "promoted_body_sha256": sha256_text(view[url]["body"]),
        })

    if incomplete:
        raise Refused(
            "refusing to promote: %d record(s) carry no capture provenance, so "
            "a promoted row could not say which bytes it came from:\n  %s"
            % (len(incomplete), "\n  ".join(sorted(incomplete)[:10])))

    urls = [r["url"] for r in rows]
    if len(set(urls)) != len(urls):
        raise Refused("refusing to promote: the corrected view has duplicate URLs.")
    return rows, holds, digest, cc.holds_digest(state)


# ── write ─────────────────────────────────────────────────────────────────────

PROVENANCE_DDL = """
CREATE TABLE IF NOT EXISTS shadow_promotions (
    url                    TEXT PRIMARY KEY,
    desk                   TEXT NOT NULL,
    source_slug            TEXT NOT NULL,
    promoted_at            TEXT NOT NULL,
    state_commit           TEXT,
    state_tree             TEXT,
    database_sha256        TEXT NOT NULL,
    overlay_sha256         TEXT NOT NULL,
    holds_sha256           TEXT,
    capture_content_sha256 TEXT NOT NULL,
    capture_sha256         TEXT NOT NULL,
    captured_at            TEXT NOT NULL,
    first_seen_run         TEXT,
    promoted_title_sha256  TEXT NOT NULL,
    promoted_body_sha256   TEXT NOT NULL
)
"""


def ensure_source(con: sqlite3.Connection, manifest: dict) -> int:
    """The desk's own manifest supplies the source row. Nothing is invented
    here: if the manifest does not declare the slug the shadow records carry,
    that disagreement is the answer, not something to paper over."""
    src = manifest["sources"][0]
    row = con.execute("select id from sources where slug = ?",
                      (src["slug"],)).fetchone()
    if row:
        return row[0]
    cur = con.execute(
        "insert into sources (slug, display_name, base_url, language, "
        "is_active, created_at, desk_id, institution_id, language_tag, "
        "authority_tier, enabled, listing_endpoints, article_url_patterns, "
        "notes) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (src["slug"], src["display_name"], src["base_url"],
         src["language_tag"].split("-")[0], 1, utcnow(),
         manifest["desk"]["desk_id"], src["institution_id"],
         src["language_tag"], src["authority_tier"],
         1 if src.get("enabled") else 0,
         json.dumps(src.get("listing_endpoints", []), ensure_ascii=False),
         json.dumps(src.get("article_url_patterns", []), ensure_ascii=False),
         src.get("notes", "")))
    return cur.lastrowid


def require_desk_manifest(path: Path) -> dict:
    """`--manifest` is the desk's own manifest, not a packet.

    Handing this the corrected-view packet is an easy mistake — both are JSON
    beside each other in the same workflow — and without this it surfaces as a
    `KeyError` or a `TypeError` several frames down, which reads like a bug in
    the promoter rather than a wrong argument."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise Refused("%s is not a desk manifest: it is a %s"
                      % (path, type(doc).__name__))
    desk = doc.get("desk")
    if not isinstance(desk, dict) or not desk.get("desk_id"):
        raise Refused(
            "%s is not a desk manifest: it declares no desk.desk_id. Pass the "
            "desk's manifest (shadow/<desk>/manifest.json), not a packet."
            % path)
    sources = doc.get("sources")
    if not isinstance(sources, list) or not sources:
        raise Refused("%s declares no sources, so no source row can be "
                      "derived from it" % path)
    return doc


def promote(state: Path, state_repo: Optional[Path], manifest_path: Path,
            into: Path, dry_run: bool = False) -> dict:
    if into.resolve() == (REPO_ROOT / "pla_watch.db").resolve():
        raise Refused(
            "refusing to promote into the tracked database. Promotion is an "
            "owner decision taken through the release path, not a side effect "
            "of running this program.")
    manifest = require_desk_manifest(manifest_path)
    rows, holds, overlay_sha, holds_sha = promotable(state, state_repo)
    bind = cc.binding(state, state_repo)

    report = {
        "kind": PROMOTION_KIND,
        "desk": manifest["desk"]["desk_id"],
        "promoted_at": utcnow(),
        "binding": bind,
        "overlay_sha256": overlay_sha,
        "holds_sha256": holds_sha,
        "corpus_records": len(rows) + len(holds),
        "held": sorted(holds),
        "held_count": len(holds),
        "candidates": len(rows),
        "inserted": 0,
        "already_present": 0,
        "dry_run": dry_run,
    }
    if dry_run:
        return report

    con = sqlite3.connect(str(into))
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.execute(PROVENANCE_DDL)
        source_id = ensure_source(con, manifest)
        for r in rows:
            present = con.execute("select 1 from articles where url = ?",
                                  (r["url"],)).fetchone()
            if present:
                report["already_present"] += 1
                continue
            con.execute(
                "insert into articles (url, content_hash, source_id, "
                "title_original, text_original, published_date, scraped_at, "
                "processing_state) values (?,?,?,?,?,?,?,?)",
                (r["url"], r["capture_content_sha256"], source_id,
                 r["title"], r["body"], r["published_date"], r["captured_at"],
                 PROMOTED_PROCESSING_STATE))
            con.execute(
                "insert or replace into shadow_promotions (url, desk, "
                "source_slug, promoted_at, state_commit, state_tree, "
                "database_sha256, overlay_sha256, holds_sha256, "
                "capture_content_sha256, capture_sha256, captured_at, "
                "first_seen_run, promoted_title_sha256, promoted_body_sha256) "
                "values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r["url"], report["desk"], r["source_slug"], report["promoted_at"],
                 bind["state_commit"], bind["state_tree"], bind["database_sha256"],
                 overlay_sha, holds_sha, r["capture_content_sha256"],
                 r["capture_sha256"], r["captured_at"], str(r["first_seen_run"]),
                 r["promoted_title_sha256"], r["promoted_body_sha256"]))
            report["inserted"] += 1
        con.commit()
    finally:
        con.close()
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Promote a verified shadow corpus.")
    ap.add_argument("--state-dir", required=True, type=Path)
    ap.add_argument("--state-repo", type=Path, default=None)
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--into", required=True, type=Path)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    report = promote(a.state_dir, a.state_repo, a.manifest, a.into, a.dry_run)
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
