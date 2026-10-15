"""Guard the China-focus release: three public browsing files, zero corpus drift."""
import argparse
import json
from pathlib import Path
import shutil

RELEASE_FILES = ("archive.html", "browse.js", "corpus-index.json")
CHINA_SOURCES = {"pla_daily", "mod_china", "china_mil_online",
                 "xinhua_mil", "global_times_mil"}
POLICY = "automated_research_focus_not_human_curated"
# Historical extraction holds preserved in the full index, never automatically
# promoted into the initial focused browse set. Keep synchronized with
# core.china_discovery.KNOWN_BODY_HOLDS when the prerequisite PR merges.
HISTORICAL_BODY_HOLDS = frozenset({
    170, 419, 905, 946, 1246, 1954, 2180, 2265, 2753, 2881, 3180, 3181
})


def stage(generated, public, expected_china=600):
    generated, public = Path(generated), Path(public)
    for name in RELEASE_FILES:
        for directory in (generated, public):
            path = directory / name
            if not path.is_file() or path.is_symlink():
                raise ValueError("missing or unsafe release file: %s" % path)
    old = json.loads((public / "corpus-index.json").read_text())
    new = json.loads((generated / "corpus-index.json").read_text())
    without_focus = lambda x: {k: v for k, v in x.items()
                               if k not in ("focus_ids", "focus_policy")}
    if without_focus(old) != without_focus(new):
        raise ValueError("preserved corpus/index drift: full render required")
    rows, sources = new["records"], new["sources"]
    full = {r[0] for r in rows}
    if len(full) != len(rows) or len(rows) != new["snapshot"]["records"]:
        raise ValueError("full corpus identity or count inconsistent")
    ids = new.get("focus_ids")
    if (new.get("focus_policy") != POLICY or not isinstance(ids, list)
            or any(type(n) is not int or n <= 0 for n in ids)
            or len(ids) != len(set(ids)) or not set(ids) <= full):
        raise ValueError("focus policy or membership invalid")
    selected, china, other = set(ids), set(), set()
    for record in rows:
        if len(record) != 6 or not isinstance(record[2], int):
            raise ValueError("bad record schema")
        source = sources[record[2]]
        if (source["code"] in CHINA_SOURCES
                or (source.get("desk") or {}).get("code") == "china"):
            china.add(record[0])
        else:
            other.add(record[0])
    if len(selected & china) != expected_china or not other <= selected:
        raise ValueError("China quota or non-China desk visibility violated")
    if HISTORICAL_BODY_HOLDS & selected:
        raise ValueError("historically compromised capture promoted")
    if {2391, 2849} <= full and not {2391, 2849} <= selected:
        raise ValueError("provisional important originals missing")
    if not set(new["trail_ids"]) <= full:
        raise ValueError("source trail no longer preserved")
    archive = (generated / "archive.html").read_text()
    for marker in ("Research focus", "Full preserved record", "corpus.html",
                   "not individually fact-checked or editor-approved",
                   "Every record is also reachable by publication week"):
        if marker not in archive:
            raise ValueError("missing research/full-corpus disclosure: " + marker)
    script = (generated / "browse.js").read_bytes()
    if not 0 < len(script) <= 9500 or not all(
            s in script for s in (b"focus_ids", b"scope", b"preserved records")):
        raise ValueError("browser scope or 9500-byte budget failed")
    # Complete every preflight BEFORE modifying a single published file.
    for name in RELEASE_FILES:
        shutil.copyfile(generated / name, public / name)
    return {"full": len(full), "china": len(china),
            "china_focus": len(selected & china), "non_china": len(other),
            "all_focus": len(selected), "paths": RELEASE_FILES}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-dir", type=Path, required=True)
    parser.add_argument("--to-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.from_dir, args.to_dir), sort_keys=True))


if __name__ == "__main__":
    main()
