"""Per-route invariants for the 17 Brief article routes.
usage: invariants.py <hist_root> <site_root> <out.json>
"""
import json, re, sys
from pathlib import Path
from bs4 import BeautifulSoup

HIST = ["2026-05-09","2026-05-16","2026-05-23","2026-05-30","2026-06-06","2026-06-13","2026-06-20",
        "2026-06-27","2026-07-04","2026-07-11","2026-07-18","2026-08-01","2026-08-08","2026-08-15"]
NATIVE = ["maritime-cooperation-2026","trident-resolve-regional-scale-specific-chinese-tasks",
          "xiangshan-security-frames-defense-ties"]

def ws(s): return re.sub(r"\s+", " ", s or "").strip()

def extract(html):
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("main") or soup
    meta = {}
    for m in soup.find_all("meta"):
        k = m.get("property") or m.get("name")
        if k and (k.startswith("og:") or k.startswith("twitter:") or k in ("description","robots","author")):
            meta[k] = m.get("content")
    links = {l.get("rel")[0] if isinstance(l.get("rel"), list) else l.get("rel"): l.get("href")
             for l in soup.find_all("link") if l.get("rel") and ("canonical" in l.get("rel") or "alternate" in l.get("rel"))}
    article = main.find("article") or main
    return {
        "title": ws(soup.title.string if soup.title else ""),
        "meta": meta, "links": links,
        "h1": [ws(h.get_text()) for h in main.find_all("h1")],
        "headings": [(h.name, h.get("id"), ws(h.get_text())) for h in main.find_all(["h1","h2","h3"])],
        "ids": sorted({e["id"] for e in main.find_all(id=True)}),
        "article_paragraphs": [ws(p.get_text()) for p in article.find_all("p")],
        "hrefs": [(a.get("href"), ws(a.get_text())) for a in main.find_all("a", href=True)],
        "external_hrefs": sorted({a["href"] for a in main.find_all("a", href=True) if a["href"].startswith("http")}),
        "lang_spans": [(e.get("lang"), ws(e.get_text())) for e in main.find_all(attrs={"lang": True})],
        "imgs": [(i.get("src"), i.get("alt")) for i in main.find_all("img")],
        "figcaptions": [ws(f.get_text()) for f in main.find_all("figcaption")],
        "citation": ws((main.find(id="pw-cite") or main.find(class_="cite-text") or soup.new_tag("x")).get_text()),
        "provenance": ws((main.find(class_="historical-provenance") or soup.new_tag("x")).get_text()),
        "byline": ws((main.find(class_="brief-byline") or soup.new_tag("x")).get_text()),
        "model_flagged_count": main.get_text().count("Model-flagged"),
    }

def main():
    hist, site, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    res = {}
    for d in HIST:
        res[f"the-pla-watch/posts/{d}.html"] = extract((hist / f"the-pla-watch/posts/{d}.html").read_text())
    for s in NATIVE:
        res[f"briefs/{s}.html"] = extract((site / f"briefs/{s}.html").read_text())
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(len(res), "routes ->", out)

if __name__ == "__main__": main()
