"""Convert selected Phase 0 study shots to JPG for repo evidence.
Excludes every capture that contains PLA Daily / 81.cn imagery (B2)."""
import sys
from pathlib import Path
from PIL import Image
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
SEL = {
 "home": ["home-%s-%s-%s" % (s, k, w) for s in ("before", "after")
          for k in ("finder", "register", "selected", "band", "desks") for w in ("1280", "375")]
         + ["home-stack-finder-1280", "home-stack-register-1280", "home-forced-finder-1280", "home-forced-register-1280"],
 "briefs": ["base-hero-1280", "base-hero-375", "base-list-1280", "study-hero-1280", "study-hero-375",
            "no81-list-1280", "no81-list-mid-1280"],
 "desks": ["base-map-1280", "base-reads-1280", "study-map-1280", "study-map-900", "study-map-375",
           "study-reads-1280", "study-reads-375", "study-focus-sg-1280"],
 "archive": ["base-top-1280", "base-rows-1280", "study-top-1280", "study-top-375", "study-rows-1280", "study-rows-375"],
}
# The 375 px analysis-band captures end at the top edge of the home Brief
# photograph (PLA Daily); cut above it.
CUT = {"home-before-band-375": 1012, "home-after-band-375": 1575}
total = 0
for d, names in SEL.items():
    for n in names:
        im = Image.open(src / d / (n + ".png")).convert("RGB")
        if n in CUT:
            im = im.crop((0, 0, im.width, CUT[n]))
        out = dst / ("%s-%s.jpg" % (d, n) if d != "home" else n + ".jpg")
        im.save(out, quality=74, optimize=True, progressive=True)
        total += out.stat().st_size
print("files", sum(map(len, SEL.values())), "bytes", total)
