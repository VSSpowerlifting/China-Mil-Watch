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

Usage:
    python3 scripts/validate_output.py [output_dir]   # default: ../output
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

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

    return (errors, warnings)


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
                url = (f"https://chinamilwatch.org/the-pla-watch/posts/"
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
