#!/usr/bin/env python3
"""Deterministically re-render only the fourteen existing historical Brief HTML pages.

The immutable JSON sidecars and existing historic authorship/veil evidence are
the source of truth. No sources, images, feed, model API, DB or site routes are
written. --check fails if checked-in HTML differs from the current renderer.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.edition_identity import resolve_identity
from scripts.rerender_pla_watch import (
    POSTS_DIR, _build_post_context, _sidecar_has_body, validate_sidecar_identities,
)
from scripts.historical_brief_render import render_historical_brief

EXPECTED = 14


def render(check: bool = True) -> tuple[int, int]:
    paths = sorted(POSTS_DIR.glob("*.json"))
    if len(paths) != EXPECTED:
        raise ValueError("Refusing historical rewrite: expected exactly 14 sidecars, got %d" % len(paths))
    sidecars = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    validate_sidecar_identities(sidecars)
    for path, edition in zip(paths, sidecars):
        if not edition.get("date") or path.stem != edition["date"]:
            raise ValueError("Historical sidecar filename/date mismatch: %s" % path.name)
        if not _sidecar_has_body(edition):
            raise ValueError("Historical edition has no body text: %s" % path.name)
        resolve_identity(edition)

    changes = 0
    for i, edition in enumerate(sidecars):
        context = _build_post_context(edition)
        context["prev_post"] = sidecars[i - 1] if i else None
        context["next_post"] = sidecars[i + 1] if i + 1 < len(sidecars) else None
        content = render_historical_brief(context)
        if 'Indo-Pacific Record Briefs' not in content:
            raise ValueError("Historic publication identity missing from %s" % edition["date"])
        if 'data-surface="brief"' not in content:
            raise ValueError("Historic Brief lost new surface-scoped presentation")
        if 'href="../../enrichment.css"' not in content:
            raise ValueError("Missing correctly rooted historical enhancement asset")
        if 'href="../../briefs.css"' not in content:
            raise ValueError("Missing historical Brief reader stylesheet")
        if "historical-provenance" not in content or "historical-source-list" not in content:
            raise ValueError("Historic issue provenance/source trail missing")
        target = POSTS_DIR / (edition["date"] + ".html")
        existing = target.read_text(encoding="utf-8") if target.exists() else None
        if existing != content:
            changes += 1
            if not check:
                target.write_text(content, encoding="utf-8")
            print("%s %s" % ("STALE" if check else "UPDATED", target.relative_to(ROOT)))
    if check and changes:
        raise ValueError("%d historical HTML file(s) differ from canonical renderer" % changes)
    print("Historic articles verified: %d; regenerated differences: %d; write=%s"
          % (len(sidecars), changes, not check))
    return len(sidecars), changes


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--write", action="store_true",
                   help="Regenerate only historical HTML in a controlled local branch")
    args = p.parse_args()
    try:
        render(check=not args.write)
    except (ValueError, OSError) as exc:
        print("HISTORICAL-RENDER-HOLD: %s" % exc, file=sys.stderr)
        raise SystemExit(1)
