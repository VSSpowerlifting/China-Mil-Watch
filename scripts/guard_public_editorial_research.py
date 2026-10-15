"""Validate IPR research index against *actual rendered site* before any release."""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from core.public_editorial_research import load_catalog


class RenderHold(ValueError):
    pass


class AnchorCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []
        self.published = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.hrefs.append(attrs.get("href", ""))
        if tag == "section" and attrs.get("aria-labelledby") == "ipr-published-research-heading":
            self.published = True


def verify_render(root, catalog=None):
    root = Path(root).resolve()
    if not root.is_dir():
        raise RenderHold("actual rendered site directory is missing")
    entries = load_catalog() if catalog is None else catalog
    by_desk = {}
    for entry in entries:
        by_desk.setdefault(entry["desk"], []).append(entry)
        rel = entry["ipr_page"]
        if rel.startswith("/") or ".." in Path(rel).parts:
            raise RenderHold("invalid IPR route")
        page = (root / rel).resolve()
        if root not in page.parents or not page.is_file() or page.is_symlink():
            raise RenderHold("approved IPR article is not really rendered: " + rel)
        brief = AnchorCollector()
        brief.feed(page.read_text(encoding="utf-8"))
        for source in entry["source_links"]:
            if source["publisher_url"] not in brief.hrefs:
                raise RenderHold("published Brief lacks approved source citation: " + rel)

    for desk, papers in by_desk.items():
        desk_page = (root / (desk + ".html")).resolve()
        if root not in desk_page.parents or not desk_page.is_file():
            raise RenderHold("approved country page missing: " + desk)
        text = desk_page.read_text(encoding="utf-8")
        page = AnchorCollector()
        page.feed(text)
        if not page.published:
            raise RenderHold("permanent IPR research heading missing")
        for paper in papers:
            if page.hrefs.count(paper["ipr_page"]) != 1:
                raise RenderHold("expected exactly one IPR article link on desk page")
            for src in paper["source_links"]:
                if page.hrefs.count(src["publisher_url"]) < 1:
                    raise RenderHold("official original link not rendered on desk page")
        if "not a production source-text archive" not in text:
            raise RenderHold("editorial vs collector distinction missing")
        if 'href="archive.html?desk=' + desk + '"' in text:
            raise RenderHold("unadmitted source corpus accidentally exposed")
        if "publisher's article bodies" in text or "privately_preserved = true" in text:
            raise RenderHold("publisher rehost or private custody misrepresented")
    return {"approved_ipr_publications": len(entries),
            "desk_count": len(by_desk),
            "linked_originals": sum(len(x["source_links"]) for x in entries),
            "source_bodies_rehosted_by_this_index": False,
            "private_original_custody_verified_by_this_index": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    try:
        outcome = verify_render(args.root)
        print(outcome)
    except (RenderHold, OSError, UnicodeError, ValueError) as exc:
        parser.exit(1, "IPR permanent research publication gate: %s\n" % exc)


if __name__ == "__main__":
    main()
