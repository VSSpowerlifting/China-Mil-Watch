#!/usr/bin/env python3
"""Temporary, review-only, checksum-pinned No.1 photo acquisition. No publication."""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlsplit
import hashlib, io, json, sys
from PIL import Image
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.build_catalogue_media import derive
TITLE = "File:2018-06-27 Beijing Ministry of National Defense.jpg"
EXPECT_SHA1 = "a07e6f412425ca46c7b1a16a1474f57500e5d3fc"
EXPECT_SIZE = 3049499
EXPECT_PIXELS = (5880, 3925)
FOLDER = ROOT / "docs" / "engineering" / "photo_review"
SOURCE = FOLDER / "no-01-wei-fenghe-2018-original.jpg"
CARD = FOLDER / "no-01-wei-fenghe-2018-card.jpg"
DOC = ROOT / "docs" / "engineering" / "BRIEFS_PHOTO_WAVE10_NO01_WEI_REVIEW_2026-10-14.md"
HEADERS = {"User-Agent": "IndoPacificRecord-cover-source-review/1.0 (https://indopacificrecord.org)"}

def sha256(data): return hashlib.sha256(data).hexdigest()

def main():
    root_admissions = ROOT / "site" / "assets" / "catalogue" / "admissions.json"
    state_before = root_admissions.read_bytes()
    data = json.loads(state_before)
    assert {e["issue"]: e["status"] for e in data["entries"] if e["issue"] in (1,10,12)} == {
        1:"held", 10:"held", 12:"denied"
    }
    query = urlencode({"action":"query","format":"json","prop":"imageinfo",
                      "iiprop":"sha1|size|url","titles":TITLE})
    request = Request("https://commons.wikimedia.org/w/api.php?"+query, headers=HEADERS)
    with urlopen(request,timeout=50) as response:
        info=next(iter(json.load(response)["query"]["pages"].values()))["imageinfo"][0]
    assert info["sha1"] == EXPECT_SHA1, info
    assert info["size"] == EXPECT_SIZE, info
    assert (info["width"],info["height"]) == EXPECT_PIXELS, info
    url=info["url"]
    assert urlsplit(url).scheme=="https" and urlsplit(url).hostname=="upload.wikimedia.org",url
    with urlopen(Request(url,headers=HEADERS),timeout=90) as response:
        assert urlsplit(response.url).hostname=="upload.wikimedia.org",response.url
        blob=response.read(EXPECT_SIZE+1)
    assert len(blob)==EXPECT_SIZE,len(blob)
    assert hashlib.sha1(blob).hexdigest() == EXPECT_SHA1
    with Image.open(io.BytesIO(blob)) as im:
        assert im.format=="JPEG" and im.size==EXPECT_PIXELS,(im.format,im.size)
        im.verify()
    FOLDER.mkdir(parents=True,exist_ok=True)
    SOURCE.write_bytes(blob)
    card=derive(SOURCE,"50% 47%")
    CARD.write_bytes(card)
    with Image.open(CARD) as im:
        assert im.format=="JPEG" and im.size==(720,480)
    summary=(
       "- Original: \`docs/engineering/photo_review/no-01-wei-fenghe-2018-original.jpg\` "
       "SHA-256 \`"+sha256(blob)+"\`.\n"
       "- Candidate card: \`docs/engineering/photo_review/no-01-wei-fenghe-2018-card.jpg\` "
       "SHA-256 \`"+sha256(card)+"\`, 720 × 480; **not admitted or published**.\n"
       "- Commons SHA-1 \`"+EXPECT_SHA1+"\`; full-sized original verified against "
       "live MediaWiki imageinfo and exact downloaded bytes.\n"
    )
    t=DOC.read_text(encoding="utf-8")
    assert t.count("%%HASHES%%")==1
    DOC.write_text(t.replace("%%HASHES%%",summary),encoding="utf-8")
    assert root_admissions.read_bytes()==state_before,"Admission mutated"
    assert not (ROOT / "site/assets/catalogue/media/no-01-wei-fenghe-2018-card.jpg").exists()
    print("Review-only acquisition completed. Original SHA256",sha256(blob),
          "Card SHA256",sha256(card),flush=True)
if __name__=="__main__": main()
