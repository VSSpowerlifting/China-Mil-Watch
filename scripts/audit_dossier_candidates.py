#!/usr/bin/env python3
"""Bounded, read-only *discovery* audit for possible IPR Living Dossiers.

Candidate matches are title/category leads, NOT approved citations, source-use
clearance, independent event counts, factual findings, or public coverage.
No network, model, writes to the tracked DB, or output/ changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.reconcile_db import read_only

TOPICS = {
    "South China Sea maritime reporting": {
        "terms": ("南海", "黄岩", "仁爱礁", "仙宾礁", "美济礁",
                  "south china sea", "west philippine sea",
                  "scarborough", "second thomas", "sabina shoal"),
        "category": "south_china_sea",
        "purpose": "Recurring official accounts of maritime developments, not event adjudication.",
    },
    "China–Singapore military contact": {
        "terms": ("新加坡", "singapore", "中新"),
        "bilateral": True,
        "second": ("军", "防", "部队", "海军", "联合", "战舰", "exercise",
                   "military", "navy", "defence", "defense", "maritime", "cooperation"),
        "purpose": "Bilateral exchanges/exercises, not all Singapore defence news.",
    },
    "Philippines maritime security": {
        "terms": ("菲律宾", "菲方", "马尼拉", "philippin", "manila",
                  "west philippine sea", "scarborough", "黄岩", "仁爱礁"),
        "second": ("海", "军", "船", "警", "岛", "礁", "maritime",
                   "navy", "coast", "sea", "vessel", "ship", "security"),
        "purpose": "Philippines-linked maritime episodes, not an exhaustive national maritime record.",
    },
    "Regional exercise diplomacy": {
        "terms": ("联合演习", "联演", "联合训练", "军事交流", "防务合作",
                  "军演", "演习", "joint exercise", "bilateral exercise", "exercise",
                  "maritime cooperation", "defence cooperation",
                  "defense cooperation", "military exercise"),
        "regional": True,
        "purpose": "Exercises/cooperation reported by official publishers across desks.",
    },
    "Singapore naval exercise diplomacy": {
        "terms": ("exercise", "演习"),
        "desk": "singapore",
        "second": ("navy", "navies", "maritime", "naval", "bilateral", "fleet", "海军"),
        "purpose": "MINDEF announcements about Singapore naval exercises with foreign partners; a single issuing perspective.",
    },
    "Taiwan Strait military messaging (contrast)": {
        "terms": ("台湾", "台海", "台岛", "taiwan strait", "taiwan"),
        "category": "taiwan",
        "purpose": "Contrast case likely dominated by a single issuing perspective.",
    },
}
ISSUE_BASE = "https://github.com/VSSpowerlifting/China-Mil-Watch/issues/319"


def norm(text):
    return (text or "").casefold()


def match_topic(row, categories, query):
    title = norm(row["title_original"]) + " " + norm(row["title_english"])
    if not title.strip():
        return False, False
    primary = any(term in title for term in query["terms"])
    via_category = bool(query.get("category") in categories)
    secondary = query.get("second")
    title_match = primary and (secondary is None or any(t in title for t in secondary))
    if query.get("desk") and row["desk_id"] != query["desk"]:
        title_match = False
    if query.get("bilateral"):
        # A Singapore MINDEF headline routinely says "Singapore"; require a
        # China counterpart as well, not any MINDEF exercise with another state.
        china = any(t in title for t in ("中国", "中方", "中新", "解放军", "china", "chinese", "pla"))
        singapore = any(t in title for t in ("新加坡", "中新", "singapore"))
        title_match = title_match and china and singapore
    if query.get("regional"):
        partner = any(t in title for t in (
            "联合", "中泰", "中老", "中新", "中柬", "中越", "与", "东盟",
            "bilateral", "joint", "multinational", "foreign", "singapore",
            "malays", "philippin", "brunei", "indones", "laos", "vietnam",
            "cambod", "thailand", "australia", "russia"))
        title_match = title_match and partner
    # Category assignment is model-originated and is merely a discovery lead.
    return title_match or via_category, title_match


def cover_span(rows):
    dates = [r["published_date"] for r in rows if r["published_date"]]
    return (min(dates), max(dates)) if dates else ("unavailable", "unavailable")


def clean(s, cap=86):
    # Human-readable publisher titles are leads, NOT attested source excerpts.
    return re.sub(r"\s+", " ", (s or "")).replace("|", "/")[:cap]


def audit(database, max_examples):
    db_sha = hashlib.sha256(database.read_bytes()).hexdigest()
    registry = json.loads((ROOT / "desks/registry.json").read_text(encoding="utf-8"))
    desks = {d["slug"]: d for d in registry["desks"]}
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          check=True, text=True, capture_output=True).stdout.strip()
    with read_only(database) as conn:
        conn.row_factory = __import__("sqlite3").Row
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or foreign_keys:
            raise RuntimeError("tracked database failed read-only integrity/FK check")
        schema = {r[1] for r in conn.execute("PRAGMA table_info(sources)")}
        if "desk_id" not in schema:
            raise RuntimeError("source desk IDs missing: do not guess provenance")
        columns = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
        required = {"id", "published_date", "title_original", "title_english",
                    "url", "content_hash", "passed_relevance"}
        if not required.issubset(columns):
            raise RuntimeError("unexpected archive article schema")
        rows = [dict(r) for r in conn.execute("""
          SELECT a.id, a.published_date, a.title_original, a.title_english,
                 a.url, a.content_hash, a.passed_relevance,
                 s.slug AS source_slug, s.display_name AS publisher,
                 s.desk_id
          FROM articles a JOIN sources s ON s.id = a.source_id
          ORDER BY a.id
        """)]
        category_map = defaultdict(set)
        for rid, cat in conn.execute("""
          SELECT ac.article_id, c.slug FROM article_categories ac
          JOIN categories c ON c.id = ac.category_id
        """):
            category_map[rid].add(cat)

    live = {k for k, d in desks.items() if d["status"] == "live" and d["public"]}
    stored = [r for r in rows if r["desk_id"] in live]
    excluded = [r for r in rows if r["desk_id"] not in live]
    lines = [
        "# Living Dossiers B0 — preserved-record title discovery audit",
        "",
        "**Status: exploratory evidence discovery, NOT a dossier publication or source approval.**",
        "",
        f"- Git snapshot: \`{head}\`.",
        f"- Tracked DB SHA-256: \`{db_sha}\`.",
        f"- Stored article rows: **{len(rows)}**; declared live-desk rows: **{len(stored)}**; rows outside live-desk scope: **{len(excluded)}**.",
        f"- Record publication-date span (stored live-desk rows): **{cover_span(stored)[0]} to {cover_span(stored)[1]}**.",
        "- Query scope: stored *original and translated titles*, plus existing desk-specific category labels. No publisher-site re-fetch, model reasoning, or use of full source bodies; title matching and category assignments are triage leads only.",
        "- Record IDs, URLs and dates below are copied from archived SQLite rows. They have NOT been independently reconciled against original-language full text, rights, source-site versions, or reporting events.",
        "",
        "## Declared desk status and measured archive counts",
        "",
        "| Desk | Registry status | Stored rows | Limits |",
        "|---|---|---:|---|",
    ]
    totals = Counter(r["desk_id"] for r in rows)
    for slug, d in desks.items():
        limits = clean((d.get("limits") or ["No completeness claim."])[0], 130)
        lines.append(f"| {slug} | {d['status']} | {totals[slug]} | {limits} |")
    lines += ["", "## Lexical candidate comparison", "",
              "| Candidate subject | Title/category leads | Title-only hits | Distinct dates | Weeks | Desks | Publishers | Date range |",
              "|---|---:|---:|---:|---:|---:|---:|---|"]
    reports = {}
    for label, query in TOPICS.items():
        matches, only = [], 0
        for r in stored:
            qualifies, in_title = match_topic(r, category_map[r["id"]], query)
            if qualifies:
                matches.append(r)
                only += int(in_title)
        reports[label] = matches
        dates = {r["published_date"] for r in matches if r["published_date"]}
        weeks = {d[:7] + "-w" + str((int(d[8:10])-1)//7 + 1) for d in dates}
        groups = {r["desk_id"] for r in matches}
        sources = {r["source_slug"] for r in matches}
        span = " – ".join(cover_span(matches))
        lines.append(f"| {label} | {len(matches)} | {only} | {len(dates)} | {len(weeks)} | {len(groups)} | {len(sources)} | {span} |")
    lines += ["", "## Candidate preserved-record leads", "",
              "The following records are *sampled pointers*, not a source-to-claim matrix. One source or announcement can describe the same event as another; distinct IDs/dates do not establish independent developments.",
              ""]
    for label, matches in reports.items():
        query = TOPICS[label]
        lines += [f"### {label}", "", query["purpose"], ""]
        title_matches = [r for r in matches if match_topic(r, category_map[r["id"]], query)[1]]
        by_desk = Counter(r["desk_id"] for r in matches)
        by_source = Counter(r["source_slug"] for r in matches)
        lines += [
            f"- Rows by desk: {', '.join(f'{k}: {v}' for k,v in sorted(by_desk.items())) or 'none'}.",
            f"- Publisher/source slugs: {', '.join(f'{k}: {v}' for k,v in sorted(by_source.items())) or 'none'}.",
            "- A high count does not establish subject suitability; inspect actual originals, source duplication, episodic spread and the explicit registry coverage limits.",
            "",
            "| Record | Desk / publisher | Published | Original title (truncated) | Publisher URL |",
            "|---|---|---|---|---|",
        ]
        # Spread over publication months; within each month take latest record,
        # then fill remaining slots with distinct publication weeks (metadata only).
        chosen, used_months, used_weeks = [], set(), set()
        for r in sorted(title_matches or matches, key=lambda item: ((item["published_date"] or ""), item["id"]), reverse=True):
            month = (r["published_date"] or "")[:7]
            if month not in used_months:
                chosen.append(r); used_months.add(month)
            if len(chosen) >= max_examples:
                break
        for r in sorted(title_matches or matches, key=lambda item: ((item["published_date"] or ""), item["id"]), reverse=True):
            week = (r["published_date"] or "")[:8] + str((int((r["published_date"] or "0000-00-01")[8:10])-1)//7)
            if r in chosen or week in used_weeks:
                continue
            chosen.append(r); used_weeks.add(week)
            if len(chosen) >= max_examples:
                break
        for r in chosen:
            title = clean(r["title_original"] or r["title_english"])
            url = r["url"] or "MISSING"
            url = url.replace("|", "%7C").replace("\n", "")
            lines.append(f"| {r['id']} | {r['desk_id']} / {r['source_slug']} | {r['published_date']} | {title} | {url} |")
        if not chosen:
            lines.append("| — | No preserved live-desk title/category candidates | — | — | — |")
        lines.append("")
    lines += [
        "## Human qualification gates (not passed by this automated audit)",
        "",
        "1. Open each original preserved record and inspect its full original-language body; corroborate title, publisher, captured URL, publication date and source manifest/rights eligibility.",
        "2. Cluster candidate IDs by *distinct actual events* and documentary lineage, not by publication week, duplicate headlines, and retellings of one announcement.",
        "3. Assess at least two substantive thematic questions beyond a single chronology; document disagreements, source concentration, reporting and collection gaps.",
        "4. Check at least one independent issuer where available, without claiming a second agency's release proves the first agency's account.",
        "5. Present a bounded source-to-claim matrix, no automatic scope approval. If sources cannot support a maintained subject reference, recommend no-go.",
        "",
        f"**Next review gate:** {ISSUE_BASE}. This is discovery evidence only, not an approved dossier, timeline or Brief.",
    ]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=ROOT / "pla_watch.db")
    ap.add_argument("--max-examples", type=int, default=10)
    args = ap.parse_args()
    if not 1 <= args.max_examples <= 15:
        ap.error("--max-examples must be 1..15")
    sys.stdout.write(audit(args.db, args.max_examples))


if __name__ == "__main__":
    main()
