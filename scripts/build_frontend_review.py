#!/usr/bin/env python3
"""Render a complete disposable frontend review, with unchanged carried evidence.

Uses the production renderer and historical sidecar adapter. Never writes
output/, source sidecars, the DB or timeline editorial state. No publication.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def build(destination):
    destination = Path(destination).resolve()
    if destination == ROOT or ROOT in destination.parents or destination in ROOT.parents:
        raise ValueError('Frontend review requires a disposable destination outside the repository')
    spec = importlib.util.spec_from_file_location('ipr_review_render', ROOT/'site/render.py')
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    renderer.render_site(output_dir=destination, site_origin='https://indopacificrecord.org')
    for folder in ('the-pla-watch', 'data', 'assets'):
        for source in (ROOT/'output'/folder).rglob('*'):
            if source.is_file():
                target = destination/source.relative_to(ROOT/'output')
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    from scripts.rerender_pla_watch import _build_post_context, _sidecar_has_body, _flatten_term
    from scripts.historical_brief_render import render_historical_brief, render_historical_utility
    sidecars = [json.loads(p.read_text()) for p in sorted((ROOT/'output/the-pla-watch/posts').glob('*.json'))]
    for i, sidecar in enumerate(sidecars):
        if not _sidecar_has_body(sidecar):
            raise ValueError('Historical sidecar has no body: '+sidecar['date'])
        context = _build_post_context(sidecar)
        context['prev_post'] = sidecars[i-1] if i else None
        context['next_post'] = sidecars[i+1] if i+1<len(sidecars) else None
        (destination/'the-pla-watch/posts'/ (sidecar['date']+'.html')).write_text(render_historical_brief(context))
    newest = list(reversed(sidecars))
    for name in ('index.html', 'archive.html'):
        (destination/'the-pla-watch'/name).write_text(render_historical_utility(
            'Earlier Briefs', 'the-pla-watch/' if name == 'index.html' else 'the-pla-watch/'+name, posts=newest))
    terms = []
    for sidecar in newest:
        word, explanation = _flatten_term(sidecar)
        if word.strip():
            terms.append(dict(term=word, explanation=explanation, date=sidecar['date'],
                              issue_number=sidecar.get('issue_number'),
                              week_ending=sidecar.get('week_ending') or sidecar['date']))
    (destination/'the-pla-watch/terms.html').write_text(render_historical_utility(
        'Terms to Know', 'the-pla-watch/terms.html', terms=terms))
    print('Complete private review: %s; %s historical articles from unchanged sidecars' % (destination, len(sidecars)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    build(parser.parse_args().out)
