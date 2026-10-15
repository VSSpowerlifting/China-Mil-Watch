"""Prepare a true China corpus retirement without touching the tracked database.

The 600-record China research focus is a machine-generated *starting point*,
NOT a human sign-off. Every published Brief trail ID and every other desk
record is additionally protected. The optional destructive operation is
limited to a newly-created, outside-repository scratch SQLite copy.

This module intentionally cannot stage, overwrite, commit, or deploy
pla_watch.db or output/. Active production deletion requires a separate
reviewed and recoverable release.
"""
import argparse
from datetime import date
import os
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
CHINA_SOURCES = frozenset({
    "pla_daily", "mod_china", "china_mil_online",
    "xinhua_mil", "global_times_mil",
})
POLICY = "automated_research_focus_not_human_curated"
IMPORTANT_ORIGINALS = frozenset({2391, 2849})
HISTORICAL_HOLDS = frozenset({
    170, 419, 905, 946, 1246, 1954, 2180, 2265,
    2753, 2881, 3180, 3181,
})


def publication_record_dependencies(root):
    """Collect explicitly bound record IDs from native Briefs and Timelines.

    Both approved work and unpublished in-progress manuscripts are guarded;
    deleting a source would otherwise silently damage a saved editorial draft.
    Historical PLA Watch sidecars do not carry record IDs, so the full index's
    separately derived exact-URL trail_ids remain mandatory.
    """
    root = Path(root)
    ids = set()
    counts = Counter()
    for dirname in ("briefs", "timelines"):
        folder = root / dirname
        if not folder.is_dir():
            raise ValueError("missing canonical publication directory: " + dirname)
        for path in sorted(folder.glob("*.json")):
            item = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(item, dict):
                raise ValueError("invalid canonical editorial JSON: " + str(path))
            if dirname == "briefs":
                entries = item.get("source_trail", [])
            else:
                entries = [proof for event in item.get("entries", [])
                           for proof in event.get("evidence", [])]
            if not isinstance(entries, list):
                raise ValueError("invalid source dependency array: " + str(path))
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError("invalid source dependency: " + str(path))
                value = entry.get("record_id")
                if value is None:
                    continue
                if type(value) is not int or value <= 0:
                    raise ValueError("invalid referenced record ID: " + str(path))
                ids.add(value)
                counts[dirname] += 1
    return ids, dict(counts)


