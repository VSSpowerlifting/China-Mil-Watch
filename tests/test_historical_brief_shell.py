"""Current-shell consolidation must preserve real historical edition evidence."""
import copy
import hashlib
import json
import functools
import http.server
import re
import shutil
import socketserver
import tempfile
import threading
from pathlib import Path
import unittest
import unittest.mock

from bs4 import BeautifulSoup
from markupsafe import escape

from core.article_media import (CHANGE_NOTE, CONTEXT_NOTE, PLATE_ART, PLATE_NOTE,
                                PLATE_CONTEXT, PLATE_VIEWBOX, PRESERVED_MEDIA)
from scripts.historical_brief_render import (next_brief_after, render_historical_brief,
                                             render_historical_utility, SECTIONS)
from scripts.pw_env import format_date, inline_markup, make_pw_env
from scripts.rerender_pla_watch import _build_post_context, _flatten_term

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "output/the-pla-watch/posts"

# Temporary, until the owner's governed rerender of the earlier issues
# (`scripts/rerender_pla_watch.py --no-covers`). Until then the checked-in
# pages carry the pre-3C form. The checked-in page is never edited: the
# current render alone is turned back into the exact pre-3C form, one counted
# replacement per known Phase 3C change, and every other byte must match.
# Each replacement is rebuilt from the issue's own context, so a changed image
# source, alt text, caption source, citation or held figure still fails.
# Once the rerendered pages carry PHASE_3C_MARKER the comparison is strict
# byte equality with no transform at all.
PHASE_3C_MARKER = "brief-issue-nav-label"
_TEMPLATE = (ROOT / "site/preview/templates/historical-brief.html").read_text()
_3C_STYLE = _TEMPLATE[_TEMPLATE.index("/* Phase 3C."):
                      _TEMPLATE.index("@media print{.brief-issue-nav{display:none}")
                      + len("@media print{.brief-issue-nav{display:none}")]
_PRE_3C_NAV_STYLE = (".historical-issue-nav{display:flex;justify-content:space-between;flex-wrap:wrap;gap:1rem;margin:2rem 0}\n"
                     ".historical-issue-nav a{min-height:44px;display:inline-flex;align-items:center}\n")
_NAV_ANCHOR = ".brief-citation{overflow-wrap:anywhere;font:15px/1.8 var(--sans)}\n"
_NAV = re.compile(r'    <nav class="brief-issue-nav historical-issue-nav" aria-label="Adjacent historical issues">\n.*?</nav>\n', re.S)
_MODEL_FLAG = '<span class="evidence evidence--model">Model-flagged</span>'


def _plate_block(desks=("china",)):
    art = "../../" + PLATE_ART
    uses = "".join(f'<use href="{art}#region-{d}"/>' for d in desks)
    return ('    <figure class="article-plate" data-article-media="plate">\n'
            f'      <svg class="article-plate-art" viewBox="{PLATE_VIEWBOX}" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false"><use href="{art}#region"/>{uses}</svg>\n'
            f'      <figcaption><span class="article-media-kind">Editorial plate</span> · {PLATE_NOTE} {PLATE_CONTEXT}</figcaption>\n'
            '    </figure>\n')


def _once(page, old, new):
    if page.count(old) != 1:
        raise AssertionError(f"expected exactly one Phase 3C change: {old[:60]!r}")
    return page.replace(old, new, 1)


