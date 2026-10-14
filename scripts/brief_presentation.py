#!/usr/bin/env python3
"""Prepare, check and privately preview explicitly selected Brief sections.

Never generates headings, edits a manuscript or records human approval.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.brief_contract import validate_brief, validate_readiness
from core.brief_presentation import (DIRECTORY, VERSION, load_presentation,
                                     presentation_fingerprint, presentation_view, validate_presentation)
from core.brief_source_linked import fingerprint, is_source_linked
from core.desk_registry import load_registry


def scaffold(article, slug, sections):
    """An explicit outline only: no paragraph-count heuristic or sign-off."""
    return {"version": VERSION, "article": slug, "manuscript_fingerprint": fingerprint(article),
            "status": "draft", "sections": sections, "approval": None}


def section_arg(value):
    try:
        ident, start, end, heading = value.split("|", 3)
        return {"id": ident, "start": int(start), "end": int(end), "heading": heading}
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use id|first-paragraph|last-paragraph|heading") from exc


def check_media(manifest, article, slug, root=ROOT):
    """Reuse the same article + paired catalogue admission gate as rendering."""
    if not manifest.get("figures"):
        return
    from core.brief_collection import brief_entry
    from core.brief_photography import article_cover
    from core.catalogue_media import load_admissions
    from core.article_media import native_article_media
    cover = article_cover(brief_entry(slug, article), root,
                          admissions=load_admissions(repo_root=root))
    media = native_article_media(None, article["desks"], root="../", cover=cover)
    presentation_view(manifest, article, media=media)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("scaffold")
    create.add_argument("article", type=Path)
    create.add_argument("--section", action="append", type=section_arg, required=True)
    for name in ("check", "digest", "preview"):
        command = commands.add_parser(name)
        command.add_argument("manifest", type=Path)
        if name == "check":
            command.add_argument("--release", action="store_true")
        if name == "preview":
            command.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "scaffold":
            source = args.article.resolve()
            if source.parent != (ROOT / "briefs").resolve() or source.suffix != ".json":
                raise ValueError("use canonical briefs/<slug>.json")
            slug = source.stem
            manifest_path = ROOT / DIRECTORY / (slug + ".json")
        else:
            manifest_path = args.manifest.resolve()
            if manifest_path.parent != (ROOT / DIRECTORY).resolve() or manifest_path.suffix != ".json":
                raise ValueError("use canonical briefs/presentation/<slug>.json")
            slug = manifest_path.stem
            source = ROOT / "briefs" / (slug + ".json")
        article = json.loads(source.read_text(encoding="utf-8"))
        if not is_source_linked(article):
            raise ValueError("native Briefs already use the standing article anatomy")
        errors = validate_brief(article, load_registry())
        if errors:
            raise ValueError("manuscript contract: " + "; ".join(errors))
        if args.command == "scaffold":
            manifest = scaffold(article, slug, args.section)
            errors = validate_presentation(manifest, article, slug=slug)
            if errors:
                raise ValueError("presentation: " + "; ".join(errors))
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            with manifest_path.open("x", encoding="utf-8") as stream:
                json.dump(manifest, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            print(manifest_path)
            return 0
        manifest = load_presentation(manifest_path, article, slug=slug, review=True)
        check_media(manifest, article, slug)
        if args.command == "digest":
            print(presentation_fingerprint(manifest))
        elif args.command == "check":
            if args.release:
                errors = validate_readiness(article, load_registry())
                if manifest["status"] != "approved":
                    errors.append("presentation awaits independent owner approval")
                if errors:
                    raise ValueError("release: " + "; ".join(errors))
            print("Valid structure; %s presentation%s." % (
                manifest["status"], " (private preview only)" if manifest["status"] == "draft" else ""))
        else:
            spec = importlib.util.spec_from_file_location("ipr_render", ROOT / "site/render.py")
            renderer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(renderer)
            renderer.render_site(output_dir=args.out, review_presentation=manifest_path)
            print(args.out.resolve() / "briefs" / (slug + ".html"))
        return 0
    except (ValueError, OSError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
