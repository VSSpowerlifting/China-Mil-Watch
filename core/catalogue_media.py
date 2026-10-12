"""
Catalogue media admission for the Briefs catalogue (`analysis.html`).

One deterministic decision: does a catalogue card show a credited photograph,
or its original Editorial plate? The default is the plate. A photograph is
admitted only by an explicit entry in `site/assets/catalogue/admissions.json`
that also passes every check below. This is a catalogue-surface decision and
nothing else:

  * It never calls the article-image or Signal Veil resolvers
    (`scripts/pw_env.py`, `core/brief_collection.brief_veil`), never reads an
    entry's `cover` or `photo`, and never opens an `output/` sidecar or a
    `*-source-image.*` / `*-veil.*` file. An existing article image, a
    matching source-trail URL or a curated-manifest route is not permission
    for a new surface (Phase 3A ledger, gate 1).
  * Fail-closed: a missing record, a held or denied status, a missing or
    altered file, a licence outside Public domain / CC BY, or an incomplete
    credit all return a plate with a reason code. Nothing raises at build.
    A swapped or removed curated source, or a manifest entry whose licence,
    source page or credit no longer matches the record, also falls to a
    plate: the record was reviewed against that source, not a later one.
  * No. 12 is refused here regardless of what a record says (DECISION_LOG
    2026-10-10, B5), and a record cannot admit a file from a veil path.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

KIND_PHOTOGRAPH = "photograph"
KIND_PLATE = "plate"

ADMISSIONS_PATH = Path("site/assets/catalogue/admissions.json")
MANIFEST_PATH = Path("site/assets/editorial/manifest.json")
MEDIA_ROUTE_PREFIX = "assets/catalogue/media/"
SOURCE_ROOT = "site/assets/editorial/"

# Licences a catalogue photograph may carry. CC BY-SA is out (B6: share-alike
# review), as is anything unlicensed or "all rights reserved".
ALLOWED_LICENCES = frozenset({"Public domain", "CC BY 4.0"})
LICENCE_NEEDS_LINK = frozenset({"CC BY 4.0"})

# Issues the catalogue may never show a photograph for, whatever a record says.
DENIED_ISSUES = frozenset({12})

# Files a catalogue photograph may never be built from or served as. Source
# veils, source images and the homepage veil are other surfaces' media.
_FORBIDDEN = re.compile(
    r"(-source-image|-veil\b|-veil\.|/veil-|veil-ocean|/media/[^/]*-(source-image|veil))",
    re.IGNORECASE)

# Desks the region plate can lift (the plate art has only these two).
PLATE_DESKS = ("china", "singapore")

_REQUIRED = ("alt", "caption", "credit", "creator", "license", "source_page",
             "source_label", "change_note", "served", "source_file",
             "source_manifest_id", "source_sha256", "served_sha256",
             "width", "height")

# Manifest fields the admission record must still agree with at build time.
# The manifest is read only to confirm that the curated source an admission
# was reviewed against is the one on disk; it grants nothing.
_CONTINUITY = ("license", "license_url", "source_page", "credit")


@dataclass(frozen=True)
class CatalogueMedia:
    kind: str
    reason: str
    issue: Optional[int]
    plate_desks: tuple = ()
    photo: Optional[Mapping] = None

    @property
    def is_photograph(self) -> bool:
        return self.kind == KIND_PHOTOGRAPH


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_admissions(path: Optional[Path] = None, *, repo_root: Optional[Path] = None) -> dict:
    """The admission record as `{(issue, week_ending): entry}`. A missing or
    unreadable file is an empty record, so every card falls back to a plate."""
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parent.parent
    target = Path(path) if path else root / ADMISSIONS_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        entries = data["entries"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    out = {}
    for e in entries:
        if isinstance(e, dict) and isinstance(e.get("issue"), int) and e.get("week_ending"):
            out[(e["issue"], str(e["week_ending"]))] = e
    return out


def _plate_desks(row: Mapping) -> tuple:
    """Desks lifted on the plate: the China Desk for an earlier issue (it
    published them all; the Series table says so), otherwise the Brief's own
    desks the plate can draw."""
    entry = row["entry"]
    if row.get("kind") == "issue":
        return ("china",)
    return tuple(d for d in (entry.get("desks") or ()) if d in PLATE_DESKS)


def _manifest_entry(manifest_id: str, repo_root: Path) -> Optional[Mapping]:
    try:
        rows = json.loads((repo_root / MANIFEST_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for row in rows if isinstance(rows, list) else ():
        if isinstance(row, dict) and row.get("id") == manifest_id:
            return row
    return None


def _check(entry: Mapping, repo_root: Path) -> Optional[str]:
    """None when the entry passes, else a reason code."""
    for key in _REQUIRED:
        if entry.get(key) in (None, "", 0):
            return "incomplete-record:" + key
    source = str(entry["source_file"])
    served = str(entry["served"])
    if not source.startswith(SOURCE_ROOT) or ".." in source:
        return "source-outside-editorial-assets"
    if not served.startswith(MEDIA_ROUTE_PREFIX) or ".." in served:
        return "served-outside-catalogue-media"
    if _FORBIDDEN.search(source) or _FORBIDDEN.search(served):
        return "veil-or-source-image-path"
    if entry["license"] not in ALLOWED_LICENCES:
        return "licence-not-allowed"
    if entry["license"] in LICENCE_NEEDS_LINK and not entry.get("license_url"):
        return "licence-link-missing"
    if not str(entry["source_page"]).startswith("https://"):
        return "source-page-not-https"
    # Origin continuity: the curated source this admission was reviewed
    # against must still be the file on disk and the manifest entry it names.
    # A swapped or removed source fails to a plate instead of silently
    # keeping an old "admitted" route.
    manifest_id = str(entry["source_manifest_id"])
    if not Path(source).name.startswith(manifest_id + "-"):
        return "source-not-from-manifest-entry"
    source_path = repo_root / source
    if not source_path.is_file():
        return "source-missing"
    if sha256_file(source_path) != entry["source_sha256"]:
        return "source-hash-mismatch"
    curated = _manifest_entry(manifest_id, repo_root)
    if curated is None:
        return "manifest-entry-missing"
    for key in _CONTINUITY:
        if (curated.get(key) or "") != (entry.get(key) or ""):
            return "manifest-changed:" + key
    path = repo_root / "site" / served
    if not path.is_file():
        return "file-missing"
    if sha256_file(path) != entry["served_sha256"]:
        return "hash-mismatch"
    return None


def resolve_catalogue_media(row: Mapping, admissions: Mapping, *,
                            repo_root: Optional[Path] = None) -> CatalogueMedia:
    """The catalogue media for one collection row (`{"entry", "kind", ...}`)."""
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parent.parent
    entry = row["entry"]
    issue = entry.get("issue")
    desks = _plate_desks(row)

    def plate(reason):
        return CatalogueMedia(KIND_PLATE, reason, issue if isinstance(issue, int) else None, desks)

    if entry.get("synthetic") or entry.get("is_review"):
        return plate("not-a-published-brief")
    if not isinstance(issue, int):
        return plate("unnumbered")
    if issue in DENIED_ISSUES:
        return plate("denied")
    record = admissions.get((issue, str(entry.get("date"))))
    if record is None:
        return plate("no-admission-record")
    if record.get("status") != "admitted":
        return plate(str(record.get("status") or "held"))
    problem = _check(record, root)
    if problem:
        return plate(problem)
    photo = {k: record.get(k, "") for k in (
        "alt", "caption", "credit", "creator", "creator_native", "creator_native_lang",
        "license", "license_url", "source_page", "source_label", "date_note",
        "change_note", "served", "width", "height", "focal")}
    return CatalogueMedia(KIND_PHOTOGRAPH, "admitted", issue, (), photo)


def audit_rows(rows, admissions: Mapping, *, repo_root: Optional[Path] = None) -> list:
    """One dict per row: what the catalogue will show and why. For receipts."""
    out = []
    for row in rows:
        m = resolve_catalogue_media(row, admissions, repo_root=repo_root)
        e = row["entry"]
        out.append({"issue": e.get("issue"), "slug": e.get("slug"), "date": str(e.get("date")),
                    "kind": m.kind, "reason": m.reason, "plate_desks": list(m.plate_desks),
                    "served": (m.photo or {}).get("served"),
                    "credit": (m.photo or {}).get("credit"),
                    "license": (m.photo or {}).get("license")})
    return out