def _as_published_before_3c(page, ctx, bridge_href=None):
    """The current render in its exact pre-3C form (see PHASE_3C_MARKER)."""
    head, end, body = page.partition("</style>")
    head = _once(head, _3C_STYLE, "@media print{")
    head = _once(head, _NAV_ANCHOR, _NAV_ANCHOR + _PRE_3C_NAV_STYLE)
    kind = re.findall(r'data-article-media="([a-z-]+)"', body)
    if kind == ["plate"]:
        body = _once(body, " brief-hero--photo", "")
        body = _once(body, _plate_block(), "")
    elif kind == ["signal-veil"]:
        body = _once(body, ' data-article-media="signal-veil"', "")
        body = _once(body, '<span class="article-media-kind">Signal Veil</span> · ', "")
    elif kind == ["photograph"]:
        veil = ctx["pw_veil"]
        body = _once(body, ' data-article-media="photograph"', "")
        new = re.findall(r'      <figcaption><span class="article-media-kind">Photograph</span>.*</figcaption>\n', body)
        if len(new) != 1:
            raise AssertionError("expected one Photograph caption")
        subject = f" · {escape(veil['subject'])}" if veil.get("subject") else ""
        body = _once(body, new[0], f'      <figcaption>Image: <a href="{escape(veil["source_page"])}" rel="noopener nofollow">{escape(veil["source_id"])}</a>{subject} · Context, not evidence.</figcaption>\n')
    elif kind:
        raise AssertionError(f"unexpected article media {kind}")
    body = body.replace(_MODEL_FLAG, "Model-flagged")
    nav = _NAV.findall(body)
    if len(nav) != 1:
        raise AssertionError("expected one issue navigation")
    hrefs = re.findall(r'href="([^"]+)"', nav[0])
    prev, nxt = ctx.get("prev_post"), ctx.get("next_post")
    expected = ([prev["date"] + ".html"] if prev else []) + (
        [nxt["date"] + ".html"] if nxt else [bridge_href] if bridge_href else [])
    if hrefs != expected:
        raise AssertionError(f"issue navigation {hrefs} != {expected}")
    links = ""
    if prev:
        links += f'<a href="{prev["date"]}.html">← No. {prev["issue_number"]} · {format_date(prev["week_ending"])}</a>'
    if nxt:  # the cross-series bridge did not exist before Phase 3C
        links += f'<a href="{nxt["date"]}.html">No. {nxt["issue_number"]} · {format_date(nxt["week_ending"])} →</a>'
    body = _once(body, nav[0], '    <nav class="historical-issue-nav" aria-label="Adjacent historical issues">\n'
                 + links + "    </nav>\n")
    return head + end + body


def _without_output_refresh_hooks(page):
    # Source-only candidates may add these two inert presentation hooks and
    # the owned stylesheet before an authorized output refresh.
    return page.replace(' data-surface="historical" data-route="analysis.html"', '').replace(
        '<link rel="stylesheet" href="../../surfaces.css">\n', '')


def _published_and_current(ctx, rendered, bridge_href=None):
    """(checked-in page, current render in comparable form) for one issue."""
    published = (POSTS / (ctx["date"] + ".html")).read_text(encoding="utf-8")
    published = _without_output_refresh_hooks(published)
    candidate = _without_output_refresh_hooks(rendered)
    if PHASE_3C_MARKER not in published:
        candidate = _as_published_before_3c(candidate, ctx, bridge_href)
    return published, candidate


class HistoricalBriefShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.posts = []
        cls.files = list(POSTS.glob("*.json")) + [ROOT / "pla_watch.db"]
        cls.fingerprints = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in cls.files}
        sides = sorted((json.loads(p.read_text()) for p in POSTS.glob("*.json")),
                       key=lambda s: s["date"])
        cls.bridge = next_brief_after(sides)
        for i, side in enumerate(sides):
            ctx = _build_post_context(side)
            ctx["prev_post"] = sides[i - 1] if i else None
            ctx["next_post"] = sides[i + 1] if i + 1 < len(sides) else None
            before = copy.deepcopy(ctx)
            page = render_historical_brief(ctx, next_brief=cls.next_brief(ctx))
            if ctx != before:
                raise AssertionError("renderer mutated historical context")
            cls.posts.append((ctx, page, BeautifulSoup(page, "html.parser")))

    @classmethod
    def next_brief(cls, ctx):
        bridge = cls.bridge
        return bridge["link"] if bridge and bridge["slug"] == ctx["date"] else None

    def bridge_href(self, ctx):
        link = self.next_brief(ctx)
        return link["href"] if link else None

    def test_every_real_issue_is_exercised(self):
        self.assertEqual(len(self.posts), len(list(POSTS.glob("*.json"))))
        self.assertGreaterEqual(len(self.posts), 14)

    def test_historical_utility_register_preserves_titles_deks_and_identity(self):
        sides = [json.loads(p.read_text()) for p in sorted(POSTS.glob('*.json'), reverse=True)]
        before = copy.deepcopy(sides)
        for route in ('the-pla-watch/', 'the-pla-watch/archive.html'):
            soup = BeautifulSoup(render_historical_utility('Earlier Briefs', route, posts=sides), 'html.parser')
            self.assertEqual(soup.select_one('link[rel=canonical]')['href'], 'https://indopacificrecord.org/'+route)
            rows = soup.select('.issue-ledger-row')
            self.assertEqual(len(rows), len(sides))
            for row, side in zip(rows, sides):
                self.assertEqual(row.h2.get_text(), side['title'])
                self.assertEqual(row.h2.a['href'], 'posts/'+side['date']+'.html')
                self.assertEqual(row.select_one('.issue-ledger-copy>p').get_text(), side['dek'])
                if side.get('publication_timing') == 'retrospective':
                    self.assertIn('Retrospective edition', row.get_text())
        self.assertEqual(sides, before)

    def test_glossary_shell_preserves_exact_terms_explanations_and_issue_urls(self):
        terms = []
        for side in [json.loads(p.read_text()) for p in sorted(POSTS.glob('*.json'), reverse=True)]:
            word, explanation = _flatten_term(side)
            if word.strip():
                terms.append(dict(term=word, explanation=explanation, date=side['date'],
                                  issue_number=side.get('issue_number'), week_ending=side.get('week_ending') or side['date']))
        soup = BeautifulSoup(render_historical_utility('Terms to Know', 'the-pla-watch/terms.html', terms=terms), 'html.parser')
        for row, term in zip(soup.select('.term-entry'), terms):
            self.assertEqual(row.h2.get_text(), term['term'])
            actual = [p.get_text() for p in row.select('.term-entry-expl>p')]
            expected = [BeautifulSoup(str(inline_markup(p.strip())), 'html.parser').get_text()
                        for p in term['explanation'].split('\n\n') if p.strip()]
            self.assertEqual(actual, expected)
            self.assertEqual(row.select_one('.term-entry-src a')['href'], 'posts/'+term['date']+'.html')

    def test_current_shell_and_collection_on_every_direct_article(self):
        for ctx, page, soup in self.posts:
            with self.subTest(issue=ctx["issue_number"]):
                chrome = str(soup.header) + str(soup.footer)
                self.assertIn('aria-label="Indo-Pacific Record home"', chrome)
                self.assertNotIn("China Mil Watch", chrome)
                self.assertNotIn("The PLA Watch", chrome)
                self.assertEqual(soup.select_one('.brief-eyebrow').get_text(strip=True),
                                 "Indo-Pacific Record Briefs")
                self.assertEqual(soup.select_one('meta[property="og:site_name"]')["content"],
                                 "Indo-Pacific Record")
                self.assertFalse(soup.select('meta[name="robots"][content*="noindex"]'))
                self.assertEqual(soup.select_one('link[rel="canonical"]')["href"], ctx["page_url"])

    def test_all_stored_body_paragraphs_remain_identical(self):
        fields = list(SECTIONS) + [
            ("what_im_watching_next", "s-watching", ""),
            ("term_to_know_explanation", "s-term", ""),
        ]
        for ctx, page, soup in self.posts:
            for key, anchor, _ in fields:
                if not ctx.get(key):
                    continue
                with self.subTest(issue=ctx["issue_number"], field=key):
                    actual = [p.get_text() for p in soup.select(f"#{anchor}>p")
                              if "term-word" not in p.get("class", [])]
                    expected = [BeautifulSoup(str(inline_markup(p.strip())), "html.parser").get_text()
                                for p in ctx[key].split("\n\n") if p.strip()]
                    self.assertEqual(actual, expected)

    def test_current_ipr_title_and_social_sharing_preserve_original_citation(self):
        for ctx, page, soup in self.posts:
            with self.subTest(issue=ctx["issue_number"]):
                expected = soup.select_one("#brief-title").get_text() + " — Indo-Pacific Record"
                self.assertEqual(soup.title.get_text(), expected)
                self.assertEqual(soup.select_one('meta[property="og:title"]')["content"], expected)
                self.assertEqual(soup.select_one('meta[name="twitter:title"]')["content"], expected)
                self.assertFalse(expected.startswith("The PLA Watch: "))

    def test_original_citation_is_exactly_the_existing_citation(self):
        old = make_pw_env().get_template("pla-watch-post.html")
        for ctx, page, soup in self.posts:
            with self.subTest(issue=ctx["issue_number"]):
                before = BeautifulSoup(old.render(**ctx), "html.parser").select_one('#pw-cite')
                self.assertEqual(soup.select_one('#pw-cite').get_text(), before.get_text())
                self.assertIn(ctx["publication"], soup.select_one('.historical-provenance').get_text())

    def test_every_source_title_original_url_outlet_date_and_flag_survives(self):
        for ctx, page, soup in self.posts:
            items = soup.select('.historical-source-list>li')
            self.assertEqual(len(items), len(ctx["articles"]))
            for source, item in zip(ctx["articles"], items):
                self.assertEqual(item.a["href"], source["url"])
                self.assertEqual(item.a.get_text(), source["title"])
                original = item.select_one('.source-card-original')
                self.assertEqual(original.get_text() if original else "", source.get("title_zh", ""))
                self.assertIn(source["source"], item.get_text())
                if source.get("date"):
                    self.assertEqual(item.time["datetime"], source["date"])
                self.assertEqual("Model-flagged" in item.get_text(), source["is_significant"])

    def test_historical_author_information_is_labelled_and_unmodified(self):
        for ctx, page, soup in self.posts:
            author = soup.select_one('details.historical-author')
            self.assertEqual(author.summary.get_text(), "Author information at original publication")
            self.assertEqual(author.select_one('.author-block-name').get_text(), ctx["author_name"])
            self.assertEqual(author.select_one('.author-block-title').get_text(), ctx["author_title"])
            self.assertEqual(author.select_one('.author-block-bio').get_text(), ctx["author_bio"])
            self.assertNotIn("China Mil Watch", soup.select_one('.brief-byline').get_text())

    def test_signal_veils_and_credit_survive_all_real_issues(self):
        for ctx, page, soup in self.posts:
            with self.subTest(issue=ctx["issue_number"]):
                original = ctx.get("pw_veil")
                figures = soup.select("figure.historical-veil")
                if not original:
                    self.assertEqual(figures, [])
                    continue
                self.assertEqual(len(figures), 1)
                figure = figures[0]
                self.assertEqual(figure["data-editorial-id"], original["id"])
                self.assertEqual(figure["aria-label"], "Historical visual context, not evidence")
                self.assertEqual(figure.img["src"], original["duo"])
                self.assertEqual(figure.img["alt"], original["alt"])
                self.assertIn(original["mask_focus"], figure.img["style"])
                caption = figure.figcaption.get_text()
                self.assertIn(original.get("subject") or "", caption)
                hrefs = [a["href"] for a in figure.select("a[href]")]
                if original["id"] in PRESERVED_MEDIA:
                    # Held: the pre-3C figure, unrelabelled.
                    self.assertFalse(figure.has_attr("data-article-media"))
                    self.assertEqual(hrefs, [original["source_page"]])
                    self.assertTrue(caption.startswith("Image: "))
                    self.assertIn(original["source_id"], caption)
                    self.assertIn("Context, not evidence", caption)
                elif original["kind"] == "source":
                    self.assertEqual(figure["data-article-media"], "signal-veil")
                    self.assertEqual(figure.select_one(".article-media-kind").get_text(), "Signal Veil")
                    self.assertEqual(hrefs, [original["source_page"]])
                    self.assertIn(original["source_id"], caption)
                    self.assertIn("Context, not evidence", caption)
                    # The collector note is never shown as a credit.
                    if original.get("credit"):
                        self.assertNotIn(original["credit"], caption)
                else:
                    self.assertEqual(original["kind"], "curated")
                    self.assertEqual(figure["data-article-media"], "photograph")
                    self.assertEqual(figure.select_one(".article-media-kind").get_text(), "Photograph")
                    self.assertIn(original["source_page"], hrefs)
                    for segment in original["credit"].split(" · "):
                        self.assertIn(segment.strip(), caption)
                    self.assertIn(original["license"], caption)
                    self.assertIn(CHANGE_NOTE, caption)
                    self.assertIn(CONTEXT_NOTE, caption)
                self.assertFalse(soup.select(".brief-opening-photo"),
                    "Resolved Signal Veil replaces in-page cover, not duplicates it")

    def test_replaced_cover_photographs_keep_original_source_credit(self):
        for ctx, page, soup in self.posts:
            if not (ctx.get("pw_veil") and ctx.get("cover_media_item")):
                continue
            with self.subTest(issue=ctx["issue_number"]):
                note = next((p for p in soup.select("#s-snapshot .historical-source-meta")
                             if "Edition cover (link-preview image)" in p.get_text()), None)
                self.assertIsNotNone(note)
                cover = ctx["cover_media_item"]
                self.assertEqual(note.a["href"],
                                 cover.get("source_page") or cover.get("source_url"))
                self.assertIn("visual context only", note.get_text())
                self.assertFalse(soup.select(".brief-opening-photo"))

    def test_signal_veil_without_cover_uses_photo_grid(self):
        context = next(copy.deepcopy(ctx) for ctx, _, _ in self.posts
                       if ctx.get("pw_veil"))
        context["cover_media_item"] = None
        page = render_historical_brief(context)
        soup = BeautifulSoup(page, "html.parser")
        self.assertIn("brief-hero--photo",
                      soup.select_one(".brief-hero").get("class", []))
        self.assertIsNotNone(soup.select_one(
            ".brief-hero-inner > figure.historical-veil"))
        self.assertIn(".historical-veil{grid-area:photo",
                      soup.select_one("style").get_text())
        self.assertEqual(soup.select_one("figure.historical-veil img")["src"],
                         context["pw_veil"]["duo"])

    def test_original_author_links_preserved_and_unsafe_hrefs_rejected(self):
        for ctx, page, soup in self.posts:
            with self.subTest(issue=ctx["issue_number"]):
                anchors = soup.select("details.historical-author .historical-author-links a")
                actual = {a.get_text(): a["href"] for a in anchors}
                self.assertEqual(actual, ctx.get("author_links") or {})
        ctx = copy.deepcopy(self.posts[0][0])
        ctx["author_links"] = {
            "Unsafe": "javascript:alert(1)",
            "Unsafe data": "data:text/html,bad",
            "Unsafe relative": "../../secrets",
            "Valid": "https://example.org/profile",
        }
        rendered = BeautifulSoup(render_historical_brief(ctx), "html.parser")
        self.assertEqual(
            [(a.get_text(), a["href"]) for a in rendered.select(".historical-author-links a")],
            [("Valid", "https://example.org/profile")],
        )

    def test_checked_in_pages_equal_current_sidecar_render(self):
        marked = [PHASE_3C_MARKER in (POSTS / (ctx["date"] + ".html")).read_text()
                  for ctx, _, _ in self.posts]
        # The governed rerender refreshes every issue at once, never a subset.
        self.assertIn(sum(marked), (0, len(self.posts)))
        for ctx, rendered, _ in self.posts:
            with self.subTest(issue=ctx["issue_number"]):
                published, candidate = _published_and_current(
                    ctx, rendered, self.bridge_href(ctx))
                self.assertEqual(published, candidate)

    def _guard_fails(self, ctx, rendered):
        try:
            published, candidate = _published_and_current(
                ctx, rendered, self.bridge_href(ctx))
        except AssertionError:
            return True
        return published != candidate

    def test_regression_guard_still_catches_media_alt_source_and_citation_changes(self):
        by_kind = {}
        for ctx, page, soup in self.posts:
            figure = soup.select_one("figure[data-article-media]")
            by_kind.setdefault(figure["data-article-media"] if figure else "preserved",
                               (ctx, page))
        self.assertEqual(set(by_kind), {"photograph", "signal-veil", "plate", "preserved"})
        for kind in ("photograph", "signal-veil"):
            ctx, page = by_kind[kind]
            self.assertFalse(self._guard_fails(ctx, page))
            for field, value in (("duo", "../../assets/editorial/other.jpg"),
                                 ("alt", "A different description"),
                                 ("source_page", "https://example.org/other"),
                                 ("source_id", "Another outlet")):
                with self.subTest(kind=kind, field=field):
                    changed = copy.deepcopy(ctx)
                    changed["pw_veil"][field] = value
                    self.assertTrue(self._guard_fails(
                        changed, render_historical_brief(changed, next_brief=self.next_brief(ctx))))
        for kind, (ctx, page) in by_kind.items():
            with self.subTest(kind=kind, change="citation"):
                cite = re.search(r'<p class="brief-citation" id="pw-cite">.*?</p>', page).group(0)
                self.assertTrue(self._guard_fails(ctx, page.replace(cite, cite.replace("No.", "Issue"), 1)))
            with self.subTest(kind=kind, change="model flag removed"):
                if _MODEL_FLAG in page:
                    self.assertTrue(self._guard_fails(ctx, page.replace(_MODEL_FLAG, "", 1)))
        held = 0
        for ctx, page, soup in self.posts:
            figure = soup.select_one("figure.historical-veil:not([data-article-media]), figure.brief-opening-photo")
            if figure is None:
                continue
            held += 1
            img = figure.select_one("img")
            with self.subTest(issue=ctx["issue_number"], change="held figure"):
                old = f'alt="{escape(img["alt"])}"'
                self.assertEqual(page.count(old), 1)
                self.assertTrue(self._guard_fails(ctx, page.replace(old, 'alt="changed"', 1)))
        self.assertEqual(held, 3)  # Nos. 1, 10 and 12

    def test_photograph_caption_links_are_pinned(self):
        # The pre-3C normalisation swaps the whole Photograph caption, so its
        # licence deed and file-page links are pinned here, exactly.
        expected = {
            "2026-06-27": ["https://creativecommons.org/licenses/by/4.0",
                           "https://commons.wikimedia.org/wiki/File:A_PLAN_Shenyang_J-15_carrier-based_fighter_aircraft_is_preparing_to_land_on_Chinese_aircraft_carrier_PLANS_Liaoning_(CV-16)_20220504.jpg"],
            "2026-07-04": ["https://commons.wikimedia.org/wiki/File:ISS045-E-77332_-_View_of_Scarborough_Shoal.jpg"],
        }
        found = {}
        for ctx, page, soup in self.posts:
            figure = soup.select_one('figure[data-article-media="photograph"]')
            if figure is not None:
                found[ctx["date"]] = [a["href"] for a in figure.select("figcaption a")]
        self.assertEqual(found, expected)

    def test_links_and_assets_use_the_correct_two_level_root(self):
        for ctx, page, soup in self.posts:
            self.assertEqual(soup.select_one('.brand')["href"], '../../index.html')
            self.assertIn('../../analysis.html', [a["href"] for a in soup.header.select('a[href]')])
            self.assertEqual([s["href"] for s in soup.select('link[rel="stylesheet"]')],
                             ['../../fonts.css', '../../styles.css', '../../surfaces.css', '../../briefs.css'])
            self.assertEqual(soup.select_one('script[src]')["src"], '../../shell.js')
            self.assertFalse(soup.select('.publication-freshness'))
            for neighbor in (ctx["prev_post"], ctx["next_post"]):
                if neighbor:
                    self.assertIn(neighbor["date"] + '.html',
                                  [a["href"] for a in soup.select('.historical-issue-nav a')])

    def test_newest_issue_and_first_brief_link_each_other(self):
        from core.brief_collection import adjacent_items, load_collection
        from core.desk_registry import load_registry
        from scripts.historical_brief_render import _site_definition
        newest_ctx, _, newest = self.posts[-1]
        nav = [a["href"] for a in newest.select(".historical-issue-nav a")]
        self.assertEqual(nav, [self.posts[-2][0]["date"] + ".html",
                               "../../briefs/maritime-cooperation-2026.html"])
        self.assertEqual(newest.select_one('.historical-issue-nav a[rel="next"]')["href"],
                         self.bridge_href(newest_ctx))
        # The brief's own previous link, from the collection the site builds.
        collection = load_collection(_site_definition().load_editions(ROOT),
                                     load_registry(), briefs_dir=ROOT / "briefs")
        previous = adjacent_items(collection, "maritime-cooperation-2026")["previous"]
        self.assertEqual(previous["href"], "../the-pla-watch/posts/%s.html" % newest_ctx["date"])
        self.assertEqual(previous["number"], newest_ctx["issue_number"])
        # Every earlier issue keeps its own sidecar neighbours; none gains a brief.
        for ctx, _, soup in self.posts[:-1]:
            with self.subTest(issue=ctx["issue_number"]):
                self.assertTrue(all(a["href"].endswith(".html") and "/" not in a["href"]
                                    for a in soup.select(".historical-issue-nav a")))

    def test_bridge_is_approval_gated_and_never_guessed(self):
        sides = sorted((json.loads(p.read_text()) for p in POSTS.glob("*.json")),
                       key=lambda s: s["date"])
        brief = json.loads((ROOT / "briefs/maritime-cooperation-2026.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp)
            self.assertIsNone(next_brief_after(sides, briefs_dir=empty))
            draft = dict(brief, editorial_status="draft")
            (empty / "maritime-cooperation-2026.json").write_text(json.dumps(draft))
            self.assertIsNone(next_brief_after(sides, briefs_dir=empty))
            (empty / "maritime-cooperation-2026.json").write_text(
                json.dumps(dict(brief, editorial_status="pending")))
            with unittest.mock.patch("builtins.print") as warned:
                self.assertIsNone(next_brief_after(sides, briefs_dir=empty))
            self.assertIn("WARN", warned.call_args[0][0])
        self.assertIsNone(next_brief_after([]))

    def test_no_invented_dates_source_fields_or_unsafe_markup(self):
        ctx = copy.deepcopy(self.posts[0][0])
        ctx['opening_note'] = '<script>alert(1)</script> <strong>Kept</strong>'
        soup = BeautifulSoup(render_historical_brief(ctx), 'html.parser')
        self.assertFalse(soup.select('#s-opening script'))
        self.assertEqual(soup.select_one('#s-opening strong').get_text(), 'Kept')

    def test_render_is_deterministic_and_canonical_bytes_do_not_change(self):
        ctx, first, _ = self.posts[0]
        self.assertEqual(render_historical_brief(ctx), first)
        self.assertEqual({p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.files},
                         self.fingerprints)


class HistoricalBriefBrowserTests(unittest.TestCase):
    """Actual current-shell pages: old template browser tests remain rollback QA."""
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.tmp = tempfile.TemporaryDirectory(prefix='ipr-historical-browser-')
        cls.root = Path(cls.tmp.name)
        for name in ('fonts.css', 'styles.css', 'surfaces.css', 'briefs.css', 'shell.js'):
            shutil.copy2(ROOT / 'site/preview' / name, cls.root / name)
        shutil.copytree(ROOT / 'output/assets', cls.root / 'assets')
        shutil.copytree(ROOT / 'site/assets/material', cls.root / 'assets/material', dirs_exist_ok=True)
        # The editorial plate's art ships with the build (CATALOGUE_STATIC_ASSETS)
        # and is not yet in the checked-in output.
        shutil.copy2(ROOT / 'site/assets/geo/region.svg', cls.root / 'assets/geo/region.svg')
        for name in ('media', 'covers'):
            shutil.copytree(ROOT / 'output/the-pla-watch' / name,
                            cls.root / 'the-pla-watch' / name)
        posts = cls.root / 'the-pla-watch/posts'
        posts.mkdir()
        cls.routes = []
        for source in sorted(POSTS.glob('*.json')):
            context = _build_post_context(json.loads(source.read_text()))
            route = 'the-pla-watch/posts/' + source.stem + '.html'
            (cls.root / route).write_text(render_historical_brief(context))
            cls.routes.append(route)
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        cls.server = socketserver.TCPServer(('127.0.0.1', 0),
            functools.partial(Quiet, directory=str(cls.root)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.tmp.cleanup()

    def visit(self, page, route):
        page.goto(f'http://127.0.0.1:{self.server.server_address[1]}/{route}')
        page.evaluate('document.fonts.ready')

    def test_all_historical_articles_fit_mobile_tablet_and_desktop(self):
        for width in (320, 375, 768, 1280):
            page = self.browser.new_page(viewport={'width': width, 'height': 900})
            failures = []
            page.on('pageerror', lambda e: failures.append(str(e)))
            for route in self.routes:
                with self.subTest(width=width, route=route):
                    self.visit(page, route)
                    dimensions = page.evaluate('({viewport:innerWidth,width:document.documentElement.scrollWidth})')
                    self.assertLessEqual(dimensions['width'], dimensions['viewport'])
                    self.assertEqual(page.locator('h1').count(), 1)
                    self.assertTrue(page.locator('#pw-cite').is_visible())
                    self.assertFalse(failures)
            page.close()

    def test_no_javascript_and_reduced_motion_keep_sources_and_navigation(self):
        for options in ({'java_script_enabled': False}, {'reduced_motion': 'reduce'}):
            context = self.browser.new_context(viewport={'width':375,'height':900}, **options)
            page = context.new_page()
            for route in self.routes:
                with self.subTest(mode=options, route=route):
                    self.visit(page, route)
                    self.assertTrue(page.locator('#s-sources').is_visible())
                    self.assertTrue(page.locator('#pw-cite').is_visible())
                    page.locator('.brief-reading-navigation>summary').click()
                    self.assertTrue(page.locator('.brief-toc a').first.is_visible())
                    page.locator('.historical-author>summary').click()
                    self.assertTrue(page.locator('.author-block-bio').is_visible())
            context.close()

    def test_keyboard_menu_escape_and_skip_link(self):
        page = self.browser.new_page(viewport={'width':375,'height':900})
        self.visit(page, self.routes[0])
        page.keyboard.press('Tab')
        self.assertEqual(page.evaluate('document.activeElement.className'), 'skip')
        page.keyboard.press('Enter')
        self.assertTrue(page.url.endswith('#main'))
        page.keyboard.press('Tab')
        self.assertTrue(page.evaluate('document.activeElement.closest("main")!==null'))
        menu = page.locator('.nav-mobile>summary')
        menu.focus()
        page.keyboard.press('Enter')
        self.assertTrue(page.locator('.nav-mobile').evaluate('(e)=>e.open'))
        page.keyboard.press('Escape')
        self.assertFalse(page.locator('.nav-mobile').evaluate('(e)=>e.open'))
        page.close()

    def test_local_styles_fonts_scripts_and_photos_resolve(self):
        page = self.browser.new_page()
        failed = []
        page.on('response', lambda response: failed.append(response.url)
                if response.status >= 400 else None)
        for route in self.routes:
            self.visit(page, route)
            self.assertEqual(page.locator('img').evaluate_all(
                '(images)=>images.filter(i=>i.loading!=="lazy" && (!i.complete || !i.naturalWidth)).length'), 0)
        self.assertEqual(failed, [])
        page.close()


if __name__ == '__main__':
    unittest.main()
