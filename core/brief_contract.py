"""
The contract an Indo-Pacific Record Brief satisfies before approval, and the
rule that gives it a stable issue number.

What a brief is (DECISION_LOG 2026-09-23)
-----------------------------------------
A brief starts from one concrete Indo-Pacific development and compares how the
relevant governments or institutions officially describe or respond to it, in
the existing article anatomy. It draws evidence from at least two live desks by
default; a single-desk brief exists only as an explicitly approved exception.
No brief has to include every desk.

What this module enforces, and what it cannot
---------------------------------------------
Mechanically, here:

  * every declared desk is live with production records and contributes at
    least one source-trail entry, and every trail entry belongs to a declared
    desk;
  * two or more desks, or one desk plus a recorded exception naming who
    approved it, when, and why;
  * every trail entry keeps its record's own desk and language —
    `title_original` with `lang`, never `title_zh`, because a desk's sources are
    not all in one language (the China Desk collects two in English);
  * every cross-desk claim cites at least one trail entry from each desk it
    compares, and a claim worded as coordination names the cited record that
    states it (`basis: "stated_in_record"`, `stated_in`) — it never rests on
    similar timing;
  * a draft carries no issue number; an approved brief carries one, with its
    approval, and keeps it.

Editorially, in `EDITORIAL_QA_CHECKLIST.md`: whether the development is
concrete, whether each claim says only what its citations support, whether each
institution is described fairly. The coordination check below is a tripwire,
not a proof: passing it does not make an inference sound.

Numbering
---------
A number is assigned at approval: one more than the highest number already
assigned anywhere in the collection, never a rank by the week an issue covers.
A retrospective brief approved later takes a later number and states the week
it covers. An approved number is never reassigned. And no number is assigned
while an existing issue's publication status is unreconciled — see
`UNRECONCILED_ISSUES`.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Iterable, Mapping

from core.edition_identity import (
    COLLECTION_NAME, SERIES_NAME, IdentityError, is_brief,
)

BRIEF_SCHEMA = 1

#: Live desks a brief draws evidence from unless an exception is approved.
MIN_DESKS = 2

STATUS_DRAFT = "draft"
STATUS_APPROVED = "approved"
EDITORIAL_STATUSES = (STATUS_DRAFT, STATUS_APPROVED)

#: How a cross-desk claim is supported. `comparison` sets what two or more
#: institutions published side by side. `stated_in_record` is required for any
#: claim of coordination, and names the cited record that states it.
BASIS_COMPARISON = "comparison"
BASIS_STATED = "stated_in_record"
CLAIM_BASES = (BASIS_COMPARISON, BASIS_STATED)

#: Record processing states, using the codes the site already publishes
#: (`site/preview/generate_preview.py` PROCESSING_STATES). Carried per record,
#: never filtered on: desks do not share one pipeline.
SCREENING_ANALYZED = "analyzed"
SCREENING_NOT_SELECTED = "not_selected"
SCREENING_AWAITING = "awaiting_screening"
SCREENING_INCOMPLETE = "analysis_incomplete"

#: The standing anatomy an approved brief fills, as the existing issues do.
REQUIRED_SECTIONS = ("title", "dek", "opening_note", "what_stood_out",
                     "why_it_matters", "what_was_routine",
                     "what_im_watching_next")

#: Existing issues whose publication status the editorial record and the
#: deployed site disagree on. No. 14: DECISION_LOG 2026-09-04 and PROJECT_STATE
#: §4 record it as drafted and not published; the deployed site has served it
#: since 2026-09-05 (gh-pages 57ca945f5), linked from the series index, archive,
#: sitemap and feed, and no approval is on record. While any issue is listed
#: here the next number is not known, so none is assigned. Clearing it is the
#: owner's ruling, recorded in DECISION_LOG — never an edit made to unblock a
#: build.
UNRECONCILED_ISSUES = frozenset({14})

#: Wording that asserts coordination between institutions. A tripwire only.
_COORDINATION = re.compile(
    r"\b(coordinat\w*|concerted|in concert|in tandem|lockstep|"
    r"synchroni[sz]\w*|orchestrat\w*|choreograph\w*)\b", re.IGNORECASE)

_LANG_TAG = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{1,8})*$")

PREDECESSOR_AUTHORING_CLOSED = (
    "No new issue is authored or published as %s (DECISION_LOG 2026-09-23). "
    "Existing issues re-render from their sidecars with "
    "scripts/rerender_pla_watch.py; new issues are %s, scaffolded with "
    "scripts/author_brief.py." % (SERIES_NAME, COLLECTION_NAME))


class BriefContractError(ValueError):
    """A brief that does not satisfy the contract. Carries every problem."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


