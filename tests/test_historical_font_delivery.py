"""Historical faces retain immutable source bytes and complete local delivery."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HistoricalFontIntegrity(unittest.TestCase):
    def test_original_faces_and_licenses_match_the_provenance_receipt(self):
        directory = ROOT / 'site/assets/fonts/historical'
        receipt = json.loads((directory / 'RECEIPT.json').read_text())
        self.assertEqual({f['family'] for f in receipt['fonts']}, {'Inter', 'Source Serif 4', 'IBM Plex Mono'})
        self.assertEqual(len(receipt['fonts']), 18)
        for face in receipt['fonts']:
            with self.subTest(file=face['file']):
                data = (directory / face['file']).read_bytes()
                self.assertEqual(data[:4], b'wOF2')
                self.assertEqual(len(data), face['bytes'])
                self.assertEqual(hashlib.sha256(data).hexdigest(), face['sha256'])
                self.assertEqual(face['binary_treatment'], 'Original Google WOFF2 bytes, unchanged')
                self.assertTrue(face['source'].startswith('https://fonts.gstatic.com/'))
        self.assertEqual(sum(f['bytes'] for f in receipt['fonts']), receipt['total_font_bytes'])
        for license in directory.glob('*-OFL.txt'):
            self.assertIn('SIL OPEN FONT LICENSE', license.read_text())
        self.assertEqual(len(list(directory.glob('*-OFL.txt'))), 3)

    def test_linked_css_is_compact_local_and_uses_the_same_axes(self):
        receipt = json.loads((ROOT / 'site/assets/fonts/historical/RECEIPT.json').read_text())
        data = (ROOT / receipt['css']['path']).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), receipt['css']['sha256'])
        # This preparation target preserves exact subset assignments; every route still passes the governed 120 KB gate.
        self.assertLessEqual(len(data), 6000)
        self.assertNotIn(b'https:', data)
        for face in receipt['fonts']:
            self.assertIn(face['file'].encode(), data)
            if face['family'] == 'Inter':
                self.assertEqual([face['axes']['wght'][0], face['axes']['wght'][-1]], [100.0, 900.0])
            if face['family'] == 'Source Serif 4':
                self.assertEqual([face['axes']['opsz'][0], face['axes']['opsz'][-1]], [8.0, 60.0])


if __name__ == '__main__':
    unittest.main()
