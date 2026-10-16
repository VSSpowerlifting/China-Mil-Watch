"""Compare the committed China retirement output with actual Pages Git bytes.

The release creates a complete output/ tree and publishes it to gh-pages.
A green gh-pages push by itself does not prove the published branch contains
the same record IDs, export, sitemap, briefs and assets. This check is read-only
and fails if *any* regular site file differs, disappears or unexpectedly remains.
It checks the Pages Git branch, not DNS or time-delayed CDN cache state.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from core.retired_article_urls import verify_no_active_retired_urls


# The Pages action may synthesize these two hosting controls, but they must
# still be valid. No other extra or changed page/media files are permitted.
HOSTING_FILES = frozenset(("CNAME", ".nojekyll"))


def _files(root):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("expected an existing site directory")
    files = {}
    for item in root.rglob("*"):
        if ".git" in item.relative_to(root).parts:
            continue
        if item.is_symlink():
            raise ValueError("published tree contains symlink: " + str(item))
        if item.is_file():
            files[item.relative_to(root).as_posix()] = sha256(item.read_bytes()).hexdigest()
    return files


def verify(expected_output, pages_tree, db_path, *, expected_tombstones=4400):
    expected_output, pages_tree, db_path = (
        Path(expected_output), Path(pages_tree), Path(db_path))
    expected, deployed = _files(expected_output), _files(pages_tree)
    # We never compare Git internal metadata, only the actual served tree.
    want = {k: v for k, v in expected.items() if k not in HOSTING_FILES}
    actual = {k: v for k, v in deployed.items() if k not in HOSTING_FILES}
    if want.keys() != actual.keys():
        missing = sorted(want.keys() - actual.keys())
        extra = sorted(actual.keys() - want.keys())
        raise ValueError("Pages tree file-list drift: missing=%s extra=%s"
                         % (missing[:10], extra[:10]))
    changed = [path for path in want if want[path] != actual[path]]
    if changed:
        raise ValueError("Pages tree byte mismatch: " + ", ".join(changed[:10]))
    cname = (pages_tree / "CNAME")
    if not cname.is_file() or cname.read_text(encoding="utf-8").strip() != "indopacificrecord.org":
        raise ValueError("Pages custom domain not preserved")
    if not (pages_tree / ".nojekyll").is_file():
        raise ValueError("Pages needs .nojekyll for static serving")

    expected_idx = json.loads((expected_output / "corpus-index.json").read_text(encoding="utf-8"))
    published_idx = json.loads((pages_tree / "corpus-index.json").read_text(encoding="utf-8"))
    if expected_idx != published_idx:
        raise ValueError("Pages corpus index differs from committed output")
    ids = [r[0] for r in published_idx["records"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate live source IDs")
    with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro&immutable=1",
                         uri=True) as con:
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("release SQLite integrity failure")
        if con.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("release SQLite foreign-key failure")
        if verify_no_active_retired_urls(con) != expected_tombstones:
            raise ValueError("production retirement ledger count differs")
        active = {int(row[0]) for row in con.execute("SELECT id FROM articles")}
    if active != set(ids):
        raise ValueError("published records do not match production SQLite")
    if not set(published_idx["trail_ids"]) <= active:
        raise ValueError("published evidence citation would be lost")

    return {"published_files_verified": len(want),
            "active_record_count": len(active),
            "retired_url_id_tombstones": expected_tombstones,
            "static_site_sha256": sha256(
                "\n".join("%s %s" % (key, want[key]) for key in sorted(want)).encode()
            ).hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--expected-output", type=Path, required=True)
    p.add_argument("--pages-tree", type=Path, required=True)
    p.add_argument("--db", type=Path, required=True)
    p.add_argument("--expected-tombstones", type=int, default=4400)
    a = p.parse_args()
    print(json.dumps(verify(a.expected_output, a.pages_tree, a.db,
                            expected_tombstones=a.expected_tombstones),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
