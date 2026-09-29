#!/usr/bin/env python3
"""
Desk-scoped re-screening: plan it, or propose verdicts for human review.

Nothing here writes to a database. The database is opened read-only
(`mode=ro&immutable=1`), and there is no apply command: changing a stored
verdict is a separate, owner-approved step taken after the proposal file has
been reviewed.

  plan     Offline. Lists the desk's records that a desk-scoped screening
           would touch (never screened, and previously rejected, with the stage
           and the stored reason), and estimates the model cost from the real
           prompt text. Makes no API call.

  propose  Calls the desk-scoped relevance stage ONLY
           (Analyzer.score_relevance with the desk profile) for the listed
           records — never Analyzer.analyze(), so no translation, summary or
           categorisation runs — and writes proposed verdicts next to the
           stored ones in a JSON sidecar for review. Refuses to run without
           --confirm-spend and a named id list.

    .venv/bin/python scripts/rescreen_desk.py plan --desk singapore \\
        --db /path/to/snapshot.db --out plan.json
    .venv/bin/python scripts/rescreen_desk.py propose --desk singapore \\
        --db /path/to/snapshot.db --ids 4421,4422 --confirm-spend --out proposal.json
"""

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from config import RELEVANCE_MODEL, RELEVANCE_THRESHOLD  # noqa: E402
from processing.screening import profile_for_desk  # noqa: E402

KEYWORD_REJECTION = "failed keyword pre-filter"
# English prose tokenizes at roughly 4 characters per token; 3.5 over-counts on
# purpose, as scripts/spend_guard.py does for Chinese.
CHARS_PER_TOKEN_EN = 3.5
# score_relevance() allows 500 output tokens; a one-sentence JSON verdict uses
# far fewer. The ceiling is the bound, the typical figure is the expectation.
OUTPUT_TOKENS_CEILING = 500
OUTPUT_TOKENS_TYPICAL = 80


def open_readonly(db_path) -> sqlite3.Connection:
    uri = "file:%s?mode=ro&immutable=1" % Path(db_path).resolve()
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def desk_records(con, desk_id: str) -> list:
    rows = con.execute(
        """
        SELECT a.id, a.url, a.title_original, a.text_original, a.published_date,
               a.passed_relevance, a.relevance_score, a.relevance_reasoning,
               a.processing_state, s.slug AS source_slug
          FROM articles a JOIN sources s ON s.id = a.source_id
         WHERE s.desk_id = ?
         ORDER BY a.id
        """, (desk_id,)).fetchall()
    return [dict(r) for r in rows]


def stage_of(rec: dict) -> str:
    if rec["passed_relevance"] is None:
        return "unscreened"
    if rec["passed_relevance"]:
        return "passed"
    if (rec["relevance_reasoning"] or "") == KEYWORD_REJECTION:
        return "rejected_keyword"
    return "rejected_model"


def estimate(profile, recs: list, model: str = RELEVANCE_MODEL) -> dict:
    from scripts.spend_guard import _price
    sys_chars = len(profile.system_prompt or "")
    per = []
    for r in recs:
        msgs = profile.build_messages(r["title_original"] or "",
                                      r["text_original"] or "")
        user_chars = sum(len(m["content"]) for m in msgs)
        per.append(user_chars)
    n = len(recs)
    in_tok = (sum(per) + sys_chars * n) / CHARS_PER_TOKEN_EN
    price = _price(model)
    def usd(out_per_call):
        return (in_tok * price["input"] + n * out_per_call * price["output"]) / 1e6
    return {
        "model": model,
        "records": n,
        "chars_per_token_assumed": CHARS_PER_TOKEN_EN,
        "system_prompt_chars": sys_chars,
        "user_message_chars_total": sum(per),
        "input_tokens_estimate": int(in_tok),
        "output_tokens_typical": n * OUTPUT_TOKENS_TYPICAL,
        "output_tokens_ceiling": n * OUTPUT_TOKENS_CEILING,
        "usd_typical": round(usd(OUTPUT_TOKENS_TYPICAL), 4),
        "usd_ceiling": round(usd(OUTPUT_TOKENS_CEILING), 4),
        "price_usd_per_mtok": price,
        "price_source": "scripts/spend_guard.py PRICING_USD_PER_MTOK "
                        "(checked 2026-07-31; re-verify before spending)",
        "note": "No prompt-cache discount assumed: the system prompt is priced "
                "at full input rate on every call.",
    }


