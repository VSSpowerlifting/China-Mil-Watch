"""
A native Brief's cover photograph: the one gate that may give an opened Brief a
curated photograph from the editorial manifest.

A cover is granted only by a manifest entry that names the Brief's slug in
`match.briefs`, is built by `scripts/build_brief_cover.py`, carries a licence
this project accepts with its full credit, and whose retained source and
derivatives still match their recorded digests. Exactly one entry may name a
slug; two are a conflict and grant nothing. The entry must match nothing
else: a cover is not a Signal Veil, an edition veil or a homepage image, so
its other match lists stay empty and it has no `placement`. Any failure
leaves the Brief on its existing opening (the Editorial plate), never on a
guess.

An entry also names the surfaces it is approved for (`surfaces`). It must
include "article", and it may include "catalogue". An entry that names
"catalogue" is a paired cover: one photograph, cropped separately for the card
and the opened article. Neither surface keeps the photograph if the other's
record or files fail (`core.brief_photography`). Any notice the source's terms
require is checked here word for word (`core.source_terms`).

This module checks the opened article's half only. The catalogue card is a
separate surface with its own admission record (`core/catalogue_media.py`),
which must agree with the entry here on credit, licence, source, notice and
treatment. `core/article_media.py` decides how a granted cover is shown. The
contract every cover follows is `docs/BRIEF_PHOTOGRAPHY_CONTRACT.md`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping, Optional

from core.source_terms import notice_problem

BUILDER = "scripts/build_brief_cover.py"
MANIFEST_PATH = Path("site/assets/editorial/manifest.json")
EDITORIAL_ROOT = Path("site/assets/editorial")
#: Where a cover's derivatives are published, relative to the site root.
ROUTE_PREFIX = "assets/editorial/"

ALLOWED_LICENCES = frozenset({"Public domain", "CC BY 4.0"})
LICENCE_NEEDS_LINK = frozenset({"CC BY 4.0"})

#: How a cover is presented, and the change note each makes true. The pixels
#: are the same resized photograph for both; `gradient` adds the IPR navy
#: gradient in CSS over it. A note must describe what the reader sees, so the
#: note follows the treatment on every surface (`core/catalogue_media.py`
#: checks the card's).
TREATMENT_NOTES = {
    "photograph": "Cropped and resized by IPR.",
    "gradient": "Cropped and resized by IPR; IPR gradient overlaid.",
}

#: The surfaces a cover may be approved for. "article" is always required.
SURFACES = frozenset({"article", "catalogue"})
#: What a cover shows: the event the Brief covers, or context for it.
DEPICTS = frozenset({"event", "context"})

_REQUIRED = ("id", "file", "sha256", "alt", "caption", "credit", "creator",
             "license", "source_page", "source_label", "cover_treatment",
             "surfaces", "depicts")
_EXCLUSIVE = ("article_urls", "categories", "threads", "editions", "routes")
_DERIVATIVES = ("-1600.jpg", "-800.webp", "-1600.webp")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(repo_root: Path) -> list:
    try:
        data = json.loads((Path(repo_root) / MANIFEST_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [e for e in data if isinstance(e, dict)] if isinstance(data, list) else []


def is_cover(entry: Optional[Mapping]) -> bool:
    """True for an entry built or matched as a Brief cover. Such an entry
    keeps the cover rules wherever it is used."""
    if not entry:
        return False
    return (entry.get("derivative_builder") == BUILDER
            or bool((entry.get("match") or {}).get("briefs")))


def is_paired(entry: Mapping) -> bool:
    """True when the cover is also approved for its catalogue card."""
    return "catalogue" in (entry.get("surfaces") or ())


def derivative_path(entry: Mapping, suffix: str) -> str:
    """A derivative's path relative to the editorial root."""
    return "derivatives/" + entry["id"] + suffix


def cover_entries(manifest: Iterable[Mapping], slug: str) -> list:
    return [e for e in manifest
            if slug in ((e.get("match") or {}).get("briefs") or ())]


def problem(entry: Mapping, repo_root: Path) -> Optional[str]:
    """None when the entry may serve as a cover, else a reason code."""
    for key in _REQUIRED:
        if not entry.get(key):
            return "incomplete-record:" + key
    if entry.get("derivative_builder") != BUILDER:
        return "not-a-cover-build"
    match = entry.get("match") or {}
    if any(match.get(k) for k in _EXCLUSIVE) or entry.get("placement"):
        return "matches-another-surface"
    if entry["license"] not in ALLOWED_LICENCES:
        return "licence-not-allowed"
    if entry["license"] in LICENCE_NEEDS_LINK and not entry.get("license_url"):
        return "licence-link-missing"
    if not str(entry["source_page"]).startswith("https://"):
        return "source-page-not-https"
    if entry["cover_treatment"] not in TREATMENT_NOTES:
        return "unknown-treatment"
    surfaces = entry["surfaces"]
    if (not isinstance(surfaces, list) or "article" not in surfaces
            or not set(surfaces) <= SURFACES):
        return "surfaces-invalid"
    if entry["depicts"] not in DEPICTS:
        return "depicts-invalid"
    notice = notice_problem(entry)
    if notice:
        return notice
    root = Path(repo_root) / EDITORIAL_ROOT
    source = root / entry["file"]
    if not source.is_file() or sha256_file(source) != entry["sha256"]:
        return "source-hash-mismatch"
    recorded = {d.get("file"): d for d in entry.get("derivatives") or ()}
    for suffix in _DERIVATIVES:
        rel = derivative_path(entry, suffix)
        rec = recorded.get(rel)
        if not rec:
            return "derivative-unrecorded:" + suffix
        path = root / rel
        if not path.is_file() or sha256_file(path) != rec.get("sha256"):
            return "derivative-hash-mismatch:" + suffix
    return None


def brief_cover(slug: str, repo_root: Path,
                manifest: Optional[Iterable[Mapping]] = None) -> Optional[dict]:
    """The article half of the cover for the Brief `slug`, or None. A page
    builder calls `core.brief_photography.article_cover`, which adds the
    paired-cover check."""
    entries = cover_entries(load_manifest(repo_root) if manifest is None else manifest, slug)
    if len(entries) != 1 or problem(entries[0], repo_root):
        return None
    entry = entries[0]
    root = Path(repo_root) / EDITORIAL_ROOT
    derivs = {d["file"]: d for d in entry["derivatives"]}
    files = []
    for suffix in _DERIVATIVES:
        rel = derivative_path(entry, suffix)
        files.append({"file": root / rel, "route": ROUTE_PREFIX + rel,
                      "width": derivs[rel]["width"], "height": derivs[rel]["height"]})
    return {"entry": dict(entry), "files": files,
            "src": files[0], "webp": [f for f in files if f["route"].endswith(".webp")]}
