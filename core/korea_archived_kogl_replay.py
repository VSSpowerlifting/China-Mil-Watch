"""Read-only authenticated Korea KOGL Type 1 mark replay from saved originals.

Source Git inventory and HWPX replay are performed by the established
stage_korea_production_candidates bridge. This adapter independently checks
the exact original HTML *bytes* and the article-local text-only license mark.
It does NOT approve third-party content, authenticate today's publisher policy,
sign editorial reviews, call a model, or publish anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
from scripts import stage_korea_production_candidates as stage

IDENT = re.compile(r"korea-policy:[0-9]{9}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_HTML = 10_000_000
MARK = "텍스트에 한하여 공공누리 제1유형"
NOTICE = "출처표시"
MEDIA = "사진·이미지·일러스트·동영상"
SCHEMA = "ipr-korea-archived-kogl-text-mark-replay/1"


class MarkHold(ValueError):
    """Fixed codes: never include source text or HTML in exceptions."""


def need(value, reason):
    if not value:
        raise MarkHold(reason)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def inspect_captured_mark(html_bytes, expected_url):
    """Prove article-local KOGL Type 1 *text* marking, never full-file rights."""
    need(type(html_bytes) is bytes and 0 < len(html_bytes) <= MAX_HTML,
         "publisher_html_capture_missing_or_oversize")
    try:
        html_text = html_bytes.decode("utf-8", "strict")
    except UnicodeError:
        raise MarkHold("publisher_html_not_utf8") from None
    soup = BeautifulSoup(html_text, "html.parser")
    canonical = soup.select('link[rel="canonical"]')
    need(len(canonical) == 1 and canonical[0].get("href") == expected_url,
         "captured_publisher_article_identity_mismatch")
    wrappers = soup.select("div.kogl_wrap")
    need(len(wrappers) == 1, "article_specific_license_wrapper_missing")
    types = wrappers[0].select(".type")
    need(len(types) == 1, "article_license_type_ambiguous")
    strong = types[0].select("span strong")
    need(len(strong) == 1, "article_license_text_marker_missing")
    marked = " ".join(strong[0].get_text(" ", strip=True).split())
    need(MARK in marked and NOTICE in marked,
         "article_not_marked_kogl_type1_text_only")
    images = types[0].select("img")
    need(len(images) == 1
         and images[0].get("src") == "/images/v5/common/open_type_01.png"
         and "1유형" in images[0].get("alt", "")
         and NOTICE in images[0].get("alt", ""),
         "article_license_badge_conflicts_with_text")
    warnings = wrappers[0].select(".info p")
    need(len(warnings) >= 1
         and any(MEDIA in w.get_text(" ", strip=True)
                 and "허락" in w.get_text(" ", strip=True) for w in warnings),
         "nontext_third_party_exception_notice_missing")
    need(not any(label in wrappers[0].get_text(" ", strip=True)
                 for label in ("제2유형", "제3유형", "제4유형")),
         "conflicting_article_license_markers")
    return {"mark": "KOGL_TYPE_1_TEXT", "mark_sha256": digest(marked.encode()),
            "scope": "original_text_only", "whole_hwpx_licensed": False,
            "media_licensed": False}


def _capture(source_checkout, row):
    stamp = row["publisher_html_sha256"]
    need(type(stamp) is str and HEX.fullmatch(stamp) is not None,
         "publisher_html_hash_invalid")
    path = Path(source_checkout) / "state" / "captures" / (stamp + ".bin")
    need(path.is_file() and not path.is_symlink()
         and 0 < path.stat().st_size <= MAX_HTML,
         "publisher_html_capture_missing_or_oversize")
    content = path.read_bytes()
    need(digest(content) == stamp, "publisher_html_capture_hash_mismatch")
    return inspect_captured_mark(content, row["canonical_source_url"])


def _authenticated(source_checkout):
    # stage.build checks the frozen Git ancestor, clean tree, all source-capture
    # hashes and independent re-extraction of EVERY original HWPX.
    packet = stage.build(str(source_checkout))
    originals = stage._rows(Path(source_checkout))
    by_identity = {r["source_identity"]: r for r in originals}
    need(len(originals) == len(by_identity) == len(packet["records"]),
         "original_source_roster_inconsistent")
    return packet, by_identity


def verify_archive(source_checkout):
    """Examine all authenticated originals; return counts/hashes, no bodies."""
    packet, originals = _authenticated(source_checkout)
    verified = []
    for row in packet["records"]:
        identity = row["source_identity"]
        need(IDENT.fullmatch(identity) is not None and identity in originals,
             "archived_korea_source_identity_invalid")
        original = originals[identity]
        need(digest(original["text_original"].encode("utf-8"))
             == row["original_text_sha256"]
             and digest(original["title_original"].encode("utf-8"))
             == row["original_title_sha256"]
             and original["capture_sha256"] == row["publisher_html_sha256"],
             "archived_source_not_version_bound")
        mark = _capture(source_checkout, row)
        verified.append((row, mark))
    return {
        "schema": SCHEMA,
        "status": "EVIDENCE_ONLY_NO_PUBLICATION",
        "source_git_commit": packet["source_git_commit"],
        "source_original_count": len(verified),
        "text_only_type1_marks_verified": len(verified),
        "editorial_exception_count": sum(
            r["editorial_exception"] is not None for r, _ in verified),
        "full_hwpx_redistribution_authorized": False,
        "translation_review_complete": False,
        "current_policy_authenticated": False,
        "item_exception_review_complete": False,
        "production_records_written": 0,
        "public_files_written": 0,
    }


class KoreaArchivedMarkAdapter:
    """Trusted source + item-mark callbacks for standing_source_rights.

    Deliberately does NOT supply the standing-policy or item-exception
    callbacks. Those require independent current policy and content checks.
    """

    def __init__(self, source_checkout, identity):
        need(type(identity) is str and IDENT.fullmatch(identity) is not None,
             "source_identity_outside_korea_scope")
        self.checkout = Path(source_checkout)
        packet, originals = _authenticated(self.checkout)
        selected = [r for r in packet["records"] if r["source_identity"] == identity]
        need(len(selected) == 1 and identity in originals,
             "verified_korea_source_not_found")
        row = selected[0]
        need(row["editorial_exception"] is None,
             "source_has_unresolved_editorial_exception")
        self._mark = _capture(self.checkout, row)
        self._identity = identity
        self._version = row["candidate_version_sha256"]
        self._commit = packet["source_git_commit"]
        self.source = {
            "desk": "korea", "source_family": "kr_policy_mnd_releases",
            "source_identity": identity,
            "official_url": row["canonical_source_url"],
            "source_git_commit": self._commit,
            "source_capture_sha256": row["publisher_html_sha256"],
            "publisher_posted_date": row["publisher_posted_date"],
            "language": "ko",
        }

    def _fresh(self):
        packet, originals = _authenticated(self.checkout)
        need(packet["source_git_commit"] == self._commit,
             "original_git_capture_changed")
        selected = [r for r in packet["records"]
                    if r["source_identity"] == self._identity]
        need(len(selected) == 1 and self._identity in originals
             and selected[0]["candidate_version_sha256"] == self._version
             and selected[0]["editorial_exception"] is None,
             "original_source_version_changed")
        row = selected[0]
        need(row["publisher_html_sha256"] ==
             self.source["source_capture_sha256"]
             and row["canonical_source_url"] == self.source["official_url"],
             "original_capture_identity_changed")
        need(_capture(self.checkout, row) == self._mark,
             "publisher_license_mark_changed")
        return row, originals[self._identity]

    def source_replay(self, source):
        need(source == self.source, "source_callback_identity_mismatch")
        row, original = self._fresh()
        need(digest(original["text_original"].encode("utf-8"))
             == row["original_text_sha256"],
             "original_text_changed_after_replay")
        return {
            "source_git_commit": self._commit,
            "source_capture_sha256": row["publisher_html_sha256"],
            "entire_clean_original_text_sha256": row["original_text_sha256"],
            "original_custody_authenticated": True,
            "source_text_complete": True,
        }

    def item_license_replay(self, source, license_kind):
        need(source == self.source and license_kind == "KOGL_TYPE_1_TEXT",
             "item_license_callback_identity_mismatch")
        self._fresh()
        return True

    def read_original_text_private(self):
        """Return captured UTF-8 only to the local operator; never print it."""
        _, original = self._fresh()
        return original["text_original"].encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only Korean archived KOGL audit")
    parser.add_argument("--source-checkout", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(verify_archive(args.source_checkout), sort_keys=True))
    except (MarkHold, stage.IntakeHold, OSError, UnicodeError, ValueError):
        print(json.dumps({"schema": SCHEMA, "status": "HOLD",
                          "public_files_written": 0,
                          "production_records_written": 0}, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
