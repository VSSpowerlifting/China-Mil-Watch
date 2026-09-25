"""
Which publication published a given issue: an edition of The PLA Watch, or an
Indo-Pacific Record Brief.

Why this module exists
----------------------
The project was renamed on 2026-08-27: *China Mil Watch* became *Indo-Pacific
Record* (`README.md`, `DECISION_LOG.md`). The series name, *The PLA Watch*, did
not change with the rename; since 2026-09-23 it is closed to new issues (below).

Editions 1–13 were published under the predecessor name. They keep it. An
edition is a dated artifact of record: re-rendering one must reproduce the page
that was published, not restate it under whatever the project is called today.
No. 14 resolves to Indo-Pacific Record, and so does every brief.

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
no issue number at all, which no edition in this repository does. It never
applies to a brief: an unnumbered brief draft is current whatever week it
covers.

Resolution order
----------------
  0. a brief (`is_brief()`) is always current, and may name no other
     publication;
  1. an explicit `publication` recorded in the sidecar always wins — new
     sidecars record it, so a page can be reproduced without inferring anything;
  2. otherwise `issue_number` decides against `LAST_HISTORICAL_ISSUE`;
  3. otherwise the edition date decides against `RENAME_DATE`;
  4. otherwise it is treated as current, because an edition with no date, no
     number and no recorded publication is a new one being built.

Stored author fields still win over era defaults. The era supplies the default
only when the sidecar is silent — which is what makes editions 1 and 2 correct
by rule instead of by accident. A brief's stored author fields may not present
The PLA Watch or China Mil Watch as a current role
(`_predecessor_role_problems`); an existing issue's are never checked.

The collection, and why membership is not attribution
------------------------------------------------------
Since 2026-09-23 (`DECISION_LOG.md`) every issue belongs to one continuing
collection, *Indo-Pacific Record Briefs*: the existing issues and every issue
published from now on. The existing issues stay *published as* The PLA Watch —
their titles, pages, feed entries and stored identity say so, and a collection
may display that provenance but never rewrite it. So `SERIES_NAME` keeps naming
the predecessor series, and no new issue is published under it. A brief says it
is a brief by recording `collection` explicitly; `is_brief()` refuses a sidecar
that looks like a brief without saying so, and any issue after
`LAST_PREDECESSOR_ISSUE` that names no collection, rather than reading either
as The PLA Watch.

What this module does *not* decide
----------------------------------
The current site chrome — the series landing page, the archive, the terms page,
navigation, and site-level metadata — is Indo-Pacific Record, always, even
though the archive it lists contains historical editions. That is a property of
the site, not of any edition, so it is not resolved per edition here. Nor does
it decide whether a brief satisfies its editorial contract or which number it
takes: that is `core.brief_contract`.
"""

from __future__ import annotations

import re
from datetime import date

#: The last edition published under the predecessor name. Editions at or below
#: this number are historical; 14 and above are Indo-Pacific Record. See the
#: module docstring for why this is a number and not a date.
LAST_HISTORICAL_ISSUE = 13

#: Documented fallback only, for a sidecar with no issue number. The rename
#: date from README.md and DECISION_LOG.md.
RENAME_DATE = date(2026, 8, 27)

#: The predecessor series. Every existing issue was published in it and keeps
#: it. Unchanged by the rename, and not era-dependent. Since 2026-09-23 it is
#: attribution only: no new issue is authored or published under it. The
#: constant keeps its name because it names what those issues were published
#: as; renaming it would invite exactly the silent re-attribution this module
#: exists to prevent.
SERIES_NAME = "The PLA Watch"

#: The continuing collection. It includes every existing issue and every issue
#: published from now on. Membership is not attribution: an existing issue is in
#: the collection and is still published as The PLA Watch.
COLLECTION_NAME = "Indo-Pacific Record Briefs"

#: No issue numbered above this is published as The PLA Watch; every existing
#: sidecar is at or below it. This records that the predecessor series is
#: closed. It does not say No. 14 is published — its status is unreconciled,
#: see `core.brief_contract.UNRECONCILED_ISSUES` — and it does not decide the
#: next number.
LAST_PREDECESSOR_ISSUE = 14

#: Fields only a brief carries. A sidecar holding any of them without naming
#: its collection is refused rather than read as The PLA Watch.
BRIEF_ONLY_FIELDS = ("brief_schema", "desks", "development",
                     "cross_desk_claims", "single_desk_exception")

#: The predecessor series and the predecessor publication, as a brief's stored
#: author fields might name them. Case- and spacing-insensitive.
PREDECESSOR_NAME_RE = re.compile(r"(?:the\s+)?PLA\s+Watch|China\s+Mil\s+Watch",
                                 re.IGNORECASE)

