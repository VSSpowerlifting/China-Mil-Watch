"""
The Archive's desk markers: one tight silhouette file per country desk.

`python scripts/build_desk_marks.py` copies each country desk's outline out of
the committed `site/assets/geo/emblems.svg` (the `d-<slug>` paths, already
generalized Natural Earth geometry; see `scripts/build_geo_assets.py`) into its
own small SVG under `site/assets/desk-marks/`, with a viewBox cropped to the
outline, and writes a receipt of input and output hashes.

Why separate files: `archive.css` draws the marker as a CSS mask, and a mask
needs a standalone image. A `<symbol>` in a sprite is not one (Chromium draws
nothing for `mask-image: url(sprite.svg#id)`; the probe is kept in
docs/evidence/archive-refinement-2b-2026-10-11/). Nothing new is projected or
simplified here, so the marker is the same coastline the homepage emblem draws.

Eligible desks are exactly `build_geo_assets.DESKS`: the desks drawn as a
country outline. The US Indo-Pacific desk is drawn as Hawaii (its command's
seat, not a country) and the Philippines desk has no geometry; both get no
marker rather than an invented one. The output is deterministic and carries no
time.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_geo_assets as geo  # noqa: E402

REPO_ROOT = geo.REPO_ROOT
SOURCE = REPO_ROOT / "site" / "assets" / "geo" / "emblems.svg"
OUT_DIR = REPO_ROOT / "site" / "assets" / "desk-marks"
RECEIPT = "desk-marks.receipt.json"
SLUGS = tuple(sorted(geo.DESKS))


def outline(emblems: str, slug: str) -> str:
    m = re.search(r'<path id="d-%s"[^>]*? d="([^"]+)"' % re.escape(slug), emblems)
    if not m:
        raise SystemExit("no d-%s outline in emblems.svg" % slug)
    return m.group(1)


def mark(slug: str, d: str) -> str:
    pairs = [(float(x), float(y))
             for x, y in re.findall(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)", d)]
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    x0, y0 = min(xs), min(ys)
    w, h = max(xs) - x0, max(ys) - y0
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%.1f %.1f %.1f %.1f">'
        '<!-- %s desk mark: outline copied from assets/geo/emblems.svg (#d-%s), '
        'built by scripts/build_desk_marks.py. Natural Earth public domain via '
        'world-atlas 2.0.2 (ISC). Generalized; not a boundary claim. '
        'Decorative. -->'
        '<path d="%s"/></svg>\n' % (x0, y0, w, h, slug, slug, d))


def build(out_dir: Path = OUT_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    emblems = SOURCE.read_text(encoding="utf-8")
    outputs = {}
    for slug in SLUGS:
        data = mark(slug, outline(emblems, slug)).encode("utf-8")
        (out_dir / (slug + ".svg")).write_bytes(data)
        outputs[slug + ".svg"] = {"bytes": len(data),
                                  "sha256": hashlib.sha256(data).hexdigest()}
    receipt = {
        "generator": "scripts/build_desk_marks.py",
        "input": {"file": "site/assets/geo/emblems.svg",
                  "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest()},
        "outputs": outputs,
        "licence": geo.SOURCE,
    }
    (out_dir / RECEIPT).write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n",
                                   encoding="utf-8")
    return receipt


if __name__ == "__main__":
    r = build()
    print(", ".join("%s %d B" % (k, v["bytes"]) for k, v in sorted(r["outputs"].items())))
