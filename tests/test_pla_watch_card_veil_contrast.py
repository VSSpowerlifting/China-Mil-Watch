"""
The latest-edition card's own text, over the Signal Veil that sits under it.

Why this file exists. `tests/test_pla_watch_veil_contrast.py` measures the
article hero band. The index card carries the same photograph, but every index
render in the suite passes `latest_veil=None` (test_pla_watch_reading_ergonomics,
test_pla_watch_chrome_render), so nothing measured the card with a veil under
it. On No. 14, the first edition whose veil reaches the card in a while, the
dek measured 2.96:1, the retrospective badge 2.88:1, the source-trail label
3.81:1 and the "model-flagged" stat 3.49:1 on composited pixels, against 6.77,
5.82, 4.83 and 4.83 for the same card without a veil.

Method. The repo's own glyph-pixel algorithm (`ContrastMixin.band_contrasts`),
unchanged: screenshot the card, screenshot it again with every glyph made
transparent, and take the 2nd-percentile contrast of the backdrop pixels behind
each glyph core. Only the element whose text runs are collected differs, and it
is swapped in for the duration of one call, never assigned to the module.

Two assertions, deliberately different:
  1. The four roles this fix is about must clear the governed floor (4.65:1,
     the same number the hero holds) at every sampled width.
  2. No text run may be made worse by the veil than the same card measures
     without one. That is what catches a regression on a role nobody named,
     and it does not ask pre-existing sub-floor runs (the "Latest Edition"
     eyebrow at 2.48:1 and the "Significant" badge at 4.56:1 on main, both
     with no veil at all) to pass a bar they never met. Those are a separate
     ruling, not this test's to settle.

The render is the production one: `generate_pla_watch.render_index`, which
resolves the veil through `veil_for_edition`, into a tree shaped like
`output/` so the real photographs load.

Scope, stated so it is not mistaken for coverage. This pins No. 14, the
edition the card carries today, at the widths that bracket each card regime.
It does not gate every photograph in the tree. Measured with the same card CSS,
the other eleven editions' photographs would leave the source-trail label or
the dek under 4.65:1 in 10 of 22 (edition, width) cells (worst: No. 13's trail
label at 375px, 2.98:1). That gap is not new: those cards had it when each was
the latest edition. It is a property of putting a photograph under the title
column, and it is recorded here so the next edition's card is measured, not
assumed.
"""

import unittest
from unittest import mock

import tests.test_pla_watch_veil_contrast as vc    # the module, not its classes:
                                                    # `from` would rediscover them here

FLOOR = vc.CONTRAST_FLOOR                # 4.65, governed
REGRESSION_SLACK = 0.10                  # rasteriser noise between two renders
# The card has three regimes: <=700px (the mobile mask), 701-900px (the desktop
# mask running across a narrow card, the range the hero also had trouble in) and
# 901px up. 375/700, 720/768/820 and 1024/1440 sample each; 820 is where the
# eyebrow date line fell to 4.07:1 before it was given its own ink.
WIDTHS = (375, 700, 720, 768, 820, 1024, 1440)
FOCUS_DATE = "2026-08-15"                # No. 14

CARD_RUNS_JS = r"""
() => {
  const card = document.querySelector('.issue-cover');
  if (!card) return null;
  const runs = [];
  const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (!node.textContent.trim()) continue;
    const el = node.parentElement;
    if (!el) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const rects = [...range.getClientRects()].filter(r => r.width > 1 && r.height > 1);
    if (!rects.length) continue;
    const size = parseFloat(cs.fontSize);
    const weight = parseInt(cs.fontWeight) || 400;
    const cls = el => (typeof el.className === 'string' && el.className.trim()) || '';
    runs.push({
      // The full class list, and the parent's when the element has none, so the
      // two badges and the bold count inside the trail label stay distinguishable.
      label: cls(el) || (el.tagName + '<' + cls(el.parentElement)),
      text: node.textContent.trim().slice(0, 48),
      color: cs.color,
      sizePx: size,
      isLarge: size >= 24 || (size >= 18.66 && weight >= 700),
      rects: rects.map(r => ({x: r.x, y: r.y, w: r.width, h: r.height})),
    });
  }
  const b = card.getBoundingClientRect();
  return {runs, band: {x: b.x, y: b.y, w: b.width, h: b.height}};
}
"""

# Same neutralising rule as the hero measurement, aimed at the card.
CARD_HIDE_GLYPHS_CSS = """
.issue-cover, .issue-cover * {
  color: transparent !important;
  text-shadow: none !important;
  -webkit-text-stroke: 0 !important;
  text-decoration-color: transparent !important;
}
"""


def role_of(run):
    """The named role a text run plays, or None. The four this fix is about."""
    label, text = run["label"], run["text"]
    if "issue-cover-dek" in label:
        return "dek"
    if "pw-badge--retrospective" in label:
        return "retrospective badge"
    if "nd-tickrow-label" in label:
        return "source-trail label"          # the sentence and the bold count
    if label == "stat" and "model-flagged" in text:
        return "model-flagged label"
    return None


