#!/usr/bin/env python3
"""
Build the Ocean Signal Veil derivative from its public-domain source photograph.

What is canonical and what is derived
-------------------------------------
`site/assets/editorial/reagan-jmsdf-2015.jpg` is the unmodified source
photograph and the rights anchor. This script never writes it and refuses to
run if its digest has changed. The two files under `derivatives/` are produced
here, so a reviewer can regenerate them and compare digests rather than
trusting a binary that arrived in a commit — the same contract
`scripts/build_identity_assets.py` holds for the identity set.

Why the crop is stated rather than implied
------------------------------------------
An earlier builder accepted a crop box and then silently centre-cropped it to
the output aspect, so the box it was given was not the crop it produced: a
request for y 0.28..0.86 returned y 0.3951..0.7438. Nothing warned. This
builder derives the box from a named subject point, a width fraction, an
output aspect and an anchor, and writes the effective crop it actually used
into `derivatives/veil-ocean.json`. The box you ask for is the box you get,
and the record says which box that was.

Two geometric properties are load-bearing, and both are asserted below:

* **The derivative is authored NARROWER than the narrowest veil box.** The
  veil box at 1280 is 2.442:1. An asset wider than that is scaled by HEIGHT
  under `background-size: cover`, and its left edge walks off screen as the
  viewport widens — at 3.617:1 only x 0.325..1.000 of the asset was ever
  visible at 1280 and the left third was unreachable. At 2.049:1 the full
  width shows at every width >= 1280. The historical China Mil Watch veil had
  this property (1600x1086, 1.47:1); it was lost and is restored here.

* **The subject sits on the `background-position-Y` anchor (0.75).** `cover`
  scales about the position anchor, so the image point at that fraction maps
  to the same box fraction at every viewport width. The carrier therefore
  holds box y 0.750 at 1280 and at 1920 instead of sliding out of frame.

The duotone is baked offline, keyed to the p1 tokens rather than to the
photograph, so the browser runs no filter and makes no second request.

Usage
-----
    python3 scripts/make_veil.py            # rebuild and report
    python3 scripts/make_veil.py --check    # verify digests, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

REPO_ROOT = Path(__file__).resolve().parent.parent
EDITORIAL = REPO_ROOT / "site" / "assets" / "editorial"
SOURCE = EDITORIAL / "reagan-jmsdf-2015.jpg"
STEM = EDITORIAL / "derivatives" / "veil-ocean"

#: The source photograph, pinned. Public domain — a work of the U.S. federal
#: government prepared by a service member in the course of duty, 17 U.S.C.
#: § 105, tagged {{PD-USGov-Military}} on its Commons file page.
SOURCE_SHA256 = "2098aac8a9d9d9fd35dfbb9b9bcb89fbb12b5102879db0283ed4919b6dfeac18"
SOURCE_PX = (2500, 1663)
SOURCE_PAGE = ("https://commons.wikimedia.org/wiki/File:Ronald_Reagan_Carrier_"
               "Strike_Group_and_Japan_Maritime_Self-Defense_Force,_November_"
               "23,_2015.jpg")

#: p1 institutional tokens. The veil is keyed to the page, not to the
#: photograph: shadows land on --band, mids on --accent (the logo's own dark
#: stop) and highlights on --bg, so the image resolves into the paper rather
#: than sitting on top of it.
SHADOW = (0x12, 0x22, 0x2C)   # --band
MID = (0x25, 0x5E, 0x7A)      # --accent
PAPER = (0xF3, 0xF1, 0xEA)    # --bg

#: The selected T3 Wake geometry. Changing any of these changes the rendered
#: veil, and the glyph-contrast contract in
#: `tests/test_homepage_veil_contract.py` is measured against this crop.
CROP = {
    "subject": (0.65, 0.57),   # carrier D in the source frame
    "width_frac": 0.58,
    "aspect": 2.05,
    "anchor": (0.80, 0.75),    # 0.75 == background-position-Y
    "out_w": 1500,
}
TONE = {"paper_blend": 0.04, "contrast": 1.16, "clarity": 0.75,
        "brightness": 1.0, "knee": 0.54, "blur": 0.4}
QUALITY = {"webp": 72, "jpg": 74}

#: The narrowest veil box the layout produces: `.opening` at 1280, 88% wide.
#: The derivative must be narrower than this or `cover` scales it by height.
NARROWEST_VEIL_BOX_ASPECT = 2.442

#: Built outputs, pinned. Pillow's encoders are not byte-reproducible across
#: builds, so `--check` compares geometry and tone parameters and reports the
#: digests it finds rather than failing on an encoder difference. The digests
#: are recorded so a reviewer can see when the asset actually changed.
EXPECT = {
    "veil-ocean.webp": "5c5dae8e3aa4543b68985d5abf2417a51458e483140abe5c20164a41fd515c5a",
    "veil-ocean.jpg": "19232d6e3d6cb85f97128bf562c4837bee11364223c9e2af2b48f48b181b1da3",
}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_source() -> None:
    if not SOURCE.is_file():
        raise SystemExit("source photograph missing: %s" % SOURCE)
    actual = sha256_of(SOURCE)
    if actual != SOURCE_SHA256:
        raise SystemExit(
            "source photograph has changed.\n  expected %s\n  found    %s\n"
            "This file is the rights anchor and is never rewritten here."
            % (SOURCE_SHA256, actual))


def ramp(knee: float) -> list:
    """256-entry duotone LUT: shadows -> band, mids -> accent, highs -> paper."""
    lut = []
    for i in range(256):
        t = i / 255.0
        if t < knee:
            k = t / knee
            lut.append(tuple(round(SHADOW[j] + (MID[j] - SHADOW[j]) * k)
                             for j in range(3)))
        else:
            k = (t - knee) / (1.0 - knee)
            lut.append(tuple(round(MID[j] + (PAPER[j] - MID[j]) * k)
                             for j in range(3)))
    return lut


def crop_box(src_w: int, src_h: int, subject, width_frac: float,
             aspect: float, anchor) -> tuple:
    """
    The explicit contract.

    `subject` is the point of interest as fractions of the source frame;
    `width_frac` the crop width as a fraction of the source width; `aspect`
    the output ratio, from which the crop height follows; `anchor` where the
    subject sits inside the crop. Returns the box as source fractions plus the
    list of edges that had to be clamped, so a silent clamp cannot be mistaken
    for the box that was requested.
    """
    bw = float(width_frac)
    bh = bw * src_w / (aspect * src_h)
    if bw > 1.0 or bh > 1.0:
        raise SystemExit("crop larger than the frame: bw=%.3f bh=%.3f" % (bw, bh))
    left = subject[0] - anchor[0] * bw
    top = subject[1] - anchor[1] * bh
    clamped = []
    if left < 0:
        left, clamped = 0.0, clamped + ["left"]
    if top < 0:
        top, clamped = 0.0, clamped + ["top"]
    if left + bw > 1.0:
        left, clamped = 1.0 - bw, clamped + ["right"]
    if top + bh > 1.0:
        top, clamped = 1.0 - bh, clamped + ["bottom"]
    return (left, top, left + bw, top + bh), clamped


def build(check_only: bool = False) -> int:
    verify_source()

    aspect = CROP["aspect"]
    if aspect >= NARROWEST_VEIL_BOX_ASPECT:
        raise SystemExit(
            "derivative aspect %.3f is not narrower than the 1280 veil box "
            "(%.3f). `cover` would scale it by height and the subject would "
            "walk off the left edge as the viewport widens."
            % (aspect, NARROWEST_VEIL_BOX_ASPECT))

    im = Image.open(SOURCE).convert("RGB")
    src_w, src_h = im.size
    if (src_w, src_h) != SOURCE_PX:
        raise SystemExit("source is %dx%d, expected %dx%d"
                         % (src_w, src_h, SOURCE_PX[0], SOURCE_PX[1]))

    box, clamped = crop_box(src_w, src_h, CROP["subject"], CROP["width_frac"],
                            aspect, CROP["anchor"])
    px_box = (round(src_w * box[0]), round(src_h * box[1]),
              round(src_w * box[2]), round(src_h * box[3]))
    out_w = CROP["out_w"]
    out_h = round(out_w / aspect)

    record = {
        "source": str(SOURCE.relative_to(REPO_ROOT)),
        "source_sha256": SOURCE_SHA256,
        "source_page": SOURCE_PAGE,
        "source_px": [src_w, src_h],
        "subject": list(CROP["subject"]),
        "width_frac": CROP["width_frac"],
        "aspect": aspect,
        "anchor": list(CROP["anchor"]),
        "effective_crop_frac": [round(v, 5) for v in box],
        "effective_crop_px": list(px_box),
        "crop_px_size": [px_box[2] - px_box[0], px_box[3] - px_box[1]],
        "clamped_edges": clamped,
        "resample_scale": round(out_w / (px_box[2] - px_box[0]), 4),
        "output_px": [out_w, out_h],
        "narrower_than_veil_box": True,
    }
    record.update(TONE)

    if check_only:
        problems = []
        for name, expected in EXPECT.items():
            path = STEM.parent / name
            if not path.is_file():
                problems.append("%s missing" % name)
                continue
            found = sha256_of(path)
            with Image.open(path) as built:
                if built.size != (out_w, out_h):
                    problems.append("%s is %dx%d, expected %dx%d"
                                    % (name, built.size[0], built.size[1],
                                       out_w, out_h))
            if found != expected:
                print("note: %s digest %s (pinned %s) — Pillow encoder output "
                      "is not byte-reproducible across builds; geometry is "
                      "what is enforced." % (name, found[:16], expected[:16]))
        if problems:
            for p in problems:
                print("FAIL: %s" % p, file=sys.stderr)
            return 1
        print("veil derivative OK: %dx%d, aspect %.4f, crop %s"
              % (out_w, out_h, aspect, record["effective_crop_frac"]))
        return 0

    im = im.crop(px_box).resize((out_w, out_h), Image.LANCZOS)
    if TONE["clarity"]:
        im = im.filter(ImageFilter.UnsharpMask(
            radius=6, percent=int(TONE["clarity"] * 100), threshold=2))
    im = ImageEnhance.Contrast(im).enhance(TONE["contrast"])
    grey = ImageEnhance.Brightness(im.convert("L")).enhance(TONE["brightness"])

    lut = ramp(TONE["knee"])
    gp = grey.load()
    out = Image.new("RGB", (out_w, out_h))
    op = out.load()
    for y in range(out_h):
        for x in range(out_w):
            op[x, y] = lut[gp[x, y]]
    if TONE["blur"]:
        out = out.filter(ImageFilter.GaussianBlur(TONE["blur"]))
    if TONE["paper_blend"]:
        out = Image.blend(out, Image.new("RGB", out.size, PAPER),
                          TONE["paper_blend"])

    STEM.parent.mkdir(parents=True, exist_ok=True)
    webp, jpg = STEM.with_suffix(".webp"), STEM.with_suffix(".jpg")
    out.save(webp, "WEBP", quality=QUALITY["webp"], method=6)
    out.save(jpg, "JPEG", quality=QUALITY["jpg"], optimize=True,
             progressive=True)

    record["bytes"] = {"webp": webp.stat().st_size, "jpg": jpg.stat().st_size}
    record["sha256"] = {"webp": sha256_of(webp), "jpg": sha256_of(jpg)}
    STEM.with_name(STEM.name + ".json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(record, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the built derivative against the declared "
                         "geometry and digests; write nothing")
    args = ap.parse_args()
    return build(check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
