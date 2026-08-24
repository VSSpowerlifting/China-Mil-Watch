"""
Text extraction from PDF documents.

Written for the Japan Joint Staff press releases, which are published as PDF
(`/js/pdf/<YYYY>/p<YYYYMMDD>_<NN>e.pdf`) rather than HTML. Nothing here is
Japan-specific: it takes PDF bytes and returns what text they carry.

The rule this module exists to enforce
--------------------------------------
A PDF that carries no text layer — a scan, or a page of pure vector art — parses
perfectly and yields the empty string. So does a PDF whose pages all failed to
decode. So, for that matter, does a document that genuinely says nothing. If
extraction returned `str`, all three would arrive at the caller as `""` and be
stored as an article with an empty body.

That is not hypothetical here. `PROJECT_STATE.md` records article id=2678:
`text_original` is 0 chars because the body was never captured, and because it
was stored anyway it went on to pass relevance screening **on its title alone**.
One empty string became a scored, published record of nothing.

So this module never returns a bare string. It returns a `PdfExtraction` whose
`status` says which of those worlds it is in, and `text` is non-empty only when
the status is `OK`. This mirrors `core/collection/status.py` one level down: the
same discipline, applied per document instead of per run.

Determinism
-----------
Same bytes in, same result out. No wall clock, no network, no filesystem. The
whitespace normalisation matches `visible_text()` in the source adapters so a
PDF body and an HTML body are comparable once stored.

Limits, and whose job they are
------------------------------
Text is never truncated. There is no output ceiling, and none should be added
quietly: a shortened body returned as `OK` is indistinguishable from a short
document, which is the confusion this whole module exists to prevent.

The two limits that do exist — `MAX_BYTES` and `MAX_PAGES` — are refusals, not
trims. Both are checked before any text is assembled and both return their own
status carrying no text at all. Any limit added later must follow that rule:
**fail closed under a distinct status** (`resource_limit_exceeded` or a more
specific one), never return partial text as success. `__post_init__` enforces
the second half of that mechanically — a non-`OK` result cannot carry text even
if someone tries.

These limits are a backstop against a pathological document, not an intake
policy. **A caller that fetches over the network is responsible for its own
fetch-size and timeout policy before it calls this function.** By the time bytes
arrive here they have already been downloaded; refusing them at this point saves
parsing, not bandwidth.
"""

from __future__ import annotations

import contextlib
import io
import logging
import re
from dataclasses import dataclass

# ── outcomes ─────────────────────────────────────────────────────────────────

OK = "ok"
"""A text layer was found and yielded usable text."""

NO_TEXT_LAYER = "no_text_layer"
"""The PDF parsed, but carries no extractable text — typically a scan. NOT an
error and NOT an empty document: it means the text exists only as pixels, and
that OCR, not a retry, is what would change the answer."""

ENCRYPTED = "encrypted"
"""Password-protected or permission-encrypted. Distinct from malformed: the
bytes are a valid PDF that this collector is not entitled to read."""

MALFORMED = "malformed"
"""Not a PDF, or damaged past the point where a page tree can be read."""

TOO_LARGE = "too_large"
"""Refused before parsing, on byte count. A policy decision, not a defect in
the document."""

TOO_MANY_PAGES = "too_many_pages"
"""Refused after reading the page count. Also policy."""

#: Statuses that carry text. Exactly one, by design — a caller that checks
#: `status in TEXT_BEARING` cannot accidentally treat a scan as a short article.
TEXT_BEARING = frozenset({OK})

#: Refusals that a retry cannot fix. Useful to a collector deciding whether a
#: document belongs in a retry queue or in a permanent-skip list.
TERMINAL = frozenset({NO_TEXT_LAYER, ENCRYPTED, MALFORMED, TOO_LARGE,
                      TOO_MANY_PAGES})

# ── policy ───────────────────────────────────────────────────────────────────

#: Joint Staff releases are one or two pages. The cap exists so a pathological
#: or hostile document cannot turn one fetch into an unbounded parse.
MAX_PAGES = 200

#: PDFs are larger than the 4 MB HTML ceiling the source adapters use, but not
#: unboundedly so. A ministry press release above this is not a press release.
MAX_BYTES = 8_000_000

#: The floor that separates "this document has a text layer" from "these are a
#: few stray characters a scanner left behind" (a page number, a fax header).
#: Deliberately much lower than the collectors' 200-character *body* floor:
#: that one is an editorial judgement about whether a document is worth storing,
#: and it belongs to the collector. This one is a structural question about the
#: file, and answering it here keeps the two from being confused.
MIN_TEXT_CHARS = 24

#: The first bytes of any PDF. Checked before handing anything to the parser so
#: an HTML error page served with a .pdf URL is reported as MALFORMED rather
#: than raising from inside the library.
MAGIC = b"%PDF-"


