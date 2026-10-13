"""Phase 4A browser gate for the actual rendered eight-desk directory.

A source-only browser contract. It builds into a disposable folder, reads the
tracked DB through the renderer's safe path, and never touches output/ or CI
production state. Captures geometry; it does not declare aesthetic sign-off.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site" / "preview"))
import generate_preview as gp  # noqa: E402

DB = ROOT / "pla_watch.db"
WIDTHS = (320, 375, 768, 900, 1100, 1280, 1480, 1600)

# Evaluate DOM layout, not an estimated static geometry. Only visible labels
# and plates enter collision checks; a country may be hidden at small widths
# because the complete accessible directory remains immediately below it.
PROBE = r"""() => {
  const bbox = el => {
    const b = el.getBoundingClientRect();
    return {name:el.dataset.desk || el.textContent.trim(),
      left:b.left,top:b.top,right:b.right,bottom:b.bottom,
      width:b.width,height:b.height};
  };
  const overlap = (a,b) => a.left < b.right - .75 &&
    b.left < a.right - .75 && a.top < b.bottom - .75 &&
    b.top < a.bottom - .75;
  const visible = el => {
    const s=getComputedStyle(el), b=el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0;
  };
  const cards=[...document.querySelectorAll('.deskmap-register .deskmap-plate')].filter(visible).map(bbox);
  const labels=[...document.querySelectorAll('.dm-label')].filter(visible).map(bbox);
  const overlaps=[];
  for(let i=0;i<cards.length;i++) for(let j=i+1;j<cards.length;j++)
    if(overlap(cards[i],cards[j])) overlaps.push(cards[i].name+'/'+cards[j].name);
  const labelHits=[];
  for(let i=0;i<labels.length;i++) for(let j=i+1;j<labels.length;j++)
    if(overlap(labels[i],labels[j])) labelHits.push(labels[i].name+'/'+labels[j].name);
  if(innerWidth >= 1480) for(const c of cards) for(const l of labels)
    if(overlap(c,l)) labelHits.push(c.name+' covers '+l.name);
  return {
    width:innerWidth,docWidth:document.documentElement.scrollWidth,
    cards:cards.length,unplaced:document.querySelectorAll('.deskmap-plate.is-unplaced').length,
    countries:[...document.querySelectorAll('.dm-country')].map(x=>x.dataset.desk),
    overlaps,labelHits,
    outside:cards.filter(c=>c.left < -.75 || c.right > innerWidth+.75).map(c=>c.name)
  };
}"""

class DeskMapResponsiveBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DB.is_file():
            raise unittest.SkipTest("tracked DB unavailable")
        cls.tmp = Path(tempfile.mkdtemp(prefix="ipr-phase4a-browser-"))
        cls.out = cls.tmp / "preview"
        try:
            gp.build(cls.out, "Indo-Pacific Record", DB,
                     snapshot=gp.snapshot_from_corpus(DB))
            cls.playwright = sync_playwright().start()
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception:
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "browser"):
            cls.browser.close()
        if hasattr(cls, "playwright"):
            cls.playwright.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_map_card_geometry_and_desktop_labels(self):
        for width in WIDTHS:
            with self.subTest(width=width):
                page = self.browser.new_page(viewport={"width":width,"height":900},
                                             reduced_motion="reduce")
                try:
                    page.goto((self.out / "desks.html").as_uri(), wait_until="load")
                    result = page.evaluate(PROBE)
                    self.assertEqual(result["cards"], 7, result)
                    self.assertEqual(result["unplaced"], 1, result)
                    self.assertNotIn("us-indopacific", result["countries"], result)
                    self.assertFalse(result["overlaps"], result)
                    self.assertFalse(result["labelHits"], result)
                    self.assertFalse(result["outside"], result)
                    self.assertLessEqual(result["docWidth"], width+1, result)
                finally:
                    page.close()

    def test_all_flag_tabs_really_load_in_the_public_build(self):
        page = self.browser.new_page(viewport={"width":375,"height":812})
        try:
            page.goto((self.out / "desks.html").as_uri(), wait_until="load")
            flags = page.locator(".deskmap-flag-tab img")
            self.assertEqual(flags.count(), 8)
            images = flags.evaluate_all(
                "(nodes) => nodes.map(n => ({src:n.getAttribute('src'), "
                "complete:n.complete, naturalWidth:n.naturalWidth}))"
            )
            self.assertTrue(all(i["complete"] and i["naturalWidth"] > 0
                                for i in images), images)
            self.assertTrue((self.out / "assets/flags/LICENSE").is_file())
        finally:
            page.close()

    def test_no_javascript_still_exposes_every_public_desk(self):
        context = self.browser.new_context(viewport={"width":375,"height":812},
                                           java_script_enabled=False)
        page = context.new_page()
        try:
            page.goto((self.out / "desks.html").as_uri(), wait_until="load")
            self.assertEqual(page.locator(".deskmap-plate").count(), 8)
            self.assertEqual(page.locator('.deskmap-plate h2 a').count(), 8)
            self.assertTrue(page.locator(".deskmap-controls").is_hidden())
            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 376)
        finally:
            context.close()

    def test_selection_and_forced_color_readability(self):
        page=self.browser.new_page(viewport={"width":1280,"height":900},
                                   forced_colors="active",reduced_motion="reduce")
        try:
            page.goto((self.out / "desks.html").as_uri(), wait_until="load")
            button=page.locator('[data-select-desk="singapore"]').first
            button.click()
            self.assertEqual(button.get_attribute("aria-pressed"), "true")
            self.assertTrue(page.locator('.deskmap-context-entry[data-context-desk="singapore"]').is_visible())
            self.assertEqual(page.locator(".deskmap-plate.is-selected").count(), 1)
        finally:
            page.close()

if __name__ == "__main__":
    unittest.main()
