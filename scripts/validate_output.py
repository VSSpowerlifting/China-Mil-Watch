#!/usr/bin/env python3
"""
Pre-deploy validation for the rendered site in output/.

Run after site generation and before any GitHub Pages deploy. A non-zero exit
blocks deployment, so a broken render never reaches production. Stdlib-only so
it runs in workflows without installing project dependencies.

Checks (each failure is fatal unless noted):
  1. output/index.html exists and is non-empty.
  2. No unrendered Jinja markers ({{ , {% , %}) remain in any .html file.
  3. output/data/articles.json exists and parses as a JSON list.
  4. Every article_path referenced in articles.json exists on disk.
  5. Every non-empty `date` is a real YYYY-MM-DD (empty date → warning only).
  6. No analyzed article has a blank summary.
  7. The PLA Watch (output/the-pla-watch/): every sidecar JSON parses, has
     matching HTML (and vice versa), consistent dates/issue numbers/source
     counts, body text sufficient to re-render, and a source trail whose
     entries carry title/url/source/date. Index and archive must link every
     edition. Missing LinkedIn .txt and cadence gaps are warnings.
  8. Every analyzed article in pla_watch.db has a rendered page (orphaned
     pages are a warning). Only runs against the repo's own output/ when the
     DB is present, so validating a copied tree still works.

Usage:
    python3 scripts/validate_output.py [output_dir]   # default: ../output
"""

import json
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.reconcile_db import read_only                      # noqa: E402
# Stdlib-only (re, datetime): no network, no config, no model. Imported so the
# deploy gate validates against the same contract the generator and the
# re-renderer use, rather than a second copy of the allowed values.
from core.edition_identity import (                            # noqa: E402
    IdentityError, parse_timing, resolve_identity)

#: The published origin. Deliberately a literal rather than `from config import
#: SITE_ORIGIN`: this script is the deploy gate and the workflow runs it on the
#: runner's system Python, with none of the project's dependencies installed.
#: Importing `config` would pull in python-dotenv and fail the deploy before it
#: validated anything. `tests/test_site_mode_contract.py` asserts this value and
#: `config.SITE_ORIGIN` agree, so the copy cannot drift.
SITE_ORIGIN = "https://indopacificrecord.org"

# Jinja markers that indicate an unrendered template. Deliberately excludes the
# bare "}}" because minified CSS media queries legitimately end in "}}"; any
# unrendered expression still contains "{{", so detection stays complete.
JINJA_MARKER = re.compile(r"\{\{|\{%|%\}")
DATE_RE      = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _resolve_output_dir(argv: list[str]) -> Path:
    if len(argv) > 1:
        return Path(argv[1]).resolve()
    return (Path(__file__).resolve().parent.parent / "output").resolve()


