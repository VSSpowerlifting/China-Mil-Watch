"""Verify decorative navy material's provenance, seams and delivery constraints."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from scripts.build_surface_material import build, prepare, MASTER_SHA, PAPER_SHA

ROOT = Path(__file__).resolve().parents[1]
MATERIAL = ROOT / 'site/assets/material'


class SurfaceMaterial(unittest.TestCase):
    def test_receipt_binds_source_chain_and_delivered_asset(self):
        receipt = json.loads((MATERIAL / 'NAVY_RECEIPT.json').read_text())
        source = (MATERIAL / 'chart-paper.png').read_bytes()
        source_receipt = (MATERIAL / 'ASSET_RECEIPT.json').read_bytes()
        data = (MATERIAL / 'navy-paper.png').read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), PAPER_SHA)
        self.assertEqual(receipt['source']['sha256'], PAPER_SHA)
        self.assertEqual(receipt['source']['receipt_sha256'], hashlib.sha256(source_receipt).hexdigest())
        self.assertEqual(receipt['source']['master']['sha256'], MASTER_SHA)
        self.assertEqual(receipt['asset']['sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(receipt['asset']['bytes'], len(data))
        self.assertLessEqual(len(data), 16000)

    def test_finished_material_is_seamless_low_contrast_and_small_to_decode(self):
        with Image.open(MATERIAL / 'navy-paper.png') as image:
            self.assertEqual(image.mode, 'P')
            self.assertEqual(image.size, (256, 256))
            self.assertLessEqual(image.width * image.height * 4, 262144)
            self.assertEqual(set(image.getdata()), set(range(8)))
            self.assertEqual(list(image.crop((0, 0, 1, 256)).getdata()), list(image.crop((255, 0, 256, 256)).getdata()))
            self.assertEqual(list(image.crop((0, 0, 256, 1)).getdata()), list(image.crop((0, 255, 256, 256)).getdata()))
            self.assertEqual(image.convert('RGB').getextrema(), ((16, 23), (42, 49), (52, 59)))
            with Image.open(MATERIAL / 'chart-paper.png') as source:
                self.assertEqual(list(image.getdata()), list(source.getdata()))

    def test_builder_reproduces_decoded_asset_and_provenance(self):
        # PNG IDAT deflate output is not stable across Pillow/zlib versions.
        # Requiring matching compressed bytes rejected CI's valid rebuild
        # even though the verified source indices and resulting navy pixels
        # did not change. Keep the checked-in asset's immutable SHA receipt
        # in test_receipt_binds_source_chain_and_delivered_asset above, and
        # compare actual indexed pixels/palette as well as metadata here.
        with tempfile.TemporaryDirectory() as directory:
            generated_receipt = build(directory)
            target = Path(directory)
            generated_bytes = (target / 'navy-paper.png').read_bytes()
            stored_bytes = (MATERIAL / 'navy-paper.png').read_bytes()
            generated_meta = json.loads(
                (target / 'NAVY_RECEIPT.json').read_text())
            stored_meta = json.loads(
                (MATERIAL / 'NAVY_RECEIPT.json').read_text())

            self.assertEqual(generated_receipt, generated_meta)
            self.assertEqual(generated_meta['source'], stored_meta['source'])
            for key in ('purpose', 'builder', 'method', 'palette_rgb',
                        'dimensions', 'decoded_rgba_bytes',
                        'delivery_cap_bytes'):
                self.assertEqual(generated_meta[key], stored_meta[key])
            self.assertEqual(generated_meta['asset']['path'], 'navy-paper.png')
            self.assertEqual(
                generated_meta['asset']['sha256'],
                hashlib.sha256(generated_bytes).hexdigest())
            self.assertEqual(
                generated_meta['asset']['bytes'], len(generated_bytes))
            self.assertLessEqual(len(generated_bytes), 16000)
            # Bytes can differ when the encoder uses different IDAT deflate
            # decisions, but the complete indexed artwork must not drift.
            with Image.open(target / 'navy-paper.png') as generated:
                with Image.open(MATERIAL / 'navy-paper.png') as delivered:
                    self.assertEqual(
                        (generated.format, generated.mode, generated.size),
                        (delivered.format, delivered.mode, delivered.size))
                    self.assertEqual(generated.tobytes(), delivered.tobytes())
                    self.assertEqual(generated.getpalette(),
                                     delivered.getpalette())
                    self.assertEqual(generated.convert('RGBA').tobytes(),
                                     delivered.convert('RGBA').tobytes())

    def test_changed_source_or_master_chain_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'paper.png'
            source.write_bytes((MATERIAL / 'chart-paper.png').read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'Paper digest changed'):
                prepare(source, MATERIAL / 'ASSET_RECEIPT.json')
            receipt = json.loads((MATERIAL / 'ASSET_RECEIPT.json').read_text())
            receipt['master']['sha256'] = '0' * 64
            receipt_path = Path(directory) / 'receipt.json'
            receipt_path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'Paper source chain changed'):
                prepare(MATERIAL / 'chart-paper.png', receipt_path)
