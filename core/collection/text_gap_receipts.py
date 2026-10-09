"""Metadata-only receipts for individual source pages with no usable prose.

The per-source collection result counts these pages but loses their identity.
Capture this evidence BEFORE title/URL dedup or keyword filtering, since an
unreadable source item may be duplicate or rejected instead of newly inserted.
No source text, title, query string, credentials or model payload in logs.
"""
from __future__ import annotations

import hashlib
import logging
import re
from urllib.parse import urlsplit, urlunsplit

_MAX_RECEIPTS = 10
_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _url_receipt(url):
    """Return a bounded public locator and a stable digest of the full URL.

    Queries and userinfo can contain credentials. The full original URL is
    only hashed in memory, never printed. This is evidence for a human source
    review, not an invitation to fetch the page again.
    """
    if not isinstance(url, str) or not url:
        return "<invalid-url>", "unavailable"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
        if parts.scheme.lower() not in ("http", "https") or not hostname:
            return "<invalid-url>", digest
        if ":" in hostname:  # Preserve IPv6 formatting without credentials.
            hostname = "[" + hostname + "]"
        locator = urlunsplit((parts.scheme.lower(), hostname, parts.path, "", ""))
        return locator[:240], digest
    except ValueError:
        return "<invalid-url>", digest


def _published_date(value):
    return value if isinstance(value, str) and _DATE_RE.fullmatch(value) else "unknown"


def log_unreadable_source_receipts(source_slug, documents, logger: logging.Logger,
                                   limit: int = _MAX_RECEIPTS) -> int:
    """Log identity, not contents, for every unreadable document up to a cap.

    Does not change the source result, document, database or model queue.
    Returns the FULL unreadable count even when log detail is capped.
    """
    gaps = [doc for doc in documents if not doc.has_usable_text]
    if not gaps:
        return 0
    safe_source = source_slug if isinstance(source_slug, str) and re.fullmatch(
        r"[a-z0-9_]{1,64}", source_slug
    ) else "unknown"
    cap = max(0, limit)
    for doc in gaps[:cap]:
        locator, digest = _url_receipt(doc.url)
        logger.warning(
            "Source document without usable text: source=%s url=%r "
            "published_date=%s identity_sha256_16=%s; source review required "
            "(not a publisher-silence verdict)",
            safe_source, locator, _published_date(doc.published_date), digest,
        )
    if len(gaps) > cap:
        logger.warning(
            "Source no-text detail capped: source=%s shown=%d total=%d; "
            "no remaining identities inferred",
            safe_source, cap, len(gaps),
        )
    return len(gaps)
