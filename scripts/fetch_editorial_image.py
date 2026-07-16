"""
Guarded editorial-image fetcher for the China Mil Watch image manifest.

Downloads ONE named Wikimedia Commons file into the hand-maintained
editorial asset library at site/assets/editorial/, verifies its license
against the same conservative allowlist used by fetch_pla_watch_media.py
(public domain / CC0 / CC BY / CC BY-SA only — anything else is rejected),
optimizes it, and records a structured manifest entry with full provenance.

The manifest (site/assets/editorial/manifest.json) is the source of truth
for every editorial image the site may render. site/generator.py and the
weekly renderers select from it at build time; an image with no matching
entry for the current record simply does not render (text-led fallback).

This script never calls the Anthropic API, never touches pla_watch.db,
and never scrapes PRC sites. It only talks to commons.wikimedia.org and
writes inside site/assets/editorial/.

Usage:
    python scripts/fetch_editorial_image.py \
        --commons-title "File:Scarborough Shoal Landsat.jpg" \
        --id scarborough-shoal-landsat \
        --alt "Satellite view of Scarborough Shoal" \
        --caption "Scarborough Shoal (Huangyan Island) seen from orbit." \
        --edition 2026-07-04 --thread scarborough-shoal --route pw-post \
        [--article-url URL] [--category slug]... [--focal "50% 40%"] \
        [--display-label "Visual context"] [--dry-run]
"""

import argparse
import datetime as dt
import io
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.fetch_pla_watch_media import (  # noqa: E402
    USER_AGENT,
    HTTP_TIMEOUT,
    build_credit,
    commons_imageinfo,
    parse_candidate,
)

ASSET_DIR = ROOT / "site" / "assets" / "editorial"
MANIFEST = ASSET_DIR / "manifest.json"
MAX_WIDTH = 1600
JPEG_QUALITY = 82


def load_manifest() -> list:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return []


def save_manifest(entries: list) -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def fetch_and_optimize(url: str, out_path: Path) -> tuple:
    """Download, downscale to MAX_WIDTH, save optimized JPEG. Returns (w, h)."""
    from PIL import Image

    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT * 3)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content))
    if img.mode not in ("RGB",):
        img = img.convert("RGB")
    if img.width > MAX_WIDTH:
        ratio = MAX_WIDTH / img.width
        img = img.resize((MAX_WIDTH, round(img.height * ratio)), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    return img.width, img.height


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commons-title", required=True, help='e.g. "File:Foo.jpg"')
    ap.add_argument("--id", required=True, help="stable manifest id / filename stem")
    ap.add_argument("--alt", required=True)
    ap.add_argument("--caption", required=True)
    ap.add_argument("--display-label", default="Visual context")
    ap.add_argument("--article-url", action="append", default=[])
    ap.add_argument("--category", action="append", default=[])
    ap.add_argument("--thread", action="append", default=[])
    ap.add_argument("--edition", action="append", default=[])
    ap.add_argument("--route", action="append", default=[],
                    help="home | article | pw-post (repeatable)")
    ap.add_argument("--focal", default="50% 50%", help="CSS object-position")
    ap.add_argument("--note", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    info = commons_imageinfo([args.commons_title])
    ii = info.get(args.commons_title) or next(iter(info.values()), None)
    if not ii:
        print(f"REJECT: Commons returned no imageinfo for {args.commons_title}")
        return 1
    cand = parse_candidate(args.commons_title, ii)
    if not cand:
        print(f"REJECT: {args.commons_title} failed the license allowlist "
              "(only PD / CC0 / CC BY / CC BY-SA are accepted). Not downloaded.")
        return 1

    credit = build_credit(cand)
    print(f"license : {cand.get('license_label') or cand.get('license_short')}")
    print(f"credit  : {credit}")
    print(f"source  : {cand.get('description_url')}")
    print(f"original: {cand.get('width')}x{cand.get('height')}  {cand.get('url')}")

    if args.dry_run:
        print("dry-run: nothing written.")
        return 0

    out_file = ASSET_DIR / f"{args.id}.jpg"
    w, h = fetch_and_optimize(cand["url"], out_file)
    size_kb = out_file.stat().st_size // 1024
    print(f"saved   : {out_file.relative_to(ROOT)}  {w}x{h}  {size_kb} KB")

    entries = [e for e in load_manifest() if e.get("id") != args.id]
    entries.append({
        "id": args.id,
        "file": out_file.name,
        "width": w,
        "height": h,
        "alt": args.alt,
        "caption": args.caption,
        "display_label": args.display_label,
        "credit": credit,
        "creator": cand.get("artist") or "",
        "institution": cand.get("credit") or "",
        "license": cand.get("license_label") or cand.get("license_short") or "",
        "license_url": cand.get("license_url") or "",
        "source_page": cand.get("description_url") or "",
        "commons_title": args.commons_title,
        "original_url": cand.get("url") or "",
        "downloaded_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "focal": args.focal,
        "note": args.note,
        "match": {
            "article_urls": args.article_url,
            "categories": args.category,
            "threads": args.thread,
            "editions": args.edition,
            "routes": args.route or ["home"],
        },
    })
    entries.sort(key=lambda e: e["id"])
    save_manifest(entries)
    print(f"manifest: {MANIFEST.relative_to(ROOT)} ({len(entries)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
