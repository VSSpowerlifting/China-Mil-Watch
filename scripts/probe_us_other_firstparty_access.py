"""Policy-first bounded US government first-party source discovery.

One robots.txt and at most one permitted HTML listing per hardcoded host.
This is a read-only research canary: NO collection days, preservation,
state writes, publication, source-body requests or permissions claims.
"""
from __future__ import annotations

import json
import urllib.request
from scripts.probe_us_navy_first_party_access import (
    AGENT, AccessHold, NoRedirect, probe_one,
)

SCHEMA = "ipr-us-other-firstparty-discovery/1"
SOURCES = (
    ("us_navy_news", "www.navy.mil", "/Press-Office/News-Stories/"),
    ("department_of_defense", "www.defense.gov", "/News/Releases/"),
    ("us_treasury", "home.treasury.gov", "/news/press-releases"),
    ("department_of_state", "www.state.gov", "/press-releases/"),
    ("gao", "www.gao.gov", "/press-releases"),
    ("bis", "www.bis.gov", "/press-release"),
    ("dhs", "www.dhs.gov", "/news-releases"),
)

def check_targets(sources=SOURCES):
    if tuple(sources) != SOURCES or len({h for _, h, _ in sources}) != len(SOURCES):
        raise AccessHold("discovery_source_targets_modified")
    for name, host, path in sources:
        if not name or not host.endswith(".gov") and not host.endswith(".mil"):
            raise AccessHold("not_federal_first_party")
        if not path.startswith("/") or "?" in path or ".." in path:
            raise AccessHold("unsafe_path")
    return sources

def run(opener=None):
    check_targets()
    opener = opener or urllib.request.build_opener(NoRedirect)
    rows = [probe_one(*spec, opener) for spec in SOURCES]
    return {
        "schema":SCHEMA,
        "scope":"one_policy-first_html_listing_per_fixed_federal_host",
        "user_agent":AGENT,
        "results":rows,
        "records_collected":0, "publisher_content_copied":False,
        "production_records_written":0, "website_changed":False,
        "collection_authorized":False, "qualified_collection_days":0,
    }

if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
