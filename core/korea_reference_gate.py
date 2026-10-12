"""Offline, fail-closed Korea Desk review-to-preview gate.

A positive machine byte audit or publisher license never becomes human approval.
No Git or publisher access, production ingest, registry writes or deployment.
The only export is a local metadata-only workbench or privately gated preview.
"""
from __future__ import annotations

import html
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "research" / "korea_reference_candidates.json"
STATE_BRANCH = "shadow/korea-policy-briefing"
STATE_SHA = "dcb43b9c4edb471d6def5876701ec4a2e39d5264"
CANDIDATE_SCHEMA = "ipr-korea-reference-candidates/1"
APPROVAL_SCHEMA = "ipr-korea-source-admission/1"
ALLOWED_IDS = frozenset({"156783602", "156783708", "156784196", "156784297", "156784652"})
SHA = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
LICENSE = "https://www.korea.kr/guide/copyRight.do"
FIELDS = {"source_identity", "source_slug", "source_url", "title_original",
          "language", "published_date", "document_distribution_date",
          "content_sha256", "document_capture_sha256", "issuer", "publisher"}


class KoreaGateHold(ValueError):
    """No public or private preview may infer approval from held evidence."""


def require(condition, why):
    if not condition:
        raise KoreaGateHold(why)


def unique_pairs(pairs):
    result = {}
    for key, val in pairs:
        require(key not in result, "duplicate JSON key " + key)
        result[key] = val
    return result


def no_constant(value):
    raise KoreaGateHold("non-finite JSON is prohibited")


def load_json(path, *, size=131072):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "missing or symlinked evidence file")
    require(path.stat().st_size <= size, "oversized evidence file")
    try:
        return json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=unique_pairs, parse_constant=no_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise KoreaGateHold("malformed evidence JSON") from exc


