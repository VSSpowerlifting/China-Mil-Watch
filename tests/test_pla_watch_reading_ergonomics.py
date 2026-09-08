"""
Reading ergonomics on The PLA Watch surfaces — measured, never estimated.

Why this module exists
----------------------
The 2026-09-05 frontend audit reproduced three defects on the weekly surfaces,
all of them in the templates rather than in the published tree:

1.  `--color-text-muted` (#746E67) measures 3.64:1 on the ink-navy ground and
    3.40:1 on the lifted card. Thirty-six of its thirty-eight declarations set
    type between 9.28px and 12.5px, which WCAG counts as normal text and holds
    to 4.5:1. Only two declarations — the nameplate's "The" and the archive
    display italic — are genuinely large (>= 24px at every breakpoint), where
    3.64 already passes. A single global lift would therefore have brightened
    the masthead for no accessibility gain, so the token is split by role.

2.  The pre-title metadata block on No. 14 measured 87.1px at 375px against
    34.8px for No. 13, and pushed the headline from 278.5px down to 328.1px.
    The cause was `.hero-edition` being a non-wrapping flex row: the edition
    line, the edition badge and the retrospective badge were forced onto one
    line, so each shrank and wrapped inside itself. Below 375px the same block
    overflowed the viewport.

3.  `.pw-badge--retrospective` had no screen rule at all. It was styled only
    inside `@media print`, so on screen it fell back to bare `.pw-badge` and
    inherited the failing muted colour with no border and no background —
    unlike every sibling badge. The most important editorial disclosure on the
    page was its least legible element.

The contracts here are written so that the *relative* invariants (what the
retrospective disclosure costs against an edition without one) hold whatever
fonts resolve, because the offline suite has no network and falls back from
Source Serif 4 and IBM Plex Mono.

What these contrasts do NOT cover
---------------------------------
Every ratio asserted here is measured against a *token* ground. On an edition
carrying a Signal Veil the hero renders inside `.nd-veil-band`, so the byline
and the hero metadata sit over a photograph rather than over `--color-bg`.
Sampling the real composited pixels behind that text on No. 13 at 375px:

    .byline-title   ground rgb(85, 86, 88)   1.46:1 before -> 2.07:1 after
    .hero-meta      ground rgb(62, 68, 77)   1.95:1 before -> 2.77:1 after

Lifting the token improved both by about 42% and neither reaches AA, because
no colour can: the ground is an image. Fixing it means a scrim behind the text
column, which changes how the Signal Veil reads and is a decision about that
system rather than about this token. It is deliberately out of scope here, and
recorded so the passing assertions below are not mistaken for a guarantee that
every muted glyph on every edition clears 4.5.

Nothing here writes into `output/`, and nothing here touches `pla_watch.db`.
"""

from __future__ import annotations

import functools
import http.server
import json
import re
import shutil
import socketserver
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TEMPLATES = REPO_ROOT / "site" / "templates"
WEEKLY_TEMPLATES = sorted(TEMPLATES.glob("pla-watch-*.html"))
BASE_TEMPLATE = TEMPLATES / "pla-watch-base.html"
PREVIEW_CSS = REPO_ROOT / "site" / "preview" / "styles.css"
POSTS_DIR = REPO_ROOT / "output" / "the-pla-watch" / "posts"

RETIRED_DOMAIN = "chinamilwatch.org"
PREDECESSOR = "China Mil Watch"
CURRENT = "Indo-Pacific Record"

#: WCAG 2.1. Large text is >= 24px, or >= 18.66px at weight >= 700.
AA_BODY = 4.5
AA_LARGE = 3.0
LARGE_PX = 24.0
LARGE_BOLD_PX = 18.66

#: WCAG 2.5.8 Target Size (Minimum) is 24px; this publication holds standalone
#: controls to the 44px comfortable-touch figure the audit was scoped against.
TARGET_MIN_PX = 44.0

#: The tokens this change is responsible for. The muted token and its two
#: relatives are what the audit scoped; the brand and link colours are a
#: separate, publication-wide decision and are pinned below rather than
#: quietly changed here.
GOVERNED_TOKENS = {"--color-text-muted", "--color-chrome-label",
                   "--color-display-quiet", "--ink-3"}

#: Colours that were already below AA before this change and stay that way,
#: recorded so the set cannot grow without someone noticing. Each maps to the
#: worst ratio it reaches across the weekly grounds.
#:
#: `--signal-bright` is the near miss: it measures 5.10 on the ink navy it is
#: actually painted on and only dips to 4.47 against the sidebar ground, which
#: none of its selectors sit on. The other three are real and out of scope —
#: `--color-brand-light` is the publication's link colour on every page, and
#: changing it is an identity decision, not a contrast fix.
UNGOVERNED_SUB_AA = {
    "--color-border": 1.21,        # the "·" separator glyphs
    "--color-brand": 2.33,         # eyebrow labels, title hover
    "--color-brand-light": 3.46,   # the link colour, and hover states
    "--signal-bright": 4.47,       # passes on every ground it is used on
}

#: Every opaque ground the weekly surfaces paint text on.
WEEKLY_GROUNDS = {
    "--color-bg": "#0E1520",
    "--color-bg-card": "#131C29",
    "--color-bg-header": "#0A1019",
    "--color-bg-sidebar": "#18222F",
}


# ── colour maths ────────────────────────────────────────────────────────────

def _luminance(hex_colour: str) -> float:
    value = hex_colour.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    high, low = max(la, lb), min(la, lb)
    return (high + 0.05) / (low + 0.05)


