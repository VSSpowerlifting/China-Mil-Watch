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


def plan(index, *, expected_china_focus=600, minimum_retire=4300,
         maximum_retire=4500, preferred_retire=4400):
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
    kept = focus_ids | trail_ids | (IMPORTANT_ORIGINALS & full) | others
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


def scratch_retirement(db_path, scratch_path, plan_data, tombstone_path=None):
    """Apply deletions ONLY to a fresh SQLite file outside this repository."""
    from scripts.reconcile_db import read_only

    db_path = Path(db_path).resolve(strict=True)
    scratch_path = Path(scratch_path)
    if not scratch_path.is_absolute() or scratch_path.exists():
        raise ValueError("scratch path must be absolute and not exist")
    if not scratch_path.parent.is_dir() or scratch_path.parent.is_symlink():
        raise ValueError("scratch parent must exist and not be a symlink")
    destination = scratch_path.resolve()
    if (destination == ROOT or ROOT in destination.parents
            or destination == db_path):
        raise ValueError("cannot write into repository or tracked database")
    if tombstone_path is not None:
        receipt = Path(tombstone_path)
        if (not receipt.is_absolute() or receipt.exists()
                or not receipt.parent.is_dir() or receipt.parent.is_symlink()):
            raise ValueError("tombstone path must be a new absolute scratch file")
        receipt = receipt.resolve()
        if (receipt == ROOT or ROOT in receipt.parents
                or receipt == destination or receipt == db_path):
            raise ValueError("tombstone receipt must be outside the repository")

    # Copies the input through the repository's read-only scratch mechanism.
    # No direct SQLite connection ever touches the tracked file on disk.
    with read_only(db_path) as source:
        originals = {r[0] for r in source.execute("SELECT id FROM articles")}
        expected = set(plan_data["kept_ids"]) | set(plan_data["retired_ids"])
        if originals != expected:
            raise ValueError("tracked database does not match the reviewed index")
        # Retired canonical URLs must be blocked from future collection.
        # Hash the literal stored URL bytes: the ingestion path inserts these
        # exact URLs, without case folding or an invented recanonicalization.
        urls = dict(source.execute("SELECT id, url FROM articles"))
        digests = sorted(sha256(urls[i].encode("utf-8")).hexdigest()
                         for i in plan_data["retired_ids"])
        if len(digests) != len(set(digests)):
            raise ValueError("duplicate retired URL or noncanonical input")
        # Any new dependent relation that cannot cascade must be designed
        # separately; silently losing foreign-key evidence is unacceptable.
        tables = [r[0] for r in source.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ) if not r[0].startswith("sqlite_")]
        for table in tables:
            for fk in source.execute('PRAGMA foreign_key_list("%s")' %
                                     table.replace('"', '""')):
                if fk[2] == "articles" and fk[6].upper() != "CASCADE":
                    raise ValueError("unsafe referencing relation: " + table)
        target = sqlite3.connect(str(destination))
        try:
            source.backup(target)
            target.execute("PRAGMA foreign_keys=ON")
            target.execute("PRAGMA journal_mode=DELETE")
            ids = plan_data["retired_ids"]
            target.execute("BEGIN IMMEDIATE")
            for start in range(0, len(ids), 400):
                group = ids[start:start + 400]
                target.execute("DELETE FROM articles WHERE id IN (%s)" %
                               ",".join("?" for _ in group), group)
            count = target.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            if count != plan_data["total_after"]:
                raise ValueError("post-retirement article count disagrees")
            if target.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("foreign-key violation after retirement")
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("SQLite integrity failure after retirement")
            kept = {r[0] for r in target.execute("SELECT id FROM articles")}
            if kept != set(plan_data["kept_ids"]):
                raise ValueError("retained IDs changed unexpectedly")
            target.commit()
        except BaseException:
            target.rollback()
            target.close()
            destination.unlink(missing_ok=True)
            raise
        else:
            target.close()
    if tombstone_path is not None:
        payload = {
            "version": 1, "algorithm": "sha256-of-exact-stored-article-url",
            "snapshot": plan_data["snapshot"],
            "retired_count": len(digests),
            "retirement_id_sha256": plan_data["retirement_id_sha256"],
            "retired_url_sha256": digests,
        }
        try:
            with receipt.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(payload, sort_keys=True) + "\n")
            receipt.chmod(0o600)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
    return {"scratch_db": str(destination), "retired": len(plan_data["retired_ids"]),
            "kept": plan_data["total_after"], "production_db_modified": False,
            "url_tombstone_count": len(digests),
            "private_tombstone_receipt": str(receipt) if tombstone_path else None}


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
    result = plan(json.loads(args.index.read_text(encoding="utf-8")))
    public = {k: v for k, v in result.items()
              if k not in ("kept_ids", "retired_ids")}
    if args.tombstones_out and not args.scratch_db:
        parser.error("--tombstones-out requires --scratch-db")
    if args.scratch_db:
        public["rehearsal"] = scratch_retirement(
            args.db, args.scratch_db, result, tombstone_path=args.tombstones_out)
    print(json.dumps(public, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
