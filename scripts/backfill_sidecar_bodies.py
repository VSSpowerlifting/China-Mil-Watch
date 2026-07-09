"""
One-time backfill: recover post body text from published HTML into the JSON
sidecars in output/the-pla-watch/posts/.

Sidecars written before body-field storage carry only metadata and the source
trail, so scripts/rerender_pla_watch.py could not reproduce the published
prose. This script extracts the already-published section text from each
post's HTML (no new text is ever written — extraction only) and stores it in
the sidecar. It also:

  - assigns a stable chronological issue_number to every sidecar;
  - fills a missing "signal" from the published signal card;
  - normalises author fields to the current public identity
    ("Principal Analyst, China Mil Watch").

Existing non-empty body fields are never overwritten.

Usage:
    python3 scripts/backfill_sidecar_bodies.py [--dry-run]
"""

import argparse
import html as html_mod
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

POSTS_DIR = ROOT / "output" / "the-pla-watch" / "posts"

AUTHOR_TITLE = "Principal Analyst, China Mil Watch"
OLD_TITLE = "Founder & Principal Analyst, China Mil Watch"
OLD_BIO_FRAGMENT = "is the founder of China Mil Watch"
NEW_BIO_FRAGMENT = "is the principal analyst at China Mil Watch"

# Published mod-heading text → sidecar field. Includes historical variants.
HEADING_FIELDS = {
    "opening note":            "opening_note",
    "what stood out":          "what_stood_out",
    "why it matters":          "why_it_matters",
    "routine baseline":        "what_was_routine",
    "what was routine":        "what_was_routine",
    "what i'm watching next":  "what_im_watching_next",
    "what i’m watching next":  "what_im_watching_next",
}

SECTION_RE = re.compile(
    r'<div class="mod-heading brand">([^<]+)</div>\s*'
    r'<div class="section-text">(.*?)</div>\s*</div>',
    re.DOTALL,
)
PARA_RE = re.compile(r"<p>(.*?)</p>", re.DOTALL)
TERM_RE = re.compile(
    r'<div class="term-word">(.*?)</div>\s*'
    r'<div class="term-explanation">(.*?)</div>',
    re.DOTALL,
)
SIGNAL_RE = re.compile(r'<div class="signal-text">(.*?)</div>', re.DOTALL)


def _clean(fragment: str) -> str:
    """HTML paragraph fragment → plain text (published HTML was unescaped)."""
    text = re.sub(r"<[^>]+>", "", fragment)
    return html_mod.unescape(text).strip()


def _paragraphs(section_html: str) -> str:
    paras = [_clean(m) for m in PARA_RE.findall(section_html)]
    return "\n\n".join(p for p in paras if p)


def extract_body(html_text: str) -> dict:
    out: dict = {}
    for heading, section_html in SECTION_RE.findall(html_text):
        field = HEADING_FIELDS.get(heading.strip().lower())
        if field:
            text = _paragraphs(section_html)
            if text:
                out[field] = text
    m = TERM_RE.search(html_text)
    if m:
        term = _clean(m.group(1))
        explanation = _paragraphs(m.group(2)) or _clean(m.group(2))
        if term:
            out["term_to_know_term"] = term
        if explanation:
            out["term_to_know_explanation"] = explanation
    m = SIGNAL_RE.search(html_text)
    if m:
        signal = _clean(m.group(1))
        if signal:
            out["signal"] = signal
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change; write nothing.")
    args = parser.parse_args()

    json_paths = sorted(POSTS_DIR.glob("*.json"))
    if not json_paths:
        print(f"No sidecars found in {POSTS_DIR}")
        return 1

    changed = 0
    for issue_number, json_path in enumerate(json_paths, start=1):
        sidecar = json.loads(json_path.read_text(encoding="utf-8"))
        updates: dict = {}

        # Chronological issue number (sidecars sort by date-named filename).
        if sidecar.get("issue_number") != issue_number:
            updates["issue_number"] = issue_number

        # Body text from published HTML — only fields that are missing/empty.
        html_path = json_path.with_suffix(".html")
        if html_path.exists():
            extracted = extract_body(html_path.read_text(encoding="utf-8"))
            for field, text in extracted.items():
                if not (sidecar.get(field) or "").strip():
                    updates[field] = text
        else:
            print(f"WARN: {html_path.name} missing — cannot backfill body")

        # Source-trail schema normalisation (early sidecars used label/url):
        #  - label → title: same string, renamed key.
        #  - missing source → sources_seen[0], only when exactly one source
        #    was seen (this is what the published page already displays).
        # Missing dates are left missing — never invented.
        trail = sidecar.get("source_trail") or []
        sources_seen = sidecar.get("sources_seen") or []
        new_trail = []
        trail_changed = False
        for entry in trail:
            e = dict(entry)
            if not e.get("title") and e.get("label"):
                e["title"] = e.pop("label")
                trail_changed = True
            if not e.get("source") and len(sources_seen) == 1:
                e["source"] = sources_seen[0]
                trail_changed = True
            new_trail.append(e)
        if trail_changed:
            updates["source_trail"] = new_trail

        # Public identity normalisation.
        if sidecar.get("author_title") == OLD_TITLE:
            updates["author_title"] = AUTHOR_TITLE
        bio = sidecar.get("author_bio") or ""
        if OLD_BIO_FRAGMENT in bio:
            updates["author_bio"] = bio.replace(OLD_BIO_FRAGMENT, NEW_BIO_FRAGMENT)

        if not updates:
            print(f"{json_path.name}: no changes needed")
            continue

        changed += 1
        print(f"{json_path.name}: {', '.join(sorted(updates))}")
        if not args.dry_run:
            sidecar.update(updates)
            json_path.write_text(
                json.dumps(sidecar, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    print(f"\n{'Would update' if args.dry_run else 'Updated'} "
          f"{changed} of {len(json_paths)} sidecar(s).")
    return 0


if __name__ == "__main__":
    main()
