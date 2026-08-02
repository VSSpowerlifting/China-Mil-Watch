#!/usr/bin/env python3
"""
Row-level reconciliation of a diverged `pla_watch.db`.

Why this exists (DECISION_LOG 2026-08-02): `pla_watch.db` is a binary file
committed to git, and CI writes it to `main` on a schedule while humans work
on local branches. Whenever both sides advance from a common base, git can
only offer "take mine or take theirs" — and either choice silently destroys a
day of collection. This has now happened four times (07-12→16 passes, the
07-17 reconcile, the 07-30 local-main drift, and 07-30→31).

The 07-30→31 case is the worst shape it takes: CI and the local branch had
BOTH allocated article ids from 2727, so origin's article 2731 and the
branch's 2731 were different articles. Nothing about that is visible in a
`git status`, and a merge resolved either way loses 40 or 80 articles.

What this does
--------------
Merges by `url` (the table's UNIQUE key) rather than by id, and treats the
two sides asymmetrically on purpose:

  ORIGIN is authoritative for identity. Its ids are already published as
  `output/article/<id>.html` and referenced by the sitemap and feed, so
  renumbering them would break live URLs.

  LOCAL rows have not been rendered (a `--no-analysis` capture does not
  generate the site), so they are safe to renumber above origin's max.

Merge rules
  1. Base = origin, every id preserved verbatim.
  2. Local articles whose url is absent from origin are inserted with fresh
     ids; `article_categories` and `scrape_run_id` follow the remap.
  3. Local analysis is applied to shared rows still pending in origin. Rows
     already analyzed in origin are never overwritten.

Nothing is written to the working tree. The merged database is produced at
--out for inspection; landing it is a separate, deliberate act.

Usage
    .venv/bin/python scripts/reconcile_db.py --from-git --out /tmp/merged.db
    .venv/bin/python scripts/reconcile_db.py \
        --base B.db --origin O.db --local L.db --out M.db

`--from-git` re-derives all three versions from refs, so it can be re-run
after CI advances `origin/main` again without editing anything.
"""

import argparse
import logging
import shutil
import sqlite3
import subprocess
import sys

logger = logging.getLogger("reconcile_db")

DB_PATH = "pla_watch.db"

# Never copied verbatim from the local side — both are remapped on insert.
ARTICLE_COLS_SKIP = {"id", "scrape_run_id"}

# Analysis-layer fields backfilled onto shared rows still pending in origin.
ANALYSIS_COLS = [
    "relevance_score",
    "relevance_reasoning",
    "passed_relevance",
    "title_english",
    "text_english",
    "summary_english",
    "analyzed_at",
    "is_significant",
    "significance_reasoning",
    "model_id",
]


def _git(*args) -> bytes:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True
    ).stdout


def extract_from_git(workdir: str):
    """Write base/origin/local copies of the DB and return their paths."""
    _git("fetch", "origin", "--quiet")
    base_ref = _git("merge-base", "HEAD", "origin/main").decode().strip()
    logger.info("merge-base: %s", base_ref[:12])

    paths = {}
    for name, ref in (("base", base_ref), ("origin", "origin/main"), ("local", "HEAD")):
        path = f"{workdir}/db_{name}.db"
        with open(path, "wb") as fh:
            fh.write(_git("show", f"{ref}:{DB_PATH}"))
        paths[name] = path
    return paths["base"], paths["origin"], paths["local"]


def columns(con, table):
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]


