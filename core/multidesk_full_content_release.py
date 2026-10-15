"""Version-bound, rights-aware full-content release staging for all IPR desks.

An independently verified collector/source, publisher reuse right, reviewed
translation/analysis and scoped editor approvals are FOUR distinct gates.
A public note about metadata publication cannot satisfy any of them.

No collector, signer, network client, production writer or Pages deployer here.
Even a complete valid bundle can stage ONLY to a new external directory.
A future scheduler may call this after authenticating evidence and keys, then
publish the resulting reviewed bytes through separate controlled release CI.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from core.public_editorial_research import HOSTS as EDITORIAL_HOSTS
from core.standing_source_rights import (
    StandingLicenseHold, qualify_standing_text,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "ipr-multidesk-full-content-bundle/1"
RECEIPT_SCHEMA = "ipr-full-content-human-approval/1"
DOMAIN = b"IPR-FULL-CONTENT-HUMAN-APPROVAL-v1\x00"
HASH = re.compile(r"[0-9a-f]{64}\Z")
GIT = re.compile(r"[0-9a-f]{40}\Z")
IDENTITY = re.compile(r"[a-z0-9][a-z0-9._:/-]{2,220}\Z")
UTC = re.compile(r"20\d{2}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
KINDS = frozenset(("original_text", "original_pdf", "translation_en", "analysis_en"))
REQUIRED_ROLES = {
    "original_text": frozenset(("rights", "source_fidelity")),
    "original_pdf": frozenset(("rights", "document_integrity")),
    "translation_en": frozenset(("rights", "bilingual", "editor")),
    "analysis_en": frozenset(("rights", "fact_checker", "editor")),
}
SCOPES = {
    "original_text": "text_reproduction",
    "original_pdf": "entire_document_with_all_embedded_assets",
    "translation_en": "translation_and_derivative_publication",
    "analysis_en": "independently_authored_ipr_analysis_no_source_reproduction",
}
EXT = {
    "original_text": ".txt", "original_pdf": ".pdf",
    "translation_en": ".txt", "analysis_en": ".txt",
}
SIZES = {
    "original_text": 2_000_000, "original_pdf": 15_000_000,
    "translation_en": 2_000_000, "analysis_en": 2_000_000,
}
# One family is not a license for another (even when on the same hostname).
# Publicly listed source families are a closed set, not guessed from URL suffix.
FAMILIES = dict(EDITORIAL_HOSTS, **{
    "cn_pla_daily": ("china", "www.81.cn"),
    "sg_mindef_releases": ("singapore", "www.mindef.gov.sg"),
    "us_uscc_press": ("us-indopacific", "www.uscc.gov"),
    "us_treasury_press": ("us-indopacific", "home.treasury.gov"),
})
SOURCE_KEYS = frozenset({
    "desk", "source_family", "source_identity", "source_git_commit",
    "source_capture_sha256", "official_url", "published_date",
    "source_language", "publisher",
})
WORK_KEYS = frozenset({
    "kind", "content_sha256", "source_capture_sha256", "rights_basis",
    "rights_evidence_sha256", "rights_evidence_url", "rights_scope",
    "third_party_assets_cleared", "attribution_text",
    "language", "citations_verified",
})
BUNDLE_KEYS = frozenset(("schema", "source", "works"))
APPROVAL_KEYS = frozenset((
    "schema", "bundle_sha256", "source_git_commit", "source_capture_sha256",
    "source_identity", "kind", "content_sha256", "role", "reviewer",
    "reviewed_at_utc", "signature_hmac_sha256",
))
RIGHTS_BASIS = frozenset((
    "per_item_official_license", "documented_written_permission",
    "documented_public_domain", "ipr_original_copyright",
    "standing_source_family_license",
))
DANGEROUS_TEXT = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class FullContentHold(ValueError):
    """Fixed reason only: never echo private source texts or key material."""


def need(test, reason):
    if not test:
        raise FullContentHold(reason)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def require_sha(value, kind):
    need(type(value) is str and HASH.fullmatch(value) is not None,
         kind + "_digest_missing")


def instant(value):
    need(type(value) is str and UTC.fullmatch(value) is not None,
         "approval_timestamp_invalid")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        raise FullContentHold("approval_timestamp_invalid") from None


def official_url(value, host):
    need(type(value) is str and 0 < len(value) <= 2048
         and not any(ord(c) < 33 or ord(c) == 127 for c in value),
         "official_url_invalid")
    try:
        u = urlsplit(value)
        good = (u.scheme == "https" and u.hostname == host
                and u.port is None and not u.username and not u.password
                and not u.fragment and u.path.startswith("/")
                and not u.path.startswith("//") and "\\" not in value)
    except ValueError:
        good = False
    need(good, "official_source_host_not_allowlisted")
    return value


def _validate_bundle(bundle, artifacts):
    need(type(bundle) is dict and set(bundle) == BUNDLE_KEYS
         and bundle.get("schema") == SCHEMA, "invalid_full_content_bundle")
    s = bundle["source"]
    need(type(s) is dict and set(s) == SOURCE_KEYS,
         "incomplete_source_provenance")
    family = s["source_family"]
    need(type(family) is str and family in FAMILIES
         and s["desk"] == FAMILIES[family][0],
         "source_family_not_approved")
    official_url(s["official_url"], FAMILIES[family][1])
    need(type(s["source_identity"]) is str and IDENTITY.fullmatch(
         s["source_identity"]) is not None
         and ".." not in s["source_identity"]
         and "//" not in s["source_identity"],
         "source_identity_not_canonical")
    need(type(s["publisher"]) is str and 3 <= len(s["publisher"]) <= 120
         and not DANGEROUS_TEXT.search(s["publisher"]),
         "source_publisher_missing")
    need(type(s["source_git_commit"]) is str
         and GIT.fullmatch(s["source_git_commit"]) is not None,
         "source_git_commit_missing")
    require_sha(s["source_capture_sha256"], "original_capture")
    need(type(s["source_language"]) is str and
         re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z]{2,4})?", s["source_language"]),
         "source_language_invalid")
    need(type(s["published_date"]) is str,
         "published_date_invalid")
    try:
        need(date.fromisoformat(s["published_date"]).isoformat() ==
             s["published_date"], "published_date_invalid")
    except ValueError:
        raise FullContentHold("published_date_invalid") from None

    works = bundle["works"]
    need(type(works) is list and 1 <= len(works) <= len(KINDS)
         and type(artifacts) is dict and len(artifacts) == len(works),
         "artifact_roster_invalid")
    found = set()
    for w in works:
        need(type(w) is dict and set(w) == WORK_KEYS and
             w.get("kind") in KINDS, "work_manifest_invalid")
        k = w["kind"]
        need(k not in found and k in artifacts, "duplicate_or_missing_work")
        found.add(k)
        require_sha(w["content_sha256"], "work")
        need(w["source_capture_sha256"] == s["source_capture_sha256"],
             "work_original_version_drift")
        require_sha(w["rights_evidence_sha256"], "rights")
        need(w["rights_scope"] == SCOPES[k]
             and w["rights_basis"] in RIGHTS_BASIS,
             "rights_scope_unapproved")
        official_url(w["rights_evidence_url"],
                     urlsplit(s["official_url"]).hostname) if (
            w["rights_basis"] == "per_item_official_license") else _https_evidence(
                w["rights_evidence_url"])
        need(type(w["third_party_assets_cleared"]) is bool
             and type(w["citations_verified"]) is bool,
             "content_checks_missing")
        need(type(w["attribution_text"]) is str
             and 12 <= len(w["attribution_text"]) <= 1000
             and w["attribution_text"] == w["attribution_text"].strip()
             and not DANGEROUS_TEXT.search(w["attribution_text"])
             and s["official_url"] in w["attribution_text"],
             "official_source_attribution_missing")
        need(type(w["language"]) is str, "work_language_missing")
        if k in ("translation_en", "analysis_en"):
            need(w["language"] == "en"
                 and w["citations_verified"] is True,
                 "translation_or_analysis_evidence_missing")
        else:
            need(w["language"] == s["source_language"],
                 "original_language_version_mismatch")
        if k == "original_pdf":
            need(w["third_party_assets_cleared"] is True
                 and w["rights_basis"] != "ipr_original_copyright",
                 "complete_binary_and_embedded_asset_permission_missing")
        if k in ("original_text", "translation_en"):
            need(w["rights_basis"] != "ipr_original_copyright",
                 "official_expression_rights_missing")
        if k == "analysis_en":
            need(w["rights_basis"] == "ipr_original_copyright",
                 "analysis_must_be_independent_ipr_authorship")
        body = artifacts[k]
        need(type(body) is bytes and 0 < len(body) <= SIZES[k],
             "artifact_bytes_missing_or_excessive")
        need(sha(body) == w["content_sha256"], "artifact_bytes_version_mismatch")
        if k == "original_pdf":
            need(body.startswith(b"%PDF-") and
                 b"%%EOF" in body[-1024:],
                 "original_document_not_a_complete_pdf")
        else:
            try:
                txt = body.decode("utf-8")
            except UnicodeError:
                raise FullContentHold("artifact_not_utf8") from None
            need(len(txt.strip()) >= 80 and not DANGEROUS_TEXT.search(txt),
                 "artifact_text_incomplete_or_unsafe")
    need(found == set(artifacts), "unlisted_artifacts_refused")
    return sha(canonical(bundle))


def _https_evidence(url):
    need(type(url) is str and url.startswith("https://")
         and len(url) <= 2048, "rights_evidence_url_invalid")
    try:
        p = urlsplit(url)
        good = (p.scheme == "https" and p.hostname is not None and
                p.port is None and not p.username and not p.password and
                not p.fragment and "\\" not in url)
    except ValueError:
        good = False
    need(good, "rights_evidence_url_invalid")


def signature_payload(approval):
    """What a human signs; excludes the MAC itself."""
    need(type(approval) is dict and set(approval) == APPROVAL_KEYS,
         "approval_receipt_unrecognized")
    return {k: approval[k] for k in APPROVAL_KEYS
            if k != "signature_hmac_sha256"}


def sign_for_test_or_offline_reviewer(payload, secret):
    """Pure signing primitive, NEVER a workflow or web-facing signing endpoint.

    The real reviewer must assess original rights, content and quality outside
    this function. Never check private reviewer secrets into git.
    """
    need(type(secret) is bytes and len(secret) >= 32,
         "independent_reviewer_secret_missing")
    return hmac.new(secret, DOMAIN + canonical(payload), hashlib.sha256).hexdigest()


def verify_bundle(bundle, artifacts, approvals, *, role_secrets,
                  authorized_reviewers=None, source_verifier=None,
                  rights_verifier=None, standing_verifiers=None):
    """Return a safe staging plan; publication requires separate authorization.

    Source replay is always mandatory. Ordinary document rights are checked by
    rights_verifier; when a source-family standing *text* license is applicable,
    the independent standing-source, current-policy and exception verifiers can
    REPLACE per-item human rights approval. Complete exact source text also
    replaces repetitive human source-fidelity signatures. Translation/editor
    quality signoff remains separate; PDF/media rights NEVER inherit text use.
    """
    digest = _validate_bundle(bundle, artifacts)
    need(callable(source_verifier),
         "independent_source_and_rights_verifiers_not_wired")
    need(source_verifier(bundle["source"]) is True,
         "original_source_capture_not_authenticated")
    by_kind = {w["kind"]: w for w in bundle["works"]}
    review_roles = {}
    qualified_standing = []
    for work in bundle["works"]:
        k = work["kind"]
        if work["rights_basis"] == "standing_source_family_license":
            need(k in ("original_text", "translation_en"),
                 "standing_text_rights_cannot_cover_pdf_or_analysis")
            need(type(standing_verifiers) is dict
                 and set(standing_verifiers) == {
                     "now_utc", "source_replay", "policy_replay",
                     "exception_replay", "item_license_replay"},
                 "standing_source_license_verifiers_missing")
            src = bundle["source"]
            source = {
                "desk": src["desk"],
                "source_family": src["source_family"],
                "source_identity": src["source_identity"],
                "official_url": src["official_url"],
                "source_git_commit": src["source_git_commit"],
                "source_capture_sha256": src["source_capture_sha256"],
                "publisher_posted_date": src["published_date"],
                "language": src["source_language"],
            }
            try:
                qualified = qualify_standing_text(
                    source, kind=k, proposed_sha256=work["content_sha256"],
                    attribution=work["attribution_text"],
                    **standing_verifiers)
            except StandingLicenseHold:
                raise FullContentHold("standing_source_license_not_qualified") from None
            need(qualified["publisher_policy_sha256"] ==
                 work["rights_evidence_sha256"]
                 and qualified["policy_url"] == work["rights_evidence_url"],
                 "standing_source_policy_version_drift")
            qualified_standing.append(k)
            # For authentic *unchanged* government source text, byte-verified
            # replay is its source fidelity approval. The standing publisher
            # license replaces a new human rights signature for every record.
            # New translations still NEED separate bilingual/editor review.
            review_roles[k] = (frozenset() if k == "original_text"
                               else frozenset(("bilingual", "editor")))
        else:
            need(callable(rights_verifier),
                 "independent_source_and_rights_verifiers_not_wired")
            need(rights_verifier(bundle["source"], work) is True,
                 "publisher_or_editorial_rights_not_independently_verified")
            review_roles[k] = REQUIRED_ROLES[k]
    need(type(approvals) is list and type(role_secrets) is dict
         and type(authorized_reviewers) is dict,
         "human_editorial_approval_material_missing")
    required_roles = {r for roles in review_roles.values() for r in roles}
    need(set(authorized_reviewers) == required_roles and
         all(type(names) in (tuple, list) and 1 <= len(names) <= 20
             and all(type(n) is str and 3 <= len(n) <= 100 for n in names)
             and len(set(names)) == len(names)
             for names in authorized_reviewers.values()),
         "independent_reviewer_roster_missing")
    need(set(role_secrets) >= required_roles
         and all(type(role_secrets[role]) is bytes
                 and len(role_secrets[role]) >= 32
                 for role in required_roles)
         and len({role_secrets[role] for role in required_roles}) ==
             len(required_roles),
         "reviewer_keys_not_role_separated")
    seen = set()
    signers = {}
    for a in approvals:
        payload = signature_payload(a)
        kind, role = a["kind"], a["role"]
        need(kind in by_kind and role in review_roles[kind],
             "approval_role_out_of_scope")
        need((kind, role) not in seen,
             "duplicate_artifact_role_approval")
        seen.add((kind, role))
        w = by_kind[kind]
        need(a["schema"] == RECEIPT_SCHEMA
             and a["bundle_sha256"] == digest
             and a["source_git_commit"] == bundle["source"]["source_git_commit"]
             and a["source_capture_sha256"] ==
                 bundle["source"]["source_capture_sha256"]
             and a["source_identity"] == bundle["source"]["source_identity"]
             and a["content_sha256"] == w["content_sha256"]
             and type(a["reviewer"]) is str
             and 3 <= len(a["reviewer"]) <= 100
             and a["reviewer"] == a["reviewer"].strip()
             and not DANGEROUS_TEXT.search(a["reviewer"]),
             "human_approval_source_version_mismatch")
        need(a["reviewer"] in authorized_reviewers[role],
             "signer_not_in_independent_reviewer_roster")
        need(instant(a["reviewed_at_utc"]).date() >=
             date.fromisoformat(bundle["source"]["published_date"]),
             "review_precedes_publication")
        secret = role_secrets.get(role)
        need(type(secret) is bytes and len(secret) >= 32,
             "independent_reviewer_secret_missing")
        expected = sign_for_test_or_offline_reviewer(payload, secret)
        need(type(a["signature_hmac_sha256"]) is str and
             hmac.compare_digest(a["signature_hmac_sha256"], expected),
             "human_review_approval_signature_invalid")
        signers[(kind, role)] = a["reviewer"]
    need(seen == {(k, r) for k in by_kind for r in review_roles[k]},
         "necessary_human_work_review_missing")
    # Separate a translation/factual checker from the final publishing editor.
    for k in ("translation_en", "analysis_en"):
        if k in by_kind:
            specialist = "bilingual" if k == "translation_en" else "fact_checker"
            need(signers[(k, specialist)] != signers[(k, "editor")],
                 "independent_language_or_fact_check_missing")
    return {
        "schema": "ipr-approved-full-content-staging-plan/1",
        "source_desk": bundle["source"]["desk"],
        "source_identity": bundle["source"]["source_identity"],
        "source_git_commit": bundle["source"]["source_git_commit"],
        "bundle_sha256": digest,
        "kinds": sorted(by_kind),
        "standing_license_qualified_kinds": sorted(qualified_standing),
        "permission_asserted_by_unverified_json_only": False,
        "source_rights_and_originals_independently_validated": True,
        "downstream_publication_performed": False,
    }


def stage_approved_bundle(bundle, artifacts, approvals, *,
                          role_secrets, authorized_reviewers=None,
                          source_verifier=None, rights_verifier=None,
                          target_dir):
    """Stage approved bytes outside the repository. NEVER push to Pages.

    The required output destination must not exist, be a symlink, or be under
    the repo root; verify all provenance and signatures before any file IO.
    """
    plan = verify_bundle(bundle, artifacts, approvals,
                         role_secrets=role_secrets,
                         authorized_reviewers=authorized_reviewers,
                         source_verifier=source_verifier,
                         rights_verifier=rights_verifier,
                         standing_verifiers=standing_verifiers)
    target = Path(target_dir).expanduser()
    resolved = target.resolve()
    need(not target.exists() and not target.is_symlink()
         and target.parent.is_dir() and
         resolved != ROOT and ROOT not in resolved.parents
         and not target.parent.is_symlink(),
         "staging_must_be_new_external_directory")
    s = bundle["source"]
    subdir = s["desk"] + "/" + sha(
        (s["source_family"] + "\x00" + s["source_identity"]).encode())[:20]
    dest = target / subdir
    target.mkdir(mode=0o700)
    try:
        dest.mkdir(parents=True)
        for k, data in artifacts.items():
            (dest / (k + EXT[k])).write_bytes(data)
        # Explicitly identified as an IPR packaging of publisher material;
        # no implied institutional endorsement, and no auto-generated claims.
        parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
                 '<meta name="robots" content="noindex">',
                 '<title>IPR source version — staged pending release</title>',
                 '</head><body><main>',
                 '<h1>Approved content package — not yet published</h1>',
                 '<p>Source: <a href="' +
                 html.escape(s["official_url"], quote=True) + '">' +
                 html.escape(s["publisher"]) + '</a> — ' +
                 html.escape(s["published_date"]) + '</p>']
        for w in bundle["works"]:
            k = w["kind"]
            parts.append('<section data-release-kind="' + k + '"><h2>' +
                         html.escape(k.replace("_", " ").title()) + '</h2>')
            parts.append('<p>' + html.escape(w["attribution_text"]) + '</p>')
            if k == "original_pdf":
                parts.append('<a href="original_pdf.pdf">Permitted original PDF</a>')
            else:
                # No browser execution of publisher content: all text escaped.
                parts.append('<pre>' + html.escape(
                    artifacts[k].decode("utf-8")) + '</pre>')
            if k == "translation_en":
                parts.append('<p>Unofficial IPR translation; not a translation issued by the source institution.</p>')
            if k == "analysis_en":
                parts.append('<p>Independent IPR analysis; attribution does not imply source endorsement.</p>')
            parts.append('</section>')
        parts.append('</main></body></html>')
        (dest / "index.html").write_text("\n".join(parts), encoding="utf-8")
    except Exception:
        shutil.rmtree(target)
        raise
    return {**plan, "staging_directory": str(dest),
            "downstream_publication_performed": False}


REVIEW_INSTRUCTIONS = {
    "rights": "Examine the exact page/document license or grant, third-party material, translation/derivative permission, attribution and current scope; record independent evidence.",
    "source_fidelity": "Compare exact archived source-text bytes with the original-language publisher version and identify truncation, missing content or transcription changes.",
    "document_integrity": "Verify complete original PDF, embedded images/graphs/third-party content, documentary completeness and rights to redistribute the entire binary.",
    "bilingual": "Compare the entire English translation to the version-pinned original; check numbers, entities, negations, event versus publication dates, modality and ambiguity.",
    "fact_checker": "Compare each substantive claim and citation to the underlying versioned evidence; distinguish official claims from independent facts, verify qualifications and absence of invented conclusions.",
    "editor": "Approve the exact reviewed translation or independently written IPR analysis, its attribution, caveats, corrections/limitations and readiness for public distribution.",
}


def unsigned_review_queue(bundle, artifacts):
    """Prepare bounded reviewer work, not reviewer approval or a rights grant.

    Safe for a collection workflow to call with local private artifacts: the
    result holds only identity, hashes, role instructions and explicit HOLD
    status; it does NOT contain original text, PDF bytes, model outputs, any
    signer secret or a publication token.
    """
    digest = _validate_bundle(bundle, artifacts)
    s = bundle["source"]
    entries = []
    for w in bundle["works"]:
        for role in sorted(REQUIRED_ROLES[w["kind"]]):
            entries.append({
                "kind": w["kind"], "role": role,
                "source_identity": s["source_identity"],
                "source_git_commit": s["source_git_commit"],
                "source_capture_sha256": s["source_capture_sha256"],
                "work_sha256": w["content_sha256"],
                "rights_scope": w["rights_scope"],
                "rights_evidence_sha256": w["rights_evidence_sha256"],
                "instruction": REVIEW_INSTRUCTIONS[role],
                "decision": "hold",
                "human_signoff_attached": False,
            })
    return {
        "schema": "ipr-unsigned-full-content-review-queue/1",
        "desk": s["desk"],
        "source_family": s["source_family"],
        "source_identity": s["source_identity"],
        "bundle_sha256": digest,
        "review_tasks": entries,
        "source_authentication_complete": False,
        "rights_independently_approved": False,
        "translation_or_analysis_approved": False,
        "public_release_authorized": False,
        "contains_original_source_bodies": False,
    }
