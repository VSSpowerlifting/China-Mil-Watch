"""
Deterministic editorial-image derivatives for the Source-Derived Signal
Graphics system (production).

Reads the manifest (scripts/pw_env.py::load_editorial_manifest) and, for
each entry, computes the set of derivative files its routes + treatment
require (see docs §0 naming contract), writing any that are missing or
stale (source mtime newer than the derivative) into
site/assets/editorial/derivatives/. Never modifies a source image.

Recipe reused from tmp/visual-concepts-2026-07-12/make_derivatives.py
(duotone + Floyd-Steinberg dither parts only — edges/warm variants are not
part of the production system).

Usage:
    python scripts/generate_editorial_derivatives.py            # write
    python scripts/generate_editorial_derivatives.py --check    # verify only
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageEnhance, ImageOps

from scripts.pw_env import (
    EDITORIAL_DERIV_DIR,
    EDITORIAL_DIR,
    derivative_name,
    editorial_visual_fields,
    load_editorial_manifest,
)

# Fixed palette (see docs/DESIGN_SYSTEM.md tokens: --ink, --paper, --color-bg).
PAPER = (246, 243, 236)   # --paper / #F6F3EC
INK = (28, 43, 58)        # --ink / #1C2B3A
NAVY = (14, 21, 32)       # --color-bg / #0E1520
NAVY_HI = (168, 162, 154)  # muted warm gray highlight / #A8A29A
NAVY_MID = (52, 66, 84)

DUOTONE_MAX_WIDTH = 1600
DITHER_WIDTH = 1400


def _required_kinds(entry: dict) -> set:
    """Which derivative kinds this entry's routes + treatment require."""
    match = entry.get("match") or {}
    routes = match.get("routes") or []
    treatment = editorial_visual_fields(entry)["treatment"]
    kinds = set()
    if ("home" in routes or "article" in routes):
        if treatment == "dither":
            kinds.add("dither-ink")
        else:  # default / "veil"
            kinds.add("duo-paper")
    if "pw-post" in routes:
        kinds.add("duo-navy")
    return kinds


def _load_gray(src_path: Path) -> Image.Image:
    img = Image.open(src_path).convert("L")
    return ImageOps.autocontrast(img, cutoff=1)


def _write_duotone(gray: Image.Image, black, white, mid, out_path: Path) -> None:
    duo = ImageOps.colorize(gray, black=black, white=white, mid=mid) if mid else \
        ImageOps.colorize(gray, black=black, white=white)
    if duo.width > DUOTONE_MAX_WIDTH:
        new_h = round(duo.height * DUOTONE_MAX_WIDTH / duo.width)
        duo = duo.resize((DUOTONE_MAX_WIDTH, new_h), Image.LANCZOS)
    duo.save(out_path, "JPEG", quality=86, optimize=True)


def _write_dither(gray: Image.Image, out_path: Path) -> None:
    d = gray.resize(
        (DITHER_WIDTH, round(gray.height * DITHER_WIDTH / gray.width)),
        Image.LANCZOS,
    )
    d = ImageEnhance.Contrast(d).enhance(1.25)
    bit = d.convert("1")  # Floyd-Steinberg dither (PIL default)
    rgba = Image.new("RGBA", bit.size, (0, 0, 0, 0))
    px_src, px_dst = bit.load(), rgba.load()
    for y in range(bit.height):
        for x in range(bit.width):
            if px_src[x, y] == 0:  # dark pixel -> ink dot
                px_dst[x, y] = (*INK, 255)
    rgba.save(out_path, "PNG")


def _missing_or_stale(entry: dict) -> list:
    """[(kind, out_path), ...] this entry needs written right now."""
    fname = entry.get("file")
    eid = entry.get("id")
    if not fname or not eid:
        return []
    src_path = EDITORIAL_DIR / fname
    if not src_path.exists():
        return []
    src_mtime = src_path.stat().st_mtime
    todo = []
    for kind in sorted(_required_kinds(entry)):
        out_path = EDITORIAL_DERIV_DIR / derivative_name(entry, kind)
        if not out_path.exists() or out_path.stat().st_mtime < src_mtime:
            todo.append((kind, out_path))
    return todo


def ensure_derivatives(verbose: bool = True) -> list:
    """Write every missing/stale required derivative. Returns the list of
    relative paths written (empty list = everything already current)."""
    written = []
    EDITORIAL_DERIV_DIR.mkdir(parents=True, exist_ok=True)
    for entry in load_editorial_manifest():
        todo = _missing_or_stale(entry)
        if not todo:
            continue
        src_path = EDITORIAL_DIR / entry["file"]
        gray = _load_gray(src_path)
        for kind, out_path in todo:
            if kind == "duo-paper":
                _write_duotone(gray, INK, PAPER, None, out_path)
            elif kind == "duo-navy":
                _write_duotone(gray, NAVY, NAVY_HI, NAVY_MID, out_path)
            elif kind == "dither-ink":
                _write_dither(gray, out_path)
            rel = str(out_path.relative_to(ROOT))
            written.append(rel)
            if verbose:
                print(f"Wrote {rel}")
    return written


def _check() -> int:
    """--check mode: list missing derivatives, write nothing, exit 1 if any."""
    missing = []
    for entry in load_editorial_manifest():
        for kind, out_path in _missing_or_stale(entry):
            missing.append(str(out_path.relative_to(ROOT)))
    if missing:
        print("Missing/stale derivatives:")
        for m in missing:
            print(f"  {m}")
        return 1
    print("All required derivatives present and current.")
    return 0


def main() -> int:
    if "--check" in sys.argv[1:]:
        return _check()
    written = ensure_derivatives(verbose=True)
    if not written:
        print("All derivatives already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