#: Words that mark a mention in a brief's `author_bio` as history rather than a
#: current role. One must come *before* the name in the same sentence: "He
#: previously wrote The PLA Watch" passes, "He writes The PLA Watch, formerly
#: ..." does not. Bare "was" is not one — "was X and is principal analyst at
#: China Mil Watch" would slip through.
PAST_MARKER_RE = re.compile(
    r"\b(?:formerly|previously|former|wrote|until|predecessor|originally|"
    r"published\s+as)\b", re.IGNORECASE)

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
#: relations, public diplomacy, and security affairs." Note "studies", not
#: "incoming" — that wording is retired and survives only in historical editions.
#: What he writes is Indo-Pacific Record Briefs (DECISION_LOG 2026-09-23); the
#: About page's "He writes The PLA Watch" predates that ruling and is corrected
#: with the site chrome, not here. No. 14 stores its own bio and keeps it.
_CURRENT = {
    "era": ERA_CURRENT,
    "publication": "Indo-Pacific Record",
    "publication_home_label": "Indo-Pacific Record",
    "author_title": "Creator and Editor, Indo-Pacific Record",
    "author_bio": (
        "Benjamin Yang is the creator and editor of Indo-Pacific Record. He "
        "studies International Affairs at George Washington University’s "
        "Elliott School, with interests in U.S.–China relations, public "
        "diplomacy, and security affairs. He writes Indo-Pacific Record "
        "Briefs and maintains the project’s collection pipeline."
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


def _issue_number(sidecar: dict):
    issue = sidecar.get("issue_number")
    if isinstance(issue, bool):
        return None
    if isinstance(issue, int):
        return issue
    if isinstance(issue, str) and issue.strip().isdigit():
        return int(issue)
    return None


def _predecessor_role_problems(sidecar: dict) -> list:
    """
    A brief's stored `author_title` / `author_bio` naming The PLA Watch or
    China Mil Watch as a current publication or role. Applied to briefs only:
    Nos. 3-13 store "Principal Analyst, China Mil Watch" and keep it.

    A title is a current role, so it may not name either. A bio may, but only
    as history: each sentence mentioning one must put a past marker
    (`PAST_MARKER_RE`) before the name. Anything else about the author is the
    author's own wording and is not checked.
    """
    problems = []
    title = str(sidecar.get("author_title") or "")
    found = PREDECESSOR_NAME_RE.search(title)
    if found:
        problems.append(
            "a brief's author_title names %r; a title is a current role, and "
            "no current role is held at a predecessor publication" % found.group(0))
    bio = str(sidecar.get("author_bio") or "")
    for sentence in re.split(r"(?<=[.!?;])\s+", bio):
        for found in PREDECESSOR_NAME_RE.finditer(sentence):
            if not PAST_MARKER_RE.search(sentence[:found.start()]):
                problems.append(
                    "a brief's author_bio presents %r as current in %r; mark "
                    "it as history (e.g. 'previously', 'formerly') before the "
                    "name" % (found.group(0), sentence.strip()))
    return problems


def is_brief(sidecar: dict) -> bool:
    """
    Whether a sidecar is an Indo-Pacific Record Brief rather than an issue
    published as The PLA Watch.

    An explicit `collection` decides, and only the collection's own name is
    accepted: nothing new may declare itself The PLA Watch. Absent means an
    issue published as The PLA Watch, because every sidecar written before the
    collection existed lacks the field — but only up to
    `LAST_PREDECESSOR_ISSUE`, and never for a sidecar carrying brief-only
    fields. Those two cases are refused rather than guessed.

    A brief is published by Indo-Pacific Record, whatever week it covers, so a
    brief naming any other `publication` — the retired China Mil Watch
    included — is refused here, where the contract check and the resolver both
    meet it. So is a brief whose stored author fields present either
    predecessor name as a current role (`_predecessor_role_problems`).
    """
    sidecar = sidecar or {}
    explicit = (sidecar.get("collection") or "").strip()
    if explicit:
        if explicit == COLLECTION_NAME:
            publication = (sidecar.get("publication") or "").strip()
            if publication and publication != _CURRENT["publication"]:
                raise IdentityError(
                    "a brief is published as %r, got publication=%r. %s is "
                    "the predecessor's name and stays on the issues published "
                    "under it." % (_CURRENT["publication"], publication,
                                   _HISTORICAL["publication"]))
            problems = _predecessor_role_problems(sidecar)
            if problems:
                raise IdentityError("; ".join(problems))
            return True
        raise IdentityError(
            "collection must be %r, got %r. No new issue is published as %s, "
            "and an existing issue records no collection at all."
            % (COLLECTION_NAME, explicit, SERIES_NAME))

    present = [f for f in BRIEF_ONLY_FIELDS if f in sidecar]
    if present:
        raise IdentityError(
            "sidecar carries brief fields (%s) but names no collection; a "
            "brief records collection=%r" % (", ".join(present), COLLECTION_NAME))

    issue = _issue_number(sidecar)
    if issue is not None and issue > LAST_PREDECESSOR_ISSUE:
        raise IdentityError(
            "issue %d names no collection, and no issue after No. %d is "
            "published as %s" % (issue, LAST_PREDECESSOR_ISSUE, SERIES_NAME))
    return False


def resolve_identity(sidecar: dict) -> dict:
    """
    The publication identity for one edition.

    Stored author fields win; the era supplies defaults only where the sidecar
    is silent. `pw_root` is the relative path from a post page to the parent
    site root, matching the existing template convention.

    `series_name` is what the issue was published as — The PLA Watch for every
    existing issue, the collection's own name for a brief. `collection` is the
    same for both: membership, not attribution.
    """
    sidecar = sidecar or {}
    brief = is_brief(sidecar)
    # Never inferred for a brief: one covering a week before RENAME_DATE that
    # records no publication would otherwise take the predecessor's identity.
    era = ERA_CURRENT if brief else era_for(sidecar)
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
        "series_name": COLLECTION_NAME if brief else SERIES_NAME,
        "collection": COLLECTION_NAME,
        "is_brief": brief,
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


def brief_identity_fields(timing: str = TIMING_REGULAR) -> dict:
    """
    The identity fields a new brief records explicitly: its collection and the
    current publication and author identity, so nothing about it is inferred
    from an absence.

    `author_links` is left out on purpose. Stored links are relative to a
    page's address, so the renderer supplies them for the address it gives
    the brief (`core.brief_collection.brief_view`, for `briefs/<slug>.html`).
    """
    fields = current_identity_fields(timing)
    del fields["author_links"]
    fields["collection"] = COLLECTION_NAME
    return fields