def reconcile(base_path, origin_path, local_path, out_path):
    shutil.copyfile(origin_path, out_path)
    con = sqlite3.connect(out_path)
    con.row_factory = sqlite3.Row
    con.execute("ATTACH ? AS loc", (local_path,))
    con.execute("ATTACH ? AS bse", (base_path,))

    art_cols = columns(con, "articles")
    absent = [c for c in ANALYSIS_COLS if c not in art_cols]
    if absent:
        raise SystemExit(
            f"FATAL: schema lacks expected analysis columns {absent} — refusing "
            "to merge a database whose shape has changed underneath this script."
        )

    report = {}

    # ── 1. scrape_runs ────────────────────────────────────────────────────
    # Runs in local but not in base are local-authored. Origin may have reused
    # the same ids independently, so they always get fresh ones.
    base_runs = {r[0] for r in con.execute("SELECT id FROM bse.scrape_runs")}
    local_runs = [
        r for r in con.execute("SELECT * FROM loc.scrape_runs ORDER BY id")
        if r["id"] not in base_runs
    ]
    run_cols = columns(con, "scrape_runs")
    next_run = con.execute("SELECT IFNULL(MAX(id),0) FROM scrape_runs").fetchone()[0] + 1

    run_map = {}
    for r in local_runs:
        run_map[r["id"]] = next_run
        con.execute(
            f"INSERT INTO scrape_runs ({','.join(run_cols)}) "
            f"VALUES ({','.join('?' * len(run_cols))})",
            [next_run if c == "id" else r[c] for c in run_cols],
        )
        next_run += 1
    report["scrape_runs_remapped"] = len(run_map)

    # ── 2. local-only articles ────────────────────────────────────────────
    new_rows = con.execute(
        "SELECT * FROM loc.articles "
        "WHERE url NOT IN (SELECT url FROM main.articles) ORDER BY id"
    ).fetchall()
    insert_cols = [c for c in art_cols if c not in ARTICLE_COLS_SKIP]
    next_id = con.execute("SELECT IFNULL(MAX(id),0) FROM articles").fetchone()[0] + 1

    art_map = {}
    for r in new_rows:
        art_map[r["id"]] = next_id
        con.execute(
            f"INSERT INTO articles (id, scrape_run_id, {','.join(insert_cols)}) "
            f"VALUES ({','.join('?' * (len(insert_cols) + 2))})",
            [next_id, run_map.get(r["scrape_run_id"], r["scrape_run_id"])]
            + [r[c] for c in insert_cols],
        )
        next_id += 1
    report["articles_inserted"] = len(art_map)

    # ── 3. categories for inserted rows ───────────────────────────────────
    ac_new = 0
    for old_id, new_id in art_map.items():
        for (cat_id,) in con.execute(
            "SELECT category_id FROM loc.article_categories WHERE article_id=?", (old_id,)
        ):
            cur = con.execute(
                "INSERT OR IGNORE INTO article_categories (article_id, category_id) "
                "VALUES (?,?)",
                (new_id, cat_id),
            )
            ac_new += max(cur.rowcount, 0)
    report["categories_for_new_rows"] = ac_new

    # ── 4. analysis backfill onto shared rows ─────────────────────────────
    set_clause = ",".join(f"{c}=?" for c in ANALYSIS_COLS)
    pending_shared = con.execute(
        f"SELECT l.id AS lid, l.url AS url, {','.join('l.' + c for c in ANALYSIS_COLS)} "
        "FROM loc.articles l JOIN main.articles m ON m.url = l.url "
        "WHERE l.analyzed_at IS NOT NULL AND m.analyzed_at IS NULL"
    ).fetchall()
    for r in pending_shared:
        con.execute(
            f"UPDATE articles SET {set_clause} WHERE url=?",
            [r[c] for c in ANALYSIS_COLS] + [r["url"]],
        )
    report["analysis_backfilled"] = len(pending_shared)

    # ── 5. categories for newly-analyzed shared rows ──────────────────────
    ac_shared = 0
    for r in pending_shared:
        row = con.execute("SELECT id FROM articles WHERE url=?", (r["url"],)).fetchone()
        if not row:
            continue
        for (cat_id,) in con.execute(
            "SELECT category_id FROM loc.article_categories WHERE article_id=?", (r["lid"],)
        ):
            cur = con.execute(
                "INSERT OR IGNORE INTO article_categories (article_id, category_id) "
                "VALUES (?,?)",
                (row["id"], cat_id),
            )
            ac_shared += max(cur.rowcount, 0)
    report["categories_for_shared_rows"] = ac_shared

    con.commit()
    return con, report


def gates(con, origin_path, local_path, out_path):
    """Every check that must hold before this database may be considered."""
    problems = []

    if con.execute("PRAGMA foreign_key_check").fetchall():
        problems.append("foreign_key_check reported violations")

    ok = con.execute("PRAGMA integrity_check").fetchone()[0]
    if ok != "ok":
        problems.append(f"integrity_check: {ok}")

    dupes = con.execute(
        "SELECT COUNT(*) FROM (SELECT url FROM articles GROUP BY url HAVING COUNT(*)>1)"
    ).fetchone()[0]
    if dupes:
        problems.append(f"{dupes} duplicate urls")

    # Published ids are load-bearing: no row carried over from base may move.
    drift = con.execute(
        "SELECT COUNT(*) FROM main.articles m JOIN bse.articles b USING(url) "
        "WHERE m.id <> b.id"
    ).fetchone()[0]
    if drift:
        problems.append(f"{drift} rows changed id relative to base")

    # Neither side may lose an article to the merge.
    for label, path in (("origin", origin_path), ("local", local_path)):
        probe = sqlite3.connect(out_path)
        probe.execute("ATTACH ? AS s", (path,))
        lost = probe.execute(
            "SELECT COUNT(*) FROM s.articles WHERE url NOT IN (SELECT url FROM main.articles)"
        ).fetchone()[0]
        probe.close()
        if lost:
            problems.append(f"{lost} {label} urls missing from the merge")

    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-git", action="store_true",
                    help="derive base/origin/local from merge-base, origin/main, HEAD")
    ap.add_argument("--base")
    ap.add_argument("--origin")
    ap.add_argument("--local")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="/tmp",
                    help="where --from-git writes its extracted copies")
    args = ap.parse_args()

    if args.from_git:
        base, origin, local = extract_from_git(args.workdir)
    elif args.base and args.origin and args.local:
        base, origin, local = args.base, args.origin, args.local
    else:
        ap.error("pass --from-git, or all of --base/--origin/--local")

    con, report = reconcile(base, origin, local, args.out)

    logger.info("--- reconcile report ---")
    for k, v in report.items():
        logger.info("%-26s %s", k, v)
    totals = con.execute(
        "SELECT COUNT(*), SUM(analyzed_at IS NOT NULL), MAX(id) FROM articles"
    ).fetchone()
    logger.info("%-26s %s rows, %s analyzed, max id %s", "merged", *totals)

    problems = gates(con, origin, local, args.out)
    con.close()

    logger.info("--- gates ---")
    if problems:
        for p in problems:
            logger.error("FAIL: %s", p)
        raise SystemExit(1)
    logger.info("PASS: fk, integrity, duplicate urls, id drift, url loss (both sides)")
    logger.info("merged database written to %s — not landed", args.out)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
