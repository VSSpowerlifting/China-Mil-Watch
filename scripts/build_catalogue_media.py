#!/usr/bin/env python3
"""Build the Briefs catalogue's admitted photograph derivatives, deterministically.

Reads `site/assets/catalogue/admissions.json`. For each entry with status
"admitted" it crops the entry's `source_file` (an existing curated, toned
derivative) to 3:2 around `focal`, resizes to 720x480 and writes a
progressive JPEG with no metadata to `site/<served>`. With `--write` it also
records `source_sha256`, `served_sha256`, `width` and `height` in the entry,
and the Pillow version that encoded them under `built_with`. JPEG bytes are
only reproducible for the same encoder, so the committed hash (not a re-encode)
is what production verifies.
With `--check` it exits non-zero if a committed file's hash differs from the
record. It never fetches, never edits `output/`, and never tones an image:
the toning is the existing derivative's.
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
from core.catalogue_media import ADMISSIONS_PATH, sha256_file  # noqa: E402

W, H, QUALITY = 720, 480, 74
PILLOW_VERSION = PIL.__version__


def derive(source: Path, focal: str) -> bytes:
    fx, fy = [float(p.strip().rstrip("%")) / 100 for p in focal.split()]
    with Image.open(source) as im:
        im = im.convert("RGB")
        sw, sh = im.size
        target = W / H
        if sw / sh > target:
            cw, ch = round(sh * target), sh
        else:
            cw, ch = sw, round(sw / target)
        left = min(max(round((sw - cw) * fx), 0), sw - cw)
        top = min(max(round((sh - ch) * fy), 0), sh - ch)
        im = im.crop((left, top, left + cw, top + ch)).resize((W, H), Image.LANCZOS)
        buf = BytesIO()
        im.save(buf, "JPEG", quality=QUALITY, optimize=True, progressive=True,
                subsampling="4:2:0")
        return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write files and record hashes")
    ap.add_argument("--check", action="store_true", help="verify committed files against the record")
    a = ap.parse_args()
    path = ROOT / ADMISSIONS_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    bad = 0
    for e in data["entries"]:
        if e.get("status") != "admitted":
            continue
        source = ROOT / e["source_file"]
        served = ROOT / "site" / e["served"]
        blob = derive(source, e["focal"])
        if a.write:
            served.parent.mkdir(parents=True, exist_ok=True)
            served.write_bytes(blob)
            e.update(source_sha256=sha256_file(source), served_sha256=sha256_file(served),
                     width=W, height=H)
            data["built_with"] = {"pillow": PILLOW_VERSION}
            print("wrote %s %d B" % (e["served"], len(blob)))
        elif a.check:
            ok = served.is_file() and sha256_file(served) == e.get("served_sha256")
            print("%s %s" % ("ok  " if ok else "FAIL", e["served"]))
            bad += not ok
    if a.write:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