# ── CSS reading ─────────────────────────────────────────────────────────────

def _style_source(path: Path) -> str:
    """
    The CSS a template contributes. Only the base template wraps its rules in
    `<style>`; the four children hand theirs to a Jinja block bare, so falling
    back to the whole file is what makes the scan cover all five rather than
    silently reading one and passing.
    """
    html = path.read_text(encoding="utf-8")
    blocks = re.findall(r"<style>([\s\S]*?)</style>", html)
    return "\n".join(blocks) if blocks else html


def root_tokens() -> dict:
    """`:root` custom properties declared by the weekly base template."""
    css = _style_source(BASE_TEMPLATE)
    block = css.split(":root {", 1)[1].split("\n    }", 1)[0]
    return {name: value.strip()
            for name, value in re.findall(r"(--[a-z0-9-]+):\s*([^;]+);", block)}


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*[\s\S]*?\*/", " ", css)


def _print_blocks(css: str) -> list:
    """
    Every `@media print` body. There is more than one: a small block neutralises
    the reveal-on-scroll transforms, and a later block repaints the whole
    palette for paper. Reading only the first would let a rule that exists
    solely on paper look as though it were styled for screen.
    """
    blocks, at = [], css.find("@media print")
    while at >= 0:
        i = css.find("{", at)
        if i < 0:
            break
        depth, j = 0, i
        while j < len(css):
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        blocks.append(css[i:j])
        at = css.find("@media print", j)
    return blocks


def screen_css(css: str) -> str:
    """`css` with every `@media print` body removed."""
    for block in _print_blocks(css):
        css = css.replace(block, " ")
    return css


def declarations(path: Path):
    """
    Yield `(selector, font_size_px_or_None, colour_token, is_in_print_block)`
    for every rule that sets `color: var(--token)`.

    The parser is deliberately small: these stylesheets are hand-written, one
    declaration per line, and a full CSS parser would hide more than it helps.
    """
    css = _strip_comments(_style_source(path))
    printed = "\n".join(_print_blocks(css))
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        selector, body = match.group(1).strip(), match.group(2)
        colour = re.search(r"(?<!-)\bcolor:\s*var\((--[a-z0-9-]+)\)", body)
        if not colour:
            continue
        size = re.search(r"font-size:\s*([0-9.]+)rem", body)
        px = float(size.group(1)) * 16 if size else None
        in_print = match.group(0) in printed
        yield selector.split("\n")[-1].strip(), px, colour.group(1), in_print


def inherited_font_px(selector: str, path: Path):
    """
    Resolve a font-size for a rule that declares none, by looking at the
    nearest ancestor selector that does. Returns None when nothing is found.
    """
    css = _strip_comments(_style_source(path))
    parts = selector.replace(">", " ").split()
    for depth in range(len(parts) - 1, 0, -1):
        ancestor = " ".join(parts[:depth])
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
            if match.group(1).strip().split("\n")[-1].strip() != ancestor:
                continue
            size = re.search(r"font-size:\s*([0-9.]+)rem", match.group(2))
            if size:
                return float(size.group(1)) * 16
    return None


# ── the weekly render, into scratch ─────────────────────────────────────────

class WeeklySurfaces(unittest.TestCase):
    """Renders the weekly templates the way the weekly renderer does."""

    @classmethod
    def setUpClass(cls):
        if not POSTS_DIR.is_dir() or not any(POSTS_DIR.glob("*.json")):
            raise unittest.SkipTest("no published sidecars to render")
        try:
            from scripts.pw_env import make_pw_env
            import scripts.rerender_pla_watch as rr
        except Exception as exc:                             # pragma: no cover
            raise unittest.SkipTest("weekly renderer unavailable: %s" % exc)

        cls.tmp = Path(tempfile.mkdtemp(prefix="pw-ergonomics-"))
        env = make_pw_env()
        post_tmpl = env.get_template("pla-watch-post.html")
        index_tmpl = env.get_template("pla-watch-index.html")
        archive_tmpl = env.get_template("pla-watch-archive.html")

        sidecars = [json.loads(p.read_text(encoding="utf-8"))
                    for p in sorted(POSTS_DIR.glob("*.json"))]
        by_date = sorted(sidecars, key=lambda s: s.get("date", ""))
        cls.posts = {}
        for i, sidecar in enumerate(by_date):
            ctx = rr._build_post_context(sidecar)
            ctx["prev_post"] = by_date[i - 1] if i > 0 else None
            ctx["next_post"] = by_date[i + 1] if i + 1 < len(by_date) else None
            cls.posts[sidecar["date"]] = {
                "html": post_tmpl.render(**ctx),
                "issue": sidecar.get("issue_number"),
                "sidecar": sidecar,
            }
        newest = sorted(sidecars, key=lambda s: s.get("date", ""), reverse=True)
        origin = rr.SITE_ORIGIN
        cls.index_html = index_tmpl.render(
            latest_post=newest[0], archive_posts=newest[1:], root_path="../",
            page_url="%s/the-pla-watch/" % origin, latest_veil=None)
        cls.archive_html = archive_tmpl.render(
            posts=newest, root_path="../",
            page_url="%s/the-pla-watch/archive.html" % origin)

        cls.retrospective = [d for d, p in cls.posts.items()
                             if p["sidecar"].get("publication_timing")
                             == "retrospective"]
        cls.control = [d for d, p in cls.posts.items()
                       if p["sidecar"].get("publication_timing")
                       != "retrospective"]

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "tmp"):
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def all_pages(self):
        pages = {"index.html": self.index_html,
                 "archive.html": self.archive_html}
        for date, post in self.posts.items():
            pages["posts/%s.html" % date] = post["html"]
        return pages


