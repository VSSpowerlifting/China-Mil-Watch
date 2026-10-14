"""Read-only inventory of a sitewide IPR render candidate; NEVER authorizes publication.

Run after scripts.run_briefs_render_release --scope report-only in a clean,
disposable checkout. Count tracked, staged, untracked and ignored output drift.
Unknown, source/data and media changes block a cosmetic-only preview.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from html.parser import HTMLParser

from scripts.guard_briefs_render_scope import classify_output_changes

COSMETIC_CSS = frozenset({
    "output/styles.css", "output/home.css", "output/record.css",
    "output/briefs.css", "output/relief.css",
})
HTML_SINGLE = frozenset({"output/index.html", "output/analysis.html"})
HTML_ROUTES = (
    re.compile(r"^output/(?:record/[^/]+|briefs/[^/]+|the-pla-watch/posts/[^/]+)\.html$"),
)
SHA_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def classify(path: str) -> str:
    """Even an allowed path requires human review, not publication."""
    if path in COSMETIC_CSS:
        return "css-review"
    if path in HTML_SINGLE or any(rule.fullmatch(path) for rule in HTML_ROUTES):
        return "html-manual-review"
    return "blocked-noncosmetic"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 18), b""):
            digest.update(chunk)
    return digest.hexdigest()



def css_source_parity(root: Path) -> list:
    """Attest each generated stylesheet is byte-identical to its source.

    The production renderer copies these files verbatim. A review-only output
    inventory must not greenlight a stale, truncated or accidentally modified
    CSS artifact. This check does not edit either directory.
    """
    root = Path(root)
    checks = []
    for output_rel in sorted(COSMETIC_CSS):
        source_rel = "site/preview/" + Path(output_rel).name
        source = root / source_rel
        generated = root / output_rel
        safe_files = (source.is_file() and not source.is_symlink()
                      and generated.is_file() and not generated.is_symlink())
        source_hash = sha256(source) if source.is_file() and not source.is_symlink() else None
        generated_hash = (sha256(generated) if generated.is_file()
                          and not generated.is_symlink() else None)
        checks.append({
            "source": source_rel,
            "generated": output_rel,
            "source_sha256": source_hash,
            "generated_sha256": generated_hash,
            "identical": bool(safe_files and source_hash == generated_hash),
        })
    return checks



class _DocumentarySignature(HTMLParser):
    """Compare documentary content while disregarding purely presentational CSS."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.links = []
        self.media = []
        self.metadata = []
        self.scripts = []
        self._style_depth = 0
        self._script_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        values = dict(attrs)
        if tag == "style":
            self._style_depth += 1
        if tag == "script":
            self._script_depth += 1
        if tag in ("a", "link") and "href" in values:
            self.links.append((tag, values["href"]))
        if tag in ("img", "source", "video", "audio", "iframe"):
            self.media.append((tag, tuple(
                (key, values[key]) for key in
                ("src", "srcset", "poster", "alt", "title") if key in values)))
        if tag == "meta":
            self.metadata.append((values.get("name"), values.get("property"),
                                  values.get("content")))
        if tag in ("time", "a") and "datetime" in values:
            self.metadata.append((tag, "datetime", values["datetime"]))
        if "data-source" in values:
            self.metadata.append((tag, "data-source", values["data-source"]))

    def handle_endtag(self, tag):
        if tag.lower() == "style":
            self._style_depth = max(0, self._style_depth - 1)
        if tag.lower() == "script":
            self._script_depth = max(0, self._script_depth - 1)

    def handle_data(self, data):
        if self._style_depth:
            return
        if self._script_depth:
            self.scripts.append(data)
        elif data.strip():
            self.text.append(data)

    def result(self):
        return {
            "text": " ".join(" ".join(self.text).split()),
            "links": self.links,
            "media": self.media,
            "metadata": self.metadata,
            "scripts": "".join(self.scripts),
        }


