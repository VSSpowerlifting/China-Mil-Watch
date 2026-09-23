"""
The Indo-Pacific Record Briefs collection: every issue, one ordered list.

Why this module exists
----------------------
DECISION_LOG 2026-09-23 makes *Indo-Pacific Record Briefs* one continuing
collection that includes the fourteen existing issues and every later one.
`core/brief_contract.py` says what a brief is; `core/edition_identity.py` says
who published an issue. Neither gives a brief an address. This module is the
seam between them and the site builder (`site/preview/generate_preview.py`):

  * `load_collection` reads brief sidecars, holds every one to the contract,
    and returns the existing issues and the briefs as one list, newest number
    first, each row carrying where it was published;
  * `brief_view` prepares one brief for its page: everything displayed is
    derived from the sidecar, and nothing is composed;
  * `brief_veil` resolves a brief's Signal Veil under the same provenance rule
    the existing issues use;
  * `build_briefs_feed` writes the collection's Atom feed of briefs.

What it never does
------------------
It never rewrites an existing issue. Historical rows hold the very dicts
`load_editions` produced, unchanged, and they link to the addresses those
issues were published at. The briefs feed carries briefs only: the existing
issues keep their entries, IDs and addresses in `the-pla-watch/feed.xml`,
which this module does not read, write or restate.

It never publishes a draft. A sidecar whose `editorial_status` is `draft` is
recorded as withheld and produces no page, row, feed entry or sitemap entry.

It fails closed. A sidecar that cannot be parsed, names a slug the site cannot
address, or is `approved` and breaks the contract stops the build with every
problem listed, rather than vanishing from the collection.

It assigns no number. A brief arrives carrying the number `approve()` gave it,
and while `UNRECONCILED_ISSUES` is non-empty (No. 14: DECISION_LOG 2026-09-23
point 9) no numbered brief is published at all: the next number is not known,
and a hand-written sidecar must not bypass the gate `approve()` enforces.

Where briefs live
-----------------
Source sidecars live in `briefs/<slug>.json` at the repository root: source,
not output. `output/` is generated and replaced at publish time, so a sidecar
left in it would be deleted by the build that reads it. The slug is the file
stem and becomes the address, `briefs/<slug>.html`. No real brief exists yet.

Synthetic fixtures
------------------
A sidecar with `"synthetic": true` exists to test rendering. The loader refuses
it unless the caller passes `allow_synthetic=True`, and the site builder
refuses that flag whenever a site origin is set, so a fixture can never be
built into an indexable tree or a sitemap. A fixture is not a real issue and
consumes no real number, so the unreconciled-number gate does not apply to it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping, Optional
from xml.sax.saxutils import escape as xml_escape

from core.brief_contract import (
    BASIS_COMPARISON, BASIS_STATED, STATUS_APPROVED, STATUS_DRAFT,
    UNRECONCILED_ISSUES, assigned_number, check_numbering, validate_brief)
from core.edition_identity import (
    COLLECTION_NAME, ERA_HISTORICAL, IdentityError, resolve_identity)

#: Public routes, relative to the site root. There is no `briefs/index.html`:
#: the Analysis page is the collection's landing page, and a second index of
#: the same issues would be a duplicate to keep in step.
ROUTE_DIR = "briefs"
FEED_ROUTE = "briefs/feed.xml"
MEDIA_DIRNAME = "media"
LANDING_ROUTE = "analysis.html"

#: A slug is the address: lowercase words joined by single hyphens, safe as a
#: path segment, a fragment and a feed ID without escaping.
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
#: `index` would claim the directory's index, which is deliberately unused;
#: `feed` would sit beside the feed and read as it.
RESERVED_SLUGS = frozenset({"index", "feed"})

BASIS_LABELS = {
    BASIS_COMPARISON: "Compared side by side",
    BASIS_STATED: "Stated in a cited record",
}

#: The standing anatomy, in reading order: (sidecar field, anchor, heading).
#: The development and the cross-desk comparison are placed by the template;
#: an empty section renders nothing.
SECTIONS_BEFORE = (
    ("opening_note", "s-opening", "Opening note"),
    ("what_stood_out", "s-stood-out", "What stood out"),
)
SECTIONS_AFTER = (
    ("why_it_matters", "s-why", "Why it matters"),
    ("what_was_routine", "s-routine", "Routine baseline"),
)
WATCHING = ("what_im_watching_next", "s-watching", "What I'm watching next")


class CollectionError(ValueError):
    """The collection cannot be assembled. Carries every problem."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