# ── 1. governed muted text meets AA ─────────────────────────────────────────

class TestGovernedMutedTextMeetsAA(unittest.TestCase):
    """
    The audit's first defect. Every weekly declaration that paints *normal*
    text must use a token that clears 4.5:1 on the darkest ground it can land
    on; only genuinely large type may use a quieter one, and then only down to
    3.0:1.
    """

    def setUp(self):
        self.tokens = root_tokens()

    def resolve(self, token: str):
        """Follow `var()` aliases to a literal hex, or None."""
        seen = set()
        value = self.tokens.get(token)
        while value and value.startswith("var(") and token not in seen:
            seen.add(token)
            token = value[4:].split(")")[0]
            value = self.tokens.get(token)
        return value if value and value.startswith("#") else None

    def small_text_offenders(self):
        """Every normal-size declaration below AA, as (token, description)."""
        found = []
        for path in WEEKLY_TEMPLATES:
            for selector, px, token, in_print in declarations(path):
                if in_print:
                    continue          # paper repaints the palette on white
                if px is None:
                    px = inherited_font_px(selector, path)
                if px is None:
                    px = 16.0         # inherits body copy
                if px >= LARGE_PX:
                    continue          # large text, judged separately
                colour = self.resolve(token)
                if colour is None:
                    continue
                worst = min(contrast(colour, g) for g in WEEKLY_GROUNDS.values())
                if worst < AA_BODY:
                    found.append((token, "%s:%s  %s  %.0fpx  %.2f:1"
                                  % (path.name, selector[:44], colour, px,
                                     worst)))
        return found

    def test_every_governed_small_text_declaration_meets_aa(self):
        """
        The audit's headline defect: 747 rendered instances of the muted token
        across five surfaces and three widths, none of them large enough to be
        judged at 3.0.
        """
        offenders = [d for token, d in self.small_text_offenders()
                     if token in GOVERNED_TOKENS]
        self.assertEqual(
            offenders, [],
            "governed weekly text below AA:\n  " + "\n  ".join(offenders))

    def test_the_ungoverned_sub_aa_set_has_not_grown(self):
        """
        What this change deliberately did not touch, pinned. A new token
        appearing here is a regression even though none of these are.
        """
        seen = {token for token, _ in self.small_text_offenders()}
        self.assertEqual(
            seen, set(UNGOVERNED_SUB_AA),
            "the set of sub-AA colours changed; added=%s removed=%s"
            % (sorted(seen - set(UNGOVERNED_SUB_AA)),
               sorted(set(UNGOVERNED_SUB_AA) - seen)))

    def test_large_display_text_still_clears_the_large_threshold(self):
        """
        The two declarations kept on the darker gray are display type at every
        breakpoint, and 3.64:1 clears the 3.0 they are held to. Ungoverned
        tokens are pinned by `test_the_ungoverned_sub_aa_set_has_not_grown`
        instead; `.issue-cover-title a:hover` paints the brand red and was
        below 3.0 before this change too.
        """
        offenders = []
        for path in WEEKLY_TEMPLATES:
            for selector, px, token, in_print in declarations(path):
                if in_print or token not in GOVERNED_TOKENS:
                    continue
                if px is None:
                    px = inherited_font_px(selector, path)
                if px is None or px < LARGE_PX:
                    continue
                colour = self.resolve(token)
                if colour is None:
                    continue
                worst = min(contrast(colour, g) for g in WEEKLY_GROUNDS.values())
                if worst < AA_LARGE:
                    offenders.append("%s:%s %s %.2f:1"
                                     % (path.name, selector[:40], colour, worst))
        self.assertEqual(offenders, [], "large weekly text below AA-large:\n  "
                         + "\n  ".join(offenders))

    def test_the_hierarchy_between_secondary_and_muted_survives(self):
        """
        Lifting muted must not collapse it into secondary: the ramp is what
        tells metadata apart from body copy at a glance.
        """
        secondary = self.resolve("--color-text-secondary")
        muted = self.resolve("--color-text-muted")
        ground = WEEKLY_GROUNDS["--color-bg"]
        self.assertIsNotNone(muted)
        gap = contrast(secondary, ground) / contrast(muted, ground)
        self.assertGreater(gap, 1.25,
                           "secondary and muted are too close to read as a ramp")


# ── 2. the retrospective disclosure, and the block that carries it ──────────

