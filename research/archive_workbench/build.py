"""Build only into an ignored, private namespace; never production output."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import time

from .corpus import ROOT, build_corpus, encoded

DEFAULT = ROOT / 'build/archive-workbench'
SOURCE = Path(__file__).parent / 'web'


def destination(path):
    requested = Path(path).absolute()
    resolved = requested.resolve()
    allowed = (ROOT / 'build').resolve()
    if (requested.is_symlink() or resolved == allowed or allowed not in resolved.parents
            or subprocess.run(['git', 'check-ignore', '-q', str(resolved)], cwd=ROOT).returncode):
        raise ValueError('preview_destination_must_be_ignored_under_build')
    for parent in requested.parents:
        if parent == ROOT:
            break
        if parent.is_symlink():
            raise ValueError('preview_destination_symlink_prohibited')
    if resolved.exists() and any(resolved.iterdir()):
        raise ValueError('preview_destination_must_be_new_or_empty')
    return resolved


def build(path=DEFAULT):
    out = destination(path)
    start = time.perf_counter()
    corpus, manifest = build_corpus()
    # Boundary validations finish before any preview bytes are written.
    out.mkdir(parents=True, exist_ok=True)
    for name in ('index.html', 'styles.css', 'search.js', 'app.js'):
        shutil.copyfile(SOURCE / name, out / name)
    shutil.copyfile(ROOT / 'site/assets/identity/selected-ipr/ipr-accent-32.png', out / 'favicon.png')
    shutil.copyfile(ROOT / 'site/assets/identity/selected-ipr/ipr-navy-160.png', out / 'ipr.png')
    (out / 'index.json').write_bytes(encoded(corpus))
    (out / 'manifest.json').write_bytes(encoded(manifest))
    (out / '.ipr-private-preview').write_text('archive-workbench/1\n', encoding='utf-8')
    (out / 'robots.txt').write_text('User-agent: *\nDisallow: /\n', encoding='utf-8')
    # Existing local licensed font assets, with the existing font declarations.
    shutil.copyfile(ROOT / 'site/preview/fonts.css', out / 'fonts.css')
    fonts = out / 'assets/fonts'
    fonts.mkdir(parents=True)
    for name in ('instrument-serif-1.woff2', 'inter-0.woff2', 'inter-1.woff2', 'source-serif-4-1.woff2'):
        shutil.copyfile(ROOT / 'site/assets/fonts' / name, fonts / name)
    metrics = {'build_seconds': round(time.perf_counter() - start, 4),
               'index_bytes': (out / 'index.json').stat().st_size,
               'included': manifest['included']}
    (out / 'metrics.json').write_bytes(encoded(metrics))
    return out, metrics


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=DEFAULT)
    args = parser.parse_args()
    target, results = build(args.out)
    print(target)
    print(results)
