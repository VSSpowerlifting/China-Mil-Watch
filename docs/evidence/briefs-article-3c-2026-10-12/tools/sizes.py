"""HTML + linked local CSS bytes per article route. usage: sizes.py <hist_root> <site_root>"""
import sys, re
from pathlib import Path
H, R = Path(sys.argv[1]), Path(sys.argv[2])
pages = sorted((H/"the-pla-watch/posts").glob("*.html")) + sorted((R/"briefs").glob("*.html"))
for p in pages:
    html = p.read_text(encoding="utf-8"); css = 0; js = 0
    for href in re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', html) + re.findall(r'<link[^>]+href="([^"]+\.css)"', html):
        f = (p.parent / href.split("?")[0]).resolve()
        if not f.exists(): f = (R / href.split("?")[0].lstrip("./").replace("../","")).resolve()
        css += f.stat().st_size if f.exists() else 0
    for src in set(re.findall(r'<script[^>]+src="([^"]+)"', html)):
        f = (p.parent / src.split("?")[0]).resolve()
        if not f.exists(): f = (R / src.split("?")[0].replace("../","")).resolve()
        js += f.stat().st_size if f.exists() else 0
    print(f"{p.stem[:40]:40} html={len(html.encode()):6} css={css:6} total={len(html.encode())+css:6} js={js}")
