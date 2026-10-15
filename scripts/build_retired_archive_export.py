"""Rebuild the legacy JSON compatibility export from the *retained* SQLite DB.

Used only on a disposable, freshly rendered site in the China retirement
rehearsal. Carrying output/data/articles.json from the pre-cull website would
silently advertise source pages deleted from the new active corpus.
"""
import argparse
import json
from pathlib import Path
from datetime import date

from scripts.reconcile_db import read_only

ROOT = Path(__file__).resolve().parents[1]


def build(db_path: Path, site_path: Path) -> dict:
    db_path = Path(db_path).resolve(strict=True)
    site_path = Path(site_path).resolve(strict=True)
    if site_path == ROOT or ROOT in site_path.parents or site_path in ROOT.parents:
        raise ValueError("compatibility export requires private outside-repository site")
    if not site_path.is_dir() or not (site_path / "corpus-index.json").is_file():
        raise ValueError("full newly rendered site is required")
    target = site_path / "data" / "articles.json"
    if target.exists():
        raise ValueError("legacy export was carried instead of regenerated")
    corpus = json.loads((site_path / "corpus-index.json").read_text(encoding="utf-8"))
    allowed = {row[0] for row in corpus["records"]}
    records = []
    with read_only(db_path) as conn:
        conn.row_factory = __import__("sqlite3").Row
        rows = conn.execute("""
            SELECT a.id, a.title_english, a.title_original, a.summary_english,
                   a.published_date, a.is_significant, a.significance_reasoning,
                   a.relevance_score, a.url,
                   s.display_name AS source_name, s.slug AS source_slug,
                   GROUP_CONCAT(c.slug) AS category_slugs
              FROM articles a
              JOIN sources s ON s.id=a.source_id
              LEFT JOIN article_categories ac ON ac.article_id=a.id
              LEFT JOIN categories c ON c.id=ac.category_id
             WHERE a.passed_relevance=1 AND a.analyzed_at IS NOT NULL
             GROUP BY a.id
             ORDER BY a.published_date DESC, a.is_significant DESC,
                      a.relevance_score DESC, a.id
        """).fetchall()
        for row in rows:
            aid=row["id"]
            if aid not in allowed:
                raise ValueError("analyzed article absent from reduced corpus index")
            record_path="record/%d.html" % aid
            if not (site_path / record_path).is_file():
                raise ValueError("analyzed article missing rendered record page: "+str(aid))
            pub=row["published_date"] or ""
            if pub:
                try:
                    formatted=date.fromisoformat(pub).strftime("%b %d, %Y")
                except ValueError as exc:
                    raise ValueError("invalid analyzed article publication date") from exc
            else:
                formatted=""
            categories=sorted((row["category_slugs"] or "").split(","))
            categories=[v for v in categories if v]
            records.append({
                "id":aid,
                "title_en":row["title_english"] or "",
                "title_zh":row["title_original"] or "",
                "summary":row["summary_english"] or "",
                "date":pub,
                "date_fmt":formatted,
                "source":row["source_name"] or "",
                "source_slug":row["source_slug"] or "",
                "categories":categories,
                "category_labels":categories,
                "is_significant":bool(row["is_significant"]),
                "significance_reason":row["significance_reasoning"] or "",
                "relevance_score":round(row["relevance_score"] or 0.0, 2),
                "url":row["url"] or "",
                "article_path":record_path,
                "extraction_issue":False,  # no physical extraction_issue column in SQLite
            })
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(records,ensure_ascii=False,separators=(",",":"))+"\n",
                      encoding="utf-8")
    return {"exported":len(records),"active_corpus":len(allowed),
            "no_retired_references":True,"path":str(target)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db",type=Path,required=True)
    p.add_argument("--site",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(build(a.db,a.site),sort_keys=True))


if __name__=="__main__":
    main()
