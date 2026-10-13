#!/usr/bin/env python3
"""Build a native Brief cover photograph's derivatives, deterministically.

Reads the editorial manifest (`site/assets/editorial/manifest.json`). For each
entry built by this script (`derivative_builder`), it resizes the entry's
retained source file (`file`, whose `sha256` is the retrieved bytes) to the
widths in `WIDTHS` and writes, under `site/assets/editorial/derivatives/`:

* ``<id>-1600.jpg``: the hero's fallback image and the catalogue card's
  source (`core/catalogue_media.py` crops it again for the card);
* ``<id>-800.webp`` and ``<id>-1600.webp``: the hero's responsive sources.

Nothing is toned, relit, sharpened or retouched: these are resized copies of
the photograph as published. Any treatment (the IPR gradient) is CSS, so the
pixels stay the source's. With `--write` it writes the files and records
each one's width, height and digest in the entry's `derivatives` list, and the
Pillow version under `built_with`. Encoded bytes are reproducible only for the
same encoder, so the recorded digest (not a re-encode) is what the renderer
verifies. With `--check` it exits non-zero when a committed file differs from
its record. It never fetches and never edits `output/`.
"""
import argparse
import json
import sys
from io import BytesIO
from pathlib import Path

import PIL
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.brief_cover import BUILDER, MANIFEST_PATH, sha256_file  # noqa: E402

EDITORIAL = ROOT / "site/assets/editorial"
#: (width, format) pairs, in the order they are recorded.
WIDTHS = ((1600, "jpg"), (800, "webp"), (1600, "webp"))
JPEG_QUALITY, WEBP_QUALITY = 86, 80


def derive(source: Path, width: int, fmt: str) -> tuple:
    with Image.open(source) as im:
        im = im.convert("RGB")
        sw, sh = im.size
        if sw > width:
            im = im.resize((width, round(sh * width / sw)), Image.LANCZOS)
        buf = BytesIO()
        if fmt == "jpg":
            im.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True,
                    progressive=True, subsampling="4:2:0")
        else:
            im.save(buf, "WEBP", quality=WEBP_QUALITY, method=6)
        return buf.getvalue(), im.size


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write files and record digests")
    ap.add_argument("--check", action="store_true", help="verify committed files against the record")
    a = ap.parse_args()
    path = ROOT / MANIFEST_PATH
    manifest = json.loads(path.read_text(encoding="utf-8"))
    bad = 0
    for entry in manifest:
        if entry.get("derivative_builder") != BUILDER:
            continue
        source = EDITORIAL / entry["file"]
        if sha256_file(source) != entry.get("sha256"):
            print("FAIL source digest %s" % entry["file"])
            bad += 1
            continue
        if a.write:
            records = []
            for width, fmt in WIDTHS:
                blob, (w, h) = derive(source, width, fmt)
                rel = "derivatives/%s-%d.%s" % (entry["id"], width, fmt)
                (EDITORIAL / rel).write_bytes(blob)
                records.append({"file": rel, "width": w, "height": h,
                                "sha256": sha256_file(EDITORIAL / rel)})
                print("wrote %s %d B" % (rel, len(blob)))
            entry["derivatives"] = records
            entry["built_with"] = {"pillow": PIL.__version__}
        elif a.check:
            for rec in entry.get("derivatives") or ():
                target = EDITORIAL / rec["file"]
                ok = target.is_file() and sha256_file(target) == rec.get("sha256")
                print("%s %s" % ("ok  " if ok else "FAIL", rec["file"]))
                bad += not ok
    if a.write:
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
