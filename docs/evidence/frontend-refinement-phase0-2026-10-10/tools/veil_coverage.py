import json, sys, os
from pathlib import Path
repo = Path(sys.argv[1])
sys.path.insert(0, str(repo)); sys.path.insert(0, str(repo/'scripts'))
os.chdir(repo)
import pw_env
from core import brief_collection as bc
rows=[]
for p in sorted((repo/'output/the-pla-watch/posts').glob('*.json')):
    sc=json.loads(p.read_text())
    date=p.stem
    cur=pw_env.editorial_veil_for_edition(date)
    src=pw_env.source_veil_for_edition(date, sidecar=sc)
    meta_p=repo/f'output/the-pla-watch/media/{date}-source-image.json'
    meta=json.loads(meta_p.read_text()) if meta_p.exists() else {}
    url=meta.get('article_url','')
    hit=any(pw_env._norm_url(e.get('url'))==pw_env._norm_url(url) for e in sc.get('source_trail') or []) if url else False
    rows.append(dict(kind='historical',no=sc.get('issue_number'),date=date,title=(sc.get('title') or sc.get('headline') or '')[:60],
        curated=(cur or {}).get('id'),curated_license=(cur or {}).get('license'),
        source_veil=bool(src), source_meta=bool(meta), trail_url_match=hit,
        source_host=(url.split('/')[2] if url.count('/')>=2 else ''), note=(meta.get('note') or meta.get('credit') or '')[:90],
        meta_keys=sorted(meta.keys())))
md=repo/'briefs/media'
for p in sorted((repo/'briefs').glob('*.json')):
    sc=json.loads(p.read_text()); slug=p.stem
    v=bc.brief_veil(slug, sc, md)
    meta_p=md/f'{slug}-source-image.json'
    meta=json.loads(meta_p.read_text()) if meta_p.exists() else {}
    rows.append(dict(kind='native',no=sc.get('issue_number') or sc.get('number'),date=sc.get('published_at') or sc.get('date') or sc.get('week_ending'),slug=slug,title=(sc.get('title') or '')[:60],
        source_veil=bool(v), source_meta=bool(meta), note=(meta.get('note') or '')[:90], meta_keys=sorted(meta.keys()),
        trail_len=len(sc.get('source_trail') or []), top_keys=sorted(sc.keys())[:40]))
for r in rows: print(json.dumps(r, ensure_ascii=False))
