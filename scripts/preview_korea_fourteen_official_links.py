"""Validate fourteen Korean official-link candidates and create a held local preview.

The live five-link directory is unchanged. This cannot admit new records,
mirror originals, send email, use a model, or deploy a public page.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from core.korea_public_bibliography import load_public_korea_links
from core.korea_reference_gate import ROOT, KoreaGateHold, load_json, require

SCHEMA = "ipr-korea-fourteen-source-public-link-candidates/1"
STATE = "0595f0fd29b769cbab5dd57c2ef57af174237a67"
MANIFEST = ROOT / "research/korea/MND_14_PUBLIC_LINK_REVIEW_CANDIDATES_2026-10-15.json"
ROSTER = ROOT / "research/korea/MND_HWPX_14_ORIGINAL_SOURCE_REVIEW_REGISTER_2026-10-14.md"
RIGHTS = ROOT / "docs/engineering/KOREA_MND_14_PAGE_KOGL_TYPE1_TEXT_MARK_AUDIT_2026-10-15.md"
SHA = re.compile(r"[0-9a-f]{64}\Z")
ROSTER_ROW = re.compile(r"^\| \d{1,2} \| \[([0-9]{9})\]\([^)]+\) \| [^|]+ \| \u0060([0-9a-f]{64})\u0060 \|", re.M)
RIGHTS_ROW = re.compile(r"^\| \[([0-9]{9})\]\([^)]+\) \| \u0060([0-9a-f]{64})\u0060 \| Type 1 / text only / attribution \| Non-text permission required \|$", re.M)
FIELDS = {"news_id", "source_url", "hwpx_capture_sha256",
          "publisher_html_capture_sha256", "status", "editorial_exception"}
ROOT_FIELDS = {"schema", "state_ref", "state_commit",
               "first_five_existing_release_commit", "source_family",
               "issuer_original", "publisher_original", "license_evidence",
               "mode", "reviewer_attestation_authenticated",
               "owner_approval_for_new_public_links",
               "eligible_new_public_links", "entries"}


def validate():
    evidence = load_json(MANIFEST, size=16000)
    require(type(evidence) is dict and set(evidence) == ROOT_FIELDS,
            "candidate roster has unexpected fields")
    require(evidence["schema"] == SCHEMA
            and evidence["state_ref"] == "shadow/korea-policy-briefing"
            and evidence["state_commit"] == STATE
            and evidence["first_five_existing_release_commit"] ==
            "dcb43b9c4edb471d6def5876701ec4a2e39d5264"
            and evidence["source_family"] == "kr_policy_mnd_releases"
            and evidence["issuer_original"] == "국방부"
            and evidence["publisher_original"] == "대한민국 정책브리핑"
            and evidence["license_evidence"] ==
            "KOGL Type 1 page notice, text only, attribution required; excludes embedded nontext media"
            and evidence["mode"] == "owner_review_only_not_public_release"
            and evidence["reviewer_attestation_authenticated"] is False
            and evidence["owner_approval_for_new_public_links"] is False
            and type(evidence["eligible_new_public_links"]) is int
            and evidence["eligible_new_public_links"] == 0,
            "Korea new links are not authorized")
    require(not ROSTER.is_symlink() and not RIGHTS.is_symlink(),
            "source registers cannot be symlinks")
    hwpx = dict(ROSTER_ROW.findall(ROSTER.read_text(encoding="utf-8")))
    html = dict(RIGHTS_ROW.findall(RIGHTS.read_text(encoding="utf-8")))
    require(len(hwpx) == len(html) == 14 and set(hwpx) == set(html),
            "source evidence does not have exactly fourteen original pairs")
    live = {x["source_identity"].split(":")[1]: x
            for x in load_public_korea_links()}
    require(len(live) == 5 and type(evidence["entries"]) is list
            and len(evidence["entries"]) == 14,
            "existing published five or held source count changed")
    seen = set()
    for row in evidence["entries"]:
        require(type(row) is dict and set(row) == FIELDS,
                "unsafe source row fields")
        ident = row["news_id"]
        require(type(ident) is str and ident in hwpx and ident not in seen,
                "unknown or duplicated article identity")
        seen.add(ident)
        require(row["source_url"] ==
                "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + ident
                and row["hwpx_capture_sha256"] == hwpx[ident]
                and row["publisher_html_capture_sha256"] == html[ident]
                and SHA.fullmatch(row["hwpx_capture_sha256"]) is not None
                and SHA.fullmatch(row["publisher_html_capture_sha256"]) is not None,
                "canonical URL or captured response hash mismatched")
        status = ("existing_public_bibliography_link_only" if ident in live
                  else "hold_candidate_official_link_only")
        require(row["status"] == status, "held link falsely promoted")
        exception = ("inconsistent_2025_2026_excavation_year_issue_601"
                     if ident == "156785161" else None)
        require(row["editorial_exception"] == exception,
                "unresolved Korea chronological dispute omitted")
    require(seen == set(hwpx) and len(seen - set(live)) == 9,
            "nine additional exact source identities expected")
    return evidence["entries"], live


def preview(rows, live):
    lines = [
        "# PRIVATE Korea official-link expansion review",
        "",
        "**HOLD — not for public publication, model, Sunday or editor email.**",
        "",
        "14 archived MND/Policy Briefing source identities. The first five "
        "links are already public; all nine additional links remain held.",
        "Original Korean HWPX, translated bodies, photographs and media are "
        "not included in this reviewer document.",
        "Observed rights mark on each historic article page: KOGL Type 1 "
        "for text only with attribution; nontext material excluded.",
        "",
    ]
    for item in rows:
        ident = item["news_id"]
        existing = ident in live
        title = (live[ident]["title_original"] if existing
                 else "MND release " + ident + " — original title review pending")
        lines.extend([
            "## " + title,
            "Official URL: " + item["source_url"],
            "Status: " + ("EXISTING PUBLIC LINK" if existing
                         else "HELD — no new public link permission"),
        ])
        if item["editorial_exception"]:
            lines.append("Editorial exception: contradictory excavation year (#601); no claim summary.")
        lines.append("")
    lines.extend([
        "New official links authorized: **0 of 9**.",
        "Next: exact-version identity/title/date reviewer attestation, "
        "specific text-use/attribution adjudication, and explicit "
        "owner approval before updating the existing public five-link manifest.",
        "",
    ])
    return "\n".join(lines)


def create(destination):
    rows, live = validate()
    output = Path(destination).expanduser()
    root = ROOT.resolve()
    target = output.resolve(strict=False)
    require(output.is_absolute() and output.parent.is_dir()
            and not output.parent.is_symlink() and not output.exists()
            and not output.is_symlink() and target != root
            and root not in target.parents,
            "private preview must be new absolute output outside repository")
    body = preview(rows, live)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    with os.fdopen(os.open(output, flags, 0o600), "w", encoding="utf-8") as f:
        f.write(body)
    return {
        "schema": SCHEMA, "source_count": 14, "existing_public_links": 5,
        "held_new_links": 9, "authorized_new_links": 0,
        "chronology_exception_still_held": True,
        "private_preview_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "published": False, "source_body_read": False,
        "production_admitted": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--private-preview-out", required=True)
    p.add_argument("--explicit-no-publish", action="store_true")
    args = p.parse_args(argv)
    if not args.explicit_no_publish:
        p.error("--explicit-no-publish required")
    try:
        result = create(args.private_preview_out)
    except (OSError, ValueError, KoreaGateHold):
        print(json.dumps({"result": "HOLD", "published": False}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
