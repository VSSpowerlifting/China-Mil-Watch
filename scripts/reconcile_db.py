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
import contextlib
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

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


def _published_side(path_a: str, path_b: str):
    """
    Return whichever of the two files is the published side, or None.

    The merge is asymmetric — origin keeps its ids because they are already
    live as `output/article/<id>.html` — but git hands a merge driver "ours"
    and "theirs", which say nothing about which side is published. Merging
    origin/main INTO a branch makes origin *theirs*; merging a branch into
    main makes it *ours*. Reading identity off that position would, half the
    time, renumber the published side and silently repoint every article URL.

    So identify it by content instead: hash both candidates and compare against
    the blob at `origin/main`. This is position-independent, which also makes it
    correct under rebase, where ours/theirs are inverted again.
    """
    try:
        want = _git("rev-parse", f"origin/main:{DB_PATH}").decode().strip()
    except subprocess.CalledProcessError:
        return None
    for path in (path_a, path_b):
        if _git("hash-object", path).decode().strip() == want:
            return path
    return None


def _cleanup_sqlite_sidecars(*paths: str) -> None:
    """
    Remove the -shm/-wal files SQLite leaves beside every database it opens.

    In driver mode all four paths are git's own `.merge_file_*` temporaries, so
    their sidecars are pure litter — without this they accumulate as untracked
    files in the repo root on every merge.
    """
    for path in paths:
        for suffix in ("-shm", "-wal"):
            try:
                os.remove(path + suffix)
            except OSError:
                pass


def merge_driver(ancestor: str, current: str, other: str) -> int:
    """
    git merge driver entry point (%O %A %B). The result must land in `current`.

    Refuses rather than guesses: if neither side is the blob at origin/main,
    identity cannot be established and a real conflict is the safe outcome.
    A non-zero exit leaves the conflict for a human, which is correct — this
    driver exists to remove a routine hazard, not to force every merge through.
    """
    published = _published_side(current, other)
    if published is None:
        logger.error(
            "reconcile-db: neither side matches origin/main:%s, so the published "
            "side cannot be identified. Refusing to guess — resolve by hand with "
            "`scripts/reconcile_db.py --base/--origin/--local`.", DB_PATH,
        )
        return 1

    origin_path = published
    local_path = other if published == current else current
    logger.info("reconcile-db: published side is %s",
                "ours (%A)" if published == current else "theirs (%B)")

    tmp = current + ".reconciled"
    accepted = False
    try:
        try:
            con, report = reconcile(ancestor, origin_path, local_path, tmp)
            problems = gates(con, origin_path, local_path, tmp)
            con.close()
        # noqa: BLE001 — any failure, including SystemExit from a FATAL check,
        # must become a git conflict rather than a partially accepted database.
        except (Exception, SystemExit) as exc:
            logger.error("reconcile-db: %s: %s", type(exc).__name__, exc)
            return 1

        if problems:
            for p in problems:
                logger.error("reconcile-db FAIL: %s", p)
            return 1

        shutil.move(tmp, current)
        accepted = True
    finally:
        # Sidecars for every path we opened, plus — when the merge was NOT
        # accepted — the temporary database itself. Leaving it behind litters
        # the repository root after each failed unattended merge. `current`
        # (git's merge target) and the three inputs are never removed: a failed
        # merge must leave the conflict exactly as git set it up.
        _cleanup_sqlite_sidecars(ancestor, current, other, tmp)
        if not accepted:
            try:
                os.remove(tmp)
            except OSError:
                pass
    logger.info("reconcile-db: merged %s new article(s), backfilled %s analysis row(s)",
                report["articles_inserted"], report["analysis_backfilled"])
    return 0


def install_driver() -> int:
    """
    Register the driver in .git/config.

    Merge drivers cannot be configured from a committed file — `.gitattributes`
    only names the driver, so every clone (and every CI runner) must run this
    once or the attribute silently falls back to a binary conflict.

    The interpreter is taken from `sys.executable` rather than hardcoded: local
    checkouts run this under `.venv/bin/python`, but CI installs deps against the
    runner's own python and has no `.venv` at all, so a fixed path would leave CI
    silently unprotected — precisely where an unattended conflict is most costly.
    """
    _git("config", "merge.reconcile-db.name",
         "row-level pla_watch.db reconciliation")
    _git("config", "merge.reconcile-db.driver",
         f"{sys.executable} scripts/reconcile_db.py --merge-driver %O %A %B")
    logger.info("registered merge.reconcile-db driver (%s)", sys.executable)
    return 0


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


