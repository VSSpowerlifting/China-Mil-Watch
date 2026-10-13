"""Opt-in editorial publisher links, never corpus records or desk coverage.

Presentation validation permits a private, visibly unapproved review. Release
additionally requires exact-version human source/rights review and an explicit
owner policy ruling. This module cannot establish that those humans acted.
"""
import hashlib
import json
import re
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlsplit

TYPE = "source-linked-editorial-v1"
SOURCE_FIELDS = {"id", "url", "publisher", "issuer", "date", "lang",
                 "original_title", "independence", "temporal_role", "verification"}
CHECKS = {"original_language", "claim_support", "chronology", "limited_source_use",
          "authorship", "manuscript_fidelity", "rendered_review"}


def is_source_linked(value):
    return value.get("evidence_type") == TYPE


def safe_publisher_url(value):
    if not isinstance(value, str) or not value or len(value) > 1800:
        return False
    if re.search(r"[\s\\\x00-\x1f\x7f<>\"']", value):
        return False
    try:
        p = urlsplit(value)
        return (p.scheme == "https" and bool(p.hostname) and p.port is None
                and not p.username and not p.password and not p.fragment
                and re.fullmatch(r"[a-zA-Z0-9.-]+", p.hostname) is not None
                and "." in p.hostname and bool(p.path))
    except ValueError:
        return False