class NumberingBlocked(RuntimeError):
    """No issue number may be assigned yet."""


def refuse_predecessor_authoring():
    """Stop any path that would author a new issue as The PLA Watch."""
    raise SystemExit("REFUSED: " + PREDECESSOR_AUTHORING_CLOSED)


# ── Desks ─────────────────────────────────────────────────────────────────────

def eligible_desks(registry) -> list:
    """Desks a brief may draw evidence from: live, with production records."""
    return [d.slug for d in registry
            if d.is_collecting and d.has_production_records]


# ── Records → source trail ────────────────────────────────────────────────────

def screening_state(record) -> str:
    """A record's processing state, from its stored columns."""
    if record["analyzed_at"]:
        return SCREENING_ANALYZED
    passed = record["passed_relevance"]
    if passed is None:
        return SCREENING_AWAITING
    return SCREENING_INCOMPLETE if passed else SCREENING_NOT_SELECTED


def trail_entry(record) -> dict:
    """
    One source-trail entry from a `storage.db.get_articles_for_desks()` row.

    It keeps the record's actual desk and its source's language. The original
    title is stored verbatim under `title_original`, whatever its language, and
    `lang` says which. `title` is the stored English title: the machine
    translation where one exists, or the original itself when the source
    publishes in English. A non-English record with no stored English title
    gets an empty `title`, never a composed one. `is_significant` is the
    model-flag and exists only for an analyzed record; elsewhere it is None,
    because the stored zero means "never assessed" as often as "not flagged".
    """
    lang = record["source_language_tag"] or ""
    original = record["title_original"] or ""
    english = record["title_english"] or ""
    if not english and lang.split("-")[0] == "en":
        english = original
    state = screening_state(record)
    return {
        "record_id": record["id"],
        "desk": record["desk_id"],
        "source_id": record["source_slug"],
        "source": record["source_name"],
        "lang": lang,
        "title_original": original,
        "title": english,
        "url": record["url"],
        "date": record["published_date"],
        "screening": state,
        "is_significant": (bool(record["is_significant"])
                           if state == SCREENING_ANALYZED else None),
    }


def coverage_by_desk(records, desks=()) -> dict:
    """
    Per-desk counts for a brief's coverage snapshot, keyed by desk and never
    pooled: desks differ in volume and in how far their records have been
    screened, so a sum across them describes nothing. A declared desk with no
    record in the window appears with zero records rather than vanishing.
    `model_flagged` counts analyzed records only.
    """
    acc = {d: {"records": 0, "by_screening": {}, "model_flagged": 0,
               "sources": set(), "languages": set(), "dates": set()}
           for d in desks}
    for r in records:
        c = acc.setdefault(r["desk_id"], {
            "records": 0, "by_screening": {}, "model_flagged": 0,
            "sources": set(), "languages": set(), "dates": set()})
        state = screening_state(r)
        c["records"] += 1
        c["by_screening"][state] = c["by_screening"].get(state, 0) + 1
        if state == SCREENING_ANALYZED and r["is_significant"]:
            c["model_flagged"] += 1
        c["sources"].add(r["source_name"])
        c["languages"].add(r["source_language_tag"])
        if r["published_date"]:
            c["dates"].add(r["published_date"])
    return {
        desk: {
            "records": c["records"],
            "by_screening": dict(sorted(c["by_screening"].items())),
            "model_flagged": c["model_flagged"],
            "days_with_records": len(c["dates"]),
            "sources": sorted(c["sources"]),
            "languages": sorted(c["languages"]),
        }
        for desk, c in sorted(acc.items())
    }


# ── The contract ──────────────────────────────────────────────────────────────

def _text(value) -> str:
    return str(value or "").strip()


def _iso_date(value):
    try:
        return date.fromisoformat(_text(value))
    except ValueError:
        return None


def _exception_ok(exception) -> bool:
    return (isinstance(exception, dict)
            and bool(_text(exception.get("approved_by")))
            and bool(_text(exception.get("reason")))
            and _iso_date(exception.get("approved_on")) is not None)


