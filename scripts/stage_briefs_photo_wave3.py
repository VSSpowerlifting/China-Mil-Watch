#!/usr/bin/env python3
"""TEMPORARY Wave 3 source acquisition: No.7 USCG and No.13 NASA.
Not a production workflow. No Pages writes. Remove after guarded staging.
"""
from __future__ import annotations
import hashlib, io, json, sys
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from PIL import Image
import PIL
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.build_brief_cover import derive as hero
from scripts.build_catalogue_media import derive as card
from core.catalogue_media import sha256_file,load_admissions,resolve_catalogue_media
from core.source_terms import required_notice
ED=ROOT/"site/assets/editorial"
MAN=ED/"manifest.json"; CAT=ROOT/"site/assets/catalogue/admissions.json"
PHOTOS=[
  dict(
    id="ccg-shadowing-uscg-stratton-2019",issue=7,week="2026-06-20",
    source="https://d1ldvf68ux039x.cloudfront.net/thumbs/photos/1909/5771576/1000w_q95.jpg",
    hosts=("d1ldvf68ux039x.cloudfront.net",),
    dimensions=(1000,717),
    source_page="https://www.dvidshub.net/image/5771576/coast-guard-cutter-stratton-crew-conducts-operations-south-china-sea",
    source_label="DVIDS",license="Public domain",license_url="",
    creator="Petty Officer 1st Class Nate Littlejohn, U.S. Coast Guard",
    alt="A U.S. Coast Guard small boat moves across the South China Sea with a China Coast Guard vessel visible on the horizon.",
    caption="A China Coast Guard ship appears on the horizon as a U.S. Coast Guard crew operates in the South China Sea in September 2019. Historical Chinese coast guard context, not a photograph of June 2026 activity east of Taiwan.",
    date_note="Photographed 16 September 2019, in a different sea and year from this Brief's reporting week.",
    origin_note="DVIDS image 5771576, USCG 190916-G-LS819-1002. Source file is the publisher's 1000px JPEG derivative, not the 3996px camera original.",
    focal="50% 49%",
  ),
  dict(
    id="scarborough-shoal-nasa-iss77330",issue=13,week="2026-08-08",
    source="https://upload.wikimedia.org/wikipedia/commons/c/c7/ISS045-E-77330_-_View_of_Scarborough_Shoal.jpg",
    hosts=("upload.wikimedia.org",),
    dimensions=(4928,3280),
    commons_title="File:ISS045-E-77330 - View of Scarborough Shoal.jpg",
    source_page="https://commons.wikimedia.org/wiki/File:ISS045-E-77330_-_View_of_Scarborough_Shoal.jpg",
    source_label="Wikimedia Commons",license="Public domain",license_url="",
    creator="NASA Johnson Space Center / ISS Expedition 45",
    alt="Scarborough Shoal seen as a turquoise reef within dark ocean water from the International Space Station in 2015.",
    caption="Scarborough Shoal photographed from the International Space Station on 24 October 2015 (NASA frame ISS045-E-77330). Historical geographic context, not a depiction of PLA operations or disclosures in August 2026.",
    date_note="Photographed 24 October 2015; adjacent-but-distinct orbital frame from No. 9's existing NASA image.",
    origin_note="NASA frame ISS045-E-77330. Distinct original from already published No.9 frame ISS045-E-77332, though same orbital pass.",
    focal="50% 49%",
  )
]

