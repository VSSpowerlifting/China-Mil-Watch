"""Nine owner-approved OUTBOUND Korea MND URLs; never source records.

Requires exact held fourteen-source checksum/KOGL review manifests and keeps
the original five public bibliography records, IDs and formatting intact.
Authorizes ONLY a static government link to each of nine existing page IDs.
"""
from pathlib import Path

from core.korea_reference_gate import ROOT, KoreaGateHold, load_json, require
from scripts.preview_korea_fourteen_official_links import (
    validate as held_review, MANIFEST as HELD_MANIFEST,
)

INDEX = ROOT / "research/korea_additional_public_official_links_2026-10-15.json"
SCHEMA = "ipr-korea-additional-public-official-links/1"
COMMIT = "0595f0fd29b769cbab5dd57c2ef57af174237a67"
EXPECTED = (
    "156784787", "156784873", "156785005", "156785015",
    "156785058", "156785160", "156785161", "156785162",
    "156785190",
)
KEYS = {
    "schema", "release_mode", "owner_scope", "source_family",
    "state_commit", "existing_five_unchanged",
    "separate_owner_public_link_approval",
    "korean_semantic_or_media_rights_approval",
    "production_desk_admission", "model_or_email_admission",
    "source_ids",
}
OWNER_SCOPE = (
    "approved-2026-10-15-nine-official-mnd-urls-"
    "no-document-bodies-or-interpretation"
)


def load_additional_korea_official_links(path=INDEX):
    path = Path(path)
    require(path == INDEX and not path.is_symlink(),
            "official Korea link authorization must use pinned manifest")
    data = load_json(path, size=4096)
    require(type(data) is dict and set(data) == KEYS,
            "Korea additional public links manifest has unsafe fields")
    require(data["schema"] == SCHEMA
            and data["release_mode"] == "official-outbound-links-only"
            and data["owner_scope"] == OWNER_SCOPE
            and data["source_family"] == "kr_policy_mnd_releases"
            and data["state_commit"] == COMMIT
            and data["existing_five_unchanged"] is True
            and data["separate_owner_public_link_approval"] is True
            and data["korean_semantic_or_media_rights_approval"] is False
            and data["production_desk_admission"] is False
            and data["model_or_email_admission"] is False
            and type(data["source_ids"]) is list
            and tuple(data["source_ids"]) == EXPECTED,
            "Korea public release exceeds nine owner-approved link IDs")
    # Re-verify exactly the original 14 HWPX identities and publisher
    # HTML copyright-mark digests, not a changed or future collector state.
    originals, existing = held_review()
    indexed = {x["news_id"]: x for x in originals}
    pinned = load_json(HELD_MANIFEST, size=16000)
    locked = {x["news_id"]: x for x in pinned["entries"]}
    require(len(indexed) == len(locked) == 14 and len(existing) == 5
            and set(indexed) == set(locked)
            and set(EXPECTED) == (set(indexed) - set(existing)),
            "official link release disagrees with actual source roster")
    for article_id, row in indexed.items():
        known = locked[article_id]
        require(row["source_url"] ==
                "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + article_id
                and row["source_url"] == known["source_url"]
                and row["hwpx_capture_sha256"] == known["hwpx_capture_sha256"]
                and row["publisher_html_capture_sha256"] ==
                    known["publisher_html_capture_sha256"],
                "reviewed Korea original or license identity changed")
    return [
        {
            "source_identity": "korea-policy:" + article_id,
            "source_url": indexed[article_id]["source_url"],
            "neutral_label": "MND official press release " + article_id,
            "editorial_hold": (
                "Original contains an unresolved excavation-year discrepancy; "
                "no factual account is endorsed."
                if article_id == "156785161" else ""
            ),
        }
        for article_id in EXPECTED
    ]
