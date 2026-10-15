"""Offline, version-bound review intake for three staged Korea Week-42 sources.

This is a PRIVATE human-review *recording aid*, not a reviewer identity verifier,
copyright clearance, Sunday admission, model authorization or publication gate.
No network, publisher retrieval, SMTP, AI, database or site imports.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

from core.korea_private_research_candidates import (
    COMMIT, ROOT, KoreaResearchHold, load, pairs, require,
)

SCHEMA = "ipr-korea-week42-private-human-review/1"
RECEIPT_SCHEMA = "ipr-korea-week42-private-human-review-receipt/1"
SCOPE = "restricted-local-offline-synopsis-review-only"
CONTROLS = {
    "model_use_authorized": False,
    "email_authorized": False,
    "publication_authorized": False,
    "public_original_redistribution_authorized": False,
}
HUMAN_FLAGS = (
    "rendered_hwpx_compared",
    "korean_extraction_compared",
    "issuer_and_dates_verified",
    "claim_modalities_and_caveats_verified",
)
RIGHTS_FLAGS = (
    "exact_page_text_only_mark_checked",
    "attribution_requirements_recorded",
    "all_nontext_media_excluded",
    "limited_local_offline_review_assessed",
)
UTC_SECONDS = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")


def template(*, week_ending="2026-10-17"):
    """Create blank decisions from the already-validated, immutable staging packet."""
    rows = load(week_ending=week_ending)
    return {
        "schema": SCHEMA,
        "week_ending": week_ending,
        "state_commit": COMMIT,
        "intended_use": SCOPE,
        "controls": dict(CONTROLS),
        "entries": [
            {
                "source_id": row["source_id"],
                "source_url": row["source_url"],
                "published_date": row["published_date"],
                "document_distribution_date": row["document_distribution_date"],
                "source_content_sha256": row["source_content_sha256"],
                "hwpx_capture_sha256": row["hwpx_capture_sha256"],
                "publisher_html_capture_sha256": row["publisher_html_capture_sha256"],
                "evidence_anchors": [],
                "human_review": {
                    "disposition": "pending",
                    "reviewer": "",
                    "reviewed_at_utc": None,
                    **{key: False for key in HUMAN_FLAGS},
                    "concerns": "",
                },
                "rights_review": {
                    "disposition": "pending",
                    "reviewer": "",
                    "reviewed_at_utc": None,
                    **{key: False for key in RIGHTS_FLAGS},
                    "concerns": "",
                },
                "owner_review": {
                    "disposition": "pending",
                    "reviewer": "",
                    "reviewed_at_utc": None,
                    "explicit_local_no_send_rehearsal_only": False,
                    "concerns": "",
                },
            } for row in rows
        ],
    }


def _exact(obj, keys, name):
    require(type(obj) is dict and set(obj) == set(keys), "unexpected " + name + " fields")


def _text(value, *, max_len=800, optional=True):
    return (type(value) is str and value == value.strip()
            and (optional or len(value) >= 3) and len(value) <= max_len
            and not any(ord(ch) < 32 or ord(ch) == 127 or ch in "<>" for ch in value))


def _timestamp(value, *, now):
    require(type(value) is str and UTC_SECONDS.fullmatch(value) is not None,
            "review time must be canonical UTC seconds")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise KoreaResearchHold("invalid reviewer timestamp") from exc
    require(parsed <= now, "future review timestamp")
    return parsed


def _section(value, kind, flags, positive, now):
    _exact(value, ("disposition", "reviewer", "reviewed_at_utc",
                   "concerns", *flags), kind)
    require(_text(value["concerns"]), "unsafe review concerns")
    require(value["disposition"] in ("pending", positive), "unknown review disposition")
    require(all(type(value[k]) is bool for k in flags), "non-boolean review flag")
    if value["disposition"] == "pending":
        require(value["reviewer"] == "" and value["reviewed_at_utc"] is None
                and all(value[k] is False for k in flags),
                "pending review cannot contain implied approval")
        return None
    require(_text(value["reviewer"], max_len=100, optional=False),
            "named reviewer required in private record")
    require(all(value[k] is True for k in flags),
            "reported review incomplete")
    return _timestamp(value["reviewed_at_utc"], now=now)


def _anchors(value):
    """Check claimed original-language line citations, not their truth.

    Independent reviewer must verify every hash against the frozen extracted
    Korean text and original rendered HWPX before attesting authenticity.
    """
    require(type(value) is list and 1 <= len(value) <= 8,
            "one to eight private evidence anchors required")
    observed = set()
    for row in value:
        _exact(row, ("line_number", "line_sha256", "claim_kind",
                     "editorial_linkage"), "private original-language anchor")
        number = row["line_number"]
        require(type(number) is int and 1 <= number <= 10000
                and number not in observed, "duplicate or invalid original line")
        observed.add(number)
        require(type(row["line_sha256"]) is str and
                re.fullmatch(r"[0-9a-f]{64}", row["line_sha256"]) is not None,
                "invalid original-language line SHA-256")
        require(row["claim_kind"] in (
            "announcement", "plan", "reported_action", "assessment", "discussion"
        ), "invalid original-language claim kind")
        require(_text(row["editorial_linkage"], max_len=240, optional=False)
                and len(row["editorial_linkage"]) >= 24,
                "missing bounded English-original claim linkage")


def validate(data, *, now=None, week_ending="2026-10-17"):
    """Validate structure and versions; NEVER authenticate a person or grant use.

    A fabricated, structurally plausible reviewer name is not a signature.
    Outputs are fixed-count metadata only, without names/notes/original bodies.
    """
    base = template(week_ending=week_ending)
    now = now or datetime.now(timezone.utc)
    require(now.tzinfo is not None and now.utcoffset() is not None,
            "timezone-aware validation clock required")
    _exact(data, base.keys(), "top-level review")
    for key in ("schema", "week_ending", "state_commit", "intended_use"):
        require(data[key] == base[key], "unknown review schema/week/source/scope")
    require(type(data["controls"]) is dict and data["controls"] == CONTROLS
            and all(data["controls"][k] is False for k in CONTROLS),
            "review intake cannot authorize models, email, publication or originals")
    rows = data["entries"]
    require(type(rows) is list and len(rows) == len(base["entries"]),
            "review must cover the exact three staged sources")
    counts = {"human": 0, "rights": 0, "local": 0}
    for got, expected in zip(rows, base["entries"]):
        _exact(got, expected.keys(), "source review")
        for key in ("source_id", "source_url", "published_date",
                    "document_distribution_date", "source_content_sha256",
                    "hwpx_capture_sha256", "publisher_html_capture_sha256"):
            require(got[key] == expected[key], "source pin/version mismatch")
        human = _section(got["human_review"], "human_review", HUMAN_FLAGS,
                         "reviewed_source_version", now)
        rights = _section(got["rights_review"], "rights_review", RIGHTS_FLAGS,
                          "assessed_for_local_use_only", now)
        owner = _section(
            got["owner_review"], "owner_review",
            ("explicit_local_no_send_rehearsal_only",),
            "acknowledged_local_rehearsal_only", now,
        )
        if human is None:
            require(got["evidence_anchors"] == [],
                    "unreviewed source cannot claim reviewed line anchors")
        else:
            _anchors(got["evidence_anchors"])
            require(human.date() >= date.fromisoformat(got["published_date"]),
                    "human review predates original publisher document")
        require(rights is None or human is not None,
                "rights review must not precede original-language review")
        require(owner is None or (rights is not None and human is not None),
                "owner local rehearsal request needs both human and rights reviews")
        if human is not None and rights is not None:
            require(human <= rights, "rights decision predates source review")
        if owner is not None:
            require(rights <= owner, "owner decision predates source/rights reviews")
        counts["human"] += human is not None
        counts["rights"] += rights is not None
        counts["local"] += owner is not None
    return {
        "schema": RECEIPT_SCHEMA,
        "state_commit": COMMIT,
        "week_ending": week_ending,
        "candidate_count": len(rows),
        "human_review_reports_structurally_complete": counts["human"],
        "rights_review_reports_structurally_complete": counts["rights"],
        "owner_local_rehearsal_reports_structurally_complete": counts["local"],
        "reviewer_identity_authenticated": False,
        "source_line_evidence_independently_checked": False,
        "legal_rights_adjudicated_by_software": False,
        "model_called": False,
        "email_sent": False,
        "publication_authorized": False,
        "model_use_authorized": False,
        "source_rights_automatically_approved": False,
        "sunday_admission_authorized": False,
        "source_bodies_exported": False,
    }


def _private_path(value, *, must_exist):
    raw = Path(value).expanduser()
    require(raw.is_absolute() and raw.parent.is_dir() and not raw.parent.is_symlink()
            and not raw.is_symlink(), "private path must be absolute and nonsymlinked")
    path = raw.resolve(strict=False)
    root = ROOT.resolve()
    require(path != root and root not in path.parents,
            "private reviewer data cannot be written/read inside public repo")
    require(path.is_file() if must_exist else not path.exists(),
            "review file must exist for checking and be new for creation")
    return path


def create_private_template(path):
    """Create new restrictive file; never overwrite and never write in repo."""
    target = _private_path(path, must_exist=False)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(target), flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(template(), stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target


def check_private_review(path, *, now=None):
    target = _private_path(path, must_exist=True)
    require(target.stat().st_size <= 30000, "oversized review record")
    if os.name == "posix":
        require(target.stat().st_mode & 0o077 == 0,
                "private review must not be group/world accessible")
    try:
        with target.open("r", encoding="utf-8") as stream:
            record = json.load(
                stream, object_pairs_hook=pairs,
                parse_constant=lambda _: require(False, "nonfinite review JSON"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise KoreaResearchHold("malformed review JSON") from exc
    return validate(record, now=now)