def validate(output_dir: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). A non-empty errors list must block deploy."""
    errors:   list[str] = []
    warnings: list[str] = []

    if not output_dir.is_dir():
        return ([f"output directory does not exist: {output_dir}"], warnings)

    # 1. index.html present and non-empty
    index = output_dir / "index.html"
    if not index.is_file():
        errors.append("output/index.html is missing")
    elif index.stat().st_size == 0:
        errors.append("output/index.html is empty")

    # 2. No unrendered Jinja markers in any rendered HTML file
    for html in sorted(output_dir.rglob("*.html")):
        try:
            text = html.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"could not read {html.relative_to(output_dir)}: {exc}")
            continue
        m = JINJA_MARKER.search(text)
        if m:
            line = text.count("\n", 0, m.start()) + 1
            errors.append(
                f"unrendered Jinja marker {m.group()!r} in "
                f"{html.relative_to(output_dir)}:{line}"
            )

    # 3. articles.json present and parses as a list
    data_file = output_dir / "data" / "articles.json"
    if not data_file.is_file():
        errors.append("output/data/articles.json is missing")
        return (errors, warnings)
    try:
        articles = json.loads(data_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"output/data/articles.json does not parse: {exc}")
        return (errors, warnings)
    if not isinstance(articles, list):
        errors.append("output/data/articles.json is not a JSON list")
        return (errors, warnings)

    # 4–6. Per-article integrity
    missing_pages: list[str] = []
    bad_dates:     list[str] = []
    blank_dates:   list[str] = []
    blank_summary: list[str] = []

    for entry in articles:
        aid = entry.get("id", "?")

        rel = entry.get("article_path", "")
        if not rel or not (output_dir / rel).is_file():
            missing_pages.append(f"id={aid} → {rel or '(no article_path)'}")

        d = (entry.get("date") or "").strip()
        if not d:
            blank_dates.append(str(aid))
        elif not DATE_RE.match(d) or not _is_real_date(d):
            bad_dates.append(f"id={aid} → {d!r}")

        if not (entry.get("summary") or "").strip():
            blank_summary.append(str(aid))

    if missing_pages:
        errors.append(
            f"{len(missing_pages)} article page(s) referenced but missing: "
            + ", ".join(missing_pages[:10])
            + (" …" if len(missing_pages) > 10 else "")
        )
    if bad_dates:
        errors.append(
            f"{len(bad_dates)} article(s) with malformed date: "
            + ", ".join(bad_dates[:10])
            + (" …" if len(bad_dates) > 10 else "")
        )
    if blank_summary:
        errors.append(
            f"{len(blank_summary)} analyzed article(s) with a blank summary: ids "
            + ", ".join(blank_summary[:20])
            + (" …" if len(blank_summary) > 20 else "")
        )
    if blank_dates:
        warnings.append(
            f"{len(blank_dates)} article(s) with an empty date: ids "
            + ", ".join(blank_dates[:20])
            + (" …" if len(blank_dates) > 20 else "")
        )

    _validate_pla_watch(output_dir, errors, warnings)

    _validate_editorial_images(output_dir, errors, warnings)

    _validate_db_coverage(output_dir, errors, warnings)

    return (errors, warnings)


# ── DB ↔ output coverage ────────────────────────────────────────────────────

def _validate_db_coverage(output_dir: Path, errors: list, warnings: list) -> None:
    """
    Every analyzed article must have a rendered page.

    Why this exists (2026-08-03): the 07-30 translation backfill wrote 117
    analyzed articles to the DB, a reconcile merge carried them onto main, and
    nothing re-rendered. Checks 1-7 all read output/ in isolation, so a site
    missing a sixth of its analyzed corpus passed the gate through four
    consecutive deploys. Any path that writes the DB without re-rendering —
    backfills, reconciles, merges — reproduces this, so the gate has to compare
    the two rather than trust either alone.

    Skipped when the DB is absent or a non-default output dir was passed, so
    validating a copied or deployed tree still works.
    """
    repo_root = Path(__file__).resolve().parent.parent
    db_path = repo_root / "pla_watch.db"
    if not db_path.is_file() or output_dir != (repo_root / "output").resolve():
        return

    article_dir = output_dir / "article"
    if not article_dir.is_dir():
        errors.append("output/article/ is missing — no article pages rendered")
        return

    # Reads a scratch copy, not the tracked file. A direct `mode=ro` URI is not
    # a portable, side-effect-free read of a WAL database: depending on SQLite,
    # the VFS and the filesystem it either fails to open or creates the sidecars
    # beside the input (DECISION_LOG 2026-08-14, corrected 2026-08-17). Where it
    # failed, this raised, was swallowed into a warning, and check 8 silently did
    # not run — the one check that exists because output lagged the DB by 117
    # articles across four deploys (DECISION_LOG 2026-08-03). A gate that
    # disappears quietly is worse than no gate.
    try:
        with read_only(db_path) as conn:
            db_ids = {
                str(r[0]) for r in conn.execute(
                    "SELECT id FROM articles "
                    " WHERE analyzed_at IS NOT NULL AND passed_relevance = 1"
                )
            }
    except (sqlite3.Error, OSError) as exc:
        # An unreadable database is a failed check, not a note. The file exists
        # — that was established above — so this is a real fault.
        errors.append(
            f"could not read pla_watch.db for the coverage check: {exc}")
        return

    page_ids = {p.stem for p in article_dir.glob("*.html")}

    unrendered = sorted(db_ids - page_ids, key=lambda s: int(s) if s.isdigit() else 0)
    if unrendered:
        errors.append(
            f"{len(unrendered)} analyzed article(s) in pla_watch.db have no "
            "rendered page — run `site/generator.py`: ids "
            + ", ".join(unrendered[:20])
            + (" …" if len(unrendered) > 20 else "")
        )

    orphans = sorted(page_ids - db_ids, key=lambda s: int(s) if s.isdigit() else 0)
    if orphans:
        warnings.append(
            f"{len(orphans)} rendered page(s) have no analyzed article in the DB: ids "
            + ", ".join(orphans[:20])
            + (" …" if len(orphans) > 20 else "")
        )


# ── Editorial imagery (Source-Derived Signal Graphics) ──────────────────────

# Path token as rendered into HTML (src/href/url(...) values), including any
# leading ../ segments so it can be resolved against the page's directory.
EDITORIAL_REF_RE = re.compile(r"[^\"'()\s]*assets/editorial/[^\"'()\s]+")
EDITORIAL_ID_TAG_RE = re.compile(r"<[^>]*data-editorial-id=\"([^\"]+)\"[^>]*>")
ARIA_LABEL_RE = re.compile(r"aria-label=\"[^\"]+\"")

# Retired conventional-figure patterns: the veil system replaced these
# blocks; their reappearance means a template regression.
RETIRED_FIGURE_PATTERNS = ('class="lead-figure"', "hero-figure", "issue-cover-thumb",
                           'class="cover-figure"', "entry-thumb")


def _required_editorial_derivatives(entry: dict) -> set:
    """Derivative filenames this manifest entry's routes+treatment require
    (§0 naming contract — kept in sync with scripts/pw_env.py, duplicated
    here so this validator stays stdlib-only)."""
    match = entry.get("match") or {}
    routes = match.get("routes") or []
    treatment = entry.get("treatment") or "veil"
    eid = entry.get("id") or ""
    names = set()
    if "home" in routes or "article" in routes:
        if treatment == "dither":
            names.add(f"{eid}-dither-ink.png")
        else:
            names.add(f"{eid}-duo-paper.jpg")
    if "pw-post" in routes:
        names.add(f"{eid}-duo-navy.jpg")
    return names


def _source_veil_entry(eid: str, output_dir: Path, errors: list, rel):
    """Resolve an automatic Signal Veil id ('src-YYYY-MM-DD') to a
    manifest-shaped entry.

    These are the V&M §2 "source photographs" class — pulled verbatim from an
    edition's own cited article by scripts/fetch_article_image.py, not from
    the curated PD/CC library — so they are validated against their fetch
    metadata and derivative on disk instead of against manifest.json. The
    credit/aria/'not evidence' checks that follow are the same for both
    classes, and the exact-URL grounding is checked harder here: the article
    the photo came from must be linked on the page.
    """
    date = eid[4:]
    media = output_dir / "the-pla-watch" / "media"
    meta_path = media / f"{date}-source-image.json"
    if not meta_path.is_file():
        errors.append(f"{rel}: source veil {eid!r} has no fetch metadata at "
                      f"the-pla-watch/media/{date}-source-image.json")
        return None
    if not (media / f"{date}-veil.jpg").is_file():
        errors.append(f"{rel}: source veil {eid!r} derivative missing: "
                      f"the-pla-watch/media/{date}-veil.jpg")
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{rel}: source veil {eid!r} metadata unreadable ({exc})")
        return None
    article_url = meta.get("article_url")
    if not article_url:
        errors.append(f"{rel}: source veil {eid!r} metadata carries no article_url — "
                      f"provenance cannot be verified")
        return None
    return {"id": eid, "source_page": article_url}


def _validate_editorial_images(output_dir: Path, errors: list, warnings: list) -> None:
    site_editorial = Path(__file__).resolve().parent.parent / "site" / "assets" / "editorial"
    manifest_path = site_editorial / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        # Imagery is optional; a missing manifest just means no images.
        warnings.append(f"editorial manifest unreadable ({exc}); image checks skipped")
        return
    if not isinstance(manifest, list):
        warnings.append("editorial manifest is not a JSON list; image checks skipped")
        return

    by_id = {e.get("id"): e for e in manifest if isinstance(e, dict) and e.get("id")}
    site_deriv = site_editorial / "derivatives"
    out_editorial = output_dir / "assets" / "editorial"
    out_deriv = out_editorial / "derivatives"

    # 2. Required derivatives exist on both sides; sources copied to output.
    for entry in manifest:
        if not isinstance(entry, dict):
            continue
        eid = entry.get("id", "?")
        routes = (entry.get("match") or {}).get("routes") or []
        for name in sorted(_required_editorial_derivatives(entry)):
            if not (site_deriv / name).is_file():
                errors.append(f"editorial: required derivative missing on site side: "
                              f"site/assets/editorial/derivatives/{name} (entry {eid})")
            if not (out_deriv / name).is_file():
                errors.append(f"editorial: required derivative missing in output: "
                              f"assets/editorial/derivatives/{name} (entry {eid})")
        if routes and entry.get("file"):
            if not (out_editorial / entry["file"]).is_file():
                errors.append(f"editorial: source image missing in output: "
                              f"assets/editorial/{entry['file']} (entry {eid})")

    # 3–6. Rendered-page checks.
    for html in sorted(output_dir.rglob("*.html")):
        try:
            text = html.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # unreadable files already reported by the marker check
        rel = html.relative_to(output_dir)

        # 3. Every editorial asset reference must resolve to a real file.
        for ref in set(EDITORIAL_REF_RE.findall(text)):
            target = (html.parent / ref).resolve()
            if not target.is_file():
                errors.append(f"{rel}: rendered reference points at missing asset: {ref}")

        # 4. Every veil/ghost element: known id, credit link, aria-label,
        #    and the standing "not evidence" language on the page.
        for m in EDITORIAL_ID_TAG_RE.finditer(text):
            eid = m.group(1)
            if eid.startswith("src-"):
                entry = _source_veil_entry(eid, output_dir, errors, rel)
            else:
                entry = by_id.get(eid)
                if entry is None:
                    errors.append(f"{rel}: data-editorial-id={eid!r} not in manifest")
            if entry is None:
                continue
            if entry.get("source_page") and entry["source_page"] not in text:
                errors.append(f"{rel}: editorial element {eid!r} has no credit link "
                              f"to {entry['source_page']}")
            if not ARIA_LABEL_RE.search(m.group(0)):
                errors.append(f"{rel}: editorial element {eid!r} missing a non-empty aria-label")
            if "not evidence" not in text.lower():
                errors.append(f"{rel}: page renders editorial imagery ({eid!r}) without "
                              f"'not evidence' context language")

        # 5. Article pages: exact-URL match must be visible on the page
        #    (the "View original source" href).
        if rel.parts[0] == "article":
            for m in EDITORIAL_ID_TAG_RE.finditer(text):
                eid = m.group(1)
                entry = by_id.get(eid)
                if entry is None:
                    continue  # already reported above
                urls = (entry.get("match") or {}).get("article_urls") or []
                if urls and not any(u in text for u in urls):
                    errors.append(f"{rel}: editorial image {eid!r} rendered but none of "
                                  f"its match.article_urls appear on the page")

        # 6. Retired conventional-figure patterns must not reappear.
        for pattern in RETIRED_FIGURE_PATTERNS:
            if pattern in text:
                errors.append(f"{rel}: retired pattern {pattern!r} found — conventional "
                              f"figure block where the veil system should render")


# ── The PLA Watch (weekly editions) ──────────────────────────────────────────

PW_REQUIRED_FIELDS = (
    "date", "week_ending", "week_start", "title", "dek",
    "n_articles", "n_significant", "edition_type", "source_trail",
)
PW_BODY_FIELDS = (
    "opening_note", "what_stood_out", "why_it_matters",
    "what_was_routine", "what_im_watching_next",
)


def _validate_pla_watch(output_dir: Path, errors: list, warnings: list) -> None:
    pw_dir = output_dir / "the-pla-watch"
    posts_dir = pw_dir / "posts"
    if not posts_dir.is_dir():
        return  # No weekly publication in this output tree.

    sidecars = []
    for json_path in sorted(posts_dir.glob("*.json")):
        rel = f"the-pla-watch/posts/{json_path.name}"
        try:
            sc = json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"{rel} does not parse: {exc}")
            continue

        # Publication identity and timing, through the canonical contract. A
        # sidecar that omits both is historical and stays valid; a value the
        # repository cannot explain is an error, not a warning, because a page
        # would otherwise render under a publication nobody declared.
        if "publication" in sc:
            try:
                resolve_identity({"publication": sc.get("publication"),
                                  "issue_number": sc.get("issue_number")})
            except IdentityError as exc:
                errors.append(f"{rel}: publication — {exc}")
        try:
            parse_timing(sc.get("publication_timing"))
        except IdentityError as exc:
            errors.append(f"{rel}: publication_timing — {exc}")

        missing = [f for f in PW_REQUIRED_FIELDS if not sc.get(f) and sc.get(f) != 0]
        if missing:
            errors.append(f"{rel}: missing field(s) {', '.join(missing)}")

        d, we, ws = sc.get("date", ""), sc.get("week_ending", ""), sc.get("week_start", "")
        if json_path.stem != d:
            errors.append(f"{rel}: filename does not match date field {d!r}")
        if d != we:
            errors.append(f"{rel}: date {d!r} != week_ending {we!r}")
        try:
            span = (date.fromisoformat(we) - date.fromisoformat(ws)).days
            if span != 6:
                msg = f"{rel}: week_start→week_ending spans {span} days, expected 6"
                # Pilot editions legitimately covered a shorter window.
                if "pilot" in (sc.get("edition_label") or "").lower():
                    warnings.append(msg + " (pilot edition)")
                else:
                    errors.append(msg)
        except ValueError:
            errors.append(f"{rel}: malformed week_start/week_ending ({ws!r}, {we!r})")

        n_articles = sc.get("n_articles") or 0
        n_sig = sc.get("n_significant") or 0
        trail = sc.get("source_trail") or []
        if n_sig > n_articles:
            errors.append(f"{rel}: n_significant ({n_sig}) > n_articles ({n_articles})")
        if len(trail) > n_articles:
            errors.append(f"{rel}: source_trail has {len(trail)} entries but n_articles={n_articles}")
        undated = 0
        for i, entry in enumerate(trail):
            bad = [k for k in ("title", "url", "source") if not entry.get(k)]
            if bad:
                errors.append(f"{rel}: source_trail[{i}] missing {', '.join(bad)}")
            if not entry.get("date"):
                undated += 1
        if undated:
            # Early editions did not record per-item dates; report only.
            warnings.append(f"{rel}: {undated}/{len(trail)} source_trail entries have no date")
            ed = entry.get("date", "")
            if ed and (ws and we) and not (ws <= ed <= we):
                warnings.append(f"{rel}: source_trail[{i}] dated {ed}, outside {ws}..{we}")
        if n_sig > 0 and trail and not any(e.get("is_significant") for e in trail):
            warnings.append(f"{rel}: n_significant={n_sig} but no source_trail entry is marked significant")

        if not any((sc.get(f) or "").strip() for f in PW_BODY_FIELDS):
            errors.append(f"{rel}: no body text fields — sidecar cannot re-render the post")

        if not json_path.with_suffix(".html").is_file():
            errors.append(f"{rel}: rendered HTML {json_path.stem}.html is missing")

        sidecars.append(sc)

    # Orphan HTML (post page with no sidecar)
    for html_path in sorted(posts_dir.glob("*.html")):
        if not html_path.with_suffix(".json").is_file():
            errors.append(f"the-pla-watch/posts/{html_path.name}: no sidecar JSON")

    # Issue numbers: present, unique, chronological
    numbered = [(sc.get("date", ""), sc.get("issue_number")) for sc in sidecars]
    missing_no = [d for d, n in numbered if not n]
    if missing_no:
        warnings.append(f"editions without issue_number: {', '.join(missing_no)}")
    nums = [n for _, n in numbered if n]
    if len(set(nums)) != len(nums):
        errors.append("duplicate issue_number values across editions")
    if nums and nums != sorted(nums):
        errors.append("issue_number values are not chronological")

    # Index and archive must link every edition
    for page in ("index.html", "archive.html"):
        page_path = pw_dir / page
        if not page_path.is_file():
            errors.append(f"the-pla-watch/{page} is missing")
            continue
        text = page_path.read_text(encoding="utf-8")
        # index.html shows the latest edition card + previous list; both pages
        # should reference every post URL.
        for sc in sidecars:
            if f"posts/{sc.get('date', '')}.html" not in text:
                errors.append(f"the-pla-watch/{page}: no link to edition {sc.get('date')}")

    # Atom feed: well-formed XML with one entry per edition
    feed_path = pw_dir / "feed.xml"
    if not feed_path.is_file():
        errors.append("the-pla-watch/feed.xml is missing")
    else:
        import xml.etree.ElementTree as ET
        try:
            feed_root = ET.fromstring(feed_path.read_text(encoding="utf-8"))
            ns = "{http://www.w3.org/2005/Atom}"
            entries = feed_root.findall(f"{ns}entry")
            if len(entries) != len(sidecars):
                errors.append(
                    f"the-pla-watch/feed.xml: {len(entries)} entries "
                    f"but {len(sidecars)} editions")
            feed_ids = {e.findtext(f"{ns}id") or "" for e in entries}
            for sc in sidecars:
                url = (f"{SITE_ORIGIN}/the-pla-watch/posts/"
                       f"{sc.get('date', '')}.html")
                if url not in feed_ids:
                    errors.append(
                        f"the-pla-watch/feed.xml: no entry for edition "
                        f"{sc.get('date')}")
        except ET.ParseError as exc:
            errors.append(f"the-pla-watch/feed.xml does not parse: {exc}")

    # Terms page: must exist and link every edition that published a term
    terms_path = pw_dir / "terms.html"
    if not terms_path.is_file():
        errors.append("the-pla-watch/terms.html is missing")
    else:
        terms_text = terms_path.read_text(encoding="utf-8")
        for sc in sidecars:
            has_term = bool(
                (sc.get("term_to_know_term") or "").strip()
                or (isinstance(sc.get("term_to_know"), dict)
                    and (sc["term_to_know"].get("term") or "").strip()))
            if has_term and f"posts/{sc.get('date', '')}.html" not in terms_text:
                errors.append(
                    f"the-pla-watch/terms.html: no entry for edition "
                    f"{sc.get('date')}")

    # LinkedIn companion files (repo-side, non-fatal: historical gaps exist)
    linkedin_dir = output_dir.parent / "the-pla-watch" / "linkedin"
    if linkedin_dir.is_dir():
        for sc in sidecars:
            d = sc.get("date", "")
            if d and not (linkedin_dir / f"{d}.txt").is_file():
                warnings.append(f"LinkedIn file missing for edition {d}")

    # Cadence: weekly editions should be 7 days apart (report, don't block)
    dates = sorted(d for d, _ in numbered if d)
    for prev, cur in zip(dates, dates[1:]):
        try:
            gap = (date.fromisoformat(cur) - date.fromisoformat(prev)).days
        except ValueError:
            continue
        if gap != 7:
            warnings.append(f"cadence gap: {prev} → {cur} is {gap} days (expected 7)")


def _is_real_date(s: str) -> bool:
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def main() -> int:
    output_dir = _resolve_output_dir(sys.argv)
    errors, warnings = validate(output_dir)

    for w in warnings:
        print(f"WARN:  {w}")
    for e in errors:
        print(f"ERROR: {e}")

    if errors:
        print(f"\nValidation FAILED — {len(errors)} error(s). Deploy blocked.")
        return 1
    print(f"Validation passed ({len(warnings)} warning(s)). Output OK: {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
