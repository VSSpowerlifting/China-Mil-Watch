"""Versioned reading structure, separate from frozen Brief publication records.

No prose is generated. Drafts are private previews; production requires an
independent exact-content receipt and the existing manuscript release gates.
"""
import hashlib
import json
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

from core.brief_source_linked import fingerprint, is_source_linked

VERSION = "brief-presentation-v1"
DIRECTORY = Path("briefs/presentation")
CHECKS = {"headings", "excerpts", "media", "rendered_page"}
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
ANCHOR = re.compile(r"reading-[a-z0-9]+(?:-[a-z0-9]+)*")
RESERVED = {"reading-finding", "reading-evidence", "reading-establishes", "reading-uncertain"}


def presentation_fingerprint(manifest):
    payload = {k: v for k, v in manifest.items() if k not in {"status", "approval"}}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def _plain(value, limit):
    return (isinstance(value, str) and bool(value.strip()) and len(value) <= limit
            and not re.search(r"[<>\x00-\x1f\x7f]", value))


def _keys(value, required, optional=()):
    return isinstance(value, dict) and set(required) <= set(value) <= set(required) | set(optional)


def validate_presentation(manifest, article, *, slug):
    """Fail closed on malformed structure, bindings, excerpts or receipts."""
    required = {"version", "article", "manuscript_fingerprint", "status", "sections", "approval"}
    if not _keys(manifest, required, {"central_finding", "evidence", "figures"}):
        return ["presentation has invalid fields"]
    errors = []
    if manifest["version"] != VERSION or not is_source_linked(article):
        errors.append("presentation requires v1 and a source-linked manuscript")
    if not SLUG.fullmatch(slug) or manifest["article"] != slug:
        errors.append("presentation article identity differs")
    if manifest["manuscript_fingerprint"] != fingerprint(article):
        errors.append("presentation manuscript binding is stale")
    if manifest["status"] not in ("draft", "approved"):
        errors.append("presentation status must be draft or approved")
    paragraphs = article.get("body_paragraphs") or []
    sections = manifest["sections"]
    if not isinstance(sections, list) or not 1 <= len(sections) <= len(paragraphs):
        errors.append("presentation needs ordered sections")
        sections = []
    next_paragraph, anchors = 1, set()
    for section in sections:
        if not _keys(section, {"id", "heading", "start", "end"}):
            errors.append("section has invalid fields")
            continue
        anchor = section["id"]
        if (not isinstance(anchor, str) or not ANCHOR.fullmatch(anchor)
                or anchor in anchors or anchor in RESERVED):
            errors.append("section has duplicate or unsafe anchor")
        else:
            anchors.add(anchor)
        if not _plain(section["heading"], 140):
            errors.append("section heading must be bounded plain text")
        start, end = section["start"], section["end"]
        if (type(start) is not int or type(end) is not int or start != next_paragraph
                or not 1 <= start <= end <= len(paragraphs)):
            errors.append("sections must cover every paragraph once in order")
        else:
            next_paragraph = end + 1
    if next_paragraph != len(paragraphs) + 1:
        errors.append("sections omit manuscript paragraphs")

    def excerpt(value):
        if not _keys(value, {"paragraph", "quote", "sources"}):
            errors.append("excerpt has invalid fields")
            return
        index, quote, sources = value["paragraph"], value["quote"], value["sources"]
        if type(index) is not int or not 1 <= index <= len(paragraphs):
            errors.append("excerpt paragraph is invalid")
            return
        original = "".join(r["text"] for r in paragraphs[index - 1])
        if not _plain(quote, 1600) or quote not in original:
            errors.append("excerpt must quote exact approved manuscript text")
        supported = article["paragraph_support"][index - 1]["sources"]
        if (not isinstance(sources, list) or not sources
                or any(not isinstance(s, str) for s in sources)
                or len(set(sources)) != len(sources)
                or any(s not in supported for s in sources)):
            errors.append("excerpt contains unsupported evidence references")

    if "central_finding" in manifest:
        excerpt(manifest["central_finding"])
    if "evidence" in manifest:
        evidence = manifest["evidence"]
        if not _keys(evidence, {"establishes", "uncertain"}):
            errors.append("evidence component needs both parts")
        else:
            for part in evidence.values():
                if not isinstance(part, list) or not 1 <= len(part) <= 4:
                    errors.append("evidence part needs 1–4 reviewed excerpts")
                else:
                    for statement in part:
                        excerpt(statement)
    figures = manifest.get("figures", [])
    if not isinstance(figures, list) or len(figures) > 4:
        errors.append("figures must be a bounded list")
        figures = []
    placements = set()
    for figure in figures:
        if not _keys(figure, {"after_paragraph", "media_id"}):
            errors.append("figure has invalid fields")
            continue
        index, media_id = figure["after_paragraph"], figure["media_id"]
        if (type(index) is not int or not 1 <= index <= len(paragraphs)
                or index in placements):
            errors.append("figure placement is invalid or duplicated")
        else:
            placements.add(index)
        if not isinstance(media_id, str) or not SLUG.fullmatch(media_id):
            errors.append("figure must name a local approved media identity")
    approval = manifest["approval"]
    if manifest["status"] == "draft":
        if approval is not None:
            errors.append("draft presentation cannot carry approval")
    elif manifest["status"] == "approved":
        if not _keys(approval, {"reviewed_by", "reviewed_on", "reference", "fingerprint", "checks"}):
            errors.append("approved presentation needs an independent complete receipt")
        else:
            if (not _plain(approval["reviewed_by"], 120)
                    or not _plain(approval["reference"], 1800)):
                errors.append("presentation approval needs reviewer and authorization reference")
            try:
                if date.fromisoformat(approval["reviewed_on"]).isoformat() != approval["reviewed_on"]:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append("presentation approval date is invalid")
            if approval["fingerprint"] != presentation_fingerprint(manifest):
                errors.append("presentation approval fingerprint differs")
            if (not isinstance(approval["checks"], dict) or set(approval["checks"]) != CHECKS
                    or any(v is not True for v in approval["checks"].values())):
                errors.append("presentation approval checks are incomplete")
    return errors