def _attached_columns(con, schema, table):
    """Column names of a table in an ATTACHed database, or [] if absent."""
    try:
        return [r[1] for r in con.execute(f"PRAGMA {schema}.table_info({table})")]
    except sqlite3.Error:
        return []


# Tables every input must have, whatever its migration level.
LEGACY_TABLES = ("articles", "sources", "categories", "article_categories",
                 "scrape_runs")

# If a post-0001 table is present at all, it must carry at least these columns,
# or this script cannot read it safely. A legacy input that simply lacks the
# table is fine — that is what normalize_schema() exists for.
NEWER_TABLE_MINIMUM = {
    "source_run_results": ("scrape_run_id", "source_slug", "status"),
    "schema_migrations": ("version",),
    "desks": ("desk_id",),
    "institutions": ("institution_id", "desk_id"),
}


@contextlib.contextmanager
def _read_only(path):
    """
    Read a database with no possibility of altering the original.

    A plain `sqlite3.connect()` can write to an input merely by opening it
    (journal/WAL recovery, checkpointing). A `mode=ro` URI avoids that but
    cannot open a WAL-mode database whose `-wal` is present — SQLite needs to
    write the WAL index to read it — and inputs written by this project are in
    WAL mode.

    So: copy the database and any sidecars to a scratch directory and read the
    copy. The original is untouched by construction rather than by hoping, and
    a hot WAL is recovered into the copy instead of being ignored (dropping the
    `-wal` would silently hide committed rows from validation).
    """
    tmpdir = tempfile.mkdtemp(prefix="reconcile-validate-")
    try:
        target = os.path.join(tmpdir, "input.db")
        shutil.copyfile(path, target)
        for suffix in ("-wal", "-shm"):
            side = path + suffix
            if os.path.exists(side):
                shutil.copyfile(side, target + suffix)
        con = sqlite3.connect(target)
        try:
            yield con
        finally:
            con.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def validate_inputs(base_path, origin_path, local_path):
    """
    Read-only preflight over base, origin and local. Raises SystemExit on any
    defect, before the merge target is touched.

    The distinction that matters: **a legacy input is valid; a corrupt one is
    not.** Missing newer tables and a missing migration ledger are normal and
    expected — they are exactly what this script migrates. Internal corruption,
    dangling foreign keys, a missing legacy table, or a newer table that exists
    but is structurally unreadable are defects, and merging from them can only
    produce a wrong answer.
    """
    problems = []
    for label, path in (("base", base_path), ("origin", origin_path),
                        ("local", local_path)):
        try:
            ctx = _read_only(path)
            con = ctx.__enter__()
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{label}: cannot open for validation: {exc}")
            continue
        try:
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                problems.append(f"{label}: integrity_check: {integrity}")

            violations = con.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                problems.append(
                    f"{label}: {len(violations)} foreign key violation(s), "
                    f"e.g. {violations[:3]}"
                )

            present = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            for table in LEGACY_TABLES:
                if table not in present:
                    problems.append(f"{label}: required table '{table}' missing")

            for table, required in NEWER_TABLE_MINIMUM.items():
                if table not in present:
                    continue          # legitimately pre-migration
                cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
                missing = [c for c in required if c not in cols]
                if missing:
                    problems.append(
                        f"{label}: table '{table}' exists but lacks {missing}"
                    )
        except sqlite3.Error as exc:
            problems.append(f"{label}: unreadable: {exc}")
        finally:
            ctx.__exit__(None, None, None)

    if problems:
        raise SystemExit(
            "FATAL: reconciliation inputs failed validation; refusing to merge.\n  "
            + "\n  ".join(problems)
        )


