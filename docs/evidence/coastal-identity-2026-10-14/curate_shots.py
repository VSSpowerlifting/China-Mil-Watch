"""Create the small committed review set from a complete local capture archive.
Only screenshots are cropped/compressed. Site assets and source evidence are untouched.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image

EVIDENCE=Path(__file__).resolve().parent
HEIGHTS={'home':None,'analysis':4000,'record':2600,'native':3300,'laos':3600,'historical':3300}
FOCUSED=('after-home-editorial-1280.webp','after-native-signal-375.webp',
         'after-v2-finding-1280.webp','after-record-custody-1280.webp',
         'after-home-dark-focus-375.webp','after-record-1280-forced.webp',
         'before-home-1280-print.webp','after-home-1280-print.webp','after-native-1280-print.webp')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True,help='Complete, external shots directory')
    args=parser.parse_args();source=args.source.resolve();target=EVIDENCE/'shots'
    if source==target.resolve():parser.error('use an external full archive, never the curated set as input')
    inventory=[];keep=set()
    def save(name,height=None,lossless=False):
        src=source/name;output=target/(src.stem+'.webp')
        with Image.open(src) as im:
            original=im.size;crop=(0,0,im.width,min(im.height,height or im.height))
            im=im.crop(crop)
            im.save(output,'WEBP',quality=80,method=6,lossless=lossless)
            dimensions=im.size
        keep.add(output.name)
        inventory.append({'file':output.name,'source_capture':name,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
                          'source_dimensions':original,'crop':crop,'dimensions':dimensions,
                          'coverage':'full page' if crop[3]==original[1] else 'opening and reading excerpt; full page generated locally',
                          'encoding':'lossless WebP' if lossless else 'WebP quality80 at original pixel width',
                          'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest()})
    target.mkdir(exist_ok=True)
    for route,height in HEIGHTS.items():
        for width in (375,1280):
            for phase in ('before','after'):save(f'{phase}-{route}-{width}.jpg',height)
    for name in FOCUSED:save(name,lossless=True)
    for old in target.iterdir():
        if old.is_file() and old.name not in keep:old.unlink()
    report={'original_count':len(list(source.iterdir())),'original_bytes':sum(p.stat().st_size for p in source.iterdir() if p.is_file()),
            'retained_count':len(inventory),'retained_bytes':sum(p['bytes'] for p in inventory),
            'complete_run':'48 full page captures, modes and component supplements generated externally by capture.py',
            'images':inventory}
    (EVIDENCE/'image-inventory.json').write_text(json.dumps(report,indent=2))
    (EVIDENCE/'screenshot-hashes.json').write_text(json.dumps({x['file']:x['sha256'] for x in inventory},indent=2))
    print(f"{report['original_count']} -> {len(inventory)} images; {report['original_bytes']} -> {report['retained_bytes']} bytes")


if __name__=='__main__':main()