def brief_route(slug: str) -> str:
    return "%s/%s.html" % (ROUTE_DIR, slug)


def paragraphs(text) -> list:
    """Blank-line separated paragraphs of plain prose. Nothing is markup."""
    return [p.strip() for p in re.split(r"\n\s*\n", str(text or ""))
            if p.strip()]


def _iso(value):
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def _norm_url(url) -> str:
    """Scheme, `www.` and a trailing slash do not make a different article."""
    url = re.sub(r"^https?://", "", str(url or "").strip().lower())
    url = re.sub(r"^www\.", "", url)
    return url.rstrip("/")


# ── Loading ───────────────────────────────────────────────────────────────────

def load_briefs(briefs_dir: Optional[Path], registry, *,
                historical_numbers: Iterable[int] = (),
                allow_synthetic: bool = False,
                unreconciled=UNRECONCILED_ISSUES):
    """
    Published briefs from `briefs_dir`, as `[(slug, sidecar)]`, and the slugs
    withheld as drafts. Raises `CollectionError` naming every problem.
    """
    if not briefs_dir or not Path(briefs_dir).is_dir():
        return [], []
    published, withheld, problems = [], [], []
    for path in sorted(Path(briefs_dir).glob("*.json")):
        slug = path.stem
        if not SLUG_RE.match(slug) or slug in RESERVED_SLUGS:
            problems.append(
                "%s: %r is not a usable address (lowercase words joined by "
                "hyphens, and not %s)"
                % (path.name, slug, " or ".join(sorted(RESERVED_SLUGS))))
            continue
        try:
            sidecar = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append("%s: cannot be read (%s)" % (path.name, exc))
            continue
        if not isinstance(sidecar, dict):
            problems.append("%s: is not a JSON object" % path.name)
            continue
        if sidecar.get("synthetic") and not allow_synthetic:
            problems.append("%s: is a synthetic rendering fixture and cannot "
                            "be published" % path.name)
            continue
        status = sidecar.get("editorial_status")
        if status == STATUS_DRAFT:
            withheld.append(slug)
            continue
        if status != STATUS_APPROVED:
            problems.append("%s: editorial_status must be %r or %r"
                            % (path.name, STATUS_DRAFT, STATUS_APPROVED))
            continue
        found = validate_brief(sidecar, registry)
        for field_name in ("week_start", "week_ending"):
            if _iso(sidecar.get(field_name)) is None:
                found.append("%s must be an ISO date" % field_name)
        problems += ["%s: %s" % (path.name, p) for p in found]
        if not found:
            published.append((slug, sidecar))

    real = [slug for slug, s in published if not s.get("synthetic")]
    if real and unreconciled:
        problems.append(
            "no numbered brief is published while No. %s has an unreconciled "
            "publication status (DECISION_LOG 2026-09-23 point 9); clearing it "
            "is the owner's ruling, never an edit made to unblock a build "
            "(refused: %s)"
            % (", ".join(str(n) for n in sorted(unreconciled)),
               ", ".join(real)))
    numbered = ([{"issue_number": n} for n in historical_numbers]
                + [s for _, s in published])
    problems += check_numbering(numbered)
    if problems:
        raise CollectionError(problems)
    return published, withheld


# ── Rows ──────────────────────────────────────────────────────────────────────

def brief_entry(slug: str, sidecar: Mapping) -> dict:
    """
    A brief as the same kind of dict `load_editions` yields for an issue, so
    the templates that list issues list briefs without a second code path.

    `articles` and `flagged` are None on purpose. A brief's records are counted
    per desk, never pooled: desks differ in volume and in how far their records
    are screened, so a sum across them describes nothing.
    """
    identity = resolve_identity(sidecar)
    return {
        "slug": slug,
        "date": sidecar["week_ending"],
        "issue": assigned_number(sidecar),
        "title": sidecar["title"],
        "dek": sidecar["dek"],
        "articles": None,
        "flagged": None,
        "label": (sidecar.get("edition_type") or "").strip(),
        "url": brief_route(slug),
        "rendered_locally": True,
        "cover": None,
        "synthetic": bool(sidecar.get("synthetic")),
        "desks": list(sidecar["desks"]),
        "approved_on": sidecar["approval"]["approved_on"],
        "author_name": identity["author_name"],
        "publication": identity["publication"],
        "publication_home_label": identity["publication_home_label"],
        "series_name": identity["series_name"],
        "era": identity["era"],
        "publication_timing": identity["publication_timing"],
        "is_retrospective": identity["is_retrospective"],
        "retrospective_label": identity["retrospective_label"],
    }


