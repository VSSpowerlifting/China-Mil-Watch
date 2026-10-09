"""Night Desk contrast remains measured after the gradient veil is retired."""
from tests import test_homepage_veil_contract as probe


class TestTheBandInTheBrowser(probe.TestTextOverTheVeilIsMeasuredAtItsGlyphs):
    RUNS = {'.home-coast-band h2': 3.0, '.home-coast-band .meta': 4.5,
            '.home-coast-band .home-small-label': 4.5}
