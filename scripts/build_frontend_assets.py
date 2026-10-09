#!/usr/bin/env python3
"""Resize full source frames for the reviewed frontend; never write editorial sources.

Requires Pillow. Generated files are committed build assets; the production
renderer only copies them. Re-run after an approved Brief adds a source photo.
"""
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / 'site/assets/frontend'


def build():
    ASSETS.mkdir(parents=True, exist_ok=True)
    sources = [(ROOT / 'site/assets/editorial/reagan-jmsdf-2015.jpg', 'pacific-fleet', (800, 1600, 2500))]
    for path in sorted((ROOT / 'briefs').glob('*.json')):
        brief = json.loads(path.read_text())
        meta_path = path.parent / 'media' / (path.stem + '-source-image.json')
        source = path.parent / 'media' / (path.stem + '-source-image.jpg')
        if brief.get('editorial_status') != 'approved' or not meta_path.is_file() or not source.is_file():
            continue
        meta = json.loads(meta_path.read_text())
        if hashlib.sha256(source.read_bytes()).hexdigest() != meta['source_sha256']:
            raise ValueError('Source photograph hash changed: ' + str(source))
        sources.append((source, path.stem, (600, 1200)))
    entries = []
    for source, slug, widths in sources:
        with Image.open(source) as image:
            for width in widths:
                target = ASSETS / ('%s-%s.webp' % (slug, width))
                if width > image.width:
                    continue
                height = round(image.height * width / image.width)
                image.resize((width, height), Image.Resampling.LANCZOS).save(target, 'WEBP', quality=78, method=6)
                entries.append({'file': target.name, 'source': source.relative_to(ROOT).as_posix(),
                                'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                                'width': width, 'height': height, 'crop': None,
                                'bytes': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    (ASSETS / 'DELIVERY.json').write_text(json.dumps({'builder': 'scripts/build_frontend_assets.py', 'images': entries}, indent=2) + '\n')
    print([(e['file'], e['bytes']) for e in entries])


if __name__ == '__main__':
    build()