def day(value):
    require(isinstance(value, str), "date must be string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise KoreaGateHold("invalid date") from exc
    require(parsed.isoformat() == value, "date must be ISO canonical")
    return parsed


def timestamp(value, now):
    require(isinstance(value, str) and UTC.fullmatch(value) is not None,
            "approval time must be explicit canonical UTC second")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise KoreaGateHold("invalid approval time") from exc
    require(moment <= now, "future approval time refused")
    return moment


def identity_and_url(entry):
    sid = entry["source_identity"]
    require(isinstance(sid, str) and sid.startswith("korea-policy:"),
            "source identity is not Korean Policy Briefing")
    ident = sid.partition(":")[2]
    require(ident in ALLOWED_IDS, "source outside five-record pilot")
    expected = "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + ident
    require(entry["source_url"] == expected, "noncanonical or mismatched official URL")
    # String equality is deliberate: no host alias, extra query keys or redirects.
    return ident


def load_candidates(path=CANDIDATES):
    data = load_json(path)
    require(isinstance(data, dict) and set(data) ==
            {"schema", "state_branch", "state_commit", "entries"},
            "candidate inventory structure changed")
    require(data["schema"] == CANDIDATE_SCHEMA
            and data["state_branch"] == STATE_BRANCH
            and data["state_commit"] == STATE_SHA,
            "candidate inventory not bound to reviewed Korean shadow state")
    rows = data["entries"]
    require(isinstance(rows, list) and len(rows) == 5,
            "pilot inventory must have precisely five known candidates")
    ids = set()
    for e in rows:
        require(isinstance(e, dict) and set(e) == FIELDS,
                "unexpected candidate fields (possible source text leak)")
        ident = identity_and_url(e)
        require(ident not in ids, "duplicate Korean document")
        ids.add(ident)
        require(e["source_slug"] == "kr_policy_mnd_releases"
                and e["language"] == "ko"
                and e["issuer"] == "국방부"
                and e["publisher"] == "대한민국 정책브리핑",
                "issuer or source-family mismatch")
        require(isinstance(e["title_original"], str)
                and 8 <= len(e["title_original"].strip()) <= 200
                and e["title_original"] == e["title_original"].strip()
                and not any(ord(c) < 32 for c in e["title_original"]),
                "invalid original Korean title")
        pub = day(e["published_date"])
        distributed = day(e["document_distribution_date"])
        require(distributed <= pub, "source release date after portal publication")
        require(all(isinstance(e[k], str) and SHA.fullmatch(e[k])
                    for k in ("content_sha256", "document_capture_sha256")),
                "original source and captured HWPX hashes required")
    require(ids == ALLOWED_IDS, "five-record allowlist altered")
    missile = next(r for r in rows if r["source_identity"].endswith("156784297"))
    require(missile["published_date"] == "2026-10-06"
            and missile["document_distribution_date"] == "2026-10-04",
            "MND statement's October 4 versus October 6 chronology lost")
    return sorted(rows, key=lambda x: (x["published_date"], x["source_identity"]),
                  reverse=True)


def exact_keys(obj, fields, what):
    require(isinstance(obj, dict) and set(obj) == set(fields),
            what + " must have exact fields")


def signed_section(value, fields, now, what):
    exact_keys(value, fields, what)
    who = value["reviewer"]
    require(isinstance(who, str) and 3 <= len(who.strip()) <= 100
            and who == who.strip() and not any(ord(c) < 32 for c in who),
            "real named " + what + " reviewer required")
    return timestamp(value["reviewed_at_utc"], now)


def approve(rows, approvals_file, *, now=None):
    """Structural evidence checks; DOES NOT authenticate signatures or identity.

    Actual publisher/owner verifies the human and rights reviewers externally.
    """
    if approvals_file is None:
        return []
    evidence = load_json(approvals_file)
    exact_keys(evidence, ("schema", "state_commit", "entries"), "approval packet")
    require(evidence["schema"] == APPROVAL_SCHEMA and
            evidence["state_commit"] == STATE_SHA,
            "approval packet is for another source snapshot")
    entries = evidence["entries"]
    require(isinstance(entries, list) and len(entries) <= 5,
            "approval entries exceed bounded pilot")
    now = now or datetime.now(timezone.utc)
    indexed = {r["source_identity"]: r for r in rows}
    seen = set()
    out = []
    for item in entries:
        exact_keys(item, ("source_identity", "content_sha256",
                          "document_capture_sha256", "human_korean_review",
                          "source_rights_review", "owner_publication_approval",
                          "english_description"), "source approval")
        ident = item["source_identity"]
        require(isinstance(ident, str) and ident in indexed and ident not in seen,
                "unknown or duplicate source approval")
        seen.add(ident)
        row = indexed[ident]
        require(item["content_sha256"] == row["content_sha256"]
                and item["document_capture_sha256"] == row["document_capture_sha256"],
                "approval refers to different original text or HWPX bytes")
        human = item["human_korean_review"]
        rights = item["source_rights_review"]
        owner = item["owner_publication_approval"]
        ht = signed_section(human,
                            ("reviewer", "reviewed_at_utc", "rendered_hwpx_compared",
                             "korean_semantics_verified", "names_dates_verified",
                             "distribution_versus_posting_checked"),
                            now, "Korean-language")
        require(all(human[k] is True for k in (
            "rendered_hwpx_compared", "korean_semantics_verified",
            "names_dates_verified", "distribution_versus_posting_checked")),
            "original-language review is not complete")
        rt = signed_section(rights,
                            ("reviewer", "reviewed_at_utc", "page_notice_verified",
                             "attribution_required", "text_only",
                             "nontext_media_excluded", "intended_use_approved"),
                            now, "source-rights")
        require(all(rights[k] is True for k in (
            "page_notice_verified", "attribution_required", "text_only",
            "nontext_media_excluded", "intended_use_approved")),
            "source-specific text/attachment rights review incomplete")
        ot = signed_section(owner, ("reviewer", "reviewed_at_utc",
                                   "explicit_approval_for_reference_only"), now,
                            "owner/editor")
        require(owner["explicit_approval_for_reference_only"] is True,
                "owner did not authorize this specific reference")
        require(ht <= ot and rt <= ot, "owner decision predates required review")
        desc = item["english_description"]
        require(isinstance(desc, str) and 30 <= len(desc.strip()) <= 320
                and desc == desc.strip()
                and not any(ord(c) < 32 or c in "<>" for c in desc),
                "description empty, HTML-shaped or too long")
        out.append({**row, "english_description": desc,
                    "reviewed_on": ot.date().isoformat(),
                    "source_rights": "KOGL Type 1 — attributed text only"})
    return sorted(out, key=lambda x: (x["published_date"], x["source_identity"]),
                  reverse=True)


def render(rows, *, mode, accepted=()):
    require(mode in ("workbench", "release-preview"), "unknown mode")
    approved = {r["source_identity"] for r in accepted}
    visible = rows if mode == "workbench" else list(accepted)
    pieces = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='robots' content='noindex,nofollow'>",
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">",
        "<title>Korea Desk — PRIVATE " + ("review workbench" if mode == "workbench"
                                    else "reference preview") + "</title>",
        "<style>body{font:16px/1.55 system-ui,sans-serif;max-width:890px;margin:3rem auto;padding:0 1.2rem;color:#172b36}article{padding:1.1rem 0;border-top:1px solid #beced5}small{color:#495f6d}a{color:#07537a} .hold{color:#8b301d;font-weight:700}.ok{color:#175e45;font-weight:700}</style>",
        "</head><body><h1>South Korea — PRIVATE " + (
            "source review workbench" if mode == "workbench" else "approved reference preview") + "</h1>",
        "<p>Five-record Ministry of National Defense republication pilot. "
        "Government Policy Briefing is the publisher, not an independent corroborating source. "
        "This file is not a live public Korea Desk or deployment approval.</p>",
        "<p>Preserved source commit: <code>" + STATE_SHA + "</code>. "
        "Source-only text marked KOGL Type 1 with attribution; "
        "no attachment, image or original body is reproduced.</p>",
    ]
    if mode == "workbench":
        pieces.append("<p class='hold'>UNSIGNED items remain held. The workbench "
                      "is a private reference list, not a reviewer signoff.</p>")
    if not visible:
        pieces.append("<p class='hold'>No human/rights/owner-approved rows. Nothing eligible for publication.</p>")
    for r in visible:
        title = html.escape(r["title_original"], quote=True)
        url = html.escape(r["source_url"], quote=True)
        sid = html.escape(r["source_identity"], quote=True)
        permitted = r["source_identity"] in approved
        pieces.extend([
            "<article><p class='" + ("ok" if permitted else "hold") + "'>" +
            ("STRUCTURALLY APPROVED FOR PRIVATE PREVIEW" if permitted else "HOLD — human review pending") + "</p>",
            "<h2><a lang='ko' rel='noopener noreferrer' href='" + url + "'>" +
            title + "</a></h2>",
            "<p><small>" + sid + " · Portal: " + r["published_date"] +
            " · MND distribution: " + r["document_distribution_date"] +
            " · Issuer: Republic of Korea Ministry of National Defense" +
            " · Publisher: Republic of Korea Policy Briefing</small></p>",
            "<p><small>Archived Korean text SHA-256: " +
            html.escape(r["content_sha256"], quote=True) + "</small></p>",
        ])
        if permitted:
            pieces.append("<p>" + html.escape(r["english_description"], quote=True) + "</p>")
        pieces.append("</article>")
    pieces.append("<p><a rel='noopener noreferrer' href='" + LICENSE +
                  "'>Publisher copyright policy</a>. Machine and JSON checks cannot "
                  "authenticate a reviewer or authorize public deployment.</p>")
    pieces.append("</body></html>")
    return "\n".join(pieces)


def write_private(destination, content):
    dest = Path(destination).expanduser().absolute()
    root = ROOT.resolve()
    require(dest.parent.is_dir() and not dest.parent.is_symlink()
            and not dest.is_symlink() and not dest.exists()
            and root != dest.resolve() and root not in dest.resolve().parents,
            "output must be a new private path outside repository")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(dest), flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return str(dest)
