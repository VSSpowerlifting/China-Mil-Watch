"""
The oceanic palette, measured — and the accessibility rules it must not break.

Contrast here is computed, never estimated. Three of the seed colours cannot
carry body text against the page ground, and the point of computing rather than
eyeballing is that they are demoted on purpose rather than shipped and
apologised for later.

The other half of the rule matters more than the ratios: colour never carries
meaning alone. Every desk status and every collection outcome has a text label
and a distinct glyph, so a monochrome print, a colour-blind reader and a screen
reader all get the same distinctions the palette draws.

Nothing here renders production or touches the tracked database.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

sys.path.insert(0, str(REPO_ROOT / "site" / "preview"))
import generate_preview as gp                                    # noqa: E402
from core.domain import DESK_STATUSES                            # noqa: E402

TRACKED_DB = REPO_ROOT / "pla_watch.db"
CSS = REPO_ROOT / "site" / "preview" / "styles.css"

#: WCAG 2.1 thresholds. Large text is >= 24px, or >= 18.66px bold.
AA_BODY = 4.5
AA_LARGE = 3.0


def _relative_luminance(hex_colour: str) -> float:
    value = hex_colour.lstrip("#")
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    la, lb = _relative_luminance(a), _relative_luminance(b)
    high, low = max(la, lb), min(la, lb)
    return (high + 0.05) / (low + 0.05)


def tokens() -> dict:
    """Every custom property declared on `:root`, as name -> value."""
    css = CSS.read_text(encoding="utf-8")
    root = css.split(":root {", 1)[1].split("\n}", 1)[0]
    found = {}
    for name, value in re.findall(r"(--[a-z0-9-]+):\s*([^;]+);", root):
        found[name] = value.strip()
    return found


class TestContrastIsMeasuredNotAssumed(unittest.TestCase):

    def setUp(self):
        self.t = tokens()

    def colour(self, name: str) -> str:
        value = self.t["--" + name]
        self.assertRegex(value, r"^#[0-9A-Fa-f]{6}$",
                         "--%s is not a literal colour" % name)
        return value

    def test_body_text_on_paper_meets_aa(self):
        self.assertGreaterEqual(
            contrast(self.colour("ink"), self.colour("paper")), AA_BODY)

    def test_secondary_and_muted_text_meet_aa_on_every_ground_they_use(self):
        pairs = (
            ("deep", "paper"), ("deep", "mist"),
            ("text-muted", "paper"), ("text-muted", "mist"),
            ("text-muted-tinted", "mist"), ("text-muted-tinted", "seaglass"),
        )
        for text, ground in pairs:
            with self.subTest(text=text, ground=ground):
                self.assertGreaterEqual(
                    contrast(self.colour(text), self.colour(ground)), AA_BODY)

    def test_the_structural_accent_meets_aa_wherever_links_sit(self):
        for ground in ("paper", "mist", "seaglass"):
            with self.subTest(ground=ground):
                self.assertGreaterEqual(
                    contrast(self.colour("ocean"), self.colour(ground)),
                    AA_BODY)

    def test_the_machine_output_signal_meets_aa(self):
        for ground in ("paper", "mist"):
            with self.subTest(ground=ground):
                self.assertGreaterEqual(
                    contrast(self.colour("signal"), self.colour(ground)),
                    AA_BODY)

    def test_the_desk_status_tone_meets_aa(self):
        self.assertGreaterEqual(
            contrast(self.colour("teal-text"), self.colour("paper")), AA_BODY)

    def test_the_dark_band_text_meets_aa_on_ink(self):
        for text in ("seaglass", "turquoise"):
            with self.subTest(text=text):
                self.assertGreaterEqual(
                    contrast(self.colour(text), self.colour("ink")), AA_BODY)

    def test_the_demoted_colours_are_documented_as_demoted(self):
        """
        Three seed colours fail body contrast on paper. They are kept for marks
        and fills, and the header comment has to say so — a colour that fails
        silently is one somebody uses for text next month.
        """
        css = CSS.read_text(encoding="utf-8")
        for name, ceiling in (("teal", AA_BODY), ("turquoise", AA_BODY),
                              ("seaglass", AA_BODY)):
            with self.subTest(colour=name):
                self.assertLess(
                    contrast(self.colour(name), self.colour("paper")), ceiling)
        header = css.split(":root {", 1)[0]
        self.assertIn("demoted", header)
        self.assertIn("OCEANIC PALETTE, MEASURED", header)

    def test_the_large_only_accent_still_clears_the_large_text_bar(self):
        self.assertGreaterEqual(
            contrast(self.colour("teal"), self.colour("paper")), AA_LARGE)


class TestColourIsCentralised(unittest.TestCase):

    def test_every_colour_is_a_token(self):
        """
        A literal hex outside `:root` is a colour nobody can retune and nobody
        measured. The only exceptions are the print block, which deliberately
        forces pure black on pure white, and the standalone mark, which has to
        work as a file on its own.
        """
        css = CSS.read_text(encoding="utf-8")
        body = css.split(":root {", 1)[1].split("\n}", 1)[1]
        print_block = body.split("@media print", 1)[1]
        body_without_print = body.split("@media print", 1)[0]
        literals = re.findall(r"#[0-9A-Fa-f]{3,6}\b", body_without_print)
        self.assertEqual(literals, [], "colour literals outside :root: %s"
                         % literals)
        self.assertIn("#fff", print_block)

    def test_no_page_carries_an_inline_colour(self):
        build = Path(tempfile.mkdtemp(prefix="palette-"))
        self.addCleanup(shutil.rmtree, build, True)
        if not TRACKED_DB.exists():
            self.skipTest("production database not present")
        out = build / "b"
        gp.build(out, "Test Title", TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(TRACKED_DB))
        for page in sorted(out.glob("*.html")):
            html = page.read_text(encoding="utf-8")
            with self.subTest(page=page.name):
                self.assertNotRegex(html, r'style="[^"]*(?:color|background)')


class TestMeaningNeverRestsOnColourAlone(unittest.TestCase):

    def setUp(self):
        self.css = CSS.read_text(encoding="utf-8")

    def test_every_desk_status_has_a_glyph_as_well_as_a_colour(self):
        for status in DESK_STATUSES:
            with self.subTest(status=status):
                self.assertRegex(
                    self.css,
                    r"\.desk-state--%s::before\s*\{\s*content:\s*\"[^\"]+\""
                    % status)

    def test_no_two_desk_statuses_share_a_glyph(self):
        glyphs = {}
        for status in DESK_STATUSES:
            match = re.search(
                r"\.desk-state--%s::before\s*\{\s*content:\s*\"([^\"]+)\""
                % status, self.css)
            self.assertIsNotNone(match)
            glyphs[status] = match.group(1).strip()
        self.assertEqual(len(set(glyphs.values())), len(DESK_STATUSES),
                         "two desk statuses share a marker: %s" % glyphs)

    def test_every_run_outcome_carries_a_mark_and_a_name(self):
        template = (REPO_ROOT / "site" / "preview" / "templates"
                    / "coverage.html").read_text(encoding="utf-8")
        self.assertIn('class="status-mark" aria-hidden="true"', template)
        self.assertIn('class="status-name"', template)

    def test_every_stored_status_has_reader_facing_prose(self):
        """
        A status with no entry renders as its raw stored token, which is
        repository language on a reader surface — and, worse, an outcome the
        reader has to guess at.
        """
        from core.collection import status as st
        self.assertEqual(sorted(gp.STATUS_PROSE), sorted(st.ALL_STATUSES))
        for code, (label, prose) in gp.STATUS_PROSE.items():
            with self.subTest(status=code):
                self.assertTrue(label.strip())
                self.assertTrue(prose.strip())
                self.assertNotIn("_", label)

    def test_no_two_outcomes_share_a_reader_facing_label(self):
        labels = [label for label, _ in gp.STATUS_PROSE.values()]
        self.assertEqual(len(labels), len(set(labels)),
                         "two collection outcomes collapse into one label")


class TestKeyboardAndMotionRules(unittest.TestCase):

    def setUp(self):
        self.css = CSS.read_text(encoding="utf-8")

    def test_focus_is_never_removed_and_is_always_visible(self):
        self.assertNotIn("outline: none", self.css)
        self.assertNotIn("outline:none", self.css)
        focus = re.search(r":focus-visible[^{]*\{([^}]*)\}", self.css)
        self.assertIsNotNone(focus)
        self.assertIn("outline: 2px solid", focus.group(1))
        self.assertIn("outline-offset", focus.group(1))

    def test_a_skip_link_is_the_first_thing_in_tab_order(self):
        base = (REPO_ROOT / "site" / "preview" / "templates"
                / "base.html").read_text(encoding="utf-8")
        body = base.split("<body>", 1)[1]
        self.assertTrue(body.lstrip().startswith('<a class="skip"'))
        self.assertIn(".skip:focus", self.css)

    def test_reduced_motion_is_honoured(self):
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
        block = self.css.split(
            "@media (prefers-reduced-motion: reduce)", 1)[1]
        for rule in ("animation-duration", "transition-duration",
                     "scroll-behavior"):
            with self.subTest(rule=rule):
                self.assertIn(rule, block)

    def test_body_links_are_distinguishable_without_colour(self):
        """
        Links in prose keep their underline. The places that drop it are
        headings and the masthead, where the surrounding structure already
        marks the target — and every one of those restores it on hover.
        """
        undecorated = re.findall(
            r"([^{}]*a[^{}]*)\{[^{}]*text-decoration:\s*none", self.css)
        for selector in undecorated:
            flat = selector.strip()
            with self.subTest(selector=flat):
                self.assertTrue(
                    any(marker in flat for marker in
                        # `h2.plain a` joined this list on 2026-08-27 for the
                        # desk cards. Same rationale as `h3 a`, and it meets the
                        # same condition: it is a card heading rather than
                        # prose, the card's own border and status chip already
                        # mark it as a target, and the rule restores the
                        # underline on hover.
                        (".brand", "h3 a", "h2.plain a", ".lead-title",
                         ".editions", "nav.primary", ".skip")),
                    "%s removes the underline from prose links" % flat)


if __name__ == "__main__":
    unittest.main()