def validate_brief(sidecar: Mapping, registry) -> list:
    """Every way `sidecar` breaks the brief contract. Empty means it holds."""
    try:
        if not is_brief(sidecar):
            return ["not a brief: it names no collection, so it reads as an "
                    "issue published as %s" % SERIES_NAME]
    except IdentityError as exc:
        return [str(exc)]

    problems = []
    if sidecar.get("brief_schema") != BRIEF_SCHEMA:
        problems.append("brief_schema must be %d" % BRIEF_SCHEMA)
    status = sidecar.get("editorial_status")
    if status not in EDITORIAL_STATUSES:
        problems.append("editorial_status must be one of: %s"
                        % ", ".join(EDITORIAL_STATUSES))
    approved = status == STATUS_APPROVED

    if _text(sidecar.get("title")).lower().startswith(SERIES_NAME.lower()):
        problems.append("the title begins %r; no new issue is published as %s"
                        % (SERIES_NAME, SERIES_NAME))

    # Desks, and the default of two.
    desks = sidecar.get("desks")
    if (not isinstance(desks, list) or not desks
            or not all(isinstance(d, str) and d.strip() for d in desks)):
        problems.append("desks must be a non-empty list of desk slugs")
        desks = ([d for d in desks if isinstance(d, str)]
                 if isinstance(desks, list) else [])
    declared = set(desks)
    if len(declared) != len(desks):
        problems.append("desks names a desk twice")
    live = set(eligible_desks(registry))
    for d in desks:
        if d not in live:
            problems.append("desk %r is not a live desk with production "
                            "records" % d)
    exception = sidecar.get("single_desk_exception")
    if len(declared) < MIN_DESKS:
        if not _exception_ok(exception):
            problems.append(
                "a brief draws evidence from at least %d live desks; a "
                "single-desk brief needs single_desk_exception with "
                "approved_by, approved_on and reason" % MIN_DESKS)
    elif exception:
        problems.append("single_desk_exception is recorded, but the brief "
                        "draws on %d desks" % len(declared))

    # Source trail: each entry keeps its own desk and language.
    trail = sidecar.get("source_trail")
    if not isinstance(trail, list):
        problems.append("source_trail must be a list")
        trail = []
    entries = {}
    for i, e in enumerate(trail):
        at = "source_trail[%d]" % i
        if not isinstance(e, dict):
            problems.append(at + " is not an object")
            continue
        rid = e.get("record_id")
        if not isinstance(rid, int) or isinstance(rid, bool):
            problems.append(at + " has no record_id")
        elif rid in entries:
            problems.append("%s repeats record %d" % (at, rid))
        else:
            entries[rid] = e
        if e.get("desk") not in declared:
            problems.append("%s is from desk %r, which the brief does not "
                            "declare" % (at, e.get("desk")))
        if not _LANG_TAG.match(_text(e.get("lang"))):
            problems.append(at + " records no language tag")
        if "title_zh" in e:
            problems.append(at + " uses title_zh; a brief records "
                                 "title_original with its lang")
        if not _text(e.get("url")):
            problems.append(at + " has no url")
    for d in desks:
        if not any(e.get("desk") == d for e in entries.values()):
            problems.append("desk %r is declared but no source-trail entry "
                            "comes from it" % d)

    # The development the brief begins with.
    development = sidecar.get("development")
    if not isinstance(development, dict):
        problems.append("development must be an object with summary and "
                        "citations")
        development = {}
    dev_cites = development.get("citations") or []
    for ref in dev_cites:
        if ref not in entries:
            problems.append("development cites record %r, which is not in "
                            "the source trail" % (ref,))
    if approved:
        if not _text(development.get("summary")):
            problems.append("an approved brief begins with a concrete "
                            "development: development.summary is empty")
        if not dev_cites:
            problems.append("development cites no source-trail entry")

    # Cross-desk claims: each desk compared is cited.
    claims = sidecar.get("cross_desk_claims") or []
    for i, claim in enumerate(claims):
        at = "cross_desk_claims[%d]" % i
        text = _text(claim.get("claim"))
        if not text:
            problems.append(at + " has no claim text")
        compared = claim.get("desks") or []
        if len(set(compared)) < 2:
            problems.append(at + " compares fewer than two desks")
        for d in sorted(set(compared) - declared):
            problems.append("%s names desk %r, which the brief does not "
                            "declare" % (at, d))
        cited = claim.get("citations") or []
        for ref in cited:
            if ref not in entries:
                problems.append("%s cites record %r, which is not in the "
                                "source trail" % (at, ref))
        covered = {entries[r].get("desk") for r in cited if r in entries}
        for d in compared:
            if d not in covered:
                problems.append("%s makes a claim about desk %r without "
                                "citing any of its entries" % (at, d))
        basis = claim.get("basis")
        if basis not in CLAIM_BASES:
            problems.append("%s basis must be one of: %s"
                            % (at, ", ".join(CLAIM_BASES)))
        if basis == BASIS_STATED:
            stated = claim.get("stated_in") or []
            if not stated or any(r not in cited for r in stated):
                problems.append(at + " rests on a stated record but "
                                     "stated_in names no cited record")
        elif _COORDINATION.search(text):
            problems.append(
                "%s is worded as coordination but rests on comparison; "
                "coordination must be stated in a cited record, never "
                "inferred from similar timing" % at)
    if approved and len(declared) >= MIN_DESKS and not claims:
        problems.append("an approved multi-desk brief makes at least one "
                        "cross-desk comparison")

    # Anatomy, and a term's language.
    if approved:
        for field_name in REQUIRED_SECTIONS:
            if not _text(sidecar.get(field_name)):
                problems.append("an approved brief has the standing anatomy: "
                                "%s is empty" % field_name)
    if (_text(sidecar.get("term_to_know_term"))
            and not _LANG_TAG.match(_text(sidecar.get("term_to_know_lang")))):
        problems.append("term_to_know_term is set but term_to_know_lang is "
                        "not; a term's language is recorded, not assumed")

    # Numbering: none in a draft, one with its approval once approved.
    if not approved and sidecar.get("issue_number") is not None:
        problems.append("a draft carries no issue number; numbers are "
                        "assigned at approval")
    if approved:
        if assigned_number(sidecar) is None:
            problems.append("an approved brief carries its issue number")
        approval = sidecar.get("approval") or {}
        if (not _text(approval.get("approved_by"))
                or _iso_date(approval.get("approved_on")) is None):
            problems.append("an approved brief records approval.approved_by "
                            "and approval.approved_on")
    return problems


