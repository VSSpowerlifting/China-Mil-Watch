"""DVIDS-authorized API news metadata feasibility collector (NO production writes).

DVIDS /search is a credentialed service. Never bypass, guess or expose an API
key, reuse another client's credentials, or scrape dvidshub.net as a fallback.
The only output is neutral official news URL/date/issuer metadata to a new
private scratch JSON file outside the Git repository.

Policy: USINDOPACOM *tagged* DVIDS items are not command statements or a
complete Indo-Pacific publication history. Media, headlines, descriptions,
photographs, documents and original analysis are intentionally discarded.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
HOST = "api.dvidshub.net"
SOURCE = "https://api.dvidshub.net/search"
FAMILY = "dvids_usindopacom_news_api"
ISSUER = "dvids_defense_visual_information_distribution_service"
SCHEMA = "ipr.dvids.usindopacom.news.metadata_shadow.v1"
URL_RE = re.compile(r"https://www\.dvidshub\.net/news/([0-9]{1,12})(?:/[a-z0-9-]+)?\Z")
ID_RE = re.compile(r"news:([0-9]{1,12})\Z")
# DVIDS documents the `key-` public-key prefix, but not a suffix alphabet or
# fixed suffix length. Avoid rejecting correctly issued keys on invented rules.
KEY_PREFIX = "key-"
MAX_KEY_BYTES = 512

class DVIDSHold(ValueError):
    pass

def need(ok, reason):
    if not ok:
        raise DVIDSHold(reason)

def timestamp(value):
    need(type(value) is str and value.endswith("Z") and len(value) <= 35,
         "missing_or_non_utc_publication_timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise DVIDSHold("invalid_publication_timestamp") from None
    need(parsed.utcoffset().total_seconds() == 0, "publication_timezone_not_utc")
    return parsed

def sanitize(payload, *, observed_on_utc):
    """Strip and validate the API result; accept nothing but neutral metadata."""
    need(type(payload) is dict and set(payload) >= {"results", "page_info"},
         "search_api_shape_changed")
    rows = payload["results"]
    info = payload["page_info"]
    need(type(rows) is list and type(info) is dict and 0 < len(rows) <= 20,
         "unbounded_or_empty_news_api_results")
    need(type(info.get("results_per_page")) is int
         and 1 <= info["results_per_page"] <= 20,
         "untrusted_api_page_size")
    need(type(info.get("total_results")) is int and
         info["total_results"] >= len(rows), "untrusted_total_results")
    try:
        observation = date.fromisoformat(observed_on_utc)
    except (ValueError, TypeError):
        raise DVIDSHold("invalid_observation_day") from None
    need(observation.isoformat() == observed_on_utc, "noncanonical_observation_day")
    records, ids, urls = [], set(), set()
    for record in rows:
        need(type(record) is dict, "bad_api_news_record")
        need(record.get("type") == "news", "non_news_media_item")
        ident = record.get("id")
        url = record.get("url")
        need(type(ident) is str and ID_RE.fullmatch(ident) is not None,
             "unexpected_dvids_news_identity")
        need(type(url) is str and URL_RE.fullmatch(url) is not None,
             "noncanonical_first_party_news_url")
        need(ID_RE.fullmatch(ident).group(1) == URL_RE.fullmatch(url).group(1),
             "api_news_identity_url_mismatch")
        published = timestamp(record.get("date_published"))
        need(published.date() <= observation, "future_published_dvids_record")
        need(ident not in ids and url not in urls, "duplicate_dvids_reference")
        ids.add(ident)
        urls.add(url)
        records.append({
            "source_identity": "us-dvids-api:" + ident,
            "canonical_official_url": url,
            "publisher_posted_date": published.date().isoformat(),
            "official_issuer": ISSUER,
            "official_publisher": "DVIDS",
            "api_source_family": FAMILY,
        })
    records.sort(key=lambda r: (r["publisher_posted_date"],
                                r["source_identity"]), reverse=True)
    return records

def build_packet(api_payload, *, observed_on_utc):
    rows = sanitize(api_payload, observed_on_utc=observed_on_utc)
    normalized = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return {
        "schema": SCHEMA,
        "source_api": SOURCE,
        "source_family": FAMILY,
        "query_filters": {"cocom": "USINDOPACOM",
                          "type": "news", "max_results": 20,
                          "sort": "publishdate", "sortdir": "desc"},
        "observed_on_utc": observed_on_utc,
        "official_metadata_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
        "rows": rows,
        "first_page_only": True,
        "complete_cocom_history_claimed": False,
        "dvids_items_treated_as_pacom_statements": False,
        "original_titles_copied": False,
        "descriptions_copied": False,
        "media_rehosted": False,
        "analysis_performed": False,
        "source_remove_and_update_sync_verified": False,
        "credentials_verified_for_publisher_use": False,
        "production_records_written": 0,
        "public_release_authorized": False,
    }

def normalize_issued_key(value):
    """Strip copy/paste whitespace, never alter the DVIDS-issued key itself.

    The DVIDS public Search API key begins with 'key-'; never substitute the
    private OAuth client secret or silently bypass the publisher's key format.
    No credential contents, length, suffix characters or URL are logged.
    """
    need(type(value) is str and bool(value.strip()),
         "dvids_issued_api_key_missing")
    key = value.strip()
    need(key.startswith(KEY_PREFIX),
         "dvids_public_search_key_prefix_missing")
    suffix = key[len(KEY_PREFIX):]
    # Explain the class of rejected copy/paste error, never the secret.
    # A broad suffix character check is appropriate because DVIDS documents
    # only the key- prefix, not a suffix alphabet or fixed suffix length.
    need(bool(suffix), "dvids_public_search_key_suffix_empty")
    need(len(key.encode("utf-8")) <= MAX_KEY_BYTES,
         "dvids_public_search_key_input_over_limit")
    need(not any(char.isspace() for char in suffix),
         "dvids_public_search_key_embedded_whitespace")
    need(not any(ord(char) < 33 or ord(char) == 127 for char in suffix),
         "dvids_public_search_key_control_character")
    need(all(ord(char) < 128 for char in suffix),
         "dvids_public_search_key_non_ascii_character")
    return key


def fetch_with_issued_key(key):
    key = normalize_issued_key(key)
    params = urllib.parse.urlencode({
        "api_key": key,
        "cocom": "USINDOPACOM",
        "type": "news",
        "max_results": "20",
        "sort": "publishdate",
        "sortdir": "desc",
    })
    request = urllib.request.Request(
        SOURCE + "?" + params,
        headers={"User-Agent": "IndoPacificRecord/1.0 (official link metadata; https://indopacificrecord.org)",
                 "Accept": "application/json"})
    # Refuse redirects before following them: the issued key lives in the URL.
    # An ordinary urlopen follows redirects and could disclose that key.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=20) as response:
            need(response.geturl() == request.full_url, "api_redirect_refused")
            need(response.status == 200, "api_status_not_success")
            raw = response.read(120_001)
    except urllib.error.HTTPError as exc:
        # Never print exception URL -- the API key is in the query string.
        raise DVIDSHold("dvids_api_http_status_" + str(exc.code)) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise DVIDSHold("dvids_api_transport_unavailable") from None
    need(0 < len(raw) <= 120_000, "api_response_unbounded")
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        raise DVIDSHold("api_json_invalid") from None

def stage_private(packet, output):
    path = Path(output)
    need(path.is_absolute() and not path.exists() and not path.is_symlink(),
         "new_absolute_scratch_output_required")
    dest = path.resolve(strict=False)
    need(ROOT not in (dest, *dest.parents) and dest.parent.is_dir(),
         "scratch_output_must_be_outside_repo")
    payload = json.dumps(packet, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    need(len(payload) <= 120_000, "packet_size_unbounded")
    fd = os.open(str(dest), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return dest

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch-json", required=True)
    parser.add_argument("--owner-authorized-api-rehearsal", action="store_true")
    args = parser.parse_args(argv)
    if not args.owner_authorized_api_rehearsal:
        raise SystemExit("HOLD: explicit owner-approved DVIDS API rehearsal required")
    try:
        payload = fetch_with_issued_key(os.environ.get("DVIDS_API_KEY"))
        packet = build_packet(payload,
                              observed_on_utc=datetime.now(timezone.utc).date().isoformat())
        stage_private(packet, args.scratch_json)
    except (DVIDSHold, OSError) as exc:
        raise SystemExit("HOLD: DVIDS API metadata-only shadow: " + str(exc))
    print("PASS_DVIDS_API_BOUNDED_NEUTRAL_METADATA_ONLY",
          len(packet["rows"]),
          "items; private scratch only; no production DB or Pages changes")

if __name__ == "__main__":
    main()
