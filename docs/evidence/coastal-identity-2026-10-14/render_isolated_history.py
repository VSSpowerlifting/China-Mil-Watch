"""Re-render unchanged historical contexts in an isolated QA tree only."""
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.rerender_pla_watch import _build_post_context
from scripts.historical_brief_render import render_historical_brief, next_brief_after


def main():
    dest = Path(sys.argv[1]).resolve()
    if dest == ROOT or ROOT in dest.parents or dest in ROOT.parents:
        raise SystemExit('QA destination must be outside the repository')
    source = ROOT / 'output/the-pla-watch'
    shutil.copytree(source, dest/'the-pla-watch', dirs_exist_ok=True)
    # Carry existing evidence and exports without replacing newly built assets.
    for name in ('assets', 'data'):
        for path in (ROOT/'output'/name).rglob('*'):
            if path.is_file():
                target = dest/name/path.relative_to(ROOT/'output'/name)
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
    sides = sorted((json.loads(p.read_text()) for p in (source/'posts').glob('*.json')), key=lambda s:s['date'])
    bridge = next_brief_after(sides)
    for index, side in enumerate(sides):
        context = _build_post_context(side)
        context['prev_post'] = sides[index-1] if index else None
        context['next_post'] = sides[index+1] if index+1<len(sides) else None
        link = bridge['link'] if bridge and bridge['slug']==side['date'] else None
        (dest/'the-pla-watch/posts'/f"{side['date']}.html").write_text(render_historical_brief(context,next_brief=link))
    print(f'{len(sides)} historical pages rendered; canonical inputs untouched')


if __name__ == '__main__':
    main()
