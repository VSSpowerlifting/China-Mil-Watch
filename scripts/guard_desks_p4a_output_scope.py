"""Exact-path contract for the separately approved Phase 4A Desks release.

This guard runs against git's entire generated output delta, including ignored
and untracked paths: GitHub Pages publishes the full output tree, not merely
tracked paths. It does not modify or publish anything.
"""
from __future__ import annotations

from pathlib import Path

from scripts.guard_country_research_output_scope import classify_output_changes

REVIEWED_PATHS = frozenset({
    "output/desks.html",
    "output/desk-map.css",
    "output/assets/flags/LICENSE",
    *(f"output/assets/flags/{iso}.svg"
      for iso in ("cn", "id", "jp", "kr", "ph", "sg", "us", "vn")),
})


def check(root: Path, *, require_changes: bool = True) -> tuple[set[str], set[str]]:
    root = Path(root)
    changed, unexpected = classify_output_changes(root, REVIEWED_PATHS)
    if unexpected:
        raise RuntimeError("Unreviewed site output would be deployed: "
                           + ", ".join(sorted(unexpected)))
    if require_changes and not changed:
        raise RuntimeError("No Phase 4A output changed; no new release to commit")
    return changed, unexpected


def validate_staged(root: Path) -> None:
    root = Path(root)
    html_file = root / "output/desks.html"
    if not html_file.is_file() or html_file.stat().st_size > 120_000:
        raise RuntimeError("Missing or oversized Desks page")
    html = html_file.read_text(encoding="utf-8")
    required = ("8 declared", "2 collecting", "Shadow evaluation",
                "Not admitted", "desk-map.css", "relief.css",
                'href="china.html"', 'href="singapore.html"',
                'href="japan.html"', 'href="korea.html"',
                'href="vietnam.html"', 'href="philippines.html"',
                'href="indonesia.html"')
    for marker in required:
        if marker not in html:
            raise RuntimeError(f"Missing required Desks public contract: {marker}")
    if 'class="dm-country' not in html or 'dm-anchor' not in html:
        raise RuntimeError("Missing geographic map presentation")
    if 'class="dm-country' in html and 'data-desk="us-indopacific"><use' in html:
        raise RuntimeError("Refused a sovereign US Indo-Pacific country fill")
    for forbidden in ("state/shadow.db", "body_original", "text_original",
                      "shadow_originals", "private_originals"):
        if forbidden in html:
            raise RuntimeError("Private evidence leaked to Desks page: " + forbidden)
    css = root / "output/desk-map.css"
    source_css = root / "site/preview/desk-map.css"
    if css.read_bytes() != source_css.read_bytes():
        raise RuntimeError("Rendered Desks CSS differs from reviewed source")
    for iso in ("cn", "id", "jp", "kr", "ph", "sg", "us", "vn"):
        route = f"assets/flags/{iso}.svg"
        if f'src="{route}"' not in html:
            raise RuntimeError("Map flag reference missing: " + route)
        if (root / "output" / route).read_bytes() != (
                root / "site" / route).read_bytes():
            raise RuntimeError("Rendered flag differs from licensed original: " + route)
    licence = "assets/flags/LICENSE"
    if (root / "output" / licence).read_bytes() != (root / "site" / licence).read_bytes():
        raise RuntimeError("Public flag MIT notice missing or mismatched")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-unchanged", action="store_true",
        help="Allow an exact reviewed-output replay after a Pages-only failure",
    )
    args = parser.parse_args()
    try:
        paths, _ = check(Path.cwd(), require_changes=not args.allow_unchanged)
        validate_staged(Path.cwd())
    except (RuntimeError, FileNotFoundError, OSError) as exc:
        print("BLOCKED:", exc)
        return 1
    print("Phase 4A Desks release exact output paths:", len(paths))
    for path in sorted(paths):
        print("REVIEWED:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
