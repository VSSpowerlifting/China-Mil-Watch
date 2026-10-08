"""Conservative source-lineage gate for provisional Philippines event evidence.

This is a read-only research auditor. It counts *documentary records* separately
from *attributed originating institutions* and from *verified independent
institutional confirmations*. It never verifies a human identity, source rights,
event chronology, source authorship, or publication permission.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
PILOT = ROOT / "research/philippines/evidence_independence/pilot.json"
DOSSIER = ROOT / "research/philippines/sanlakas_2026/source_event_candidates.json"

EVENTS = {
    "ph-2026-iax-02-pagsasanay-sanlakas": ("afp:1391", "afp:1393", "afp:1394"),
    "ph-2026-09-29-jpscc-sixth-meeting": ("afp:1390",),
}
ARCHIVED_SHA256 = {
    "afp:1390": ("c51136832b8271f81957a021bc68b6588fa7e1d65fff4ca9979ec74593e2faea",
                 "4120dd834b5bb5fbce8616f51e5bf0fe8c1c4fc289c04476187d2af48b4fc864"),
    "afp:1391": ("2207cc71ef080ebfecbf35dba117ce775b3583b043415b39352a65622d62f724",
                 "721e5379732008b4a1ecfe9b45fe93b41200e9bda97243fef157f1247bcd22ae"),
    "afp:1393": ("b6b50aea327ea452e62f7ba0b9d5278c165a27da08686cbeddee65e5f54a71da",
                 "b00b39d3647c7786e2d63b8775125e7a1bbd790ec463b79e3d089a6f5df7bf64"),
    "afp:1394": ("0f99d426c5860b25788a152f7a487463bf6979db84915b58c9509b5817dce003",
                 "168ba1fba196d133676c68f8fd79365d86666473f0b9959185111fa795c51064"),
}
EXTERNAL = {
    "PCG-PIA-01": "https://pia.gov.ph/press-release/pcg-commandant-activates-coast-guard-auxiliary-district-in-kalayaan-island-group-kalayaan-mayor-leads-new-pcga-members-in-oath-taking/",
    "PCG-PIA-02": "https://pia.gov.ph/news/pcg-deploys-aircraft-and-brp-teresa-magbanua-to-challenge-china-coast-guard-vessel-near-cabra-island-pla-navy-warships-monitored-in-the-area/",
}
FALSE_GATES = {
    "source_lineage_human_approved",
    "origin_issuer_authenticated",
    "repeat_host_dedup_adjudicated",
    "event_memberships_approved",
    "archival_rights_confirmed",
    "topic_classifications_approved",
    "timeline_approved",
    "production_data_write_authorized",
}
ORIGIN_STATUSES = {
    "ph-afp": "first_party_archived_not_human_approved",
    "ph-pcg": "byline_attribution_only_unverified",
    "ph-pia": "hosting_institution_not_equivalent_to_pcg",
}
ARCHIVE_FIELDS = {
    "record_id", "origin_institution", "host_institution",
    "attribution_basis", "human_review_complete", "mirror_of",
    "issuer_independent_approval",
}
EXTERNAL_FIELDS = {
    "candidate_id", "source_url", "host_institution", "credited_issuer",
    "byline_observation", "issuer_authenticated", "source_capture_sha256",
    "original_pcg_url", "link_to_candidate_event_ids",
    "source_authorized_for_archiving", "rights_review_complete",
}


class SourceLineageError(ValueError):
    """A pilot assertion would overstate provenance or independence."""


def require(ok, why):
    if not ok:
        raise SourceLineageError(why)


def verified_origin_count(sources):
    """Count verified *originating institutions*, never different host URLs.

    A same-issuer mirror is not a second independent institution. Technical
    approval requires BOTH original-issuer authentication and attributable
    human editorial verification; passing this function is not itself review.
    """
    origin_ids = set()
    for row in sources:
        if not isinstance(row, dict):
            raise SourceLineageError("independent-evidence row must be an object")
        issuer = row.get("origin_institution")
        host = row.get("host_institution")
        require(type(issuer) is str and issuer.strip() and
                type(host) is str and host.strip(),
                "source needs separate origin and hosting institution identifiers")
        issuer_pass = row.get("issuer_authenticated") is True
        human_pass = row.get("human_review_complete") is True
        if issuer_pass and human_pass:
            origin_ids.add(issuer)
    return len(origin_ids)


def validate(pilot, dossier):
    require(type(pilot) is dict and
            pilot.get("protocol") == "ipr_ph_source_evidence_lineage_v1" and
            pilot.get("status") == "unsigned_research_only" and
            pilot.get("derived_from") ==
            "research/philippines/sanlakas_2026/source_event_candidates.json" and
            pilot.get("review_cutoff") == "2026-10-08",
            "unexpected evidence-lineage protocol or review scope")
    require(type(pilot.get("scope_note")) is str and
            len(pilot["scope_note"]) > 45 and
            type(pilot.get("interpretation")) is str and
            "not automatically a unique event" in pilot["interpretation"],
            "source-versus-event caution lost")
    gates = pilot.get("review_gates")
    require(type(gates) is dict and set(gates) == FALSE_GATES and
            all(gates[x] is False for x in FALSE_GATES),
            "source lineage may not approve any reviewer, timeline or production gate")
    orgs = pilot.get("institutional_origins")
    require(type(orgs) is dict and set(orgs) == set(ORIGIN_STATUSES),
            "host and issuer organizations cannot be silently added")
    for oid, expected in ORIGIN_STATUSES.items():
        require(type(orgs[oid]) is dict and
                orgs[oid].get("status") == expected and
                type(orgs[oid].get("name")) is str and
                len(orgs[oid]["name"]) > 10,
                "issuer and host attribution status cannot be promoted")
    require(type(dossier) is dict and
            dossier.get("schema") == "ipr_philippines_provisional_source_event_v1" and
            dossier.get("status") == "unsigned_research_candidate_requires_human_review" and
            dossier.get("archive", {}).get("state_commit") ==
            "492001f34ba6176169b6acc96a237f05592a3395" and
            dossier.get("archive", {}).get("state_db_blob") ==
            "e42f8f0dde480a99452d89bcfc7ee84b5aa55f13" and
            type(dossier.get("permissions")) is dict and
            all(value is False for value in dossier["permissions"].values()),
            "dossier archive or permissions have changed")
    original_records = dossier.get("records")
    require(type(original_records) is list and
            len(original_records) == len(ARCHIVED_SHA256),
            "event dossier source set drifted")
    record_map = {}
    for r in original_records:
        require(type(r) is dict and
                type(r.get("id")) is str and r["id"] in ARCHIVED_SHA256 and
                r["id"] not in record_map,
                "unexpected or duplicated original AFP record")
        a, b = ARCHIVED_SHA256[r["id"]]
        require(r.get("content_sha256") == a and
                r.get("capture_sha256") == b and
                type(r.get("source_url")) is str and
                r["source_url"].startswith("https://www.afp.mil.ph/news/"),
                "source archival fingerprint or first-party URL changed")
        record_map[r["id"]] = r
    require(set(record_map) == set(ARCHIVED_SHA256),
            "original source identity coverage incomplete")

    documented_events = dossier.get("event_candidates")
    require(type(documented_events) is list and len(documented_events) == 2,
            "event dossier cannot silently create a new occurrence")
    doc_groups = {}
    for event in documented_events:
        require(type(event) is dict and
                event.get("candidate_event_id") in EVENTS and
                event.get("candidate_event_id") not in doc_groups and
                event.get("status") == "provisional_source_based_grouping",
                "unexpected or implicitly approved event")
        doc_groups[event["candidate_event_id"]] = event.get("record_ids")
    require(set(doc_groups) == set(EVENTS) and
            all(doc_groups[event] == list(ids)
                for event, ids in EVENTS.items()),
            "dossier conflated independent occurrence and exercise phases")

    memberships = pilot.get("event_memberships")
    require(type(memberships) is list and len(memberships) == len(EVENTS),
            "two specific event memberships are mandatory")
    seen_events = set()
    for m in memberships:
        require(type(m) is dict and
                set(m) == {"candidate_event_id", "source_record_ids",
                           "candidate_only"},
                "event reference schema drift")
        eid = m.get("candidate_event_id")
        require(eid in EVENTS and eid not in seen_events and
                m.get("source_record_ids") == list(EVENTS[eid]) and
                m.get("candidate_only") is True,
                "event membership must stay provisional and source-specific")
        seen_events.add(eid)

    refs = pilot.get("archived_record_lineages")
    require(type(refs) is list and len(refs) == len(ARCHIVED_SHA256),
            "four AFP original records required")
    seen_records = set()
    for row in refs:
        require(type(row) is dict and set(row) == ARCHIVE_FIELDS,
                "source lineage record schema changed")
        ident = row.get("record_id")
        require(ident in ARCHIVED_SHA256 and ident not in seen_records,
                "unknown or duplicate archive source record")
        seen_records.add(ident)
        require(row["origin_institution"] == "ph-afp" and
                row["host_institution"] == "ph-afp" and
                row["attribution_basis"] == "pinned_first_party_AFP_capture" and
                row["human_review_complete"] is False and
                row["issuer_independent_approval"] is False and
                row["mirror_of"] is None,
                "first-party records must not become reviewed or mirror-linked")

    leads = pilot.get("external_unadmitted_hosts")
    require(type(leads) is list and len(leads) == len(EXTERNAL),
            "expected two independent pending host observations")
    seen = set()
    for item in leads:
        require(type(item) is dict and set(item) == EXTERNAL_FIELDS,
                "unadmitted PIA lead schema changed")
        ident = item.get("candidate_id")
        require(type(ident) is str and ident in EXTERNAL and
                ident not in seen and item.get("source_url") == EXTERNAL[ident],
                "unknown or duplicate external host lead")
        seen.add(ident)
        uri = urlsplit(item["source_url"])
        require(uri.scheme == "https" and uri.hostname == "pia.gov.ph" and
                not uri.query and not uri.fragment,
                "PIA lead must remain on the exact PIA hosting domain")
        require(item["host_institution"] == "ph-pia" and
                item["credited_issuer"] == "ph-pcg" and
                item["byline_observation"] == "By PCG" and
                item["issuer_authenticated"] is False and
                item["source_capture_sha256"] is None and
                item["original_pcg_url"] is None and
                item["link_to_candidate_event_ids"] == [] and
                item["source_authorized_for_archiving"] is False and
                item["rights_review_complete"] is False,
                "PIA-hosted leads are unverified, unarchived and not AFP event evidence")
    require(seen == set(EXTERNAL), "external lead coverage drift")

    claims = dossier.get("claims")
    require(type(claims) is list and len(claims) == 11,
            "fixed AFP eleven-claim evidence scope changed")
    for claim in claims:
        require(type(claim) is dict and
                type(claim.get("evidence")) is list and
                len(claim["evidence"]) == 1,
                "claim cannot acquire outside-source corroboration implicitly")
        evidence = claim["evidence"][0]
        require(type(evidence) is dict and
                evidence.get("record_id") in seen_records,
                "claim source not in preserved AFP set")
        allowed = next((ids for eid, ids in EVENTS.items()
                        if evidence["record_id"] in ids), None)
        require(allowed is not None, "missing claim-event source association")
        expected_key = ("sanlakas_exercise"
                        if "afp:1390" not in allowed else "jpscc_meeting")
        require(claim.get("event_key") == expected_key,
                "claim event grouping drifted")

    analysis = []
    by_record = {x["record_id"]: x for x in refs}
    for eid, members in EVENTS.items():
        voices = {by_record[r]["origin_institution"] for r in members}
        hosts = {by_record[r]["host_institution"] for r in members}
        analysis.append({
            "event_candidate_id": eid,
            "provisional_archived_article_count": len(members),
            "provisionally_attributed_origin_organizations": sorted(voices),
            "distinct_provisionally_attributed_origins": len(voices),
            "distinct_host_organizations": len(hosts),
            "independently_authenticated_origin_organizations":
                verified_origin_count([
                    {**by_record[r], "issuer_authenticated": False}
                    for r in members
                ]),
            "external_PIA_PCG_leads_used_as_corrob": 0,
            "event_approved": False,
        })
    return {
        "scope": "philippines_provisional_research_only",
        "event_candidates": analysis,
        "total_archived_AFP_documents": len(seen_records),
        "total_unadmitted_PIA_hosted_PCG_credited_leads": len(leads),
        "all_external_issuer_authentication_pending": True,
        "reviewer_authentication_complete": False,
        "archive_rights_confirmed": False,
        "independent_corroboration_confirmed": False,
        "timeline_publication_approved": False,
        "production_writes": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, default=PILOT)
    parser.add_argument("--dossier", type=Path, default=DOSSIER)
    args = parser.parse_args()
    try:
        pilot = json.loads(args.pilot.read_text(encoding="utf-8"))
        dossier = json.loads(args.dossier.read_text(encoding="utf-8"))
        print(json.dumps(validate(pilot, dossier),
                         ensure_ascii=False, indent=2, sort_keys=True))
    except (ValueError, TypeError, OSError) as exc:
        parser.exit(1, "Philippines source-lineage audit: %s\n" % exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
