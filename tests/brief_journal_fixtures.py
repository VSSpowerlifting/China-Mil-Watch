"""Private future-layout fixtures built with the real Brief renderer.

Nothing here supplies publication authority. Four explicit synthetic records use
reserved test numbers. The source-linked variant copies the exact existing Laos
manuscript as an unnumbered draft, with a simulated presentation receipt. Its
admission is mocked only inside this helper; production cannot publish it.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest import mock

from core import brief_collection as bc, brief_cover as bcv
from core.brief_contract import validate_brief
from core.brief_photography import article_cover
from core.brief_presentation import CHECKS, presentation_fingerprint, validate_presentation
from core.brief_source_linked import fingerprint
from core.desk_registry import load_registry
from tests import brief_fixtures

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site/preview"))
import generate_preview as gp

SOURCE_SLUG = "fixture-journal-source-linked"
PHOTO_SLUG = "fixture-journal-photograph"
VARIANTS = {
    PHOTO_SLUG: "Synthetic normal-length Brief with a scratch-only granted photograph",
    "fixture-journal-no-photograph": "Synthetic Brief with the real editorial-plate fallback",
    "fixture-journal-long-cross-desk": "Synthetic long English title and long cross-desk body",
    "fixture-journal-short": "Synthetic short body without optional term, signal or contributor",
    SOURCE_SLUG: "Unnumbered draft copied from the exact approved Laos manuscript with simulated reviewed presentation",
}


def fixture_records():
    base = json.loads((brief_fixtures.FIXTURE_DIR /
                       (brief_fixtures.FIXTURE_SLUG + ".json")).read_text())
    result = {}
    for number, slug in enumerate(list(VARIANTS)[:4], 9001):
        value = copy.deepcopy(base)
        value.update(issue_number=number,
                     title="Synthetic journal fixture: " + slug[len("fixture-journal-"):])
        value["fixture_note"] = VARIANTS[slug] + ". Private test-only; never publication authority."
        if slug.endswith("long-cross-desk"):
            value["title"] = ("Synthetic journal fixture: a deliberately long English heading across two desks "
                              "for testing the inherited article layout and navigation on narrow screens")
            value["what_stood_out"] = "\n\n".join([base["what_stood_out"]] * 12)
            value["cross_desk_claims"][0]["claim"] = "\n\n".join([base["cross_desk_claims"][0]["claim"]] * 6)
        if slug.endswith("short"):
            for field in ("term_to_know_term", "term_to_know_lang", "term_to_know_explanation", "signal"):
                value.pop(field, None)
            for field in ("opening_note", "what_stood_out", "why_it_matters", "what_was_routine", "what_im_watching_next"):
                value[field] = "Synthetic fixture paragraph."
        result[slug] = value
    article = json.loads((ROOT / "briefs/what-is-being-built-in-laos.json").read_text())
    article.update(editorial_status="draft", issue_number=None)
    for field in ("approval", "editorial_review", "policy_ruling"):
        article.pop(field, None)
    result[SOURCE_SLUG] = article
    return result


def reviewed_presentation(article):
    manifest = json.loads((ROOT / "briefs/presentation/what-is-being-built-in-laos.json").read_text())
    manifest.update(article=SOURCE_SLUG, manuscript_fingerprint=fingerprint(article), status="approved")
    manifest["sections"][0]["heading"] = "Synthetic fixture navigation heading for the unchanged approved manuscript introduction"
    manifest["approval"] = {
        "reviewed_by": "Fixture reviewer (simulated only)", "reviewed_on": "2026-10-14",
        "reference": "Private test receipt; no manuscript publication or real presentation approval",
        "checks": {check: True for check in CHECKS}, "fingerprint": "",
    }
    manifest["approval"]["fingerprint"] = presentation_fingerprint(manifest)
    return manifest


def stage_cover(scratch):
    """Copy real admitted pixels/credits; retarget only a scratch manifest."""
    entry = copy.deepcopy(next(e for e in bcv.load_manifest(ROOT)
                               if (e.get("match") or {}).get("briefs") == ["what-is-being-built-in-laos"]))
    entry["surfaces"] = ["article"]
    entry["match"] = {"briefs": [PHOTO_SLUG]}
    media = Path(scratch) / bcv.EDITORIAL_ROOT
    for rel in [entry["file"]] + [d["file"] for d in entry["derivatives"]]:
        target = media / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / bcv.EDITORIAL_ROOT / rel, target)
    return entry


def build_private_fixtures(out_dir):
    """Export five noindex pages/assets; return a route -> variation mapping.

    Destination must be new and outside the repository and its parent directories. The whole
    site is built to keep shell, CSS, fonts, links and image copying realistic.
    Mocked admissions are scoped to this call and never affect production code.
    """
    out = Path(out_dir).resolve()
    if out.exists() or out == ROOT or ROOT in out.parents or out in ROOT.parents:
        raise ValueError("fixture export requires a new private destination outside the repository")
    records = fixture_records()
    registry = load_registry()
    for article in records.values():
        errors = validate_brief(article, registry)
        if errors:
            raise ValueError("invalid layout fixture: " + "; ".join(errors))
    manifest = reviewed_presentation(records[SOURCE_SLUG])
    errors = validate_presentation(manifest, records[SOURCE_SLUG], slug=SOURCE_SLUG)
    if errors:
        raise ValueError("invalid presentation fixture: " + "; ".join(errors))
    real_load = gp.load_collection
    with tempfile.TemporaryDirectory(prefix="ipr-journal-input-") as directory:
        scratch = Path(directory)
        briefs = scratch / "briefs"
        (briefs / "presentation").mkdir(parents=True)
        for slug, article in records.items():
            (briefs / (slug + ".json")).write_text(json.dumps(article), encoding="utf-8")
        (briefs / "presentation" / (SOURCE_SLUG + ".json")).write_text(json.dumps(manifest), encoding="utf-8")
        cover_entry = stage_cover(scratch)

        def private_collection(*args, **kwargs):
            collection = real_load(*args, **kwargs)
            # The real loader correctly withholds this draft. Admit it only to
            # the private rendering test; keep its draft/unnumbered status.
            article = records[SOURCE_SLUG]
            entry = bc.brief_entry(SOURCE_SLUG, article)
            rows = bc.order_rows(list(collection.rows) + [{"entry": entry, "kind": "brief", "provenance": bc.provenance(entry)}])
            return bc.Collection(rows=tuple(rows), briefs=collection.briefs + (entry,),
                                withheld=collection.withheld,
                                sidecars=dict(collection.sidecars, **{SOURCE_SLUG: article}))

        def private_cover(entry, repo_root, **kwargs):
            if entry["slug"] in VARIANTS:
                return article_cover(entry, scratch, manifest=[cover_entry])
            return article_cover(entry, repo_root, **kwargs)

        with mock.patch.object(gp, "load_collection", side_effect=private_collection), \
                mock.patch.object(gp, "article_cover", side_effect=private_cover):
            gp.build(out, gp.PUBLIC_TITLE, ROOT / "pla_watch.db",
                     snapshot=gp.snapshot_from_corpus(ROOT / "pla_watch.db"),
                     briefs_dir=briefs, allow_synthetic_briefs=True)
    return {bc.brief_route(slug): description for slug, description in VARIANTS.items()}
