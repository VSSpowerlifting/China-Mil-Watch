"""
The Desks-page map: one projection, used twice.

At build time (`python scripts/desk_map.py <countries-50m.json>`) it turns
Natural Earth's 1:50m country boundaries (public domain, via the world-atlas
2.0.2 TopoJSON) into `templates/_desk_map_geo.svg`: the Indo-Pacific frame,
generalized and clipped, with land, borders, coastline and a graticule, and
each desk country under its own id for the page to emphasise. That file is
committed; the raw TopoJSON is not, and the site build never needs it.

At render time `layout()` projects each desk's seat and plate positions from
`desks/geography.json` through the same projection, so an anchor always lands
on the coastline the build drew.

Miller cylindrical, 10 units per degree of longitude. Boundaries are Natural
Earth's de facto lines, generalized for a page-scale map; nothing here is a
boundary claim.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GEOGRAPHY = REPO_ROOT / "desks" / "geography.json"
GEO_SVG = REPO_ROOT / "site" / "preview" / "templates" / "_desk_map_geo.svg"

# The frame: the Arabian Sea to east of Hawaii, the Sea of Okhotsk to Tasmania.
LON_W, LON_E = 60.0, 214.0
LAT_N, LAT_S = 54.0, -47.0
K = 10.0                     # units per degree of longitude
TOLERANCE = 0.06             # Douglas-Peucker tolerance, degrees
MIN_RING_AREA = 6.0          # square units; smaller islands are dropped
MIN_RUN = 26.0               # a leader's horizontal run into its plate, units


def _miller(lat: float) -> float:
    phi = math.radians(lat)
    return math.degrees(1.25 * math.log(math.tan(math.pi / 4 + 0.4 * phi)))


Y_TOP = _miller(LAT_N)
WIDTH = round((LON_E - LON_W) * K)
HEIGHT = round((Y_TOP - _miller(LAT_S)) * K)


def project(lon: float, lat: float) -> tuple:
    return ((lon - LON_W) * K, (Y_TOP - _miller(lat)) * K)


# ── render time ───────────────────────────────────────────────────────────────

def _leader(ax, ay, cx, cy, hang):
    """Anchor → plate. A plate hung `left` or `right` takes the leader at a
    top corner: a vertical drop if needed, one 45° diagonal, then a
    horizontal run that continues the plate's top rule. A plate hung `up` or
    `down` takes a vertical leader square into its bottom or top edge."""
    if hang in ("up", "down"):
        if (cy - ay) * (1 if hang == "down" else -1) < MIN_RUN:
            raise ValueError("leader would cross its own plate")
        return "%.1f,%.1f %.1f,%.1f" % (ax, ay, ax, cy)
    sx = -1 if hang == "left" else 1     # direction of travel along the run
    if (cx - ax) * sx < MIN_RUN:
        raise ValueError("leader would cross its own plate")
    dx = abs(cx - ax) - MIN_RUN
    dy = cy - ay
    d = min(dx, abs(dy))
    sy = 1 if dy > 0 else -1
    pts = [(ax, ay), (ax, ay + sy * (abs(dy) - d)),
           (cx - sx * (MIN_RUN + dx - d), cy), (cx, cy)]
    out = []
    for p in pts:
        if not out or (abs(p[0] - out[-1][0]) > .05 or abs(p[1] - out[-1][1]) > .05):
            out.append(p)
    return " ".join("%.1f,%.1f" % p for p in out)


def _plate(ax, ay, card):
    """Where the plate's box goes, as CSS: the point it hangs from, in
    percent of the map, and the translate that puts the right edge there."""
    hang = card["hang"]
    if hang in ("up", "down"):
        # The leader stays on the anchor's meridian; `align` says how far
        # along the plate's width it meets the edge.
        cx, cy = ax, project(*card["at"])[1]
        tx = "%g%%" % (-100 * card.get("align", .5))
        ty = "-100%" if hang == "up" else "0%"
    else:
        cx, cy = project(*card["at"])
        tx, ty = ("-100%" if hang == "left" else "0%"), "0%"
    return {
        "hang": hang,
        "left": "%.2f%%" % (cx / WIDTH * 100),
        "top": "%.2f%%" % (cy / HEIGHT * 100),
        "tx": tx, "ty": ty,
        "points": _leader(ax, ay, cx, cy, hang),
    }


def layout(desks) -> dict:
    """slug -> anchor and plate placement, for the desks the registry declares
    and the geography file places. Everything else renders in the list only."""
    places = json.loads(GEOGRAPHY.read_text(encoding="utf-8"))["desks"]
    out = {}
    for desk in desks:
        geo = places.get(desk.slug)
        if not geo:
            continue
        lon, lat = geo["anchor"]
        ax, ay = project(lon, lat)
        entry = {
            "seat": geo["seat"],
            "coords": "%.1f°%s %.1f°%s" % (
                abs(lat), "N" if lat >= 0 else "S",
                lon if lon <= 180 else 360 - lon, "E" if lon <= 180 else "W"),
            "x": "%.1f" % ax, "y": "%.1f" % ay,
            # The phone map's own label sits west of a point near the edge.
            "label_west": ax > WIDTH * .7,
        }
        for mode, card in geo["card"].items():
            entry[mode] = _plate(ax, ay, card)
        out[desk.slug] = entry
    return {"width": WIDTH, "height": HEIGHT, "desks": out}


# ── build time ────────────────────────────────────────────────────────────────

def _decode_arcs(topo):
    (sx, sy), (tx, ty) = topo["transform"]["scale"], topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    return arcs


def _simplify(pts, tol):
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        (x1, y1), (x2, y2) = pts[i], pts[j]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        best, idx = 0.0, None
        for k in range(i + 1, j):
            x0, y0 = pts[k]
            dist = (abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / norm
                    if norm else math.hypot(x0 - x1, y0 - y1))
            if dist > best:
                best, idx = dist, k
        if idx is not None and best > tol:
            keep[idx] = True
            stack += [(i, idx), (idx, j)]
    return [p for p, k in zip(pts, keep) if k]


def _polygons(geom):
    if geom["type"] == "MultiPolygon":
        return geom["arcs"]
    return [geom["arcs"]] if geom["type"] == "Polygon" else []


def _ring(refs, arcs):
    pts = []
    for r in refs:
        seg = arcs[r] if r >= 0 else arcs[~r][::-1]
        pts.extend(seg if not pts else seg[1:])
    return pts


def _shift(pts):
    """Wholly-western rings and lines move east of 180°, so Hawaii and the
    far side of Chukotka sit where the Pacific frame expects them."""
    if max(p[0] for p in pts) <= 0:
        return [(x + 360, y) for x, y in pts]
    return pts


PAD = 6.0  # clip a little outside the frame so no edge shows inside it


def _clip_ring(pts):
    """Sutherland–Hodgman against the padded frame, in projected units."""
    edges = [(0, -PAD, 1), (0, WIDTH + PAD, -1), (1, -PAD, 1), (1, HEIGHT + PAD, -1)]
    for axis, bound, sign in edges:
        if not pts:
            break
        out = []
        for i, cur in enumerate(pts):
            prev = pts[i - 1]
            cin = (cur[axis] - bound) * sign >= 0
            pin = (prev[axis] - bound) * sign >= 0
            if cin != pin:
                t = (bound - prev[axis]) / (cur[axis] - prev[axis])
                out.append((prev[0] + t * (cur[0] - prev[0]),
                            prev[1] + t * (cur[1] - prev[1])))
            if cin:
                out.append(cur)
        pts = out
    return pts


def _inside(p):
    return -PAD <= p[0] <= WIDTH + PAD and -PAD <= p[1] <= HEIGHT + PAD


def _clip_line(pts):
    """Split a polyline into the runs that touch the frame."""
    runs, cur = [], []
    for i, p in enumerate(pts):
        near = _inside(p) or (i and _inside(pts[i - 1])) or (
            i + 1 < len(pts) and _inside(pts[i + 1]))
        if near:
            cur.append(p)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return [r for r in runs if len(r) > 1]


def _area(pts):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2)
                   in zip(pts, pts[1:] + pts[:1]))) / 2


def _d(paths, closed):
    parts = []
    for pts in paths:
        coords = ["%.1f %.1f" % p for p in pts]
        # Drop repeats the rounding created.
        dedup = [c for i, c in enumerate(coords) if not i or c != coords[i - 1]]
        if len(dedup) < (3 if closed else 2):
            continue
        parts.append("M" + "L".join(dedup).replace(".0 ", " ").replace(".0L", "L")
                     + ("Z" if closed else ""))
    return "".join(parts)


def _proj(pts):
    return [project(x, y) for x, y in pts]


def build(topo_path: Path) -> str:
    topo = json.loads(Path(topo_path).read_text(encoding="utf-8"))
    arcs = [_simplify(a, TOLERANCE) for a in _decode_arcs(topo)]
    desk_iso = {}
    for slug, geo in json.loads(GEOGRAPHY.read_text(encoding="utf-8"))["desks"].items():
        for iso in geo["countries"]:
            desk_iso[iso] = slug

    # Shared arcs are borders; the land object's rings are the coastline,
    # so one path fills the land and strokes the coast without a border in it.
    use = {}
    desk_rings = {}
    for geom in topo["objects"]["countries"]["geometries"]:
        slug = desk_iso.get(geom.get("id"))
        for poly in _polygons(geom):
            for refs in poly:
                for r in refs:
                    use[r if r >= 0 else ~r] = use.get(r if r >= 0 else ~r, 0) + 1
                if slug:
                    ring = _clip_ring(_proj(_shift(_ring(refs, arcs))))
                    if len(ring) >= 3:
                        desk_rings.setdefault(slug, []).append(ring)
    land = []
    for geom in topo["objects"]["land"]["geometries"]:
        for poly in _polygons(geom):
            for refs in poly:
                ring = _clip_ring(_proj(_shift(_ring(refs, arcs))))
                if len(ring) >= 3 and _area(ring) >= MIN_RING_AREA:
                    land.append(ring)
    borders = []
    for i, n in use.items():
        if n > 1:
            borders += _clip_line(_proj(_shift(arcs[i])))

    lines = []
    for lon in range(80, int(LON_E) + 1, 20):
        x = (lon - LON_W) * K
        lines.append([(x, 0), (x, HEIGHT)])
    for lat in range(-40, int(LAT_N) + 1, 20):
        y = project(LON_W, lat)[1]
        lines.append([(0, y), (WIDTH, y)])

    labels = []
    for lon in range(80, int(LON_E) + 1, 20):
        x = (lon - LON_W) * K
        name = "180°" if lon == 180 else ("%d°E" % lon if lon < 180 else "%d°W" % (360 - lon))
        labels.append('<text x="%.0f" y="%.0f" text-anchor="middle">%s</text>'
                      % (x, HEIGHT - 10, name))
    for lat in range(-40, int(LAT_N) + 1, 20):
        y = project(LON_W, lat)[1]
        name = "0°" if lat == 0 else ("%d°N" % lat if lat > 0 else "%d°S" % -lat)
        labels.append('<text x="%d" y="%.0f" text-anchor="end">%s</text>'
                      % (WIDTH - 12, y - 6, name))

    out = [
        "<!-- Generated by scripts/desk_map.py from Natural Earth 1:50m",
        "     (public domain; world-atlas 2.0.2). Do not edit by hand. -->",
        '<rect class="dm-sea" width="%d" height="%d"/>' % (WIDTH, HEIGHT),
        '<path class="dm-graticule" d="%s"/>' % _d(lines, False),
        '<path class="dm-land" fill-rule="evenodd" d="%s"/>' % _d(land, True),
        "<defs>",
    ]
    for slug, rings in sorted(desk_rings.items()):
        out.append('<path id="dm-geo-%s" fill-rule="evenodd" d="%s"/>'
                   % (slug, _d(rings, True)))
    out += [
        "</defs>",
        '<path class="dm-borders" d="%s"/>' % _d(borders, False),
        '<g class="dm-scale">%s</g>' % "".join(labels),
    ]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: desk_map.py <world-atlas countries-50m.json>")
    svg = build(Path(sys.argv[1]))
    GEO_SVG.write_text(svg, encoding="utf-8")
    print("wrote %s (%d bytes, %dx%d)" % (GEO_SVG, len(svg.encode()), WIDTH, HEIGHT))
