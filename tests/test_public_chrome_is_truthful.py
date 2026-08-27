"""
The public chrome may not describe the site as unpublished.

On 2026-08-27 PR #32 made this build the public site at
`https://indopacificrecord.org`. Until that moment the footer carried three
sentences written for a candidate that had never been deployed:

    Release candidate. Built in indo-pacific-record mode and not published
    or deployed. The public site continues under its current identity until
    a separately authorized launch.

The moment the build was published, all three became false — on 3,680 live
pages at once, in the chrome, on every page a reader could reach. Nothing
detected it, because nothing was watching the chrome for claims that had a
shelf life.

That is what these tests are. They read a real build rather than the template,
because what a template contains and what a page says are different questions,
and it was the pages that were wrong.

Scope, deliberately narrow: **project chrome only**. A stored source record may
legitimately contain any of these words — an institution is free to publish the
phrase "release candidate", and a record page quoting it must keep quoting it
verbatim. So the scan is confined to the header, footer and navigation, and the
record body is explicitly out of scope.
"""

from __future__ import annotations

import importlib.util
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

TRACKED_DB = REPO_ROOT / "pla_watch.db"

#: Claims that were true of a candidate and are false of a publication.
#: Lower-cased; the text is whitespace-normalised before matching because the
#: original defect spanned a line break in the template and so never matched a
#: naive search of the rendered HTML.
FORBIDDEN_IN_CHROME = (
    "release candidate",
    "not published or deployed",
    "public site continues under its current identity",
    "separately authorized launch",
    "candidate build",
    "unpublished",
    "not yet public",
    "until a separately authorized",
)

#: The predecessor may be named as history. It may not be the masthead.
FORBIDDEN_AS_MASTHEAD = ("china mil watch",)

CHROME = re.compile(r"<(header|footer|nav)\b[\s\S]*?</\1>", re.I)


def flatten(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).lower()


class BuildCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="public-chrome-"))
        cls.out = cls.tmp / "site"
        cls.result = gp.build(
            cls.out, gp.PUBLIC_TITLE, TRACKED_DB,
            snapshot=gp.snapshot_from_corpus(TRACKED_DB),
            legacy_routes=True, site_origin="https://a-real-domain.org")
        cls.pages = sorted(p for p in cls.out.rglob("*.html")
                           if p.parent.name != "article")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def chrome_of(self, page: Path) -> str:
        html = page.read_text("utf-8", errors="replace")
        return " ".join(flatten(m.group(0)) for m in CHROME.finditer(html))


class TestNoPageDescribesItselfAsUnpublished(BuildCase):

    def test_the_chrome_of_every_page_is_clean(self):
        offenders = {}
        for page in self.pages:
            chrome = self.chrome_of(page)
            for phrase in FORBIDDEN_IN_CHROME:
                if phrase in chrome:
                    offenders.setdefault(phrase, []).append(
                        str(page.relative_to(self.out)))
        self.assertEqual(
            offenders, {},
            "public chrome claims the site is unpublished: %s" % offenders)

    def test_the_build_actually_produced_pages_to_check(self):
        """A scan of nothing passes for the wrong reason."""
        self.assertGreater(len(self.pages), 3000)

    def test_every_page_has_chrome_to_scan(self):
        without = [str(p.relative_to(self.out)) for p in self.pages[:200]
                   if not self.chrome_of(p).strip()]
        self.assertEqual(without, [])


class TestTheFooterSaysWhatThePublicationIs(BuildCase):

    def footer(self, page: Path) -> str:
        html = page.read_text("utf-8", errors="replace")
        match = re.search(r"<footer\b[\s\S]*?</footer>", html, re.I)
        return flatten(match.group(0)) if match else ""

    def test_the_footer_names_the_publication_and_its_editor(self):
        footer = self.footer(self.out / "index.html")
        self.assertIn("indo-pacific record", footer)
        self.assertIn("independent research project", footer)
        self.assertIn("benjamin yang", footer)

    def test_the_footer_keeps_the_two_standing_qualifications(self):
        """
        Selectivity and the record/claim distinction are the two things the
        footer has always had to say, and the correction must not drop them
        while removing the sentences that expired.
        """
        footer = self.footer(self.out / "index.html")
        self.assertIn("coverage is selective", footer)
        self.assertIn("not whether its claims are true", footer)

    def test_the_footer_is_the_same_on_every_page_type(self):
        seen = set()
        for name in ("index.html", "archive.html", "methodology.html",
                     "desks.html", "coverage.html", "about.html",
                     "record/1.html"):
            page = self.out / name
            if page.is_file():
                seen.add(self.footer(page))
        self.assertEqual(len(seen), 1, "the footer differs between page types")


class TestThePredecessorIsHistoryNotIdentity(BuildCase):

    def test_no_masthead_carries_the_predecessor_name(self):
        offenders = []
        for page in self.pages:
            html = page.read_text("utf-8", errors="replace")
            match = re.search(r"<header\b[\s\S]*?</header>", html, re.I)
            if not match:
                continue
            head = flatten(match.group(0))
            for phrase in FORBIDDEN_AS_MASTHEAD:
                if phrase in head:
                    offenders.append(str(page.relative_to(self.out)))
        self.assertEqual(offenders, [])

    def test_the_predecessor_may_still_be_named_as_history(self):
        """
        The inverse guard. Scrubbing the predecessor everywhere would be its
        own falsehood: the weekly series really was published under that name,
        and the legacy-series page has to say so.
        """
        series = (self.out / "pla-watch.html").read_text("utf-8")
        self.assertIn("China Mil Watch", series)


class TestQuotedSourceTextIsNotPoliced(BuildCase):
    """
    The scan must not reach into the record. An institution may publish any
    phrase at all, and a record page repeating it verbatim is doing its job —
    a guard that forced a stored document to be edited would be worse than the
    defect it was written for.
    """

    def test_the_chrome_pattern_does_not_match_the_record_body(self):
        page = self.out / "record" / "1.html"
        html = page.read_text("utf-8", errors="replace")
        chrome = " ".join(m.group(0) for m in CHROME.finditer(html))
        body = re.search(r"<main\b[\s\S]*?</main>", html, re.I)
        self.assertIsNotNone(body)
        # The record body sits outside every region this test inspects.
        self.assertNotIn("<main", chrome)


if __name__ == "__main__":
    unittest.main()