def provenance(entry: Mapping) -> str:
    """
    Where an issue was published, from the identity the entry resolved to. An
    existing issue says what it was published as, and by whom; a brief says it
    is one. Nothing here claims an approval the record does not hold.
    """
    if entry.get("series_name") == COLLECTION_NAME:
        text = "Published as an %s brief" % COLLECTION_NAME.replace(
            " Briefs", "")
    else:
        text = "Published as %s %s %s" % (
            entry.get("series_name"),
            "under" if entry.get("era") == ERA_HISTORICAL else "by",
            entry.get("publication"))
    if entry.get("is_retrospective"):
        text += " · " + entry["retrospective_label"]
    return text


@dataclass(frozen=True)
class Collection:
    """`rows` newest number first; `briefs` the brief entries; `withheld` drafts."""
    rows: tuple
    briefs: tuple
    withheld: tuple
    sidecars: dict

    @property
    def lead(self):
        """The newest issue. With no brief, exactly the site's current lead."""
        return self.rows[0]["entry"] if self.rows else None


def load_collection(editions: list, registry, *,
                    briefs_dir: Optional[Path] = None,
                    allow_synthetic: bool = False,
                    unreconciled=UNRECONCILED_ISSUES) -> Collection:
    """
    The existing issues plus every published brief, one list.

    `editions` is `load_editions()`'s list and is not modified: the historical
    rows hold those same dict objects, in the order given.
    """
    published, withheld = load_briefs(
        briefs_dir, registry,
        historical_numbers=[e["issue"] for e in editions
                            if isinstance(e.get("issue"), int)],
        allow_synthetic=allow_synthetic, unreconciled=unreconciled)
    try:
        briefs = [brief_entry(slug, sc) for slug, sc in published]
    except IdentityError as exc:
        raise CollectionError([str(exc)])
    briefs.sort(key=lambda e: -(e.get("issue") or 0))
    # Briefs come first because every brief is numbered after every existing
    # issue; the existing issues keep exactly the order the site already has.
    rows = ([{"entry": e, "kind": "brief", "provenance": provenance(e)}
             for e in briefs]
            + [{"entry": e, "kind": "issue", "provenance": provenance(e)}
               for e in editions])
    return Collection(rows=tuple(rows), briefs=tuple(briefs),
                      withheld=tuple(withheld),
                      sidecars={slug: sc for slug, sc in published})


# ── Signal Veil ───────────────────────────────────────────────────────────────

def source_image_name(slug: str) -> str:
    return "%s-source-image.json" % slug


def veil_name(slug: str) -> str:
    return "%s-veil.jpg" % slug


def brief_veil(slug: str, sidecar: Mapping, media_dir: Optional[Path]):
    """
    A brief's Signal Veil: the photograph published inside one of the brief's
    own cited source articles, as a duotone derivative.

    The same rule the existing issues follow (`scripts/pw_env.py`
    `source_veil_for_edition`, tightened in PR #70): fetch metadata, a local
    derivative, and an exact article-URL match into this brief's own source
    trail. A file in the media directory is not provenance on its own. Any miss
    returns None, which leaves the designed text-led hero.
    """
    if not media_dir:
        return None
    media_dir = Path(media_dir)
    meta_path = media_dir / source_image_name(slug)
    derivative = media_dir / veil_name(slug)
    if not meta_path.is_file() or not derivative.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(meta, dict):
        return None
    article_url = str(meta.get("article_url") or "").strip()
    if not article_url:
        return None
    hit = next((e for e in sidecar.get("source_trail") or []
                if isinstance(e, dict)
                and _norm_url(e.get("url")) == _norm_url(article_url)), None)
    if hit is None:
        return None

    title = (hit.get("title") or hit.get("title_original") or "").strip()
    subject = title if len(title) <= 64 else title[:63].rstrip() + "…"
    source = (hit.get("source") or "").strip() or \
        _norm_url(article_url).split("/")[0]
    alt = ("Photograph published with the cited source article “%s”, "
           "rendered as a duotone background." % title if title else
           "Photograph from one of this brief's cited source articles, "
           "rendered as a duotone background.")
    return {
        "id": "brief-%s" % slug,
        "file": derivative,
        "route": "%s/%s" % (MEDIA_DIRNAME, veil_name(slug)),
        "alt": alt,
        # Centre-weighted, as for the existing issues: the mask fades rather
        # than crops, and an off-centre focus on an uncurated news photograph
        # risks a misleading crop.
        "mask_focus": "50% 42%",
        "source": source,
        "subject": subject,
        "record_id": hit.get("record_id"),
        "anchor": ("r-%d" % hit["record_id"]
                   if isinstance(hit.get("record_id"), int) else ""),
        "source_page": hit.get("url") or article_url,
        "credit": str(meta.get("note") or "").strip(),
    }