def fingerprint(value):
    """Bind review to all editorial, citation, credit and chronology fields."""
    payload = {k: v for k, v in value.items() if k not in {
        "editorial_status", "issue_number", "approval", "editorial_review", "policy_ruling"}}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def manuscript_html_errors(value, html):
    """Compare ordered rendered paragraphs and linked phrases to frozen runs."""
    class Reader(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.paragraphs, self.links = [], []
            self.current, self.link = None, None
            self.article_depth, self.ordinals = 0, []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "section":
                if self.article_depth:
                    self.article_depth += 1
                elif attrs.get("id") == "s-article":
                    self.article_depth = 1
            if tag == "p" and self.article_depth:
                self.current = []
                self.paragraphs.append(self.current)
                self.links.append([])
                self.ordinals.append(attrs.get("data-manuscript-paragraph"))
            if tag == "a" and self.current is not None:
                self.link = [attrs.get("href"), []]
                self.links[-1].append(self.link)

        def handle_data(self, data):
            if self.current is not None:
                self.current.append(data)
                if self.link is not None:
                    self.link[1].append(data)

        def handle_endtag(self, tag):
            if tag == "a":
                self.link = None
            if tag == "p":
                self.current = None
            if tag == "section" and self.article_depth:
                self.article_depth -= 1

    reader = Reader()
    reader.feed(html)
    norm = lambda text: " ".join(text.split())
    expected = [norm("".join(run["text"] for run in p)) for p in value["body_paragraphs"]]
    actual = [norm("".join(p)) for p in reader.paragraphs]
    problems = [] if actual == expected else ["rendered manuscript paragraphs differ in text, count or order"]
    if reader.ordinals != [str(i + 1) for i in range(len(expected))]:
        problems.append("rendered manuscript paragraph markers differ in count or order")
    urls = {s["id"]: s["url"] for s in value["publisher_references"]}
    expected_links = [[(urls[r["source"]], norm(r["text"])) for r in p if "source" in r]
                      for p in value["body_paragraphs"]]
    actual_links = [[(url, norm("".join(text))) for url, text in links] for links in reader.links]
    if actual_links != expected_links:
        problems.append("rendered inline URLs or their manuscript associations differ")
    return problems


def _day(value):
    try:
        d = date.fromisoformat(value)
        return d if d.isoformat() == value else None
    except (ValueError, TypeError):
        return None


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and "\x00" not in value


def _attestation(value):
    return (isinstance(value, dict) and _text(value.get("reviewed_by"))
            and _day(value.get("reviewed_on")) is not None
            and _text(value.get("reference")))


def validate_source_linked(value, *, release=False):
    problems = []
    for field, empty in (("desks", []), ("source_trail", []), ("coverage_by_desk", {})):
        if value.get(field) != empty:
            problems.append("source-linked article requires empty " + field)
    for field in ("external_evidence", "single_desk_exception", "cross_desk_claims",
                  "development", "opening_note", "what_stood_out", "why_it_matters",
                  "what_was_routine", "what_im_watching_next", "cover_source_url",
                  "photo", "synthetic"):
        if value.get(field):
            problems.append("source-linked article cannot carry " + field)
    for field in ("title", "dek", "author_name"):
        if not _text(value.get(field)) or len(value[field]) > (120 if field == "author_name" else 1400):
            problems.append("source-linked article requires " + field)
    start, end = _day(value.get("week_start")), _day(value.get("week_ending"))
    if not start or not end or (end - start).days != 6 or end.weekday() != 5:
        problems.append("source-linked reporting window must be Sunday through Saturday")
    if not re.fullmatch(r"[a-f0-9]{64}", str(value.get("manuscript_sha256", ""))):
        problems.append("source-linked article requires manuscript SHA-256")
    sources = value.get("publisher_references")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 20:
        return problems + ["publisher_references must contain 1–20 sources"]
    ids, urls = set(), set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
            problems.append("publisher reference has invalid fields; no corpus identifiers allowed")
            continue
        ident = source["id"]
        if not isinstance(ident, str) or not re.fullmatch(r"s[1-9][0-9]*", ident) or ident in ids:
            problems.append("publisher reference identity is invalid or duplicated")
        else:
            ids.add(ident)
        if not safe_publisher_url(source["url"]) or source["url"] in urls:
            problems.append("publisher URL must be unique safe HTTPS")
        else:
            urls.add(source["url"])
        for field in ("publisher", "issuer", "lang"):
            if not _text(source[field]):
                problems.append("publisher reference lacks " + field)
        if not isinstance(source["lang"], str) or not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{1,8})*", source["lang"]):
            problems.append("publisher reference requires a source language tag")
        if source["independence"] not in ("official", "independent"):
            problems.append("reference must distinguish official and independent reporting")
        d = _day(source["date"])
        role = source["temporal_role"]
        if (not d or not start or not end or role not in ("in-window", "background")
                or (role == "in-window" and not start <= d <= end)
                or (role == "background" and not d < start)):
            problems.append("publisher reference has incorrect chronology")
        verification = source["verification"]
        if (not isinstance(verification, dict) or set(verification) != {"method", "locator"}
                or verification["method"] not in ("publisher", "indexed-original", "syndicated", "unresolved")
                or not _text(verification["locator"])):
            problems.append("publisher reference requires an honest verification method and locator")
        if release and (not _text(source["original_title"])
                        or not isinstance(verification, dict)
                        or verification.get("method") == "unresolved"):
            problems.append("release requires verified original reference metadata: " + str(ident))
    body = value.get("body_paragraphs")
    used = set()
    if not isinstance(body, list) or not body:
        problems.append("source-linked article requires ordered body_paragraphs")
    else:
        for paragraph in body:
            if not isinstance(paragraph, list) or not paragraph:
                problems.append("empty or malformed manuscript paragraph")
                continue
            for run in paragraph:
                if (not isinstance(run, dict) or not set(run) <= {"text", "source"}
                        or not _text(run.get("text"))):
                    problems.append("manuscript run must contain plain text and optional source")
                    continue
                if "source" in run:
                    if not isinstance(run["source"], str) or run["source"] not in ids:
                        problems.append("inline citation has no publisher reference")
                    else:
                        used.add(run["source"])
        if used != ids:
            problems.append("every publisher reference must be cited in manuscript prose")
    support = value.get("paragraph_support")
    if not isinstance(support, list) or not isinstance(body, list) or len(support) != len(body):
        problems.append("paragraph_support must map every manuscript paragraph in order")
    else:
        for entry in support:
            if (not isinstance(entry, dict) or set(entry) != {"kind", "sources"}
                    or entry["kind"] not in ("reporting", "analysis", "follow-up")
                    or not isinstance(entry["sources"], list) or not entry["sources"]
                    or any(not isinstance(s, str) or s not in ids for s in entry["sources"])):
                problems.append("paragraph support needs explicit evidence and analytical distinction")
    if release:
        review = value.get("editorial_review")
        if (not _attestation(review) or review.get("fingerprint") != fingerprint(value)
                or not isinstance(review.get("checks"), dict)
                or set(review["checks"]) != CHECKS
                or any(v is not True for v in review["checks"].values())):
            problems.append("release requires exact-version human editorial/source/rights review")
        ruling = value.get("policy_ruling")
        if not _attestation(ruling) or ruling.get("fingerprint") != fingerprint(value):
            problems.append("release requires explicit owner source-linked evidence policy ruling")
        approval = value.get("approval")
        approved_on = _day(approval.get("approved_on")) if isinstance(approval, dict) else None
        for attestation in (review, ruling):
            if _attestation(attestation):
                reviewed = _day(attestation["reviewed_on"])
                if (end and reviewed < end) or (approved_on and reviewed > approved_on):
                    problems.append("human review/ruling dates conflict with reporting or approval")
    return problems
