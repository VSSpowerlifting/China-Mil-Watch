"""Bounded, source-linked *private drafting* evidence from non-production desks.

These short editorial notes are NOT archived article bodies, production records,
approved citations or a declaration that any country desk is live. The weekly
writer may consider them while drafting one article for a human editor. It must
use typed external IDs; production numeric IDs never stand in for shadow data.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = ROOT / "research" / "briefs_editorial_evidence"
SCHEMA = "ipr-private-drafting-evidence/1"
STATUS = "unapproved-source-linked-editorial-candidate"
COPY_SCOPE = "private-model-drafting-only-no-source-body"
MAX_ITEMS = 8
TAGS = frozenset((
    "hadr", "defense_exercises", "alliance_diplomacy", "maritime_security",
    "technology_cooperation", "security_industry", "regional_partnerships",
))
FIELDS = {
    "id", "desk", "source_name", "source_url", "published_date", "language",
    "title_original", "source_kind", "state_commit", "source_content_sha256",
    "hash_rule", "summary", "caveats", "topics", "status", "copy_scope",
}
KINDS = {"shadow-extracted-original", "official-publisher-page-reviewed-for-research"}
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
JAPAN_ID = re.compile(r"JP-W[0-9]{2}-[0-9]{2}\Z")
VIETNAM_ID = re.compile(r"VN-MPS-([1-9][0-9]{6,20})\Z")
# Typed editorial identities are never integer production IDs.
# The new families encode the reporting Saturday's ISO week.
AFP_ID = re.compile(r"PH-AFP-W(0[1-9]|[1-4][0-9]|5[0-3])-[0-9]{2}\Z")
KEMHAN_ID = re.compile(r"ID-KEMHAN-W(0[1-9]|[1-4][0-9]|5[0-3])-[0-9]{2}\Z")
# One reviewed research provenance identity, not an open-ended Indonesia feed.
INDONESIA_W42_ID = "ID-W42-01"
INDONESIA_W42_URL = (
    "https://www.kemhan.go.id/2026/10/12/"
    "menhan-dampingi-presiden-dalam-pertemuan-bilateral-dengan-presiden-republik-arab-mesir.html"
)
INDONESIA_W42_COMMIT = "43d9bc7bc94dcb0e257866e0f24e1ce404e98149"
INDONESIA_W42_TEXT_SHA256 = "3475c65c11e5ea7fbee196a435865e9b9ecfb422d2ef88658a1af9efe303393e"



class EditorialEvidenceError(ValueError):
    """Refuse stale, unsourced, malformed or falsely authorized research notes."""


def _require(ok, message):
    if not ok:
        raise EditorialEvidenceError(message)


def _pairs(pairs):
    result = {}
    for name, value in pairs:
        _require(name not in result, "duplicate JSON key: " + name)
        result[name] = value
    return result


def _day(value):
    _require(isinstance(value, str), "invalid date type")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise EditorialEvidenceError("invalid calendar date") from exc
    _require(d.isoformat() == value, "date must be YYYY-MM-DD")
    return d


def _line(value, *, min_length=1, max_length=700):
    return (isinstance(value, str) and
            min_length <= len(value.strip()) <= max_length and
            value == value.strip() and
            not any(ord(ch) < 32 or ord(ch) == 127 for ch in value) and
            "===" not in value and
            not re.search(r"\[External |\[Record ", value))


def _official(item):
    """Constrain editorial links to source families, not any government host.

    This is a format/identity gate, not fact verification or reuse approval.
    Source-specific human checks remain required before model use/publication.
    """
    ident = item["id"]
    _require(isinstance(ident, str), "external ID must be a string")
    desk = item["desk"]
    url = item["source_url"]
    _require(_line(url, min_length=35, max_length=1800), "invalid source URL")
    try:
        p = urlsplit(url)
        no_port = p.port is None
    except ValueError as exc:
        raise EditorialEvidenceError("invalid source URL") from exc
    _require(p.scheme == "https" and no_port and not p.username and
             not p.password and not p.query and not p.fragment,
             "official source URL must be HTTPS and unmodified")

    if desk == "japan":
        _require(bool(JAPAN_ID.fullmatch(ident)),
                 "bad Japan typed source identity")
        mod = (item["source_name"] == "Japan Ministry of Defense"
               and p.hostname == "www.mod.go.jp" and
               (p.path.startswith("/en/article/") and p.path.endswith(".html")
                or p.path.startswith("/j/press/news/") and
                p.path.endswith((".html", ".pdf"))))
        jcg = (item["source_name"] == "Japan Coast Guard"
               and p.hostname == "www.kaiho.mlit.go.jp"
               and bool(re.fullmatch(r"/e/topics_archive/article[0-9]+\.html",
                                     p.path)))
        _require(mod or jcg, "unrecognized Japan MOD/JCG publisher/source family")
        _require(item["language"] in ("ja", "en"), "invalid Japan source language")
    elif desk == "vietnam":
        match = VIETNAM_ID.fullmatch(ident)
        _require(bool(match), "bad Vietnam typed source identity")
        _require(item["source_name"] == "Vietnam Ministry of Public Security"
                 and p.hostname == "bocongan.gov.vn"
                 and p.path.startswith("/bai-viet/")
                 and p.path.endswith("-" + match.group(1))
                 and item["language"] == "vi",
                 "unrecognized Vietnam MPS publisher/source family")
    elif desk == "philippines":
        _require(bool(AFP_ID.fullmatch(ident)), "bad Philippines source identity")
        _require(item["source_name"] == "Armed Forces of the Philippines"
                 and p.hostname == "www.afp.mil.ph"
                 and bool(re.fullmatch(
                     r"/news/[a-z0-9]+(?:-[a-z0-9]+)*", p.path))
                 and item["language"] == "en",
                 "unrecognized Philippines AFP publisher/source family")
    elif desk == "indonesia":
        if ident == INDONESIA_W42_ID:
            # Preserve exact-source evidence already reviewed for Week 42.
            _require(item["source_name"] == "Indonesia Ministry of Defense"
                     and item["source_url"] == INDONESIA_W42_URL
                     and p.hostname == "www.kemhan.go.id"
                     and item["language"] == "id"
                     and item["published_date"] == "2026-10-12"
                     and item["source_kind"] == "shadow-extracted-original"
                     and item["state_commit"] == INDONESIA_W42_COMMIT
                     and item["source_content_sha256"] == INDONESIA_W42_TEXT_SHA256
                     and item["hash_rule"] == "sha256-text-original-utf8",
                     "unrecognized Indonesia Week 42 original/version")
        else:
            _require(bool(KEMHAN_ID.fullmatch(ident)), "bad Indonesia source identity")
            _require(item["source_name"] == "Indonesia Ministry of Defense"
                     and p.hostname == "www.kemhan.go.id"
                     and bool(re.fullmatch(
                         r"/20[0-9]{2}/(?:0[1-9]|1[0-2])/"
                         r"(?:0[1-9]|[12][0-9]|3[01])/"
                         r"[a-z0-9]+(?:-[a-z0-9]+)*\.html", p.path))
                     and item["language"] == "id",
                     "unrecognized Indonesia Kemhan publisher/source family")
    else:
        raise EditorialEvidenceError("research desk/source family is not supported")

def _item(item, start, cutoff):
    _require(isinstance(item, dict) and set(item) == FIELDS,
             "editorial item has missing or extra fields")
    _official(item)
    _require(item["status"] == STATUS and item["copy_scope"] == COPY_SCOPE,
             "unreviewed source is not approved for publication or copying")
    date_published = _day(item["published_date"])
    _require(start <= date_published <= cutoff,
             "research evidence published outside the reporting cutoff")
    if (item["desk"] == "philippines" or
            (item["desk"] == "indonesia" and item["id"] != INDONESIA_W42_ID)):
        matched = (AFP_ID if item["desk"] == "philippines" else KEMHAN_ID).fullmatch(
            item["id"])
        _require(int(matched.group(1)) == cutoff.isocalendar()[1],
                 "research ID must match the reporting ISO week")
    if item["desk"] == "indonesia":
        _require(urlsplit(item["source_url"]).path.startswith(
            date_published.strftime("/%Y/%m/%d/")),
            "Indonesia publisher URL date does not match claimed publication date")
    _require(_line(item["title_original"], min_length=10, max_length=350),
             "missing original-language headline")
    _require(isinstance(item["source_kind"], str) and
             item["source_kind"] in KINDS, "unknown provenance class")
    commit, digest = item["state_commit"], item["source_content_sha256"]
    if item["source_kind"] == "shadow-extracted-original":
        # New publisher families use independently checked publisher links
        # until an exact collector-specific extraction hash rule is reviewed.
        _require((item["desk"] in ("japan", "vietnam") and
                  item["source_name"] != "Japan Coast Guard") or
                 (item["desk"] == "indonesia" and item["id"] == INDONESIA_W42_ID),
                 "new publisher source needs separately qualified shadow hash rule")
        expected_rule = ("mps-vi-content-v1" if item["desk"] == "vietnam"
                         else "sha256-text-original-utf8")
        _require(isinstance(commit, str) and HEX40.fullmatch(commit)
                 and isinstance(digest, str) and HEX64.fullmatch(digest)
                 and item["hash_rule"] == expected_rule,
                 "shadow source must pin Git commit, exact version digest and hash rule")
    else:
        _require(commit is None and digest is None and item["hash_rule"] is None,
                 "public webpage is not a verified shadow capture")
    _require(_line(item["summary"], min_length=65, max_length=700),
             "short attributed editorial synopsis required; not a full article")
    caveats = item["caveats"]
    _require(isinstance(caveats, list) and 1 <= len(caveats) <= 4 and
             all(_line(t, min_length=15, max_length=270) for t in caveats),
             "missing bounded source-accuracy cautions")
    tags = item["topics"]
    _require(isinstance(tags, list) and 1 <= len(tags) <= 3
             and all(isinstance(t, str) for t in tags)
             and len(set(tags)) == len(tags) and set(tags) <= TAGS,
             "invalid topical labels")
    return dict(item)


def load_editorial_evidence(week_ending, as_of, *, directory=PACK_DIR):
    """Validated private-prompt notes for the exact week, or empty if absent.

    Handles Friday previews and Sunday full-week drafting. It is fail-closed:
    malformed packets block the model rather than silently skip verification.
    """
    saturday = _day(week_ending)
    cutoff = _day(as_of)
    _require(saturday.weekday() == 5 and
             cutoff in (saturday, saturday - timedelta(days=1)),
             "editorial evidence cutoff must be reporting Friday or Saturday")
    start = saturday - timedelta(days=6)
    path = Path(directory) / (week_ending + ".json")
    _require(not path.is_symlink(), "symlinked editorial source packet refused")
    if not path.exists():
        return []
    _require(path.is_file() and path.stat().st_size <= 40000,
             "missing, non-regular or oversized source packet")
    try:
        data = json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=_pairs,
                          parse_constant=lambda x: (_ for _ in ()).throw(
                              EditorialEvidenceError("non-finite JSON value")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise EditorialEvidenceError("invalid editorial evidence JSON") from exc
    _require(isinstance(data, dict) and set(data) == {
        "schema", "week_ending", "status", "items"}, "unknown evidence packet fields")
    _require(data["schema"] == SCHEMA and data["status"] == STATUS
             and data["week_ending"] == week_ending, "incorrect week/schema/status")
    items = data["items"]
    _require(isinstance(items, list) and len(items) <= MAX_ITEMS,
             "editorial evidence must have at most eight sources")
    checked = [_item(x, start, cutoff) for x in items]
    ids = [x["id"] for x in checked]
    urls = [x["source_url"] for x in checked]
    _require(len(set(ids)) == len(ids) and len(set(urls)) == len(urls),
             "duplicate source identity or URL")
    # Never let a model invent a production ID: these IDs stay letter-prefixed.
    return sorted(checked, key=lambda x: (x["published_date"], x["id"]), reverse=True)


def evidence_prompt(items):
    """Bounded first-party pointers and cautious ANALYST paraphrases, never bodies."""
    lines = []
    for row in items:
        lines.extend((
            '<external_source id="{}" desk="{}">'.format(row["id"], row["desk"]),
            "Official publisher: " + row["source_name"],
            "Publisher URL: " + row["source_url"],
            "Published: " + row["published_date"],
            "Original language: " + row["language"],
            "Original headline: " + row["title_original"],
            "Topics (clustering suggestions, NOT proof of a shared event): " +
                ", ".join(row["topics"]),
            "Research provenance: " + row["source_kind"],
            "Short, unapproved, source-attributed research synopsis: " + row["summary"],
            "Accuracy cautions: " + " | ".join(row["caveats"]),
            "WARNING: source requires human review before public Brief approval.",
            "</external_source>",
        ))
    return "\n".join(lines)
