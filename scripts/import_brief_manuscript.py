"""Extract a frozen DOCX's exact text and inline links; never rewrite prose.

Paragraph indices are explicit editorial selections, zero-based. Output is an
intermediate JSON snapshot, not publication approval or a numbered Brief.
"""
import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def extract(path, *, expected_sha256, title_index, subtitle_index, body_start, body_stop):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("DOCX does not match frozen manuscript SHA-256")
    with ZipFile(path) as archive:
        doc = ET.fromstring(archive.read("word/document.xml"))
        rels = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
    if any(doc.iter(W + "ins")) or any(doc.iter(W + "del")):
        raise ValueError("resolve tracked changes before freezing the manuscript")
    links = {r.attrib["Id"]: r.attrib["Target"] for r in rels
             if r.attrib.get("Type", "").endswith("/hyperlink")}
    paragraphs = doc.find(W + "body").findall(W + "p")
    def text(element):
        return "".join(t.text or "" for t in element.iter(W + "t"))
    sources, body = {}, []
    for paragraph in paragraphs[body_start:body_stop]:
        runs = []
        for element in paragraph:
            if element.tag == W + "pPr":
                continue
            value = text(element)
            if not value:
                continue
            run = {"text": value}
            if element.tag == W + "hyperlink":
                url = links[element.attrib[R + "id"]]
                if url not in sources:
                    sources[url] = "s%d" % (len(sources) + 1)
                run["source"] = sources[url]
            if runs and runs[-1].get("source") == run.get("source"):
                runs[-1]["text"] += value
            else:
                runs.append(run)
        body.append(runs)
    return {"title": text(paragraphs[title_index]),
            "dek": text(paragraphs[subtitle_index]),
            "manuscript_sha256": expected_sha256,
            "body_paragraphs": body,
            "publisher_references": [{"id": ident, "url": url} for url, ident in sources.items()]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("docx", type=Path)
    p.add_argument("--expected-sha256", required=True)
    for field in ("title-index", "subtitle-index", "body-start", "body-stop"):
        p.add_argument("--" + field, required=True, type=int)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    result = extract(args.docx, expected_sha256=args.expected_sha256,
                     title_index=args.title_index, subtitle_index=args.subtitle_index,
                     body_start=args.body_start, body_stop=args.body_stop)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
