"""Complete local HTML/CSS and script delivery budgets (stdlib only)."""
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Dependencies(HTMLParser):
    def __init__(self):
        super().__init__()
        self.css, self.js, self.inline_css, self.inline_js = [], [], [], []
        self.assets = []
        self.active = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("style"):
            self.inline_css.append(attrs["style"])
        if tag == "link" and "stylesheet" in attrs.get("rel", "").split():
            self.css.append(attrs.get("href", ""))
        if tag in ("img", "source"):
            if attrs.get("src"):
                self.assets.append(attrs["src"])
            self.assets.extend(part.strip().split()[0] for part in attrs.get("srcset", "").split(",") if part.strip())
        if tag == "video" and attrs.get("poster"):
            self.assets.append(attrs["poster"])
        if tag == "link" and set(attrs.get("rel", "").split()) & {"icon", "apple-touch-icon", "preload"}:
            self.assets.append(attrs.get("href", ""))
        if tag == "style":
            self.active = self.inline_css
        if tag == "script" and attrs.get("type", "") in ("", "module", "text/javascript", "application/javascript"):
            if attrs.get("src"):
                self.js.append(attrs["src"])
            else:
                self.active = self.inline_js

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.active = None

    def handle_data(self, data):
        if self.active is not None:
            self.active.append(data)


def measure_page(page, root):
    """Count each local dependency once, including nested imports and inline JS.

    Inline CSS already belongs to HTML bytes. Missing local files fail the gate.
    External dependencies are reported, so remote delivery cannot go unnoticed.
    """
    root, page = Path(root).resolve(), Path(page).resolve()
    parser = Dependencies()
    parser.feed(page.read_text(encoding="utf-8"))
    css, js, external = set(), set(), set()
    assets, external_assets = set(), set()

    def local(url, owner, remote=external):
        parsed = urlsplit(url)
        if parsed.scheme == "data":
            return None  # Embedded bytes already belong to HTML/CSS.
        if parsed.scheme or parsed.netloc:
            remote.add(url)
            return None
        if not parsed.path:
            return None
        path = unquote(parsed.path)
        target = (root / path.lstrip("/") if path.startswith("/") else owner.parent / path).resolve()
        if root not in target.parents:
            raise ValueError("dependency escapes rendered root: " + url)
        if not target.is_file():
            raise ValueError("missing local dependency: " + str(target))
        return target

    imports = re.compile(r'@import\s+(?:url\(\s*)?[\"\']?([^\s\"\'\);]+)', re.I)
    modules = re.compile(r'(?:\b(?:import|export)\s+(?:[^;]*?\sfrom\s+)?|\bimport\s*\(\s*)[\"\']([^\"\']+)[\"\']')

    def visit(url, owner, found, pattern):
        target = local(url, owner)
        if target is None or target in found:
            return
        found.add(target)
        text = re.sub(r'/\*.*?\*/', '', target.read_text(encoding="utf-8"), flags=re.S)
        for dependency in pattern.findall(text):
            visit(dependency, target, found, pattern)

    for url in parser.css:
        visit(url, page, css, imports)
    for inline in parser.inline_css:
        for url in imports.findall(inline):
            visit(url, page, css, imports)
    for url in parser.js:
        visit(url, page, js, modules)
    for inline in parser.inline_js:
        for url in modules.findall(inline):
            visit(url, page, js, modules)
    # Conservative asset inventory: all CSS URLs, fonts, image variants and
    # icons. Actual browser requests choose a subset (viewport/font use/cache).
    urls = re.compile(r'url\(\s*[\"\']?([^\"\'\)\s]+)', re.I)

    def asset(url, owner):
        target = local(url, owner, external_assets)
        if target is not None and target not in css and target not in js:
            assets.add(target)

    for url in parser.assets:
        asset(url, page)
    for owner in css:
        contents = re.sub(r'/\*.*?\*/', '', owner.read_text(encoding="utf-8"), flags=re.S)
        for url in urls.findall(contents):
            asset(url, owner)
    for inline in parser.inline_css:
        for url in urls.findall(inline):
            asset(url, page)
    return {"html_css_bytes": page.stat().st_size + sum(p.stat().st_size for p in css),
            "js_bytes": sum(p.stat().st_size for p in js) + sum(len(s.encode("utf-8")) for s in parser.inline_js),
            "css": sorted(p.relative_to(root).as_posix() for p in css),
            "js": sorted(p.relative_to(root).as_posix() for p in js),
            "external": sorted(external),
            "asset_bytes": sum(p.stat().st_size for p in assets),
            "assets": sorted(p.relative_to(root).as_posix() for p in assets),
            "external_assets": sorted(external_assets)}
