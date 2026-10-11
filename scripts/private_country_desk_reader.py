"""PRIVATE analyst-facing reader for Philippines, Vietnam and Korea shadow records.

Reads literal, locally available Git commits (never mutable branch tips).
Searches preserved article text IN MEMORY, then displays ONLY publisher metadata,
source URLs, IDs, and exact state SHA. Does not export body text or screenshots,
fetch publishers, approve reuse, alter SQLite/state, or touch production.

Country desks can be used for private research immediately, without
mistaking unapproved shadow records for publicly admitted archive records.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sqlite3
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "ipr-private-shadow-desk-reader/1"
SHA = re.compile(r"[0-9a-f]{40}\Z")
MAX_DB_BYTES = 64 * 1024 * 1024
MAX_SCANNED_ROWS = 20000
MAX_RESULTS = 300
SOURCES = {
    "ph_afp_articles": ("philippines", "Armed Forces of the Philippines", "www.afp.mil.ph", "standard"),
    "ph_nsc_official_statements": ("philippines", "National Security Council (publisher)", "nsc.gov.ph", "standard"),
    "vn_mps_foreign_affairs_vi": ("vietnam", "Ministry of Public Security", "bocongan.gov.vn", "vietnam"),
    "vn_moit_energy_vi": ("vietnam", "Ministry of Industry and Trade — Energy", "moit.gov.vn", "vietnam"),
    "vn_moit_foundational_industry_vi": ("vietnam", "Ministry of Industry and Trade — Foundational Industry", "moit.gov.vn", "vietnam"),
    "kr_policy_mnd_releases": ("korea", "Ministry of National Defense (issuer); Korea Policy Briefing (publisher)", "www.korea.kr", "korea"),
}


class ReaderHold(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise ReaderHold(reason)


def git(repo, *args, cap=MAX_DB_BYTES):
    repo = Path(repo)
    require(repo.is_dir() and not repo.is_symlink(),
            "repository must be an existing nonsymlink local directory")
    try:
        process = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, check=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        raise ReaderHold("immutable source Git object unavailable") from None
    require(len(process.stdout) <= cap, "Git object exceeds local read cap")
    return process.stdout


def parse_input(value):
    require(isinstance(value, str), "source argument missing")
    parts = value.split(",", 2)
    require(len(parts) == 3, "source must be SLUG,LOCAL_GIT_REPO,EXACT_SHA")
    slug, repo, commit = parts
    require(slug in SOURCES and SHA.fullmatch(commit) is not None,
            "unknown source or nonimmutable commit")
    path = Path(repo).expanduser()
    require(path.is_absolute() and path.is_dir() and not path.is_symlink(),
            "source repository must be an absolute nonsymlink path")
    require(path.resolve() != ROOT and ROOT not in path.resolve().parents,
            "private source state must be inspected outside the production checkout")
    return slug, path, commit


def _url(url, expected_host):
    require(isinstance(url, str) and len(url) <= 1700, "missing or excessive URL")
    p = urlsplit(url)
    require(p.scheme == "https" and p.hostname == expected_host and
            p.port is None and not p.username and not p.password and
            not p.fragment and p.path.startswith("/"),
            "record is not an exact official HTTPS publisher link")
    return url


def _row(rec, slug, commit):
    country, institution, host, _ = SOURCES[slug]
    sid, url, title, published, first = (rec[k] for k in
        ("source_identity", "url", "title_original", "published_date", "first_seen_run"))
    require(all(isinstance(x, str) and x for x in
                (sid, url, title, published, first)), "missing source identity/metadata")
    require(len(sid) <= 180 and len(title) <= 700 and len(first) <= 100,
            "record metadata exceeds bounded display size")
    try:
        date.fromisoformat(published)
    except ValueError:
        raise ReaderHold("invalid source publication date") from None
    _url(url, host)
    require(rec["source_slug"] == slug, "record source family misbound")
    if slug == "kr_policy_mnd_releases":
        match = re.fullmatch(r"korea-policy:([0-9]{6,20})", sid)
        require(match is not None and url ==
                "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" +
                match.group(1), "Korea MND original identity and canonical portal URL disagree")
        require(rec.get("language_tag") == "ko", "Korean original-language label missing")
        try:
            metadata = json.loads(rec["metadata_json"])
        except (TypeError, ValueError):
            raise ReaderHold("Korean record provenance is not valid JSON") from None
        require(isinstance(metadata, dict) and
                metadata.get("issuer") == "국방부" and
                metadata.get("publisher") == "대한민국 정책브리핑" and
                metadata.get("publication_kind") == "syndicated_press_release" and
                metadata.get("body_scope") == "published_hwpx_text" and
                metadata.get("attachments_collected") is True,
                "Korean republication issuer, publisher, or document scope is unverified")
        document_url = metadata.get("document_url")
        document_match = re.fullmatch(
            r"https://www\.korea\.kr/common/download\.do\?fileId=[0-9]+&tblKey=GMN",
            document_url) if isinstance(document_url, str) else None
        require(document_match is not None, "Korean HWPX document identity invalid")
        require(isinstance(rec.get("text_original"), str) and
                bool(rec["text_original"].strip()), "Korean original text missing")
        original_sha = rec.get("content_sha256")
        require(isinstance(original_sha, str) and
                re.fullmatch(r"[0-9a-f]{64}", original_sha) is not None and
                hashlib.sha256(rec["text_original"].encode("utf-8")).hexdigest() == original_sha,
                "Korean stored original text hash mismatch")
        for sha in (rec.get("capture_sha256"),
                    metadata.get("document_capture_sha256")):
            require(isinstance(sha, str) and
                    re.fullmatch(r"[0-9a-f]{64}", sha) is not None,
                    "Korean preserved original-document capture reference invalid")
        # Metadata-only admission: no HWPX re-extraction, real-language review,
        # source reuse permission, translation, or public citation authority.
    return {"country": country, "institution": institution, "source_slug": slug,
            "identity": sid, "url": url, "title": " ".join(title.split()),
            "published_date": published, "first_seen_run": first,
            "state_commit": commit, "review_status": "not_human_reviewed_for_public_use"}


def _read_snapshot(slug, repo, commit, term):
    # Reconfirm actual Git commit and source-specific clock: no branch names,
    # mutable working DBs, or non-Git state.
    require(git(repo, "cat-file", "-t", commit, cap=40).strip() == b"commit",
            "not an immutable Git commit")
    clock_raw = git(repo, "show", commit + ":state/clock.json", cap=10000)
    try:
        clock = json.loads(clock_raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ReaderHold("source clock malformed") from None
    require(isinstance(clock, dict) and
            isinstance(clock.get("day_zero_run_id"), str) and
            (re.fullmatch(r"[1-9][0-9]*-[1-9][0-9]*", clock["day_zero_run_id"]) or
             (slug == "kr_policy_mnd_releases" and
              clock["day_zero_run_id"] == "local-native-20261006-korea")) and
            isinstance(clock.get("day_zero_utc"), str),
            "source clock missing immutable Day 0 provenance")
    # Existing AFP, NSC and MPS/MOIT clock files intentionally have no desk
    # key. They cannot prove source identity: the SQLite rows must do that.
    if "desk" in clock or "desk_id" in clock:
        expected = SOURCES[slug][0]
        require(clock.get("desk", clock.get("desk_id")) == expected,
                "source clock claims a different desk")
    size = git(repo, "cat-file", "-s", commit + ":state/shadow.db", cap=32)
    try:
        n = int(size)
    except ValueError:
        raise ReaderHold("shadow DB Git size is invalid") from None
    require(0 < n <= MAX_DB_BYTES, "shadow DB too large for bounded private inspection")
    data = git(repo, "show", commit + ":state/shadow.db", cap=MAX_DB_BYTES)
    require(len(data) == n and data.startswith(b"SQLite format 3\x00"),
            "pinned source data is not the recorded SQLite blob")
    with tempfile.TemporaryDirectory(prefix="ipr-private-desk-") as td:
        local = Path(td) / "shadow.db"
        local.write_bytes(data)
        # Immutable, read-only connection; never journal or rewrite source DB.
        with sqlite3.connect(local.as_uri() + "?mode=ro&immutable=1", uri=True) as cx:
            cx.row_factory = sqlite3.Row
            expected = {"shadow_records", "shadow_versions"} if (
                SOURCES[slug][3] == "vietnam") else {"shadow_records"}
            tables = {x[0] for x in cx.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            require(expected <= tables, "pinned source schema is missing required tables")
            if SOURCES[slug][3] == "korea":
                require("shadow_meta" in tables and
                        cx.execute("SELECT desk FROM shadow_meta").fetchall() ==
                        [("korea",)], "Korean pinned DB is not a Korea shadow state")
            if SOURCES[slug][3] == "vietnam":
                sql = """SELECT r.source_identity, r.source_slug, r.url,
                    v.title_original, r.published_date, r.first_seen_run,
                    v.text_original FROM shadow_records r
                    JOIN shadow_versions v ON
                    v.source_identity=r.source_identity AND
                    v.content_sha256=r.current_content_sha256
                    ORDER BY r.published_date DESC, r.source_identity"""
            elif SOURCES[slug][3] == "korea":
                sql = """SELECT source_identity, source_slug, url, title_original,
                    published_date, first_seen_run, text_original, language_tag,
                    metadata_json, content_sha256, capture_sha256
                    FROM shadow_records
                    ORDER BY published_date DESC, source_identity"""
            else:
                sql = """SELECT source_identity, source_slug, url, title_original,
                    published_date, first_seen_run, text_original
                    FROM shadow_records
                    ORDER BY published_date DESC, source_identity"""
            rows = list(cx.execute(sql))
            require(len(rows) <= MAX_SCANNED_ROWS, "source snapshot exceeds audit row cap")
            require(len(rows) == cx.execute(
                "SELECT COUNT(*) FROM shadow_records").fetchone()[0],
                "incomplete version join or changed source row count")
            matches = []
            for raw in rows:
                rec = dict(raw)
                out = _row(rec, slug, commit)
                # Original full text is used in-process for local full-text
                # filtering only; it never enters emitted metadata/HTML/JSON.
                if term and term.casefold() not in (
                    out["title"] + "\n" + (rec["text_original"] or "")).casefold():
                    continue
                matches.append(out)
            return matches, len(rows)


def build(source_args, *, term="", country=None, max_results=100):
    require(type(max_results) is int and 1 <= max_results <= MAX_RESULTS,
            "display cap must be 1..300")
    require(isinstance(term, str) and len(term) <= 140, "query too long")
    require(country in (None, "philippines", "vietnam", "korea"), "unknown desk filter")
    parsed = [parse_input(x) for x in source_args]
    require(parsed and len(parsed) <= len(SOURCES), "1..6 pinned sources required")
    require(len({x[0] for x in parsed}) == len(parsed), "duplicate family source")
    all_rows, summaries = [], []
    for slug, repo, commit in parsed:
        if country is not None and SOURCES[slug][0] != country:
            continue
        rows, total = _read_snapshot(slug, repo, commit, term)
        summaries.append({"source_slug": slug, "country": SOURCES[slug][0],
                          "institution": SOURCES[slug][1], "state_commit": commit,
                          "stored_records": total, "query_matches": len(rows)})
        all_rows.extend(rows)
    all_rows.sort(key=lambda v: (v["published_date"], v["identity"]), reverse=True)
    # Factual metadata only. No article bodies/excerpts, source captures or license claims.
    return {"schema": SCHEMA, "status": "private_research_not_source_admitted",
            "query": term, "desk_filter": country, "sources": summaries,
            "matched_total": len(all_rows), "results": all_rows[:max_results],
            "truncated": len(all_rows) > max_results,
            "source_body_text_exported": False,
            "automated_source_rights_approved": False,
            "human_source_review_completed": False,
            "production_records_changed": False,
            "country_desks_promoted": False,
            "public_release_authorized": False}


def render_html(report):
    """Self-contained PRIVATE local metadata browser, safe against hostile titles."""
    require(report.get("schema") == SCHEMA, "unknown report schema")
    meta = []
    for x in report["results"]:
        url = html.escape(x["url"], quote=True)
        title = html.escape(x["title"], quote=True)
        institution = html.escape(x["institution"], quote=True)
        rid = html.escape(x["identity"], quote=True)
        state = html.escape(x["state_commit"], quote=True)
        key = html.escape((x["title"] + " " + x["institution"] + " " +
                           x["identity"]).casefold(), quote=True)
        meta.append(
            '<article class="record" data-search="' + key + '" data-country="' +
            html.escape(x["country"], quote=True) + '">'
            '<div class="record-meta">' + institution + ' · ' +
            html.escape(x["published_date"]) + '</div><h2><a rel="noopener noreferrer" '
            'target="_blank" href="' + url + '">' + title + '</a></h2>' +
            '<div class="evidence"><code>' + rid + '</code><span>State ' +
            state[:12] + '…</span><span>PUBLIC REVIEW PENDING</span></div></article>')
    source_parts = "; ".join(
        html.escape(x["institution"]) + " (" + str(x["stored_records"]) + " stored)"
        for x in report["sources"])
    summary = html.escape(
        str(report["matched_total"]) + " local matches; displaying " +
        str(len(report["results"])) + ".")
    notice = ("Private analyst-only index • source bodies never included • "
              "not a public archive, review, license or coverage certification.")
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow,noarchive">'
        '<title>IPR | Private country desk reader</title><style>'
        ':root{color-scheme:light;font-family:Georgia,serif;background:#f4f1e9;color:#242a28}'
        'body{max-width:960px;margin:3rem auto;padding:0 1.4rem;line-height:1.6}'
        'h1{font-size:2.5rem;margin-bottom:0}h2{font-size:1.2rem;line-height:1.4}'
        'a{color:#214e50}.notice{padding:1rem;border:1px solid #a9b5aa}'
        '.filters{display:flex;gap:1rem;flex-wrap:wrap;margin:2rem 0}'
        'input,select{font:inherit;padding:.6rem;border:1px solid #777;background:white}'
        'input{flex:1;min-width:220px}.record{padding:1.2rem 0;border-bottom:1px solid #c8cbc5}'
        '.record-meta,.evidence{font:12px/1.6 system-ui,sans-serif;letter-spacing:.02em;color:#57645f}'
        '.evidence{display:flex;gap:1rem;flex-wrap:wrap}.small{color:#5c6661}'
        '</style></head><body><p class="small">INDO-PACIFIC RECORD / PRIVATE RESEARCH</p>'
        '<h1>Country desk reader</h1><p class="notice">' +
        html.escape(notice) + '</p><p>' + summary + '</p><p class="small">' +
        source_parts + '</p><div class="filters"><input id="search" type="search" '
        'aria-label="Filter displayed source metadata" placeholder="Filter titles and identities">'
        '<select id="country" aria-label="Country filter"><option value="">All countries</option>'
        '<option value="philippines">Philippines</option><option value="vietnam">Vietnam</option><option value="korea">South Korea</option>'
        '</select></div><main id="items">' + "".join(meta) + '</main>'
        '<script>(function(){const q=document.getElementById("search");'
        'const c=document.getElementById("country");const a=[...document.querySelectorAll(".record")];'
        'function f(){const v=q.value.toLocaleLowerCase(),d=c.value;'
        'for(const n of a){n.hidden=!!((d&&n.dataset.country!==d)||'
        '(v&&!n.dataset.search.includes(v)));}}q.addEventListener("input",f);'
        'c.addEventListener("change",f);})();</script>'
        '</body></html>'
    )


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", action="append", required=True,
                   help="SLUG,ABSOLUTE_LOCAL_GIT_REPO,EXACT_40CHAR_COMMIT (repeat)")
    p.add_argument("--query", default="", help="private title/body search; never exports body")
    p.add_argument("--country", choices=("philippines", "vietnam", "korea"))
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--format", choices=("json", "html"), default="json")
    p.add_argument("--output", help="required absolute OUTSIDE-repository path for HTML")
    args = p.parse_args(argv)
    try:
        result = build(args.source, term=args.query, country=args.country,
                       max_results=args.limit)
        if args.format == "html":
            require(args.output, "HTML export needs explicit private destination")
            output = Path(args.output).expanduser()
            require(output.is_absolute() and output.parent.is_dir() and
                    not output.is_symlink() and
                    ROOT not in output.resolve().parents and output.resolve() != ROOT,
                    "HTML may be written only outside the production checkout")
            require(not output.exists(), "refuse to replace an existing private report")
            output.write_text(render_html(result), encoding="utf-8")
            print("Private metadata-only desk report written: " + str(output))
        else:
            require(args.output is None, "JSON output is stdout-only; redirect privately")
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except (ReaderHold, sqlite3.DatabaseError, OSError, UnicodeError) as exc:
        p.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
