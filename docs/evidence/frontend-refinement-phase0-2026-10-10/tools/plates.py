"""Phase 0 study helper (disposable). Regional fragment for the labelled
editorial plate (the fallback when a Brief has no eligible photograph).
Every land ring inside a lon/lat box from the desk map's Natural Earth 1:50m
file, desk map decoder and Miller projection; desk countries are kept as
separate paths so the plate can tone them. Writes JSON into the scratchpad.

usage: python -I plates.py <repo> <countries-50m.json> <out.json>
"""
import json
import sys
from pathlib import Path

repo, f50, out = (Path(a) for a in sys.argv[1:4])
sys.path.insert(0, str(repo / "scripts"))
import desk_map as dm  # noqa: E402  (read-only reuse)

topo = json.loads(f50.read_text(encoding="utf-8"))
arcs = [dm._simplify(a, 0.09) for a in dm._decode_arcs(topo)]
geo = json.loads((repo / "desks" / "geography.json").read_text(encoding="utf-8"))["desks"]

DESK_IDS = {"china": {"156"}, "singapore": {"702"}}
LON0, LAT0, LON1, LAT1 = 70.0, -4.0, 150.0, 45.0
x0, y1 = dm.project(LON0, LAT0)
x1, y0 = dm.project(LON1, LAT1)
W = 300.0
s = W / (x1 - x0)
H = (y1 - y0) * s
amin = (x1 - x0) * (y1 - y0) * 0.00002   # drops specks, incl. contested islets

paths = {"land": [], "china": [], "singapore": []}
for g in topo["objects"]["countries"]["geometries"]:
    gid = g.get("id")
    key = next((k for k, ids in DESK_IDS.items() if gid in ids), "land")
    for poly in dm._polygons(g):
        r = [dm.project(x, y) for x, y in dm._shift(dm._ring(poly[0], arcs))]
        xs = [p[0] for p in r]; ys = [p[1] for p in r]
        if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1:
            continue
        if key == "land" and dm._area(r) < amin:
            continue
        pts = ["%.1f %.1f" % ((x - x0) * s, (y - y0) * s) for x, y in r]
        dd = [p for i, p in enumerate(pts) if not i or p != pts[i - 1]]
        if len(dd) >= 3:
            paths[key].append("M" + "L".join(dd) + "Z")

seats = {}
for slug in ("china", "singapore"):
    x, y = dm.project(*geo[slug]["anchor"])
    seats[slug] = [round((x - x0) * s, 1), round((y - y0) * s, 1)]

res = {"viewBox": "0 0 %.0f %.0f" % (W, H), "box": [LON0, LAT0, LON1, LAT1],
       "paths": {k: "".join(v) for k, v in paths.items()}, "seats": seats,
       "note": "Natural Earth 1:50m via world-atlas 2.0.2; desk-map Miller projection"}
print(res["viewBox"], {k: len(v) for k, v in res["paths"].items()}, seats)
out.write_text(json.dumps(res), encoding="utf-8")