# ── One brief, ready to render ────────────────────────────────────────────────

def brief_view(slug: str, sidecar: Mapping, *, desk_names: Mapping,
               state_labels: Mapping, state_order, language_label,
               veil=None) -> dict:
    """
    Everything a brief's page displays, derived from the sidecar. Text is
    passed through as written; what is absent is absent.
    """
    def name(desk):
        return desk_names.get(desk) or desk

    trail = {}
    for e in sidecar["source_trail"]:
        original = (e.get("title_original") or "").strip()
        english = (e.get("title") or "").strip()
        lang = (e.get("lang") or "").strip()
        display = english or original
        trail[e["record_id"]] = {
            "record_id": e["record_id"],
            "anchor": "r-%d" % e["record_id"],
            "desk": e["desk"],
            "desk_name": name(e["desk"]),
            "source": e.get("source") or e.get("source_id") or "",
            "lang": lang,
            "lang_label": language_label(lang),
            "display_title": display,
            # The language of the text shown, from the record's own tag and
            # never from a key name: the China Desk stores English titles from
            # its two English-language sources too (DECISION_LOG 2026-09-23).
            "display_lang": lang if display == original else "en",
            "original": original if original and original != display else "",
            "url": e["url"],
            "date": e.get("date") or "",
            "screening_label": state_labels.get(e.get("screening"), ""),
            # Only an analyzed record carries a model flag; elsewhere it is
            # None and says nothing.
            "model_flagged": e.get("is_significant") is True,
        }

    def cite(ids):
        return [trail[i] for i in ids or [] if i in trail]

    def section(field_name, anchor, heading):
        paras = paragraphs(sidecar.get(field_name))
        return ({"id": anchor, "heading": heading, "paragraphs": paras}
                if paras else None)

    development = sidecar.get("development") or {}
    coverage = sidecar.get("coverage_by_desk") or {}
    term = None
    if (sidecar.get("term_to_know_term") or "").strip():
        term = {"term": sidecar["term_to_know_term"].strip(),
                "lang": (sidecar.get("term_to_know_lang") or "").strip(),
                "paragraphs": paragraphs(sidecar.get("term_to_know_explanation"))}

    identity = resolve_identity(sidecar)
    # The identity default links are written for a page two levels down; a
    # brief sits one level down, at `briefs/<slug>.html`. Stored links win.
    links = dict(identity["author_links"])
    if not sidecar.get("author_links"):
        links[identity["publication_home_label"]] = "../index.html"

    claims = [{
        "paragraphs": paragraphs(c.get("claim")),
        "desks": [name(d) for d in c.get("desks") or []],
        "basis": c.get("basis"),
        "basis_label": BASIS_LABELS.get(c.get("basis"), ""),
        "citations": cite(c.get("citations")),
        "stated_in": cite(c.get("stated_in")),
    } for c in sidecar.get("cross_desk_claims") or []]

    return {
        "slug": slug,
        "route": brief_route(slug),
        "synthetic": bool(sidecar.get("synthetic")),
        "title": sidecar["title"],
        "dek": sidecar["dek"],
        "signal": (sidecar.get("signal") or "").strip(),
        "number": assigned_number(sidecar),
        "week_start": sidecar["week_start"],
        "week_ending": sidecar["week_ending"],
        "edition_type": (sidecar.get("edition_type") or "").strip(),
        "is_retrospective": identity["is_retrospective"],
        "timing_label": identity["retrospective_label"],
        "series_name": identity["series_name"],
        "publication": identity["publication"],
        "desks": [{"slug": d, "name": name(d)} for d in sidecar["desks"]],
        "single_desk_exception": sidecar.get("single_desk_exception"),
        "approval": sidecar["approval"],
        "development": {"paragraphs": paragraphs(development.get("summary")),
                        "citations": cite(development.get("citations"))},
        "claims": claims,
        "sections_before": [s for s in (section(*f) for f in SECTIONS_BEFORE)
                            if s],
        "sections_after": [s for s in (section(*f) for f in SECTIONS_AFTER)
                           if s],
        "term": term,
        "watching": section(*WATCHING),
        "coverage": [{
            "desk": d, "name": name(d),
            "records": coverage[d].get("records"),
            "model_flagged": coverage[d].get("model_flagged"),
            "days": coverage[d].get("days_with_records"),
            "sources": coverage[d].get("sources") or [],
            "languages": [language_label(t)
                          for t in coverage[d].get("languages") or []],
            "screening": [(state_labels[c], coverage[d]["by_screening"][c])
                          for c in state_order
                          if c in (coverage[d].get("by_screening") or {})],
        } for d in sidecar["desks"] if isinstance(coverage.get(d), dict)],
        "trail_groups": [{
            "desk": d, "name": name(d),
            "entries": [t for t in trail.values() if t["desk"] == d],
        } for d in sidecar["desks"]],
        "trail_count": len(trail),
        "author_name": identity["author_name"],
        "author_title": identity["author_title"],
        "author_bio": identity["author_bio"],
        "author_links": links,
        "publication_home_label": identity["publication_home_label"],
        "veil": veil,
    }


