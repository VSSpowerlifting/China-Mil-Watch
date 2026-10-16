"""Reviewed English translation and source-anchored Korea analysis contracts.

Strictly separate labelled machine candidates from genuinely reviewed outputs.
Hash/paragraph/quote alignment establishes traceability, not semantic accuracy.
The owner must approve release outside this JSON schema in authenticated
GitHub Actions, and neither foreign media nor HWPX may be included.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from core.korea_full_content_rehearsal import original_paragraphs
from core.korea_published_originals import read_release_index

SCHEMA = "ipr-korea-reviewed-english-and-analysis/1"
REGISTER = "ipr-korea-editorial-english-publications/1"
SOURCE_RE = re.compile(r"korea-policy:([0-9]{9})\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
SAFE_MODEL = re.compile(r"[A-Za-z0-9._:/-]{2,120}\Z")
ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "research/korea_english_publications.json"
CONTENT_DIR = ROOT / "research/korea_english_reviewed"
ALLOWED_REVIEWS = {"VSSpowerlifting"}
MAX_PARAGRAPHS = 2000
MAX_ANALYSIS_CLAIMS = 12


class KoreaEnglishHold(ValueError):
    """Safe static reason codes; never expose privately reviewed wording."""


def need(condition, reason):
    if not condition:
        raise KoreaEnglishHold(reason)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def exact(value, keys, reason):
    need(type(value) is dict and set(value) == set(keys), reason)


def prose(value, reason, *, minimum=8, maximum=10000):
    need(type(value) is str and minimum <= len(value.strip()) <= maximum
         and not any((ord(c) < 32 and c not in "\r\n\t") or ord(c) == 127 for c in value),
         reason)


def utc(value):
    need(type(value) is str and re.fullmatch(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", value)
         is not None, "korea_english_review_timestamp_invalid")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        raise KoreaEnglishHold("korea_english_review_timestamp_invalid") from None


def verify_review(review, source, *, allow_machine=False):
    """Validate reviewed pack against exact *already published* original."""
    exact(review, ("schema", "source_identity", "source_sha256",
                   "model_id", "translations", "analysis",
                   "review"), "korea_english_review_schema_invalid")
    ident = source["source_identity"]
    need(review["schema"] == SCHEMA and review["source_identity"] == ident
         and review["source_sha256"] == source["original_text_sha256"],
         "korea_english_review_source_version_mismatch")
    need(type(review["model_id"]) is str and SAFE_MODEL.fullmatch(review["model_id"])
         is not None, "korea_english_model_provenance_invalid")
    ko = original_paragraphs(source["text_original"])
    need(1 <= len(ko) <= MAX_PARAGRAPHS, "korea_english_original_too_large")
    translations = review["translations"]
    need(type(translations) is list and len(translations) == len(ko),
         "korea_english_paragraph_count_mismatch")
    for i, (original, pair) in enumerate(zip(ko, translations), 1):
        exact(pair, ("index", "original_sha256", "text_en"),
              "korea_english_translation_fields_invalid")
        need(type(pair["index"]) is int and pair["index"] == i
             and pair["original_sha256"] == digest(original.encode("utf-8")),
             "korea_english_translation_alignment_invalid")
        # Government release layout contains single-word labels such as
        # "End" and "Contact"; short *accurate* translations must not be padded.
        prose(pair["text_en"], "korea_english_translation_missing",
              minimum=1, maximum=20000)
    analysis = review["analysis"]
    exact(analysis, ("heading_en", "thesis_en", "claims", "limitations_en"),
          "korea_english_analysis_fields_invalid")
    prose(analysis["heading_en"], "korea_english_analysis_heading_invalid", maximum=180)
    prose(analysis["thesis_en"], "korea_english_thesis_invalid", maximum=1400)
    prose(analysis["limitations_en"], "korea_english_limitations_missing", maximum=4000)
    claims = analysis["claims"]
    need(type(claims) is list and 2 <= len(claims) <= MAX_ANALYSIS_CLAIMS,
         "korea_english_claim_count_invalid")
    for claim in claims:
        exact(claim, ("heading_en", "analysis_en", "source_indices", "source_quotes_ko",
                      "assessment_type"), "korea_english_claim_fields_invalid")
        prose(claim["heading_en"], "korea_english_claim_heading_invalid", maximum=180)
        prose(claim["analysis_en"], "korea_english_claim_body_invalid", maximum=3800)
        need(claim["assessment_type"] in (
             "attributed_source_interpretation", "bounded_analytical_inference"),
             "korea_english_unsupported_analysis_type")
        indices = claim["source_indices"]
        quotes = claim["source_quotes_ko"]
        need(type(indices) is list and 1 <= len(indices) <= 6
             and indices == sorted(set(indices))
             and all(type(n) is int and 1 <= n <= len(ko) for n in indices),
             "korea_english_claim_indices_invalid")
        need(type(quotes) is list and len(quotes) == len(indices),
             "korea_english_claim_quote_alignment_invalid")
        for n, quote in zip(indices, quotes):
            need(type(quote) is str and 8 <= len(quote) <= 240
                 and quote in ko[n-1],
                 "korea_english_claim_quote_not_exact_source")
    stamp = review["review"]
    exact(stamp, ("status", "reviewer", "reviewed_at_utc",
                  "translation_semantics_checked", "analysis_fact_checked",
                  "attribution_checked", "source_limitations_checked"),
          "korea_english_review_attestation_invalid")
    if allow_machine:
        need(stamp["status"] in ("machine_unreviewed", "editor_approved"),
             "korea_english_review_status_invalid")
    else:
        need(stamp["status"] == "editor_approved"
             and stamp["reviewer"] in ALLOWED_REVIEWS
             and all(stamp[k] is True for k in (
                 "translation_semantics_checked", "analysis_fact_checked",
                 "attribution_checked", "source_limitations_checked")),
             "korea_english_editorial_attestation_missing")
    utc(stamp["reviewed_at_utc"])
    return {
        "identity": ident, "source_sha256": source["original_text_sha256"],
        "review_sha256": digest(
            json.dumps(review, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")),
        "paragraphs": len(ko), "claims": len(claims),
        "machine_only": stamp["status"] == "machine_unreviewed",
        "editorial_meaning_verified_by_code": False,
    }


def public_registry(index=INDEX, directory=CONTENT_DIR, *,
                    source_index=None, source_dir=None):
    """Only explicitly registered and structurally approved exact-source packs."""
    index, directory = Path(index), Path(directory)
    need(index.is_file() and not index.is_symlink()
         and index.stat().st_size <= 240000,
         "korea_english_publication_register_missing")
    try:
        payload = json.loads(index.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise KoreaEnglishHold("korea_english_publication_register_invalid") from None
    exact(payload, ("schema", "releases"),
          "korea_english_publication_register_invalid")
    need(payload["schema"] == REGISTER and type(payload["releases"]) is list
         and len(payload["releases"]) <= 50,
         "korea_english_publication_register_invalid")
    source_kwargs = {}
    if source_index is not None:
        source_kwargs["index"] = source_index
    if source_dir is not None:
        source_kwargs["original_dir"] = source_dir
    known = {r["source_identity"]: r for r in read_release_index(**source_kwargs)}
    published, ids = [], set()
    for row in payload["releases"]:
        exact(row, ("source_identity", "source_sha256", "review_sha256",
                    "owner_run_id", "released_at_utc"),
              "korea_english_publication_release_fields_invalid")
        identity = row["source_identity"]
        match = SOURCE_RE.fullmatch(identity) if type(identity) is str else None
        need(match is not None and identity not in ids and identity in known,
             "korea_english_publication_source_not_published")
        ids.add(identity)
        need(type(row["source_sha256"]) is str and HASH.fullmatch(row["source_sha256"])
             and type(row["review_sha256"]) is str and HASH.fullmatch(row["review_sha256"])
             and row["source_sha256"] == known[identity]["original_text_sha256"],
             "korea_english_publication_source_digest_mismatch")
        need(type(row["owner_run_id"]) is str
             and re.fullmatch(r"[0-9]{3,24}", row["owner_run_id"])
             and utc(row["released_at_utc"]), "korea_english_publication_owner_evidence_invalid")
        path = directory / (match.group(1) + ".json")
        need(path.is_file() and not path.is_symlink()
             and path.stat().st_size <= 1_000_000,
             "korea_english_reviewed_pack_missing")
        raw = path.read_bytes()
        try:
            review = json.loads(raw.decode("utf-8", "strict"))
        except (ValueError, UnicodeError):
            raise KoreaEnglishHold("korea_english_reviewed_pack_invalid") from None
        verified = verify_review(review, known[identity])
        need(verified["review_sha256"] == row["review_sha256"],
             "korea_english_reviewed_pack_modified")
        published.append((row, review, known[identity]))
    return published


def render_translation(row, review, source):
    esc = lambda v: html.escape(str(v), quote=True)
    number = source["source_identity"].split(":")[1]
    route = "korea-translations/" + number + ".html"
    sections = "".join(
        "<section><h3>Paragraph " + str(p["index"]) + "</h3><p lang='en'>"
        + esc(p["text_en"]) + "</p><details><summary>Korean source</summary><p lang='ko'>"
        + esc(original_paragraphs(source["text_original"])[p["index"]-1])
        + "</p></details></section>"
        for p in review["translations"]
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>English translation of Korean MND release ' + number + '</title>'
        '<link rel="canonical" href="https://indopacificrecord.org/' + route + '">'
        '<link rel="stylesheet" href="../styles.css"></head><body>'
        '<main style="max-width:76ch;margin:2rem auto;padding:1rem">'
        '<p><a href="../korea.html">South Korea Desk</a> · '
        '<a href="../korea-originals/' + number + '.html">Korean original</a></p>'
        '<h1>English translation — Korean MND release ' + number + '</h1>'
        '<p>English translation reviewed for meaning against the Korean source. '
        'Not a statement of IPR editorial agreement or independent verification.</p>'
        '<p>Source: <a href="' + esc(source["official_url"])
        + '">Republic of Korea Ministry of National Defense via Policy Briefing</a>. '
        'Translation made from source text under KOGL Type 1 with attribution; '
        'changes of language are explicitly disclosed.</p>'
        '<p>Original source SHA-256: <code>' + esc(source["original_text_sha256"])
        + '</code></p>' + sections + '</main></body></html>'
    )


def render_analysis(row, review, source):
    esc = lambda v: html.escape(str(v), quote=True)
    number = source["source_identity"].split(":")[1]
    route = "korea-analysis/" + number + ".html"
    claims = "".join(
        '<section><h2>' + esc(c["heading_en"]) + '</h2><p>' +
        esc(c["analysis_en"]) + '</p><p>Original-source paragraph references: ' +
        ", ".join(str(i) for i in c["source_indices"]) +
        '.</p><details><summary>Verbatim Korean evidence</summary>' +
        "".join("<blockquote lang='ko'>" + esc(q) + "</blockquote>"
                for q in c["source_quotes_ko"]) +
        '</details></section>'
        for c in review["analysis"]["claims"]
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + esc(review["analysis"]["heading_en"]) + ' — IPR Korea</title>'
        '<link rel="canonical" href="https://indopacificrecord.org/' + route + '">'
        '<link rel="stylesheet" href="../styles.css"></head><body>'
        '<main style="max-width:76ch;margin:2rem auto;padding:1rem">'
        '<p><a href="../korea.html">South Korea Desk</a> · '
        '<a href="../korea-originals/' + number + '.html">Verified Korean original</a> · '
        '<a href="../korea-translations/' + number + '.html">Reviewed translation</a></p>'
        '<h1>' + esc(review["analysis"]["heading_en"]) + '</h1>'
        '<p><strong>IPR source-grounded analysis</strong>, reviewed by an editor. '
        'Claims attributed to the Ministry of National Defense are not independently '
        'corroborated merely because they appear in an official release.</p>'
        '<p>' + esc(review["analysis"]["thesis_en"]) + '</p>'
        + claims + '<h2>Limits of the evidence</h2><p>'
        + esc(review["analysis"]["limitations_en"]) + '</p>'
        '<p>Official source: <a href="' + esc(source["official_url"]) +
        '">Republic of Korea Policy Briefing</a>. '
        'Evidence is confined to the cited Korean text; no media reproduced.</p>'
        '<p>Source SHA-256: <code>' + esc(source["original_text_sha256"])
        + '</code></p></main></body></html>'
    )