def plan(index, *, expected_china_focus=600, minimum_retire=4300,
         maximum_retire=4500, preferred_retire=4400,
         publication_ids=()):
    """Build a deterministic retirement candidate set, never an editorial verdict."""
    if (index.get("fields") !=
            ["id", "date", "source", "state", "title_en", "title_orig"]):
        raise ValueError("unknown corpus-index fields")
    rows = index.get("records")
    sources = index.get("sources")
    snapshot = index.get("snapshot")
    focus = index.get("focus_ids")
    trails = index.get("trail_ids")
    if not all(isinstance(x, list) for x in (rows, sources, focus, trails)):
        raise ValueError("complete records, focus, sources and trails required")
    if not isinstance(snapshot, dict) or snapshot.get("records") != len(rows):
        raise ValueError("snapshot record count changed")
    if index.get("focus_policy") != POLICY:
        raise ValueError("not the disclosed, automated China research focus")
    if (any(type(n) is not int or n <= 0 for n in focus + trails)
            or len(focus) != len(set(focus))
            or len(trails) != len(set(trails))):
        raise ValueError("invalid or duplicate evidence identities")

    full, china, others = set(), set(), set()
    by_source = Counter()
    for row in rows:
        if not isinstance(row, list) or len(row) != 6:
            raise ValueError("invalid corpus row")
        ident, _, src, _, _, _ = row
        if (type(ident) is not int or ident <= 0 or ident in full
                or type(src) is not int or not 0 <= src < len(sources)):
            raise ValueError("invalid/duplicate record or source identifier")
        full.add(ident)
        source = sources[src]
        if not isinstance(source, dict):
            raise ValueError("invalid source metadata")
        slug = source.get("code")
        if ((source.get("desk") or {}).get("code") == "china"
                or slug in CHINA_SOURCES):
            china.add(ident)
            by_source[slug] += 1
        else:
            others.add(ident)

    focus_ids, trail_ids = set(focus), set(trails)
    if not focus_ids <= full or not trail_ids <= full:
        raise ValueError("lost source identity or published citation")
    if not others <= focus_ids:
        raise ValueError("other desks are absent from the research view")
    if len(focus_ids & china) != expected_china_focus:
        raise ValueError("China research cohort changed, no release authority")
    if focus_ids & HISTORICAL_HOLDS:
        raise ValueError("known original-body hold promoted into research focus")

    # Citation-held records are never retired, even when their original
    # capture is suspect. They require correction, not broken public citations.
    bound = set(publication_ids)
    if any(type(ident) is not int or ident <= 0 for ident in bound):
        raise ValueError("invalid canonical publication dependency")
    if not bound <= full:
        raise ValueError("published or draft citation refers to missing corpus ID")
    kept = focus_ids | trail_ids | (IMPORTANT_ORIGINALS & full) | others | bound
    initially_removable = len(full - kept)
    # The owner approved an actual 4,300–4,500 deletion range, NOT an
    # arbitrary minimum of 3,500. If the focus and citations leave more than
    # 4,400 removable China rows, protect additional *context* records in
    # a separate openly automated tier. This does not claim editorial review.
    supplemental = []
    if initially_removable > preferred_retire:
        count = initially_removable - preferred_retire
        safe = []
        for row in rows:
            ident, date, src, state, _, _ = row
            if ident not in china or ident in kept or ident in HISTORICAL_HOLDS:
                continue
            slug = sources[src]["code"]
            # Avoid adding older known-contaminated Global Times captures
            # as superficially safe retained context.
            if slug == "global_times_mil":
                continue
            # Prefer original ministry and non-PLA sources, then more recent
            # records; deterministic and explicitly *non-editorial*.
            source_priority = {
                "mod_china": 3, "xinhua_mil": 2,
                "china_mil_online": 1, "pla_daily": 0,
            }.get(slug, -1)
            safe.append((source_priority, date or "", ident))
        safe.sort(reverse=True)
        if len(safe) < count:
            raise ValueError("insufficient safe context rows to reach target range")
        supplemental = [ident for _, _, ident in safe[:count]]
        kept.update(supplemental)
    removed = full - kept
    if not removed <= china or not minimum_retire <= len(removed) <= maximum_retire:
        raise ValueError("retirement outside owner-approved 4300–4500 range")
    if not trail_ids <= kept or not IMPORTANT_ORIGINALS & full <= kept:
        raise ValueError("protected editorial evidence lost")

    fingerprint = sha256(",".join(map(str, sorted(removed))).encode()).hexdigest()
    return {
        "snapshot": snapshot,
        "total_before": len(full),
        "china_before": len(china),
        "other_desks_before": len(others),
        "automated_china_focus": len(focus_ids & china),
        "published_trail_references": len(trail_ids),
        "bound_brief_and_timeline_ids": len(bound),
        "citation_only_china_retained": len((trail_ids & china) - focus_ids),
        "supplemental_automated_context": len(supplemental),
        "china_to_retire": len(removed),
        "china_after": len(china - removed),
        "total_after": len(kept),
        "by_source_before": dict(sorted(by_source.items())),
        "retirement_id_sha256": fingerprint,
        "kept_ids": tuple(sorted(kept)),
        "retired_ids": tuple(sorted(removed)),
    }


