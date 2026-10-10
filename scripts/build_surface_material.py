#!/usr/bin/env python3
"""Derive owned navy grain from the verified Briefs paper tile, not photographs.

Usage: .venv/bin/python scripts/build_surface_material.py
The production renderer copies the result; it does not run this preparation step.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MATERIAL = ROOT / 'site/assets/material'
PAPER_SHA = '7011fdf20fe6955e1886d326f27c62d48f08af03f09a68b85562c70b69052daf'
MASTER_SHA = '61002883e45fd8418f5544a2fd27656cef2c656c1566c0b1def250953879c672'
NAVY = (20, 46, 56)  # Existing analytical band, #142E38.


def prepare(source, source_receipt):
    """Return deterministic indexed PNG bytes and their complete source receipt."""
    data = Path(source).read_bytes()
    receipt_data = Path(source_receipt).read_bytes()
    receipt = json.loads(receipt_data)
    if hashlib.sha256(data).hexdigest() != PAPER_SHA:
        raise ValueError('Paper digest changed; review provenance before replacement')
    if (receipt['assets']['chart-paper.png']['sha256'] != PAPER_SHA
            or receipt['master']['sha256'] != MASTER_SHA):
        raise ValueError('Paper source chain changed; review before replacement')
    with Image.open(io.BytesIO(data)) as source_image:
        if source_image.mode != 'P' or source_image.size != (256, 256):
            raise ValueError('Expected the verified 256px indexed paper tile')
        indices = list(source_image.getdata())
    if set(indices) != set(range(8)):
        raise ValueError('Expected exactly eight paper palette indices')
    # Keep the verified tile's pixel topology exactly. Only its decorative
    # palette changes: eight RGB steps around the existing analytical band.
    navy = Image.new('P', (256, 256))
    navy.putdata(indices)
    palette = [[channel + index - 4 for channel in NAVY] for index in range(8)]
    navy.putpalette(sum(palette, []) + palette[-1] * 248)
    buffer = io.BytesIO()
    navy.save(buffer, format='PNG', optimize=True)
    result = buffer.getvalue()
    if len(result) > 16000:
        raise ValueError('Navy material exceeds its 16,000 byte delivery cap')
    metadata = {
        'purpose': 'Generated abstract navy material; no evidence, geography or documentary imagery',
        'builder': 'scripts/build_surface_material.py',
        'source': {
            'path': 'site/assets/material/chart-paper.png',
            'sha256': PAPER_SHA, 'bytes': len(data),
            'receipt': 'site/assets/material/ASSET_RECEIPT.json',
            'receipt_sha256': hashlib.sha256(receipt_data).hexdigest(),
            'master': receipt['master'],
        },
        'method': 'Preserve verified seamless tile indices; replace eight paper tones with eight navy RGB tones around #142E38',
        'palette_rgb': palette,
        'dimensions': [256, 256],
        'decoded_rgba_bytes': 262144,
        'delivery_cap_bytes': 16000,
        'asset': {
            'path': 'navy-paper.png', 'bytes': len(result),
            'sha256': hashlib.sha256(result).hexdigest(),
        },
    }
    return result, metadata


def build(out=MATERIAL):
    data, receipt = prepare(MATERIAL / 'chart-paper.png', MATERIAL / 'ASSET_RECEIPT.json')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'navy-paper.png').write_bytes(data)
    (out / 'NAVY_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=MATERIAL)
    print(json.dumps(build(parser.parse_args().out), indent=2))