class TestRetrospectiveDisclosureIsPreserved(WeeklySurfaces):

    def test_every_retrospective_edition_still_states_its_timing(self):
        self.assertTrue(self.retrospective, "no retrospective edition to check")
        for date in self.retrospective:
            with self.subTest(date=date):
                html = self.posts[date]["html"]
                label = self.posts[date]["sidecar"].get(
                    "retrospective_label", "Retrospective edition")
                self.assertIn(label, html)

    def test_the_disclosure_is_never_hidden_or_truncated(self):
        for date in self.retrospective:
            with self.subTest(date=date):
                html = self.posts[date]["html"]
                match = re.search(
                    r'<span class="pw-badge pw-badge--retrospective"[^>]*>'
                    r'([^<]*)</span>', html)
                self.assertIsNotNone(match, "disclosure badge missing")
                self.assertTrue(match.group(1).strip())
                tag = match.group(0)
                for forbidden in ("hidden", "aria-hidden", "display:none",
                                  "display: none"):
                    self.assertNotIn(forbidden, tag)

    def test_the_disclosure_badge_has_a_screen_rule_not_only_a_print_one(self):
        """
        The defect: `.pw-badge--retrospective` was declared only inside
        `@media print`, so on screen it inherited the failing muted colour with
        no border while every sibling badge carried one.
        """
        screen = screen_css(_strip_comments(_style_source(BASE_TEMPLATE)))
        self.assertIn(".pw-badge--retrospective", screen,
                      "retrospective badge has no screen treatment")

    def test_the_disclosure_reads_at_aa_on_screen(self):
        screen = screen_css(_strip_comments(_style_source(BASE_TEMPLATE)))
        rule = re.search(r"\.pw-badge--retrospective\s*\{([^}]*)\}", screen)
        self.assertIsNotNone(rule)
        body = rule.group(1)
        token = re.search(r"(?<!-)\bcolor:\s*var\((--[a-z0-9-]+)\)", body)
        literal = re.search(r"(?<!-)\bcolor:\s*(#[0-9A-Fa-f]{3,6})\b", body)
        self.assertTrue(token or literal, "badge sets no explicit screen colour")
        colour = (root_tokens().get(token.group(1)) if token
                  else literal.group(1))
        self.assertTrue(colour and colour.startswith("#"))
        worst = min(contrast(colour, g) for g in WEEKLY_GROUNDS.values())
        self.assertGreaterEqual(worst, AA_BODY,
                                "disclosure badge measures %.2f:1" % worst)


class TestMetadataBlockStructure(WeeklySurfaces):
    """
    The metadata block must wrap at semantic joints. The defect was a flex row
    that could not wrap, so it shredded the edition line into four ragged
    lines instead of letting the status badges fall to their own.
    """

    def test_the_edition_line_and_the_status_badges_are_separate_groups(self):
        for date in self.retrospective + self.control:
            with self.subTest(date=date):
                html = self.posts[date]["html"]
                self.assertIn('class="hero-edition-line"', html)

    def test_the_edition_line_never_breaks_inside_a_date_or_a_number(self):
        css = _strip_comments(_style_source(REPO_ROOT / "site" / "templates"
                                            / "pla-watch-post.html"))
        self.assertRegex(css, r"\.ed-no[^{]*\{[^}]*white-space:\s*nowrap")
        self.assertRegex(css, r"\.ed-week[^{]*\{[^}]*white-space:\s*nowrap")

    def test_the_metadata_block_reading_order_is_unchanged(self):
        """Edition line first, then status. Same order at every viewport."""
        for date in self.retrospective:
            with self.subTest(date=date):
                html = self.posts[date]["html"]
                line = html.find('class="hero-edition-line"')
                status = html.find('class="hero-status"')
                title = html.find('class="hero-title"')
                self.assertNotEqual(line, -1)
                self.assertNotEqual(status, -1)
                self.assertLess(line, status)
                self.assertLess(status, title)


# ── 3. target sizes, declared as a contract ─────────────────────────────────

class TestTouchTargetContract(unittest.TestCase):

    def test_the_weekly_stylesheet_declares_the_target_floor(self):
        """
        The contract is expressed once, as a documented custom property, so a
        future rule can reach for it instead of re-deriving 44 by hand.
        """
        tokens = root_tokens()
        self.assertIn("--target-min", tokens)
        self.assertEqual(tokens["--target-min"], "44px")

    def test_hit_area_expansion_never_costs_masthead_height(self):
        """
        Growing the nav links to 44px with `min-height` cost 35.7px of
        masthead and pushed the headline down — fighting the very defect this
        change exists to fix. The expansion is padding balanced by negative
        margin, which leaves layout untouched.
        """
        css = _strip_comments(_style_source(BASE_TEMPLATE))
        rule = re.search(r"\.pw-nav a\s*\{([^}]*)\}", css)
        self.assertIsNotNone(rule)
        self.assertNotIn("min-height", rule.group(1),
                         "min-height on nav links inflates the masthead")


# ── identity, unchanged ─────────────────────────────────────────────────────

class TestIdentityIsUntouched(WeeklySurfaces):

    def test_historical_editions_keep_the_publisher_that_published_them(self):
        for date, post in self.posts.items():
            if post["issue"] and post["issue"] <= 13:
                with self.subTest(date=date, issue=post["issue"]):
                    self.assertIn(PREDECESSOR, post["html"])

    def test_current_editions_carry_the_current_publication(self):
        for date, post in self.posts.items():
            if post["issue"] and post["issue"] > 13:
                with self.subTest(date=date, issue=post["issue"]):
                    self.assertIn(CURRENT, post["html"])
                    body = post["html"].split('class="byline"', 1)[-1][:400]
                    self.assertNotIn(PREDECESSOR, body)

    def test_no_weekly_page_hard_codes_the_retired_domain(self):
        for name, html in self.all_pages().items():
            with self.subTest(page=name):
                self.assertNotIn(RETIRED_DOMAIN, html)

    def test_edition_numbering_and_classification_are_not_restyled_away(self):
        for date, post in self.posts.items():
            if not post["issue"]:
                continue
            with self.subTest(date=date):
                self.assertIn("No. %d" % post["issue"], post["html"])


