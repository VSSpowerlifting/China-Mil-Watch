#!/usr/bin/env python3
"""One-time branch-only No.15 DVIDS photo staging. Never deploy or schedule.
Remove this downloader and its workflow before opening final PR for merge.
"""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit
import hashlib,io,json,sys
from PIL import Image
import PIL
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.build_brief_cover import derive as make_derivative
from scripts.build_catalogue_media import derive as make_card
from core.catalogue_media import sha256_file,load_admissions,resolve_catalogue_media
from core.source_terms import required_notice
ID="rss-steadfast-pearl-harbor-2026"
SOURCE="https://d1ldvf68ux039x.cloudfront.net/thumbs/photos/2606/9771570/1000w_q95.jpg"
PAGE="https://www.dvidshub.net/image/9771570/republic-singapore-navy-formidable-class-guided-missile-frigate-rss-steadfast-70-arrives-pearl-harbor-rimpac-2026"
ED=ROOT/"site/assets/editorial"
MAN=ED/"manifest.json"
CAT=ROOT/"site/assets/catalogue/admissions.json"
FILENAME=ID+".jpg"
DERIV="derivatives/"+ID+"-1600.jpg"
CARD_ROUTE="assets/catalogue/media/no-15-"+ID+".jpg"
CREDIT="Mass Communication Specialist 1st Class Brandon Roberson, U.S. Navy · Public domain · via DVIDS"
CAPTION=("Republic of Singapore Navy frigate RSS Steadfast (70) arriving in Hawaii for RIMPAC, "
         "22 June 2026. The same ship subsequently participated in Singapore–China Exercise Maritime "
         "Cooperation that September; this photograph does not depict that bilateral exercise.")
ALT="Grey frigate RSS Steadfast (70) viewed side-on in Pearl Harbor, Hawaii, with mountains and trees behind it."
NOTICE=required_notice({"source_page":PAGE,"source_label":"DVIDS"})
assert NOTICE and "does not imply or constitute DoW endorsement" in NOTICE

def main():
    m=json.loads(MAN.read_text(encoding="utf8"))
    a=json.loads(CAT.read_text(encoding="utf8"))
    assert not any(x.get("id")==ID for x in m)
    assert not any(x.get("issue")==15 for x in a["entries"])
    req=Request(SOURCE,headers={"User-Agent":"IndoPacificRecord-image-provenance/1.0 (https://indopacificrecord.org)"})
    with urlopen(req,timeout=55) as resp:
        assert urlsplit(resp.url).hostname=="d1ldvf68ux039x.cloudfront.net"
        raw=resp.read(2_000_001)
    assert 40_000<len(raw)<2_000_000,len(raw)
    with Image.open(io.BytesIO(raw)) as image:
        assert image.format=="JPEG",image.format
        width,height=image.size
        assert width==1000 and 640<=height<=710,(width,height)
        image.verify()
    src=ED/FILENAME
    src.write_bytes(raw)
    dst=ED/DERIV
    blob,dims=make_derivative(src,1600,"jpg")
    dst.write_bytes(blob)
    card_path=ROOT/"site"/CARD_ROUTE
    card_path.parent.mkdir(parents=True,exist_ok=True)
    card_path.write_bytes(make_card(dst,"53% 49%"))
    shared={
      "alt":ALT,"caption":CAPTION,"date_note":"Photographed 22 June 2026 at Pearl Harbor, Hawaii, three months before the bilateral exercise.",
      "creator":"Mass Communication Specialist 1st Class Brandon Roberson, U.S. Navy",
      "creator_native":"","creator_native_lang":"",
      "license":"Public domain","license_url":"","source_page":PAGE,
      "source_label":"DVIDS","credit":CREDIT,"notice":NOTICE,"depicts":"context",
    }
    m.append({
      "id":ID,"file":FILENAME,"width":width,"height":height,
      "sha256":sha256_file(src),"original_url":SOURCE,
      "origin_reference":PAGE,"source_fingerprint":{"sha256":sha256_file(src),"sha1":hashlib.sha1(raw).hexdigest()},
      "license_basis":"US Navy official-duty public domain, DVIDS photo No.9771570, VIRIN 260622-N-SY758-1005; publisher 1000px preview, NOT original full-resolution image.",
      "note":"Same RSS Steadfast vessel as September 2026 Maritime Cooperation, but June RIMPAC at Pearl Harbor. No Singapore MINDEF or PLA photograph rehosting.",
      "focal":"53% 49%","match":{"article_urls":[],"categories":[],"threads":[],"editions":[],"routes":[]},
      "derivatives":[{"file":DERIV,"width":dims[0],"height":dims[1],"sha256":sha256_file(dst)}],
      **shared
    })
    a["entries"].append({
      "issue":15,"week_ending":"2026-09-19","status":"admitted",
      "source_file":"site/assets/editorial/"+DERIV,"source_manifest_id":ID,
      "focal":"53% 49%","served":CARD_ROUTE,
      "change_note":"Cropped and resized by IPR.",
      "review_note":"Candidate only: owner selection required. Historical June 2026 Hawaii RIMPAC photo of the same frigate in Sept 2026 XMC; not an XMC event photo.",
      "source_sha256":sha256_file(dst),"served_sha256":sha256_file(card_path),"width":720,"height":480,
      **shared
    })
    a["built_with"]={"pillow":PIL.__version__}
    MAN.write_text(json.dumps(m,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    CAT.write_text(json.dumps(a,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    got=resolve_catalogue_media({"kind":"brief","entry":{"issue":15,"date":"2026-09-19","slug":"maritime-cooperation-2026"}},
      load_admissions(repo_root=ROOT),repo_root=ROOT)
    assert got.is_photograph,got.reason
    assert {e["issue"]:e["status"] for e in a["entries"] if e["issue"] in (1,10,12)}=={1:"held",10:"held",12:"denied"}
    print("STAGED No.15 DVIDS same-vessel photo. JPEG",width,height,"sha256",sha256_file(src),flush=True)
if __name__=="__main__":main()
