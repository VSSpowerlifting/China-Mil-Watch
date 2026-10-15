#!/usr/bin/env python3
"""Build an explicitly PRIVATE China curation review preview outside the repo.

A triage ledger is not a publication allowlist. This program neither invokes
the production renderer nor changes the archive, index, database, or sitemap.
"""
import argparse
from collections import Counter
from html import escape
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_china_curation_review import validate_ledger  # noqa: E402

INDEX = ROOT / "output" / "corpus-index.json"
LEDGER = ROOT / "research/china/archive-curation-triage-2026-10-15.json"

STYLE = """
:root{font-family:system-ui,-apple-system,sans-serif;color:#193140;background:#fbfaf6}
*{box-sizing:border-box}body{margin:0}main,header,footer{max-width:1060px;margin:auto;padding:20px}
header{padding-top:36px}a{color:#11647b}a:focus-visible,input:focus-visible{outline:3px solid #d58a3f}
h1{font-size:clamp(1.8rem,4vw,3.1rem);letter-spacing:-.035em;margin:.3em 0}
h2{margin:1.8em 0 .6em}p{line-height:1.6}.eyebrow{text-transform:uppercase;letter-spacing:.12em;font-weight:750;font-size:.74rem}
.notice{border-top:4px solid #92512c;border-bottom:1px solid #d5c3b5;padding:15px 0}
.counts{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}.count{background:#e9eee9;padding:14px;border-radius:4px;min-width:150px}
.count strong{font-size:1.6rem;display:block}nav{display:flex;flex-wrap:wrap;gap:20px;border-block:1px solid #d0d5d5;padding:12px 0}
.record{border-bottom:1px solid #dce2e2;padding:17px 0;list-style:none;max-width:100%}
.record h3{font-size:1.08rem;margin:0 0 .4em}.record p{margin:.35em 0;color:#40535c}
.record .meta{font-size:.85rem}.record .cue{font-size:.88rem;font-weight:700;color:#613c23}
ul.records{padding:0}.small{font-size:.88rem;color:#53646c}
input{border:1px solid #85979b;padding:12px;width:100%;font-size:1rem}
body.private::before{content:"PRIVATE DRAFT · NOT A PUBLIC EDITORIAL SELECTION";display:block;background:#71392e;color:#fff;text-align:center;padding:9px;font-weight:750;font-size:.78rem;letter-spacing:.06em}
summary{cursor:pointer;font-weight:650;margin:1.1em 0}.empty{padding:1.4em;color:#656565}
@media print{body.private::before{color:#111;background:white;border-bottom:2px solid black}}
"""

SEARCH_SCRIPT = """
(function(){
  var q=document.getElementById('record-query'),list=document.getElementById('record-list');
  if(!q||!list)return;
  q.addEventListener('input',function(){
    var term=q.value.trim().toLocaleLowerCase(),shown=0;
    Array.prototype.forEach.call(list.querySelectorAll('.record'),function(r){
      var okay=r.textContent.toLocaleLowerCase().indexOf(term)>=0;
      r.hidden=!okay;if(okay)shown++;
    });
    document.getElementById('match-count').textContent=
      shown.toLocaleString()+' entries shown from this page';
  });
})();
"""


def h(value):
    return escape(str(value), quote=True)


def _row(record, decision=None, source=None, status=None):
    ident = int(record[0])
    name = record[5] or record[4] or "(Untitled captured record)"
    secondary = ("<p class='small' lang='en'>English title: %s</p>" %
                 h(record[4])) if record[4] and record[5] and record[4] != record[5] else ""
    category = ""
    if decision is not None:
        category = ("<p class='cue'>%s · %s · NOT APPROVED</p>"
                    "<p>%s</p>" %
                    (h(decision["disposition"].replace("_", " ")),
                     h(decision["review_stage"].replace("_", " ")),
                     h(decision["rationale"])))
        if decision["representative_id"] is not None:
            category += ("<p>Proposed grouping under record #%d; both records remain"
                         " separately preserved.</p>" % decision["representative_id"])
    meta = ("%s · %s · %s · record #%d" %
            (h(record[1]), h(source or ""), h(status or ""), ident))
    return ("<li class='record'><h3><a rel='noopener noreferrer' "
            "href='https://indopacificrecord.org/record/%d.html'>%s</a></h3>"
            "%s<p class='meta'>%s</p>%s</li>" %
            (ident, h(name), secondary, meta, category))