class TestCompassSizingIsUnchanged(unittest.TestCase):
    """
    The compass belongs to the record site, not to the weekly templates. This
    change must not reach it; 56 desktop and 48 compact stay as published.
    """

    def test_the_mark_is_56_on_desktop_and_48_compact(self):
        css = PREVIEW_CSS.read_text(encoding="utf-8")
        self.assertRegex(css, r"\.brand-mark\s*\{[^}]*width:\s*56px;"
                              r"\s*height:\s*56px")
        self.assertRegex(css, r"\.brand-mark\s*\{\s*width:\s*48px;"
                              r"\s*height:\s*48px;\s*\}")

    def test_the_weekly_templates_do_not_style_the_mark(self):
        for path in WEEKLY_TEMPLATES:
            with self.subTest(template=path.name):
                self.assertNotIn("brand-mark", path.read_text(encoding="utf-8"))


# ── measured in a browser, where one is available ──────────────────────────

class BrowserCase(WeeklySurfaces):
    """
    Serves the rendered weekly pages from a loopback port and measures them.

    Skips cleanly where playwright or its chromium build is absent: the
    pull-request workflow installs no browser, and a skipped check is honest
    where a silently-passing one is not.
    """

    WIDTHS = (375, 768, 1280)

    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:                                  # pragma: no cover
            raise unittest.SkipTest("playwright not installed")
        super().setUpClass()

        (cls.tmp / "posts").mkdir(parents=True, exist_ok=True)
        for name, html in cls().all_pages().items():
            (cls.tmp / name).write_text(html, encoding="utf-8")

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
        handler = functools.partial(Quiet, directory=str(cls.tmp))
        socketserver.TCPServer.allow_reuse_address = True
        cls.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever,
                                      daemon=True)
        cls.thread.start()

        cls._pw = sync_playwright().start()
        try:
            cls.browser = cls._pw.chromium.launch()
        except Exception as exc:                             # pragma: no cover
            cls._pw.stop()
            cls.httpd.shutdown()
            cls.httpd.server_close()
            raise unittest.SkipTest(
                "chromium not available (%s); run `playwright install chromium`"
                % type(exc).__name__)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "browser"):
            cls.browser.close()
            cls._pw.stop()
            cls.httpd.shutdown()
            cls.httpd.server_close()
        super().tearDownClass()

    def measure(self, page_path: str, width: int, script: str,
                block_webfonts: bool = False, extra_css: str = None):
        """
        Measures one page at one width.

        `block_webfonts` aborts the Google Fonts requests, which is the
        condition the CI runner reproduces and a developer machine with a warm
        font cache does not. A fresh context per call means a font cached by an
        earlier measurement cannot leak in and quietly re-run the webfont path.

        `extra_css` injects a stylesheet after load. It exists so a test can
        restore a pre-fix condition and prove a diagnostic still names the
        offender; it is not a way to invent geometry the product never has.
        """
        ctx = self.browser.new_context(viewport={"width": width, "height": 900},
                                       device_scale_factor=1)
        page = ctx.new_page()
        blocked = {"n": 0}
        try:
            if block_webfonts:
                def abort(route):
                    blocked["n"] += 1
                    route.abort()
                page.route("**://fonts.googleapis.com/**", abort)
                page.route("**://fonts.gstatic.com/**", abort)
            page.goto("http://127.0.0.1:%d/%s" % (self.port, page_path),
                      wait_until="load")
            if extra_css:
                page.add_style_tag(content=extra_css)
            page.wait_for_timeout(200 if block_webfonts else 120)
            result = page.evaluate(script)
            if isinstance(result, dict):
                result["blockedFontRequests"] = blocked["n"]
            return result
        finally:
            ctx.close()


LAYOUT_JS = r"""
() => {
  const box = s => { const e = document.querySelector(s); if (!e) return null;
    const r = e.getBoundingClientRect();
    return { h:+r.height.toFixed(1), top:+(r.top+scrollY).toFixed(1) }; };
  const label = e => e.tagName.toLowerCase() + '.' +
      String(e.className || '').split(' ').filter(Boolean).slice(0,2).join('.');

  // Element border boxes. Unchanged: this is what named the No. 14 metadata
  // defect in 2026-09-05 and it stays the first thing a reader sees.
  const over = [...document.querySelectorAll('*')].filter(e => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && (r.right > innerWidth + 1);
  }).slice(0, 6).map(label);

  const overflowX = document.documentElement.scrollWidth > innerWidth;

  // Inline text runs. An element's border box can sit entirely inside the
  // viewport while the text inside it lays out past both the box and the
  // viewport -- exactly the source-trail domain case, where the cell was
  // 280px wide and its text reached 376.28 on a 375px viewport.
  // getBoundingClientRect() cannot see that, scrollWidth can, and the
  // difference is why this assertion used to fail with an empty list.
  //
  // Only walked when the document actually overflows: the passing path stays
  // one integer comparison, so the browser suite does not get slower.
  const textOver = [];
  if (overflowX) {
    const clipped = el => { let a = el && el.parentElement;
      while (a) { const cs = getComputedStyle(a);
        // Text under a clipping ancestor cannot grow the scrollable area, so
        // naming it would send a reader after the wrong element.
        if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') return true;
        a = a.parentElement; }
      return false; };
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode()) && textOver.length < 6) {
      if (!n.textContent.trim()) continue;
      const parent = n.parentElement;
      if (!parent || clipped(parent)) continue;
      const range = document.createRange();
      range.selectNodeContents(n);
      for (const b of range.getClientRects()) {
        if (b.width > 0 && b.right > innerWidth + 0.01) {
          textOver.push({
            el: label(parent),
            right: +b.right.toFixed(4),
            past: +(b.right - innerWidth).toFixed(4),
            text: n.textContent.trim().replace(/\s+/g, ' ').slice(0, 60),
          });
          break;
        }
      }
    }
  }

  return { meta: box('.hero-meta-top'), title: box('.hero-title'),
           overflowX,
           scrollW: document.documentElement.scrollWidth,
           viewportW: innerWidth,
           overflowers: over,
           textOverflowers: textOver };
}
"""


