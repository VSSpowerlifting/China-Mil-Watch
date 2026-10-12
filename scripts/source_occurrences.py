"""Offline archive inventory / local replay. Never collects, stores native rows or publishes."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

from core.collection.contract import ExtractedDocument
from core.manifests import load_all_desks
from core.source_occurrences import (
    Batch, Metadata, NativeRecord, Observation, OccurrenceError, Relation,
    actual_date, actual_time, canonical, digest, locator, require, valid_digest,
    validate_batch,
)
from processing.dedup import _HOST_AUTHORITY_SLUG, dedup_articles_detailed, title_hash, url_host
from processing.deduplicator import deduplicate_detailed
from processing.metadata import compute_content_hash, normalize_article
from scripts.reconcile_db import read_only
from storage.source_occurrences import commit_batch, initialize, read_batches, write_report

ROOT = Path(__file__).resolve().parents[1]


def file_digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def snapshot_guard(path, expected):
    path = Path(path)
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)),
            "snapshot_missing_or_unsafe")
    require(valid_digest(expected), "invalid_snapshot_pin")
    require(not any(Path(str(path) + s).exists() or Path(str(path) + s).is_symlink()
                    for s in ("-wal", "-shm", "-journal")), "snapshot_not_quiescent")
    s = path.stat()
    require(file_digest(path) == expected, "snapshot_digest_mismatch")
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


@contextmanager
def pinned_archive(path, expected):
    """Only externally quiescent, checkpointed input; not a mutable WAL repair.

    Recheck bytes, inode, timestamps and sidecars before/after the existing
    scratch-copy helper. A changing source aborts before batch acceptance.
    """
    before = snapshot_guard(path, expected)
    try:
        with read_only(path) as con:
            require(snapshot_guard(path, expected) == before, "snapshot_changed")
            require(con.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "snapshot_corrupt")
            con.row_factory = sqlite3.Row
            rows = [dict(r) for r in con.execute("SELECT a.*, s.slug AS source_slug, "
                "s.desk_id, s.institution_id FROM articles a LEFT JOIN sources s "
                "ON s.id=a.source_id ORDER BY a.id")]
            sources = [dict(r) for r in con.execute("SELECT s.slug,s.desk_id,s.institution_id, "
                "i.institution_id AS resolved_institution,i.desk_id AS institution_desk, "
                "d.desk_id AS resolved_desk FROM sources s "
                "LEFT JOIN institutions i ON i.institution_id=s.institution_id "
                "LEFT JOIN desks d ON d.desk_id=s.desk_id")]
            for s in sources:
                if s["desk_id"] is not None or s["institution_id"] is not None:
                    require(s["resolved_desk"] == s["desk_id"] and
                            s["resolved_institution"] == s["institution_id"] and
                            s["institution_desk"] == s["desk_id"], "source_identity_mismatch")
            # Native pointers resolve in this exact selected snapshot, not another DAO.
            require(len({r["id"] for r in rows}) == len(rows), "native_identity_invalid")
            yield rows, sources
    except sqlite3.Error:
        raise OccurrenceError("snapshot_schema_or_corruption") from None
    finally:
        require(snapshot_guard(path, expected) == before, "snapshot_changed")


def code_binding():
    files = [ROOT / p for p in ("processing/dedup.py", "processing/deduplicator.py",
        "processing/metadata.py", "core/source_occurrences.py", "storage/source_occurrences.py",
        "scripts/source_occurrences.py", "scripts/source_occurrences_view.py",
        "scripts/reconcile_db.py", "core/collection/contract.py", "core/manifests.py",
        "scraper/sources/sg_mindef.py")]
    files += sorted((ROOT / "desks").glob("*/manifest.json"))
    sha = digest(canonical({str(p.relative_to(ROOT)): file_digest(p) for p in files}))
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    return sha, head


def verified_sources(sources):
    governed = {s.slug: s for cfg in load_all_desks().values() for s in cfg.sources}
    verified = {}
    for s in sources:
        cfg = governed.get(s["slug"])
        if cfg is None:
            continue
        require((cfg.desk_id, cfg.institution_id) == (s["desk_id"], s["institution_id"]),
                "source_identity_mismatch")
        hosts = {url_host(cfg.base_url)} | {h for h, slug in _HOST_AUTHORITY_SLUG.items()
                                          if slug == cfg.slug}
        verified[cfg.slug] = (cfg.desk_id, cfg.institution_id, hosts)
    return verified


def validate_input(raw):
    require(type(raw) is dict, "malformed_local_document")
    locator(raw.get("url"))
    for field in ("title_original", "text_original", "title_zh", "body_zh",
                  "published_date", "source_slug", "scraped_at"):
        require(raw.get(field) is None or type(raw[field]) is str, "malformed_local_document")
        if raw.get(field) is not None:
            try:
                raw[field].encode("utf-8")
            except UnicodeError:
                raise OccurrenceError("malformed_local_document") from None
    try:
        canonical(raw)
    except (ValueError, TypeError, RecursionError):
        raise OccurrenceError("malformed_local_document") from None


def metadata(raw, normalized, sources, *, retained=False):
    slug = raw.get("source_slug")
    identity = sources.get(slug)
    if identity:
        require(url_host(raw["url"]) in identity[2], "source_locator_mismatch")
    title = raw.get("title_original")
    text = raw.get("text_original")
    body = normalized["text_original"]
    stored = raw.get("content_hash") if retained else None
    # Malformed historical hashes refuse; none are rewritten. Well-formed
    # stored hashes remain verbatim even when recomputation disagrees.
    require(stored is None or stored == "" or valid_digest(stored), "invalid_stored_hash")
    stored = stored or None
    legacy = compute_content_hash(title, text)
    producer = raw.get("capture_sha256")
    return Metadata(
        url=raw["url"], supplied_url=locator(raw.get("occurrence_supplied_url", raw["url"])),
        source_slug=slug if identity else None,
        desk_id=identity[0] if identity else None,
        institution_id=identity[1] if identity else None,
        identity_state="verified_source" if identity else "unknown_identity",
        supplied_identity_sha256=digest(canonical(slug)),
        published_date=actual_date(raw.get("published_date")),
        supplied_date_sha256=digest(canonical(raw.get("published_date"))),
        scraped_at=actual_time(raw.get("scraped_at")),
        producer_retrieved_at=actual_time(raw.get("retrieved_at")),
        producer_capture_sha256=producer if valid_digest(producer) else None,
        saved_input_bytes_sha256=raw.get("occurrence_saved_input_sha256")
            if valid_digest(raw.get("occurrence_saved_input_sha256")) else None,
        extracted_title_sha256=digest(title) if title is not None else None,
        title_state="missing" if title is None else "extracted_title"
            if normalized["title_original"] else "blank",
        extracted_text_sha256=digest(text) if text is not None else None,
        extracted_document_sha256=digest(canonical({"title_original": title, "text_original": text})),
        normalized_text_sha256=digest(body) if body else None,
        title_group_sha1=title_hash(normalized.get("title_zh") or normalized["title_original"]),
        legacy_title_text_sha256=legacy, stored_legacy_title_text_sha256=stored,
        stored_hash_state=("not_stored" if not retained else "missing" if stored is None
                           else "agrees" if stored == legacy else "disagrees"),
        body_state="extracted_text" if body else "missing" if text is None else "blank",
        body_kind="media_only" if raw.get("content_verdict") == "media_only" and not body
                  else "text" if body else "unavailable")


def relation_sets(observations, native_records, mode):
    """Indexed memberships, O(rows + text bytes); never all-pairs body comparison."""
    groups = defaultdict(list)
    nodes = [("o:" + o.observation_id, o.metadata) for o in observations]
    if mode == "observed_replay":
        nodes.extend(("n:" + str(r.native_id), r.metadata) for r in native_records)
    for node, m in nodes:
        keys = {"same_title_group": m.title_group_sha1, "exact_url": digest(m.url),
                "equal_normalized_text": m.normalized_text_sha256,
                "equal_normalized_title_text": m.legacy_title_text_sha256
                    if m.normalized_text_sha256 else None}
        for kind, key in keys.items():
            if key:
                groups[kind, key].append(node)
    return tuple(Relation(k, key, tuple(sorted(members)))
                 for (k, key), members in sorted(groups.items()) if len(members) > 1 and
                 any(m.startswith("o:") for m in members))


def build_batch(mode, batch_identity, snapshot_sha, rows, sources, documents=None):
    require(mode in {"archive_inventory", "observed_replay"}, "invalid_mode")
    require(type(batch_identity) is str and bool(batch_identity), "batch_identity_required")
    source_map = verified_sources(sources)
    raw = rows if mode == "archive_inventory" else [
        d.as_article_dict() if isinstance(d, ExtractedDocument) else d for d in documents]
    # Validate every input before normalization or algorithm/SQLite acceptance.
    for a in raw:
        validate_input(a)
    try:
        input_sha = digest(canonical(raw))
    except (TypeError, ValueError):
        raise OccurrenceError("malformed_local_document") from None
    code_sha, head = code_binding()
    batch_key = digest(batch_identity)
    execution = digest(canonical([batch_key, mode, input_sha, snapshot_sha, code_sha]))
    ids = [digest(execution + ":" + str(i)) for i in range(len(raw))]
    normalized = [normalize_article(a) for a in raw]
    native_records = tuple(NativeRecord(r["id"], metadata(r, normalize_article(r), source_map,
                                                       retained=True)) for r in rows)
    url_index, hash_index = defaultdict(list), defaultdict(list)
    for r in rows:
        url_index[r["url"]].append(r["id"])
        hash_index[r["content_hash"]].append(r["id"])
    observations = []
    if mode == "archive_inventory":
        for i, (a, n) in enumerate(zip(raw, normalized)):
            observations.append(Observation(ids[i], i, "existing_archive_row",
                metadata(a, n, source_map, retained=True), "existing_archive_row", None,
                "historical_decision_unknown", None, (a["id"],), ()))
    else:
        title = dedup_articles_detailed(normalized)
        url_hash = deduplicate_detailed(title.articles,
            url_lookup=lambda url: bool(url_index.get(url)),
            hash_lookup=lambda sha: bool(hash_index.get(sha)))
        stage = {title.positions[d.position]: d for d in url_hash.decisions}
        for i, (a, n, t) in enumerate(zip(raw, normalized, title.decisions)):
            d = stage.get(i)
            reason = d.reason if d else "not_reached"
            decision_ids = (url_index.get(n["url"], ()) if reason == "stored_url_match" else
                            hash_index.get(n["content_hash"], ()) if reason == "stored_legacy_hash_match" else ())
            observations.append(Observation(ids[i], i, "supplied_local_document",
                metadata(a, n, source_map), t.reason,
                ids[t.representative] if t.representative is not None else None,
                reason, ids[title.positions[d.representative]] if d and d.representative is not None else None,
                tuple(url_index.get(n["url"], ())), tuple(decision_ids)))
    observations = tuple(observations)
    relations = relation_sets(observations, native_records, mode)
    used_native = {n for o in observations for n in (*o.native_ids, *o.decision_native_ids)}
    used_native.update(int(node[2:]) for r in relations for node in r.members if node.startswith("n:"))
    records = tuple(r for r in native_records if r.native_id in used_native)
    return validate_batch(Batch(1, batch_key, execution, input_sha, snapshot_sha,
                               code_sha, head, mode, observations, records, relations))


def saved_mindef(index_path):
    """Replay existing saved HTML via the actual adapter, without fetch/discover.

    The local file digest is NOT asserted to be an HTTP capture. Producer
    capture references remain absent unless supplied by an existing producer.
    """
    from core.collection import status as st
    from core.collection.contract import CandidateReference, CaptureResult
    from scraper.sources.sg_mindef import SGMindefAdapter
    try:
        path = Path(index_path)
        require(path.is_file() and not path.is_symlink(), "fixture_index_unsafe")
        items = json.loads(path.read_text(encoding="utf-8"))
        require(type(items) is list and all(type(x) is dict and set(x) == {"file", "url"}
                                          for x in items), "fixture_index_invalid")
        source = next(s for cfg in load_all_desks().values() for s in cfg.sources
                      if s.slug == "sg_mindef_releases")
        adapter = SGMindefAdapter(source)
        documents = []
        for item in items:
            locator(item["url"])
            require(type(item["file"]) is str, "fixture_path_unsafe")
            file = path.parent / item["file"]
            require(file.is_file() and not any(p.is_symlink() for p in (file, *file.parents)) and
                    file.resolve().parent == path.parent.resolve(), "fixture_path_unsafe")
            reference = CandidateReference(item["url"], "sg_mindef_releases")
            payload = file.read_bytes()
            capture = CaptureResult(reference, st.OK, item["url"], body=payload.decode("utf-8"))
            result = adapter.extract(capture)
            require(st.is_success(result.status) and len(result.documents) == 1,
                    "saved_fixture_extraction_refused")
            raw = result.documents[0].as_article_dict()
            raw["occurrence_supplied_url"] = item["url"]
            raw["occurrence_saved_input_sha256"] = hashlib.sha256(payload).hexdigest()
            documents.append(raw)
        return documents
    except (OSError, ValueError, TypeError, AttributeError):
        raise OccurrenceError("saved_fixture_invalid_or_refused") from None


def summary(batch):
    cohorts = [r for r in batch.relations if r.kind == "same_title_group"]
    lookup = {"o:" + o.observation_id: o.metadata for o in batch.observations}
    lookup.update({"n:" + str(r.native_id): r.metadata for r in batch.records})
    by_desk = defaultdict(int)
    stored = defaultdict(int)
    for o in batch.observations:
        by_desk[o.metadata.desk_id or "unknown"] += 1
    for r in batch.records:
        if r.metadata.stored_legacy_title_text_sha256:
            stored[r.metadata.stored_legacy_title_text_sha256] += 1
    return {"mode": batch.mode, "snapshot_sha256": batch.snapshot_sha256,
            "input_sha256": batch.input_sha256, "execution_sha256": batch.execution_sha256,
            "observations": len(batch.observations), "native_records": len(batch.records),
            "observations_by_desk": dict(sorted(by_desk.items())),
            "duplicate_nonempty_stored_hash_groups": sum(n > 1 for n in stored.values()),
            "title_cohorts": len(cohorts), "cohort_members": sum(len(r.members) for r in cohorts),
            "cohorts_differing_dates": sum(len({lookup[n].published_date for n in r.members
                                           if lookup[n].published_date}) > 1 for r in cohorts),
            "cohorts_differing_sources": sum(len({lookup[n].source_slug for n in r.members
                                              if lookup[n].source_slug}) > 1 for r in cohorts),
            "stale_stored_hashes": sum(r.metadata.stored_hash_state == "disagrees" for r in batch.records)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--ledger", required=True, type=Path)
    for command in ("inventory", "replay"):
        p = sub.add_parser(command)
        p.add_argument("--ledger", required=True, type=Path)
        p.add_argument("--archive", required=True, type=Path)
        p.add_argument("--snapshot-sha256", required=True)
        p.add_argument("--batch", required=True, help="explicit local identity; use a new identity for revisions")
        if command == "replay":
            group = p.add_mutually_exclusive_group(required=True)
            group.add_argument("--saved-mindef", type=Path, help="existing items.json and saved HTML")
            group.add_argument("--documents", type=Path, help="already-held adapter article dictionaries JSON; never exported")
    p = sub.add_parser("export")
    p.add_argument("--ledger", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser("serve")
    p.add_argument("--ledger", required=True, type=Path)
    p.add_argument("--port", default=8767, type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            initialize(args.ledger)
            print("Private metadata ledger initialized.")
        elif args.command in {"inventory", "replay"}:
            documents = None
            if args.command == "replay":
                if args.saved_mindef:
                    documents = saved_mindef(args.saved_mindef)
                else:
                    require(args.documents.is_file() and not any(p.is_symlink() for p in
                            (args.documents, *args.documents.parents)), "documents_path_unsafe")
                    documents = json.loads(args.documents.read_text(encoding="utf-8"))
                    require(type(documents) is list, "malformed_local_batch")
            with pinned_archive(args.archive, args.snapshot_sha256) as (rows, sources):
                batch = build_batch("archive_inventory" if args.command == "inventory" else
                                    "observed_replay", args.batch, args.snapshot_sha256, rows, sources, documents)
            accepted = commit_batch(args.ledger, batch)
            print(canonical(dict(summary(batch), accepted=accepted)))
        elif args.command == "export":
            write_report(args.out, canonical([b.as_dict() for b in read_batches(args.ledger)]) + "\n")
            print("Metadata-only export written.")
        elif args.command == "serve":
            from scripts.source_occurrences_view import serve
            serve(args.ledger, args.port)
        return 0
    except (OccurrenceError, OSError, ValueError, TypeError):
        # No repr(payload), parser traceback, arbitrary path or publisher prose.
        print("Refused: invalid input, snapshot, ledger or private destination. See the local runbook.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
