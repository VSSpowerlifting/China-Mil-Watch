"""Fail-closed, three-path public Desks Source Atlas release guard.

Phase 4B is separate from the already-published Phase 4A map. Public
publication requires an explicitly approved new main SHA and independent
owner visual sign-off; neither is inferred from green CI.
"""
from __future__ import annotations

import re
from pathlib import Path

from core.frontend_budget import measure_page
from scripts.guard_country_research_output_scope import classify_output_changes

REVIEWED_PATHS = frozenset({
    "output/desks.html",
    "output/desk-atlas.css",
    "output/assets/glyphs/sources.svg",
})

APPROVED_US_LIMIT = (
    "U.S. institutional statements are evaluated under the same "
    "source-verification and editorial standards as every other desk; "
    "they are not treated as independent confirmation of their own claims."
)

# Only the Desks hub receives the owner's 300,000-byte HTML + linked CSS
# exception. All other routes keep their existing delivery contracts.
DESKS_HUB_CAP = 300_000
DESKS_JS_CAP = 10_000


def check(root: Path, *, require_changes: bool = True) -> tuple[set[str], set[str]]:
    changed, unexpected = classify_output_changes(Path(root), REVIEWED_PATHS)
    if unexpected:
        raise RuntimeError("Unreviewed output changes: " + ", ".join(sorted(unexpected)))
    if require_changes and not changed:
        raise RuntimeError("No reviewed Source Atlas files changed")
    return changed, unexpected


def validate_staged(root: Path) -> None:
    root = Path(root)
    out = root / "output"
    page = out / "desks.html"
    if not page.is_file():
        raise RuntimeError("Desks HTML is missing")
    html = page.read_text(encoding="utf-8")
    if not (root / "site/preview/desk-atlas.css").is_file():
        raise RuntimeError("Atlas stylesheet source missing")
    css = out / "desk-atlas.css"
    glyph = out / "assets/glyphs/sources.svg"
    if not css.is_file() or css.read_bytes() != (
            root / "site/preview/desk-atlas.css").read_bytes():
        raise RuntimeError("Rendered Atlas stylesheet mismatch")
    if not glyph.is_file() or glyph.read_bytes() != (
            root / "site/assets/glyphs/sources.svg").read_bytes():
        raise RuntimeError("IPR source-family glyph missing or mismatched")

    budget = measure_page(page, out)
    if (page.stat().st_size > DESKS_HUB_CAP or
            budget["html_css_bytes"] > DESKS_HUB_CAP or
            budget["js_bytes"] > DESKS_JS_CAP):
        raise RuntimeError("Desks-only 300 KB hub / 10 KB JS limit exceeded")
    for marker in ('href="desk-atlas.css"', "desk-map.css",
                   "assets/glyphs/sources.svg", 'id="atlas-china"',
                   'id="atlas-singapore"', 'id="atlas-japan"',
                   'id="atlas-korea"', 'id="atlas-vietnam"',
                   'id="atlas-philippines"', 'id="atlas-indonesia"',
                   'id="atlas-us-indopacific"', "Not admitted",
                   "Shadow evaluation", APPROVED_US_LIMIT):
        if marker not in html:
            raise RuntimeError("Required owner-approved Source Atlas content missing: " + marker)

    panels = re.findall(r'<article class="sa-panel [^"]*" id="atlas-([^"]+)"', html)
    if len(panels) != 8 or len(set(panels)) != 8:
        raise RuntimeError("Atlas must show eight distinct public desks")
    if 'class="dm-country' not in html or 'class="desk desk--' not in html:
        raise RuntimeError("Phase 4A Desks map disappeared")
    for slug in ("korea", "japan", "vietnam", "indonesia", "philippines"):
        body = html.split(f'id="atlas-{slug}"', 1)
        if len(body) != 2:
            raise RuntimeError("Missing desk panel: " + slug)
        section = body[1].split("</article>", 1)[0]
        if re.search(r"Browse its \d[\d,]* records", section):
            raise RuntimeError("A nonproduction desk claims a public corpus: " + slug)
    for forbidden in ("state/shadow.db", "shadow_originals", "private_originals",
                      "body_original", "text_original", "us_dvids_indopacom",
                      "shadow/jp_mod/manifest.json", "manifest-only fixture"):
        if forbidden in html:
            raise RuntimeError("Private/source-only diagnostics leaked into site: " + forbidden)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-unchanged", action="store_true")
    args = parser.parse_args()
    try:
        changed, _ = check(Path.cwd(), require_changes=not args.allow_unchanged)
        validate_staged(Path.cwd())
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        print("BLOCKED:", exc)
        return 1
    print("Phase 4B permitted output routes:", len(REVIEWED_PATHS),
          "; changed:", len(changed))
    for path in sorted(changed):
        print("REVIEWED:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
