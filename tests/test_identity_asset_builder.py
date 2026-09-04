"""
What `scripts/build_identity_assets.py` promises, and what it can actually keep.

Two claims in the first version of that script were stronger than the code
behind them, and both are the kind that get believed.

`--check` said it verified the committed derivatives. It verified four of
them — the vector mark and the three PNGs computed from geometry — and returned
before reaching the social card, which is the one asset a reviewer is least
able to eyeball. Meanwhile the inventory recorded a digest for it, so the
documentation implied a check that did not run.

The first attempt at fixing that over-corrected in the other direction: it
claimed every geometry-computed derivative was byte-reproducible and compared
all of them. CI disproved it immediately — regenerating
`ipr-compass-icon-16.png` on Linux produces a different file from the committed
macOS one, because Pillow's PNG encoder output depends on the Pillow and zlib
build even when the pixels are identical.

So the line is not "computed from geometry" versus "rendered in a browser". It
is what the *format* guarantees:

  * the vector mark is text generated from coordinates, byte-identical
    anywhere CPython runs, and is **regenerated and byte-compared**;
  * every raster — the icons, the masthead asset, the touch icon and the
    social card — is **pinned by recorded digest**, because no PNG here is
    reproducible across platforms. The social card additionally has its
    1200 x 630 geometry and byte budget checked.

Digest pinning catches what actually matters: a file replaced or edited
without the change being declared.

The second claim was about colour. The builder said the palette was sampled
from the canonical artwork "so the two cannot drift", while the values were
literal constants that nothing bound to the file. Constants are the right
implementation — a build that reads pixels at render time is a build that
changes silently when the artwork does — but the prose had to stop promising
enforcement it was not doing. So the binding is asserted here instead: these
tests read the canonical PNG and fail if a constant no longer matches the
pixel it was sampled from.

Nothing here writes into the identity directory or into `output/`.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BUILDER = REPO_ROOT / "scripts" / "build_identity_assets.py"
IDENTITY_DIR = REPO_ROOT / "site" / "assets" / "identity"
CANONICAL = IDENTITY_DIR / "ipr-compass-logo.png"
SOCIAL = IDENTITY_DIR / "ipr-social-card-1200x630.png"

#: The pixels each palette constant was sampled from, as (x, y) in the
#: canonical 500 x 500 artwork. These coordinates are the evidence: the field
#: gradient is read from a background column clear of the compass, and the
#: rose colour is the artwork's brightest pixel.
FIELD_TOP_PIXEL = (8, 8)
FIELD_BOTTOM_PIXEL = (8, 491)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_builder():
    import importlib
    return importlib.import_module("scripts.build_identity_assets")


class TestThePaletteIsBoundToTheCanonicalArtwork(unittest.TestCase):
    """
    The constants are pinned samples, not live reads. These are what make that
    an honest description instead of an unenforced claim.
    """

    @classmethod
    def setUpClass(cls):
        try:
            from PIL import Image
        except Exception:                                # pragma: no cover
            raise unittest.SkipTest("Pillow not available")
        cls.image = Image.open(CANONICAL).convert("RGB")
        cls.mod = load_builder()

    def test_the_field_gradient_top_matches_its_sampled_pixel(self):
        self.assertEqual(self.mod.FIELD_TOP,
                         self.image.getpixel(FIELD_TOP_PIXEL))

    def test_the_field_gradient_bottom_matches_its_sampled_pixel(self):
        self.assertEqual(self.mod.FIELD_BOTTOM,
                         self.image.getpixel(FIELD_BOTTOM_PIXEL))

    def test_the_rose_colour_is_the_artworks_brightest_pixel(self):
        brightest = max(self.image.getdata(), key=sum)
        self.assertEqual(self.mod.ROSE, brightest)

    def test_the_builder_records_where_each_sample_came_from(self):
        """
        A constant with no recorded provenance is a constant nobody can
        re-derive. The coordinates have to be in the source, not only here.
        """
        text = BUILDER.read_text(encoding="utf-8")
        for x, y in (FIELD_TOP_PIXEL, FIELD_BOTTOM_PIXEL):
            with self.subTest(pixel=(x, y)):
                self.assertIn("(%d, %d)" % (x, y), text)

    def test_the_builder_does_not_claim_drift_is_impossible(self):
        """
        The prose said the palette was sampled "so the two cannot drift".
        Nothing enforced that at the time. Drift is now caught by this module,
        which is a test, so the script may say the values are pinned — not
        that divergence is structurally impossible.
        """
        text = BUILDER.read_text(encoding="utf-8")
        self.assertNotIn("cannot drift", text)


class TestCheckModeVerifiesWhatItClaims(unittest.TestCase):

    def run_check(self):
        return subprocess.run(
            [sys.executable, str(BUILDER), "--check"],
            cwd=str(REPO_ROOT), capture_output=True, text=True)

    def test_check_passes_against_the_committed_assets(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0,
                         result.stdout + result.stderr)

    def test_check_reports_on_every_committed_raster(self):
        """
        The gap this closes: the first implementation returned before the
        social card was looked at, so `--check` was silent about the asset it
        could not regenerate. It now names every raster it pinned.
        """
        result = self.run_check()
        combined = result.stdout + result.stderr
        from scripts.build_identity_assets import RASTER_SHA256
        for name in RASTER_SHA256:
            with self.subTest(asset=name):
                self.assertIn(name, combined)

    def test_check_byte_compares_the_vector_mark(self):
        """
        The one asset whose format actually guarantees reproducibility.
        """
        result = self.run_check()
        self.assertRegex(result.stdout,
                         r"reproduced ipr-compass-mark-small\.svg\s+byte-identical")

    def test_every_raster_digest_matches_its_committed_file(self):
        from scripts.build_identity_assets import RASTER_SHA256
        for name, expected in RASTER_SHA256.items():
            with self.subTest(asset=name):
                self.assertEqual(sha256_of(IDENTITY_DIR / name), expected)

    def test_the_social_card_digest_is_recorded_in_the_builder(self):
        mod = load_builder()
        self.assertEqual(mod.SOCIAL_SHA256, sha256_of(SOCIAL))

    def test_a_replacement_card_of_the_right_shape_still_fails_check(self):
        """
        The property that makes digest pinning worth doing. A 1200 x 630 PNG
        under budget is not automatically *this* card, and swapping one in
        without updating the recorded digest has to be caught.
        """
        try:
            from PIL import Image
        except Exception:                                # pragma: no cover
            self.skipTest("Pillow not available")
        original = SOCIAL.read_bytes()
        import io
        buf = io.BytesIO()
        Image.new("RGB", (1200, 630), (10, 26, 34)).save(buf, format="PNG")
        try:
            SOCIAL.write_bytes(buf.getvalue())
            result = self.run_check()
            self.assertNotEqual(result.returncode, 0,
                                "--check accepted a substituted social card")
            self.assertIn("ipr-social-card-1200x630.png",
                          result.stdout + result.stderr)
        finally:
            SOCIAL.write_bytes(original)
        self.assertEqual(sha256_of(SOCIAL), load_builder().SOCIAL_SHA256)

    def test_check_writes_nothing(self):
        before = {p.name: sha256_of(p) for p in sorted(IDENTITY_DIR.iterdir())
                  if p.is_file()}
        self.run_check()
        after = {p.name: sha256_of(p) for p in sorted(IDENTITY_DIR.iterdir())
                 if p.is_file()}
        self.assertEqual(before, after)


class TestTheDocumentedContractMatchesTheCode(unittest.TestCase):
    """
    Help text, module docstring, the inventory and the tests all have to
    describe the same behaviour. The first version had four descriptions of
    three behaviours.
    """

    def setUp(self):
        import re
        self.builder = BUILDER.read_text(encoding="utf-8")
        raw = (IDENTITY_DIR / "IDENTITY_ASSETS.md").read_text("utf-8")
        # Collapsed so an assertion about wording is not also an assertion
        # about where the paragraph happened to wrap, and stripped of emphasis
        # markers for the same reason.
        self.inventory = re.sub(r"\s+", " ", raw.replace("*", ""))

    def test_the_help_text_distinguishes_the_two_kinds_of_verification(self):
        result = subprocess.run(
            [sys.executable, str(BUILDER), "--help"],
            cwd=str(REPO_ROOT), capture_output=True, text=True)
        help_text = " ".join(result.stdout.lower().split())
        self.assertIn("byte-compare", help_text)
        self.assertIn("digest", help_text)
        self.assertIn("not reproducible across platforms", help_text)

    def test_the_inventory_names_the_social_card_as_digest_pinned(self):
        self.assertIn("ipr-social-card-1200x630.png", self.inventory)
        self.assertRegex(self.inventory, r"(?i)pinned by (?:its )?recorded digest")

    def test_the_inventory_does_not_claim_any_png_is_byte_reproducible(self):
        """
        The inventory must scope reproducibility to the vector mark. Claiming
        it for the PNGs is the error CI caught.
        """
        self.assertRegex(
            self.inventory,
            r"(?i)ipr-compass-mark-small\.svg[^|]{0,120}?byte-identical")
        self.assertRegex(self.inventory,
                         r"(?i)PNG encoding is not reproducible across platforms")


if __name__ == "__main__":
    unittest.main()
