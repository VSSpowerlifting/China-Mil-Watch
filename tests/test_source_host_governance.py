"""
What `base_url` governs, what it does not, and how an adapter's own endpoint
stays accountable to registry policy.

THE QUESTION THIS FILE SETTLES
------------------------------
The Xinhua adapter retrieves from `www.news.cn` while its manifest `base_url`
reads `https://www.xinhuanet.com`. Is that a divergence the project forbids, or
an arrangement it already relies on?

Already relies on — and not narrowly. `sources.base_url` is a **legacy identity
column**: it is written once when a source is first inserted, it is displayed,
and `sync_desk_config()` deliberately refuses ever to rewrite it, because "a
config sync must not be able to rename a live source or re-point it at a
different host" (core/registry.py). It has never been a retrieval origin, and
production proves it: China Military Online is declared as
`english.chinamil.com.cn` and every one of its 445 stored records is on
`eng.chinamil.com.cn`. PLA Daily is declared `https://` and fetched `http://`.

So `base_url` is publisher identity and display; the adapter owns its endpoint.
That arrangement is only safe while it is accountable, which is what the last
class here enforces: every host an adapter will retrieve from must be declared
by the adapter AND registered in the project's sanctioned host-alias table, so
an adapter cannot quietly start fetching from somewhere the project has never
agreed to.

Offline. The corpus assertions read a scratch copy through
`reconcile_db.read_only`; the tracked database is never opened directly.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from processing.dedup import _HOST_AUTHORITY_SLUG                # noqa: E402
from scraper.sources import xinhua_mil as X                      # noqa: E402
from scripts.reconcile_db import read_only                       # noqa: E402

MANIFEST = REPO_ROOT / "desks" / "china" / "manifest.json"
TRACKED_DB = REPO_ROOT / "pla_watch.db"


def manifest_sources() -> dict:
    return {s["slug"]: s
            for s in json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"]}


class TestBaseUrlIsIdentityNotRetrievalOrigin(unittest.TestCase):
    """The precedent, demonstrated rather than asserted in prose."""

    def test_sync_refuses_to_repoint_a_live_source(self):
        source = (REPO_ROOT / "core" / "registry.py").read_text(
            encoding="utf-8")
        self.assertIn(
            "must not be able to rename a live source or re-point it at a",
            source,
            "the rule this whole file rests on is no longer stated in "
            "core/registry.py")
        self.assertIn("display_name / base_url / language / is_active are left",
                      source)

    def test_an_existing_source_already_retrieves_from_another_host(self):
        """
        China Military Online: declared english.chinamil.com.cn, served from
        eng.chinamil.com.cn. If this ever stops being true, the Xinhua
        arrangement loses its precedent and should be re-argued, not assumed.
        """
        declared = urlsplit(
            manifest_sources()["china_mil_online"]["base_url"]).netloc
        self.assertEqual(declared, "english.chinamil.com.cn")

        # The retrieval constant, not the prose: the adapter's own docstring
        # notes that "the homepage is at english.chinamil.com.cn but all
        # article links resolve to eng.chinamil.com.cn", so the file mentions
        # both and only `_BASE` says where it actually fetches.
        adapter = (REPO_ROOT / "scraper" / "sources"
                   / "china_mil_online.py").read_text(encoding="utf-8")
        base = re.search(r'^_BASE\s*=\s*"([^"]+)"', adapter, re.M)
        self.assertIsNotNone(base, "china_mil_online declares no _BASE")
        self.assertEqual(urlsplit(base.group(1)).netloc, "eng.chinamil.com.cn")
        self.assertNotEqual(urlsplit(base.group(1)).netloc, declared)

    def test_the_corpus_shows_the_divergence_is_load_bearing(self):
        if not TRACKED_DB.exists():
            self.skipTest("tracked corpus not present")
        with read_only(str(TRACKED_DB)) as con:
            rows = con.execute(
                "SELECT a.url FROM articles a JOIN sources s "
                "    ON s.id = a.source_id "
                " WHERE s.slug = 'china_mil_online'").fetchall()
        if not rows:
            self.skipTest("no china_mil_online records in this corpus")
        hosts = {urlsplit(r[0]).netloc for r in rows}
        self.assertEqual(
            hosts, {"eng.chinamil.com.cn"},
            "every stored record for this source is on a host its base_url "
            "does not name — that is the precedent Xinhua relies on")

    def test_xinhua_base_url_is_deliberately_not_the_retrieval_host(self):
        declared = urlsplit(manifest_sources()["xinhua_mil"]["base_url"]).netloc
        self.assertEqual(declared, "www.xinhuanet.com")
        self.assertNotIn(declared, X.PERMITTED_HOSTS)


class TestXinhuaPermittedHostBoundary(unittest.TestCase):
    """A narrow declared boundary, not a redirect and not an escape."""

    PATH = "/milpro/20260915/" + "a" * 32 + "/c.html"

    def test_the_permitted_hosts_are_declared_and_closed(self):
        self.assertEqual(set(X.PERMITTED_HOSTS), {"www.news.cn", "news.cn"})

    def test_every_permitted_host_canonicalises(self):
        for host in X.PERMITTED_HOSTS:
            with self.subTest(host=host):
                self.assertEqual(
                    X.canonical_url("https://%s%s" % (host, self.PATH)),
                    "https://www.news.cn" + self.PATH)

    def test_no_other_host_is_followed(self):
        for host in ("www.xinhuanet.com", "xinhuanet.com", "example.com",
                     "news.cn.evil.test", "www.news.cn.attacker.test",
                     "localhost", "127.0.0.1", "www.globaltimes.cn"):
            with self.subTest(host=host):
                self.assertIsNone(
                    X.canonical_url("https://%s%s" % (host, self.PATH)),
                    "%s was accepted as a retrieval host" % host)

    def test_a_listing_link_to_a_foreign_host_is_dropped(self):
        """A relative link resolves against the listing; an absolute one must
        not be able to walk the adapter off its own site."""
        self.assertIsNone(X.canonical_url(
            "https://evil.test" + self.PATH,
            base="https://www.news.cn/milpro/"))

    def test_the_scheme_is_normalised_to_https(self):
        self.assertTrue(X.canonical_url(
            "http://www.news.cn" + self.PATH).startswith("https://"))


class TestAdaptersCannotSilentlyDiverge(unittest.TestCase):
    """
    The accountability rule. An adapter may own its endpoint, but every host it
    will retrieve from has to be registered in the project's sanctioned
    host-alias table — the one place a host is deliberately, reviewably
    associated with a source.
    """

    def test_every_xinhua_permitted_host_is_registered(self):
        for host in X.PERMITTED_HOSTS:
            with self.subTest(host=host):
                self.assertEqual(
                    _HOST_AUTHORITY_SLUG.get(host), "xinhua_mil",
                    "%s is fetched but not registered to this source" % host)

    def test_the_predecessor_host_stays_registered(self):
        """Stored records still carry it; forgetting it would orphan them."""
        self.assertEqual(_HOST_AUTHORITY_SLUG.get("www.xinhuanet.com"),
                         "xinhua_mil")

    def test_every_declared_base_url_host_is_registered(self):
        for slug, src in manifest_sources().items():
            host = urlsplit(src["base_url"]).netloc
            with self.subTest(slug=slug, host=host):
                self.assertEqual(
                    _HOST_AUTHORITY_SLUG.get(host), slug,
                    "%s declares %s but the alias table does not map it"
                    % (slug, host))

    def test_no_registered_host_maps_to_an_unknown_source(self):
        known = set(manifest_sources())
        for host, slug in _HOST_AUTHORITY_SLUG.items():
            with self.subTest(host=host):
                self.assertIn(slug, known,
                              "%s maps to %s, which is not a declared source"
                              % (host, slug))

    def test_the_registry_is_not_a_wildcard(self):
        for host in _HOST_AUTHORITY_SLUG:
            self.assertNotIn("*", host)
            self.assertFalse(host.startswith("."))


if __name__ == "__main__":
    unittest.main()