@contextlib.contextmanager
def _quiet_pypdf():
    """
    Keep pypdf's complaints out of the run log.

    pypdf logs "EOF marker not found" and similar at ERROR level for exactly the
    damaged inputs this module is built to handle. Every one of them becomes a
    `MALFORMED` result the caller records, so letting the library also shout
    into the log would put an unactioned error line beside a handled outcome —
    the same "log disagrees with the record" problem the collection-health table
    was reordered to fix. Scoped to the parse; nothing else is silenced.
    """
    logger = logging.getLogger("pypdf")
    previous = logger.level
    logger.setLevel(logging.CRITICAL)
    try:
        yield
    finally:
        logger.setLevel(previous)


@dataclass(frozen=True)
class PdfExtraction:
    """
    What a PDF turned out to contain. `text` is non-empty only when OK.

    What `OK` claims, precisely: the parser read this document and what came
    back is here in full, untruncated. It does **not** claim every page
    contributed. A page that raised during extraction is skipped rather than
    failing the document, and `pages_failed` records how many — so `OK` with
    `pages_failed > 0` means "complete as far as the parser got", and a caller
    that needs whole-document certainty should read that field rather than the
    status alone. `page_count` and `pages_with_text` bound the same question
    from the other side.
    """

    status: str
    text: str = ""
    page_count: int = 0
    pages_with_text: int = 0
    pages_failed: int = 0
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == OK

    def __post_init__(self):
        # The invariant is the whole point of the module, so it is enforced
        # rather than documented and hoped for.
        if self.text and self.status not in TEXT_BEARING:
            raise ValueError(
                "PdfExtraction carries text with status %r; only %s may carry "
                "text" % (self.status, sorted(TEXT_BEARING)))


def normalise(text: str) -> str:
    """Collapse whitespace the way the HTML adapters do, so bodies compare."""
    # PDF extraction emits hard line breaks mid-sentence wherever the source
    # laid out a line. Joining them is what makes the result a paragraph rather
    # than a column of fragments.
    text = text.replace("­", "")          # soft hyphens, invisible in print
    text = re.sub(r"-\n(?=[a-z])", "", text)   # hyphenated line breaks
    return re.sub(r"\s+", " ", text).strip()


def extract_pdf_text(data: bytes, *, max_bytes: int = MAX_BYTES,
                     max_pages: int = MAX_PAGES,
                     min_chars: int = MIN_TEXT_CHARS) -> PdfExtraction:
    """
    Extract the text layer from PDF bytes.

    Never raises for bad input: a caller handling documents from the open web
    needs a value it can record, not an exception that ends the run. Programmer
    error (a wrong argument type) still raises.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("extract_pdf_text expects bytes, got %s"
                        % type(data).__name__)
    if len(data) > max_bytes:
        return PdfExtraction(TOO_LARGE, page_count=0,
                             detail="%d bytes exceeds the %d-byte ceiling"
                                    % (len(data), max_bytes))
    if not data.startswith(MAGIC):
        return PdfExtraction(
            MALFORMED,
            detail="does not begin with %s — a PDF URL that returns an error "
                   "page reaches here as HTML" % MAGIC.decode("ascii"))

    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError as exc:                              # pragma: no cover
        raise RuntimeError(
            "pypdf is required for PDF extraction; add it to requirements.txt"
        ) from exc

    try:
        with _quiet_pypdf():
            reader = PdfReader(io.BytesIO(bytes(data)))
    except Exception as exc:
        return PdfExtraction(MALFORMED,
                             detail="%s: %s" % (type(exc).__name__, exc))

    if getattr(reader, "is_encrypted", False):
        # pypdf can open some encrypted files with an empty password. Try it,
        # because a permissions-only encryption is readable and refusing it
        # would lose a document we are entitled to read; a real password is a
        # refusal.
        try:
            if not reader.decrypt(""):
                return PdfExtraction(ENCRYPTED,
                                     detail="password required")
        except Exception as exc:
            return PdfExtraction(ENCRYPTED,
                                 detail="%s: %s" % (type(exc).__name__, exc))

    try:
        with _quiet_pypdf():
            pages = list(reader.pages)
    except Exception as exc:
        return PdfExtraction(MALFORMED,
                             detail="page tree unreadable: %s" % type(exc).__name__)

    if len(pages) > max_pages:
        return PdfExtraction(TOO_MANY_PAGES, page_count=len(pages),
                             detail="%d pages exceeds the %d-page ceiling"
                                    % (len(pages), max_pages))

    chunks, with_text, failed = [], 0, 0
    for page in pages:
        # One unreadable page must not cost the document. The count is carried
        # out so a body assembled from half a file is visibly that.
        try:
            with _quiet_pypdf():
                piece = page.extract_text() or ""
        except Exception:
            failed += 1
            continue
        if piece.strip():
            with_text += 1
            chunks.append(piece)

    text = normalise("\n".join(chunks))
    if len(text) < min_chars:
        return PdfExtraction(
            NO_TEXT_LAYER, page_count=len(pages), pages_with_text=with_text,
            pages_failed=failed,
            detail="%d character(s) recovered from %d page(s); below the "
                   "%d-character floor that distinguishes a text layer from "
                   "scanner residue" % (len(text), len(pages), min_chars))

    return PdfExtraction(OK, text=text, page_count=len(pages),
                         pages_with_text=with_text, pages_failed=failed,
                         detail="")