def overflow_report(r):
    """Renders LAYOUT_JS output as an assertion message that names something.

    The element list alone printed `[]` whenever the overflow came from inline
    text, which is the case that actually shipped.
    """
    parts = ["document scrollWidth %s vs viewport %s"
             % (r.get("scrollW"), r.get("viewportW"))]
    if r.get("overflowers"):
        parts.append("element boxes past the viewport: %s" % (r["overflowers"],))
    for t in r.get("textOverflowers") or []:
        parts.append("inline text in %s reaches %.4f (%+.4f past the viewport): %r"
                     % (t["el"], t["right"], t["past"], t["text"]))
    if not r.get("overflowers") and not r.get("textOverflowers"):
        parts.append("no element box and no unclipped text run exceeded the "
                     "viewport; the overflow is sub-pixel or comes from a "
                     "source this probe does not model")
    return "; ".join(parts)

TARGET_JS = r"""
() => {
  const bad = [];
  document.querySelectorAll('a[href],button,[role="button"],summary')
    .forEach(el => {
      const r = el.getBoundingClientRect();
      if (!r.width && !r.height) return;
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') return;
      const p = el.parentElement;
      // WCAG 2.5.8 exempts a link sitting inside a sentence of running text.
      const inlineInProse = cs.display.startsWith('inline') && p &&
        p.textContent.trim().length > (el.textContent||'').trim().length + 12;
      if (inlineInProse) return;
      const min = Math.min(r.width, r.height);
      if (min < 44) bad.push({
        sel: el.tagName.toLowerCase() + '.' +
             String(el.className||'').split(' ').filter(Boolean).slice(0,2).join('.'),
        min: +min.toFixed(1),
        text: (el.innerText||'').replace(/\s+/g,' ').trim().slice(0,28) });
    });
  return bad;
}
"""

FOCUS_JS = r"""
() => {
  const a = document.querySelector('.pw-nav a');
  if (!a) return null;
  a.focus();
  const cs = getComputedStyle(a);
  return { outlineWidth: cs.outlineWidth, outlineStyle: cs.outlineStyle,
           boxShadow: cs.boxShadow, active: document.activeElement === a };
}
"""


class TestMobileMetadataHierarchy(BrowserCase):

    def _dates(self):
        self.assertTrue(self.retrospective, "no retrospective edition")
        self.assertTrue(self.control, "no control edition")
        return self.retrospective[0], sorted(self.control)[-1]

    def test_the_disclosure_costs_almost_nothing_in_metadata_height(self):
        """
        The defect, stated as an invariant that does not depend on which fonts
        resolve: carrying the retrospective disclosure measured 87.1px against
        the control's 34.8px at 375px — two and a half times taller.
        """
        retro, control = self._dates()
        r = self.measure("posts/%s.html" % retro, 375, LAYOUT_JS)
        c = self.measure("posts/%s.html" % control, 375, LAYOUT_JS)
        self.assertLessEqual(
            r["meta"]["h"], c["meta"]["h"] + 8.0,
            "retrospective metadata is %.1fpx against a %.1fpx control"
            % (r["meta"]["h"], c["meta"]["h"]))

    def test_the_disclosure_does_not_push_the_headline_down(self):
        retro, control = self._dates()
        r = self.measure("posts/%s.html" % retro, 375, LAYOUT_JS)
        c = self.measure("posts/%s.html" % control, 375, LAYOUT_JS)
        self.assertLessEqual(
            r["title"]["top"], c["title"]["top"] + 12.0,
            "headline starts at %.1fpx against a %.1fpx control"
            % (r["title"]["top"], c["title"]["top"]))

    def test_the_metadata_block_stays_within_three_lines_at_375(self):
        retro, _ = self._dates()
        r = self.measure("posts/%s.html" % retro, 375, LAYOUT_JS)
        self.assertLessEqual(r["meta"]["h"], 56.0,
                             "metadata block is %.1fpx tall" % r["meta"]["h"])

    def test_no_weekly_surface_overflows_horizontally(self):
        pages = ["index.html", "archive.html"]
        pages += ["posts/%s.html" % d for d in
                  (self.retrospective[:1] + sorted(self.control)[-1:])]
        for page in pages:
            for width in self.WIDTHS:
                with self.subTest(page=page, width=width):
                    r = self.measure(page, width, LAYOUT_JS)
                    self.assertFalse(
                        r["overflowX"],
                        "overflow at %dpx on %s: %s"
                        % (width, page, overflow_report(r)))


class TestActionableTargetsAreComfortable(BrowserCase):

    def test_standalone_controls_meet_the_target_floor(self):
        pages = ["index.html", "archive.html"]
        pages += ["posts/%s.html" % d for d in
                  (self.retrospective[:1] + sorted(self.control)[-1:])]
        offenders = {}
        for page in pages:
            for width in self.WIDTHS:
                bad = self.measure(page, width, TARGET_JS)
                if bad:
                    offenders["%s@%d" % (page, width)] = bad
        self.assertEqual(offenders, {},
                         "controls under %.0fpx:\n%s"
                         % (TARGET_MIN_PX, json.dumps(offenders, indent=1)))


