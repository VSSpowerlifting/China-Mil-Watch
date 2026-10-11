"""
The relief illustrations' geometry: one symbol sprite, built from data.

`python scripts/build_geo_assets.py <countries-50m.json> <countries-10m.json>`
turns Natural Earth country boundaries (public domain, via the world-atlas
2.0.2 TopoJSON) into three symbol sprites under `site/assets/geo/` and one
receipt. They are split by use so a page fetches only the geometry it shows:
`emblems.svg` (desk silhouettes and seats, small), `strait.svg` (the
Singapore Strait coast) and `region.svg` (the regional fragment behind an
Editorial plate). The inputs
are arguments and are never fetched; the raw TopoJSON is not committed, and
the site build never needs it.

It reuses `scripts/desk_map.py`'s decoder, simplifier and Miller projection,
so an emblem is the same coastline the Desks map draws, and its parameters
are the ones reviewed in Phase 0 (docs/FRONTEND_REFINEMENT_PHASE0_2026-10-10.md
§10). The output is deterministic: the same inputs give the same bytes, and
the receipt records the input and output hashes, never a time.

Every symbol is decorative. A page places one with
`<svg aria-hidden="true"><use href="assets/geo/emblems.svg#china"/></svg>`
and styles it through custom properties (`--rl-w1` … `--rl-seat`), which
cross into the `<use>` tree; class selectors on the page cannot reach it.
`--rl-draw` (0 drawn, 1 hidden) offsets the water lines for the draw motion.

Geography is drawn, never claimed. Small rings below a share of a country's
largest are dropped, which also removes contested islets; the US desk is
drawn as Hawaii, its seat, never the sovereign US outline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import desk_map as dm  # noqa: E402

REPO_ROOT = dm.REPO_ROOT
OUT_DIR = REPO_ROOT / "site" / "assets" / "geo"
SPRITES = ("emblems.svg", "strait.svg", "region.svg")
RECEIPT = "geo.receipt.json"
SOURCE = "Natural Earth country boundaries (public domain), via world-atlas 2.0.2 (ISC)"

# Desk silhouettes: (file, Natural Earth ids, minimum share of the largest
# ring, Douglas-Peucker tolerance in degrees). Phase 0 values.
DESKS = {
    "china": ("50m", ("156",), 0.002, 0.12),
    "japan": ("50m", ("392",), 0.004, 0.06),
    "vietnam": ("50m", ("704",), 0.02, 0.03),
    "singapore": ("10m", ("702",), 0.05, 0.0),
}
HAWAII = ("50m", ("840",), lambda r: all(150 < x % 360 < 210 and 15 < y < 25 for x, y in r))
# The Singapore Strait: Singapore, southern Johor, Batam and Bintan, cropped.
STRAIT = ("10m", (("702",), ("458",), ("360",)), 0.004, (103.35, 0.75, 104.65, 1.78), 0.02)
# The regional fragment behind an Editorial plate.
REGION = ("50m", 0.09, (70.0, -4.0, 150.0, 45.0), 300.0, 0.00002,
          {"china": ("156",), "singapore": ("702",)})

EMBLEM_PAD = 9  # viewBox margin so the outer water line is not clipped

# Default paint, used only where a page sets no --rl-* property. Widths are in
# each symbol's own units: emblems are 100 across, the strait 400, the region 300.
EMBLEM_WL = (("#9cc9c2", 15), ("#fafbf7", 12), ("#9cc9c2", 8), ("#fafbf7", 5.6), ("#6fb0a7", 2.4))
STRAIT_WL = (("#22505a", 22), ("#142e38", 18), ("#2a5f66", 13), ("#142e38", 9), ("#4f8f8c", 2.4))
REGION_WL = (("#24505a", 4), ("#18343f", 2.2))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    topo = json.loads(path.read_text(encoding="utf-8"))
    return topo, dm._decode_arcs(topo)


def rings_for(topo, arcs, ids, keep=None, tol=0.0):
    """Projected outer rings (no lakes) of the countries with these ids."""
    sarcs = [dm._simplify(a, tol) for a in arcs] if tol else arcs
    rings = []
    for g in topo["objects"]["countries"]["geometries"]:
        if g.get("id") not in ids:
            continue
        for poly in dm._polygons(g):
            r = dm._shift(dm._ring(poly[0], sarcs))
            if keep and not keep(r):
                continue
            rings.append([dm.project(x, y) for x, y in r])
    return rings


def _d(rings, x0, y0, s, pad):
    parts = []
    for r in rings:
        pts = ["%.1f %.1f" % ((x - x0) * s + pad, (y - y0) * s + pad) for x, y in r]
        dd = [p for i, p in enumerate(pts) if not i or p != pts[i - 1]]
        if len(dd) >= 3:
            parts.append("M" + "L".join(dd) + "Z")
    return "".join(parts)


def fit(rings, size=100.0, min_share=0.0, pad=4.0, box=None):
    """Scale rings into a `size`-wide box; the Phase 0 emblem fit."""
    if min_share:
        big = max(dm._area(r) for r in rings)
        rings = [r for r in rings if dm._area(r) >= big * min_share]
    xs = [x for r in rings for x, _ in r]
    ys = [y for r in rings for _, y in r]
    x0, x1, y0, y1 = box or (min(xs), max(xs), min(ys), max(ys))
    s = (size - 2 * pad) / max(x1 - x0, y1 - y0)
    w, h = (x1 - x0) * s + 2 * pad, (y1 - y0) * s + 2 * pad
    return {"w": round(w), "h": round(h), "d": _d(rings, x0, y0, s, pad),
            "scale": s, "origin": (x0, y0), "pad": pad}


def seat(emb, lon, lat):
    x, y = dm.project(lon, lat)
    return [round((x - emb["origin"][0]) * emb["scale"] + emb["pad"], 1),
            round((y - emb["origin"][1]) * emb["scale"] + emb["pad"], 1)]


def geometry(files, anchors):
    """Every path and seat, from {'50m': (topo, arcs), '10m': ...}."""
    res = {}
    for slug, (f, ids, share, tol) in DESKS.items():
        emb = fit(rings_for(*files[f], set(ids), tol=tol), min_share=share)
        emb["seat"] = seat(emb, *anchors[slug])
        res[slug] = emb
    f, ids, keep = HAWAII
    emb = fit(rings_for(*files[f], set(ids), keep=keep))
    emb["seat"] = seat(emb, *anchors["us-indopacific"])
    res["hawaii"] = emb

    f, groups, tol, (lw, ls, le, ln), amin = STRAIT
    bx0, by1 = dm.project(lw, ls)
    bx1, by0 = dm.project(le, ln)
    rings = []
    for ids in groups:
        for r in rings_for(*files[f], set(ids), tol=tol):
            xs = [x for x, _ in r]
            ys = [y for _, y in r]
            if max(xs) > bx0 and min(xs) < bx1 and max(ys) > by0 and min(ys) < by1 and dm._area(r) > amin:
                rings.append(r)
    res["strait"] = fit(rings, size=400, pad=0, box=(bx0, bx1, by0, by1))

    f, tol, (lw, ls, le, ln), width, share, desk_ids = REGION
    topo, arcs = files[f]
    sarcs = [dm._simplify(a, tol) for a in arcs]
    x0, y1 = dm.project(lw, ls)
    x1, y0 = dm.project(le, ln)
    s = width / (x1 - x0)
    amin = (x1 - x0) * (y1 - y0) * share  # drops specks, incl. contested islets
    groups = {"land": [], **{k: [] for k in desk_ids}}
    for g in topo["objects"]["countries"]["geometries"]:
        key = next((k for k, ids in desk_ids.items() if g.get("id") in ids), "land")
        for poly in dm._polygons(g):
            r = [dm.project(x, y) for x, y in dm._shift(dm._ring(poly[0], sarcs))]
            xs = [p[0] for p in r]
            ys = [p[1] for p in r]
            if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1:
                continue
            if key == "land" and dm._area(r) < amin:
                continue
            groups[key].append(r)
    region = {"w": round(width), "h": round((y1 - y0) * s), "scale": s, "origin": (x0, y0), "pad": 0,
              "paths": {k: _d(v, x0, y0, s, 0) for k, v in groups.items()}}
    region["seats"] = {k: seat(region, *anchors[k]) for k in desk_ids}
    res["region"] = region
    return res


def _num(v):
    return ("%g" % v)


def _wl(ref, lines, n0=1):
    return "".join(
        '<use href="#%s" style="stroke:var(--rl-w%d,%s);stroke-width:var(--rl-w%dw,%s)"/>'
        % (ref, i, colour, i, _num(width))
        for i, (colour, width) in enumerate(lines, n0))


WL_GROUP = '<g style="fill:none;stroke-linejoin:round;stroke-dasharray:1;stroke-dashoffset:var(--rl-draw,0)">'


HEAD = ("<!-- Generated by scripts/build_geo_assets.py from %s. Do not edit by hand. "
        "Decorative: every use is aria-hidden. Outlines are generalized and are not boundary claims. -->" % SOURCE)
EMBLEMS = ("china", "japan", "vietnam", "singapore", "hawaii")


def _doc(defs, symbols):
    return "\n".join(['<svg xmlns="http://www.w3.org/2000/svg">', HEAD, "<defs>", *defs, "</defs>",
                      *symbols, "</svg>"]) + "\n"


def sprites(geo) -> dict:
    """{file name: SVG text} for the three sprites."""
    p = EMBLEM_PAD
    defs, symbols = [], []
    for slug in EMBLEMS:
        e = geo[slug]
        ref = "d-" + slug
        defs.append('<path id="%s" pathLength="1" d="%s"/>' % (ref, e["d"]))
        vb = "%d %d %d %d" % (-p, -p, e["w"] + 2 * p, e["h"] + 2 * p)
        symbols.append(
            '<symbol id="%s" viewBox="%s">%s%s</g>'
            '<use href="#%s" transform="translate(1.4 2)" style="fill:var(--rl-side,#0f2830)"/>'
            '<use href="#%s" style="fill:var(--rl-land,#142e38);stroke:var(--rl-coast,#3c6370);stroke-width:var(--rl-coastw,.5)"/>'
            "</symbol>" % (slug, vb, WL_GROUP, _wl(ref, EMBLEM_WL), ref, ref))
        cx, cy = e["seat"]
        symbols.append(
            '<symbol id="%s-seat" viewBox="%s"><circle cx="%s" cy="%s" r="2.8" '
            'style="fill:var(--rl-seat,#fafbf7);stroke:var(--rl-seat-ring,#142e38);stroke-width:1.2"/></symbol>'
            % (slug, vb, _num(cx), _num(cy)))
    out = {"emblems.svg": _doc(defs, symbols)}

    e = geo["strait"]
    out["strait.svg"] = _doc(
        ['<path id="d-strait" pathLength="1" d="%s"/>' % e["d"]],
        ['<symbol id="strait" viewBox="0 0 %d %d">%s%s</g>'
         '<use href="#d-strait" transform="translate(3 5)" style="fill:var(--rl-side,#0b1f27)"/>'
         '<use href="#d-strait" style="fill:var(--rl-land,#1d3d4a);stroke:var(--rl-coast,#5f9c97);stroke-width:var(--rl-coastw,1)"/>'
         "</symbol>" % (e["w"], e["h"], WL_GROUP, _wl("d-strait", STRAIT_WL))])

    reg = geo["region"]
    vb = "0 0 %d %d" % (reg["w"], reg["h"])
    defs = ['<path id="d-region-%s" pathLength="1" d="%s"/>' % (k, d) for k, d in reg["paths"].items()]
    symbols = ['<symbol id="region" viewBox="%s">%s%s</g>'
               '<use href="#d-region-land" style="fill:var(--rl-land,#24434e);stroke:var(--rl-coast,#3f6b74);stroke-width:.35"/>'
               "</symbol>" % (vb, WL_GROUP, _wl("d-region-land", REGION_WL))]
    for key, (cx, cy) in reg["seats"].items():
        symbols.append(
            '<symbol id="region-%s" viewBox="%s">'
            '<use href="#d-region-%s" style="fill:var(--rl-desk,#3d7f86);stroke:var(--rl-desk-edge,#92d5cc);stroke-width:.5"/>'
            '<circle cx="%s" cy="%s" r="2.4" style="fill:var(--rl-seat,#f3f2ec);stroke:var(--rl-seat-ring,#142e38);stroke-width:1"/>'
            "</symbol>" % (key, vb, key, _num(cx), _num(cy)))
    out["region.svg"] = _doc(defs, symbols)
    return out


def receipt(inputs, geo, files) -> dict:
    symbols = {slug: "%d %d %d %d" % (-EMBLEM_PAD, -EMBLEM_PAD, geo[slug]["w"] + 2 * EMBLEM_PAD,
                                      geo[slug]["h"] + 2 * EMBLEM_PAD)
               for slug in EMBLEMS}
    symbols["strait"] = "0 0 %d %d" % (geo["strait"]["w"], geo["strait"]["h"])
    symbols["region"] = "0 0 %d %d" % (geo["region"]["w"], geo["region"]["h"])
    return {
        "generator": "scripts/build_geo_assets.py",
        "source": SOURCE,
        "licence": "Natural Earth: public domain. world-atlas: ISC.",
        "inputs": {name: {"file": "countries-%s.json" % name, "sha256": digest}
                   for name, digest in sorted(inputs.items())},
        "projection": "scripts/desk_map.py Miller cylindrical (project)",
        "parameters": {
            "desks": {k: {"file": v[0], "ids": list(v[1]), "min_share": v[2], "tolerance": v[3]}
                      for k, v in DESKS.items()},
            "hawaii": {"file": HAWAII[0], "ids": list(HAWAII[1]),
                       "keep": "rings within 150-210E (mod 360), 15-25N; seat from us-indopacific"},
            "strait": {"file": STRAIT[0], "ids": [i for g in STRAIT[1] for i in g], "tolerance": STRAIT[2],
                       "box_lon_lat": list(STRAIT[3]), "min_area": STRAIT[4]},
            "region": {"file": REGION[0], "tolerance": REGION[1], "box_lon_lat": list(REGION[2]),
                       "width": REGION[3], "min_area_share": REGION[4],
                       "desks": {k: list(v) for k, v in REGION[5].items()}},
            "emblem_pad": EMBLEM_PAD,
        },
        "symbols": symbols,
        "seats": {**{slug: geo[slug]["seat"] for slug in EMBLEMS},
                  **{"region-" + k: v for k, v in geo["region"]["seats"].items()}},
        "outputs": {name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                    for name, data in sorted(files.items())},
    }


def build(f50: Path, f10: Path, out_dir: Path = OUT_DIR, geography: Path = dm.GEOGRAPHY) -> dict:
    files = {"50m": load(f50), "10m": load(f10)}
    anchors = {slug: d["anchor"] for slug, d in
               json.loads(geography.read_text(encoding="utf-8"))["desks"].items()}
    geo = geometry(files, anchors)
    files = {name: text.encode("utf-8") for name, text in sprites(geo).items()}
    rec = receipt({"50m": sha256(f50), "10m": sha256(f10)}, geo, files)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (out_dir / name).write_bytes(data)
    (out_dir / RECEIPT).write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return {"geometry": geo, "receipt": rec}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("countries_50m", type=Path)
    ap.add_argument("countries_10m", type=Path)
    ap.add_argument("--out", type=Path, default=OUT_DIR, help="output folder (default: site/assets/geo)")
    args = ap.parse_args(argv)
    res = build(args.countries_50m, args.countries_10m, args.out)
    for name, out in res["receipt"]["outputs"].items():
        print("wrote %s/%s (%d bytes, sha256 %s)" % (args.out, name, out["bytes"], out["sha256"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
