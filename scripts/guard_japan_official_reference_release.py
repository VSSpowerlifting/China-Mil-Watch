"""Verify exact reviewed external Japan references before country-page release.

This is a public-presentation contract, never an original-body admission gate.
It inspects generated HTML, so a template-only green test cannot authorize a
release that accidentally omits an approved source link.
"""
from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


JCG_PREFIX = "https://www.kaiho.mlit.go.jp/e/topics_archive/article"
MOD_PREFIX = "https://www.mod.go.jp/j/press/news/2026/"
JCG_LINKS = tuple(JCG_PREFIX + str(n) + ".html" for n in
                  (9399, 9424, 9436, 9453, 9455, 9465))
MOD_LINKS = tuple(MOD_PREFIX + name for name in
                  ("08/27b.pdf", "08/28a.pdf", "08/28b.pdf",
                   "08/28f.pdf", "09/17a.pdf", "09/29d.pdf", "10/05b.pdf"))
REVIEWED_LINKS = frozenset(JCG_LINKS + MOD_LINKS)
REQUIRED_TEXT = (
    "Six official Japan Coast Guard publication links",
    "Seven official Japan Ministry of Defense PDF links",
    "external official-source links only",
    "not production IPR records",
    "All Japan production records remain held",
    "Japan remains shadow-only; no production or model use is authorized",
    "repository gate was observed unset or unavailable",
    "Visual original review only: no extractable PDF text layer",
    "No extractable text layer; not eight independent archive originals",
    "The oversized October 2 original remains intentionally excluded.",
)


class _JapanLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.official_links = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        d = dict(attrs)
        href = d.get("href", "")
        if ((href.startswith(JCG_PREFIX) and href.endswith(".html"))
                or (href.startswith(MOD_PREFIX) and href.endswith(".pdf"))):
            self.official_links.append((href, set((d.get("rel") or "").split())))


def validate_japan_release_html(html: str) -> list[str]:
    errors = []
    p = _JapanLinks()
    p.feed(html)
    counts = Counter(url for url, _ in p.official_links)
    for url in sorted(REVIEWED_LINKS):
        if counts[url] != 1:
            errors.append("Expected exactly one link for " + url
                          + "; found " + str(counts[url]))
    for url in sorted(set(counts) - REVIEWED_LINKS):
        errors.append("Unreviewed official Japan link: " + url)
    for url, rel in p.official_links:
        if not {"noopener", "noreferrer"} <= rel:
            errors.append("Missing external-link protection: " + url)
    for phrase in REQUIRED_TEXT:
        if phrase not in html:
            errors.append("Missing Japan release qualification: " + phrase)
    for forbidden in ("state/shadow.db", "text_original", "body_original",
                      'href="archive.html?desk=japan"', "data-reference-list"):
        if forbidden in html:
            errors.append("Japan shadow corpus boundary violated: " + forbidden)
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--page", type=Path, default=Path("output/japan.html"))
    args = parser.parse_args(argv)
    try:
        html = args.page.read_text(encoding="utf-8")
        errors = validate_japan_release_html(html)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        errors = [str(exc)]
    for error in errors:
        print("BLOCKED: " + error)
    if errors:
        return 1
    print("Japan release: 6 JCG + 7 MOD original links, boundaries and qualifications verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