class TestKeyboardFocusStaysVisible(BrowserCase):

    def test_a_focused_nav_link_paints_a_ring(self):
        for width in self.WIDTHS:
            with self.subTest(width=width):
                r = self.measure("archive.html", width, FOCUS_JS)
                self.assertIsNotNone(r)
                self.assertTrue(r["active"])
                visible = (r["outlineStyle"] not in ("none", "")
                           and r["outlineWidth"] not in ("0px", "")) \
                    or r["boxShadow"] not in ("none", "")
                self.assertTrue(visible,
                                "no visible focus ring: %r" % (r,))


# ── 8. source-trail domains wrap instead of overflowing ─────────────────────

SOURCE_DOMAIN_JS = r"""
() => {
  const de = document.documentElement, view = de.clientWidth;
  const cells = [...document.querySelectorAll('.source-card-domain')];
  const clipsSomewhere = el => {
    let a = el.parentElement;
    while (a) { const cs = getComputedStyle(a);
      if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') return true;
      a = a.parentElement; }
    return false;
  };
  const runs = [];
  for (const cell of cells) {
    const card = cell.closest('.source-card');
    const box = cell.getBoundingClientRect();
    const cardBox = card ? card.getBoundingClientRect() : null;
    let right = -Infinity, lines = 0;
    for (const n of cell.childNodes) {
      if (n.nodeType !== 3 || !n.textContent.trim()) continue;
      const r = document.createRange(); r.selectNodeContents(n);
      for (const b of r.getClientRects()) { lines++; if (b.right > right) right = b.right; }
    }
    runs.push({
      text: cell.textContent.trim(),
      right: right === -Infinity ? null : +right.toFixed(4),
      overView: right === -Infinity ? null : +(right - view).toFixed(4),
      lines,
      boxRight: +box.right.toFixed(4), boxWidth: +box.width.toFixed(2),
      boxHeight: +box.height.toFixed(2),
      visible: box.width > 0 && box.height > 0,
      clipped: clipsSomewhere(cell),
      cardRight: cardBox ? +cardBox.right.toFixed(4) : null,
      insideCard: cardBox ? right <= cardBox.right + 0.5 : null,
      // a monospace fingerprint: the same string measures differently under
      // the webfont and under the fallback, which is how the test proves the
      // fallback path was genuinely taken rather than assumed.
    });
  }
  const probe = document.createElement('span');
  probe.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;'
                      + 'font-family:var(--mono);font-size:100px';
  probe.textContent = 'MMMMMMMMMM';
  document.body.appendChild(probe);
  const monoWidth = +probe.getBoundingClientRect().width.toFixed(3);
  probe.remove();
  return {runs, view, scrollW: de.scrollWidth, clientW: de.clientWidth,
          overflowX: de.scrollWidth > de.clientWidth, monoWidth};
}
"""


class TestSourceTrailDomainsWrap(BrowserCase):
    """
    A source-trail domain is a single unbroken token. `.source-card-domain`
    declared no wrapping behaviour, so a long one laid out past its own border
    box and past the viewport: the element stayed 280px wide inside the card
    while its text run reached 376.28px on a 375px viewport.

    `documentElement.scrollWidth` rounds to the nearest integer, which is why
    this surfaced as an intermittent defect rather than a constant one. Under
    the webfont the run overhangs by 0.22px and 375.22 rounds back to 375;
    under the fallback it overhangs by 1.28px and 376.28 rounds to 376. The
    geometry is wrong in both cases — only one of them is visible to a
    document-level assertion, and it is the one the CI runner hits.

    So these tests block the webfont deliberately. A developer machine with a
    warm font cache would otherwise measure the rounding-down case and call it
    healthy.
    """

    PAGE = None       # resolved per-test: the retrospective edition (No. 14)

    def page_for(self, date):
        return "posts/%s.html" % date

    def worst(self, runs):
        real = [r for r in runs if r["right"] is not None]
        return max(real, key=lambda r: r["right"]) if real else None

    def test_the_fallback_font_path_is_actually_exercised(self):
        """Guards the other tests: if blocking silently stopped working they
        would pass against the webfont and prove nothing."""
        date = self.retrospective[0]
        warm = self.measure(self.page_for(date), 375, SOURCE_DOMAIN_JS)
        cold = self.measure(self.page_for(date), 375, SOURCE_DOMAIN_JS,
                            block_webfonts=True)
        self.assertEqual(0, warm["blockedFontRequests"])
        self.assertGreater(cold["blockedFontRequests"], 0,
                           "no webfont request was intercepted; the fallback "
                           "condition was never established")
        self.assertNotEqual(
            warm["monoWidth"], cold["monoWidth"],
            "the monospace face measured identically with and without the "
            "webfont (%s), so the fallback was not really in use"
            % warm["monoWidth"])

    def test_a_long_domain_does_not_push_the_document_wider_than_the_viewport(self):
        for date in sorted(set(self.retrospective[:1] + sorted(self.control)[-1:])):
            for block in (False, True):
                with self.subTest(page=date, webfonts="blocked" if block else "on"):
                    r = self.measure(self.page_for(date), 375, SOURCE_DOMAIN_JS,
                                     block_webfonts=block)
                    worst = self.worst(r["runs"])
                    self.assertIsNotNone(worst, "%s has no source domains" % date)
                    self.assertFalse(
                        r["overflowX"],
                        "%s at 375px (webfonts %s): document scrollWidth %d "
                        "exceeds clientWidth %d; worst domain run reaches "
                        "%.4f (%+.4f past the viewport): %r"
                        % (date, "blocked" if block else "on", r["scrollW"],
                           r["clientW"], worst["right"], worst["overView"],
                           worst["text"]))
                    self.assertLessEqual(
                        worst["right"], r["clientW"] + 0.5,
                        "%s: a domain run reaches %.4f on a %d-wide viewport"
                        % (date, worst["right"], r["clientW"]))

    def test_every_domain_stays_inside_its_own_card(self):
        for date in sorted(set(self.retrospective[:1] + sorted(self.control)[-1:])):
            r = self.measure(self.page_for(date), 375, SOURCE_DOMAIN_JS,
                             block_webfonts=True)
            for run in r["runs"]:
                if run["right"] is None:
                    continue
                self.assertTrue(
                    run["insideCard"],
                    "%s: %r reaches %.4f but its card ends at %.4f"
                    % (date, run["text"], run["right"], run["cardRight"]))

    def test_the_domain_text_is_complete_visible_and_unclipped(self):
        """The remedy must be wrapping, not hiding. Nothing may be truncated,
        ellipsed, or tucked under a clipping ancestor."""
        for date in sorted(set(self.retrospective[:1] + sorted(self.control)[-1:])):
            r = self.measure(self.page_for(date), 375, SOURCE_DOMAIN_JS,
                             block_webfonts=True)
            self.assertTrue(r["runs"], "%s renders no source domains" % date)
            for run in r["runs"]:
                self.assertTrue(run["visible"],
                                "%s: %r is not visible" % (date, run["text"]))
                self.assertFalse(
                    run["clipped"],
                    "%s: %r sits inside a clipping ancestor, so a wrapped "
                    "second line could be hidden" % (date, run["text"]))
                self.assertNotIn(
                    "\u2026", run["text"],
                    "%s: %r was truncated with an ellipsis" % (date, run["text"]))

    def test_a_long_domain_wraps_rather_than_overhanging(self):
        """The specific failing value, asserted by behaviour: the longest
        domain on the page must occupy more than one line box and still end
        inside the viewport."""
        date = self.retrospective[0]
        r = self.measure(self.page_for(date), 375, SOURCE_DOMAIN_JS,
                         block_webfonts=True)
        worst = self.worst(r["runs"])
        self.assertIsNotNone(worst)
        self.assertGreater(
            worst["lines"], 1,
            "%r fits on one line box at 375px, so this page no longer "
            "exercises the wrapping path and the guard is not measuring "
            "what it claims" % worst["text"])
        self.assertLessEqual(worst["right"], worst["boxRight"] + 0.5,
                             "%r overhangs its own border box: run ends at "
                             "%.4f, box ends at %.4f"
                             % (worst["text"], worst["right"], worst["boxRight"]))


