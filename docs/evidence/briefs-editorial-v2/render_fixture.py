"""Reproduce the isolated excerpt component; never a publication renderer."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from jinja2 import Environment, FileSystemLoader, select_autoescape
from bs4 import BeautifulSoup
from markupsafe import Markup
from core.brief_collection import brief_view
from core.brief_presentation import presentation_view, validate_presentation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--style-base", default="/review", help="URL prefix of a private preview served locally")
    args = parser.parse_args()
    out = args.out.resolve()
    if out == ROOT or ROOT in out.parents or out in ROOT.parents:
        parser.error("fixture output must be outside the repository")
    slug = "what-is-being-built-in-laos"
    article = json.loads((ROOT / "briefs" / (slug + ".json")).read_text())
    manifest = json.loads((ROOT / "tests/fixtures/brief-presentation/evidence-excerpts.json").read_text())
    errors = validate_presentation(manifest, article, slug=slug)
    if errors:
        parser.error("; ".join(errors))
    view = brief_view(slug, article, desk_names={}, state_labels={}, state_order=[], language_label=str)
    view["presentation"] = presentation_view(manifest, article)
    env = Environment(loader=FileSystemLoader(ROOT / "site/preview/templates"),
                      autoescape=select_autoescape(["html"]))
    rendered = env.get_template("_brief_reading.html").module.reading_article(view)
    content = Markup(str(BeautifulSoup(str(rendered), "html.parser").select_one(".brief-reading-evidence")))
    document = env.from_string('''<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Evidence component design fixture</title>
{% for css in ['fonts.css', 'styles.css', 'surfaces.css', 'briefs.css'] %}
<link rel="stylesheet" href="{{ style_base }}/{{ css }}">{% endfor %}</head><body>
<main class="brief-page"><div class="wrap"><p class="brief-fixture" role="note" style="padding:24px;font:16px/1.7 var(--sans)">
<strong>Component design fixture.</strong> Exact Laos manuscript excerpts; proposed evidence/uncertainty classification.
Unapproved, isolated from the Laos candidate and production.</p>
<article class="brief-main" style="max-width:44rem;margin:48px auto">{{ content }}
<section id="s-publishers"><h2>Fixture publisher references</h2><ul>
{% for reference in references %}<li id="publisher-{{ reference.id }}"><a href="{{ reference.url }}" rel="noopener noreferrer">{{ reference.publisher }}</a> · {{ reference.date }}</li>{% endfor %}
</ul></section></article>
</div></main></body></html>''')
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(document.render(style_base=args.style_base, content=content,
                                                  references=article["publisher_references"]), encoding="utf-8")


if __name__ == "__main__":
    main()
