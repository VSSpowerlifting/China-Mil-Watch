"""Phase 0 study helper (disposable). Builds small silhouette paths from the
same Natural Earth / world-atlas 2.0.2 TopoJSON the desk map uses, with the
desk map's own decoder and Miller projection, so every emblem is real
geometry. Writes JSON only into the scratchpad.

usage: python -I emblems.py <repo> <countries-50m.json> <countries-10m.json> <out.json>
"""
import json
import math
import sys
from pathlib import Path

repo, f50, f10, out = (Path(a) for a in sys.argv[1:5])
sys.path.insert(0, str(repo / "scripts"))
import desk_map as dm  # noqa: E402  (read-only reuse of the repo decoder)


def load(p):
    topo = json.loads(p.read_text(encoding="utf-8"))
    return topo, dm._decode_arcs(topo)


def rings_for(topo, arcs, ids, keep=None, tol=0.0):
    sarcs = [dm._simplify(a, tol) for a in arcs] if tol else arcs
    rings = []
    for g in topo["objects"]["countries"]["geometries"]:
        if g.get("id") not in ids:
            continue
        for poly in dm._polygons(g):
            for refs in poly[:1]:              # outer ring only; no lakes
                r = dm._shift(dm._ring(refs, sarcs))
                if keep and not keep(r):
                    continue
                rings.append([dm.project(x, y) for x, y in r])
    return rings


def area(pts):
    return dm._area(pts)


def fit(rings, size=100.0, min_share=0.0, pad=4.0, box=None):
    if min_share:
        big = max(area(r) for r in rings)
        rings = [r for r in rings if area(r) >= big * min_share]
    xs = [x for r in rings for x, _ in r]
    ys = [y for r in rings for _, y in r]
    x0, x1, y0, y1 = box or (min(xs), max(xs), min(ys), max(ys))
    s = (size - 2 * pad) / max(x1 - x0, y1 - y0)
    w, h = (x1 - x0) * s + 2 * pad, (y1 - y0) * s + 2 * pad
    parts = []
    for r in rings:
        pts = ["%.1f %.1f" % ((x - x0) * s + pad, (y - y0) * s + pad) for x, y in r]
        dd = [p for i, p in enumerate(pts) if not i or p != pts[i - 1]]
        if len(dd) >= 3:
            parts.append("M" + "L".join(dd) + "Z")
    return {"viewBox": "0 0 %.0f %.0f" % (w, h), "d": "".join(parts),
            "scale": s, "origin": [x0, y0], "pad": pad}


def seat(name, emb, lon, lat):
    x, y = dm.project(lon, lat)
    emb["seat"] = [round((x - emb["origin"][0]) * emb["scale"] + emb["pad"], 1),
                   round((y - emb["origin"][1]) * emb["scale"] + emb["pad"], 1)]
    return emb


geo = json.loads((repo / "desks" / "geography.json").read_text(encoding="utf-8"))["desks"]
t50, a50 = load(f50)
t10, a10 = load(f10)
res = {}

# Desk silhouettes. Small rings below a share of the largest are dropped,
# which also removes contested islets from any national outline.
spec = {
    "china": (t50, a50, {"156"}, 0.002, 0.12),
    "japan": (t50, a50, {"392"}, 0.004, 0.06),
    "vietnam": (t50, a50, {"704"}, 0.02, 0.03),
    "singapore": (t10, a10, {"702"}, 0.05, 0.0),
}
for slug, (t, a, ids, share, tol) in spec.items():
    emb = fit(rings_for(t, a, ids, tol=tol), min_share=share)
    lon, lat = geo[slug]["anchor"]
    res[slug] = seat(slug, emb, lon, lat)

# Hawaii only (the seat), never the sovereign US polygon.
hi = rings_for(t50, a50, {"840"}, keep=lambda r: all(150 < x % 360 < 210 and 15 < y < 25 for x, y in r))
res["hawaii"] = seat("hawaii", fit(hi, min_share=0.0), *geo["us-indopacific"]["anchor"])

# Singapore Strait coast for the relief study: Singapore, southern Johor,
# Batam/Bintan. Box in projected units around 103.4–104.6E, 0.8–1.75N.
bx0, by1 = dm.project(103.35, 0.75)
bx1, by0 = dm.project(104.65, 1.78)
strait = []
for ids in ({"702"}, {"458"}, {"360"}):
    for r in rings_for(t10, a10, ids, tol=0.004):
        xs = [x for x, _ in r]; ys = [y for _, y in r]
        if max(xs) > bx0 and min(xs) < bx1 and max(ys) > by0 and min(ys) < by1 and area(r) > 0.02:
            strait.append(r)
res["strait"] = fit(strait, size=400, pad=0, box=(bx0, bx1, by0, by1))
res["strait"]["note"] = "Natural Earth 10m via world-atlas 2.0.2; rings cropped by viewBox"

# Hainan (an uncontested alternative coast).
hx0, hy1 = dm.project(108.4, 18.0)
hx1, hy0 = dm.project(111.2, 20.3)
hain = [r for r in rings_for(t10, a10, {"156"}, tol=0.006)
        if min(x for x, _ in r) > hx0 - 5 and max(x for x, _ in r) < hx1 + 5
        and min(y for _, y in r) > hy0 - 5 and max(y for _, y in r) < hy1 + 5 and area(r) > 0.5]
res["hainan"] = fit(hain, size=400, pad=8)

for k, v in res.items():
    print(k, v["viewBox"], len(v["d"]), "B", v.get("seat"))
out.write_text(json.dumps(res), encoding="utf-8")

# Provenance check: rebuilding the committed map geometry from this 50m file
# must reproduce the template byte-for-byte.
built = dm.build(f50)
print("50m rebuild matches committed _desk_map_geo.svg:", built == dm.GEO_SVG.read_text(encoding="utf-8"))
