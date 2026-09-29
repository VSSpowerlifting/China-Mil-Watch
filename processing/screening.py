"""
Desk-scoped relevance screening.

Both screening stages were written for the China Desk: the keyword pre-filter
matches PLA vocabulary (and the US spelling "defense", which a Singapore
release never uses), and the model prompt asks whether a Chinese-language
article covers Chinese military organisations. Applied to Singapore MINDEF
releases they reject by construction — 13 of 14 Singapore records screened by
2026-09-28 were rejected by the model as "not Chinese military", and the 14th
failed the keyword stage.

A `ScreeningProfile` says, per desk, how each stage judges a record:

  * `keyword_prefilter` — True: the shared China keyword lists
    (processing.relevance.passes_keyword_filter). False: the source itself is
    the desk's declared scope, so every record from it goes on to the model
    stage. Nearly every MINDEF release names "MINDEF" or "Minister for
    Defence", so a keyword list there would filter nothing.
  * `build_messages` / `system_prompt` — the model prompt for the desk.
    `system_prompt` is None for the Analyzer's existing system prompt. A desk
    prompt is built on first use from the desk's scope in desks/registry.json,
    so routing and the daily-queue gate never read that file.
  * `daily_queue` — whether pipeline.py sends the desk's records to the model
    at all. The daily analysis that follows a pass (translation from Chinese,
    a summary, the PLA category taxonomy) exists only for the China Desk, so a
    desk without that is held out of the daily queue: its records stay
    `passed_relevance IS NULL` ("awaiting screening"). Screening such a desk is
    a deliberate, reviewed operation (scripts/rescreen_desk.py), not a
    side effect of the next scheduled run.

A record whose desk is unknown gets the China profile, which is exactly what
every record got before this module existed.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Dict, List, Optional

from analysis.prompts import (
    PROMPT_VERSION,
    SINGAPORE_RELEVANCE_PROMPT_VERSION,
    build_relevance_messages,
    build_singapore_relevance_messages,
    build_singapore_system_prompt,
)

DEFAULT_DESK = "china"


def _declared_scope(desk_id: str) -> str:
    from core.desk_registry import get_desk_registry
    entry = get_desk_registry().get(desk_id)
    if entry is None or not entry.scope:
        raise LookupError("desks/registry.json declares no scope for %r" % desk_id)
    return entry.scope


@dataclass(frozen=True)
class ScreeningProfile:
    desk_id: str
    keyword_prefilter: bool
    daily_queue: bool
    build_messages: Callable[[str, str], List[dict]]
    prompt_version: str
    build_system_prompt: Optional[Callable[[str], str]] = None

    @property
    def system_prompt(self) -> Optional[str]:
        if self.build_system_prompt is None:
            return None
        return self.build_system_prompt(_declared_scope(self.desk_id))


CHINA_PROFILE = ScreeningProfile(
    desk_id="china",
    keyword_prefilter=True,
    daily_queue=True,
    build_messages=build_relevance_messages,
    prompt_version=PROMPT_VERSION,
)

SINGAPORE_PROFILE = ScreeningProfile(
    desk_id="singapore",
    keyword_prefilter=False,
    daily_queue=False,
    build_messages=build_singapore_relevance_messages,
    prompt_version=SINGAPORE_RELEVANCE_PROMPT_VERSION,
    build_system_prompt=build_singapore_system_prompt,
)

_PROFILES: Dict[str, ScreeningProfile] = {
    "china": CHINA_PROFILE,
    "singapore": SINGAPORE_PROFILE,
}


def profile_for_desk(desk_id: Optional[str]) -> ScreeningProfile:
    """The desk's profile; the China profile for an unknown or missing desk."""
    return _PROFILES.get(desk_id or DEFAULT_DESK, CHINA_PROFILE)


@lru_cache(maxsize=1)
def _desk_by_source() -> Dict[str, str]:
    from core.manifests import load_all_desks
    return {src.slug: desk_id
            for desk_id, desk in load_all_desks().items()
            for src in desk.sources}


def desk_for_source(source_slug: Optional[str]) -> Optional[str]:
    """The desk a source belongs to, from desks/*/manifest.json."""
    if not source_slug:
        return None
    return _desk_by_source().get(source_slug)


def profile_for_source(source_slug: Optional[str]) -> ScreeningProfile:
    return profile_for_desk(desk_for_source(source_slug))
