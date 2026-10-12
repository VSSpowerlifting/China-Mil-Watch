"""Prepare ACTUAL five archived Korean HWPX originals for independent human review.

This is a private local handoff, NEVER a publication, signoff or CI artifact.
Reads one immutable existing Git shadow state; no publisher requests or writes
to shadow, repository, output/ or production. Originals stay on local 0700 disk.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from core.korea_reference_gate import (
    APPROVAL_SCHEMA, ROOT, STATE_SHA, KoreaGateHold, load_candidates, require,
)
from scripts import audit_korea_source_fidelity as fidelity
from scripts import review_desk_shadow as formal

RISKS = {
    "156783602": (
        "전시회 개최 *예정*과 실제 개최 확인을 구분하십시오.",
        "미수습 전사자 약 12만 명의 수치는 국방부 인용으로 표시하십시오.",
        "전시 이미지, 피규어 사진, QR 콘텐츠의 권리를 본문 텍스트와 별도로 검토하십시오.",
    ),
    "156783708": (
        "해군 대비태세 점검과 청해부대의 아덴만 파병 준비를 구분하십시오.",
        "10월 초 *투입 예정*을 이미 배치 완료한 사실로 번역하지 마십시오.",
        "장관·해군작전사령부·청해부대의 정식 명칭을 검토하십시오.",
    ),
    "156784196": (
        "캠프 험프리스 방문과 제이비어 브런슨 장군 접견의 일시를 확인하십시오.",
        "연합방위태세 *재확인*을 신규 합의, 병력 증원 또는 협정 체결로 과장하지 마십시오.",
        "한미연합사·주한미군사·유엔사의 기관별 명칭을 확인하십시오.",
    ),
    "156784297": (
        "국방부 원문 배포일 10월 4일과 정책브리핑 게시일 10월 6일을 각각 확인하십시오.",
        "탐지·요격 *가능 수준으로 평가*를 실제 요격 성공 사실로 바꾸지 마십시오.",
        "발사 횟수·탄종·발사 시각 및 국제법적 결론을 임의로 추가하지 마십시오.",
    ),
    "156784652": (
        "조선·방산협력 및 무인·자율체계에 관한 *논의*와 확정 사업을 구분하십시오.",
        "한화 필리조선소 관련 문장에 계약 체결·투자 약정이 있는지 원문으로 확인하십시오.",
        "미 상원의원과 국방부 장관의 실명 및 기관명을 대조하십시오.",
    ),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_pinned_rows(state):
    """Read exact shadow SQLite snapshot without creating SQLite WAL/SHM."""
    db = state / "shadow.db"
    require(db.is_file() and not db.is_symlink(), "shadow database absent")
    con = sqlite3.connect(db.as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        con.row_factory = sqlite3.Row
        rows = []
        for r in con.execute("SELECT * FROM shadow_records ORDER BY source_identity"):
            row = dict(r)
            metadata = json.loads(row.pop("metadata_json"))
            require(isinstance(metadata, dict), "unstructured preserved metadata")
            row["metadata"] = metadata
            rows.append(row)
        require(len(rows) == 5, "pinned Korea snapshot is not exactly five originals")
        require(len({r["source_identity"] for r in rows}) == len(rows),
                "duplicate preserved source identity")
        return {r["source_identity"]: r for r in rows}
    finally:
        con.close()


def confirm_original(candidate, row, state):
    """Machine parity required, still not human-language or rights clearance."""
    result = fidelity.source_compare(row, state)
    require(result["machine_fidelity"] == "PASS",
            "archived original HWPX audit failed for " + candidate["source_identity"])
    for expected_key, stored_key in (
        ("source_identity", "source_identity"), ("source_url", "url"),
        ("source_slug", "source_slug"), ("title_original", "title_original"),
        ("published_date", "published_date"),
        ("content_sha256", "content_sha256"),
    ):
        require(candidate[expected_key] == row[stored_key],
                "candidate and preserved original differ: " + expected_key)
    require(candidate["document_capture_sha256"] ==
            row["metadata"]["document_capture_sha256"],
            "archived HWPX differs from pinned reviewer candidate")
    require(candidate["issuer"] == row["metadata"]["issuer"] and
            candidate["publisher"] == row["metadata"]["publisher"] and
            row["language_tag"] == "ko",
            "wrong original-language provenance")
    hwpx = (state / "captures" /
            (candidate["document_capture_sha256"] + ".bin"))
    original = hwpx.read_bytes()
    text = row["text_original"]
    require(sha(original) == candidate["document_capture_sha256"] and
            sha(text.encode("utf-8")) == candidate["content_sha256"],
            "original content changed since audit")
    require(len(original) <= 10_000_000 and len(text) <= 150000,
            "unexpected archived original size")
    return original, text


def make_blank(candidate):
    """Deliberately INVALID for source admission until humans supply checks."""
    return {
        "source_identity": candidate["source_identity"],
        "content_sha256": candidate["content_sha256"],
        "document_capture_sha256": candidate["document_capture_sha256"],
        "evidence_anchors": [],
        "human_korean_review": {
            "reviewer": "",
            "reviewed_at_utc": None,
            "rendered_hwpx_compared": False,
            "korean_semantics_verified": False,
            "names_dates_verified": False,
            "distribution_versus_posting_checked": False,
            "evidence_anchors_checked": False,
        },
        "source_rights_review": {
            "reviewer": "",
            "reviewed_at_utc": None,
            "page_notice_verified": False,
            "attribution_required": False,
            "text_only": False,
            "nontext_media_excluded": False,
            "intended_use_approved": False,
        },
        "owner_publication_approval": {
            "reviewer": "",
            "reviewed_at_utc": None,
            "explicit_approval_for_reference_only": False,
        },
        "english_description": "",
    }


def original_line_index(candidate, text):
    """Private no-body line-hash index for 1-based physical .ko.txt lines."""
    require(isinstance(text, str) and
            sha(text.encode("utf-8")) == candidate["content_sha256"],
            "line index must match exact pinned Korean text SHA")
    lines = [
        {"line_number": number, "line_sha256": sha(line.encode("utf-8"))}
        for number, line in enumerate(text.splitlines(), 1)
        if line.strip()
    ]
    require(bool(lines), "archived original Korean text has no nonblank lines")
    return {"schema": "ipr-korea-original-line-index/1",
            "source_identity": candidate["source_identity"],
            "content_sha256": candidate["content_sha256"],
            "state_commit": STATE_SHA, "lines": lines}


def checklist(candidate):
    ident = candidate["source_identity"].partition(":")[2]
    lines = [
        "# SOURCE HOLD — independent Korean original and rights review",
        "",
        "**Document:** " + candidate["source_identity"],
        "**Source:** " + candidate["source_url"],
        "**원제:** " + candidate["title_original"],
        "**원문 발행 기관:** " + candidate["issuer"],
        "**포털 재게시 기관:** " + candidate["publisher"],
        "**정책브리핑 게시일:** " + candidate["published_date"],
        "**국방부 문서 배포일(검증 필요):** " + candidate["document_distribution_date"],
        "**원문 텍스트 SHA-256:** " + candidate["content_sha256"],
        "**원본 HWPX SHA-256:** " + candidate["document_capture_sha256"],
        "**고정 원본 커밋:** " + STATE_SHA,
        "",
        "## Korean-language reviewer — MUST inspect local files",
        "",
        "- [ ] Open matching `originals/" + ident + ".hwpx` in a trusted Korean-capable viewer.",
        "- [ ] Compare all headings, paragraphs, tables, footnotes, names, event dates and reading order to `originals/" + ident + ".ko.txt`.",
        "- [ ] Confirm official publisher page, original issuing institution, document distribution date and portal posting date SEPARATELY.",
        "- [ ] Check modality: announcements, plans, readiness assessments and discussions are not completed outcomes.",
        "- [ ] Record every correction in controlled reviewer notes, keeping raw source copies out of GitHub.",
        "- [ ] For each proposed English claim, verify the exact 1-based line_number and line_sha256 from reviews/" + ident + ".line-hashes.json against .ko.txt and rendered HWPX.",
        "- [ ] Classify the original statement as announcement, plan, reported_action, assessment or discussion and privately explain its relevance to the English wording.",
        "",
        "### Source-specific Korean review flags",
        "",
    ]
    lines.extend("- [ ] " + item for item in RISKS[ident])
    lines += [
        "",
        "## Source-specific reuse rights — separate decision",
        "",
        "- [ ] Reopen the exact publisher page at the canonical URL above.",
        "- [ ] Confirm KOGL Type 1 **text-only** label and legally adequate attribution for the *proposed use*.",
        "- [ ] Examine the archived HWPX for excluded photographs, graphics, annexes, QR media or third-party material; do not infer they are licensed.",
        "- [ ] Confirm final output will contain only original human-edited short English descriptions, bibliographic identity and outbound official links.",
        "- [ ] Record whether any element requires additional owner permission; HOLD when uncertain.",
        "- [ ] Review official publisher rights policy: https://www.korea.kr/guide/copyRight.do",
        "",
        "## Approval (NOT AUTOMATIC)",
        "",
        "This file is a BLANK checklist, not a decision. A named independent Korean",
        "reviewer, separate designated rights reviewer and IPR owner must complete",
        "and verify the corresponding fields in `approvals_UNFILLED.json` **offline**.",
        "A JSON name/date alone cannot authenticate a reviewer or establish consent.",
        "The owner may choose to exclude this individual record for any reason.",
        "",
    ]
    return "\n".join(lines)


def private_write(path, payload):
    require(not path.exists(), "refuse overwrite private reviewer file")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(path), flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)


def output_ok(path):
    path = Path(path).expanduser()
    require(path.is_absolute() and not path.exists() and not path.is_symlink()
            and path.parent.is_dir() and not path.parent.is_symlink(),
            "output must be an unused absolute directory with a real parent")
    dest = path.resolve()
    root = ROOT.resolve()
    require(dest != root and root not in dest.parents and
            dest not in root.parents,
            "private source originals cannot be written into repository")
    return path


def assemble(candidates, records, state, destination):
    """Verify all originals BEFORE creating any reviewer output directory."""
    data = []
    require(len(candidates) == 5 and len(records) == 5,
            "five pinned sources required")
    require({r["source_identity"] for r in candidates} == set(records),
            "candidate/original record identity mismatch")
    for entry in candidates:
        original, text = confirm_original(entry, records[entry["source_identity"]], state)
        data.append((entry, original, text))
    destination = output_ok(destination)
    destination.mkdir(mode=0o700)
    try:
        originals = destination / "originals"
        reviews = destination / "reviews"
        originals.mkdir(mode=0o700)
        reviews.mkdir(mode=0o700)
        unsigned = []
        receipt = []
        for item, raw, text in data:
            ident = item["source_identity"].partition(":")[2]
            private_write(originals / (ident + ".hwpx"), raw)
            private_write(originals / (ident + ".ko.txt"), text.encode("utf-8"))
            private_write(reviews / (ident + ".md"), checklist(item).encode("utf-8"))
            private_write(reviews / (ident + ".line-hashes.json"),
                          (json.dumps(original_line_index(item, text),
                                      ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
            unsigned.append(make_blank(item))
            receipt.append({
                "source_identity": item["source_identity"],
                "text_sha256": item["content_sha256"],
                "hwpx_sha256": item["document_capture_sha256"],
                "original_document_parity": "PASS",
                "qualified_human_approval": False,
                "source_rights_approval": False,
                "owner_publication_approval": False,
            })
        packet = {"schema": APPROVAL_SCHEMA, "state_commit": STATE_SHA,
                  "entries": unsigned}
        private_write(destination / "approvals_UNFILLED.json",
                      (json.dumps(packet, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        intro = (
            "# PRIVATE — Korea five-original reviewer package (NOT a publication)\n\n"
            "Contains actual original government-republished HWPX documents and extracted "
            "original-Korean text. **DO NOT commit, upload to public Actions artifacts, "
            "email publicly, or rehost these originals.** Access may be subject to rights "
            "outside the publisher text-only KOGL notice.\n\n"
            "For each source, compare `originals/<newsId>.hwpx` and "
            "`originals/<newsId>.ko.txt` with the official release page. "
            "Read `reviews/<newsId>.md` and private `reviews/<newsId>.line-hashes.json` "
            "to locate original Korean lines supporting each English claim. "
            "Line hashes are pointers, not proof of an accurate translation. "
            "Then record independent Korean-language and source-specific rights "
            "decisions. ALL approval fields in "
            "`approvals_UNFILLED.json` are FALSE/BLANK. "
            "Only the real reviewers and publisher/owner may authenticate signoffs; "
            "the JSON gate is structural, not a cryptographic identity service.\n\n"
            "State SHA: `" + STATE_SHA + "`\n"
            "No new source collecting, production release, site publication or "
            "automatic Sunday Brief source admission is authorized.\n"
        )
        private_write(destination / "README_PRIVATE.md", intro.encode("utf-8"))
        summary = {
            "schema": "ipr-korea-local-human-review-package/1",
            "state_commit": STATE_SHA,
            "records": receipt,
            "reviewer_approvals": 0,
            "public_release_authorized": False,
            "source_bodies_in_public_artifact": False,
            "production_data_modified": False,
        }
        private_write(destination / "receipt.json",
                      (json.dumps(summary, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    except BaseException:
        shutil.rmtree(destination)
        raise
    return summary


def run(state_repo, commit, destination):
    require(commit == STATE_SHA, "must use the exact frozen five-original state commit")
    repo = Path(state_repo).expanduser()
    require(repo.is_absolute() and repo.is_dir() and not repo.is_symlink(),
            "state repo must be an existing nonsymlink absolute Git repo")
    destination = output_ok(destination)
    # Validate branch ancestry and all git blobs through pre-existing formal
    # export controls, rather than trusting a copied unversioned SQLite file.
    with tempfile.TemporaryDirectory(prefix="ipr-korea-source-originals-") as tmp:
        state_dir = Path(tmp)
        formal.export_commit(repo, commit, "korea", state_dir)
        state = state_dir / "state"
        records = read_pinned_rows(state)
        return assemble(load_candidates(), records, state, destination)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-repo", required=True, type=Path,
                        help="absolute local Git clone containing Korea shadow branch")
    parser.add_argument("--state-commit", required=True,
                        help="exact frozen 40-char state SHA")
    parser.add_argument("--out", required=True, type=Path,
                        help="new secure directory OUTSIDE repository")
    parser.add_argument("--acknowledge-private-originals", action="store_true",
                        help="confirm rights-restricted originals stay local, never public")
    args = parser.parse_args(argv)
    if not args.acknowledge_private_originals:
        parser.error("explicit local original-document handling acknowledgement required")
    try:
        summary = run(args.state_repo, args.state_commit, args.out)
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    # Only metadata-only receipt goes to stdout (source bodies never logged).
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
