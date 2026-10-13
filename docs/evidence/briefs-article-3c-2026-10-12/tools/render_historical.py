"""Render the 14 historical Briefs into a disposable directory (never output/)."""
import json, sys
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve(); OUT = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(ROOT))
from scripts.rerender_pla_watch import _build_post_context
from scripts.historical_brief_render import render_historical_brief
try:  # the review revision's No. 14 -> No. 15 bridge; absent at the baseline
    from scripts.historical_brief_render import next_brief_after
except ImportError:
    next_brief_after = None
POSTS = ROOT / "output/the-pla-watch/posts"
assert ROOT / "output" not in OUT.parents and OUT != ROOT / "output"
sides = sorted((json.loads(p.read_text()) for p in POSTS.glob("*.json")), key=lambda s: s["date"])
(OUT / "the-pla-watch/posts").mkdir(parents=True, exist_ok=True)
bridge = next_brief_after(sides) if next_brief_after else None
for i, side in enumerate(sides):
    ctx = _build_post_context(side)
    ctx["prev_post"] = sides[i-1] if i else None
    ctx["next_post"] = sides[i+1] if i+1 < len(sides) else None
    (OUT / f"the-pla-watch/posts/{side['date']}.html").write_text(render_historical_brief(ctx, **(
        {"next_brief": bridge["link"]} if bridge and bridge["slug"] == side["date"] else {})), encoding="utf-8")
print(len(sides), "historical pages ->", OUT)
