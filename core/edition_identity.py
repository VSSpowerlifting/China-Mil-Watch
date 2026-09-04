"""
Which publication published a given edition of The PLA Watch.

Why this module exists
----------------------
The project was renamed on 2026-08-27: *China Mil Watch* became *Indo-Pacific
Record* (`README.md`, `DECISION_LOG.md`). The series name, *The PLA Watch*, did
not change and is unaffected by any of this.

Editions 1–13 were published under the predecessor name. They keep it. An
edition is a dated artifact of record: re-rendering one must reproduce the page
that was published, not restate it under whatever the project is called today.
Edition 14 onward are published by Indo-Pacific Record.

The hazard this closes
----------------------
Before this module, an edition's author identity came from module constants in
`scripts/generate_pla_watch.py`, with stored sidecar values taking precedence
only when present:

    "author_title": meta.get("author_title", AUTHOR_TITLE)

Editions 3–13 store those fields, so they were safe. **Editions 1 and 2 store
none of them.** They rendered the historical identity only because the constants
still happened to be stale — the moment those constants were corrected to the
current identity, editions 1 and 2 would have silently rebranded, with no test
failing. Correctness by coincidence is not correctness. Here the era decides,
and the constants cannot reach across the boundary.

The boundary is the issue number, not the covered week
------------------------------------------------------
`LAST_HISTORICAL_ISSUE = 13` is the whole rule, and the reason it is not a date
comparison matters. Edition 14 covers the week ending 2026-08-15, which *precedes*
the 2026-08-27 rename — but it is published now, by Indo-Pacific Record. The
parent publication of an edition is the one that publishes it, not the one that
existed during the week it describes. A retrospective edition is exactly the case
where those two diverge, so a `week_ending < RENAME_DATE` test would get it
backwards and put No. 14 under the retired name.

`RENAME_DATE` is retained only as a documented fallback for a sidecar carrying
no issue number at all, which no edition in this repository does.

Resolution order
----------------
  1. an explicit `publication` recorded in the sidecar always wins — new
     sidecars record it, so a page can be reproduced without inferring anything;
  2. otherwise `issue_number` decides against `LAST_HISTORICAL_ISSUE`;
  3. otherwise the edition date decides against `RENAME_DATE`;
  4. otherwise it is treated as current, because an edition with no date, no
     number and no recorded publication is a new one being built.

Stored author fields still win over era defaults. The era supplies the default
only when the sidecar is silent — which is what makes editions 1 and 2 correct
by rule instead of by accident.

What this module does *not* decide
----------------------------------
The current site chrome — the series landing page, the archive, the terms page,
navigation, and site-level metadata — is Indo-Pacific Record, always, even
though the archive it lists contains historical editions. That is a property of
the site, not of any edition, so it is not resolved per edition here.
"""

from __future__ import annotations

from datetime import date

#: The last edition published under the predecessor name. Editions at or below
#: this number are historical; 14 and above are Indo-Pacific Record. See the
#: module docstring for why this is a number and not a date.
LAST_HISTORICAL_ISSUE = 13

#: Documented fallback only, for a sidecar with no issue number. The rename
#: date from README.md and DECISION_LOG.md.
RENAME_DATE = date(2026, 8, 27)

#: The series. Unchanged by the rename, and not era-dependent.
SERIES_NAME = "The PLA Watch"

ERA_HISTORICAL = "historical"
ERA_CURRENT = "current"

#: Publication timing. `regular` is an edition published in its own week;
#: `retrospective` is one prepared after the fact for an earlier week. This is
#: deliberately independent of `edition_type` (`significant` / `routine`), which
#: describes what the week contained, not when the edition was written.
TIMING_REGULAR = "regular"
TIMING_RETROSPECTIVE = "retrospective"
TIMINGS = (TIMING_REGULAR, TIMING_RETROSPECTIVE)

#: Shown on a retrospective edition. Restrained on purpose: it is a fact about
#: the edition, not a disclaimer.
RETROSPECTIVE_LABEL = "Retrospective edition"


class IdentityError(ValueError):
    """A sidecar field that cannot be trusted to name an identity. Fatal."""


_HISTORICAL = {
    "era": ERA_HISTORICAL,
    "publication": "China Mil Watch",
    "publication_home_label": "China Mil Watch",
    "author_title": "Principal Analyst, China Mil Watch",
    "author_bio": (
        "Benjamin Yang is the principal analyst at China Mil Watch and an "
        "incoming International Affairs student at George Washington "
        "University’s Elliott School, focused on U.S.-China relations, "
        "public diplomacy, and security affairs."
    ),
}

