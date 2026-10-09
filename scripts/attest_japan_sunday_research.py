"""Read-only Japan Sunday research provenance attestation; no editorial approval.

An exact archived extracted-text digest is not the original Japanese PDF.
The official English webpage candidates are pointers, not archived captures.
No model call, HTTP fetching, production modifications or email.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from core.brief_editorial_evidence import load_editorial_evidence
from scripts import audit_japan_oct05_brief_source as archived

WEEK = "2026-10-10"
IDS = {"JP-W41-01", "JP-W41-02", "JP-W41-06"}
HTML = {
    "JP-W41-01": ("https://www.mod.go.jp/en/article/2026/10/5fc631a5d1b2f36a9b697a611082a85af444ea54.html", "2026-10-06"),
    "JP-W41-02": ("https://www.mod.go.jp/en/article/2026/10/92045078e2a66f0957658c577e65cb0832261b17.html", "2026-10-06"),
}


class JapanSundayAuditError(ValueError):
    pass


def attest(*, week_ending, as_of, state_repo=None, directory=None, snapshot=None):
    """Verify bounded packet identities and exact pinned JP MOD text extraction.

    The snapshot argument exists for network-free tests only. Weeks other than
    Oct 10 cannot silently inherit the frozen Oct 10 Japan research packet.
    """
    if not isinstance(week_ending, str) or not isinstance(as_of, str):
        raise JapanSundayAuditError("reporting day must be an ISO string")
    try:
        saturday = date.fromisoformat(week_ending)
        cutoff = date.fromisoformat(as_of)
    except ValueError as exc:
        raise JapanSundayAuditError("invalid ISO date") from exc
    if saturday.isoformat() != week_ending or cutoff.isoformat() != as_of:
        raise JapanSundayAuditError("canonical YYYY-MM-DD required")
    if saturday.weekday() != 5:
        raise JapanSundayAuditError("week-ending must be Saturday")
    if week_ending == WEEK and as_of not in ("2026-10-09", WEEK):
        raise JapanSundayAuditError("Oct10 research cutoff must be Friday or Saturday")
    if week_ending != WEEK:
        if cutoff not in (saturday, date.fromordinal(saturday.toordinal() - 1)):
            raise JapanSundayAuditError("other-week cutoff must be Friday or Saturday")
        return {
            "schema": "ipr-japan-private-research-attestation/1",
            "week_ending": week_ending, "as_of": as_of,
            "status": "no_japan_packet_for_this_week",
            "japan_records": 0, "evidence": [],
            "archived_original_pdf_bytes_verified": False,
            "human_source_review_completed": False,
            "editorial_inclusion_approved": False,
            "japan_production_eligible": False, "smtp_or_production_writes": 0,
        }
    kwargs = {} if directory is None else {"directory": Path(directory)}
    rows = load_editorial_evidence(week_ending, as_of, **kwargs)
    japan = {x["id"]: x for x in rows if x["desk"] == "japan"}
    if len(japan) != len(IDS) or set(japan) != IDS:
        raise JapanSundayAuditError("Japan research roster differs from exact 3 source IDs")
    evidence = []
    for ident in sorted(HTML):
        item = japan[ident]
        url, day = HTML[ident]
        if (item["source_url"], item["published_date"]) != (url, day):
            raise JapanSundayAuditError("MOD HTML original identity or publication date drifted")
        if (item["source_kind"] != "official-publisher-page-reviewed-for-research"
            or item["language"] != "en" or item["state_commit"] is not None
            or item["source_content_sha256"] is not None or item["hash_rule"] is not None):
            raise JapanSundayAuditError("public MOD page incorrectly claims archived full text")
        evidence.append({
            "id": ident, "publisher_url": url, "publication_date": day,
            "verification_class": "publisher_url_and_date_metadata_only",
            "original_html_body_pinned": False,
            "source_body_human_verified": False,
        })
    pdf = japan["JP-W41-06"]
    if (pdf["source_kind"] != "shadow-extracted-original"
        or pdf["source_url"] != archived.PDF_URL
        or pdf["published_date"] != "2026-10-05"
        or pdf["title_original"] != archived.TITLE
        or pdf["language"] != "ja"
        or pdf["state_commit"] != archived.STATE_COMMIT
        or pdf["source_content_sha256"] != archived.TEXT_SHA256
        or pdf["hash_rule"] != "sha256-text-original-utf8"):
        raise JapanSundayAuditError("Oct5 PDF research version differs from verified shadow")
    if snapshot is None:
        if state_repo is None:
            raise JapanSundayAuditError("exact original Japan MOD state repo required")
        try:
            verified = archived.inspect_snapshot(
                archived.read_git_blob(Path(state_repo)))
        except (archived.JapanShadowAuditError, OSError) as exc:
            raise JapanSundayAuditError("immutable Japan source verification failed") from exc
    else:
        verified = snapshot
    if (verified.get("state_commit") != archived.STATE_COMMIT
        or verified.get("state_db_blob_sha1") != archived.DB_BLOB_SHA1
        or verified.get("archived_text_sha256_verified") is not True
        or verified.get("source_url") != archived.PDF_URL
        or verified.get("source_published_date") != "2026-10-05"
        or verified.get("archive_current_week_records_through_oct08") != 1
        or verified.get("archived_original_pdf_bytes_verified") is not False
        or verified.get("full_pdf_human_fidelity_review_complete") is not False
        or verified.get("editorial_inclusion_approved") is not False):
        raise JapanSundayAuditError("pinned Japan shadow receipt fails nonapproval contract")
    evidence.append({
        "id": "JP-W41-06", "publisher_url": archived.PDF_URL,
        "publication_date": "2026-10-05",
        "verification_class": "immutable_shadow_extracted_text_digest_only",
        "pinned_state_commit": archived.STATE_COMMIT,
        "pinned_sqlite_blob_sha1": archived.DB_BLOB_SHA1,
        "text_sha256": archived.TEXT_SHA256,
        "archived_extracted_text_verified": True,
        "archived_original_pdf_bytes_verified": False,
        "full_pdf_human_fidelity_review_complete": False,
    })
    return {
        "schema": "ipr-japan-private-research-attestation/1",
        "week_ending": WEEK, "as_of": as_of,
        "status": "exact_versions_verified_not_editorial_approval",
        "japan_records": 3, "evidence": evidence,
        "archived_original_pdf_bytes_verified": False,
        "human_source_review_completed": False,
        "editorial_inclusion_approved": False,
        "japan_production_eligible": False,
        "smtp_or_production_writes": 0,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--week-ending", default=WEEK)
    p.add_argument("--as-of", default=WEEK)
    p.add_argument("--state-repo", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    if args.output.exists():
        p.error("refusing to overwrite research verification receipt")
    try:
        result = attest(week_ending=args.week_ending, as_of=args.as_of,
                        state_repo=args.state_repo)
    except (JapanSundayAuditError, ValueError, OSError) as exc:
        p.error(str(exc))
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                      indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"week_ending": result["week_ending"],
                      "status": result["status"],
                      "japan_records": result["japan_records"],
                      "editorial_inclusion_approved": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
