#!/usr/bin/env python3
"""Temporary branch-only repair: change No.6 to a *different* MOD observation frame.
Verify exact Commons original SHA-1. Never publish. Delete this after staging.
"""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
import hashlib, io, json, sys, PIL
from PIL import Image
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.build_brief_cover import derive as hero_derive
from scripts.build_catalogue_media import derive as card_derive
from core.catalogue_media import sha256_file,load_admissions,resolve_catalogue_media
ED=ROOT/"site/assets/editorial"
MAN=ED/"manifest.json"; CAT=ROOT/"site/assets/catalogue/admissions.json"
TITLE="A_PLAN_Shenyang_J-15_carrier-based_fighter_aircraft_is_taking_off_from_Chinese_aircraft_carrier_PLANS_Liaoning_%28CV-16%29_20220504.jpg"
URL="https://upload.wikimedia.org/wikipedia/commons/b/b7/"+TITLE
PAGE="https://commons.wikimedia.org/wiki/File:A_PLAN_Shenyang_J-15_carrier-based_fighter_aircraft_is_taking_off_from_Chinese_aircraft_carrier_PLANS_Liaoning_(CV-16)_20220504.jpg"
SHA1="abb48c8d4996558b97d3308e700a90318de69c14"
ID="liaoning-j15-may2022"
def main():
    manifest=json.loads(MAN.read_text())
    data=json.loads(CAT.read_text())
    entry=next(x for x in manifest if x.get("id")==ID)
    adm=next(x for x in data["entries"] if x.get("issue")==6)
    other=next(x for x in data["entries"] if x.get("issue")==8)
    assert other["source_page"]!=PAGE and entry["source_page"]!=PAGE
    req=Request(URL,headers={"User-Agent":"IndoPacificRecord-image-provenance/1.0 (https://indopacificrecord.org)"})
    with urlopen(req,timeout=60) as resp:
        assert urlsplit(resp.url).netloc=="upload.wikimedia.org"
        raw=resp.read(3_000_001)
    assert 500000<len(raw)<3_000_000
    assert hashlib.sha1(raw).hexdigest()==SHA1
    with Image.open(io.BytesIO(raw)) as im:
        assert im.format=="JPEG" and im.size==(3898,2476), (im.format,im.size)
        im.verify()
    source=ED/(ID+".jpg")
    source.write_bytes(raw)
    derivative=ED/"derivatives"/(ID+"-1600.jpg")
    blob,size=hero_derive(source,1600,"jpg")
    derivative.write_bytes(blob)
    served=ROOT/"site/assets/catalogue/media/no-06-liaoning-j15-may2022.jpg"
    served.write_bytes(card_derive(derivative,"50% 50%"))
    alt="A Chinese J-15 fighter taking off beside the bow of the aircraft carrier Liaoning at sea in 2022."
    caption=("A J-15 launches near the carrier Liaoning in Japanese Ministry of Defense imagery published May 2022. "
             "Historical carrier context, not the June 2026 operation described in this Brief.")
    date_note="Publisher image released 4 May 2022; the accompanying report describes observations on 3 May 2022. Not photographed during the 2026 reporting week."
    for row in (entry,adm):
        row.update(source_page=PAGE,alt=alt,caption=caption,date_note=date_note)
    entry.update(width=3898,height=2476,sha256=sha256_file(source),original_url=URL,
                 license_basis="Exact Commons original SHA-1 "+SHA1+"; Japanese MOD Joint Staff original, CC BY 4.0; verified 2026-10-13",
                 note="Distinct 2022 carrier-based J-15 takeoff view, NOT the landing-approach photograph already used on Brief No.8. Context only.",
                 derivatives=[{"file":"derivatives/"+ID+"-1600.jpg","width":size[0],"height":size[1],"sha256":sha256_file(derivative)}])
    adm.update(source_sha256=sha256_file(derivative),served_sha256=sha256_file(served),
               review_note="Wave 2 distinct-source correction: J-15 takeoff image is separate from No.8's approach image. Historical context only. Owner selection review required.")
    assert entry["sha256"] != next(x for x in manifest if x["id"]=="liaoning-j15-recovery").get("sha256")
    MAN.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    CAT.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n")
    output=resolve_catalogue_media({"kind":"issue","entry":{"issue":6,"date":"2026-06-13"}},load_admissions(repo_root=ROOT),repo_root=ROOT)
    assert output.is_photograph, output.reason
    print("STAGED distinct No.6 source",SHA1,"SHA256",sha256_file(source),"Pillow",PIL.__version__)
if __name__=="__main__":
    main()
