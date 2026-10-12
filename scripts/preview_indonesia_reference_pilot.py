"""STRICT PRIVATE preview of the preapproved-zero Indonesia official-link pilot.

No collection, publisher requests, corpus writes, source body, model use,
source licence, human approval, public renderer integration or desk activation.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "research/indonesia/public_reference_pilot_2026-10-11.json"
STATE = "17dfae7e6e1e9e1142d81c89764f022ebf03552f"
TOP_KEYS = {
    "schema", "generated_for", "publisher", "source_family",
    "fixed_state_commit", "source_page_has_ministry_copyright_notice",
    "rights_basis", "intended_display", "public_renderer_consumes_this_file",
    "owner_release_approved", "independent_human_source_review_completed",
    "day7_review_completed", "production_admitted", "candidates",
}
ROW_KEYS = {
    "reference_id", "source_identity", "source_url", "title_original",
    "published_date", "language", "source_family", "archived_at_commit",
    "editorial_caveat_tag", "assistant_semantic_read",
    "independent_human_original_review", "publisher_body_republication_approved",
    "source_specific_rights_approved", "public_reference_approved",
}
CAVEATS = {
    "ID-01": "not_a_2027_conference",
    "ID-02": "farewell_meeting_not_new_agreement",
    "ID-03": "sanggau_833_not_operational_readiness_certificate",
    "ID-04": "bengkayang_926_visit_on_oct8",
}
FALSE_TOP = (
    "public_renderer_consumes_this_file", "owner_release_approved",
    "independent_human_source_review_completed", "day7_review_completed",
    "production_admitted",
)
FALSE_ROW = (
    "independent_human_original_review",
    "publisher_body_republication_approved",
    "source_specific_rights_approved",
    "public_reference_approved",
)


class PilotHold(ValueError):
    pass


def require(cond, why):
    if not cond:
        raise PilotHold(why)


def unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, "duplicate JSON field")
        obj[key] = value
    return obj


def validate(obj):
    require(type(obj) is dict and set(obj) == TOP_KEYS, "unknown pilot fields")
    require(obj["schema"] == "ipr-indonesia-private-link-pilot/1", "unknown schema")
    require(obj["generated_for"] == "2026-10-11", "misdated pilot")
    require(obj["publisher"] == "Kementerian Pertahanan Republik Indonesia", "wrong publisher")
    require(obj["source_family"] == "id_kemhan_news", "wrong source family")
    require(obj["fixed_state_commit"] == STATE, "original Git commit pin changed")
    require(obj["source_page_has_ministry_copyright_notice"] is True,
            "publisher rights observation missing")
    require(obj["rights_basis"] ==
            "no_specific_open_license_observed_proposed_bibliographic_links_only",
            "no verified source licence for this pilot")
    require(obj["intended_display"] == "offline_private_preview_only",
            "public rendering not authorized")
    require(all(obj[k] is False for k in FALSE_TOP), "false approval claim")
    rows = obj["candidates"]
    require(type(rows) is list and len(rows) == 4, "pilot must contain exactly four links")
    require([x.get("reference_id") for x in rows if type(x) is dict] ==
            list(CAVEATS), "unreviewed or reordered reference")
    seen = set()
    for row in rows:
        require(type(row) is dict and set(row) == ROW_KEYS, "unsafe reference fields")
        ref = row["reference_id"]
        require(row["editorial_caveat_tag"] == CAVEATS[ref],
                "editorial nonclaim altered")
        require(row["language"] == "id" and row["source_family"] == "id_kemhan_news" and
                row["archived_at_commit"] == STATE, "wrong original source or language")
        require(row["assistant_semantic_read"] is True,
                "this item was not read in the source-review docket")
        require(all(row[k] is False for k in FALSE_ROW), "false source-use approval")
        title, link, ident, published = (
            row["title_original"], row["source_url"],
            row["source_identity"], row["published_date"])
        require(type(title) is str and bool(title.strip()) and len(title) <= 260 and
                not any(ord(c) < 32 or c in "<>" for c in title),
                "unsafe original bibliographic title")
        require(type(link) is str and len(link) <= 350, "unsafe source link")
        parts = urlsplit(link)
        require(parts.scheme == "https" and parts.netloc == "www.kemhan.go.id" and
                not parts.query and not parts.fragment,
                "noncanonical official-source link")
        m = re.fullmatch(
            r"/([0-9]{4})/([0-9]{2})/([0-9]{2})/[a-z0-9-]+\.html",
            parts.path)
        require(m is not None and type(ident) is str and ident == "kemhan:" + parts.path,
                "canonical Indonesia Berita source identity mismatch")
        try:
            require(date(*map(int, m.groups())).isoformat() == published,
                    "official date disagrees with URL")
        except ValueError:
            raise PilotHold("invalid original date") from None
        require(link not in seen, "duplicate official reference")
        seen.add(link)
    return rows


def load(path=DEFAULT):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "pilot file absent or symlink")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"),
                         object_pairs_hook=unique_pairs)
    except (UnicodeError, OSError, json.JSONDecodeError) as exc:
        raise PilotHold("pilot JSON unreadable") from exc
    validate(obj)
    return obj


def private_preview(obj):
    rows = validate(obj)
    articles = []
    for row in rows:
        link = html.escape(row["source_url"], quote=True)
        title = html.escape(row["title_original"])
        date_label = html.escape(row["published_date"])
        ref = html.escape(row["reference_id"])
        articles.append(
            '<li><small>' + ref + ' · Kemhan Berita · ' + date_label +
            '</small><p><a target="_blank" rel="noopener noreferrer" href="' +
            link + '">' + title + '</a></p></li>')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow,noarchive">'
        '<title>IPR Indonesia — private unapproved link preview</title>'
        '<style>body{font:17px/1.65 Georgia,serif;margin:4rem auto;max-width:760px;'
        'padding:0 1rem;color:#20313a;background:#f4f1e9}'
        'li{padding:1.1rem 0;border-bottom:1px solid #a3afb0}small{font:13px system-ui}'
        'a{color:#166065}</style></head><body>'
        '<p>INDO-PACIFIC RECORD · PRIVATE RESEARCH ONLY</p>'
        '<h1>Indonesia — proposed official-source references</h1>'
        '<p><strong>NOT APPROVED FOR PUBLICATION.</strong> No named independent human '
        'source check, publisher reuse permission, owner launch decision or Day 7 review '
        'is represented. Links and original Indonesian bibliographic titles only; '
        'no article bodies, images, translations or independent event verification.</p>'
        '<ol>' + "".join(articles) + '</ol>'
        '<p>Coverage: one Kemhan Berita publication family, four selected items. '
        'Not the Indonesian armed forces or national defence record. '
        'The fifth reviewed item is held for a publisher geographic inconsistency.</p>'
        '</body></html>'
    )


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=DEFAULT)
    p.add_argument("--preview", type=Path,
                   help="EXCLUSIVE new private HTML outside checkout; no site changes")
    args = p.parse_args(argv)
    try:
        obj = load(args.input)
        if args.preview:
            dest = args.preview.expanduser()
            require(dest.is_absolute() and dest.parent.is_dir() and not dest.exists() and
                    not dest.is_symlink() and
                    ROOT.resolve() not in (dest.resolve(), *dest.resolve().parents),
                    "preview must be new and outside checkout")
            with dest.open("x", encoding="utf-8") as f:
                f.write(private_preview(obj))
        print(json.dumps({
            "source_family": obj["source_family"], "pinned_git": STATE,
            "link_candidates": len(obj["candidates"]),
            "independent_human_review_completed": False,
            "source_specific_rights_approved": False,
            "public_release_authorized": False,
            "day7_review_completed": False,
            "production_changed": False,
        }, sort_keys=True))
    except (PilotHold, OSError) as e:
        p.error(str(e))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
