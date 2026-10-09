"""Constrained, manually triggered Japan MOD HTML metadata observations.

NEVER a full-body archive, official-publisher version attestation, copyright
clearance, original-language signoff, model source-use grant or Sunday release.
Only two exact already-pinned MOD URLs from the Oct 10 research packet.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit

SCHEMA = "ipr-japan-mod-two-html-observation/1"
MAX_BYTES = 1_500_000
TARGETS = {
    "JP-W41-01": (
        "https://www.mod.go.jp/en/article/2026/10/5fc631a5d1b2f36a9b697a611082a85af444ea54.html",
        "2026-10-06",
        "JS Kunisaki Departs Indonesia after Completing International Disaster Relief Activities",
    ),
    "JP-W41-02": (
        "https://www.mod.go.jp/en/article/2026/10/92045078e2a66f0957658c577e65cb0832261b17.html",
        "2026-10-06",
        "Courtesy call on Defense Minister Koizumi by H. E. Mr. George Glass, the U.S. Ambassador to Japan",
    ),
}
DATE_FORMS = ("october 6, 2026", "6 october 2026", "2026/10/06",
              "2026-10-06", "oct. 6, 2026")
ALLOWED_PAGE_STATUS = "NOT_REVIEWED_OBSERVATION_ONLY"


class MODObservationError(ValueError):
    """Invalid site identity, bytes, metadata or claimed source rights."""


def need(value, reason):
    if not value:
        raise MODObservationError(reason)


def compact(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


class VisibleWords(HTMLParser):
    """Text in the received HTML only; never executes or requests resources."""

    SKIP = frozenset({"script", "style", "template", "noscript", "svg"})

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.suppressed = 0
        self.parts = []
        self.in_title = False
        self.title = []
        self.html_seen = False

    def handle_starttag(self, tag, attrs):
        if tag == "html":
            self.html_seen = True
        if tag in self.SKIP:
            self.suppressed += 1
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.suppressed = max(0, self.suppressed - 1)
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.suppressed:
            return
        if self.in_title:
            self.title.append(data)
            return  # A metadata <title> alone does NOT prove body content.
        self.parts.append(data)


def attest_packet_scope(rows):
    """Reject a broadened source set or forged research rights."""
    need(isinstance(rows, list) and len(rows) <= 8,
         "only bounded validated editorial packet accepted")
    japan = {r.get("id"): r for r in rows if isinstance(r, dict)
             and r.get("desk") == "japan"}
    need(set(japan) == {"JP-W41-01", "JP-W41-02", "JP-W41-06"},
         "expected exact Oct10 Japan research roster")
    for ident, (url, day, title) in TARGETS.items():
        r = japan[ident]
        need(r.get("source_url") == url
             and r.get("published_date") == day
             and r.get("title_original") == title
             and r.get("status") == "unapproved-source-linked-editorial-candidate"
             and r.get("copy_scope") == "private-model-drafting-only-no-source-body"
             and r.get("source_kind") == "official-publisher-page-reviewed-for-research"
             and r.get("state_commit") is None
             and r.get("source_content_sha256") is None
             and r.get("hash_rule") is None
             and r.get("language") == "en",
             "official MOD HTML research identity, title, or use scope changed")
    return japan


def observe(ident, payload, *, fetched_url, content_type, observed_utc):
    """A reversible-proof-LIMITED *observation*: hash bytes, discard text."""
    need(ident in TARGETS, "unrecognized official source")
    expected_url, day, title = TARGETS[ident]
    u = urlsplit(fetched_url)
    need(fetched_url == expected_url
         and u.scheme == "https" and u.netloc == "www.mod.go.jp"
         and not u.fragment and not u.query,
         "redirected or untrusted official-publisher URL")
    need(content_type.lower().split(";", 1)[0].strip() == "text/html",
         "official publisher response is not HTML")
    need(type(payload) is bytes and 20 <= len(payload) <= MAX_BYTES,
         "official HTML capture missing or oversized")
    need(isinstance(observed_utc, str) and
         datetime.fromisoformat(observed_utc.replace("Z", "+00:00")).tzinfo is not None,
         "non-timezone-aware observation instant")
    try:
        decoded = payload.decode("utf-8-sig", "strict")
    except UnicodeDecodeError as exc:
        raise MODObservationError("invalid UTF-8 original publisher HTML") from exc
    parser = VisibleWords()
    try:
        parser.feed(decoded)
        parser.close()
    except ValueError as exc:
        raise MODObservationError("malformed MOD source HTML") from exc
    need(parser.html_seen and parser.parts,
         "publisher HTML root or readable content missing")
    words = compact(" ".join(parser.parts))
    title_found = compact(title) in words
    date_found = any(form in words for form in DATE_FORMS)
    # These booleans are provisional content signals, NOT a human factual review.
    reason = ("visible_title_and_date_detected_not_human_source_review"
              if title_found and date_found else
              "expected_title_or_date_not_located_manual_original_check_required")
    return {
        "id": ident,
        "published_date_in_prior_research": day,
        "raw_html_sha256": hashlib.sha256(payload).hexdigest(),
        "decoded_visible_text_sha256": hashlib.sha256(
            words.encode("utf-8")).hexdigest(),
        "raw_html_byte_count": len(payload),
        "observed_utc": observed_utc,
        "expected_title_text_found": bool(title_found),
        "expected_date_text_found": bool(date_found),
        "observation_status": ALLOWED_PAGE_STATUS,
        "reason": reason,
        "historical_html_body_preserved_or_verified": False,
        "current_html_body_in_receipt": False,
        "human_english_japanese_original_comparison_done": False,
        "publisher_reuse_terms_signed_off": False,
        "editorial_model_use_authorized": False,
        "editor_email_authorized": False,
        "publication_authorized": False,
    }


def summarize(rows, payloads, observed_utc=None):
    """At most two official pages, each fetched once on explicit operator action."""
    attest_packet_scope(rows)
    need(isinstance(payloads, dict) and set(payloads) == set(TARGETS),
         "two and only two scoped MOD observations required")
    observed_utc = observed_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    items = []
    for ident in sorted(TARGETS):
        item = payloads[ident]
        need(isinstance(item, dict) and set(item) ==
             {"payload", "fetched_url", "content_type"},
             "invalid per-source HTTP observation response")
        items.append(observe(ident, item["payload"],
                             fetched_url=item["fetched_url"],
                             content_type=item["content_type"],
                             observed_utc=observed_utc))
    return {
        "schema": SCHEMA,
        "week_ending": "2026-10-10",
        "observation_count": 2,
        "items": items,
        "expected_visible_title_and_date_count": sum(
            bool(x["expected_title_text_found"] and x["expected_date_text_found"])
            for x in items),
        "original_html_bodies_retained": False,
        "historical_to_live_body_equality_proven": False,
        "live_source_signoff_completed": False,
        "model_called": False,
        "model_input_authorized": False,
        "dylan_editor_email_authorized": False,
        "publication_authorized": False,
        "japan_desk_production_activated": False,
        "instructions": (
            "Hash-only metadata of manually requested official live HTML bytes. "
            "Original HTML not archived; publisher version history and text "
            "fidelity cannot be independently reconstructed from this receipt. "
            "Separately review original language, third-party rights and reuse. "
            "No model, email or publication authorization is granted."
        ),
    }
