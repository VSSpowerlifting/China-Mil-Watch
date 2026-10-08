"""One-week Indonesia research bridge for Friday's provisional AI editorial draft.

No archive DB reads or writes, no networking, no source promotion, no approval.
The published primary-source original is linked and already appears in the
isolated October 7 Kemhan shadow run; the model receives only attributed
analyst paraphrases. The editor must independently compare the original.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

FRIDAY = date(2026, 10, 9)
SATURDAY = date(2026, 10, 10)
DEFAULT_PACKET = (Path(__file__).resolve().parents[1] /
                  "research/indonesia/friday_2026-10-09/official_source_candidates.json")
SOURCE_ID = "ID-W41-01"
SOURCE_URL = (
    "https://www.kemhan.go.id/2026/10/06/"
    "menhan-sjafrie-terima-courtesy-call-athan-singapura-apresiasi-dedikasi-selama-bertugas.html"
)
STATE_COMMIT = "dc6a76193d17f3513c32ec1de02902ed01421437"
CAPTURE_SHA256 = "62e3d7d48601d2395adb1d2a3fc88d20c6b67d572a247bd9e8408fa25ae8af0b"
STATUS = "captured_source_claims_pending_human_review_not_IPR_record"
EXPECTED_CLAIMS = (
    "The Indonesian Ministry of Defense reports that Defense Minister Sjafrie Sjamsoeddin received outgoing Singapore defense attaché ME7 Gan Chee Weng Melvin at the ministry in Jakarta on October 5; the ministry published this account on October 6.",
    "The ministry characterized the courtesy call as defense diplomacy and appreciation for the attaché's work supporting Indonesia–Singapore defense communications; its account also reports meetings with the deputy minister and secretary-general.",
)


class IndonesiaEditorialSourceError(ValueError):
    """Evidence is missing, altered, or outside the one approved reporting window."""


def _iso(value):
    if not isinstance(value, str):
        raise IndonesiaEditorialSourceError("invalid source packet date")
    try:
        day = date.fromisoformat(value)
    except ValueError as exc:
        raise IndonesiaEditorialSourceError("invalid source packet date") from exc
    if day.isoformat() != value:
        raise IndonesiaEditorialSourceError("non-canonical source packet date")
    return day


def load_indonesia_writer_sources(week_ending, as_of, *, packet_path=DEFAULT_PACKET):
    """Offer exactly one bounded, source-labeled non-production research record.

    Different weeks return [], preserving normal collection and authoring.
    Same-week missing/tampered source state refuses the automatic handoff.
    """
    ending, cutoff = _iso(week_ending), _iso(as_of)
    if ending != SATURDAY:
        return []
    if cutoff != FRIDAY or cutoff.weekday() != 4 or ending != cutoff + timedelta(days=1):
        raise IndonesiaEditorialSourceError("Indonesia research restricted to October 9 Friday")
    path = Path(packet_path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 20000:
        raise IndonesiaEditorialSourceError("missing or unsafe Indonesia research packet")
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IndonesiaEditorialSourceError("unreadable Indonesia source packet") from exc
    if not isinstance(packet, dict):
        raise IndonesiaEditorialSourceError("invalid Indonesia source packet")
    for key, expected in (
        ("protocol", "ipr_indonesia_week41_nonproduction_research_v1"),
        ("status", "source_verified_analyst_research_without_human_approval"),
        ("source_scope", "Indonesia Ministry of Defense original-language Kemhan Berita; NOT a production desk"),
        ("week_start", "2026-10-04"),
        ("reporting_friday", "2026-10-09"),
        ("week_ending", "2026-10-10"),
        ("shadow_state_branch", "shadow/indonesia-kemhan"),
        ("shadow_state_commit", STATE_COMMIT),
        ("shadow_run_id", "37693074726-1"),
        ("shadow_ledger_path", "state/ledger/20261007T215950.014595+0000-37693074726-1.json"),
    ):
        if packet.get(key) != expected:
            raise IndonesiaEditorialSourceError("unrecognized Indonesia source lineage: " + key)
    rows = packet.get("source_candidates")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise IndonesiaEditorialSourceError("one explicit Indonesia source required")
    row = rows[0]
    expected = {
        "candidate_id": SOURCE_ID, "public_source_url": SOURCE_URL,
        "title": "Menhan Sjafrie Terima Courtesy Call Athan Singapura, Apresiasi Dedikasi Selama Bertugas",
        "publisher_date": "2026-10-06", "event_date": "2026-10-05",
        "institution": "Kementerian Pertahanan Republik Indonesia",
        "source_family": "Kemhan Berita", "source_language": "id",
        "captured_response_sha256": CAPTURE_SHA256,
        "evidence_representation":
            "analyst_paraphrase_of_official_original_not_an_archived_body_in_prompt",
        "production_record_id": None, "shadow_record_id": None,
        "original_body_independently_human_verified": False,
        "source_admission_approved": False,
        "editorial_inclusion_approved": False, "source_reuse_cleared": False,
    }
    for key, value in expected.items():
        if key not in row or row[key] != value or type(row[key]) is not type(value):
            raise IndonesiaEditorialSourceError("unrecognized Indonesia source identity: " + key)
    parsed = urlsplit(row["public_source_url"])
    if parsed.scheme != "https" or parsed.hostname != "www.kemhan.go.id" or (
        parsed.query or parsed.fragment or parsed.username or parsed.password):
        raise IndonesiaEditorialSourceError("invalid official source URL")
    if _iso(row["event_date"]) > _iso(row["publisher_date"]) or (
        _iso(row["publisher_date"]) > cutoff):
        raise IndonesiaEditorialSourceError("out-of-window Indonesia article")
    claims = row.get("provisional_claims")
    caveats = row.get("caveats")
    if claims != list(EXPECTED_CLAIMS):
        raise IndonesiaEditorialSourceError("unreviewed Indonesia claim mutation")
    if (not isinstance(caveats, list) or len(caveats) < 4
            or any(not isinstance(x, str) or not 25 <= len(x) <= 500 for x in caveats)):
        raise IndonesiaEditorialSourceError("insufficient source/translation caveats")
    governance = packet.get("editorial_handling")
    if not isinstance(governance, dict) or any(
        governance.get(k) is not v for k, v in (
            ("may_offer_to_single_provisional_ai_call", True),
            ("requires_two_live_production_desks", True),
            ("section_citations_must_keep_separate_namespace", True),
            ("independent_human_verification_before_publication", True),
            ("never_counts_as_live_desk", True),
            ("never_modify_production_database", True),
        )
    ):
        raise IndonesiaEditorialSourceError("nonproduction source rules changed")
    return [{
        "id": SOURCE_ID, "desk": "indonesia",
        "issuer": row["institution"], "url": row["public_source_url"],
        "published_date": row["publisher_date"], "title": row["title"],
        "source_language": "id",
        "evidence_representation": row["evidence_representation"],
        "status": STATUS, "claims": list(claims), "caveats": list(caveats),
        "shadow_state_commit": STATE_COMMIT, "shadow_run_id": "37693074726-1",
        "captured_response_sha256": CAPTURE_SHA256,
    }]
