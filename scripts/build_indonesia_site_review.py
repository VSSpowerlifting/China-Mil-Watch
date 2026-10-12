"""Build a PRIVATE Indonesia page from IPR's ACTUAL desk template.

No renderer path, registry admission, model, publisher fetch, record bodies,
production output/, public origin, sitemap, human signoff or release action.
"""
from __future__ import annotations

import argparse
import calendar
import json
import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site" / "preview"))
import generate_preview as presentation  # noqa: E402

from core.desk_registry import DeskEntry  # noqa: E402
from core.viewmodel import DeskView  # noqa: E402
from scripts.preview_indonesia_reference_pilot import load  # noqa: E402


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def render_private(out_dir: Path, candidate_path=None):
    """Generate one site-equivalent, deliberately unpublished reference page."""
    # Validate precise source pins, four candidates, and *all* zero approvals
    # BEFORE creating the destination; even malicious rights flags fail closed.
    raw = load(candidate_path) if candidate_path is not None else load()
    requested = Path(out_dir).expanduser()
    destination = requested.resolve()
    require(requested.is_absolute() and not requested.exists()
            and not requested.is_symlink() and not requested.parent.is_symlink(),
            "new absolute private output directory required")
    require(destination != ROOT and ROOT not in destination.parents
            and destination not in ROOT.parents, "private preview must be outside repository")
    require(destination.parent.exists() and destination.parent.is_dir(),
            "private output parent directory must exist")
    # This object exists exclusively in RAM. The public desk registry stays
    # unchanged, so this cannot become a declared public desk.
    candidate = DeskEntry(
        slug="indonesia", name="Indonesia Desk", route="indonesia.html",
        scope=("Initial research scope: institutional Berita articles from the "
               "Indonesian Ministry of Defence (Kemhan). No claimed national, "
               "armed-forces-wide, procurement or Siaran Pers coverage."),
        status="shadow",
        status_explanation=("A single Ministry of Defence Berita source is collecting "
                            "into separate, unpublished Git shadow state. "
                            "No records have been admitted to IPR's public corpus."),
        public=False, manifest_path=None, has_production_records=False,
        limits=[
            "Only one institutional news channel is represented.",
            "The source's description of policy and activity is not independent verification.",
            "Four official URLs are release candidates, not independently human-approved citations.",
            "Publisher reuse/rights, Day 7 and owner site-release decisions remain incomplete.",
        ],
    )
    desk = DeskView(entry=candidate)
    env = Environment(
        loader=FileSystemLoader(str(ROOT / "site" / "preview" / "templates")),
        autoescape=True, trim_blocks=True, lstrip_blocks=True,
    )
    env.globals["topography_style"] = presentation.topography_style
    env.filters["count"] = lambda n: "{:,}".format(n) if isinstance(n, int) else n
    env.filters["reader_date"] = presentation.reader_date
    env.filters["language_label"] = presentation.language_label
    env.filters["script_lang"] = presentation.script_lang
    env.filters["weekday"] = presentation.weekday
    env.filters["month_name"] = lambda n: calendar.month_name[n]
    env.filters["status_label"] = lambda value: presentation.STATUS_PROSE.get(value, (value, ""))[0]
    env.filters["status_prose"] = lambda value: presentation.STATUS_PROSE.get(value, ("", value))[1]
    env.filters["source_type_label"] = (
        lambda value: presentation.SOURCE_TYPE_LABELS.get(value, value or "—"))
    # Jinja parses all branches of the shared templates, even though no brief
    # content is rendered in this private isolated page.
    from markupsafe import Markup
    env.filters["brief_prose"] = lambda value: Markup(presentation.linked_prose(value))
    page = env.get_template("desk.html").render(
        page="indonesia.html", desk=desk,
        indonesia_preview=True, indonesia_preview_candidates=raw["candidates"],
        public_source_links=[], public_source_options=[],
        public_reference_languages=[], display_limits=desk.limits,
        title=presentation.PUBLIC_TITLE, tagline=presentation.TAGLINE,
        maintainer=presentation.MAINTAINER,
        mode="private-disconnected-indonesia-reference-review",
        review_mode=True,
        root_path="", desks=[], timelines=[],
        live_base=presentation.LIVE_BASE, collection_name=presentation.COLLECTION_NAME,
        predecessor_series=presentation.PREDECESSOR_SERIES,
        predecessor_name=presentation.PREDECESSOR_NAME,
        run_status=None, desk_weeks={},
    )
    require('<meta name="robots" content="noindex, nofollow">' in page,
            "private page missing noindex")
    require(page.count('lang="id"') == 4 and
            "NOT APPROVED FOR PUBLICATION" in page,
            "missing unapproved original-language reference scope")
    require("text_original" not in page and "body_original" not in page,
            "unexpected source-body exposure")
    require("INDONESIA_PRIVATE_PREVIEW" not in page, "unsafe marker")

    destination.mkdir(mode=0o700)
    (destination / "indonesia.html").write_text(page, encoding="utf-8")
    for css in ("fonts.css", "styles.css", "support.css", "surfaces.css",
                "desk-references.css"):
        shutil.copyfile(ROOT / "site" / "preview" / css, destination / css)
    for name in ("ipr-navy-160.png", "ipr-navy-320.png",
                 "ipr-accent-32.png", "ipr-accent-180.png"):
        src = ROOT / "site" / "assets" / "identity" / "selected-ipr" / name
        require(src.is_file(), "required preview image asset missing: " + name)
        target = destination / "assets" / "identity" / "selected-ipr" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
    # All review flags must remain visibly and mechanically unapproved.
    (destination / "PRIVATE_HOLD_RECEIPT.json").write_text(json.dumps({
        "schema": "ipr-indonesia-site-template-private-proof/1",
        "template": "site/preview/templates/desk.html",
        "source_state_commit": raw["fixed_state_commit"],
        "selected_bibliographic_candidates": len(raw["candidates"]),
        "rendered_original_bodies": False,
        "human_review_approved": False,
        "rights_reuse_approved": False,
        "day7_checkpoint_completed": False,
        "public_release_authorized": False,
        "registry_changed": False,
        "production_changed": False,
        "purpose": "LOCAL_REVIEW_ONLY_NOT_FOR_DEPLOYMENT",
    }, indent=2, sort_keys=True) + "\n")
    return destination / "indonesia.html"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True,
                        help="nonexistent absolute directory outside all repository paths")
    parser.add_argument("--candidates", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        result = render_private(args.out, args.candidates)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"private_page": str(result),
                      "public_release_authorized": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
