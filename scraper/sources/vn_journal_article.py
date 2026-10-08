"""Offline-only English National Defence Journal article extraction candidate.

Confirmed 2026-10-08 GitHub Actions structural probe:
- .newsdt-page-ct-tit is the article headline (not h1).
- .newsdt-page-ct-time span is the source publication date (not site clock).
- .newsdt-page-ct-text contains direct paragraphs and occasional tables.
- The final paragraph may contain a rank/title-qualified author credit.

This module performs no network requests, storage, source activation or
publication. Full text is returned in memory solely for separately authorized
future shadow-adapter use. Synthetic test fixtures contain no source prose.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from bs4 import BeautifulSoup, Tag
from scraper.sources import vn_defence_journal as source

PUBLISHER = "National Defence Journal (Tạp chí Quốc phòng toàn dân)"
AUTHOR_PREFIX = re.compile(
    r"(?i)\b(?:major general|lieutenant general|senior colonel|colonel|"
    r"brigadier general|general|associate professor|prof(?:essor)?\.?|"
    r"ph\.?\s*d\.?|dr\.?|captain|commander)\b"
)
MAX_BLOCKS = 100
MAX_TEXT_CHARS = 150_000


class ExtractionRefused(ValueError):
    pass


@dataclass(frozen=True)
class OfflineArticle:
    url: str
    source_slug: str
    source_identity: str
    title_original: str
    published_date: str
    published_date_original: str
    language_tag: str
    publisher: str
    text_original: str
    body_blocks: Tuple[Tuple[str, str], ...]
    author_credit_original: Optional[str]
    author_name_verified: bool = False
    full_text_reuse_authorized: bool = False


def one(root, selector, label):
    nodes = root.select(selector)
    if len(nodes) != 1:
        raise ExtractionRefused("expected exactly one " + label)
    return nodes[0]


def clean_text(node):
    return " ".join(node.get_text(" ", strip=True).split())


def classify_author(paragraph):
    """Extract explicit final credit conservatively, without invented names."""
    if paragraph.name != "p":
        return None
    emphasis = paragraph.select("strong > em")
    if len(emphasis) != 1:
        return None
    text = clean_text(paragraph)
    credit = clean_text(emphasis[0])
    # Measured pages put a rank-qualified name in strong/em, but may add
    # affiliation or a role after that emphasis in the *same final p*.
    # Preserve that entire credit as metadata, not a prose paragraph.
    if (not text or not credit or not text.startswith(credit)
            or not AUTHOR_PREFIX.search(credit) or len(text) > 500):
        return None
    return text


def parse_desktop_article(html, url):
    """Parse supplied in-memory page HTML, refusing uncertain source shape."""
    try:
        normalized = source.canonical_article_url(url)
    except ValueError as exc:
        raise ExtractionRefused("unrecognized journal URL") from exc
    if normalized != url:
        raise ExtractionRefused("desktop canonical article URL required")
    soup = BeautifulSoup(html, "html.parser")
    if not soup.html or not soup.body:
        raise ExtractionRefused("incomplete journal HTML document")
    article = one(soup, ".page-main-left-newsdt .newsdt-page-ct",
                  "article container")
    heading = clean_text(one(article, ".newsdt-page-ct-tit", "article headline"))
    stamp = clean_text(one(article, ".newsdt-page-ct-time span", "publication date"))
    body = one(article, ".newsdt-page-ct-text", "article body")
    if not heading or len(heading) > 500:
        raise ExtractionRefused("missing or implausible article headline")
    try:
        published = source.stated_date(stamp)
    except ValueError as exc:
        raise ExtractionRefused("unrecognized article publication date") from exc
    children = [c for c in body.children if isinstance(c, Tag)]
    if not children or len(children) > MAX_BLOCKS:
        raise ExtractionRefused("empty or excessive article body structure")
    if any(child.name not in {"p", "table"} for child in children):
        raise ExtractionRefused("unknown journal body structure")
    # Both measured samples place the rank-qualified credit near the end,
    # but not at the absolute final p. Search the final six direct elements,
    # refuse competing credits, and remove only the recognized paragraph.
    candidates = [(index, credit) for index, child in enumerate(children)
                  if index >= max(0, len(children) - 6)
                  for credit in [classify_author(child)] if credit is not None]
    if len(candidates) > 1:
        raise ExtractionRefused("ambiguous author credit in journal body")
    author_credit = candidates[0][1] if candidates else None
    if candidates:
        children.pop(candidates[0][0])
    blocks = []
    for child in children:
        prose = clean_text(child)
        if prose:
            kind = "caption_or_table" if child.name == "table" else "paragraph"
            blocks.append((kind, prose))
    if not blocks:
        raise ExtractionRefused("no readable original journal prose")
    assembled = "\n\n".join(t for _, t in blocks)
    if len(assembled) > MAX_TEXT_CHARS:
        raise ExtractionRefused("article body exceeds bounded text size")
    if assembled.strip() == heading:
        raise ExtractionRefused("article has only a title shell")
    return OfflineArticle(
        url=url, source_slug=source.SOURCE_SLUG,
        source_identity=source.article_identity(url),
        title_original=heading, published_date=published,
        published_date_original=stamp, language_tag="en", publisher=PUBLISHER,
        text_original=assembled, body_blocks=tuple(blocks),
        author_credit_original=author_credit,
    )
