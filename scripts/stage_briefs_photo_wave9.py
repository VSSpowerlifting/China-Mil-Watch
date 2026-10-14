#!/usr/bin/env python3
"""TEMPORARY No5 Chinese CCG photo import. Research review ONLY, never publish.
Original USCG official-duty PD file pinned to Commons SHA1, original DVIDS terms.
Remove this script and its Action before PR release.
"""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode,urlsplit
import json,hashlib,io,sys
import PIL
from PIL import Image
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.build_brief_cover import derive as hero
from scripts.build_catalogue_media import derive as card
from core.catalogue_media import sha256_file,load_admissions,resolve_catalogue_media
from core.source_terms import required_notice

ID="chinese-coast-guard-2301-2018"
TITLE="File:USCGC Alex Haley transfers detained fishing vessel to China Coast Guard 2301 in Sea of Japan (5-6).jpg"
PAGE="https://commons.wikimedia.org/wiki/File:USCGC_Alex_Haley_transfers_detained_fishing_vessel_to_China_Coast_Guard_2301_in_Sea_of_Japan_(5-6).jpg"
DVIDS="https://www.dvidshub.net/image/4504032/uscgc-alex-haley-transfers-detained-fishing-vessel-prc-coast-guard-sea-japan"
SIZE=(5184,3456)
ED=ROOT/"site/assets/editorial"
MAN=ED/"manifest.json";ADM=ROOT/"site/assets/catalogue/admissions.json"
SOURCE=ED/(ID+".jpg")
DERIV=ED/"derivatives"/(ID+"-1600.jpg")
CARD_ROUTE="assets/catalogue/media/no-05-"+ID+".jpg"
CREATOR="Petty Officer 1st Class William Colclough, U.S. Coast Guard"
ALT="China Coast Guard patrol vessel 2301 alongside the U.S. Coast Guard cutter Alex Haley during a 2018 fisheries-enforcement handover in the Sea of Japan."
CAPTION=("Chinese Coast Guard patrol vessel 2301 during a 2018 fisheries-law-enforcement handover "
    "with the U.S. Coast Guard in the Sea of Japan. Historical maritime-enforcement context, "
    "not the June 2026 patrol east of Taiwan, loitering-munition discussion or Rocket Force training "
    "reported in this Brief.")
NOTICE=required_notice({"source_page":DVIDS,"source_label":"DVIDS"})
assert NOTICE and "does not imply or constitute DoW endorsement" in NOTICE
HEADERS={"User-Agent":"IndoPacificRecord-photo-provenance/1.0 (https://indopacificrecord.org)"}
def main():
    m=json.loads(MAN.read_text(encoding="utf8"))
    a=json.loads(ADM.read_text(encoding="utf8"))
    assert not any(x.get("id")==ID for x in m)
    assert not any(x.get("issue")==5 for x in a["entries"])
    args=urlencode({"action":"query","format":"json","prop":"imageinfo","iiprop":"sha1|size|url","titles":TITLE})
    req=Request("https://commons.wikimedia.org/w/api.php?"+args,headers=HEADERS)
    with urlopen(req,timeout=40) as response:
        info=next(iter(json.load(response)["query"]["pages"].values()))["imageinfo"][0]
    assert (info["width"],info["height"])==SIZE,(info["width"],info["height"])
    assert 4_000_000<=info["size"]<=5_500_000,info["size"]
    assert len(info["sha1"])==40,info["sha1"]
    url=info["url"]
    assert urlsplit(url).hostname=="upload.wikimedia.org",url
    with urlopen(Request(url,headers=HEADERS),timeout=60) as response:
        assert urlsplit(response.url).hostname=="upload.wikimedia.org"
        raw=response.read(6_000_001)
    assert len(raw)==info["size"],(len(raw),info["size"])
    assert hashlib.sha1(raw).hexdigest()==info["sha1"]
    with Image.open(io.BytesIO(raw)) as image:
        assert image.format=="JPEG" and image.size==SIZE,(image.format,image.size)
        image.verify()
    SOURCE.write_bytes(raw)
    blob,dimensions=hero(SOURCE,1600,"jpg")
    DERIV.write_bytes(blob)
    cardpath=ROOT/"site"/CARD_ROUTE
    cardpath.parent.mkdir(parents=True,exist_ok=True)
    cardpath.write_bytes(card(DERIV,"49% 52%"))
    common=dict(
        alt=ALT,caption=CAPTION,
        date_note="Photographed 21 June 2018 (EXIF 20 June 20:00 UTC), eight years before this Brief.",
        creator=CREATOR,creator_native="",creator_native_lang="",
        license="Public domain",license_url="",source_page=PAGE,source_label="Wikimedia Commons",
        credit=CREATOR+" · Public domain · via Wikimedia Commons",
        notice=NOTICE,depicts="context")
    m.append(dict(id=ID,file=SOURCE.name,width=SIZE[0],height=SIZE[1],
       sha256=sha256_file(SOURCE),original_url=url,
       source_fingerprint={"sha1":info["sha1"],"sha256":sha256_file(SOURCE)},
       origin_reference=DVIDS,
       license_basis="Official-duty USCG photograph DVIDS #4504032 (VIRIN 180621-G-G0217-1005), public domain. Publisher DVIDS non-endorsement notice retained despite Commons-hosted source.",
       note="Actual Chinese CCG patrol boat 2301 during 2018 Sea of Japan fisheries-enforcement handover. NOT 2026 East Taiwan patrol, loitering munitions or Rocket Force.",
       focal="49% 52%",match=dict(article_urls=[],categories=[],threads=[],editions=[],routes=[]),
       derivatives=[dict(file="derivatives/"+ID+"-1600.jpg",width=dimensions[0],height=dimensions[1],sha256=sha256_file(DERIV))],
       **common))
    a["entries"].append(dict(issue=5,week_ending="2026-06-06",status="admitted",
       source_file="site/assets/editorial/derivatives/"+ID+"-1600.jpg",
       source_manifest_id=ID,focal="49% 52%",served=CARD_ROUTE,
       source_sha256=sha256_file(DERIV),served_sha256=sha256_file(cardpath),
       width=720,height=480,change_note="Cropped and resized by IPR.",
       review_note="Candidate only: genuine Chinese CCG vessel but 2018 fisheries rather than 2026 East Taiwan, and only one of three No5 editorial topics. Owner must review.",
       **common))
    a["built_with"]={"pillow":PIL.__version__}
    MAN.write_text(json.dumps(m,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    ADM.write_text(json.dumps(a,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    got=resolve_catalogue_media({"kind":"issue","entry":{"issue":5,"date":"2026-06-06"}},
          load_admissions(repo_root=ROOT),repo_root=ROOT)
    assert got.is_photograph,got.reason
    hold={x["issue"]:x["status"] for x in a["entries"] if x["issue"] in (1,10,12)}
    assert hold=={1:"held",10:"held",12:"denied"},hold
    no7=next(x for x in a["entries"] if x["issue"]==7)
    no5=next(x for x in a["entries"] if x["issue"]==5)
    assert no7["source_page"]!=no5["source_page"]
    print("Source verified original SHA1",info["sha1"],"SHA256",sha256_file(SOURCE),flush=True)
if __name__=="__main__":main()
