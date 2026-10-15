"""Korea source-specific *staged* private research; not Sunday/model admission.

Reads only authored short synopses and immutable original-version identities.
There are no publisher, SQLite, HWPX, LLM, email or production side effects.
Human review coverage reported by the owner is not signed source-by-source
language review, licensing, or owner authorization to transmit to a model.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = ROOT / "research" / "korea" / "private_research_candidates"
SCHEMA = "ipr-korea-staged-private-research/1"
COMMIT = "0595f0fd29b769cbab5dd57c2ef57af174237a67"
STATUS = "held-not-sunday-or-model-eligible"
COPY_SCOPE = "authored-editorial-synopsis-only-no-original-text-or-media"
REVIEW = "owner-reports-all-14-read-no-formal-version-bound-signoff"
HOLD_NEWS_IDS = frozenset(("156785161",))
MAX_ITEMS = 3
ITEM_FIELDS = frozenset((
    "source_id", "desk", "issuer", "publisher", "source_url",
    "published_date", "document_distribution_date", "title_original",
    "source_content_sha256", "hwpx_capture_sha256", "hash_rule",
    "summary", "caveats", "claim_kind", "status", "copy_scope",
))
# Each captured source is independently version-pinned. This is *not* a
# standing allowance for any government portal page or other shadow commit.
PINS = {
    "156784873": {
        "title_original": "국방부, 첫 번째 「국방 AX 거점」 개소식 개최",
        "published_date": "2026-10-12",
        "document_distribution_date": "2026-10-12",
        "source_content_sha256": "ceee86fe0a9ab82689b8e43a5361d312b259df923ae631039e64cebed9494639",
        "hwpx_capture_sha256": "2a197b95c0174964b31148167a5c1b9d29bb64ecf60ab4326504d98793f87d4a",
        "claim_kind": "reported_action",
    },
    "156784787": {
        "title_original": "국방부차관, 방일 및 한일 국방차관회담 실시",
        "published_date": "2026-10-12",
        "document_distribution_date": "2026-10-09",
        "source_content_sha256": "a72d9371bb676a95639ff2ed7cdc352311effb249b3485cf125f462999aa4319",
        "hwpx_capture_sha256": "57ab003628355b5b29f6204ad59ee925b439849c58c9022355b924d7928db43e",
        "claim_kind": "reported_action",
    },
    "156785162": {
        "title_original": "국방부장관, 공군 제1전투비행단 대비태세 현장점검",
        "published_date": "2026-10-14",
        "document_distribution_date": "2026-10-14",
        "source_content_sha256": "e0455256a1fd66ea82fb87f8c61220e2c526378a3ca873dd3f72d5a7fb193e27",
        "hwpx_capture_sha256": "3fdaba73bce1140a1ba0f94948d4ab9849a16703d4e52f8b8858f2639dfb7994",
        "claim_kind": "reported_action",
    },
}


class KoreaResearchHold(ValueError):
    """Malformed, re-versioned, out-of-week or implicitly admitted research."""


def require(ok, reason):
    if not ok:
        raise KoreaResearchHold(reason)


def pairs(entries):
    out = {}
    for key, value in entries:
        require(key not in out, "duplicate key")
        out[key] = value
    return out


def day(value):
    require(type(value) is str and bool(re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", value)),
            "invalid date format")
    try:
        dt = date.fromisoformat(value)
    except ValueError as exc:
        raise KoreaResearchHold("invalid calendar date") from exc
    require(dt.isoformat() == value, "noncanonical date")
    return dt


def line(value, *, min_chars=1, max_chars=700):
    return (type(value) is str and value == value.strip()
            and min_chars <= len(value) <= max_chars
            and not any(ord(c) < 32 or ord(c) == 127 for c in value)
            and "<" not in value and ">" not in value)


def validate(data, *, week_ending="2026-10-17", as_of="2026-10-17"):
    saturday, cutoff = day(week_ending), day(as_of)
    require(saturday.weekday() == 5
            and cutoff in (saturday, saturday - timedelta(days=1)),
            "only reporting Saturday or Friday cutoff supported")
    require(type(data) is dict and set(data) == {
        "schema", "week_ending", "state_commit", "owner_reported_review",
        "publication_authorized", "model_use_authorized",
        "source_rights_approved", "items",
    }, "packet contains missing or extra keys")
    require(data["schema"] == SCHEMA and data["week_ending"] == week_ending
            and data["state_commit"] == COMMIT
            and data["owner_reported_review"] == REVIEW,
            "wrong week, immutable state or human coverage statement")
    require(data["publication_authorized"] is False
            and data["model_use_authorized"] is False
            and data["source_rights_approved"] is False,
            "staged research cannot grant rights, model or publication authority")
    items = data["items"]
    require(type(items) is list and 1 <= len(items) <= MAX_ITEMS,
            "only one to three pinned source candidates")
    observed = set()
    for row in items:
        require(type(row) is dict and set(row) == ITEM_FIELDS,
                "item missing or extra fields")
        ident = row["source_id"]
        require(type(ident) is str
                and bool(re.fullmatch(r"KR-MND-W42-[0-9]{2}", ident)),
                "source needs typed Week 42 identity")
        require(ident not in observed, "duplicate candidate ID")
        observed.add(ident)
        news_id = ident.rsplit("-", 1)[-1]
        # Typed sequence to literal source URL is a CLOSED mapping: a sequence
        # number cannot turn a spoofed article into a qualified source.
        source_for_seq = {"01": "156784873", "02": "156784787",
                          "03": "156785162"}
        require(news_id in source_for_seq, "unknown sequence")
        orig_id = source_for_seq[news_id]
        require(orig_id not in HOLD_NEWS_IDS, "disputed chronology source excluded")
        pin = PINS[orig_id]
        require(row["desk"] == "korea" and
                row["issuer"] == "Republic of Korea Ministry of National Defense"
                and row["publisher"] == "Korea Policy Briefing"
                and row["source_url"] ==
                "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + orig_id,
                "wrong Korean issuer/republication identity")
        parsed = urlsplit(row["source_url"])
        require(parsed.scheme == "https" and parsed.hostname == "www.korea.kr"
                and not parsed.username and not parsed.password and
                not parsed.fragment and parsed.port is None,
                "unsupported source URL")
        for key, value in pin.items():
            require(row.get(key) == value, "unpinned " + key)
        require(row["hash_rule"] == "sha256-text-original-utf8",
                "unknown Korea original-text digest rule")
        require(day(row["published_date"]) >= saturday - timedelta(days=6)
                and day(row["published_date"]) <= cutoff,
                "portal publication outside the week")
        require(day(row["document_distribution_date"]) <=
                day(row["published_date"]),
                "future relative to portal posting")
        require(line(row["summary"], min_chars=85, max_chars=650)
                and "korea-policy:" not in row["summary"],
                "summary must be short attributed editorial prose")
        require(type(row["caveats"]) is list
                and 2 <= len(row["caveats"]) <= 4
                and all(line(c, min_chars=35, max_chars=270)
                        for c in row["caveats"]),
                "missing source-specific editorial cautions")
        require(row["status"] == STATUS and row["copy_scope"] == COPY_SCOPE,
                "inferred source admission or original text reuse")
    return items


def load(*, week_ending="2026-10-17", as_of="2026-10-17",
         directory=PACK_DIR):
    """Validate a stage-only packet; do not feed it to a model or Sunday."""
    path = Path(directory) / (week_ending + ".json")
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size <= 15000, "absent or unsafe candidate packet")
    try:
        packet = json.loads(path.read_text(encoding="utf-8"),
                            object_pairs_hook=pairs,
                            parse_constant=lambda _: require(False, "nonfinite JSON"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise KoreaResearchHold("malformed candidate JSON") from exc
    return validate(packet, week_ending=week_ending, as_of=as_of)


def machine_receipt(items):
    """Bounded identity-only output. Source text and synopses stay private."""
    require(type(items) is list and 1 <= len(items) <= MAX_ITEMS,
            "unknown item list")
    return {
        "schema": "ipr-korea-private-research-readonly-receipt/1",
        "state_commit": COMMIT,
        "source_ids": [row["source_id"] for row in items],
        "source_count": len(items),
        "status": STATUS,
        "model_called": False,
        "email_sent": False,
        "publication_authorized": False,
        "source_rights_approved": False,
        "source_body_exported": False,
        "scheduled_collector_changed": False,
    }
