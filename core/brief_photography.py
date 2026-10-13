"""
The opened article's half of a paired Brief cover.

`core.brief_cover` checks the cover's own record and files.
`core.catalogue_media` checks the card, including the cover's files, whenever
a card is cut from a cover. This module adds the reverse direction, so one
failure takes the photograph off both surfaces. If a cover is approved for
the catalogue, the article keeps it only while that card still resolves to
the photograph.

A cover approved for the article alone ("surfaces": ["article"]) is not paired
and is unaffected. A card admitted from a non-cover manifest entry, such as
Nos. 8 and 9, never reaches an article: the article grant is the cover's
`match.briefs`, and a catalogue record cannot supply one.

Nothing here writes, builds or replaces an image. A failed pair leaves the
article on its Editorial plate. The contract is
`docs/BRIEF_PHOTOGRAPHY_CONTRACT.md`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, Optional

from core import brief_cover as bcv
from core import catalogue_media as cm


def pair_problem(entry: Mapping, brief: Mapping, repo_root: Path,
                 admissions: Optional[Mapping] = None) -> Optional[str]:
    """None when the cover `entry` may stay on the opened Brief `brief` (its
    collection entry: issue, date, slug) as far as pairing goes. Otherwise a
    reason code. A paired cover stays only while this Brief's own card
    resolves to a photograph cut from this same cover."""
    if not bcv.is_paired(entry):
        return None
    if admissions is None:
        admissions = cm.load_admissions(repo_root=repo_root)
    card = cm.resolve_catalogue_media({"kind": "brief", "entry": brief}, admissions,
                                      repo_root=repo_root)
    if not card.is_photograph:
        return "pair-card:" + card.reason
    record = admissions.get((brief.get("issue"), str(brief.get("date")))) or {}
    if record.get("source_manifest_id") != entry["id"]:
        return "pair-card-shows-another-image"
    return None


def article_cover(brief: Mapping, repo_root: Path, *,
                  manifest: Optional[Iterable[Mapping]] = None,
                  admissions: Optional[Mapping] = None) -> Optional[dict]:
    """The cover the opened Brief may show, or None. `brief` is the Brief's
    collection entry (`issue`, `date`, `slug`), the same one its catalogue
    card is resolved from."""
    cover = bcv.brief_cover(brief["slug"], repo_root, manifest=manifest)
    if cover is None or pair_problem(cover["entry"], brief, repo_root, admissions):
        return None
    return cover
