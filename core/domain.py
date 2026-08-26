"""
Country-neutral domain vocabulary.

This module is deliberately free of China-specific knowledge: no source slugs,
no outlet names, no Chinese-language terms, no topical categories. Everything
country-specific lives in `desks/<desk_id>/manifest.json` and its taxonomy.

Python 3.9 compatible (the CI runner pins 3.9): no PEP 604 unions (`X | None`),
no `match`. `Optional[...]` and `List[...]` throughout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# ── Controlled vocabularies ───────────────────────────────────────────────────
#
# These are sets rather than Enums so that manifest validation can report the
# offending value verbatim and list the permitted ones. An Enum would raise a
# ValueError whose message is less useful to whoever is editing the manifest.

#: How a desk is exposed publicly. `legacy` is the existing China product,
#: which is already published under its own brand; `shadow` is private
#: collection with no public surface (the Russia pilot's state); `paused`
#: stops collection without deleting configuration.
PUBLIC_STATUSES = ("legacy", "shadow", "public", "paused")

#: How a desk is presented publicly, and what it is allowed to claim.
#: Distinct from `PUBLIC_STATUSES`, which describes how a *collecting* desk is
#: exposed. These describe where a desk is in its life, including the states a
#: desk can occupy before it collects anything at all, and are the only values
#: `desks/registry.json` may use.
#:
#: `access_blocked` is deliberately separate from `paused`: paused is our
#: decision, access_blocked is the institution's publication surface refusing
#: discovery to an honestly identified collector. Collapsing them would let a
#: refusal we did not choose read as a choice we made.
DESK_STATUSES = (
    "planned",
    "research",
    "shadow",
    "live",
    "paused",
    "access_blocked",
)

#: The one status that means records reach the public corpus. Everything else
#: renders as an absence with an explanation, never as a small number.
COLLECTING_DESK_STATUSES = ("live",)

DESK_STATUS_LABELS = {
    "planned": "Planned — nothing collected",
    "research": "Researched — not yet collecting",
    "shadow": "Shadow evaluation — not public",
    "live": "Live — collecting",
    "paused": "Paused — collection stopped",
    "access_blocked": "Access blocked — not collecting",
}

#: Proximity to an institution's authorized public position.
#: **Not** a truth, reliability, accuracy, or moral score. A Tier A document is
#: not more likely to be true than a Tier D one; it is more likely to represent
#: what the institution has formally decided to say.
AUTHORITY_TIERS = ("A", "B", "C", "D")

AUTHORITY_TIER_DEFINITIONS = {
    "A": "National leader, central military command, ministry, formal "
         "directive, law, or authoritative doctrine.",
    "B": "Official armed-force or service media, official spokesperson, or "
         "institutional public-affairs channel.",
    "C": "Official state news agency.",
    "D": "State-linked or semi-official outlet.",
}

#: How the pipeline reaches a source.
ACCESS_METHODS = ("html", "rss", "api", "telegram", "manual")

#: Whether a source originates material or carries someone else's.
#: Used to keep syndicated copies from inflating message-volume counts.
ORIGINALITY = ("original", "mirror", "syndicated", "unknown")

#: Universal, cross-desk document genre. Kept small on purpose: it must mean
#: the same thing for a PLA Daily feature and a US DoD transcript. Desk-specific
#: topical labels (Taiwan, South China Sea, …) live in the desk taxonomy and are
#: never promoted into this list.
GENRES = (
    "directive_law",
    "speech_transcript",
    "official_statement",
    "exercise_operational_report",
    "procurement_industry",
    "doctrinal_essay",
    "commentary_editorial",
    "routine_unit_news",
    "feature_human_interest",
    "unknown",
)

#: What kind of body publishes a source.
INSTITUTION_TYPES = (
    "head_of_state",
    "defense_ministry",
    "armed_forces",
    "service_branch",
    "security_council",
    "state_news_agency",
    "state_linked_media",
    "other",
)

#: Calendars a desk may date against. `gregorian` covers every current desk;
#: the field exists so a future desk using another calendar cannot be silently
#: misdated by code that assumes Gregorian arithmetic.
CALENDARS = ("gregorian", "hijri", "solar_hijri")

#: What kind of evidence a claim rests on. Central to the editorial rule that
#: official messaging is not policy, doctrine, capability, or behavior.
EVIDENCE_DOMAINS = ("messaging", "policy", "doctrine", "capability", "behavior")


# ── Entities ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Desk:
    """A country/jurisdiction desk. One desk owns many institutions."""

    desk_id: str
    display_name: str
    jurisdiction_code: str          # ISO 3166-1 alpha-2, or 'XX' for reference desks
    default_timezone: str           # IANA tz name, e.g. 'Asia/Shanghai'
    supported_language_tags: List[str]   # BCP 47, e.g. ['zh-Hans', 'en']
    public_status: str
    default_calendar: str = "gregorian"
    active: bool = True

    @property
    def is_collecting(self) -> bool:
        """True when the desk should be collected from at all."""
        return self.active and self.public_status != "paused"


@dataclass(frozen=True)
class Institution:
    """A publishing body. Sources belong to institutions, not directly to desks."""

    institution_id: str
    desk_id: str
    display_name: str
    institution_type: str
    name_original: Optional[str] = None
    parent_institution_id: Optional[str] = None
    active_from: Optional[str] = None
    active_to: Optional[str] = None


@dataclass(frozen=True)
class Source:
    """
    One collectable publication surface.

    `slug` is the stable identifier and is deliberately the same string the
    legacy `sources.slug` column already holds, so existing rows, existing
    article joins and existing published URLs keep working untouched.
    """

    slug: str
    desk_id: str
    institution_id: str
    display_name: str
    base_url: str
    language_tag: str               # BCP 47
    timezone: str
    access_method: str
    authority_tier: str
    source_type: str
    originality: str
    calendar: str = "gregorian"
    expected_cadence_days: Optional[float] = None
    #: How long this source may be silent before the health report escalates.
    #: Set from the SOURCE's own publishing rate, never from our collection —
    #: our collection is the thing under test.
    silence_threshold_days: Optional[int] = None
    #: Dotted path to the adapter that collects this source, e.g.
    #: "scraper.sources.pla_daily:PLADailyScraper". Configuration, not a core
    #: import: this is what keeps the neutral pipeline from naming any
    #: country-specific class.
    adapter: Optional[str] = None
    enabled: bool = True
    active_from: Optional[str] = None
    active_to: Optional[str] = None
    listing_endpoints: List[str] = field(default_factory=list)
    article_url_patterns: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    @property
    def is_original(self) -> bool:
        return self.originality == "original"


@dataclass(frozen=True)
class DeskConfig:
    """A desk plus everything it owns, as loaded from one manifest."""

    desk: Desk
    institutions: List[Institution]
    sources: List[Source]

    def source_by_slug(self, slug: str) -> Optional[Source]:
        for src in self.sources:
            if src.slug == slug:
                return src
        return None

    @property
    def enabled_sources(self) -> List[Source]:
        return [s for s in self.sources if s.enabled]
