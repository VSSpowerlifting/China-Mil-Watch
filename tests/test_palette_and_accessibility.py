"""
The p1 institutional palette, measured — and the accessibility rules it must
not break.

Contrast here is computed, never estimated. The palette replaced the oceanic
seed set on 2026-09-15 with the old China Mil Watch style revival; it is
derived from the canonical compass logo, and unlike the set it replaced every
one of its text tones clears AA on every ground it is used on. There is
nothing to demote, so this file asserts the whole matrix rather than
documenting exceptions.

The two focus rings are the part most easily broken by a well-meaning edit.
One flat colour cannot clear both the paper ground and the dark band at 3:1,
so there are two, and each FAILS on the other's ground — 2.29 and 1.71. The
tests below assert both the passes and those two failures, because a change
that made one ring work everywhere would mean someone had flattened the
distinction the scoping depends on.

The other half of the rule matters more than the ratios: colour never carries
meaning alone. Every desk status and every collection outcome has a text label
and a distinct glyph, so a monochrome print, a colour-blind reader and a
screen reader all get the same distinctions the palette draws.

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


#: The grounds a light-surface text tone may legitimately sit on.
LIGHT_GROUNDS = ("bg", "surface", "surface-inset", "accent-tint")

#: Every token that carries text on a light ground.
LIGHT_TEXT = ("ink", "ink-2", "muted", "link", "visited", "accent",
              "accent-ink", "positive", "warning")

#: Every token that carries text on the dark band.
BAND_TEXT = ("band-ink", "band-muted", "accent-tint", "focus-band")


class TestContrastIsMeasuredNotAssumed(unittest.TestCase):

    def setUp(self):
        self.t = tokens()

    def colour(self, name: str) -> str:
        value = self.t["--" + name]
        self.assertRegex(value, r"^#[0-9A-Fa-f]{6}$",
                         "--%s is not a literal colour" % name)
        return value

    def test_every_light_text_tone_clears_aa_on_every_ground_it_uses(self):
        """
        The whole matrix — 9 tones against 4 grounds, 36 cells. The palette
        this replaced had three tones that failed here and were documented as
        demoted; this one has none, and the test is written so that
        reintroducing one is a failure rather than a comment.
        """
        for text in LIGHT_TEXT:
            for ground in LIGHT_GROUNDS:
                with self.subTest(text=text, ground=ground):
                    self.assertGreaterEqual(
                        contrast(self.colour(text), self.colour(ground)),
                        AA_BODY,
                        "--%s on --%s" % (text, ground))

    def test_every_band_text_tone_clears_aa_on_the_band(self):
        for text in BAND_TEXT:
            with self.subTest(text=text):
                self.assertGreaterEqual(
                    contrast(self.colour(text), self.colour("band")),
                    AA_BODY, "--%s on --band" % text)

    def test_the_structural_accent_is_the_link_family(self):
        """
        --accent is the sole structural accent and --accent-ink is the tone it
        takes at text weight and on hover, so the second must be at least as
        dark as the first. A hover state that lightens is a hover state that
        can fail where the resting state passed.
        """
        self.assertGreater(
            contrast(self.colour("accent-ink"), self.colour("bg")),
            contrast(self.colour("accent"), self.colour("bg")))

    def test_the_paper_focus_ring_clears_three_to_one_on_every_light_ground(self):
        for ground in LIGHT_GROUNDS:
            with self.subTest(ground=ground):
                self.assertGreaterEqual(
                    contrast(self.colour("focus"), self.colour(ground)),
                    AA_LARGE, "--focus on --%s" % ground)

    def test_the_band_focus_ring_clears_three_to_one_on_the_band(self):
        self.assertGreaterEqual(
            contrast(self.colour("focus-band"), self.colour("band")),
            AA_LARGE)

    def test_neither_focus_ring_works_on_the_other_ground(self):
        """
        The reason there are two rings, asserted rather than asserted-about.

        If either of these starts passing, one ring has been made to work
        everywhere — which would be good news, but it would also mean the
        scoping rules in the stylesheet (`--focus-band` confined to `.band`
        and the skip chip) are now arbitrary rather than required, and they
        should be revisited deliberately instead of silently kept.

        1.71:1 is the specific measurement that forbids the band ring on this
        masthead, which is a LIGHT surface in this design.
        """
        self.assertLess(
            contrast(self.colour("focus"), self.colour("band")), AA_LARGE,
            "the paper ring now works on the band")
        self.assertLess(
            contrast(self.colour("focus-band"), self.colour("surface")),
            AA_LARGE, "the band ring now works on a light surface")

    def test_the_band_ring_is_scoped_to_the_band_and_the_skip_chip(self):
        """
        Item 24 of the implementation map. Measured at 1.71:1 across 71 cells
        when it was applied to the light masthead.
        """
        css = CSS.read_text(encoding="utf-8")
        for selector in re.findall(
                r"([^{}\n]*)\{[^{}]*outline-color:\s*var\(--focus-band\)", css):
            flat = " ".join(selector.split())
            with self.subTest(selector=flat):
                self.assertTrue(
                    ".band" in flat or ".skip" in flat,
                    "the band focus ring is applied outside .band / .skip: %s"
                    % flat)

    def test_the_crimson_family_stays_off_the_light_accent_scheme(self):
        """
        Crimson is confined to dark chrome. --crimson is a text tone on light
        and a fill on dark; the two lifted tones are the dark-surface text.
        """
        self.assertGreaterEqual(
            contrast(self.colour("crimson"), self.colour("bg")), AA_BODY)
        self.assertLess(
            contrast(self.colour("crimson"), self.colour("band")), AA_LARGE,
            "--crimson must not be dark-surface text")
        self.assertGreaterEqual(
            contrast(self.colour("crimson-text"), self.colour("band")),
            AA_BODY)
        self.assertGreaterEqual(
            contrast(self.colour("crimson-mark"), self.colour("band")),
            AA_LARGE)

    def test_the_palette_header_states_what_was_measured(self):
        """
        A palette whose header stops describing it is one somebody retunes by
        eye next month.
        """
        header = CSS.read_text(encoding="utf-8").split(":root {", 1)[0]
        self.assertIn("P1 INSTITUTIONAL PALETTE, MEASURED", header)
        self.assertIn("TWO FOCUS RINGS", header)
        self.assertIn("ACCENT DISCIPLINE", header)

    def test_the_legacy_aliases_all_resolve_to_a_p1_token(self):
        """
        The interior pages still use the old semantic names. They are aliases,
        so there is still exactly one place a colour is decided — a literal
        that reappeared among them would be a second palette.
        """
        aliases = ("paper", "deep", "graphite", "ocean", "text-muted",
                   "text-muted-tinted", "mist", "surface-2", "seaglass",
                   "teal", "teal-text", "turquoise", "signal", "signal-rule",
                   "parchment-field", "line-soft", "abyss", "parchment",
                   "dark-muted")
        for name in aliases:
            with self.subTest(alias=name):
                self.assertRegex(
                    self.t["--" + name], r"^var\(--[a-z0-9-]+\)$",
                    "--%s is a literal, not an alias onto a p1 token" % name)


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
                        # `.record-headline a` joined on 2026-09-09 with the
                        # C1 lead record. It is the same object the lead card's
                        # `h3 a` was — a record heading, not prose — and it
                        # meets the same condition: the 2px ink rule the band
                        # opens on and the provenance line above it mark it as
                        # the page's lead, and the rule restores an underline
                        # on hover and on keyboard focus.
                        (".brand", "h3 a", "h2.plain a", ".lead-title",
                         ".record-headline a",
                         ".editions", "nav.primary", ".skip")),
                    "%s removes the underline from prose links" % flat)


if __name__ == "__main__":
    unittest.main()
