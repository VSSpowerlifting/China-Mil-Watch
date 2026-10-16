"""Fail-closed check of a complete 4,400-record China retirement site.

Runs on external scratch DB and site before any tracked DB, output or Pages
write. Unlike the generic site validator, compares the complete before/after
record identities, all published citation trails, both route namespaces, URL
tombstones, sitemap and the legacy export. No network, collection or mutation.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import xml.etree.ElementTree as ET

from core.retired_article_urls import verify_no_active_retired_urls

RECORD_ROUTE = re.compile(r"/(?:record|article)/([0-9]+)\.html$")


def _index(directory):
    return json.loads((Path(directory) / "corpus-index.json").read_text(encoding="utf-8"))


def _ids(index):
    rows = index["records"]
    ids = [r[0] for r in rows]
    if any(type(i) is not int or i <= 0 for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("invalid/duplicate corpus record IDs")
    return set(ids)


def validate(before_site, after_site, reduced_db, plan_summary):
    before_site, after_site, reduced_db = (
        Path(before_site).resolve(), Path(after_site).resolve(), Path(reduced_db).resolve())
    old, new = _index(before_site), _index(after_site)
    plan = json.loads(Path(plan_summary).read_text(encoding="utf-8"))
    old_ids, new_ids = _ids(old), _ids(new)
    retired = old_ids - new_ids
    if new_ids - old_ids:
        raise ValueError("new unreviewed IDs appeared in reduced site")
    if len(retired) != 4400 or plan["china_to_retire"] != 4400:
        raise ValueError("retirement must contain exactly 4,400 original IDs")
    if len(new_ids) != len(old_ids) - 4400 or len(new_ids) != plan["total_after"]:
        raise ValueError("unexpected survivor count")
    digest = sha256(",".join(map(str, sorted(retired))).encode()).hexdigest()
    if digest != plan["retirement_id_sha256"]:
        raise ValueError("retirement identity SHA-256 differs from reviewed plan")

    trails, focus = set(old["trail_ids"]), set(old["focus_ids"])
    if not trails <= new_ids or not focus <= new_ids:
        raise ValueError("published trail or research focus record removed")
    if set(new["trail_ids"]) != trails:
        raise ValueError("published trail identities changed")
    if set(new["focus_ids"]) != focus:
        raise ValueError("research focus identities changed")

    with sqlite3.connect(reduced_db.as_uri() + "?mode=ro&immutable=1", uri=True) as con:
        active_ids = {r[0] for r in con.execute("SELECT id FROM articles")}
        if active_ids != new_ids:
            raise ValueError("rendered survivor IDs differ from reduced database")
        if verify_no_active_retired_urls(con) != len(retired):
            raise ValueError("missing or extra URL/ID retirement tombstones")
        ledger_ids = {r[0] for r in con.execute(
            "SELECT original_article_id FROM retired_article_urls")}
        if ledger_ids != retired:
            raise ValueError("retired database identity ledger differs from plan")
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("reduced SQLite integrity check failed")
        if con.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("reduced SQLite has invalid foreign keys")

    # Every active article gets a /record/ page; only fully analyzed and
    # relevance-passed sources ever had /article/ legacy redirects.
    analyzed_state = next((i for i, state in enumerate(new["states"])
                           if state["code"] == "analyzed"), None)
    if analyzed_state is None:
        raise ValueError("analyzed processing state missing from index")
    required_routes = {
        "record": new_ids,
        "article": {r[0] for r in new["records"] if r[3] == analyzed_state},
    }
    for folder, required in required_routes.items():
        pages = after_site / folder
        found = {int(p.stem) for p in pages.glob("*.html") if p.stem.isdigit()}
        if found != required:
            raise ValueError(folder + " pages contain missing, stale or retired IDs")

    export = json.loads((after_site / "data" / "articles.json").read_text(encoding="utf-8"))
    if not isinstance(export, list):
        raise ValueError("legacy analyzed export is not a list")
    exported = [r["id"] for r in export]
    if (len(exported) != len(set(exported))
            or any(type(i) is not int or i not in new_ids for i in exported)):
        raise ValueError("legacy analyzed export includes duplicate or retired ID")

    for node in ET.parse(after_site / "sitemap.xml").iter():
        if node.tag.rsplit("}", 1)[-1] != "loc" or not node.text:
            continue
        match = RECORD_ROUTE.search(node.text)
        if match and int(match.group(1)) not in new_ids:
            raise ValueError("retired or unknown source route remains in sitemap")

    return {
        "before": len(old_ids),
        "retired": len(retired),
        "retained": len(new_ids),
        "protected_trails": len(trails),
        "retained_research_focus": len(focus),
        "legacy_export": len(exported),
        "url_id_tombstones": len(retired),
        "retirement_id_sha256": digest,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    p.add_argument("--db", type=Path, required=True)
    p.add_argument("--plan", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(validate(a.before, a.after, a.db, a.plan),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
