#!/usr/bin/env python3
"""One-time Wave 7 Commons ingestion; remove with its workflow before merging.
Only historic No11 catalogue photography; never publishes or edits articles.
"""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit, urlencode
import hashlib, io, json, sys
import PIL
from PIL import Image
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.build_brief_cover import derive as hero
from scripts.build_catalogue_media import derive as card
from core.catalogue_media import sha256_file,load_admissions,resolve_catalogue_media

ID="china-russia-iran-maritime-belt-2023"
TITLE="File:Arrival of Chinese and Russian ships for maritime security exercise (09).jpg"
PAGE="https://commons.wikimedia.org/wiki/File:Arrival_of_Chinese_and_Russian_ships_for_maritime_security_exercise_(09).jpg"
ORIGIN="https://www.mehrnews.com/photo/5734282/"
SHA1="324f2d3bfb165161e988cec274a2df2e7acd160c"
SIZE=(1280,853)
BYTES=216789
ED=ROOT/"site/assets/editorial"
MAN=ED/"manifest.json"
ADM=ROOT/"site/assets/catalogue/admissions.json"
SOURCE=ED/(ID+".jpg")
DERIV=ED/"derivatives"/(ID+"-1600.jpg")
ROUTE="assets/catalogue/media/no-11-"+ID+".jpg"
CREDIT="Mohsen Ranginkaman · CC BY 4.0 · via Wikimedia Commons"
ALT="Military ships arriving in the maritime exercise area during Maritime Security Belt 2023."
CAPTION=("Chinese and Russian naval vessels were photographed arriving for Maritime Security Belt 2023, "
         "a trilateral maritime exercise involving Iran. Historical March 2023 maritime-cooperation "
         "context; not the July 2026 Joint Sea exercise, naval patrol or Y-20B flight in this Brief.")
HEADERS={"User-Agent":"IndoPacificRecord-photo-review/1.0 (https://indopacificrecord.org)"}
def main():
    m=json.loads(MAN.read_text(encoding="utf8"))
    a=json.loads(ADM.read_text(encoding="utf8"))
    assert all(x.get("id")!=ID for x in m)
    assert all(x.get("issue")!=11 for x in a["entries"])
    args=urlencode({"action":"query","format":"json","prop":"imageinfo","iiprop":"sha1|size|url","titles":TITLE})
    req=Request("https://commons.wikimedia.org/w/api.php?"+args,headers=HEADERS)
    with urlopen(req,timeout=45) as response:
        j=json.load(response)
    info=next(iter(j["query"]["pages"].values()))["imageinfo"][0]
    assert (info["sha1"],info["width"],info["height"],info["size"])==(SHA1,*SIZE,BYTES),info
    url=info["url"]
    assert urlsplit(url).hostname=="upload.wikimedia.org",url
    with urlopen(Request(url,headers=HEADERS),timeout=45) as response:
        assert urlsplit(response.url).hostname=="upload.wikimedia.org"
        raw=response.read(1_000_000)
    assert len(raw)==BYTES,len(raw)
    assert hashlib.sha1(raw).hexdigest()==SHA1
    with Image.open(io.BytesIO(raw)) as image:
        assert image.format=="JPEG" and image.size==SIZE,(image.format,image.size)
        image.verify()
    SOURCE.write_bytes(raw)
    derivative,dims=hero(SOURCE,1600,"jpg")
    DERIV.write_bytes(derivative)
    served=ROOT/"site"/ROUTE
    served.parent.mkdir(parents=True,exist_ok=True)
    served.write_bytes(card(DERIV,"50% 50%"))
    shared={
      "alt":ALT,"caption":CAPTION,
      "date_note":"Photographed 15 March 2023 in a different exercise involving Iran, China and Russia.",
      "creator":"Mohsen Ranginkaman","creator_native":"","creator_native_lang":"",
      "credit":CREDIT,"license":"CC BY 4.0",
      "license_url":"https://creativecommons.org/licenses/by/4.0",
      "source_page":PAGE,"source_label":"Wikimedia Commons",
      "notice":"","depicts":"context"
    }
    m.append({"id":ID,"file":SOURCE.name,"width":SIZE[0],"height":SIZE[1],
      "sha256":sha256_file(SOURCE),"original_url":url,
      "source_fingerprint":{"sha1":SHA1,"sha256":sha256_file(SOURCE)},
      "origin_reference":ORIGIN,
      "license_basis":"Mehr News Agency CC BY 4.0 publisher footer; Commons source reviewer POS78 confirmed on 5 May 2024.",
      "note":"2023 trilateral Iran-China-Russia naval arrival, NOT 2026 Joint Sea or Y-20B. Exact individual hull identities in frame not independently proved.",
      "focal":"50% 50%",
      "match":{"article_urls":[],"categories":[],"threads":[],"editions":[],"routes":[]},
      "derivatives":[{"file":"derivatives/"+ID+"-1600.jpg","width":dims[0],"height":dims[1],"sha256":sha256_file(DERIV)}],
      **shared})
    a["entries"].append({"issue":11,"week_ending":"2026-07-18","status":"admitted",
      "source_file":"site/assets/editorial/derivatives/"+ID+"-1600.jpg",
      "source_manifest_id":ID,"focal":"50% 50%","served":ROUTE,
      "source_sha256":sha256_file(DERIV),"served_sha256":sha256_file(served),
      "width":720,"height":480,"change_note":"Cropped and resized by IPR.",
      "review_note":"Historical 2023 trilateral maritime exercise contextual to China-Russia maritime cooperation. Owner approval of image relevance/crop required.",
      **shared})
    a["built_with"]={"pillow":PIL.__version__}
    MAN.write_text(json.dumps(m,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    ADM.write_text(json.dumps(a,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    resolved=resolve_catalogue_media({"kind":"issue","entry":{"issue":11,"date":"2026-07-18"}},
            load_admissions(repo_root=ROOT),repo_root=ROOT)
    assert resolved.is_photograph,resolved.reason
    assert {x["issue"]:x["status"] for x in a["entries"] if x["issue"] in (1,10,12)}=={1:"held",10:"held",12:"denied"}
    print("Staged historic No.11 photo with checksum verified",sha256_file(SOURCE),flush=True)
if __name__=="__main__":main()