def _has_table(con, schema, table):
    row = con.execute(
        f"SELECT 1 FROM {schema}.sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def normalize_schema(out_path):
    """
    Bring the output copy to the current schema BEFORE any row is merged.

    This is the fix for two defects found in review, both of which produced a
    silently wrong database with every gate passing:

      * A legacy origin blob made the merged output legacy too — no
        `source_run_results`, no `schema_migrations`, no `desks`, and a
        `scrape_runs` CHECK that does not accept 'degraded'. The schema
        regressed and the reconciler said nothing.
      * A local run with status 'degraded' could not be inserted into a
        pre-hotfix origin at all: the INSERT raised IntegrityError, the driver
        exited non-zero, and CI got a raw binary conflict — unattended, on the
        path where a conflict is most expensive.

    Migrating the output first makes the merge target always current, so the
    statuses and tables the local side may carry are supported before anything
    is inserted. Deliberately NOT left to `init_db()` on the next pipeline run:
    by then the regressed database has already been committed and pushed, and
    rows that reconciliation dropped are gone regardless of what a later
    migration rebuilds.

    Only the OUTPUT copy is touched. base/origin/local are read-only inputs.

    The import is local to this function and the whole migration chain is
    stdlib-only (verified), so `--install-driver` still runs on a CI runner
    before `pip install`.
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from migrations.runner import apply_all, applied_versions, connect, discover

    con = connect(out_path)
    try:
        report = apply_all(con)
        ledger = set(applied_versions(con))
        expected = {m.version for m in discover()}
        missing = sorted(expected - ledger)
        if missing:
            raise SystemExit(
                f"FATAL: migrations did not complete on the merge output; "
                f"missing {missing}. Refusing to merge into a database whose "
                "schema is not current."
            )
    finally:
        con.close()

    _cleanup_sqlite_sidecars(out_path)
    return report


def reconcile(base_path, origin_path, local_path, out_path):
    # Nothing is copied or written until every input has been proven readable.
    validate_inputs(base_path, origin_path, local_path)

    shutil.copyfile(origin_path, out_path)

    # Schema first, rows second. See normalize_schema().
    migration_report = normalize_schema(out_path)

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

    report = {
        "migrations_applied": migration_report.get("applied", []),
        "migrations_already_present": migration_report.get("already_present", []),
    }

    # ── 1. scrape_runs ────────────────────────────────────────────────────
    # Runs in local but not in base are local-authored. Origin may have reused
    # the same ids independently, so they always get fresh ones.
    base_runs = {r[0] for r in con.execute("SELECT id FROM bse.scrape_runs")}
    local_runs = [
        r for r in con.execute("SELECT * FROM loc.scrape_runs ORDER BY id")
        if r["id"] not in base_runs
    ]
    # Intersect with the local side's columns: the output is now migrated and may
    # legitimately carry columns a legacy local blob does not have. Reading a
    # missing key off the local row would raise mid-merge.
    local_run_cols = set(_attached_columns(con, "loc", "scrape_runs"))
    run_cols = [c for c in columns(con, "scrape_runs") if c in local_run_cols]
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
    local_art_cols = set(_attached_columns(con, "loc", "articles"))
    # `source_id` joins the skip list: a numeric source id is meaningless across
    # two independently evolved databases. Carrying it verbatim silently
    # re-attributed articles — a local PLA Daily article whose `sources.id`
    # happened to equal origin's `mod_china` id was merged AS mod_china, with
    # every gate green. Attribution is resolved by slug below.
    insert_cols = [
        c for c in art_cols
        if c not in ARTICLE_COLS_SKIP and c != "source_id" and c in local_art_cols
    ]

    # slug is the only stable source identity across databases.
    loc_slug_by_id = {
        r[0]: r[1] for r in con.execute("SELECT id, slug FROM loc.sources")
    }
    out_id_by_slug = {}
    for sid, slug in con.execute("SELECT id, slug FROM main.sources"):
        if slug in out_id_by_slug:
            raise SystemExit(
                f"FATAL: merge output has more than one source with slug "
                f"{slug!r}; source identity is ambiguous."
            )
        out_id_by_slug[slug] = sid

    def resolve_source(local_source_id, url):
        slug = loc_slug_by_id.get(local_source_id)
        if slug is None:
            raise SystemExit(
                f"FATAL: local article {url} references source_id "
                f"{local_source_id}, which has no row in local `sources`. "
                "Refusing to guess its origin."
            )
        out_id = out_id_by_slug.get(slug)
        if out_id is None:
            raise SystemExit(
                f"FATAL: local article {url} belongs to source {slug!r}, which "
                "does not exist in the merged database. Sources are configured "
                "through desk manifests and migrations — a source that cannot "
                "be mapped that way must be reviewed by a human, not invented "
                "from local metadata."
            )
        return out_id

    # A URL both sides hold must mean the same source on both sides.
    for r in con.execute(
        "SELECT l.url AS url, l.source_id AS lsid, m.source_id AS msid "
        "FROM loc.articles l JOIN main.articles m ON m.url = l.url"
    ):
        local_slug = loc_slug_by_id.get(r["lsid"])
        origin_row = con.execute(
            "SELECT slug FROM main.sources WHERE id = ?", (r["msid"],)
        ).fetchone()
        origin_slug = origin_row[0] if origin_row else None
        if local_slug != origin_slug:
            raise SystemExit(
                f"FATAL: {r['url']} is attributed to {origin_slug!r} in origin "
                f"and {local_slug!r} in local. A shared URL with conflicting "
                "source attribution cannot be merged automatically."
            )

    next_id = con.execute("SELECT IFNULL(MAX(id),0) FROM articles").fetchone()[0] + 1

    art_map = {}
    for r in new_rows:
        art_map[r["id"]] = next_id
        con.execute(
            f"INSERT INTO articles (id, scrape_run_id, source_id, "
            f"{','.join(insert_cols)}) "
            f"VALUES ({','.join('?' * (len(insert_cols) + 3))})",
            [next_id,
             run_map.get(r["scrape_run_id"], r["scrape_run_id"]),
             resolve_source(r["source_id"], r["url"])]
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
    # Gating this on analyzed_at alone loses every screening decision that did
    # not end in a full analysis (found 2026-08-04): a relevance *rejection*
    # writes passed_relevance and leaves analyzed_at NULL, as do translation and
    # summary failures. Merging origin into a branch that had screened 156
    # articles silently returned 46 of them — 43 rejections + 3 failures — to
    # the unscored pool, discarding their scores and reasonings, which are the
    # audit record, and queueing them to be screened (and paid for) again.
    # passed_relevance is the decision column, so it is what the predicate must
    # test. Rows where origin already holds a decision are left alone, exactly
    # as before.
    set_clause = ",".join(f"{c}=?" for c in ANALYSIS_COLS)
    pending_shared = con.execute(
        f"SELECT l.id AS lid, l.url AS url, {','.join('l.' + c for c in ANALYSIS_COLS)} "
        "FROM loc.articles l JOIN main.articles m ON m.url = l.url "
        "WHERE (l.analyzed_at IS NOT NULL AND m.analyzed_at IS NULL) "
        "   OR (l.passed_relevance IS NOT NULL AND m.passed_relevance IS NULL)"
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

    # ── 6. per-source collection results ──────────────────────────────────
    # Origin's rows are already in the output (it was the base copy). Local rows
    # are merged in on top. Without this, every per-source observation written
    # locally since the last push was silently deleted by the merge while every
    # gate passed — which is the steady-state daily shape once CI writes these
    # rows, so the observability Phase 2 added would have evaporated on contact
    # with the reconciler.
    #
    # SOURCE IDENTITY: `source_run_results.source_slug` is TEXT, so identity is
    # the slug itself. Numeric `sources.id` values are NOT comparable across two
    # independently evolved databases and are deliberately never used here — no
    # guessing is required, which is why this merge is safe to automate.
    #
    # RUN IDENTITY: local runs absent from base were renumbered above origin's
    # maximum in step 1. Their results must follow that remap, or they would
    # attach to an unrelated origin run — or to nothing.
    #
    # CONFLICT RULE: the natural key is (scrape_run_id, source_slug) AFTER the
    # remap. A true collision can only happen on a run both sides share (a run
    # present in base), where each side independently recorded the same source.
    # Published/origin wins, consistent with origin being authoritative for
    # identity everywhere else in this script. Local-only rows are always kept.
    srr_merged = 0
    srr_conflicts = 0
    if _has_table(con, "main", "source_run_results"):
        out_srr_cols = columns(con, "source_run_results")
        # Substantive payload: everything except the surrogate key. Two sides
        # allocate `id` independently, so it carries no meaning across a merge.
        cmp_cols = [c for c in out_srr_cols if c != "id"]

        # Expected map, built BEFORE the merge writes anything. Origin's rows
        # are already in the output because it was the base copy.
        expected = {
            (r["scrape_run_id"], r["source_slug"]):
                tuple(r[c] for c in cmp_cols)
            for r in con.execute("SELECT * FROM source_run_results")
        }
        origin_keys = set(expected)

        if _has_table(con, "loc", "source_run_results"):
            loc_srr_cols = set(_attached_columns(con, "loc", "source_run_results"))
            unreadable = [c for c in cmp_cols if c not in loc_srr_cols]
            if unreadable:
                raise SystemExit(
                    "FATAL: local source_run_results lacks columns "
                    f"{unreadable}; the merge cannot be verified exactly. "
                    "Reconcile by hand."
                )
            copy_cols = [c for c in cmp_cols if c != "scrape_run_id"]

            # Run lineage. A local row's run must be provably one of:
            #   * local-authored and renumbered in step 1  -> run_map
            #   * inherited from the merge base            -> same id, verified
            # Anything else is unmappable. It is NOT enough that some run with
            # the same numeric id exists in the output: origin allocates ids
            # independently, so a dangling local id can coincide with a real and
            # entirely unrelated origin run. Attaching an observation there
            # misfiles analytical provenance, which is worse than losing it.
            local_run_ids = {
                r[0] for r in con.execute("SELECT id FROM loc.scrape_runs")
            }
            unmappable = []

            for r in con.execute("SELECT * FROM loc.source_run_results ORDER BY id"):
                local_run = r["scrape_run_id"]
                if local_run in run_map:
                    mapped_run = run_map[local_run]
                elif local_run in base_runs and local_run in local_run_ids:
                    mapped_run = local_run          # shared, base-inherited run
                else:
                    unmappable.append((local_run, r["source_slug"]))
                    continue

                if not con.execute(
                    "SELECT 1 FROM scrape_runs WHERE id=?", (mapped_run,)
                ).fetchone():
                    unmappable.append((local_run, r["source_slug"]))
                    continue

                key = (mapped_run, r["source_slug"])
                if key in expected:
                    srr_conflicts += 1              # true conflict: origin wins
                    continue
                payload = []
                for c in cmp_cols:
                    payload.append(mapped_run if c == "scrape_run_id" else r[c])
                expected[key] = tuple(payload)
                con.execute(
                    f"INSERT INTO source_run_results "
                    f"(scrape_run_id, {','.join(copy_cols)}) "
                    f"VALUES ({','.join('?' * (len(copy_cols) + 1))})",
                    [mapped_run] + [r[c] for c in copy_cols],
                )
                srr_merged += 1

            if unmappable:
                raise SystemExit(
                    "FATAL: %d local source_run_result(s) reference a run whose "
                    "lineage cannot be proven (not local-authored, not inherited "
                    "from the merge base): %r. These are collection observations "
                    "with analytical provenance — reconciliation stops rather "
                    "than dropping them or attaching them to another run."
                    % (len(unmappable), unmappable[:5])
                )

        # Exact accounting. Not "does this slug appear somewhere" — that check
        # let a dropped row hide behind an unrelated row with the same slug.
        actual = {
            (r["scrape_run_id"], r["source_slug"]): tuple(r[c] for c in cmp_cols)
            for r in con.execute("SELECT * FROM source_run_results")
        }
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        altered = sorted(
            k for k in set(expected) & set(actual) if expected[k] != actual[k]
        )
        if missing or extra or altered:
            raise SystemExit(
                "FATAL: source_run_results accounting failed — "
                f"missing={missing[:5]} unexpected={extra[:5]} altered={altered[:5]}"
            )
        report["source_results_expected"] = len(expected)
        report["source_results_from_origin"] = len(origin_keys)

    report["source_results_merged"] = srr_merged
    report["source_results_origin_won"] = srr_conflicts

    con.commit()
    return con, report


REQUIRED_TABLES = (
    "articles", "sources", "categories", "article_categories", "scrape_runs",
    "schema_migrations", "desks", "institutions", "source_run_results",
)


def _statuses_in(path):
    """Distinct scrape_runs.status values present in a database file."""
    with _read_only(path) as probe:
        try:
            return {r[0] for r in probe.execute(
                "SELECT DISTINCT status FROM scrape_runs") if r[0] is not None}
        except sqlite3.Error:
            return set()


def _srr_keys(path):
    """(scrape_run_id, source_slug) pairs, or None when the table is absent."""
    with _read_only(path) as probe:
        try:
            has = probe.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='source_run_results'").fetchone()
            if not has:
                return None
            return {(r[0], r[1]) for r in probe.execute(
                "SELECT scrape_run_id, source_slug FROM source_run_results")}
        except sqlite3.Error:
            return None


def _srr_payloads(path, payload_cols):
    """
    {(run, slug): payload tuple} or None when the table is absent.

    `payload_cols` must NOT include `scrape_run_id`: the run is part of the key,
    and a local row legitimately changes run id when its run is remapped.
    Including it would report every correctly remapped row as "payload altered".
    """
    with _read_only(path) as probe:
        probe.row_factory = sqlite3.Row
        try:
            has = probe.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='source_run_results'").fetchone()
            if not has:
                return None
            cols = {r[1] for r in probe.execute(
                "PRAGMA table_info(source_run_results)")}
            if not set(payload_cols) <= cols:
                return None
            return {
                (r["scrape_run_id"], r["source_slug"]):
                    tuple(r[c] for c in payload_cols)
                for r in probe.execute("SELECT * FROM source_run_results")
            }
        except sqlite3.Error:
            return None


def _run_lineage(con, origin_path):
    """
    {local run id -> merged run id}, recovered independently of reconcile().

    `gates()` receives database paths, not reconcile()'s `run_map`, so lineage
    is re-derived here rather than taken on trust from the code under test:

      * a run inherited from the merge base keeps its id;
      * a local-authored run was renumbered above origin's maximum, so the
        candidates are exactly the output runs present in NEITHER the base nor
        origin, matched by their verbatim-copied payload.

    Excluding origin's ids is what makes this exact. Matching only against
    "not in base" was ambiguous: origin's own new runs are also absent from the
    base, and an origin run whose payload happened to equal a local run's — two
    runs created the same second with default counters, which is routine —
    absorbed the match and made a correctly merged result look unaccounted.

    A local run matching neither rule is deliberately absent from the result;
    callers treat missing lineage as unaccounted, never as "fine".
    """
    payload_cols = ["started_at", "completed_at", "articles_scraped",
                    "articles_new", "articles_analyzed", "errors", "status"]
    have = {r[1] for r in con.execute("PRAGMA table_info(scrape_runs)")}
    payload_cols = [c for c in payload_cols if c in have]
    sel = ", ".join(payload_cols)

    base_ids = {r[0] for r in con.execute("SELECT id FROM bse.scrape_runs")}
    out_ids = {r[0] for r in con.execute("SELECT id FROM main.scrape_runs")}

    with _read_only(origin_path) as probe:
        try:
            origin_ids = {r[0] for r in probe.execute("SELECT id FROM scrape_runs")}
        except sqlite3.Error:
            origin_ids = set()

    candidates = {}
    for row in con.execute(f"SELECT id, {sel} FROM main.scrape_runs"):
        if row[0] in base_ids or row[0] in origin_ids:
            continue
        candidates.setdefault(tuple(row[1:]), []).append(row[0])
    for ids in candidates.values():
        ids.sort()

    lineage = {}
    for row in con.execute(f"SELECT id, {sel} FROM loc.scrape_runs ORDER BY id"):
        local_id = row[0]
        if local_id in base_ids and local_id in out_ids:
            lineage[local_id] = local_id
            continue
        matches = candidates.get(tuple(row[1:]))
        if matches:
            lineage[local_id] = matches.pop(0)
    return lineage


def _url_slug_map(path):
    """{article url: source slug} for a database file, or {} if unreadable."""
    with _read_only(path) as probe:
        try:
            return {
                r[0]: r[1] for r in probe.execute(
                    "SELECT a.url, s.slug FROM articles a "
                    "JOIN sources s ON s.id = a.source_id")
            }
        except sqlite3.Error:
            return {}


def gates(con, origin_path, local_path, out_path):
    """
    Every check that must hold before this database may be considered.

    Expanded after review: the previous set proved row and id preservation but
    was silent about schema. A merge that dropped `source_run_results` entirely
    and reverted the `scrape_runs` CHECK passed all of it. **A missing table is
    now a failure, never treated as an empty one.**
    """
    problems = []

    # ── schema currency ───────────────────────────────────────────────────
    present = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for table in REQUIRED_TABLES:
        if table not in present:
            problems.append(
                f"required table '{table}' is missing from the merge output "
                "(a missing table is not an empty table)"
            )

    if "schema_migrations" in present:
        try:
            repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)
            from migrations.runner import discover
            expected = {m.version for m in discover()}
            have = {r[0] for r in con.execute(
                "SELECT version FROM schema_migrations")}
            missing = sorted(expected - have)
            if missing:
                problems.append(f"migration ledger incomplete: missing {missing}")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"could not verify migration ledger: {exc}")

    # The output must accept every status either input legitimately carries,
    # or inserting those runs would have raised — or will raise on the next
    # write of a status the merged file cannot represent.
    run_sql = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='scrape_runs'"
    ).fetchone()
    if run_sql:
        for status in sorted(_statuses_in(origin_path) | _statuses_in(local_path)):
            if f"'{status}'" not in run_sql[0]:
                problems.append(
                    f"merged scrape_runs CHECK does not accept status "
                    f"'{status}', which is present in an input database"
                )

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

    # Nor may either side lose a screening *decision*. Counting rows and ids is
    # not enough: the 2026-08-04 defect kept every article and every id, and
    # still discarded 46 relevance decisions, because a reverted row looks
    # exactly like an unscreened one. A decision is expensive (a paid call) and
    # is the audit record, so its loss has to be an error, not a diff nobody reads.
    for label, path in (("origin", origin_path), ("local", local_path)):
        probe = sqlite3.connect(out_path)
        probe.execute("ATTACH ? AS s", (path,))
        dropped = probe.execute(
            "SELECT COUNT(*) FROM s.articles s2 JOIN main.articles m USING(url) "
            " WHERE s2.passed_relevance IS NOT NULL AND m.passed_relevance IS NULL"
        ).fetchone()[0]
        probe.close()
        if dropped:
            problems.append(
                f"{dropped} {label} relevance decision(s) lost in the merge"
            )

    # ── per-source results survive from both sides ────────────────────────
    # Counting articles and decisions is not enough: local per-source rows were
    # being deleted wholesale while every other gate passed. Origin's keys are
    # compared directly; local's are compared after the run remap, because a
    # renumbered local run legitimately changes the key.
    merged_keys = _srr_keys(out_path)
    if merged_keys is None:
        problems.append("merge output has no source_run_results table")
    else:
        # Payload excludes `id` (surrogate) and `scrape_run_id` (part of the
        # key, and legitimately rewritten by the run remap).
        payload_cols = [c for c in columns(con, "source_run_results")
                        if c not in ("id", "scrape_run_id")]
        merged_payloads = _srr_payloads(out_path, payload_cols) or {}

        # Exact accounting, independently recomputed here. The earlier version
        # asked only whether a slug appeared *somewhere* in the output, so a
        # dropped row was invisible whenever any other row shared its slug.
        origin_payloads = _srr_payloads(origin_path, payload_cols)
        if origin_payloads:
            lost = sorted(set(origin_payloads) - set(merged_keys))
            if lost:
                problems.append(
                    f"{len(lost)} origin source_run_result(s) missing from the "
                    f"merge, e.g. {lost[:3]}"
                )
            changed = sorted(
                k for k in set(origin_payloads) & set(merged_payloads)
                if origin_payloads[k] != merged_payloads[k]
            )
            if changed:
                problems.append(
                    f"{len(changed)} origin source_run_result payload(s) altered "
                    f"by the merge, e.g. {changed[:3]}"
                )

        # Local rows are compared after the run remap. A local row is accounted
        # for when its (mapped run, slug) is present with an identical payload;
        # since only origin may win a true conflict, the alternative is that
        # origin already held that exact key.
        local_payloads = _srr_payloads(local_path, payload_cols)
        lineage = _run_lineage(con, origin_path) if local_payloads else {}
        if local_payloads:
            unaccounted = []
            for (local_run, slug), payload in sorted(local_payloads.items()):
                mapped = lineage.get(local_run)
                if mapped is None:
                    unaccounted.append((local_run, slug, "run lineage unproven"))
                    continue
                key = (mapped, slug)
                if key not in merged_payloads:
                    unaccounted.append((local_run, slug, "absent from merge"))
                    continue
                if (merged_payloads[key] != payload
                        and key not in (origin_payloads or {})):
                    unaccounted.append((local_run, slug, "payload altered"))
            if unaccounted:
                problems.append(
                    f"{len(unaccounted)} local source_run_result(s) unaccounted "
                    f"for, e.g. {unaccounted[:3]}"
                )

        accounted = set(origin_payloads or {}) | {
            (lineage[run], slug)
            for run, slug in (local_payloads or {}) if run in lineage
        }
        unexpected = sorted(set(merged_keys) - accounted)
        if unexpected:
            problems.append(
                f"{len(unexpected)} source_run_result(s) in the merge belong to "
                f"neither input, e.g. {unexpected[:3]}"
            )

        dupes = con.execute(
            "SELECT COUNT(*) FROM (SELECT scrape_run_id, source_slug "
            "FROM source_run_results GROUP BY 1,2 HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        if dupes:
            problems.append(
                f"{dupes} duplicate source_run_result natural key(s) "
                "(scrape_run_id, source_slug)"
            )

        orphaned = con.execute(
            "SELECT COUNT(*) FROM source_run_results r "
            "LEFT JOIN scrape_runs s ON s.id = r.scrape_run_id "
            "WHERE s.id IS NULL"
        ).fetchone()[0]
        if orphaned:
            problems.append(
                f"{orphaned} source_run_result(s) reference a run that does not "
                "exist in the merged database"
            )

    # ── article attribution, by slug ──────────────────────────────────────
    # Numeric source ids may legitimately differ between two independently
    # evolved databases. What must never differ is which SOURCE an article is
    # attributed to. Comparing slugs catches the silent re-attribution that
    # carrying `source_id` verbatim used to produce.
    origin_urls = _url_slug_map(origin_path)
    local_urls = _url_slug_map(local_path)
    merged_urls = _url_slug_map(out_path)

    expected_urls = dict(origin_urls)
    for url, slug in local_urls.items():
        if url in expected_urls:
            if expected_urls[url] != slug:
                problems.append(
                    f"{url} is attributed to {expected_urls[url]!r} in origin and "
                    f"{slug!r} in local — conflicting source attribution"
                )
        else:
            expected_urls[url] = slug

    misattributed = sorted(
        (url, expected_urls[url], merged_urls.get(url))
        for url in expected_urls
        if merged_urls.get(url) != expected_urls[url]
    )
    if misattributed:
        problems.append(
            f"{len(misattributed)} article(s) changed source in the merge, "
            f"e.g. {misattributed[:3]}"
        )

    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-git", action="store_true",
                    help="derive base/origin/local from merge-base, origin/main, HEAD")
    ap.add_argument("--merge-driver", nargs=3, metavar=("ANCESTOR", "CURRENT", "OTHER"),
                    help="git merge driver mode (%%O %%A %%B); result is written to CURRENT")
    ap.add_argument("--install-driver", action="store_true",
                    help="register the driver in .git/config (needed once per clone)")
    ap.add_argument("--base")
    ap.add_argument("--origin")
    ap.add_argument("--local")
    ap.add_argument("--out")
    ap.add_argument("--workdir", default="/tmp",
                    help="where --from-git writes its extracted copies")
    args = ap.parse_args()

    if args.install_driver:
        raise SystemExit(install_driver())

    if args.merge_driver:
        raise SystemExit(merge_driver(*args.merge_driver))

    if not args.out:
        ap.error("--out is required unless using --merge-driver or --install-driver")

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
