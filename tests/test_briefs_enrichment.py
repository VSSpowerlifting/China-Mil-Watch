"""Guard the pilot's assets, source geometry and complete delivery accounting."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from PIL import Image
from core.frontend_budget import measure_page
from scripts.verify_frontend_delivery import verify

ROOT = Path(__file__).resolve().parents[1]


class MaterialIntegrity(unittest.TestCase):
    def test_material_receipt_and_seamless_edges(self):
        directory = ROOT / 'site/assets/material'
        receipt = json.loads((directory / 'ASSET_RECEIPT.json').read_text())
        for name, values in receipt['assets'].items():
            content = (directory / name).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), values['sha256'])
            self.assertEqual(len(content), values['bytes'])
        with Image.open(directory / 'chart-paper.png') as image:
            self.assertEqual(list(image.size), receipt['paper']['dimensions'])
            self.assertEqual(list(image.crop((0, 0, 1, image.height)).getdata()), list(image.crop((image.width - 1, 0, image.width, image.height)).getdata()))
            self.assertEqual(list(image.crop((0, 0, image.width, 1)).getdata()), list(image.crop((0, image.height - 1, image.width, image.height)).getdata()))
            # Detail survives optimization; neutral paper stays in a small range.
            self.assertGreater(len(set(image.getdata())), 2)
            extrema = image.convert('RGB').getextrema()
            self.assertTrue(all(high - low <= 7 for low, high in extrema))
        self.assertLess((directory / 'chart-paper.png').stat().st_size, 60000)

    def test_curves_are_original_and_no_operational_marks_are_added(self):
        from urllib.parse import unquote
        original = unquote((ROOT / 'site/preview/topography.css').read_text())
        for name in ('hero', 'paper'):
            svg = ET.parse(ROOT / ('site/assets/material/contours-%s.svg' % name))
            paths = list(svg.getroot().iter('{http://www.w3.org/2000/svg}path'))
            self.assertEqual(len(paths), 36)
            self.assertEqual(len(set(path.attrib['d'] for path in paths)), 12)
            for path in paths:
                self.assertIn(path.attrib['d'], original)
            self.assertEqual(set(e.tag.split('}')[-1] for e in svg.getroot().iter()), {'svg', 'g', 'path'})


class CompleteDelivery(unittest.TestCase):
    def test_every_committed_generated_route_meets_complete_budgets(self):
        result = verify(ROOT / 'output')
        self.assertGreater(result['routes_checked'], 7000)
        self.assertEqual(result['failures'], [])

    def test_fonts_css_graphics_srcset_icons_and_inline_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'css').mkdir()
            (root / 'index.html').write_text('<link rel="stylesheet" href="css/main.css"><link rel="icon" href="icon.png"><img src="small.png" srcset="small.png 320w, large.png 640w"><style>i{background:url(small.png)}</style>')
            (root / 'css/main.css').write_text('@import url(nested.css);i{background:url(../small.png)}')
            (root / 'css/nested.css').write_text('@font-face{src:url(../face.woff2)}')
            for name, size in [('small.png', 5), ('large.png', 9), ('face.woff2', 11), ('icon.png', 3)]:
                (root / name).write_bytes(b'x' * size)
            values = measure_page(root / 'index.html', root)
            self.assertEqual(values['asset_bytes'], 28)
            self.assertEqual(values['assets'], ['face.woff2', 'icon.png', 'large.png', 'small.png'])
            self.assertEqual(len(values['css']), 2)

    def test_missing_graphic_or_font_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text('<style>i{background:url(absent.png)}</style>')
            with self.assertRaises(ValueError): measure_page(root / 'index.html', root)

    def test_all_route_gate_catches_large_record_and_combined_scripts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'record').mkdir()
            (root / 'index.html').write_text('x' * 130000)
            (root / 'record/large.html').write_text('x' * 120001)
            (root / 'record/scripts.html').write_text('<script src="../a.js"></script><script src="../b.js"></script>')
            (root / 'a.js').write_text('x' * 6000); (root / 'b.js').write_text('x' * 6000)
            values = verify(root)
            self.assertEqual(values['routes_checked'], 3)
            self.assertEqual([v['route'] for v in values['failures']], ['record/large.html', 'record/scripts.html'])