UA={"User-Agent":"IndoPacificRecord-photo-source-review/1.0 (https://indopacificrecord.org)"}
def get(p):
    req=Request(p["source"],headers=UA)
    with urlopen(req,timeout=55) as rsp:
        assert urlsplit(rsp.url).hostname in p["hosts"],rsp.url
        raw=rsp.read(4_000_001)
    assert 20_000 < len(raw) < 4_000_000,len(raw)
    with Image.open(io.BytesIO(raw)) as im:
        assert im.format=="JPEG" and im.size==p["dimensions"],(im.format,im.size,p["dimensions"])
        im.verify()
    if "commons_title" in p:
        args=urlencode({"action":"query","format":"json","prop":"imageinfo","iiprop":"sha1|size|url","titles":p["commons_title"]})
        api=Request("https://commons.wikimedia.org/w/api.php?"+args,headers=UA)
        with urlopen(api,timeout=30) as rsp:
            data=json.load(rsp)
        pages=data["query"]["pages"]
        info=next(iter(pages.values()))["imageinfo"][0]
        assert info["sha1"]==hashlib.sha1(raw).hexdigest(),(info["sha1"],hashlib.sha1(raw).hexdigest())
        assert info["width"]==p["dimensions"][0] and info["height"]==p["dimensions"][1]
    return raw

def main():
    manifest=json.loads(MAN.read_text())
    admissions=json.loads(CAT.read_text())
    for p in PHOTOS:
        assert not any(e["id"]==p["id"] for e in manifest)
        assert not any(e["issue"]==p["issue"] for e in admissions["entries"])
    for p in PHOTOS:
        raw=get(p)
        src=ED/(p["id"]+".jpg");src.write_bytes(raw)
        rel="derivatives/"+p["id"]+"-1600.jpg"
        dest=ED/rel
        resized,shape=hero(src,1600,"jpg")
        dest.write_bytes(resized)
        card_route="assets/catalogue/media/no-%02d-%s.jpg"%(p["issue"],p["id"])
        cardfile=ROOT/"site"/card_route
        cardfile.parent.mkdir(parents=True,exist_ok=True)
        cardfile.write_bytes(card(dest,p["focal"]))
        notice=required_notice(p) or ""
        common=dict(alt=p["alt"],caption=p["caption"],date_note=p["date_note"],
                    creator=p["creator"],license=p["license"],license_url=p["license_url"],
                    credit=p["creator"]+" · "+p["license"]+" · via "+p["source_label"],
                    source_page=p["source_page"],source_label=p["source_label"],
                    creator_native="",creator_native_lang="",notice=notice,depicts="context")
        manifest.append(dict(id=p["id"],file=src.name,width=p["dimensions"][0],
                             height=p["dimensions"][1],sha256=sha256_file(src),
                             original_url=p["source"],source_fingerprint=dict(sha256=sha256_file(src),sha1=hashlib.sha1(raw).hexdigest()),
                             origin_reference=p["source_page"],origin_note=p["origin_note"],
                             focal=p["focal"],match=dict(article_urls=[],categories=[],threads=[],editions=[],routes=[]),
                             derivatives=[dict(file=rel,width=shape[0],height=shape[1],sha256=sha256_file(dest))],
                             **common))
        admissions["entries"].append(dict(issue=p["issue"],week_ending=p["week"],status="admitted",
             source_file="site/assets/editorial/"+rel,source_manifest_id=p["id"],served=card_route,
             focal=p["focal"],change_note="Cropped and resized by IPR.",source_sha256=sha256_file(dest),
             served_sha256=sha256_file(cardfile),width=720,height=480,
             review_note="Wave 3 staged historical photo, NOT owner photo-selection approval; no 2026 event pictured.",
             **common))
        print("STAGED",p["issue"],p["id"],"origin",sha256_file(src),"photo bytes",len(raw),flush=True)
    admissions["built_with"]={"pillow":PIL.__version__}
    MAN.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    CAT.write_text(json.dumps(admissions,indent=2,ensure_ascii=False)+"\n")
    resolved=load_admissions(repo_root=ROOT)
    for p in PHOTOS:
        row={"kind":"issue","entry":{"issue":p["issue"],"date":p["week"]}}
        got=resolve_catalogue_media(row,resolved,repo_root=ROOT)
        assert got.is_photograph,(p["issue"],got.reason)
    assert {e["issue"]:e["status"] for e in admissions["entries"] if e["issue"] in {1,10,12}}=={1:"held",10:"held",12:"denied"}
    print("Two source-verified historical cards staged; no legacy status promoted.",flush=True)
if __name__=="__main__":main()
