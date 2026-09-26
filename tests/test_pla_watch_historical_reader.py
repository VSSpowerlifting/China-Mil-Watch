"""Reader contracts for the preserved The PLA Watch series.

Render from the committed sidecars through the production weekly Jinja
environment. No generated page or canonical edition record is written.
"""

from __future__ import annotations

import html
import json
import re
import unittest
from pathlib import Path

from scripts.pw_env import make_pw_env
from scripts.rerender_pla_watch import _build_post_context


ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "output" / "the-pla-watch" / "posts"


class HistoricalReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = make_pw_env()
        cls.sidecars = sorted(
            (json.loads(path.read_text(encoding="utf-8"))
             for path in POSTS.glob("*.json")),
            key=lambda item: item["date"], reverse=True,
        )
        if not cls.sidecars:
            raise unittest.SkipTest("No historical sidecars available")

    def render_post(self, sidecar):
        return self.env.get_template("pla-watch-post.html").render(
            **_build_post_context(sidecar))

    def test_series_home_previews_only_four_earlier_issues(self):
        posts = self.sidecars
        page = self.env.get_template("pla-watch-index.html").render(
            latest_post=posts[0], archive_posts=posts[1:],
            root_path="../", latest_veil=None,
        )
        recent = page.split('<div class="archive-list">', 1)[1].split(
            '</div>\n      <a class="archive-all"', 1)[0]
        for post in posts[1:5]:
            self.assertIn(f'posts/{post["date"]}.html', recent)
        if len(posts) > 5:
            self.assertNotIn(f'posts/{posts[5]["date"]}.html', recent)
        self.assertIn('href="archive.html"', page)

    def test_series_home_links_every_issue_despite_short_preview(self):
        posts = self.sidecars
        page = self.env.get_template("pla-watch-index.html").render(
            latest_post=posts[0], archive_posts=posts[1:],
            root_path="../", latest_veil=None,
        )
        register = page.split('<nav class="index-register"', 1)[1].split(
            '</nav>', 1)[0]
        linked_dates = re.findall(r'href="posts/(\d{4}-\d{2}-\d{2})\.html"',
                                  register)
        self.assertEqual(linked_dates,
                         [post["date"] for post in reversed(posts[1:])])
        for post in posts:
            self.assertIn(f'posts/{post["date"]}.html', page)
        self.assertIn("do not imply uninterrupted weekly coverage", register)

    def test_archive_register_follows_real_issue_chronology(self):
        page = self.env.get_template("pla-watch-archive.html").render(
            posts=self.sidecars, root_path="../",
        )
        register = page.split('<nav class="issue-register"', 1)[1].split(
            '</nav>', 1)[0]
        linked_dates = re.findall(r'href="posts/(\d{4}-\d{2}-\d{2})\.html"',
                                  register)
        self.assertEqual(linked_dates,
                         [post["date"] for post in reversed(self.sidecars)])
        self.assertIn("equal spacing does not represent elapsed time", register)

    def test_original_headline_language_uses_stored_characters(self):
        observed_english = observed_chinese = 0
        for sidecar in self.sidecars:
            page = self.render_post(sidecar)
            originals = re.findall(
                r'<div class="source-card-original(?P<zh> is-zh)?"'
                r'(?P<lang> lang="zh-Hans")?>(?P<text>.*?)</div>',
                page, re.S,
            )
            expected = [item.get("title_zh") for item in
                        _build_post_context(sidecar)["articles"]
                        if item.get("title_zh")]
            self.assertEqual(len(originals), len(expected), sidecar["date"])
            for (style, lang, rendered), source in zip(originals, expected):
                self.assertEqual(html.unescape(rendered), source)
                has_cjk = bool(re.search(r"[一-鿿㐀-䶿]", source))
                self.assertEqual(bool(lang), has_cjk, source)
                self.assertEqual(bool(style), has_cjk, source)
                observed_chinese += has_cjk
                observed_english += not has_cjk
        self.assertGreater(observed_chinese, 0)
        self.assertGreater(observed_english, 0)

    def test_post_jump_targets_exist_and_source_count_is_not_guessed(self):
        sidecar = next(sc for sc in self.sidecars if not sc.get("sources_seen"))
        ctx = _build_post_context(sidecar)
        page = self.render_post(sidecar)
        jump = page.split('<nav class="post-jump"', 1)[1].split('</nav>', 1)[0]
        for target in re.findall(r'href="#([^"]+)"', jump):
            self.assertIn(f'id="{target}"', page)
        sources = list(dict.fromkeys(item["source"] for item in ctx["articles"]
                                     if item.get("source")))
        self.assertRegex(page,
                         r'<div class="num">%d</div>\s*<div class="label">Source'
                         % len(sources))
        self.assertIn("in the trail", page)


if __name__ == "__main__":
    unittest.main()
