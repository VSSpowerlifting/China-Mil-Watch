"""
Stage the synthetic brief fixtures into a scratch directory.

`tests/fixtures/briefs/` holds the sidecar and its image metadata. The veil
derivative is drawn here, at staging time, rather than committed: it is a
generated abstract pattern, not a photograph, and nothing about it should look
like a publisher's image. The pattern is deterministic, so two stagings are
byte-identical.
"""

from __future__ import annotations

import shutil
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "briefs"
FIXTURE_SLUG = "synthetic-fixture-cross-desk"

#: The band and its focus tint (site/preview/styles.css), the duotone ends.
_DARK = (0x12, 0x22, 0x2C)
_LIGHT = (0x8F, 0xC9, 0xDE)


def write_synthetic_veil(path: Path, size=(1200, 630)) -> Path:
    """A deterministic duotone test pattern at `path`."""
    from PIL import Image, ImageDraw

    width, height = size
    gray = Image.new("L", size, 40)
    draw = ImageDraw.Draw(gray)
    for i in range(-height, width, 36):
        draw.line([(i, height), (i + height, 0)], fill=110, width=10)
    for r, shade in ((260, 150), (170, 190), (90, 230)):
        cx, cy = int(width * .72), int(height * .38)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=shade, width=14)
    lut = []
    for channel in range(3):
        lo, hi = _DARK[channel], _LIGHT[channel]
        lut += [round(lo + (hi - lo) * v / 255) for v in range(256)]
    duo = Image.merge("RGB", (gray, gray, gray)).point(lut)
    path.parent.mkdir(parents=True, exist_ok=True)
    duo.save(path, "JPEG", quality=80, optimize=True)
    return path


def stage(dest: Path, *, veil: bool = True) -> Path:
    """Copy the fixtures to `dest/briefs` and return that directory."""
    from core.brief_collection import MEDIA_DIRNAME, veil_name

    briefs = Path(dest) / "briefs"
    shutil.copytree(FIXTURE_DIR, briefs)
    if veil:
        write_synthetic_veil(briefs / MEDIA_DIRNAME / veil_name(FIXTURE_SLUG))
    else:
        shutil.rmtree(briefs / MEDIA_DIRNAME, ignore_errors=True)
    return briefs
