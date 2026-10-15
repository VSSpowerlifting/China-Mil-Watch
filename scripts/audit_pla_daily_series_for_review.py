#!/usr/bin/env python3
"""Offline source-series triage for PLA Daily. Repetition is NOT rejection.

Only the historical compact index is read. This computes reproducible monthly
counts and common headline families for editorial scheduling, never decisions,
news veracity, rights judgments, suppression or source-content replacement.
"""
import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "output" / "corpus-index.json"

def family(title):
    # Chinese newsroom prefix delimiter variants, not a semantic classifier.
    # The long dash is included only where it clearly separates a column.
    pieces = re.split(r"\s*(?:[丨｜|：:]|——)\s*", title, maxsplit=1)
    label = pieces[0].strip()
    if not (2 <= len(label) <= 29):
        return None
    return label

def audit(index, min_frequency=10):
    if type(min_frequency) is not int or min_frequency < 2:
        raise ValueError("invalid frequency threshold")
    if index.get("fields") != ["id","date","source","state","title_en","title_orig"]:
        raise ValueError("source index changed")
    sources = index["sources"]
    seen, rows, months = set(), [], Counter()
    series = {}
    for rec in index["records"]:
        if not isinstance(rec, list) or len(rec) != 6:
            raise ValueError("invalid historical row")
        ident, day, src, state, en, orig = rec
        if type(ident) is not int or ident in seen:
            raise ValueError("duplicate source ID")
        seen.add(ident)
        if (type(src) is not int or not 0 <= src < len(sources)
                or type(state) is not int or not 0 <= state < len(index["states"])):
            raise ValueError("source lookup or state changed")
        if sources[src]["code"] != "pla_daily":
            continue
        if not isinstance(orig, str) or not isinstance(en, str):
            raise ValueError("source title missing")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            raise ValueError("invalid source-stated date")
        months[day[:7]] += 1
        title = orig or en
        rows.append({"id":ident,"date":day,"title":title,"state":index["states"][state]["code"]})
        label=family(title)
        if label is None:
            continue
        series.setdefault(label,[]).append({"id":ident,"date":day,"title":title})
    snapshot=index.get("snapshot")
    if not isinstance(snapshot,dict) or snapshot.get("records") != len(seen):
        raise ValueError("historical full-corpus snapshot drift")
    if not isinstance(index.get("trail_ids"),list) or not set(index["trail_ids"]).issubset(seen):
        raise ValueError("protected published source trails missing")
    top=[]
    for label,items in series.items():
        if len(items) < min_frequency:
            continue
        newest=sorted(items,key=lambda x:(x["date"],x["id"]),reverse=True)
        top.append({"family":label,"count":len(items),
                    "sample_record_ids":[x["id"] for x in newest[:6]],
                    "months":dict(sorted(Counter(x["date"][:7] for x in items).items()))})
    top.sort(key=lambda x:(-x["count"],x["family"]))
    return {
        "purpose":"headline_prefix_frequency_only_not_approved_exclusion",
        "publication_enabled":False,"editorial_rejection_decisions":0,
        "snapshot":snapshot,"pla_daily_preserved":len(rows),
        "pla_daily_months":dict(sorted(months.items())),
        "min_frequency":min_frequency,"repeated_families":top,
        "high_caution_prefixes":["外交部","国防部","国台办"],
        "warning":"Headline series are reporting-format clusters, not verdicts on event uniqueness, significance or source truth. MFA/MND prefixes can contain important primary declarations.",
    }

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index",type=Path,default=INDEX)
    ap.add_argument("--min-frequency",type=int,default=10)
    ap.add_argument("--report",type=Path,help="NEW optional private file outside repo")
    args=ap.parse_args(argv)
    if args.report:
        path=args.report.expanduser();real=path.resolve();root=ROOT.resolve()
        if not path.is_absolute() or path.exists() or path.is_symlink() or real==root or root in real.parents:
            ap.error("report needs a new absolute private file outside repo")
    out=audit(json.loads(args.index.read_text(encoding="utf-8")),args.min_frequency)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in out.items() if k!="repeated_families"}|
                     {"top_families":out["repeated_families"][:20]},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
