"""Offline, source-free check of one frozen U.S. Pacific Command link docket.

No URL fetching, DVIDS/pacom.mil access, production DB, original-body
preservation, site rendering, source-use grant, or public publication.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCKET = ROOT / "research/us_pacom_official_link_review_2026-10-15.json"
SCHEMA = "ipr-us-pacom-official-link-research-snapshot/1"
CHECKED = "ipr-us-pacom-index-only-docket-check/1"
PREFIX = "https://www.pacom.mil"
PINS = (
    ("4519249", "2026-06-16", "press_release", "institutional_designation",
     "/Media/Press-Releases-and-Readouts/Press-Releases-and-Readout-view/Article/4519249/department-of-war-restores-us-pacific-command-designation/"),
    ("4522099", "2026-06-25", "press_release", "philippines_defense_coordination",
     "/Media/Press-Releases-and-Readouts/Article/4522099/us-and-philippines-deepen-defense-cooperation-at-execom-summit/"),
    ("4566845", "2026-08-08", "press_release", "philippines_mutual_defense",
     "/Media/Press-Releases-and-Readouts/Press-Releases-and-Readout-view/Article/4566845/philippines-us-mark-75th-anniversary-of-the-mutual-defense-treaty-reaffirm-alli/"),
    ("4586166", "2026-08-30", "press_release", "philippines_mutual_defense",
     "/Media/Press-Releases-and-Readouts/Press-Releases-and-Readout-view/Article/4586166/mutual-defense-treaty-75th-anniversary/"),
    ("4589860", "2026-09-02", "news_article", "chiefs_of_defense_conference",
     "/Media/News/News-Articles/Article/4589860/28th-indo-pacific-chiefs-of-defense-conference-focuses-on-strengthening-regiona/"),
    ("4591082", "2026-09-03", "news_article", "chiefs_of_defense_meetings",
     "/Media/News/News-Articles/Article/4591082/readout-of-adm-samuel-j-paparos-meetings-on-the-sidelines-of-the-indo-pacific-c/"),
    ("4591776", "2026-09-07", "news_article", "trilateral_exercise",
     "/Media/News/News-Articles/Article/4591776/freedom-edge-2026-opening-ceremony-marks-start-of-trilateral-exercise/"),
    ("4596632", "2026-09-11", "press_release", "trilateral_exercise",
     "/Media/Press-Releases-and-Readouts/Press-Releases-and-Readout-view/Article/4596632/freedom-edge-26-concludes-advancing-trilateral-readiness-across-the-indo-pacific/"),
    ("4599539", "2026-09-11", "news_article", "dprk_missile_statement",
     "/Media/News/News-Articles/Article/4599539/us-pacific-command-statement-on-dprk-missile-launch/"),
)
FIELDS = frozenset((
    "source_identity", "official_url", "publisher_posted_date", "hosted_section",
    "reference_topic", "verification_basis",
))
HEADERS = frozenset((
    "schema", "prepared_on", "desk", "source_institution", "source_host",
    "research_state", "collector_state", "source_access_note",
    "dvids_independent_source", "published_to_ipr",
    "source_original_downloaded_for_this_snapshot", "original_body_or_media_stored",
    "automatic_discovery_or_publication_approved", "count", "records",
))
DATE = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}\Z")


class DocketHold(ValueError):
    """No source or site changes on evidence/policy disagreement."""


def require(ok, reason):
    if not ok:
        raise DocketHold(reason)


def _day(s):
    require(type(s) is str and DATE.fullmatch(s), "invalid_official_date")
    try:
        d = date.fromisoformat(s)
    except ValueError:
        raise DocketHold("invalid_official_date") from None
    require(d.isoformat() == s, "invalid_official_date")
    return d


def validate(data):
    require(type(data) is dict and set(data) == HEADERS,
            "unexpected_us_docket_fields")
    require(data["schema"] == SCHEMA and data["prepared_on"] == "2026-10-15"
            and data["desk"] == "us-indopacific"
            and data["source_institution"] == "us_pacom"
            and data["source_host"] == "www.pacom.mil"
            and data["research_state"] ==
            "indexed_official_pages_only__not_publication"
            and data["collector_state"] == "access_blocked"
            and data["source_access_note"] ==
            "Direct project-runner PACOM robots.txt access remains unresolved; indexed official page records do not authorize crawling."
            and data["dvids_independent_source"] ==
            "DVIDS is a separate paused Tier B media-service feed, not command-issued coverage."
            and data["published_to_ipr"] is False
            and data["source_original_downloaded_for_this_snapshot"] is False
            and data["original_body_or_media_stored"] is False
            and data["automatic_discovery_or_publication_approved"] is False,
            "us_access_scope_or_publication_policy_changed")
    require(type(data["count"]) is int and data["count"] == len(PINS)
            and type(data["records"]) is list
            and len(data["records"]) == len(PINS),
            "us_source_count_changed")
    seen = set()
    for row, pin in zip(data["records"], PINS):
        require(type(row) is dict and set(row) == FIELDS,
                "us_reference_includes_unapproved_fields")
        ident, day, section, topic, official_path = pin
        expected = {
            "source_identity": "us-pacom:" + ident,
            "official_url": PREFIX + official_path,
            "publisher_posted_date": day,
            "hosted_section": section,
            "reference_topic": topic,
            "verification_basis": "official_site_search_index_excerpt_only",
        }
        require(row == expected, "frozen_us_reference_or_source_date_changed")
        require(row["source_identity"] not in seen, "us_reference_duplicate")
        seen.add(row["source_identity"])
        parts = urlsplit(row["official_url"])
        require(parts.scheme == "https" and parts.netloc == "www.pacom.mil"
                and parts.path == official_path and not parts.query
                and not parts.fragment and not parts.username
                and not parts.password and "%" not in parts.path,
                "us_official_url_not_exact")
        require(_day(row["publisher_posted_date"]) <= _day(data["prepared_on"]),
                "us_future_source_date")
    return {
        "schema": CHECKED,
        "result": "PASS_INDEX_ONLY",
        "frozen_first_party_url_leads": len(PINS),
        "source_originals_downloaded": 0,
        "automated_requests_made": 0,
        "production_records_written": 0,
        "site_references_published": 0,
        "full_page_or_robots_retrieval_verified": False,
    }


def main():
    try:
        require(DOCKET.is_file() and not DOCKET.is_symlink(),
                "us_docket_unavailable")
        require(DOCKET.stat().st_size <= 16000, "us_docket_oversize")
        obj = json.loads(DOCKET.read_text(encoding="utf-8"))
        print(json.dumps(validate(obj), sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        code = str(exc) if isinstance(exc, DocketHold) else "us_docket_invalid"
        print(json.dumps({"schema": CHECKED, "result": "HOLD", "reason": code},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
