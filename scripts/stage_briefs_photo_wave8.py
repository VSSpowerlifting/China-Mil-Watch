#!/usr/bin/env python3
"""Temporary photo Wave8: actual historical PLA troops and actual CMC official.
Source reviewed at DVIDS. Catalogue-only; DO NOT publish or schedule.
Delete this script and workflow before preparing mergeable PR.
"""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit
import json,hashlib,io,sys
import PIL
from PIL import Image
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.build_brief_cover import derive as hero
from scripts.build_catalogue_media import derive as card
from core.catalogue_media import load_admissions,resolve_catalogue_media,sha256_file
from core.source_terms import required_notice
ED=ROOT/"site/assets/editorial"; MAN=ED/"manifest.json"; ADM=ROOT/"site/assets/catalogue/admissions.json"
PHOTOS=(
 dict(issue=3,week="2026-05-23",id="pla-disaster-exchange-hainan-2015",
      source="https://d1ldvf68ux039x.cloudfront.net/thumbs/photos/1501/1745480/1000w_q95.jpg",
      page="https://www.dvidshub.net/image/1745480/us-army-soldiers-work-with-pla-soldiers",
      original_resolution="3216x2136",creator="Maj. Lindsey Elder, U.S. Army Pacific",
      alt="Chinese PLA personnel and U.S. Army soldiers construct a simulated disaster-response camp in Hainan, China, in 2015.",
      caption="PLA and U.S. Army personnel set up an evacuation camp during a 2015 disaster-response field exercise in Hainan. Historical hands-on military training, not a photograph or assessment of May 2026 PLA institutional reforms.",
      date_note="Photographed 18 January 2015, not during the May 2026 reporting week.",
      focal="46% 52%",
      note="Public-domain U.S. Army image of Chinese PLA in 2015 hands-on training; NOT a picture of 2026 PLA implementation or reform."),
 dict(issue=4,week="2026-05-30",id="li-zuocheng-cmc-beijing-2019",
      source="https://d1ldvf68ux039x.cloudfront.net/thumbs/photos/1901/5031280/1000w_q95.jpg",
      page="https://www.dvidshub.net/image/5031280/cno-meets-with-chief-staff-joint-staff-department-under-chinas-central-military-commission-gen-li-zuocheng",
      original_resolution="4000x2662",creator="Chief Petty Officer Elliott Fabrizio, U.S. Navy",
      alt="General Li Zuocheng of China's Central Military Commission sits with Chinese military officers at a Beijing meeting in January 2019.",
      caption="Gen. Li Zuocheng, then chief of staff of China's CMC Joint Staff Department, at a Beijing meeting with U.S. naval leaders in January 2019. Historical CMC leadership context, not the May 2026 senior-officer directive or electronic-warfare incident.",
      date_note="Photographed 15 January 2019, seven years before this Brief's reporting period.",
      focal="60% 49%",
      note="Authentic named Chinese CMC Joint Staff chief in a 2019 U.S.-China meeting, NOT the 2026 oversight directive or claimed electronic jamming."),
)
HEADERS={"User-Agent":"IndoPacificRecord-photo-provenance/1.0 (https://indopacificrecord.org)"}

def main():
  manifest=json.loads(MAN.read_text(encoding="utf8"))
  admissions=json.loads(ADM.read_text(encoding="utf8"))
  for p in PHOTOS:
    assert not any(e.get("id")==p["id"] for e in manifest)
    assert not any(e.get("issue")==p["issue"] for e in admissions["entries"])
  for p in PHOTOS:
    with urlopen(Request(p["source"],headers=HEADERS),timeout=45) as resp:
      assert urlsplit(resp.url).hostname=="d1ldvf68ux039x.cloudfront.net"
      raw=resp.read(2_000_001)
    assert 40000<len(raw)<2_000_000
    with Image.open(io.BytesIO(raw)) as im:
      assert im.format=="JPEG",(p["issue"],im.format)
      w,h=im.size
      assert 970<=w<=1000 and 630<=h<=720,(p["issue"],w,h)
      im.verify()
    src=ED/(p["id"]+".jpg");src.write_bytes(raw)
    derived=ED/"derivatives"/(p["id"]+"-1600.jpg")
    data,dims=hero(src,1600,"jpg")
    derived.write_bytes(data)
    route="assets/catalogue/media/no-%02d-%s.jpg"%(p["issue"],p["id"])
    served=ROOT/"site"/route
    served.parent.mkdir(parents=True,exist_ok=True)
    served.write_bytes(card(derived,p["focal"]))
    notice=required_notice({"source_page":p["page"],"source_label":"DVIDS"})
    assert notice and "does not imply or constitute DoW endorsement" in notice
    common=dict(alt=p["alt"],caption=p["caption"],date_note=p["date_note"],
        creator=p["creator"],creator_native="",creator_native_lang="",
        license="Public domain",license_url="",source_label="DVIDS",source_page=p["page"],
        credit=p["creator"]+" · Public domain · via DVIDS",notice=notice,depicts="context")
    manifest.append(dict(id=p["id"],file=src.name,width=w,height=h,
       sha256=sha256_file(src),original_url=p["source"],origin_reference=p["page"],
       source_fingerprint={"sha1":hashlib.sha1(raw).hexdigest(),"sha256":sha256_file(src)},
       license_basis="U.S. Army/Navy official-duty public domain per original DVIDS photo; publisher 1000w JPEG preview, not "+p["original_resolution"]+" full image. DVIDS non-endorsement notice observed.",
       note=p["note"],focal=p["focal"],match={"article_urls":[],"categories":[],"threads":[],"editions":[],"routes":[]},
       derivatives=[dict(file="derivatives/"+p["id"]+"-1600.jpg",width=dims[0],height=dims[1],sha256=sha256_file(derived))],
       **common))
    admissions["entries"].append(dict(issue=p["issue"],week_ending=p["week"],status="admitted",
       source_file="site/assets/editorial/derivatives/"+p["id"]+"-1600.jpg",
       source_manifest_id=p["id"],focal=p["focal"],served=route,
       source_sha256=sha256_file(derived),served_sha256=sha256_file(served),width=720,height=480,
       change_note="Cropped and resized by IPR.",
       review_note="Wave8 historical institution/training photo proposal only; independent owner image/crop and relevance review required.",
       **common))
    print("STAGED issue",p["issue"],"preview",w,h,"original SHA256",sha256_file(src),flush=True)
  admissions["built_with"]={"pillow":PIL.__version__}
  MAN.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
  ADM.write_text(json.dumps(admissions,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
  loaded=load_admissions(repo_root=ROOT)
  for p in PHOTOS:
    hit=resolve_catalogue_media({"kind":"issue","entry":{"issue":p["issue"],"date":p["week"]}},
      loaded,repo_root=ROOT)
    assert hit.is_photograph,(p["issue"],hit.reason)
  assert {e["issue"]:e["status"] for e in admissions["entries"] if e["issue"] in (1,10,12)}=={1:"held",10:"held",12:"denied"}
  print("No3 and No4 photographic cards admitted to staging only.")
if __name__=="__main__": main()