class TestOverflowDiagnosticNamesInlineText(BrowserCase):
    """
    The companion to the wrapping fix.

    Before it, `test_no_weekly_surface_overflows_horizontally` failed on No. 14
    with the message `overflow at 375px: []`. The assertion was correct and the
    diagnostic was useless: it listed element border boxes, every one of which
    fitted, while the overflow came from a text run inside one of them.

    Once the production fix lands the page no longer overflows, so the only
    honest way to keep evidence that the diagnostic works is to restore the
    pre-fix condition and re-measure. `overflow-wrap: normal` is not an
    invented geometry -- it is exactly the declaration `.source-card-domain`
    carried until this change.
    """

    PRE_FIX_CSS = ".source-card-domain { overflow-wrap: normal; }"

    def test_the_fixed_page_reports_no_overflow(self):
        r = self.measure("posts/%s.html" % self.retrospective[0], 375,
                         LAYOUT_JS, block_webfonts=True)
        self.assertFalse(r["overflowX"], overflow_report(r))
        self.assertEqual([], r["textOverflowers"],
                         "nothing should be walked when the document fits")

    def test_restoring_the_pre_fix_rule_names_the_source_domain(self):
        r = self.measure("posts/%s.html" % self.retrospective[0], 375,
                         LAYOUT_JS, block_webfonts=True,
                         extra_css=self.PRE_FIX_CSS)
        self.assertTrue(
            r["overflowX"],
            "restoring overflow-wrap:normal no longer reproduces the overflow, "
            "so this guard is not measuring the defect it documents")
        self.assertEqual(
            [], r["overflowers"],
            "the element-box probe should still find nothing -- that is the "
            "whole reason the inline probe exists")
        self.assertTrue(
            r["textOverflowers"],
            "the inline-text probe reported nothing; the diagnostic would "
            "still print an empty offender list")
        first = r["textOverflowers"][0]
        self.assertIn("source-card-domain", first["el"],
                      "expected the source-trail domain to be named, got %r"
                      % (first,))
        self.assertGreater(first["past"], 0)
        self.assertTrue(first["text"], "the offender was named with no excerpt")
        self.assertLessEqual(len(first["text"]), 60,
                             "the excerpt must stay short enough to read")
        message = overflow_report(r)
        self.assertNotEqual("[]", message)
        self.assertIn("source-card-domain", message)

    def test_the_probe_ignores_text_a_clipping_ancestor_contains(self):
        """No. 13's veil sits ~0.4px past the viewport but `.nd-veil-band`
        clips it, so it cannot grow the scrollable area. Naming it would send
        a reader after the wrong element."""
        for date in sorted(self.posts):
            r = self.measure("posts/%s.html" % date, 375, LAYOUT_JS,
                             block_webfonts=True)
            for t in r["textOverflowers"] or []:
                self.assertNotIn("nd-veil", t["el"],
                                 "%s: clipped veil content was reported" % date)


if __name__ == "__main__":
    unittest.main()
