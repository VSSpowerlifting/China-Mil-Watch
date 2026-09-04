"""
Which stored cover URLs get re-based onto the current origin, and which do not.

Why this is narrow on purpose
-----------------------------
Twelve sidecars record `cover_image_url` on `chinamilwatch.org`, captured when
that was the live domain. The renderer preferred the stored value, so a
re-render would have pointed every edition's `og:image` at what is now a
redirect-only Pages site. Re-basing those is right: the host is a fact about
where this project's site lives, not a fact about the edition.

The first implementation re-based *any* absolute URL whose hostname differed
from `SITE_ORIGIN`. That is too broad, and the breadth is the bug. A future
edition may legitimately host a cover somewhere this project does not control —
a CDN, an archive, an institution's own server — and rewriting that URL onto
`indopacificrecord.org` would silently invent an address that does not exist.
A wrong `og:image` that 404s is worse than a stale one that redirects.

So the rule is an allow-list of hostnames this project actually retired, not a
deny-list of hostnames that are not the current one.

The evidence for the list
-------------------------
`config.py` records the change: the origin moved from `https://chinamilwatch.org`
on 2026-08-27. `PROJECT_STATE.md` and `DECISION_LOG.md` say the same, and add
that the old domain is served by a separate redirect-only repository. No other
predecessor hostname appears anywhere in this repository, so no other one is
listed here. The `www.` variant is included because a redirect-only site
answers both and a sidecar could have recorded either.

Sidecars are not edited. They are the canonical edition record; the renderer
reads them as published and states the current address itself.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def rebase(url: str) -> str:
    from scripts.rerender_pla_watch import _on_current_origin
    return _on_current_origin(url)


class TestRetiredOriginsAreRebased(unittest.TestCase):
    """The case the helper exists for."""

    def test_the_retired_https_origin_becomes_the_current_one(self):
        self.assertEqual(
            rebase("https://chinamilwatch.org/the-pla-watch/covers/2026-08-01.png"),
            "https://indopacificrecord.org/the-pla-watch/covers/2026-08-01.png")

    def test_the_retired_http_origin_becomes_the_current_https_one(self):
        """
        The scheme is re-based with the host. A stored `http://` URL predates
        the current site entirely, and emitting it would put an insecure URL in
        a link preview.
        """
        self.assertEqual(
            rebase("http://chinamilwatch.org/the-pla-watch/covers/2026-07-04.png"),
            "https://indopacificrecord.org/the-pla-watch/covers/2026-07-04.png")

    def test_the_retired_www_origin_becomes_the_current_one(self):
        self.assertEqual(
            rebase("https://www.chinamilwatch.org/the-pla-watch/covers/x.png"),
            "https://indopacificrecord.org/the-pla-watch/covers/x.png")

    def test_a_query_and_fragment_survive_the_rebase(self):
        """
        Only the origin is this project's to restate. Everything after it was
        written by whoever recorded the URL.
        """
        self.assertEqual(
            rebase("https://chinamilwatch.org/covers/a.png?v=2#top"),
            "https://indopacificrecord.org/covers/a.png?v=2#top")

    def test_a_bare_retired_origin_keeps_its_empty_path(self):
        self.assertEqual(rebase("https://chinamilwatch.org"),
                         "https://indopacificrecord.org")


class TestEverythingElseIsLeftAlone(unittest.TestCase):
    """
    The half that matters more. Each of these is a URL the renderer has no
    standing to rewrite, and the assertion is byte-identity rather than
    equivalence.
    """

    def test_the_current_origin_is_returned_unchanged(self):
        url = "https://indopacificrecord.org/the-pla-watch/covers/2026-08-15.png"
        self.assertEqual(rebase(url), url)

    def test_an_external_cdn_url_is_returned_unchanged(self):
        url = "https://cdn.example.net/ipr/covers/2026-09-05.png"
        self.assertEqual(rebase(url), url)

    def test_an_unrelated_https_origin_is_returned_unchanged(self):
        url = "https://commons.wikimedia.org/wiki/File:J-20.jpg"
        self.assertEqual(rebase(url), url)

    def test_an_unrelated_http_origin_is_returned_unchanged(self):
        """
        Insecure, but not this project's URL. Rewriting the host to fix the
        scheme would point at a file that was never there.
        """
        url = "http://www.81.cn/yw_208727/16462436.html"
        self.assertEqual(rebase(url), url)

    def test_a_hostname_merely_containing_the_retired_one_is_unchanged(self):
        """
        Substring matching would capture a hostname this project does not own.
        """
        for url in ("https://chinamilwatch.org.example.com/covers/a.png",
                    "https://notchinamilwatch.org/covers/a.png",
                    "https://archive.chinamilwatch.org.cdn.net/a.png"):
            with self.subTest(url=url):
                self.assertEqual(rebase(url), url)

    def test_a_relative_url_is_returned_unchanged(self):
        for url in ("../covers/2026-08-01.png",
                    "/the-pla-watch/covers/2026-08-01.png",
                    "covers/2026-08-01.png"):
            with self.subTest(url=url):
                self.assertEqual(rebase(url), url)

    def test_an_empty_value_is_returned_unchanged(self):
        self.assertEqual(rebase(""), "")

    def test_a_malformed_value_falls_through_unchanged(self):
        """
        Existing fail-safe behaviour: anything without both a scheme and a
        host is returned as-is rather than guessed at.
        """
        for url in ("not a url", "://broken", "https://", "mailto:a@b.c",
                    "data:image/png;base64,AAA"):
            with self.subTest(url=url):
                self.assertEqual(rebase(url), url)


class TestTheAllowListIsGroundedInRepositoryEvidence(unittest.TestCase):

    def test_the_retired_hosts_are_declared_and_minimal(self):
        from scripts.rerender_pla_watch import RETIRED_ORIGIN_HOSTS
        self.assertEqual(set(RETIRED_ORIGIN_HOSTS),
                         {"chinamilwatch.org", "www.chinamilwatch.org"})

    def test_the_current_origin_is_not_in_the_retired_list(self):
        from scripts.rerender_pla_watch import (RETIRED_ORIGIN_HOSTS,
                                                SITE_ORIGIN)
        from urllib.parse import urlsplit
        self.assertNotIn(urlsplit(SITE_ORIGIN).netloc, RETIRED_ORIGIN_HOSTS)

    def test_config_still_records_the_origin_this_list_was_built_from(self):
        """
        The allow-list is only as good as its evidence. If the predecessor
        domain stops being named in `config.py`, this list needs re-deriving
        rather than trusting.
        """
        config = (REPO_ROOT / "config.py").read_text(encoding="utf-8")
        self.assertIn("chinamilwatch.org", config)


class TestTheCommittedSidecarsAreCoveredButNotRelieduponAlone(unittest.TestCase):
    """
    The twelve real sidecars are a fixture, not the contract. They are checked
    because they are what shipped; the cases above are checked because they are
    what could ship next.
    """

    def test_every_stored_cover_url_resolves_to_the_current_origin(self):
        import json
        from scripts.rerender_pla_watch import SITE_ORIGIN
        posts = REPO_ROOT / "output" / "the-pla-watch" / "posts"
        if not posts.is_dir():
            self.skipTest("no published sidecars")
        seen = 0
        for path in sorted(posts.glob("*.json")):
            stored = json.loads(path.read_text(encoding="utf-8")).get(
                "cover_image_url") or ""
            if not stored.startswith(("http://", "https://")):
                continue
            seen += 1
            with self.subTest(edition=path.stem):
                self.assertTrue(rebase(stored).startswith(SITE_ORIGIN + "/"),
                                "%s -> %s" % (stored, rebase(stored)))
        self.assertGreater(seen, 0, "no absolute cover URLs found to check")


if __name__ == "__main__":
    unittest.main()
