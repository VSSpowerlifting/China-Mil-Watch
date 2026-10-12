"""
Phase 3C: how an opened article presents its hero image and its neighbours.

The contract is `core.article_media` plus the two shared macros
(`_article_media.html`, `_article_nav.html`), exercised on all 17 published
items: the 14 earlier issues rendered from their sidecars, and the 3 native
Briefs from a disposable build. Nothing here writes to `output/`.
"""
import ast
import contextlib
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site" / "preview"))

import generate_preview as gp                                    # noqa: E402
from core import article_media as am                             # noqa: E402
from core import brief_collection as bc                          # noqa: E402
from core.desk_registry import load_registry                     # noqa: E402
from scripts.historical_brief_render import (next_brief_after,  # noqa: E402
                                             render_historical_brief)
from scripts.rerender_pla_watch import _build_post_context       # noqa: E402

POSTS = ROOT / "output/the-pla-watch/posts"
MEDIA = ROOT / "output/the-pla-watch/media"
TEMPLATES = ROOT / "site/preview/templates"
MANIFEST = ROOT / "site/assets/editorial/manifest.json"

#: Every published item and the treatment its hero takes (Phase 3C audit).
EXPECTED = {
    1: am.PRESERVED,     # legacy edition cover, held by 3B
    2: am.SIGNAL_VEIL, 3: am.SIGNAL_VEIL,
    4: am.PLATE,         # no image: the China Desk's editorial plate
    5: am.SIGNAL_VEIL, 6: am.SIGNAL_VEIL, 7: am.SIGNAL_VEIL,
    8: am.PHOTOGRAPH,    # liaoning-j15-recovery, CC BY 4.0
    9: am.PHOTOGRAPH,    # scarborough-shoal-iss, public domain
    10: am.PRESERVED,    # jin-class-type-094-ssbn, held by 3B
    11: am.SIGNAL_VEIL,
    12: am.PRESERVED,    # src-2026-08-01, B5
    13: am.SIGNAL_VEIL,
    14: am.PLATE,
    15: am.PRESERVED,    # a native brief's own photograph (Phase 0 §1.2)
    16: am.PLATE, 17: am.PLATE,
}

#: Han, kana and CJK punctuation: script that needs a declared language.
CJK = re.compile(r"[\u3000-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef]")

#: The cited article's numeric id and its photograph's, as 81.cn names them.
#: A `_wm…` suffix is the CMS's watermarked rendition of the same asset.
ARTICLE_ID = re.compile(r"/(\d{6,})\.s?html?$")
IMAGE_ID = re.compile(r"/(\d{6,})_[0-9a-f]{16,}(?:_wm[0-9a-f]+)?\.[a-z]+$", re.I)


def hero(soup):
    return soup.select_one("section.brief-hero")


def media_env():
    return Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True,
                       trim_blocks=True, lstrip_blocks=True)


def figure_html(m):
    return media_env().from_string(
        '{% from "_article_media.html" import article_figure %}'
        '{{ article_figure(m) }}').render(m=m)


class ArticleMediaPagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sides = sorted((json.loads(p.read_text()) for p in POSTS.glob("*.json")),
                       key=lambda s: s["date"])
        cls.historical = {}
        with contextlib.redirect_stdout(io.StringIO()):
            bridge = next_brief_after(sides)
            for i, side in enumerate(sides):
                ctx = _build_post_context(side)
                ctx["prev_post"] = sides[i - 1] if i else None
                ctx["next_post"] = sides[i + 1] if i + 1 < len(sides) else None
                page = render_historical_brief(
                    ctx, next_brief=bridge["link"] if bridge and bridge["slug"] == side["date"] else None)
                cls.historical[side["issue_number"]] = (
                    side, ctx, page, BeautifulSoup(page, "html.parser"))

        cls.collection = bc.load_collection(gp.load_editions(ROOT), load_registry(),
                                            briefs_dir=gp.BRIEFS_SOURCE)
        cls.tmp = Path(tempfile.mkdtemp(prefix="article-media-"))
        gp.build(cls.tmp, gp.PUBLIC_TITLE, gp.TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(gp.TRACKED_DB))
        cls.native = {}
        for entry in cls.collection.briefs:
            page = (cls.tmp / "briefs" / ("%s.html" % entry["slug"])).read_text()
            cls.native[entry["issue"]] = (entry, page, BeautifulSoup(page, "html.parser"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_all_seventeen_items_are_covered(self):
        self.assertEqual(sorted(self.historical) + sorted(self.native),
                         sorted(EXPECTED))

    def test_every_earlier_issue_takes_its_recorded_treatment(self):
        for number, (side, ctx, page, soup) in self.historical.items():
            with self.subTest(issue=number):
                veil = ctx.get("pw_veil")
                manifest = ({e["id"]: e for e in json.loads(MANIFEST.read_text())}
                            .get((veil or {}).get("id"), {}))
                kind = am.historical_article_media(
                    veil, ctx.get("cover_media_item"), manifest, root="../../")["kind"]
                self.assertEqual(kind, EXPECTED[number])
                # Without a page root the adapter never invents a plate.
                if kind == am.PLATE:
                    self.assertEqual(am.historical_article_media(
                        veil, ctx.get("cover_media_item"), manifest)["kind"], am.NONE)
                marked = [f["data-article-media"]
                          for f in soup.select("figure[data-article-media]")]
                figures = hero(soup).select("figure")
                if kind in (am.PHOTOGRAPH, am.SIGNAL_VEIL, am.PLATE):
                    self.assertEqual(marked, [kind])
                    self.assertEqual(len(figures), 1)
                else:
                    self.assertEqual(kind, am.PRESERVED)
                    self.assertEqual(marked, [])
                    self.assertEqual(len(figures), 1)
                # Every opened issue now has an image card in its hero.
                self.assertIn("brief-hero--photo", hero(soup)["class"])

    def test_native_briefs_keep_their_photograph_or_carry_a_plate(self):
        for number, (entry, page, soup) in self.native.items():
            with self.subTest(brief=number):
                desks = self.collection.sidecars[entry["slug"]]["desks"]
                media = am.native_article_media(entry.get("photo"), desks, root="../")
                self.assertEqual(media["kind"], EXPECTED[number])
                photo = hero(soup).select("figure.brief-opening-photo")
                plate = hero(soup).select("figure[data-article-media=plate]")
                self.assertEqual(len(photo), 1 if EXPECTED[number] == am.PRESERVED else 0)
                self.assertEqual(len(plate), 1 if EXPECTED[number] == am.PLATE else 0)
                self.assertEqual(len(soup.select("figure[data-article-media]")), len(plate))
                self.assertIn("brief-hero--photo", hero(soup)["class"])
                if plate:
                    uses = [u["href"] for u in plate[0].select("use")]
                    self.assertEqual(uses, ["../assets/geo/region.svg#region"] + [
                        "../assets/geo/region.svg#region-%s" % d
                        for d in desks if d in am.PLATE_DESKS])

    def test_every_plate_is_labelled_decorative_original_artwork(self):
        pages = ([(n, soup) for n, (_, _, _, soup) in self.historical.items()]
                 + [(n, soup) for n, (_, _, soup) in self.native.items()])
        plated = []
        for number, soup in pages:
            plate = soup.select_one("figure[data-article-media=plate]")
            if plate is None:
                continue
            plated.append(number)
            with self.subTest(item=number):
                self.assertEqual(plate.select("img, a"), [])
                self.assertEqual(plate.svg["aria-hidden"], "true")
                self.assertEqual(plate.svg["viewbox"], am.PLATE_VIEWBOX)
                self.assertEqual(plate.figcaption.get_text(" ", strip=True).split(" · ", 1)[0],
                                 "Editorial plate")
                for text in (am.PLATE_NOTE, am.PLATE_CONTEXT):
                    self.assertIn(text, plate.figcaption.get_text())
        self.assertEqual(sorted(plated), [4, 14, 16, 17])
        # A historical plate is the China Desk's, the desk that published them.
        for number in (4, 14):
            uses = [u["href"] for u in self.historical[number][3].select("figure[data-article-media=plate] use")]
            self.assertEqual(uses, ["../../assets/geo/region.svg#region",
                                    "../../assets/geo/region.svg#region-china"])

    def test_plate_art_is_the_receipted_regional_relief(self):
        receipt = json.loads((ROOT / "site/assets/geo/geo.receipt.json").read_text())
        self.assertEqual(receipt["symbols"]["region"], am.PLATE_VIEWBOX)
        svg = (ROOT / "site/assets" / am.PLATE_ART.split("/", 1)[1]).read_text()
        for symbol in ("region",) + tuple("region-" + d for d in am.PLATE_DESKS):
            self.assertIn('id="%s" viewBox="%s"' % (symbol, am.PLATE_VIEWBOX), svg)

    def test_held_figures_are_byte_for_byte_what_was_published(self):
        for number in (1, 10, 12):
            with self.subTest(issue=number):
                side, ctx, page, soup = self.historical[number]
                published = BeautifulSoup((POSTS / ("%s.html" % side["date"])).read_text(),
                                          "html.parser")
                self.assertEqual(str(hero(soup).select_one("figure")),
                                 str(hero(published).select_one("figure")))

    def test_signal_veil_image_is_the_cited_articles_own(self):
        for number, (side, ctx, page, soup) in self.historical.items():
            if EXPECTED[number] != am.SIGNAL_VEIL:
                continue
            with self.subTest(issue=number):
                record = json.loads((MEDIA / ("%s-source-image.json" % side["date"])).read_text())
                article = ARTICLE_ID.search(record["article_url"])
                image = IMAGE_ID.search(record["image_url"])
                self.assertIsNotNone(article)
                self.assertIsNotNone(image, record["image_url"])
                self.assertEqual(article.group(1), image.group(1))
                figure = soup.select_one("figure[data-article-media]")
                self.assertEqual([a["href"] for a in figure.select("a")],
                                 [record["article_url"]])
                self.assertEqual(figure.select_one(".article-media-kind").get_text(),
                                 "Signal Veil")

    def test_no_collector_note_reaches_any_page(self):
        notes = [json.loads(p.read_text()).get("note") or ""
                 for p in MEDIA.glob("*-source-image.json")]
        pages = ([page for _, _, page, _ in self.historical.values()]
                 + [page for _, page, _ in self.native.values()])
        for page in pages:
            self.assertNotIn("Downloaded from", page)
            for note in filter(None, notes):
                self.assertNotIn(note, page)

    def test_no_12_never_credits_the_publisher_its_legacy_note_names(self):
        side, ctx, page, soup = self.historical[12]
        record = json.loads((MEDIA / "2026-08-01-source-image.json").read_text())
        self.assertIn("PLA Daily", record["note"])   # the mismatch this guards
        figure = hero(soup).select_one("figure")
        self.assertFalse(figure.has_attr("data-article-media"))
        self.assertEqual([a["href"] for a in figure.select("a")], [record["article_url"]])
        for name in ("81.cn", "PLA Daily", "解放军报"):
            self.assertNotIn(name, figure.get_text())
            self.assertNotIn(name, str(figure))

    def test_photographs_carry_full_credit_licence_and_change_note(self):
        manifest = {e["id"]: e for e in json.loads(MANIFEST.read_text())}
        for number, veil_id in ((8, "liaoning-j15-recovery"), (9, "scarborough-shoal-iss")):
            with self.subTest(issue=number):
                entry = manifest[veil_id]
                figure = self.historical[number][3].select_one("figure[data-article-media]")
                caption = figure.figcaption.get_text()
                self.assertEqual(figure["data-editorial-id"], veil_id)
                for segment in entry["credit"].split(" · "):
                    self.assertIn(segment, caption)
                self.assertIn(am.CHANGE_NOTE, caption)
                self.assertIn(am.CONTEXT_NOTE, caption)
                self.assertIn(entry["source_page"], [a["href"] for a in figure.select("a")])
        licence = self.historical[8][3].select_one("figure[data-article-media] a[rel~=license]")
        self.assertEqual(licence["href"], "https://creativecommons.org/licenses/by/4.0")
        self.assertEqual(licence.get_text(), "CC BY 4.0")
        # A licence without a recorded deed is named, not linked.
        self.assertIsNone(self.historical[9][3].select_one("figure a[rel~=license]"))

    def test_native_script_in_a_photograph_credit_declares_its_language(self):
        # No. 8's credit names the Joint Staff in Japanese. Only that name is
        # tagged, from the manifest's recorded language; no script is guessed.
        figure = self.historical[8][3].select_one("figure[data-article-media=photograph]")
        tagged = figure.figcaption.select("[lang]")
        self.assertEqual([(t.name, t["lang"], t.get_text()) for t in tagged],
                         [("span", "ja", "統合幕僚監部")])
        self.assertIn("Japan Ministry of Defense, Joint Staff (統合幕僚監部)",
                      figure.figcaption.get_text())
        for number, (_, _, _, soup) in self.historical.items():
            for fig in soup.select("figure[data-article-media=photograph]"):
                with self.subTest(issue=number):
                    for text in fig.figcaption.find_all(string=CJK):
                        self.assertIsNotNone(text.find_parent(attrs={"lang": True}),
                                             "untagged script in credit: %r" % str(text))

    def test_historical_issue_links_follow_the_sidecar_order(self):
        numbers = sorted(self.historical)
        for number in numbers:
            with self.subTest(issue=number):
                nav = self.historical[number][3].select_one("nav.brief-issue-nav.historical-issue-nav")
                prev, nxt = nav.select_one("a[rel=prev]"), nav.select_one("a[rel=next]")
                self.assertEqual(prev is None, number == numbers[0])
                self.assertIsNotNone(nxt)
                if number == numbers[-1]:
                    # The newest issue's next item is the first native Brief.
                    self.assertEqual(nxt["href"], "../../briefs/maritime-cooperation-2026.html")
                    self.assertIn("No. %d" % (number + 1), nxt.get_text())
                    nxt = None
                for link, other in ((prev, number - 1), (nxt, number + 1)):
                    if link is None:
                        continue
                    self.assertTrue((POSTS / link["href"]).is_file(), link["href"])
                    self.assertIn("No. %d" % other, link.get_text())
                    self.assertNotIn("The PLA Watch", link.select_one(".brief-issue-nav-title").get_text())

    def test_native_issue_links_reach_published_pages(self):
        for number, (entry, page, soup) in self.native.items():
            with self.subTest(brief=number):
                nav = soup.select_one("nav.brief-issue-nav")
                for link in nav.select("a[rel=prev], a[rel=next]"):
                    target = (ROOT / "output/briefs" / link["href"]).resolve()
                    built = (self.tmp / "briefs" / link["href"]).resolve()
                    self.assertTrue(target.is_file() or built.is_file(), link["href"])
        prev15 = self.native[15][2].select_one("nav.brief-issue-nav a[rel=prev]")
        self.assertEqual(prev15["href"], "../the-pla-watch/posts/2026-08-15.html")
        self.assertIn("No. 14", prev15.get_text())
        self.assertIsNone(self.native[17][2].select_one("nav.brief-issue-nav a[rel=next]"))

    def test_historical_pages_carry_their_own_nav_and_media_rules(self):
        # A rerendered issue can be published before briefs.css changes.
        for number, (side, ctx, page, soup) in self.historical.items():
            with self.subTest(issue=number):
                style = soup.select_one("style").get_text()
                self.assertIn(".brief-issue-nav{", style)
                self.assertIn(".article-media-kind{", style)
        css = (ROOT / "site/preview/briefs.css").read_text()
        self.assertIn(".brief-issue-nav{", css)
        self.assertIn(".article-media-kind{", css)


class ArticleMediaAdapterTests(unittest.TestCase):
    SOURCE = {"kind": "source", "id": "src-x", "duo": "x.jpg", "alt": "Alt",
              "mask_focus": "50% 40%", "subject": "Subject", "source_id": "src-x",
              "source_page": "https://www.81.cn/a/16400000.html",
              "credit": "Downloaded from PLA Daily / 81.cn source article"}
    CURATED = {"kind": "curated", "id": "pic", "duo": "p.jpg", "alt": "Alt",
               "subject": "", "source_page": "https://commons.wikimedia.org/wiki/File:P.jpg",
               "license": "CC BY 4.0",
               "credit": "Someone · CC BY 4.0 · via Wikimedia Commons"}

    def test_the_module_never_reads_catalogue_admissions(self):
        tree = ast.parse((ROOT / "core/article_media.py").read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported.update(a.name for a in node.names)
        self.assertFalse([n for n in imported if "catalogue" in n], imported)

    def test_a_source_veil_never_carries_its_collector_note(self):
        m = am.historical_article_media(self.SOURCE)
        self.assertEqual(m["kind"], am.SIGNAL_VEIL)
        self.assertNotIn("credit", m)
        self.assertNotIn("Downloaded", figure_html(m))

    def test_held_and_unknown_veils_keep_their_markup(self):
        for held in am.PRESERVED_MEDIA:
            self.assertEqual(am.historical_article_media(dict(self.CURATED, id=held))["kind"],
                             am.PRESERVED)
        self.assertEqual(am.historical_article_media(dict(self.SOURCE, kind="other"))["kind"],
                         am.PRESERVED)
        self.assertEqual(am.historical_article_media(None, {"src": "c.jpg"})["kind"],
                         am.PRESERVED)
        self.assertEqual(am.historical_article_media(None, {"src": ""})["kind"], am.NONE)

    def test_a_licence_deed_is_read_only_from_the_veils_own_entry(self):
        other = {"id": "someone-else", "license_url": "https://example.test/deed"}
        m = am.historical_article_media(self.CURATED, manifest_entry=other)
        self.assertFalse([p for p in m["credit"] if p["href"] == other["license_url"]])
        own = {"id": "pic", "license_url": "https://creativecommons.org/licenses/by/4.0"}
        m = am.historical_article_media(self.CURATED, manifest_entry=own)
        self.assertIn("license noopener nofollow", [p["rel"] for p in m["credit"]])

    def test_credit_parts_keep_every_word_and_link_licence_and_source(self):
        parts = am.credit_parts("Someone · CC BY 4.0 · via Wikimedia Commons",
                                license_name="CC BY 4.0",
                                license_url="https://creativecommons.org/licenses/by/4.0",
                                source_page="https://commons.wikimedia.org/wiki/File:P.jpg")
        self.assertEqual([p["before"] + p["text"] for p in parts],
                         ["Someone", "CC BY 4.0", "via Wikimedia Commons"])
        self.assertEqual([p["href"] for p in parts],
                         [None, "https://creativecommons.org/licenses/by/4.0",
                          "https://commons.wikimedia.org/wiki/File:P.jpg"])
        self.assertEqual(parts[1]["rel"], "license noopener nofollow")

    def test_credit_parts_add_only_a_source_link_when_no_host_is_named(self):
        parts = am.credit_parts("NASA · Public domain", license_name="Public domain",
                                source_page="https://example.test/p")
        self.assertEqual([p["text"] for p in parts], ["NASA", "Public domain", "Source"])
        self.assertEqual([p["href"] for p in parts], [None, None, "https://example.test/p"])
        self.assertEqual(am.credit_parts(""), [])

    def test_credit_parts_tag_only_a_recorded_native_name(self):
        credit = "Joint Staff (統合幕僚監部) · CC BY 4.0"
        parts = am.credit_parts(credit, native="統合幕僚監部", native_lang="ja")
        self.assertEqual(parts[0]["native"], {"pre": "Joint Staff (", "text": "統合幕僚監部",
                                              "lang": "ja", "post": ")"})
        self.assertEqual(parts[0]["text"], "Joint Staff (統合幕僚監部)")
        html = figure_html({**am.historical_article_media(dict(self.CURATED, credit=credit), None,
                            {"id": "pic", "credit_native": "統合幕僚監部",
                             "credit_native_lang": "ja"}), "src": "p.jpg"})
        self.assertIn('Joint Staff (<span lang="ja">統合幕僚監部</span>)', html)
        # No language recorded, absent, or ambiguous: nothing is tagged.
        for native, lang, text in (("統合幕僚監部", "", credit), ("幕僚", "ja", "幕僚 幕僚"),
                                   ("海上幕僚監部", "ja", credit)):
            self.assertTrue(all(p["native"] is None for p in
                                am.credit_parts(text, native=native, native_lang=lang)))

    def test_manifest_native_names_come_from_the_recorded_creator(self):
        for entry in json.loads(MANIFEST.read_text()):
            credit = entry.get("credit") or ""
            with self.subTest(entry=entry["id"]):
                if not CJK.search(credit):
                    self.assertNotIn("credit_native", entry)
                    continue
                native = entry["credit_native"]
                self.assertEqual(credit.count(native), 1)
                self.assertIn(native, entry["creator"])
                self.assertEqual(entry["credit_native_lang"], "ja")
                self.assertFalse(CJK.search(credit.replace(native, "")))

    def test_an_editorial_plate_is_decorative_and_labelled(self):
        plate = am.editorial_plate("../", ("singapore", "unknown", "china"))
        self.assertEqual(plate["desks"], ("singapore", "china"))
        figure = BeautifulSoup(figure_html(plate), "html.parser").select_one("figure")
        self.assertEqual(figure["data-article-media"], "plate")
        self.assertFalse(figure.has_attr("aria-label"))
        self.assertFalse(figure.has_attr("data-editorial-id"))
        self.assertEqual(figure.select("img, a"), [])
        self.assertEqual(figure.svg["aria-hidden"], "true")
        self.assertEqual(figure.svg["focusable"], "false")
        self.assertEqual([u["href"] for u in figure.select("use")],
                         ["../assets/geo/region.svg#region",
                          "../assets/geo/region.svg#region-singapore",
                          "../assets/geo/region.svg#region-china"])
        caption = figure.figcaption.get_text()
        for text in ("Editorial plate", am.PLATE_NOTE, am.PLATE_CONTEXT):
            self.assertIn(text, caption)

    def test_a_plate_never_replaces_an_image(self):
        cover = {"src": "cover.jpg"}
        for veil, cover_item, kind in ((self.SOURCE, None, am.SIGNAL_VEIL),
                                       (self.CURATED, None, am.PHOTOGRAPH),
                                       ({"id": "src-2026-08-01", "kind": "source"}, None, am.PRESERVED),
                                       (None, cover, am.PRESERVED)):
            self.assertEqual(am.historical_article_media(veil, cover_item, root="../../")["kind"], kind)
        self.assertEqual(am.native_article_media({"src": "p.jpg"}, ("china",), root="../")["kind"],
                         am.PRESERVED)
        self.assertEqual(am.native_article_media(None, ("china",))["kind"], am.NONE)

    def test_no_image_and_held_images_render_nothing_from_the_macro(self):
        for m in ({"kind": am.NONE}, {"kind": am.PRESERVED, "reason": "held"}):
            self.assertEqual(figure_html(m).strip(), "")


class CollectionNeighbourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.collection = bc.load_collection(gp.load_editions(ROOT), load_registry(),
                                            briefs_dir=gp.BRIEFS_SOURCE)

    def test_neighbours_follow_publication_order(self):
        rows = self.collection.rows
        for brief in self.collection.briefs:
            at = next(i for i, r in enumerate(rows)
                      if r["kind"] == "brief" and r["entry"]["slug"] == brief["slug"])
            adj = bc.adjacent_items(self.collection, brief["slug"])
            older = rows[at + 1]["entry"] if at + 1 < len(rows) else None
            newer = rows[at - 1]["entry"] if at > 0 else None
            self.assertEqual((adj["previous"] or {}).get("date"), (older or {}).get("date"))
            self.assertEqual((adj["next"] or {}).get("date"), (newer or {}).get("date"))

    def test_an_unknown_slug_has_no_neighbours(self):
        self.assertEqual(bc.adjacent_items(self.collection, "not-a-brief"),
                         {"previous": None, "next": None})

    def test_display_title_drops_only_the_former_masthead(self):
        for prefix in bc.SERIES_TITLE_PREFIXES:
            self.assertEqual(bc.display_title(prefix + "Week"), "Week")
        self.assertEqual(bc.display_title("Readout: The PLA Watch: x"),
                         "Readout: The PLA Watch: x")
        self.assertEqual(bc.display_title(None), "")


if __name__ == "__main__":
    unittest.main()
