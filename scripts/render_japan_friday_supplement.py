"""Offline, unsigned Japan Friday editorial supplement from MOD source leads.

Japan is NOT production-backed; these public official webpages were inspected
externally, NOT captured into the IPR archive. No source record IDs are created.
This script does not network, email, edit databases, call a model, or approve.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKET = ROOT / "research/japan/friday_2026-10-09/official_source_candidates.json"
WINDOW_START = date(2026, 10, 4)
WINDOW_END = date(2026, 10, 9)
REVIEW_CUTOFF = date(2026, 10, 8)
SOURCES = {
    "JP-W41-01": (
        "2026-10-06",
        "https://www.mod.go.jp/en/article/2026/10/5fc631a5d1b2f36a9b697a611082a85af444ea54.html",
        "https://www.mod.go.jp/j/press/news/2026/10/06a.html",
        "japan_indonesia_disaster_relief_completion",
        "primary",
    ),
    "JP-W41-02": (
        "2026-10-06",
        "https://www.mod.go.jp/en/article/2026/10/92045078e2a66f0957658c577e65cb0832261b17.html",
        None, "japan_us_alliance_communications", "secondary",
    ),
    "JP-W41-03": (
        "2026-10-06",
        "https://www.mod.go.jp/en/article/2026/10/310c36ee3042840e8ea24c951cacaa1766cba0a0.html",
        None, "japan_us_alliance_communications", "context",
    ),
    "JP-W41-04": (
        "2026-10-05",
        "https://www.mod.go.jp/en/article/2026/10/1aaec60496e51175d95622df5ffc904a24af6c9c.html",
        None, "japan_us_alliance_communications", "context",
    ),
}
DISABLED_FLAGS = (
    "automatic_friday_writer_includes_japan",
    "allow_model_citation_id_synthesis",
    "email_sent",
    "editorial_inclusion_approved",
    "source_admission_approved",
    "full_original_archive_capture_available",
    "publication_approved",
    "production_mutation",
)
REQUIRED_TRUE_FLAGS = (
    "editorial_supplement_only",
    "may_copy_into_dylan_draft_only_after_independent_review",
)
LINKED_TSU_IKI = {
    "candidate_id": "JP-W41-05",
    "status": "public_official_html_editor_candidate_not_archived",
    "publication_date": "2026-10-05",
    "institution": "Japan Ministry of Defense",
    "language": "ja",
    "url": "https://www.mod.go.jp/j/press/news/2026/10/05a.html",
    "linked_shadow_source_url": "https://www.mod.go.jp/j/press/news/2026/10/05b.pdf",
    "relationship": "Separate same-ministry MOD announcement; not independent institutional corroboration",
    "subject": "Kadena-to-Tsuiki aircraft training relocation",
    "planned_training_start": "2026-10-19",
    "planned_training_end": "2026-10-29",
    "training_relocation_sequence_at_tsuiki": 12,
    "type_ii_aircraft_range": [6, 12],
    "type_ii_days_range": [8, 14],
    "reviewer_verified_full_page": False,
    "editorial_approved": False,
    "ipr_record_id": None,
    "original_capture_sha256": None,
}

EMPTY_ARCHIVE_FIELDS = (
    "first_party_original_capture_sha256", "ipr_record_id",
)
AUTHORITY = "Japan Ministry of Defense"
CLASSES = {"official_press_release", "official_security_dialogue"}
SOURCE_SUPPORT = {
    "JP-W41-01": "english_and_japanese_official_mod_pages_checked",
    "JP-W41-02": "official_mod_english_page_checked",
    "JP-W41-03": "official_mod_english_page_checked",
    "JP-W41-04": "official_mod_english_page_checked",
}


SHADOW_ARCHIVED = {
    "historical_state_commit": "d57f0a94b2134a68b9f13fb35a0a0b8c8a4ffe13",
    "sqlite_git_blob_sha1": "60f126db5a36369ade81f44f12c3a838cddbfb59",
    "source_url": "https://www.mod.go.jp/j/press/news/2026/10/05b.pdf",
    "source_slug": "jp_mod_news_ja",
    "title_original": "日米合同委員会合意について",
    "publication_date_original": "2026-10-05",
    "extracted_body_sha256": "d8ec17263a4465f75f79e03d2096ce82b9094da649d2ee0d7f198778d0cd0eb8",
    "captured_response_sha256": "4788557ba554cd8af8211906174f44fc60eecaa53f46e2c1818b418c2d0d57bf",
    "first_seen_shadow_run": "37404326269-1",
    "agreement_approval_date": "2026-09-17",
    "planned_facility_use_start": "2026-10-19",
    "planned_facility_use_end": "2026-10-29",
    "land_area_m2_approx": 29000,
    "building_area_m2_approx": 11000,
    "text_chars_reported": 580,
}


class JapanBriefError(ValueError):
    """An unsigned Friday candidate misstates its source or privileges."""


def require(ok, why):
    if not ok:
        raise JapanBriefError(why)


def valid_date(s):
    require(type(s) is str and re.fullmatch(r"\d{4}-\d\d-\d\d", s),
            "dates must use calendar-precise YYYY-MM-DD with no inferred time")
    try:
        d = date.fromisoformat(s)
    except ValueError as exc:
        raise JapanBriefError("invalid calendar day") from exc
    require(d.isoformat() == s, "noncanonical date")
    return d


def validate(data):
    require(type(data) is dict and
            data.get("protocol") == "ipr_japan_week41_editorial_supplement_v1" and
            data.get("status") == "unsigned_source_discovery_only_not_in_brief" and
            data.get("reporting_week_start") == WINDOW_START.isoformat() and
            data.get("reporting_friday") == WINDOW_END.isoformat() and
            data.get("timezone") == "Asia/Tokyo" and
            valid_date(data.get("reviewed_as_of")) == REVIEW_CUTOFF,
            "source packet must stay in the October 8/9 bounded handoff")
    require(type(data.get("purpose")) is str and
            "human-edited" in data["purpose"] and
            type(data.get("origin_scope")) is str and
            "do not establish IPR archival capture" in data["origin_scope"],
            "external webpage observation cannot be called archival evidence")
    wf = data.get("workflow")
    require(type(wf) is dict and
            all(wf.get(k) is False for k in DISABLED_FLAGS) and
            all(wf.get(k) is True for k in REQUIRED_TRUE_FLAGS) and
            set(wf) == set(DISABLED_FLAGS) | set(REQUIRED_TRUE_FLAGS),
            "Japan cannot be silently promoted to Friday writer or approved publication")
    require(data.get("no_classification") is True and
            data.get("no_publication") is True,
            "Japan source candidates may not assign topics or publish")
    require(data.get("source_terms_url") == "https://www.mod.go.jp/en/notice.html"
            and type(data.get("rights_note")) is str and
            "third-party" in data["rights_note"],
            "terms, attribution and third-party review cannot be skipped")
    records = data.get("source_candidates")
    require(type(records) is list and len(records) == len(SOURCES),
            "candidate roster changed without separate admission review")
    seen = {}
    for row in records:
        require(type(row) is dict and row.get("candidate_id") in SOURCES and
                row["candidate_id"] not in seen, "unknown or duplicate Japan candidate")
        ident = row["candidate_id"]
        published, url, japanese, group, priority = SOURCES[ident]
        require(row.get("publisher_date") == published and
                row.get("public_source_url") == url and
                row.get("japanese_original_url") == japanese and
                row.get("proposed_group") == group and
                row.get("editorial_priority") == priority and
                row.get("support_class") == SOURCE_SUPPORT[ident],
                ident + ": URL, date, language-pair, support level or grouping changed")
        require(WINDOW_START <= valid_date(published) <= REVIEW_CUTOFF,
                ident + ": source outside the actually inspected period")
        target = urlsplit(url)
        require(target.scheme == "https" and target.hostname == "www.mod.go.jp"
                and not target.query and not target.fragment and
                target.path.startswith("/en/article/2026/10/"),
                ident + ": public source is not an exact MOD article URL")
        require(row.get("institution") == AUTHORITY and
                row.get("page_kind") in CLASSES and row.get("source_language") == "en" and
                type(row.get("title")) is str and len(row["title"]) > 25 and
                type(row.get("provisional_claims")) is list and
                len(row["provisional_claims"]) == 2 and
                all(type(x) is str and len(x) > 50 and "\n" not in x
                    for x in row["provisional_claims"]) and
                type(row.get("caveats")) is list and
                len(row["caveats"]) >= 2 and
                all(type(x) is str and len(x) >= 35 for x in row["caveats"]),
                ident + ": incomplete source-first candidate and caveats")
        require(all(row.get(k) is None for k in EMPTY_ARCHIVE_FIELDS) and
                row.get("reviewer_verified_full_page") is False and
                row.get("editorial_approved") is False,
                ident + ": do not fabricate archived record IDs or reviewer authority")
        seen[ident] = row
    require(set(seen) == set(SOURCES), "missing Japanese source candidates")
    original = data.get("shadow_current_week_original")
    require(type(original) is dict and
            original.get("status") ==
            "archived_shadow_source_candidate_not_production_or_editor_approved" and
            original.get("state_branch") == "shadow/jp-mod" and
            original.get("source_id_namespace") ==
            "shadow_only_no_numeric_ipr_record_id" and
            original.get("sqlite_path") == "state/shadow.db" and
            original.get("source_record_identifier") ==
            "shadow/jp-mod:jp_mod_news_ja:2026-10-05:05b.pdf",
            "Japan October 5 source must remain a shadow-only candidate")
    require(all(original.get(key) == value
                for key, value in SHADOW_ARCHIVED.items()) and
            original.get("original_language") == "ja" and
            original.get("publication_kind") == "press release" and
            original.get("building_scope") == "portions of four buildings" and
            original.get("exercise_mentions") ==
            ["Keen Sword 27", "aircraft training relocation"] and
            type(original.get("caution_flags")) is list and
            len(original["caution_flags"]) >= 5,
            "Japan source archival pin, date, use period or volume changed")
    require(valid_date(original["publication_date_original"]) <= REVIEW_CUTOFF and
            valid_date(original["agreement_approval_date"]) <
            valid_date(original["publication_date_original"]) <
            valid_date(original["planned_facility_use_start"]) <=
            valid_date(original["planned_facility_use_end"]),
            "original agreement, notice and future training dates must remain separate")
    require(all(original.get(k) is False for k in (
        "exact_historical_source_replay_completed",
        "human_original_source_review_complete",
        "editorial_inclusion_approved",
        "source_promoted_to_production",
    )),
            "archived Japan text does not imply source verification or admission")
    extra = data.get("linked_public_mod_tsuiki_training_notice")
    require(type(extra) is dict and
            all(extra.get(k) == v for k, v in LINKED_TSU_IKI.items()) and
            type(extra.get("caveats")) is list and len(extra["caveats"]) >= 4 and
            type(extra.get("provisional_claims")) is list and
            len(extra["provisional_claims"]) == 2 and
            all(isinstance(x, str) and len(x) > 40
                for x in extra["provisional_claims"]),
            "secondary Tsuiki notice cannot fabricate capture or change original source")
    require(valid_date(extra["publication_date"]) <= REVIEW_CUTOFF and
            valid_date(extra["publication_date"]) <
            valid_date(extra["planned_training_start"]) <=
            valid_date(extra["planned_training_end"]),
            "secondary Tsuiki notice must remain a future event")
    grouped = data.get("source_relationships")
    require(type(grouped) is dict and
            set(grouped) == {"japan_indonesia_disaster_relief_completion",
                             "japan_us_alliance_communications"},
            "source independence groups changed")
    for group, ids in (
        ("japan_indonesia_disaster_relief_completion", ["JP-W41-01"]),
        ("japan_us_alliance_communications", [
            "JP-W41-02", "JP-W41-03", "JP-W41-04",
        ]),
    ):
        g = grouped[group]
        require(type(g) is dict and
                g.get("candidate_ids") == ids and
                g.get("distinct_mod_source_pages") == len(ids) and
                g.get("distinct_provisionally_attributed_issuing_institutions") == 1 and
                g.get("independently_verified_external_institutions") == 0,
                group + ": distinct MOD links are not independent institutions")
    require("one reported Naha incident" in grouped["japan_us_alliance_communications"].get(
        "recurring_issue", "") and
        type(data.get("independent_review_needed")) is list and
        len(data["independent_review_needed"]) >= 5,
        "related Okinawa protests and independent-review warnings cannot disappear")
    return {
        "week": "2026-10-04/2026-10-09",
        "discovery_as_of": REVIEW_CUTOFF.isoformat(),
        "official_mod_public_urls": len(seen),
        "shadow_current_week_full_text_records": 1,
        "japanese_original_paired_to_english_release": 1,
        "separate_official_japanese_html_editor_leads": 1,
        "japan_production_records_added": 0,
        "japan_records_admitted_to_weekly_writer": 0,
        "editorial_claims_approved": 0,
        "verified_original_archive_captures": 0,
        "automatic_emails_sent": 0,
        "requires_current_friday_recheck": True,
        "manuscript_or_publication_approved": False,
    }


def render(data):
    validation = validate(data)
    lines = [
        "INDO-PACIFIC RECORD — JAPAN DESK | PROVISIONAL FRIDAY EDITOR SUPPLEMENT",
        "Reporting window: Sunday, October 4 to Friday, October 9, 2026",
        "Sources inspected through Thursday, October 8; Friday still incomplete.",
        "NOT a production Briefs source-trail appendix; NOT approved or emailed.",
        "Japan is not an eligible production-backed desk and has no production record IDs.",
        "",
        "PRIMARY SHADOW-ARCHIVED LEAD: Japan–U.S. Joint Committee agreement",
        "Official Japanese MOD notice dated October 5, 2026. The notice reports",
        "September 17 approval of limited use of additional land and buildings",
        "at Tsuiki Airfield (FAC 5121) for Keen Sword 27 and aircraft training",
        "relocation. It lists approximately 29,000 m2 land and portions of four",
        "buildings totaling around 11,000 m2. Planned use is October 19–29,",
        "with additional time as needed for deployment and withdrawal.",
        "This does NOT mean that the exercise has already occurred.",
        "Status: original Japanese extracted text preserved in Japan shadow SQLite;",
        "source PDF bytes are not proven retained by the shadow database.",
        "No production ID, full-PDF human review, or editorial approval exists.",
        "  Source: " + data["shadow_current_week_original"]["source_url"],
        "  Shadow commit: " + data["shadow_current_week_original"]["historical_state_commit"],
        "  Archived extracted-text SHA-256: " +
            data["shadow_current_week_original"]["extracted_body_sha256"],
        "",
        "SEPARATE OFFICIAL MOD HTML: planned Kadena-to-Tsuiki transfer",
        "October 5: MOD announced the 12th aircraft-training relocation to",
        "Tsuiki from Kadena, planned October 19–29; the Type II category",
        "means 6–12 aircraft over 8–14 days, NOT a confirmed deployment count.",
        "This public HTML is unarchived. It complements the 05b PDF shadow",
        "record, but both documents come from the SAME issuing ministry.",
        "  Source: " + data["linked_public_mod_tsuiki_training_notice"]["url"],
        "No completed training, full-source human signoff, or IPR ID is claimed.",
        "",
        "SECONDARY EDITORIAL LEAD: Japanese disaster-response operations in Indonesia",
        "MOD reports departure of JS Kunisaki from Kijing Port on October 6 after",
        "relief operations. It reports three CH-47s, 56 missions and approximately",
        "280 tons of water released. This is MOD's own account; the paired Japanese",
        "original should be read before quoting or including it in Dylan's draft.",
        "Avoid a claim of coordination with Philippine emergency drills.",
        "",
        "SECONDARY ANGLE: Japanese and U.S. defense contacts, October 5–6",
        "Three distinct courtesy-call reports from ONE issuing ministry repeat a",
        "Japanese protest concerning a reported Naha incident. Do not count",
        "them as three independent incident confirmations or policy agreements.",
        "",
        "SOURCE LINKS — EXTERNAL FIRST-PARTY DISCOVERY, NOT IPR RECORD IDs",
    ]
    for row in data["source_candidates"]:
        lines.extend([
            "- {} | {} | {} | {}".format(
                row["candidate_id"], row["publisher_date"],
                row["editorial_priority"], row["title"]),
            "  Source: " + row["public_source_url"],
        ])
        if row["japanese_original_url"]:
            lines.append("  Japanese original: " + row["japanese_original_url"])
        for n, claim in enumerate(row["provisional_claims"], 1):
            lines.append("  Potential point {}: {}".format(n, claim))
        for caveat in row["caveats"]:
            lines.append("  Caution: " + caveat)
        lines.append("")
    lines.extend([
        "EDITOR REVIEW REQUIRED",
        "- Reopen each official source before use; verify full original and date.",
        "- Decide whether the Japan item improves, rather than dilutes, the Brief.",
        "- If incorporated, cite exact MOD URL and identify it as outside the",
        "  automated production-backed source trail. Do NOT fabricate record IDs.",
        "- Do not distribute copyrighted photographs or claim human review.",
        "- Friday handoff and Saturday source delta need another current check.",
        "",
        "No email was sent, no model draft modified, no publication authorized.",
    ])
    require(validation["japan_records_admitted_to_weekly_writer"] == 0,
            "non-production source cannot enter writer")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "render"))
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.packet.read_text(encoding="utf-8"))
        if args.action == "validate":
            print(json.dumps(validate(data), indent=2))
        else:
            print(render(data), end="")
    except (JapanBriefError, ValueError, OSError, TypeError) as exc:
        parser.exit(1, "Japan Friday research supplement: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
