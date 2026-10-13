#!/usr/bin/env python3
"""One-time, fail-closed No. 18 contextual photo staging. Never publishes."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from PIL import Image
import PIL

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.build_brief_cover import derive as hero_derive, WIDTHS
from scripts.build_catalogue_media import derive as card_derive

PHOTO_ID = "laos-vientiane-museum-plane"
SLUG = "what-is-being-built-in-laos"
SOURCE_URL = ("https://upload.wikimedia.org/wikipedia/commons/8/8f/"
              "Plane_at_the_Lao_People%27s_Army_Historical_Museum_at_Vientiane%2C_Laos_09.jpg")
SOURCE_PAGE = ("https://commons.wikimedia.org/wiki/"
               "File:Plane_at_the_Lao_People%27s_Army_Historical_Museum_at_Vientiane,_Laos_09.jpg")
EDITORIAL = ROOT / "site/assets/editorial"
ORIGINAL = EDITORIAL / (PHOTO_ID + ".jpg")
MANIFEST = EDITORIAL / "manifest.json"
ADMISSIONS = ROOT / "site/assets/catalogue/admissions.json"
CARD = ROOT / "site/assets/catalogue/media/no-18-laos-vientiane-museum-plane.jpg"
ALT = ("A preserved olive-green propeller aircraft displayed under a roof at the "
       "Lao People's Army Historical Museum in Vientiane, Laos.")
CAPTION = ("A preserved aircraft at the Lao People's Army Historical Museum in "
           "Vientiane, photographed 15 July 2025. This historical context photograph "
           "does not depict Ban Keun Airport or any 2026 event described in the Brief.")
CREDIT = "Zongalez · CC BY 4.0 · via Wikimedia Commons"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0"
NOTE = "Cropped and resized by IPR."

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> None:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    catalogue = json.loads(ADMISSIONS.read_text(encoding="utf-8"))
    assert not any(e.get("id") == PHOTO_ID for e in entries), "already staged"
    assert not any(e.get("issue") == 18 for e in catalogue["entries"]), "No.18 already admitted"
    request = Request(SOURCE_URL, headers={"User-Agent": "IndoPacificRecord-image-provenance/1.0 (https://indopacificrecord.org)"})
    with urlopen(request, timeout=40) as resp:
        assert resp.url.startswith("https://upload.wikimedia.org/"), "redirected off Wikimedia"
        data = resp.read(5000000)
        assert len(data) > 2000000 and len(data) < 5000000, "image size unexpected"
    import io
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        assert image.format == "JPEG" and image.size == (2992, 2992), "source media changed"
    ORIGINAL.write_bytes(data)
    common = {
        "alt": ALT, "caption": CAPTION, "date_note": "Photographed 15 July 2025 (not during the reporting week).",
        "credit": CREDIT, "creator": "Zongalez", "license": "CC BY 4.0",
        "license_url": LICENSE_URL, "source_page": SOURCE_PAGE,
        "source_label": "Wikimedia Commons", "cover_treatment": "photograph",
        "depicts": "context",
    }
    record = {
        "id": PHOTO_ID, "file": ORIGINAL.name, "width": 2992, "height": 2992,
        **common, "sha256": digest(ORIGINAL), "original_url": SOURCE_URL,
        "license_basis": ("Wikimedia Commons: own work of uploader Zongalez, "
                          "CC BY 4.0; verified source description, author, 2025 date "
                          "and reuse conditions on 2026-10-13."),
        "note": ("Visual context for the Laos Brief only. The aircraft is a museum exhibit; "
                 "it is not a K-8, not an image of Ban Keun, and not 2026 event evidence."),
        "match": {"article_urls": [], "categories": [], "threads": [], "editions": [],
                  "routes": [], "briefs": [SLUG]},
        "derivative_builder": "scripts/build_brief_cover.py",
        "surfaces": ["article", "catalogue"], "focal": "50% 52%",
        "derivatives": [], "built_with": {"pillow": PIL.__version__},
    }
    for width, fmt in WIDTHS:
        blob, (w, h) = hero_derive(ORIGINAL, width, fmt)
        rel = f"derivatives/{PHOTO_ID}-{width}.{fmt}"
        target = EDITORIAL / rel
        target.write_bytes(blob)
        record["derivatives"].append({"file": rel, "width": w, "height": h,
                                       "sha256": digest(target)})
    entries.append(record)
    source_file = f"site/assets/editorial/derivatives/{PHOTO_ID}-1600.jpg"
    CARD.parent.mkdir(parents=True, exist_ok=True)
    CARD.write_bytes(card_derive(ROOT / source_file, "50% 52%"))
    admission = {
        "issue": 18, "week_ending": "2026-10-10", "status": "admitted",
        "source_file": source_file, "source_manifest_id": PHOTO_ID,
        "focal": "50% 52%", "served": "assets/catalogue/media/" + CARD.name,
        **common, "change_note": NOTE,
        "review_note": ("Owner accepted a non-event-specific Laos-context photograph "
                        "2026-10-13; the caption explicitly says the aircraft is a "
                        "2025 museum exhibit, not the Ban Keun 2026 training site. "
                        "No held Nos.1,10,12 photographs were admitted."),
        "source_sha256": digest(ROOT / source_file), "served_sha256": digest(CARD),
        "width": 720, "height": 480,
    }
    catalogue["entries"].append(admission)
    MANIFEST.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ADMISSIONS.write_text(json.dumps(catalogue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from core.brief_cover import problem
    from core.catalogue_media import load_admissions, resolve_catalogue_media
    from core.brief_photography import article_cover
    assert problem(record, ROOT) is None, problem(record, ROOT)
    sample = {"kind": "brief", "entry": {"issue":18,"date":"2026-10-10","slug":SLUG}}
    card = resolve_catalogue_media(sample, load_admissions(repo_root=ROOT), repo_root=ROOT)
    assert card.is_photograph, card.reason
    assert article_cover(sample["entry"], ROOT), "No.18 paired hero rejected"
    print("Validated No.18 local photo + article/catalogue hash gates", digest(ORIGINAL))

if __name__ == "__main__":
    main()
