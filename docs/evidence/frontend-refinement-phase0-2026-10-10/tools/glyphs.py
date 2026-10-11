"""Phase 0 study helper (disposable). Writes one silhouette SVG per desk
country (Natural Earth geometry already projected in emblems.json) and the
archive study overlay, which uses them as CSS masks. Phase 1 ships the SVGs
as cached static files; the page gains no script and no inline bytes.

usage: python -I glyphs.py <emblems.json> <outdir> <overlay.css>
"""
import json, sys, urllib.parse
from pathlib import Path
emb, outdir, css = json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2]), Path(sys.argv[3])
DESKS = {"china": "china", "singapore": "singapore", "japan": "japan", "vietnam": "vietnam"}
rules, sizes = [], {}
for slug, key in DESKS.items():
    e = emb[key]; w, h = map(float, e["viewBox"].split()[2:])
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %g %g"><path d="%s"/></svg>' % (w, h, e["d"]))
    (outdir / (slug + ".svg")).write_text(svg); sizes[slug] = len(svg.encode())
    uri = "url(\"data:image/svg+xml," + urllib.parse.quote(svg, safe=" /:=,.\"-") .replace('"', "'") + "\")"
    rules.append('html.study .archive-page .row-side a:is([href$="/%s.html"],[href="%s.html"])::before{--glyph:%s;--ar:%g}' % (slug, slug, uri, w / h))
base = r'''/* Phase 0 study overlay — archive (CSS only; archive JS has ~150 B headroom). */
/* 1. Search panel: modest elevation on the existing surface, one step, no motion. */
html.study .archive-page .finder{background:#fbfaf6;border:1px solid hsl(197 30% 20%/.18);border-top:3px solid var(--band,#142e38);border-radius:2px;
  box-shadow:0 1px 0 hsl(197 40% 12%/.06),0 14px 22px -18px hsl(197 50% 10%/.5)}
html.study .archive-page #f-q{background:#fff;border-color:hsl(197 30% 20%/.3)}
html.study .archive-page #f-q:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
/* 2. Desk marker: the desk country's own silhouette before its link. Same
   link in the template row and browse.js card(), so parity holds. */
html.study .archive-page .row-side a::before{content:"";display:inline-block;vertical-align:-1px;height:11px;width:calc(11px * var(--ar,1.4));margin-right:6px;
  background:var(--band,#142e38);-webkit-mask:var(--glyph) center/contain no-repeat;mask:var(--glyph) center/contain no-repeat}
html.study .archive-page .row-side a:not([href$="china.html"],[href$="singapore.html"],[href$="japan.html"],[href$="vietnam.html"])::before{display:none}
@media (forced-colors:active){html.study .archive-page .finder{box-shadow:none;border:1px solid CanvasText}html.study .archive-page .row-side a::before{background:LinkText}}
'''
css.write_text(base + "\n".join(rules) + "\n")
print(sizes, css.stat().st_size)