#: Current author identity, derived from the About page rather than invented:
#: "Benjamin Yang — Creator and Editor", "studies International Affairs at
#: George Washington University's Elliott School, with interests in U.S.–China
#: relations, public diplomacy, and security affairs. He writes The PLA Watch
#: and maintains the project's collection pipeline." Note "studies", not
#: "incoming" — that wording is retired and survives only in historical editions.
_CURRENT = {
    "era": ERA_CURRENT,
    "publication": "Indo-Pacific Record",
    "publication_home_label": "Indo-Pacific Record",
    "author_title": "Creator and Editor, Indo-Pacific Record",
    "author_bio": (
        "Benjamin Yang is the creator and editor of Indo-Pacific Record. He "
        "studies International Affairs at George Washington University’s "
        "Elliott School, with interests in U.S.–China relations, public "
        "diplomacy, and security affairs. He writes The PLA Watch and "
        "maintains the project’s collection pipeline."
    ),
}

AUTHOR_NAME = "Benjamin Yang"

#: Contact links are identity-stable; only the parent-publication link differs.
_BASE_LINKS = (
    ("LinkedIn", "https://www.linkedin.com/in/benjamin-yang-42b525294"),
    ("Email", "mailto:ben.yang@gwmail.gwu.edu"),
)


def _as_date(value):
    if isinstance(value, date):
        return value
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_timing(value) -> str:
    """
    Validate `publication_timing`. Absent means `regular`: every historical
    sidecar predates the field and must keep loading unchanged.
    """
    if value is None:
        return TIMING_REGULAR
    text = str(value).strip()
    if not text:
        return TIMING_REGULAR
    if text not in TIMINGS:
        raise IdentityError(
            "publication_timing must be one of %s, got %r"
            % (", ".join(repr(t) for t in TIMINGS), value))
    return text


def era_for(sidecar: dict) -> str:
    """The era a sidecar belongs to. See the module docstring for the order."""
    explicit = (sidecar.get("publication") or "").strip()
    if explicit:
        if explicit == _CURRENT["publication"]:
            return ERA_CURRENT
        if explicit == _HISTORICAL["publication"]:
            return ERA_HISTORICAL
        raise IdentityError(
            "publication must be %r or %r, got %r. A new publication name is a "
            "decision to record here, not to infer from a sidecar."
            % (_CURRENT["publication"], _HISTORICAL["publication"], explicit))

    issue = sidecar.get("issue_number")
    if isinstance(issue, int) or (isinstance(issue, str) and issue.strip().isdigit()):
        return (ERA_HISTORICAL if int(issue) <= LAST_HISTORICAL_ISSUE
                else ERA_CURRENT)

    when = _as_date(sidecar.get("date") or sidecar.get("week_ending"))
    if when is not None:
        return ERA_HISTORICAL if when < RENAME_DATE else ERA_CURRENT

    return ERA_CURRENT


def resolve_identity(sidecar: dict) -> dict:
    """
    The publication identity for one edition.

    Stored author fields win; the era supplies defaults only where the sidecar
    is silent. `pw_root` is the relative path from a post page to the parent
    site root, matching the existing template convention.
    """
    sidecar = sidecar or {}
    era = era_for(sidecar)
    profile = _HISTORICAL if era == ERA_HISTORICAL else _CURRENT
    timing = parse_timing(sidecar.get("publication_timing"))

    links = dict(sidecar.get("author_links") or ())
    if not links:
        links = dict(_BASE_LINKS)
        links[profile["publication_home_label"]] = "../../index.html"

    return {
        "era": era,
        "publication": profile["publication"],
        "publication_home_label": profile["publication_home_label"],
        "series_name": SERIES_NAME,
        "publication_timing": timing,
        "is_retrospective": timing == TIMING_RETROSPECTIVE,
        "retrospective_label": (RETROSPECTIVE_LABEL
                                if timing == TIMING_RETROSPECTIVE else ""),
        "author_name": sidecar.get("author_name") or AUTHOR_NAME,
        "author_title": sidecar.get("author_title") or profile["author_title"],
        "author_bio": sidecar.get("author_bio") or profile["author_bio"],
        "author_links": links,
    }


def current_identity_fields(timing: str = TIMING_REGULAR) -> dict:
    """
    The identity fields a newly generated sidecar records explicitly, so its
    page can be reproduced without inferring an era.
    """
    timing = parse_timing(timing)
    links = dict(_BASE_LINKS)
    links[_CURRENT["publication_home_label"]] = "../../index.html"
    return {
        "publication": _CURRENT["publication"],
        "publication_timing": timing,
        "author_name": AUTHOR_NAME,
        "author_title": _CURRENT["author_title"],
        "author_bio": _CURRENT["author_bio"],
        "author_links": links,
    }
