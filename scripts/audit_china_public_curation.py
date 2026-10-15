#!/usr/bin/env python3
"""Read-only, title-level China corpus curation audit; NEVER a publication gate.

Uses the already-published compact index. A proposed review sample is not an
editorial judgment and must not be reused as a record allowlist. No database,
generated output, source record, brief, or published route is modified.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = REPO_ROOT / "output" / "corpus-index.json"
REQUIRED_FIELDS = ["id", "date", "source", "state", "title_en", "title_orig"]


def _stable_key(row):
    # Reproducible within the snapshot, with no random seed or freshness bias.
    digest = hashlib.sha256(str(row["id"]).encode("ascii")).hexdigest()
    return (digest, row["id"])


def audit(index, target=600):
    """Build a stratified *human review sample* and an exhaustive status ledger.

    Every published Brief trail record is guaranteed a review slot, even if its
    machine-processing state would otherwise keep it out of this sampling pool.
    All other candidates are sampled from the analyzed China subset across
    source/month strata. Neither machine labels nor sampling confer approval.
    """
    if not isinstance(target, int) or isinstance(target, bool) or target < 1:
        raise ValueError("target must be a positive integer")
    if index.get("fields") != REQUIRED_FIELDS:
        raise ValueError("unexpected compact-index schema; fail closed")
    sources, states = index["sources"], index["states"]
    trails = index.get("trail_ids")
    if not isinstance(trails, list):
        raise ValueError("source-trail protection data missing; fail closed")
    trail_ids = set(trails)
    if len(trail_ids) != len(trails):
        raise ValueError("duplicate source-trail IDs")
    records, seen_ids = [], set()
    for raw in index["records"]:
        if not isinstance(raw, list) or len(raw) != len(REQUIRED_FIELDS):
            raise ValueError("unexpected record fields")
        rid, date, src_idx, state_idx, title_en, title_orig = raw
        if not isinstance(rid, int) or isinstance(rid, bool) or rid in seen_ids:
            raise ValueError("duplicate or invalid record ID")
        seen_ids.add(rid)
        if (not isinstance(src_idx, int) or isinstance(src_idx, bool)
                or src_idx < 0 or src_idx >= len(sources)
                or not isinstance(state_idx, int) or isinstance(state_idx, bool)
                or state_idx < 0 or state_idx >= len(states)):
            raise ValueError("invalid source/state index")
        source = sources[src_idx]
        desk = (source.get("desk") or {}).get("code")
        if not isinstance(date, str) or len(date) < 7:
            raise ValueError("missing record publication month")
        records.append({
            "id": rid,
            "date": date,
            "source": source["code"],
            "desk": desk,
            "state": states[state_idx]["code"],
            "title_en": title_en,
            "title_orig": title_orig,
            "in_published_trail": rid in trail_ids,
        })
    if not trail_ids.issubset(seen_ids):
        raise ValueError("a protected Brief trail ID has no stored record")

    china = [r for r in records if r["desk"] == "china"]
    protected = [r for r in china if r["in_published_trail"]]
    # No title-based importance scoring. Important statements can use bland
    # titles, and sensational headlines are not proof of source authority.
    sample_ids = {r["id"] for r in protected}
    buckets = defaultdict(list)
    for row in china:
        if row["id"] not in sample_ids and row["state"] == "analyzed":
            buckets[(row["source"], row["date"][:7])].append(row)
    for rows in buckets.values():
        rows.sort(key=_stable_key)
    strata = sorted(buckets)
    # Round-robin across source/month: an intentionally diverse audit sample,
    # not a recommendation to equalize institutions in the published archive.
    position = 0
    while len(sample_ids) < target and strata:
        stratum = strata[position % len(strata)]
        row = buckets[stratum].pop(0)
        sample_ids.add(row["id"])
        if not buckets[stratum]:
            strata.remove(stratum)
            position = position % len(strata) if strata else 0
        else:
            position += 1

    rows = []
    status_counts = Counter()
    for row in china:
        if row["in_published_trail"]:
            status = "protected_trail_review"
        elif row["id"] in sample_ids:
            status = "stratified_review_sample"
        elif row["state"] == "analyzed":
            status = "analyzed_not_sampled"
        elif row["state"] == "not_selected":
            status = "screened_not_selected_requires_review"
        else:
            status = "processing_not_complete"
        result = dict(row)
        result["review_status"] = status
        result["editorially_approved"] = False
        status_counts[status] += 1
        rows.append(result)

    return {
        "version": 1,
        "purpose": "private_human_review_only",
        "publication_allowlist": False,
        "snapshot": index.get("snapshot"),
        "requested_sample_size": target,
        "preserved_corpus_records": len(records),
        "china_stored_records": len(china),
        "china_records_by_source": dict(sorted(Counter(
            r["source"] for r in china).items())),
        "china_records_by_processing_state": dict(sorted(Counter(
            r["state"] for r in china).items())),
        "protected_china_trail_records": len(protected),
        "review_sample_count": len(sample_ids),
        "review_sample_by_source": dict(sorted(Counter(
            r["source"] for r in china if r["id"] in sample_ids).items())),
        "review_status_counts": dict(sorted(status_counts.items())),
        "rows": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--target", type=int, default=600)
    parser.add_argument("--out", type=Path,
                        help="Optional PRIVATE JSON review ledger OUTSIDE repository")
    args = parser.parse_args(argv)
    if args.out is not None:
        dest = args.out.resolve()
        if dest == REPO_ROOT or REPO_ROOT in dest.parents:
            parser.error("--out must be outside the repository, including output/")
        if dest.exists():
            parser.error("--out already exists; refusing to overwrite")
    report = audit(json.loads(args.index.read_text(encoding="utf-8")),
                   target=args.target)
    summary = {k: v for k, v in report.items() if k != "rows"}
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.out is not None:
        # Export only after all validation and status derivation succeeded.
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