def scratch_retirement(db_path, scratch_path, plan_data,
                       tombstone_path=None, *, minimum_retire=4300,
                       maximum_retire=4500, retired_at=None):
    """Retire physical rows and durable tombstones together on a NEW scratch DB.

    The old delete-only rehearsal MUST NOT be used: it silently omitted the
    persistent re-ingestion ledger. All deletions now flow through the one
    validated SQLite transaction in stage_china_retirement_atomic.
    """
    from scripts.stage_china_retirement_atomic import rehearse_on_new_scratch_copy

    receipt = None
    if tombstone_path is not None:
        receipt = Path(tombstone_path)
        if (not receipt.is_absolute() or receipt.exists()
                or not receipt.parent.is_dir() or receipt.parent.is_symlink()):
            raise ValueError("tombstone path must be a new absolute scratch file")
        receipt = receipt.resolve()
        if (receipt == ROOT or ROOT in receipt.parents
                or receipt == Path(scratch_path).resolve()
                or receipt == Path(db_path).resolve()):
            raise ValueError("tombstone receipt must be outside the repository")

    # No operation against the original database: the helper uses an explicit
    # read-only source copy, upgrades migrations only in scratch, verifies
    # every ID, inserts hashed retired URLs and deletes their article rows in
    # one transaction, and rolls back on any failure.
    report = rehearse_on_new_scratch_copy(
        db_path, scratch_path, plan_data,
        retired_at or date.today().isoformat(),
        minimum_retire=minimum_retire, maximum_retire=maximum_retire,
    )
    dest = Path(report["scratch_db"])
    try:
        with sqlite3.connect(str(dest)) as conn:
            rows = conn.execute(
                "SELECT url_sha256 FROM retired_article_urls "
                "WHERE selection_sha256=? ORDER BY url_sha256",
                (plan_data["retirement_id_sha256"],)
            ).fetchall()
            if len(rows) != report["retired"]:
                raise ValueError("durable retirement ledger count differs from plan")
            digests = [r[0] for r in rows]
            if len(set(digests)) != len(digests):
                raise ValueError("duplicate hashed retired URL in durable ledger")
        if receipt is not None:
            payload = {
                "version": 1, "algorithm": "sha256-of-exact-stored-article-url",
                "snapshot": plan_data["snapshot"],
                "retired_count": len(digests),
                "retirement_id_sha256": plan_data["retirement_id_sha256"],
                "retired_url_sha256": digests,
                "atomic_retirement": True,
            }
            # Mode 0600 from creation, no temporarily world-readable file.
            fd = os.open(str(receipt), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(payload, output, sort_keys=True)
                output.write("\n")
    except BaseException:
        dest.unlink(missing_ok=True)
        if receipt is not None:
            receipt.unlink(missing_ok=True)
        raise
    return {
        "scratch_db": str(dest), "retired": report["retired"],
        "kept": report["retained"], "production_db_modified": False,
        "url_tombstone_count": len(digests),
        "private_tombstone_receipt": str(receipt) if receipt else None,
        "atomic_retirement": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path,
                        default=ROOT / "output/corpus-index.json")
    parser.add_argument("--db", type=Path, default=ROOT / "pla_watch.db")
    parser.add_argument("--scratch-db", type=Path,
                        help="optional NEW database path outside repo; never publish")
    parser.add_argument("--tombstones-out", type=Path,
                        help="new private digest manifest; requires --scratch-db")
    args = parser.parse_args(argv)
    dependencies, by_type = publication_record_dependencies(ROOT)
    result = plan(json.loads(args.index.read_text(encoding="utf-8")),
                  publication_ids=dependencies)
    public = {k: v for k, v in result.items()
              if k not in ("kept_ids", "retired_ids")}
    public["canonical_publication_reference_counts"] = by_type
    if args.tombstones_out and not args.scratch_db:
        parser.error("--tombstones-out requires --scratch-db")
    if args.scratch_db:
        public["rehearsal"] = scratch_retirement(
            args.db, args.scratch_db, result, tombstone_path=args.tombstones_out)
    print(json.dumps(public, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
