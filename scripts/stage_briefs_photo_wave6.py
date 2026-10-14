#!/usr/bin/env python3
"""TEMPORARY 2022 CC0 Jiangnan Shipyard original sourcing; remove before merging.
Acquires Commons checksum-bound original, not footage from 2026 air-wing test.
Never publishes any page; no collector/workflow production integration.
"""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode,urlsplit
import json,hashlib,io,sys
from PIL import Image
import PIL
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.build_brief_cover import derive as hero
from scripts.build_catalogue_media import derive as card
from core.catalogue_media import load_admissions,resolve_catalogue_media,sha256_file
ID="jiangnan-shipyard-fujian-context-2022"
TITLE="File:JiangnanShipyardChangxingIsland (cropped).jpg"
PAGE="https://commons.wikimedia.org/wiki/File:JiangnanShipyardChangxingIsland_(cropped).jpg"
PHOTO_SHA1="d932f61c8c317ea93f87a6f0d3742e3d4480aabc"
SOURCE_DIM=(1085,708)
ORIGINAL_BYTES=656759
ED=ROOT/"site/assets/editorial"
MAN=ED/"manifest.json"
CAT=ROOT/"site/assets/catalogue/admissions.json"
SRC=ED/(ID+".jpg")
DERIV=ED/"derivatives"/(ID+"-1600.jpg")
ROUTE="assets/catalogue/media/no-02-"+ID+".jpg"
CREATOR="Raysonho (photo); Meeepmep (Commons crop)"
CAPTION=("Jiangnan Shipyard on Shanghai's Changxing Island, photographed April 2022, during the period "
         "when the carrier later named Fujian was being built there. Shipbuilding context, not a photograph "
         "of the May 2026 KJ-600 carrier qualification or Rocket Force training.")
ALT="Shipbuilding facilities on Shanghai's Changxing Island, photographed in April 2022."
SHARED={
    "alt":ALT,"caption":CAPTION,
    "date_note":"Photographed 4 April 2022; original creator dedicated image under CC0 1.0. Commons crop June 2024.",
    "creator":CREATOR,"creator_native":"","creator_native_lang":"",
    "credit":CREATOR+" · Public domain · via Wikimedia Commons",
    "license":"Public domain","license_url":"","source_page":PAGE,
    "source_label":"Wikimedia Commons","notice":"","depicts":"context"
}
HEADERS={"User-Agent":"IndoPacificRecord-image-provenance/1.0 (https://indopacificrecord.org)"}
def main():
    m=json.loads(MAN.read_text(encoding="utf8"))
    a=json.loads(CAT.read_text(encoding="utf8"))
    assert not any(x.get("id")==ID for x in m)
    assert not any(x.get("issue")==2 for x in a["entries"])
    query=urlencode({"action":"query","format":"json","prop":"imageinfo","iiprop":"sha1|size|url","titles":TITLE})
    req=Request("https://commons.wikimedia.org/w/api.php?"+query,headers=HEADERS)
    with urlopen(req,timeout=35) as response:
        info=next(iter(json.load(response)["query"]["pages"].values()))["imageinfo"][0]
    assert info["sha1"]==PHOTO_SHA1,info
    assert (info["width"],info["height"])==SOURCE_DIM,info
    assert info["size"]==ORIGINAL_BYTES,info
    url=info["url"]
    assert urlsplit(url).hostname=="upload.wikimedia.org",url
    with urlopen(Request(url,headers=HEADERS),timeout=45) as response:
        assert urlsplit(response.url).hostname=="upload.wikimedia.org",response.url
        raw=response.read(1_500_001)
    assert len(raw)==ORIGINAL_BYTES,len(raw)
    assert hashlib.sha1(raw).hexdigest()==PHOTO_SHA1
    with Image.open(io.BytesIO(raw)) as im:
        assert im.format=="JPEG" and im.size==SOURCE_DIM,(im.format,im.size)
        im.verify()
    SRC.write_bytes(raw)
    blob,shape=hero(SRC,1600,"jpg")
    DERIV.write_bytes(blob)
    served=ROOT/"site"/ROUTE
    served.parent.mkdir(parents=True,exist_ok=True)
    served.write_bytes(card(DERIV,"50% 50%"))
    m.append({
       "id":ID,"file":SRC.name,"width":SOURCE_DIM[0],"height":SOURCE_DIM[1],
       "sha256":sha256_file(SRC),"original_url":url,
       "source_fingerprint":{"sha1":PHOTO_SHA1,"sha256":sha256_file(SRC)},
       "origin_reference":"https://commons.wikimedia.org/wiki/File:JiangnanShipyardChangxingIsland.jpg",
       "license_basis":"Original author Raysonho's own-work CC0 1.0 dedication; Commons cropped derivative by Meeepmep; metadata 4 April 2022, Commons SHA-1 pinned.",
       "note":"Shipyard industrial-site context for later Fujian carrier, NOT KJ-600 launch or military-training evidence. Exact ship hull visibility needs owner crop review.",
       "focal":"50% 50%",
       "match":{"article_urls":[],"categories":[],"threads":[],"editions":[],"routes":[]},
       "derivatives":[{"file":"derivatives/"+ID+"-1600.jpg","width":shape[0],"height":shape[1],"sha256":sha256_file(DERIV)}],
       **SHARED
    })
    a["entries"].append({
      "issue":2,"week_ending":"2026-05-16","status":"admitted",
      "source_file":"site/assets/editorial/derivatives/"+ID+"-1600.jpg",
      "source_manifest_id":ID,"focal":"50% 50%","served":ROUTE,
      "width":720,"height":480,"source_sha256":sha256_file(DERIV),
      "served_sha256":sha256_file(served),
      "change_note":"Cropped and resized by IPR.",
      "review_note":"Research candidate only: clear CC0 original, relevant industrial backdrop; owner must inspect how legibly the site/ship shows at 720x480.",
      **SHARED
    })
    a["built_with"]={"pillow":PIL.__version__}
    MAN.write_text(json.dumps(m,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    CAT.write_text(json.dumps(a,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    got=resolve_catalogue_media({"kind":"issue","entry":{"issue":2,"date":"2026-05-16"}},
         load_admissions(repo_root=ROOT),repo_root=ROOT)
    assert got.is_photograph,got.reason
    blocked={x["issue"]:x["status"] for x in a["entries"] if x["issue"] in (1,10,12)}
    assert blocked=={1:"held",10:"held",12:"denied"},blocked
    print("Staged No2 verified CC0 photo; source "+sha256_file(SRC)+" card "+sha256_file(served))
if __name__=="__main__":main()
