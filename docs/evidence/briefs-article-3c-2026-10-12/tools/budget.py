"""Governed budget per article route. usage: budget.py <site_root>"""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # repo root
from core.frontend_budget import measure_page
R = Path(sys.argv[1]).resolve()
for p in sorted((R/"the-pla-watch/posts").glob("*.html")) + sorted((R/"briefs").glob("*.html")):
    v = measure_page(p, R); print(f"{p.stem[:40]:40} html_css={v['html_css_bytes']:6} js={v['js_bytes']:5} {'OVER' if v['html_css_bytes']>120000 or v['js_bytes']>10000 else ''}")