def _page(title, section, body, counts, baseline, total, count):
    items = "".join("<div class='count'><strong>%s</strong>%s</div>" %
                    (h(value), h(label)) for value, label in counts)
    heading = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name=\"robots\" content=\"noindex,nofollow,noarchive\">"
        "<meta http-equiv='Content-Security-Policy' "
        "content=\"default-src 'none'; style-src 'unsafe-inline';"
        " script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        "<title>%s — PRIVATE IPR curation preview</title>"
        "<style>%s</style></head><body class='private'>"
        "<header><p class='eyebrow'>Indo-Pacific Record · editorial engineering review</p>"
        "<h1>%s</h1>"
        "<p class='notice'><strong>Not a published archive or editorial endorsement.</strong> "
        "Every status shown is a research-review proposal; even a ledger receipt "
        "would not authenticate approval. This page is generated locally and "
        "must not be deployed, indexed, or served publicly.</p>"
        "<nav aria-label='Review preview navigation'>"
        "<a href='index.html'>Review proposals</a>"
        "<a href='preserved.html'>All preserved records</a>"
        "</nav><div class='counts'>%s</div>"
        "<p class='small'>Source snapshot: %s · %s records. "
        "All links to original record pages lead to the existing public IPR "
        "site; no original record is reproduced or changed here.</p>"
        "</header><main><h2>%s</h2>"
        "<p class='small'>All records on this page remain readable with JavaScript disabled. "
        "The optional local title/filter box below never edits the source.</p>"
        "<label for='record-query'>Filter entries on this page</label>"
        "<input id='record-query' type='search' placeholder='Search visible entries' autocomplete='off'>"
        "<p class='small' id='match-count' aria-live='polite'>%s entries shown from this page</p>"
        "<ul class='records' id='record-list'>%s</ul></main>"
        "<footer><p>Read-only internal editorial QA · No selection exported · "
        "No publication authorization · No source/citation deletion</p></footer>"
        "<script>%s</script></body></html>" %
        (h(title), STYLE, h(title), items, h(baseline), h(total),
         h(section), h(count), body, SEARCH_SCRIPT)
    )
    return heading


def _check_external_new_dir(out):
    out = Path(out).expanduser()
    if not out.is_absolute():
        raise ValueError("private preview needs an absolute output directory")
    root = ROOT.resolve()
    target = out.resolve()
    if (out.exists() or out.is_symlink()
            or target == root or root in target.parents
            or target in root.parents
            or not out.parent.is_dir()
            or out.parent.is_symlink()):
        raise ValueError("private preview requires a new external directory")
    return out


def preview(index, ledger):
    """Pure rendering: fail closed before any filesystem creation."""
    summary = validate_ledger(index, ledger)
    rows = {r[0]: r for r in index["records"]}
    sources = index["sources"]
    states = index["states"]
    reviews = {x["id"]: x for x in ledger["decisions"]}
    docket_ids = sorted(reviews, key=lambda i: (rows[i][1], i), reverse=True)
    all_ids = sorted(rows, key=lambda i: (rows[i][1], i), reverse=True)

    def article(ident, review):
        r = rows[ident]
        source = sources[r[2]]
        state = states[r[3]]
        return _row(r, review, source.get("label", source["code"]),
                    state.get("label", state["code"].replace("_", " ")))

    proposed = "".join(article(i, reviews[i]) for i in docket_ids)
    entire = "".join(article(i, None) for i in all_ids)
    date = index["snapshot"]["date"]
    common = [
        (summary["china_preserved"], "China records preserved"),
        (summary["china_unreviewed_preserved"], "China records without a review docket"),
        (summary["owner_approved"], "Owner approvals in ledger"),
    ]
    private = _page(
        "China curation — review proposals", "Unsigned China review docket",
        proposed or "<li class='empty'>No review proposals exist.</li>",
        common + [(len(reviews), "Entries proposed for review")],
        date, len(rows), len(docket_ids))
    full = _page(
        "Full preserved corpus — unchanged", "Every archived source record",
        entire, common + [(len(rows), "All preserved desk records")],
        date, len(rows), len(all_ids))
    return {"index.html": private, "preserved.html": full}, summary


def write_preview(output, pages):
    target = _check_external_new_dir(output)
    # The caller must supply a fresh directory, never output/ or a shared
    # production site path. Refuse even an existing empty destination.
    target.mkdir(mode=0o700)
    try:
        for name, html in sorted(pages.items()):
            if name not in ("index.html", "preserved.html"):
                raise ValueError("unexpected preview filename")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            fd = os.open(target / name, flags, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                file.write(html)
    except Exception:
        # Keep the private evidence inspectable on failure; never delete or
        # overwrite another file. The command exits nonzero.
        raise
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    pages, report = preview(
        json.loads(args.index.read_text(encoding="utf-8")),
        json.loads(args.ledger.read_text(encoding="utf-8")))
    path = write_preview(args.output_dir, pages)
    print(json.dumps({
        "private_preview": str(path / "index.html"),
        "preserved_view": str(path / "preserved.html"),
        "owner_approved": report["owner_approved"],
        "editorial_publication_authorized": False,
        "source_snapshot": report["index_snapshot"],
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