def db_fingerprint(db_path) -> str:
    return hashlib.sha256(Path(db_path).read_bytes()).hexdigest()


def build_plan(db_path, desk_id: str) -> dict:
    profile = profile_for_desk(desk_id)
    con = open_readonly(db_path)
    try:
        recs = desk_records(con, desk_id)
    finally:
        con.close()
    groups = {}
    for r in recs:
        groups.setdefault(stage_of(r), []).append(r)
    affected = groups.get("unscreened", []) + groups.get("rejected_keyword", []) \
        + groups.get("rejected_model", [])
    affected.sort(key=lambda r: r["id"])

    def brief(r):
        return {
            "id": r["id"], "url": r["url"], "published_date": r["published_date"],
            "title_original": r["title_original"], "stage": stage_of(r),
            "stored_score": r["relevance_score"],
            "stored_reasoning": r["relevance_reasoning"],
            "processing_state": r["processing_state"],
            "text_chars": len(r["text_original"] or ""),
        }
    return {
        "desk": desk_id,
        "db_sha256": db_fingerprint(db_path),
        "prompt_version": profile.prompt_version,
        "threshold": RELEVANCE_THRESHOLD,
        "counts": {k: len(v) for k, v in sorted(groups.items())},
        "affected_ids": [r["id"] for r in affected],
        "records": [brief(r) for r in affected],
        "estimate": estimate(profile, affected),
    }


def build_proposal(db_path, desk_id: str, ids: list, analyzer) -> dict:
    """Score `ids` with the desk profile. Reads the DB; never writes it."""
    profile = profile_for_desk(desk_id)
    con = open_readonly(db_path)
    try:
        recs = {r["id"]: r for r in desk_records(con, desk_id)}
    finally:
        con.close()
    missing = [i for i in ids if i not in recs]
    if missing:
        raise SystemExit("not %s-desk records in this database: %s"
                         % (desk_id, missing))
    out = []
    for i in ids:
        r = recs[i]
        try:
            score, reasoning = analyzer.score_relevance(
                r["title_original"] or "", r["text_original"] or "",
                profile=profile)
            error = None
        except Exception as exc:  # noqa: BLE001 — recorded, reviewed, not retried
            score, reasoning, error = None, None, "%s: %s" % (type(exc).__name__, exc)
        out.append({
            "id": i, "url": r["url"], "title_original": r["title_original"],
            "stored": {"stage": stage_of(r), "score": r["relevance_score"],
                       "reasoning": r["relevance_reasoning"]},
            "proposed": {"score": score, "reasoning": reasoning,
                         "passes_threshold": (None if score is None
                                              else score >= RELEVANCE_THRESHOLD),
                         "error": error},
            "review": {"decision": None, "reviewer": None, "note": None},
        })
    return {
        "desk": desk_id,
        "db_sha256": db_fingerprint(db_path),
        "model": RELEVANCE_MODEL,
        "prompt_version": profile.prompt_version,
        "threshold": RELEVANCE_THRESHOLD,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "applied": False,
        "records": out,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "propose"):
        p = sub.add_parser(name)
        p.add_argument("--desk", required=True)
        p.add_argument("--db", required=True)
        p.add_argument("--out", required=True)
        if name == "propose":
            p.add_argument("--ids", required=True,
                           help="comma-separated record ids, from a plan")
            p.add_argument("--confirm-spend", action="store_true")
    args = ap.parse_args(argv)

    if profile_for_desk(args.desk).desk_id != args.desk:
        ap.error("no screening profile for desk %r" % args.desk)

    if args.cmd == "plan":
        result = build_plan(args.db, args.desk)
    else:
        if not args.confirm_spend:
            ap.error("propose calls the model; pass --confirm-spend after "
                     "reading the plan's estimate")
        from analysis.analyzer import Analyzer
        ids = [int(x) for x in args.ids.split(",") if x.strip()]
        result = build_proposal(args.db, args.desk, ids, Analyzer())

    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