def html_documentary_fidelity(root: Path, changes: list) -> list:
    """Fail closed if a cosmetic release rewrites article facts or references.

    Compare changed HTML to the reviewed HEAD baseline, never against a draft.
    Pure CSS/styling edits may pass, but text, citations, images, source keys,
    metadata and executable scripts must remain stable for this release.
    """
    root = Path(root)
    results = []
    for entry in changes:
        if entry["kind"] != "html-manual-review":
            continue
        path = entry["path"]
        previous = subprocess.run(
            ["git", "show", "HEAD:" + path], cwd=root, capture_output=True)
        if previous.returncode != 0:
            results.append({"path": path, "identical": False,
                            "changed_fields": ["missing-tracked-baseline"]})
            continue
        after = (root / path).read_bytes()
        def signature(contents):
            parser = _DocumentarySignature()
            parser.feed(contents.decode("utf-8"))
            parser.close()
            return parser.result()
        try:
            before_sig = signature(previous.stdout)
            after_sig = signature(after)
            differences = [
                key for key in before_sig if before_sig[key] != after_sig[key]
            ]
        except (UnicodeDecodeError, ValueError) as exc:
            differences = ["invalid-html-encoding:" + type(exc).__name__]
        results.append({"path": path, "identical": not differences,
                        "changed_fields": differences})
    return results


def inventory(root: Path, expected_db_sha: str) -> dict:
    root = Path(root).resolve()
    if not SHA_PATTERN.fullmatch(expected_db_sha):
        raise ValueError("expected DB SHA must be exactly 64 lowercase hex characters")
    db = root / "pla_watch.db"
    if sha256(db) != expected_db_sha:
        raise RuntimeError("tracked database hash changed during render")
    if any((root / ("pla_watch.db" + suffix)).exists()
           for suffix in ("-wal", "-shm")):
        raise RuntimeError("tracked database acquired a WAL or SHM sidecar")
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all", "-z"], cwd=root)
    outside = []
    for entry in status.split(b"\0"):
        if not entry:
            continue
        path = entry[3:].decode("utf-8", errors="surrogateescape")
        # A rename's second -z path is conservatively treated as outside.
        if path and not path.startswith("output/"):
            outside.append(path)
    changed, _ = classify_output_changes(root)
    rows = []
    for path in sorted(changed):
        target = root / path
        if target.is_symlink():
            kind = "blocked-symlink"
        elif not target.is_file():
            kind = "blocked-deleted-or-nonfile"
        else:
            kind = classify(path)
        rows.append({
            "path": path, "kind": kind,
            "sha256": sha256(target) if target.is_file() and not target.is_symlink() else None,
            "bytes": target.stat().st_size if target.is_file() and not target.is_symlink() else None,
        })
    css_parity = css_source_parity(root)
    html_fidelity = html_documentary_fidelity(root, rows)
    return {
        "schema": "ipr-sitewide-render-preview-v1",
        "css_source_parity": css_parity,
        "css_source_mismatches": [x["generated"] for x in css_parity if not x["identical"]],
        "html_documentary_fidelity": html_fidelity,
        "html_content_mismatches": [x["path"] for x in html_fidelity if not x["identical"]],
        "reviewed_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "db_sha256_unchanged": expected_db_sha,
        "total_changed": len(rows),
        "css_to_review": sum(r["kind"] == "css-review" for r in rows),
        "html_to_review": sum(r["kind"] == "html-manual-review" for r in rows),
        "blocked": [r["path"] for r in rows if r["kind"].startswith("blocked-")],
        "outside_output": outside,
        "requires_human_output_review": True,
        "publish_authorized": False,
        "changes": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--expected-db-sha", required=True)
    parser.add_argument("--report", required=True)
    opts = parser.parse_args(argv)
    report = inventory(Path(opts.root), opts.expected_db_sha)
    destination = Path(opts.report).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Sitewide preview: %d CSS, %d HTML, %d blocked, %d outside output" % (
        report["css_to_review"], report["html_to_review"],
        len(report["blocked"]), len(report["outside_output"])))
    print("Review receipt:", destination)
    print("CSS source parity: %d exact / %d mismatched" % (
        len(report["css_source_parity"]) - len(report["css_source_mismatches"]),
        len(report["css_source_mismatches"])))
    if report["blocked"] or report["outside_output"] or report["css_source_mismatches"] or report["html_content_mismatches"]:
        print("BLOCKED: noncosmetic, outside-output, CSS parity or documentary HTML drift.")
        return 2
    if report["total_changed"] == 0:
        print("NO CHANGE: review would be empty; check source and output baseline.")
        return 3
    print("Documentary HTML parity: %d safe / %d changed" % (
        len(report["html_documentary_fidelity"]) - len(report["html_content_mismatches"]),
        len(report["html_content_mismatches"])))
    print("PREVIEW ONLY: human diff/visual review and separate authorization required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