def brief_citation(view: Mapping, *, origin: str = "") -> str:
    """The citation a brief is cited by, from its own recorded values."""
    number = (" No. %d" % view["number"]) if view.get("number") else ""
    where = ("%s/%s" % (origin, view["route"])) if origin else view["route"]
    return "%s, “%s,” %s%s, %s, week ending %s. %s" % (
        view["author_name"], view["title"], view["series_name"], number,
        view["publication"], view["week_ending"], where)


# ── Feed ──────────────────────────────────────────────────────────────────────

def build_briefs_feed(briefs: Iterable[Mapping], *, origin: str) -> str:
    """
    Atom feed of the briefs, newest number first. Deterministic: every
    timestamp comes from a sidecar, never the clock.

    Briefs only. The existing issues are in `the-pla-watch/feed.xml` under the
    entry IDs they were published with, and that feed is neither read nor
    restated here: carrying them again would put each one in front of a reader
    subscribed to both feeds twice. A brief's ID is its own address.
    """
    briefs = sorted(briefs, key=lambda b: -(b.get("issue") or 0))
    if not briefs:
        raise CollectionError(["a feed of briefs needs at least one brief"])
    stamps = ["%sT00:00:00Z" % b["approved_on"] for b in briefs]
    feed_url = "%s/%s" % (origin, FEED_ROUTE)
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        "  <title>%s</title>" % xml_escape(COLLECTION_NAME),
        '  <link href="%s" rel="self" type="application/atom+xml"/>'
        % xml_escape(feed_url),
        '  <link href="%s/%s" rel="alternate" type="text/html"/>'
        % (xml_escape(origin), LANDING_ROUTE),
        "  <id>%s</id>" % xml_escape(feed_url),
        "  <updated>%s</updated>" % max(stamps),
    ]
    for b, stamp in zip(briefs, stamps):
        url = xml_escape("%s/%s" % (origin, b["url"]))
        lines += [
            "  <entry>",
            "    <title>%s</title>" % xml_escape(b["title"]),
            '    <link href="%s" rel="alternate" type="text/html"/>' % url,
            "    <id>%s</id>" % url,
            "    <updated>%s</updated>" % stamp,
            "    <published>%s</published>" % stamp,
            "    <author><name>%s</name></author>" % xml_escape(b["author_name"]),
        ]
        if (b.get("dek") or "").strip():
            lines.append("    <summary>%s</summary>"
                         % xml_escape(b["dek"].strip()))
        lines.append("  </entry>")
    lines.append("</feed>")
    return "\n".join(lines) + "\n"
