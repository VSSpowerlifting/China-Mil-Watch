#!/usr/bin/env python3
"""Fetch licensed source faces and build Latin WOFF2 assets (development only).

Requires fonttools==4.60.2 and brotli==1.2.0. Production uses the committed
faces and does not request Google Fonts. A rebuild can receive newer upstream
faces: review DELIVERY.json hashes and licenses before committing.
"""
from pathlib import Path
import urllib.request,re,json,hashlib,io,sys
from fontTools.ttLib import TTFont
from fontTools import subset
ROOT = Path(__file__).resolve().parent.parent
root = ROOT / 'site/assets/fonts'; root.mkdir(parents=True, exist_ok=True)
families=[('instrument-serif','Instrument+Serif:ital@0;1','instrumentserif'),('inter','Inter:wght@400;600','inter'),('source-serif-4','Source+Serif+4:ital,wght@0,400;0,600;1,400','sourceserif4')]
css=[];receipt=[]
for slug,query,ghslug in families:
 url='https://fonts.googleapis.com/css2?family='+query+'&display=swap'
 raw=urllib.request.urlopen(url).read().decode()
 # Retain Latin subset only. CJK uses the existing system language stacks.
 blocks=re.findall(r'(@font-face\s*\{.*?\})',raw,re.S)
 if not blocks: raise RuntimeError('No Latin face for '+slug)
 for i,b in enumerate(blocks):
  source=re.search(r'url\(([^)]+)\)',b).group(1)
  blob=urllib.request.urlopen(source).read();name=slug+'-'+str(i)+'.woff2'
  font=TTFont(io.BytesIO(blob),recalcTimestamp=False)
  options=subset.Options();options.recalc_timestamp=False;options.name_IDs=['*'];options.name_legacy=True;options.name_languages=['*']
  job=subset.Subsetter(options=options);job.populate(unicodes=subset.parse_unicodes('U+0000-024F,U+1E00-1EFF,U+2000-206F,U+20A0-20CF,U+2190-21FF,U+FEFF,U+FFFD'));job.subset(font)
  font.flavor='woff2';buffer=io.BytesIO();font.save(buffer);blob=buffer.getvalue()
  (root/name).write_bytes(blob)
  b=b.replace('}', '  unicode-range: U+0000-024F,U+1E00-1EFF,U+2000-206F,U+20A0-20CF,U+2190-21FF,U+FEFF,U+FFFD;\n}')
  css.append(b.replace(source,'assets/fonts/'+name).replace("format('truetype')","format('woff2')"))
  receipt.append({'file':name,'source':source,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()})
 license_url='https://raw.githubusercontent.com/google/fonts/main/ofl/'+ghslug+'/OFL.txt'
 (root/(slug+'-OFL.txt')).write_bytes(urllib.request.urlopen(license_url).read())
(root/'DELIVERY.json').write_text(json.dumps({'provider':'Google Fonts','subset':'Latin and Latin Extended, punctuation, currency and arrows; original-language CJK uses system stacks','assets':receipt},indent=2)+'\n')
(ROOT / 'site/preview/fonts.css').write_text('\n'.join(css)+'\n')
print([(r['file'],r['bytes']) for r in receipt])