class TestLatestEditionCardTextOverTheVeil(vc.BrowserVeilCase, vc.ContrastMixin):
    """Renders the card as the latest edition, with and without its veil."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()                 # renders the posts, serves cls.tmp, starts chromium
        try:
            import scripts.generate_pla_watch as gen
            from scripts.pw_env import make_pw_env
        except Exception as exc:             # pragma: no cover
            super().tearDownClass()
            raise unittest.SkipTest("index renderer unavailable: %s" % exc)

        template = make_pw_env().get_template("pla-watch-index.html")
        if FOCUS_DATE not in cls.posts:      # pragma: no cover
            super().tearDownClass()
            raise unittest.SkipTest("No. 14's sidecar is not in the tree")
        sidecar = cls.posts[FOCUS_DATE]["sidecar"]
        here = cls.tmp / "the-pla-watch"
        # `render_index` takes the first post as the latest one and resolves its
        # veil exactly as production does; the plain card is the same template
        # with the veil withheld, which is what every other test in the suite
        # renders.
        cls.veiled_html = gen.render_index([sidecar])
        plain = template.render(latest_post=sidecar, archive_posts=[],
                                root_path="../", latest_veil=None)
        (here / "card-veil.html").write_text(cls.veiled_html, encoding="utf-8")
        (here / "card-plain.html").write_text(plain, encoding="utf-8")
        cls._measured = {}

    def url(self, key):
        return "http://127.0.0.1:%d/the-pla-watch/%s.html" % (self.port, key)

    def card_runs(self, key, width):
        """One measurement per (page, width) for the whole class."""
        if (key, width) not in self._measured:
            with mock.patch.object(vc, "COLLECT_RUNS_JS", CARD_RUNS_JS), \
                    mock.patch.object(vc, "HIDE_GLYPHS_CSS", CARD_HIDE_GLYPHS_CSS):
                self._measured[(key, width)] = self.band_contrasts(key, width)
        return self._measured[(key, width)]

    # ── the premise ─────────────────────────────────────────────────────────

    def test_the_card_really_carries_the_veil_under_test(self):
        # A measurement of a card with no photograph under it proves nothing,
        # which is exactly how the gap this file closes went unseen.
        self.assertIn('<div class="card-veil"', self.veiled_html,
                      "No. 14's index card renders no veil; the measurements "
                      "below would be of a text-led card")
        self.assertIn("issue-cover--veil", self.veiled_html)
        self.assertIn('class="card-veil-credit"', self.veiled_html)

    # ── 1. the named roles ──────────────────────────────────────────────────

    def test_named_roles_clear_the_governed_floor_over_the_veil(self):
        failures, seen = [], set()
        for width in WIDTHS:
            runs = self.card_runs("card-veil", width)
            self.assertIsNotNone(runs, "no card at %dpx" % width)
            for run in runs:
                role = role_of(run)
                if role is None:
                    continue
                seen.add(role)
                if run["ratio"] < FLOOR:
                    failures.append("@%dpx  %-20s %.2f:1  %r"
                                    % (width, role, run["ratio"], run["text"]))
        # The roles must actually have been found, or a renamed class would turn
        # this into a test of nothing.
        for role in ("dek", "retrospective badge", "source-trail label",
                     "model-flagged label"):
            self.assertIn(role, seen, "no text run matched the %r role" % role)
        self.assertEqual([], failures,
                         "No. 14 card text below the %.2f:1 governed floor with "
                         "the veil present:\n  %s"
                         % (FLOOR, "\n  ".join(failures[:24])))

    # ── 2. nothing is made worse ────────────────────────────────────────────

    def test_the_veil_makes_no_card_text_worse_than_the_same_card_without_one(self):
        worse = []
        for width in WIDTHS:
            with_veil = self.card_runs("card-veil", width)
            without = self.card_runs("card-plain", width)
            self.assertIsNotNone(with_veil)
            self.assertIsNotNone(without)
            base = {}
            for run in without:
                key = (run["label"], run["text"])
                base[key] = min(run["ratio"], base.get(key, 99.0))
            for run in with_veil:
                key = (run["label"], run["text"])
                if key not in base:
                    continue              # the credit line exists only with a veil
                allowed = min(FLOOR, base[key] - REGRESSION_SLACK)
                if run["ratio"] < allowed:
                    worse.append("@%dpx  %s %r  %.2f:1 over the veil vs %.2f:1 without"
                                 % (width, run["label"], run["text"],
                                    run["ratio"], base[key]))
        self.assertEqual([], worse,
                         "the veil lowers card text below what the card reads "
                         "without it:\n  %s" % "\n  ".join(worse[:24]))

    # ── the veil must not swallow the card's own controls ───────────────────

    def test_title_buttons_and_credit_still_receive_their_own_clicks(self):
        # Nothing here paints over the card, but the hero shipped this exact bug
        # (b384eaa) when a later layer landed above a link.
        probe = r"""
        () => {
          const pick = s => document.querySelector(s);
          const hit = el => {
            if (!el) return 'missing';
            const r = el.getBoundingClientRect();
            const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
            return top && (top === el || el.contains(top)) ? 'ok' : 'covered by ' + (top ? top.className || top.tagName : 'nothing');
          };
          const btns = [...document.querySelectorAll('.issue-cover-actions a')];
          return {
            title: hit(pick('.issue-cover-title a')),
            primary: hit(btns[0]), ghost: hit(btns[1]),
            credit: hit(pick('.card-veil-credit a')),
          };
        }
        """
        for width in (375, 1440):
            ctx, page = self.page("card-veil", width)
            try:
                page.evaluate("() => document.querySelector('.issue-cover').scrollIntoView()")
                result = page.evaluate(probe)
            finally:
                ctx.close()
            self.assertEqual({k: "ok" for k in result}, result,
                             "at %dpx a card control is covered: %s" % (width, result))


if __name__ == "__main__":
    unittest.main()
