"""Authoritative nine-link U.S. PACOM publisher index, never a source feed.

Exact official URL/date/category tuples are held in an offline immutable docket.
Loading the list does not perform network access or import publisher originals.
"""
from __future__ import annotations

from scripts.review_us_pacom_official_link_docket import DOCKET, validate
import json

def load_us_pacom_official_links():
    data = json.loads(DOCKET.read_text(encoding="utf-8"))
    verdict = validate(data)
    if verdict["result"] != "PASS_INDEX_ONLY":
        raise ValueError("us_pacom_index_not_verified")
    return [
        {"source_identity": row["source_identity"],
         "source_url": row["official_url"],
         "published_date": row["publisher_posted_date"],
         "section": row["hosted_section"],
         "neutral_label": ("PACOM "+("press/readout" if row["hosted_section"] ==
                                    "press_release" else "official-site news")
                           +" reference "+row["source_identity"].split(":", 1)[1]),
         }
        for row in data["records"]
    ]