def load_presentation(path, article, *, slug, review=False):
    path = Path(path)
    if not path.is_file():
        if review:
            raise ValueError("presentation review manifest is missing")
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    # A recognized draft is private editorial work, not a public build input.
    # Classify its envelope before checking content that may be incomplete/stale.
    if (not review and isinstance(manifest, dict) and manifest.get("status") == "draft"
            and manifest.get("version") == VERSION and manifest.get("article") == slug
            and isinstance(slug, str) and SLUG.fullmatch(slug) and is_source_linked(article)):
        return None
    errors = validate_presentation(manifest, article, slug=slug)
    if errors:
        raise ValueError("presentation: " + "; ".join(errors))
    return manifest if review or manifest["status"] == "approved" else None


def presentation_view(manifest, article, *, media=None):
    """Build only validated plain-text views; existing media gates grant figures."""
    if manifest is None:
        return None
    figures = {}
    for placement in manifest.get("figures", []):
        if not media or media.get("kind") != "photograph" or media.get("id") != placement["media_id"]:
            raise ValueError("presentation figure lacks this article's approved media admission")
        figures[placement["after_paragraph"]] = media
    return dict(manifest, sections=[dict(s, paragraphs=[{
        "index": i, "runs": article["body_paragraphs"][i - 1], "figure": figures.get(i)}
        for i in range(s["start"], s["end"] + 1)]) for s in manifest["sections"]])


def presentation_html_errors(manifest, html):
    """The output gate checks structure as well as the independent prose check."""
    class Reader(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.ids, self.headings, self.ranges, self.toc, self.quotes = [], [], {}, [], []
            self.figures, self.paragraph = [], None
            self.section = None
            self.heading = self.link = self.quote = None
            self.in_toc = False

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            ident = attrs.get("id", "")
            if ident.startswith(("reading-", "h-reading-")):
                self.ids.append(ident)
            if tag == "section" and ident.startswith("reading-") and ident != "reading-evidence":
                self.section = ident
                self.paragraph = None
                self.ranges.setdefault(ident, [])
            if tag == "p" and "data-manuscript-paragraph" in attrs and self.section:
                self.ranges[self.section].append(attrs["data-manuscript-paragraph"])
                self.paragraph = attrs["data-manuscript-paragraph"]
            if tag == "figure" and self.section:
                self.figures.append((self.paragraph, attrs.get("data-editorial-id")))
            if tag == "h2" and ident.startswith("h-reading-"):
                self.heading = [ident, []]
                self.headings.append(self.heading)
            if tag == "nav" and "brief-toc" in attrs.get("class", "").split():
                self.in_toc = True
            if tag == "a" and self.in_toc:
                self.link = [attrs.get("href"), []]
                self.toc.append(self.link)
            if tag == "blockquote":
                self.quote = []
                self.quotes.append(self.quote)

        def handle_data(self, text):
            for current in (self.heading, self.link):
                if current is not None:
                    current[1].append(text)
            if self.quote is not None:
                self.quote.append(text)

        def handle_endtag(self, tag):
            if tag == "h2":
                self.heading = None
            if tag == "a":
                self.link = None
            if tag == "nav":
                self.in_toc = False
            if tag == "section":
                self.section = None
            if tag == "blockquote":
                self.quote = None

    reader = Reader()
    reader.feed(html)
    if manifest is None:
        return ["unapproved presentation appears in rendered output"] if reader.ids else []
    headings, expected_quotes = [], []
    if "central_finding" in manifest:
        headings.append(("h-reading-finding", "Central finding"))
        expected_quotes.append(manifest["central_finding"]["quote"])
    headings.extend(("h-" + s["id"], s["heading"]) for s in manifest["sections"])
    if "evidence" in manifest:
        headings.append(("h-reading-evidence", "Evidence and uncertainty"))
        for key in ("establishes", "uncertain"):
            expected_quotes.extend(s["quote"] for s in manifest["evidence"][key])
    norm = lambda text: " ".join(text.split())
    actual_headings = [(i, norm("".join(t))) for i, t in reader.headings]
    toc = [("#" + i[2:], heading) for i, heading in headings]
    toc += [("#s-publishers", "Publisher references"), ("#s-cite", "Cite this brief")]
    ranges = {s["id"]: [str(i) for i in range(s["start"], s["end"] + 1)]
              for s in manifest["sections"]}
    errors = []
    if len(reader.ids) != len(set(reader.ids)):
        errors.append("rendered presentation anchors are duplicated")
    expected_ids = {i for i, _ in headings} | {i[2:] for i, _ in headings}
    if "evidence" in manifest:
        expected_ids |= {"h-reading-establishes", "h-reading-uncertain"}
    if set(reader.ids) != expected_ids or actual_headings != headings or reader.ranges != ranges:
        errors.append("rendered section headings, anchors or paragraph boundaries differ")
    if [(i, norm("".join(t))) for i, t in reader.toc] != toc:
        errors.append("rendered presentation navigation differs")
    if [norm("".join(t)) for t in reader.quotes] != [norm(q) for q in expected_quotes]:
        errors.append("rendered presentation excerpts differ")
    figures = sorted(manifest.get("figures", []), key=lambda f: f["after_paragraph"])
    if reader.figures != [(str(f["after_paragraph"]), f["media_id"]) for f in figures]:
        errors.append("rendered presentation figure placements differ")
    return errors
