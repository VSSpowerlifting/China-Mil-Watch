"""
The document extraction interface.

One entry point — `extract(data, content_type=..., url=...)` — for turning the
bytes of a fetched document into text, or into a status explaining why there is
none. Today it dispatches to two backends: the HTML path already used by the
source adapters, and `processing.pdf_text` for PDFs.

Why an interface rather than a second call site
-----------------------------------------------
The Japan research is the immediate reason: one of its two source families
publishes HTML and the other publishes PDF, so a collector for it needs both,
and the choice must be made once, in a place that can be tested, rather than
inside whichever adapter is written first. The durable reason is the same rule
`processing.pdf_text` was written to enforce, applied one level up: a caller
that receives `str` cannot tell an empty document from a failed extraction, so
this returns a status too.

What it does NOT do
-------------------
No network. It takes bytes a caller already has. Nothing here fetches, retries,
or decides a size policy — a caller downloading from the open web owns that
before it calls in.

**It enables nothing.** This module is imported by no collector, adapter,
manifest, workflow or site path. `processing.pdf_text` was dormant before this
existed and is dormant after it; wrapping it changes no collection behaviour,
and no Japan collector exists.

Fail-closed, preserved exactly
------------------------------
The PDF statuses pass through unchanged and keep their meanings: a scan is
`no_text_layer`, not an empty article; a malformed file and an encrypted one
stay distinguishable; the two resource ceilings are refusals that carry no
partial text; per-page failures stay visible in `pages_failed`. The one
invariant is enforced mechanically in `__post_init__`, as it is one level
down: a result that is not `OK` cannot carry text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from processing import pdf_text

#: Extraction succeeded and `text` is the complete extracted text.
OK = pdf_text.OK

#: The document parsed, and carries no text layer at all — a scan, or a page of
#: pure vector art. Distinct from a document that says little.
NO_TEXT_LAYER = pdf_text.NO_TEXT_LAYER

#: The bytes are not the document they claim to be, or the parser refused them.
MALFORMED = pdf_text.MALFORMED

#: A password is required. Not a fault, and not empty — a refusal.
ENCRYPTED = pdf_text.ENCRYPTED

#: Refusals under a resource ceiling. Neither carries partial text.
TOO_LARGE = pdf_text.TOO_LARGE
TOO_MANY_PAGES = pdf_text.TOO_MANY_PAGES

#: No backend handles this content type. The document is stored as unread
#: rather than stored as empty.
UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"

#: Only statuses in here may carry text.
TEXT_BEARING = frozenset({OK})

STATUSES = (OK, NO_TEXT_LAYER, MALFORMED, ENCRYPTED, TOO_LARGE,
            TOO_MANY_PAGES, UNSUPPORTED_MEDIA_TYPE)

#: Reader-facing meanings. Wording is plain; the distinctions are not softened,
#: because the point of having six statuses is that they are six facts.
STATUS_PROSE = {
    OK: "Text extracted in full.",
    NO_TEXT_LAYER: "The document carries no text layer — an image or a scan. "
                   "It is recorded as unread, not as empty.",
    MALFORMED: "The bytes could not be parsed as the document type they "
               "claimed.",
    ENCRYPTED: "The document is password-protected and was not opened.",
    TOO_LARGE: "The document exceeded the size ceiling and was refused whole. "
               "No partial text was kept.",
    TOO_MANY_PAGES: "The document exceeded the page ceiling and was refused "
                    "whole. No partial text was kept.",
    UNSUPPORTED_MEDIA_TYPE: "No extractor handles this document type.",
}

#: Content types each backend claims. Matched on the media type only; a charset
#: or boundary parameter is ignored.
PDF_TYPES = frozenset({"application/pdf", "application/x-pdf"})
HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})
TEXT_TYPES = frozenset({"text/plain"})

_TAG = re.compile(r"<[^>]+>")
_SCRIPT_OR_STYLE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class Extraction:
    """
    What a document turned out to contain.

    `text` is non-empty only when `status` is `OK`, enforced rather than
    documented. `pages_failed` is meaningful for paginated formats and stays 0
    elsewhere; `OK` with `pages_failed > 0` means "complete as far as the parser
    got", exactly as it does in `processing.pdf_text`.
    """

    status: str
    text: str = ""
    media_type: str = ""
    backend: str = ""
    page_count: int = 0
    pages_with_text: int = 0
    pages_failed: int = 0
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == OK

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(
                "unknown extraction status %r; known statuses are %s"
                % (self.status, ", ".join(sorted(STATUSES))))
        if self.text and self.status not in TEXT_BEARING:
            raise ValueError(
                "Extraction carries text with status %r; only %s may carry "
                "text" % (self.status, sorted(TEXT_BEARING)))


def media_type_of(content_type: Optional[str], url: Optional[str] = None) -> str:
    """
    The bare media type, lowercased, from a Content-Type header.

    Falls back to the URL suffix only when the header is absent — never when it
    is present and merely inconvenient. A server that says `text/html` for a
    file named `.pdf` is telling us something, and guessing past it is how a
    challenge page gets stored as a document.
    """
    if content_type:
        return content_type.split(";", 1)[0].strip().lower()
    if url:
        path = url.split("?", 1)[0].split("#", 1)[0].lower()
        if path.endswith(".pdf"):
            return "application/pdf"
        if path.endswith((".html", ".htm")):
            return "text/html"
        if path.endswith(".txt"):
            return "text/plain"
    return ""


def _decode(data: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "shift_jis", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _extract_markup(data: bytes) -> Extraction:
    """Strip markup to visible text, normalising whitespace as the PDF path does."""
    raw = _decode(bytes(data))
    stripped = _SCRIPT_OR_STYLE.sub(" ", raw)
    text = pdf_text.normalise(_TAG.sub(" ", stripped))
    if not text:
        # An HTML document with no visible text is the same class of fact as a
        # PDF with no text layer: it parsed, and it carries nothing to read.
        return Extraction(NO_TEXT_LAYER, media_type="text/html", backend="markup",
                          detail="markup parsed; no visible text")
    return Extraction(OK, text=text, media_type="text/html", backend="markup")


def _extract_plain(data: bytes) -> Extraction:
    text = pdf_text.normalise(_decode(bytes(data)))
    if not text:
        return Extraction(NO_TEXT_LAYER, media_type="text/plain",
                          backend="plain", detail="no text in document")
    return Extraction(OK, text=text, media_type="text/plain", backend="plain")


def _extract_pdf(data: bytes, **kwargs) -> Extraction:
    result = pdf_text.extract_pdf_text(data, **kwargs)
    return Extraction(
        status=result.status, text=result.text,
        media_type="application/pdf", backend="pdf_text",
        page_count=result.page_count, pages_with_text=result.pages_with_text,
        pages_failed=result.pages_failed, detail=result.detail,
    )


def extract(data: bytes, content_type: Optional[str] = None,
            url: Optional[str] = None, **kwargs) -> Extraction:
    """
    Extract text from document bytes, or say why there is none.

    Never raises for bad input. Programmer error — a non-bytes argument — still
    raises, as it does one level down.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("extract expects bytes, got %s" % type(data).__name__)

    media_type = media_type_of(content_type, url)

    if media_type in PDF_TYPES:
        return _extract_pdf(data, **kwargs)
    if media_type in HTML_TYPES:
        return _extract_markup(data)
    if media_type in TEXT_TYPES:
        return _extract_plain(data)

    # No declared type: sniff the one magic number we can trust. A PDF is
    # unambiguous; HTML is not, so an unsniffable document is refused rather
    # than parsed as markup and stored as whatever fell out.
    if not media_type and bytes(data[:5]) == pdf_text.MAGIC:
        return _extract_pdf(data, **kwargs)

    return Extraction(
        UNSUPPORTED_MEDIA_TYPE, media_type=media_type, backend="",
        detail="no extractor handles %r" % (media_type or "an undeclared type"))