# ── Numbering ─────────────────────────────────────────────────────────────────

def assigned_number(sidecar: Mapping):
    """The issue number a sidecar carries, or None."""
    number = sidecar.get("issue_number")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        return None
    return number


def check_numbering(collection: Iterable[Mapping]) -> list:
    """Numbers across the whole collection, predecessor issues included."""
    seen, problems = set(), []
    for sidecar in collection:
        number = assigned_number(sidecar)
        if number is None:
            continue
        if number in seen:
            problems.append("issue number %d is assigned twice" % number)
        seen.add(number)
    return problems


def next_issue_number(collection: Iterable[Mapping], *,
                      unreconciled=UNRECONCILED_ISSUES) -> int:
    """
    The number the next approved issue takes: one more than the highest number
    assigned anywhere in the collection. Dates play no part.
    """
    if unreconciled:
        raise NumberingBlocked(
            "No. %s has an unreconciled publication status, so the next issue "
            "number is not known. Assigning one needs the owner's ruling, "
            "recorded in DECISION_LOG and by clearing UNRECONCILED_ISSUES."
            % ", ".join(str(n) for n in sorted(unreconciled)))
    collection = list(collection)
    problems = check_numbering(collection)
    if problems:
        raise BriefContractError(problems)
    return max((n for n in map(assigned_number, collection) if n is not None),
               default=0) + 1


def approve(draft: Mapping, *, collection: Iterable[Mapping], registry,
            approved_by: str, approved_on: str,
            unreconciled=UNRECONCILED_ISSUES) -> dict:
    """
    A copy of `draft` as an approved brief carrying its number. The draft and
    the collection are not modified. Refuses a brief that already has a number
    — an approved number is never reassigned — and one that breaks the
    contract.
    """
    if (draft.get("editorial_status") == STATUS_APPROVED
            or draft.get("issue_number") is not None):
        raise BriefContractError([
            "this brief already carries No. %s; an approved number is never "
            "reassigned" % draft.get("issue_number")])
    number = next_issue_number(collection, unreconciled=unreconciled)
    approved = dict(draft)
    approved.update({
        "editorial_status": STATUS_APPROVED,
        "issue_number": number,
        "approval": {"approved_by": approved_by, "approved_on": approved_on},
    })
    problems = validate_brief(approved, registry)
    if problems:
        raise BriefContractError(problems)
    return approved


def numbers_changed(before: Mapping[str, Mapping],
                    after: Mapping[str, Mapping]) -> list:
    """Every issue whose assigned number moved or vanished between two views."""
    problems = []
    for key, sidecar in before.items():
        number = assigned_number(sidecar)
        if number is None:
            continue
        if key not in after:
            problems.append("%s (No. %d) is gone" % (key, number))
        elif assigned_number(after[key]) != number:
            problems.append("%s changed from No. %d to %r"
                            % (key, number, after[key].get("issue_number")))
    return problems
