#!/usr/bin/env python3
"""TEMPORARY owner-approved No.1 source admission, fully offline; never deploy."""
from pathlib import Path
import sys,json,hashlib
import PIL
from PIL import Image
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.build_brief_cover import derive as hero
from scripts.build_catalogue_media import derive as card
from core.catalogue_media import sha256_file, load_admissions, resolve_catalogue_media
from core.source_terms import REQUIRED_NOTICES

ID="wei-fenghe-mattis-official-usarmy-2018"
ORIGINAL=ROOT/"docs/engineering/photo_review/no-01-wei-fenghe-2018-original.jpg"
PHOTO_SHA256="31f65b10bd45ae2ba70e09019f8f8164367ec1ddc7f03fb111b988ac35c07a51"
COMMONS_SHA1="a07e6f412425ca46c7b1a16a1474f57500e5d3fc"
SOURCE_URL="https://commons.wikimedia.org/wiki/File:2018-06-27_Beijing_Ministry_of_National_Defense.jpg"
SOURCE_URL2="https://www.flickr.com/photos/secdef/42160945785/"
EDITORIAL=ROOT/"site/assets/editorial"
MAN=EDITORIAL/"manifest.json"
ADM=ROOT/"site/assets/catalogue/admissions.json"
SOURCE=EDITORIAL/(ID+".jpg")
DERIV=EDITORIAL/"derivatives"/(ID+"-1600.jpg")
SERVED_ROUTE="assets/catalogue/media/no-01-"+ID+".jpg"
CARD=ROOT/"site"/SERVED_ROUTE
CAPTION=("Then-Chinese defence minister Wei Fenghe meets U.S. defence secretary James Mattis in Beijing, June 2018. "
         "This historical meeting does not depict the May 2026 verdict involving Wei Fenghe and Li Shangfu; "
         "Li Shangfu is not pictured.")
ALT="Then-Chinese defence minister Wei Fenghe meets U.S. defence secretary James Mattis in Beijing in June 2018."
CREATOR="Sgt. Amber I. Smith, U.S. Army"
NOTICE=next(x["notice"] for x in REQUIRED_NOTICES if x["publisher"]=="DVIDS")
assert "does not imply or constitute DoW endorsement" in NOTICE

def main():
    original=ORIGINAL.read_bytes()
    assert len(original)==3049499,len(original)
    assert hashlib.sha256(original).hexdigest()==PHOTO_SHA256
    assert hashlib.sha1(original).hexdigest()==COMMONS_SHA1
    with Image.open(ORIGINAL) as im:
        assert im.format=="JPEG" and im.size==(5880,3925)
        im.verify()
    a=json.loads(ADM.read_text(encoding="utf8"))
    manifest=json.loads(MAN.read_text(encoding="utf8"))
    old=next(x for x in a["entries"] if x["issue"]==1)
    assert old["status"]=="held" and "25 June 2012" in old["reason"]
    assert {x["issue"]:x["status"] for x in a["entries"] if x["issue"] in (10,12)}=={10:"held",12:"denied"}
    assert not any(x.get("id")==ID for x in manifest)
    SOURCE.write_bytes(original)
    blob,(w,h)=hero(SOURCE,1600,"jpg")
    DERIV.write_bytes(blob)
    CARD.parent.mkdir(parents=True,exist_ok=True)
    CARD.write_bytes(card(DERIV,"50% 47%"))
    assert Image.open(CARD).size==(720,480)
    shared=dict(
      alt=ALT,caption=CAPTION,
      date_note="June 2018. Wikimedia camera date June 27; supplied prose caption describes June 28. This image is not from 2026.",
      creator=CREATOR,creator_native="",creator_native_lang="",
      license="Public domain",license_url="",source_page=SOURCE_URL,source_label="Wikimedia Commons",
      credit=CREATOR+" · Public domain · via Wikimedia Commons",
      notice=NOTICE,depicts="context")
    manifest.append(dict(
      id=ID,file=SOURCE.name,width=5880,height=3925,sha256=sha256_file(SOURCE),
      original_url=SOURCE_URL,
      source_fingerprint=dict(sha1=COMMONS_SHA1,sha256=PHOTO_SHA256),
      origin_reference=SOURCE_URL2,
      license_basis=("Wikimedia Commons attributes photograph and EXIF to official-duty U.S. Army "
       "Sgt. Amber I. Smith; US government public-domain designation, and Flickr CC BY 2.0 "
       "publisher upload separately Commons-reviewed. Original is not DVIDS #4517865."),
      note="Actual named subject Wei Fenghe at June 2018 Mattis meeting; NOT Li Shangfu or 2026 verdict. "
           "Supersedes a disqualified separate 2012 source for catalogue only.",
      focal="50% 47%",match=dict(article_urls=[],categories=[],threads=[],editions=[],routes=[]),
      derivatives=[dict(file="derivatives/"+ID+"-1600.jpg",width=w,height=h,sha256=sha256_file(DERIV))],
      **shared))
    replaced=dict(
      issue=1,week_ending="2026-05-09",status="admitted",source_file="site/assets/editorial/derivatives/"+ID+"-1600.jpg",
      source_manifest_id=ID,focal="50% 47%",served=SERVED_ROUTE,
      width=720,height=480,source_sha256=sha256_file(DERIV),served_sha256=sha256_file(CARD),
      change_note="Cropped and resized by IPR.",
      review_note="14 Oct 2026 owner approved Wave10 verified new photographic source. "
                  "Original 2012 photo remains rejected; no change to opened-article art.",
      **shared)
    assert sum(x["issue"]==1 for x in a["entries"])==1
    a["entries"]=[replaced if x["issue"]==1 else x for x in a["entries"]]
    a["built_with"]={"pillow":PIL.__version__}
    MAN.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    ADM.write_text(json.dumps(a,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    m=resolve_catalogue_media(
      {"kind":"issue","entry":{"issue":1,"date":"2026-05-09"}},
      load_admissions(repo_root=ROOT),repo_root=ROOT)
    assert m.is_photograph,m.reason
    assert "Li Shangfu is not pictured" in m.photo["caption"]
    assert {x["issue"]:x["status"] for x in a["entries"] if x["issue"] in (10,12)}=={10:"held",12:"denied"}
    print("Wave11 new No1 source accepted in isolated branch, full photo checksum",PHOTO_SHA256,flush=True)

if __name__=="__main__":main()
