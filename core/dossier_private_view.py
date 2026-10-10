"""Private, fictional-only Living Dossier reader projection (B2.2a).

Builds an inert, plain-text data model for a later owner-reviewed interface.
No HTML/Markdown rendering, site paths, sitemap, feeds, crawlers, publishing,
model calls, network access, source-body access, or file writes. This module
must never be wired to production output/ or Analysis without the separate
release contract and frontend authorization.

The only positive gate is a private *fictional* B2.1 preview result.  Authored
receipt strings and source-review metadata are not real permission documents.
"""
from __future__ import annotations

from core.dossier_publication import assess_dossier_release

VIEW_SCHEMA = "ipr-dossier-private-reader-view/1"
MARKER = "FICTIONAL — PRIVATE REVIEW ONLY — NOT FOR PUBLICATION"
ATTRIBUTION = {
    "issuer_statement": "Attributed issuer statement",
    "documented_publication": "Documented publication",
    "editorial_interpretation": "IPR editorial interpretation",
}


class PrivateDossierViewHold(ValueError):
    """A synthetic preview cannot safely be assembled from these inputs."""


def build_private_dossier_view(sidecar, archive_review, *, synthetic_authority):
    """Return a deterministic fictional view model; refuse all non-fictional data.

    The caller MUST construct archive_review freshly using the real B1.2
    reconciler and a synthetic, isolated SQLite test corpus. This function is
    deliberately side-effect-free; it cannot authenticate report provenance.
    No caller may convert this result to a public or deployable Dossier.
    """
    release = assess_dossier_release(
        sidecar, archive_review, synthetic_authority=synthetic_authority,
        private_synthetic_preview=True,
    )
    if release["eligible_for_publication"] or release["production_authority_configured"]:
        raise PrivateDossierViewHold("public-authority-state-rejected")
    if not release["private_synthetic_preview_ready"]:
        raise PrivateDossierViewHold("private-synthetic-review-hold")

    sources = sidecar["sources"]
    policies = release["synthetic_preview_link_policy"]
    ids = [source["record_id"] for source in sources]
    if [item["record_id"] for item in policies] != ids:
        raise PrivateDossierViewHold("private-source-order-mismatch")
    by_id = {p["record_id"]: p for p in policies}

    ledger = []
    for source in sources:
        rid = source["record_id"]
        policy = by_id[rid]
        # Even this private projection never uses an IPR public record route.
        # Safe source URLs are restricted by B2.1 to RFC-reserved example hosts.
        ledger.append({
            "record_id": rid,
            "anchor": "source-" + str(rid),
            "desk": source["desk"],
            "source_id": source["source_id"],
            "institution_id": source["institution_id"],
            "language": source["language"],
            "published_on": source["published_on"],
            "fictional_publisher_url": source["url"] if policy["publisher_link"] else None,
            "internal_source_anchor": "#source-" + str(rid),
            "local_record_link": None,
            "link_mode": ("fictional-publisher-example" if policy["publisher_link"]
                          else "internal-reference-only"),
        })

    themed = []
    for section in sidecar["sections"]:
        claims = []
        for claim in section["claims"]:
            citations = [
                {"record_id": rid, "source_anchor": "#source-" + str(rid)}
                for rid in claim["source_record_ids"]
            ]
            contrary = [
                {"record_id": rid, "source_anchor": "#source-" + str(rid)}
                for rid in claim["counterevidence_ids"]
            ]
            claims.append({
                "id": claim["id"],
                "anchor": "claim-" + claim["id"],
                "attribution_kind": claim["claim_kind"],
                "attribution_label": ATTRIBUTION[claim["claim_kind"]],
                "text": claim["text"],
                "limitations": claim["limits"],
                "event_period": (
                    {key: claim["event_period"][key]
                     for key in ("start", "end", "basis", "date_basis")}
                    if claim["event_period"] is not None else None
                ),
                "supporting_citations": citations,
                "counterevidence_citations": contrary,
            })
        themed.append({
            "id": section["id"],
            "anchor": "section-" + section["id"],
            "heading": section["heading"],
            "intro": section["intro"],
            "claims": claims,
        })

    disagreements = [{
        "id": d["id"], "status": d["status"], "note": d["note"],
        "claim_anchors": ["#claim-" + cid for cid in d["claim_ids"]],
    } for d in sidecar["disagreements"]]

    changes = [{
        "revision": c["revision"], "changed_on": c["changed_on"],
        "summary": c["summary"],
        "affected_claim_anchors": [
            "#claim-" + cid for cid in c["affected_claim_ids"]
        ],
    } for c in sidecar["changes"]]

    # The view is plain data. An eventual renderer must HTML-escape every text
    # field, append noindex, avoid canonicals and write outside the repository.
    return {
        "schema": VIEW_SCHEMA,
        "warning": MARKER,
        "private_synthetic_preview_only": True,
        "eligible_for_publication": False,
        "publication_authority_configured": False,
        "indexable": False,
        "canonical": None,
        "sitemap_route": None,
        "public_route": None,
        "feed_route": None,
        "slug": sidecar["slug"],
        "content_sha256": release["content_sha256"],
        "title": sidecar["title"],
        "dek": sidecar["dek"],
        "research_question": sidecar["research_question"],
        "overview": sidecar["overview"],
        "revision": sidecar["revision"],
        "updated_on": sidecar["updated_on"],
        "reviewed_on": sidecar["reviewed_on"],
        "author_name": sidecar["author_name"],
        "editor_name": sidecar["editor_name"],
        "scope": {
            key: (
                list(sidecar["scope"][key])
                if key in ("jurisdictions", "institutions") else
                sidecar["scope"][key]
            )
            for key in (
                "period_start", "period_end", "jurisdictions", "institutions",
                "included", "excluded", "method", "collection_limits"
            )
        },
        "sections": themed,
        "disagreements": disagreements,
        "source_ledger": ledger,
        "changes": changes,
        # Even an approved Brief/Timeline slug in authored JSON is not proof
        # that the target artifact is public; no related link is created here.
        "related_research_links": [],
    }
