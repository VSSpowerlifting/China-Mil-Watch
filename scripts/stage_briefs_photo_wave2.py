#!/usr/bin/env python3
"""ONE-TIME network acquisition for two Commons photographs. STAGING ONLY.

Never publish or run from a scheduled workflow. A temporary branch-only Action
uses this to create reviewed originals, 1600px derivatives and 720x480 cards.
Every incoming Commons file is bound to the expected SHA-1 from structured
data, dimensions, media type, source host, and exact provenance record.
Delete this script and the temporary Action before any production merge.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import PIL
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.build_brief_cover import derive as make_hero_source
from scripts.build_catalogue_media import derive as make_catalogue_card
from core.catalogue_media import load_admissions, resolve_catalogue_media, sha256_file

EDITORIAL = ROOT / "site/assets/editorial"
MANIFEST = EDITORIAL / "manifest.json"
ADMISSIONS = ROOT / "site/assets/catalogue/admissions.json"

PHOTOS = (
    {
        "issue": 14,
        "week": "2026-08-15",
        "id": "rimpac-china-indonesia-2016",
        "source_url": "https://upload.wikimedia.org/wikipedia/commons/2/29/RIMPAC_CTF_175_maneuvering_drills_160713-N-OL837-175.jpg",
        "source_sha1": "a940d524243faa619a04a86007858dbe27a482d4",
        "size": (2846, 1897),
        "source_page": "https://commons.wikimedia.org/wiki/File:RIMPAC_CTF_175_maneuvering_drills_160713-N-OL837-175.jpg",
        "origin": "https://www.dvidshub.net/image/2736121/rimpac-ctf-175-maneuvering-drills",
        "creator": "U.S. Navy / Petty Officer 1st Class Jason Noble",
        "license": "Public domain",
        "license_url": "",
        "focal": "50% 50%",
        "alt": "Chinese and Indonesian Navy warships among four vessels in formation at RIMPAC in the Pacific Ocean in July 2016.",
        "caption": "Chinese and Indonesian naval vessels sail in a four-ship formation at RIMPAC 2016. Historical photograph from July 2016, not the 2026 China–Indonesia exercise east of Taiwan.",
        "date_note": "Photographed 13 July 2016, ten years before this Brief's reporting week.",
        "notes": "2016 China–Indonesia multinational naval context, not a depiction of the August 2026 events; includes a French ship as well.",
    },
    {
        "issue": 6,
        "week": "2026-06-13",
        "id": "liaoning-j15-may2022",
        "source_url": "https://upload.wikimedia.org/wikipedia/commons/d/d1/A_PLAN_Shenyang_J-15_carrier-based_fighter_aircraft_is_preparing_to_land_on_Chinese_aircraft_carrier_PLANS_Liaoning_%28CV-16%29_20220504.jpg",
        "source_sha1": "36ed8a492fda1f2b38f40926ae0d049fa68dbfa4",
        "size": (2072, 1240),
        "source_page": "https://commons.wikimedia.org/wiki/File:A_PLAN_Shenyang_J-15_carrier-based_fighter_aircraft_is_preparing_to_land_on_Chinese_aircraft_carrier_PLANS_Liaoning_(CV-16)_20220504.jpg",
        "origin": "https://www.mod.go.jp/js/Press/press2022/press_pdf/p20220504_01.pdf",
        "creator": "Japan Ministry of Defense, Joint Staff",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0",
        "focal": "50% 50%",
        "alt": "The aircraft carrier Liaoning photographed from the side at sea, with a J-15 fighter approaching to land.",
        "caption": "The Liaoning carrier and a J-15 during Japanese Ministry of Defense observation in May 2022. Historical carrier context, not the June 2026 operation described in this Brief.",
        "date_note": "Photographed 4 May 2022, not during the June 2026 reporting week.",
        "notes": "Liaoning-specific historical context; independently different from issue No. 8's existing J-15 photograph.",
    },
)


def fetch_verified(item: dict) -> bytes:
    url = item["source_url"]
    assert urlsplit(url).netloc == "upload.wikimedia.org"
    req = Request(url, headers={"User-Agent": "IndoPacificRecord-image-provenance/1.0 (https://indopacificrecord.org)"})
    with urlopen(req, timeout=50) as response:
        assert urlsplit(response.url).netloc == "upload.wikimedia.org", "unexpected image redirect"
        raw = response.read(4_000_001)
    assert 15_000 < len(raw) < 4_000_000, "unexpected source size"
    assert hashlib.sha1(raw).hexdigest() == item["source_sha1"], "Commons original SHA-1 changed"
    with Image.open(io.BytesIO(raw)) as image:
        assert image.format == "JPEG" and image.size == item["size"], "source subject/dimensions changed"
        image.verify()
    return raw


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    data = json.loads(ADMISSIONS.read_text(encoding="utf-8"))
    existing_ids = {entry.get("id") for entry in manifest}
    existing_issues = {entry.get("issue") for entry in data["entries"]}
    # Fail closed before downloading anything if a branch replay would duplicate an image.
    for p in PHOTOS:
        assert p["id"] not in existing_ids and p["issue"] not in existing_issues, p["id"]
    for p in PHOTOS:
        raw = fetch_verified(p)
        id_ = p["id"]
        source = EDITORIAL / (id_ + ".jpg")
        source.write_bytes(raw)
        rel_derivative = "derivatives/" + id_ + "-1600.jpg"
        derivative = EDITORIAL / rel_derivative
        blob, dims = make_hero_source(source, 1600, "jpg")
        derivative.write_bytes(blob)
        card_route = "assets/catalogue/media/no-%02d-%s.jpg" % (p["issue"], id_)
        card = ROOT / "site" / card_route
        card.parent.mkdir(parents=True, exist_ok=True)
        card.write_bytes(make_catalogue_card(derivative, p["focal"]))
        credit = p["creator"] + " · " + p["license"] + " · via Wikimedia Commons"
        shared = {
            "alt": p["alt"], "caption": p["caption"], "date_note": p["date_note"],
            "creator": p["creator"], "license": p["license"],
            "license_url": p["license_url"], "credit": credit,
            "source_page": p["source_page"], "source_label": "Wikimedia Commons",
            "depicts": "context",
        }
        manifest.append({
            "id": id_, "file": source.name, "width": p["size"][0], "height": p["size"][1],
            **shared, "sha256": sha256_file(source), "original_url": p["source_url"],
            "license_basis": "Verified Commons original SHA-1 " + p["source_sha1"] +
                             "; issuing authority in linked source; image license checked 2026-10-13",
            "origin_reference": p["origin"], "note": p["notes"],
            "focal": p["focal"], "match": {
                "article_urls": [], "categories": [], "threads": [], "editions": [], "routes": []
            },
            "derivatives": [{"file": rel_derivative, "width": dims[0], "height": dims[1],
                             "sha256": sha256_file(derivative)}],
        })
        data["entries"].append({
            "issue": p["issue"], "week_ending": p["week"], "status": "admitted",
            "source_file": "site/assets/editorial/" + rel_derivative,
            "source_manifest_id": id_, "focal": p["focal"], "served": card_route,
            **shared, "creator_native": "", "creator_native_lang": "",
            "change_note": "Cropped and resized by IPR.",
            "review_note": "Proposed Wave 2 catalogue-only historical-context photograph. Requires owner visual acceptance before PR merge; historical article hero unchanged.",
            "source_sha256": sha256_file(derivative), "served_sha256": sha256_file(card),
            "width": 720, "height": 480,
        })
        print("STAGED only", p["issue"], id_, "original", sha256_file(source), flush=True)
    data["built_with"] = {"pillow": PIL.__version__}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ADMISSIONS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    admissions = load_admissions(repo_root=ROOT)
    for p in PHOTOS:
        row = {"kind": "issue", "entry": {"issue": p["issue"], "date": p["week"]}}
        resolved = resolve_catalogue_media(row, admissions, repo_root=ROOT)
        assert resolved.is_photograph, (p["issue"], resolved.reason)
    assert next(e for e in data["entries"] if e["issue"] == 1)["status"] == "held"
    assert next(e for e in data["entries"] if e["issue"] == 10)["status"] == "held"
    assert next(e for e in data["entries"] if e["issue"] == 12)["status"] == "denied"
    print("Validated both hash-gated catalogue photographs; other issues untouched.")


if __name__ == "__main__":
    main()
