#!/usr/bin/env python3
"""Temporary, one-shot No. 16 USINDOPACOM photographer-owned asset staging.
Never deploy. No external publisher copy or misleading Xiangshan representation.
Remove with its temporary workflow before preparing review PR.
"""
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
import hashlib,io,json,sys
import PIL
from PIL import Image
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.build_brief_cover import derive as hero
from scripts.build_catalogue_media import derive as card
from core.catalogue_media import sha256_file,load_admissions,resolve_catalogue_media
from core.source_terms import required_notice
ID="chan-paparo-mindef-jan2026"
PHOTO="https://d1ldvf68ux039x.cloudfront.net/thumbs/photos/2601/9490647/1000w_q95.jpg"
PAGE="https://www.dvidshub.net/image/9490647/usindopacom-commander-reinforces-us-singapore-defense-partnership-during-singapore-visit"
ED=ROOT/"site/assets/editorial"
MAN=ED/"manifest.json"
CAT=ROOT/"site/assets/catalogue/admissions.json"
SOURCE=ED/(ID+".jpg")
DERIVATIVE=ED/"derivatives"/(ID+"-1600.jpg")
CARD_ROUTE="assets/catalogue/media/no-16-"+ID+".jpg"
IMAGE_DATE="DVIDS date-taken field: 21 January 2026; descriptive caption: 22 January 2026."
ALT=("Singapore Defence Minister Chan Chun Sing and U.S. Indo-Pacific Command commander "
     "Adm. Samuel Paparo meet at Singapore's Ministry of Defence in January 2026.")
CAPTION=("Singapore Defence Minister Chan Chun Sing meets U.S. Indo-Pacific Command commander "
         "Adm. Samuel Paparo in Singapore, January 2026. This is an earlier U.S.–Singapore meeting, "
         "not the September 2026 Xiangshan Forum or Chan's meeting with Chinese Defence Minister Dong Jun.")
CREATOR="Staff Sgt. Angel Heraldez, U.S. Army"
NOTICE=required_notice({"source_page":PAGE,"source_label":"DVIDS"})
assert NOTICE
def main():
    manifest=json.loads(MAN.read_text(encoding="utf8"))
    admissions=json.loads(CAT.read_text(encoding="utf8"))
    assert not any(x["id"]==ID for x in manifest)
    assert not any(x["issue"]==16 for x in admissions["entries"])
    request=Request(PHOTO,headers={"User-Agent":"IndoPacificRecord-editorial-image-review/1.0 (https://indopacificrecord.org)"})
    with urlopen(request,timeout=50) as response:
        assert urlsplit(response.url).hostname=="d1ldvf68ux039x.cloudfront.net"
        raw=response.read(2_000_001)
    assert 40_000<len(raw)<2_000_000, len(raw)
    with Image.open(io.BytesIO(raw)) as im:
        assert im.format=="JPEG",im.format
        width,height=im.size
        assert 900<=width<=1000 and 540<=height<=800,(width,height)
        im.verify()
    SOURCE.write_bytes(raw)
    blob,size=hero(SOURCE,1600,"jpg")
    DERIVATIVE.write_bytes(blob)
    card_file=ROOT/"site"/CARD_ROUTE
    card_file.parent.mkdir(parents=True,exist_ok=True)
    card_file.write_bytes(card(DERIVATIVE,"48% 48%"))
    credit=CREATOR+" · Public domain · via DVIDS"
    shared={
      "alt":ALT,"caption":CAPTION,"date_note":IMAGE_DATE,
      "credit":credit,"creator":CREATOR,"creator_native":"","creator_native_lang":"",
      "license":"Public domain","license_url":"","source_label":"DVIDS","source_page":PAGE,
      "notice":NOTICE,"depicts":"context"
    }
    manifest.append({
       "id":ID,"file":SOURCE.name,"width":width,"height":height,
       "sha256":sha256_file(SOURCE),"original_url":PHOTO,
       "source_fingerprint":{"sha256":sha256_file(SOURCE),"sha1":hashlib.sha1(raw).hexdigest()},
       "origin_reference":PAGE,"focal":"48% 48%",
       "license_basis":"DVIDS No.9490647 (VIRIN 260121-A-GJ727-1132), official U.S. Army photographer public-domain photo; source is 1000w DVIDS preview, not original 4078x2713 file.",
       "note":"No.16 visualizes Chan Chun Sing as central speaker only; the event pictured is a DIFFERENT US-Singapore defense meeting, NOT Chan–Dong or Xiangshan.",
       "match":{"article_urls":[],"categories":[],"threads":[],"editions":[],"routes":[]},
       "derivatives":[{"file":"derivatives/"+ID+"-1600.jpg","width":size[0],"height":size[1],"sha256":sha256_file(DERIVATIVE)}],
       **shared
    })
    admissions["entries"].append({
       "issue":16,"week_ending":"2026-09-19","status":"admitted",
       "source_file":"site/assets/editorial/derivatives/"+ID+"-1600.jpg",
       "source_manifest_id":ID,"focal":"48% 48%","served":CARD_ROUTE,
       "source_sha256":sha256_file(DERIVATIVE),"served_sha256":sha256_file(card_file),
       "width":720,"height":480,"change_note":"Cropped and resized by IPR.",
       "review_note":"Staging only; owner must review relevance of 2026 US-Singapore meeting image for Xiangshan comparison article; no 2026 Xiangshan image rights inferred.",
       **shared
    })
    admissions["built_with"]={"pillow":PIL.__version__}
    MAN.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    CAT.write_text(json.dumps(admissions,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    resolved=resolve_catalogue_media({"kind":"brief","entry":{"issue":16,"date":"2026-09-19","slug":"xiangshan-security-frames-defense-ties"}},
                                   load_admissions(repo_root=ROOT),repo_root=ROOT)
    assert resolved.is_photograph,resolved.reason
    status={a["issue"]:a["status"] for a in admissions["entries"] if a["issue"] in (1,10,12)}
    assert status=={1:"held",10:"held",12:"denied"},status
    print("STAGED No.16 USINDOPACOM photo",width,height,sha256_file(SOURCE),flush=True)
if __name__=="__main__":main()
