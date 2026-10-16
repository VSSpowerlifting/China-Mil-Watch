"""Independently validate three BIS U.S. Desk surfaces: SQLite, Pages Git, CDN.

The workflow caller fetches the production DB, exact gh-pages Git file and
public HTTP response. No writes, no network requests from this module and no
source-body article count changes. Synthetic inputs cannot prove deployment.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from bs4 import BeautifulSoup
from core.us_bis_authenticated_metadata import load_public_links


class BISReadbackHold(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise BISReadbackHold(reason)


def read_bounded(path, cap=1_000_000):
    path=Path(path)
    require(path.is_file() and not path.is_symlink() and
            0 < path.stat().st_size <= cap,"invalid_page_file")
    return path.read_bytes()


def verified_html(raw, expected):
    try:
        html=raw.decode("utf-8")
    except UnicodeError:
        raise BISReadbackHold("page_not_utf8") from None
    soup=BeautifulSoup(html,"html.parser")
    refs=soup.select("li[data-us-bis-official-link]")
    require(len(refs)==len(expected),"bis_reference_count_wrong")
    for li,row in zip(refs,expected):
        anchor=li.select_one("a[href]")
        timetag=li.select_one("time[datetime]")
        require(anchor is not None and timetag is not None,
                "bis_link_or_date_missing")
        require(li.get("data-us-bis-official-link")==row["source_identity"] and
                anchor["href"]==row["source_url"] and
                anchor.get_text(" ",strip=True)==row["neutral_label"] and
                timetag["datetime"]==row["published_date"] and
                timetag.get_text(" ",strip=True)==row["published_date"],
                "bis_official_reference_disagrees")
        require(anchor.get("target")=="_blank" and
                "noopener" in anchor.get("rel",[]) and
                "noreferrer" in anchor.get("rel",[]),"bis_link_not_safe")
    for selector,count in (
            ("li[data-us-pacom-link] a",9),
            ("li[data-uscc-official-link] a",10),
            ("li[data-us-treasury-official-link] a",10)):
        found=len(soup.select(selector))
        require(found==count if count==9 else found>=count,
                "other_us_reference_missing")
    require("PACOM remains access-blocked" in html and "DVIDS paused" in html,
            "existing_us_source_limitations_missing")
    require(all(x not in html for x in (
        "title_original","text_original","body_original")),
        "original_publisher_text_detected")
    return len(refs)


def verify(db_path, main_page, pages_page, deployed_page):
    rows=load_public_links(db_path)
    require(rows,"no_authenticated_bis_live_metadata")
    main=read_bounded(main_page)
    gitpages=read_bounded(pages_page)
    http=read_bounded(deployed_page)
    require(main==gitpages,"github_pages_differs_from_main_us_desk")
    require(http==gitpages,"public_cdn_does_not_match_gh_pages")
    count=verified_html(main,rows)
    return {
        "status":"PASS_BIS_INDEPENDENT_DEPLOYED_READBACK",
        "records":count,
        "us_desk_sha256":hashlib.sha256(main).hexdigest(),
        "main_matches_pages_git":True,
        "pages_git_matches_public_http":True,
        "original_bis_text_rehosted":False,
        "complete_bis_publisher_history_claimed":False,
    }


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--production-db",required=True)
    parser.add_argument("--main-page",required=True)
    parser.add_argument("--pages-git-file",required=True)
    parser.add_argument("--public-http-file",required=True)
    args=parser.parse_args(argv)
    try:
        report=verify(args.production_db,args.main_page,
                      args.pages_git_file,args.public_http_file)
    except (BISReadbackHold,ValueError,OSError) as exc:
        print(json.dumps({"status":"HOLD_BIS_DEPLOYED_READBACK",
                          "reason":str(exc)},sort_keys=True))
        return 2
    print(json.dumps(report,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
