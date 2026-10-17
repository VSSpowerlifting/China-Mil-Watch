"""Editorial team visibility and production-template contracts."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.staff_directory import credited_works, load_staff

ROOT = Path(__file__).resolve().parents[1]
ROSTER = ROOT / "site/preview/staff.json"
TEMPLATES = ROOT / "site/preview/templates"


def _ctx(**kw):
    values = dict(
        title="Indo-Pacific Record",
        tagline="Official-source research",
        mode="indo-pacific-record",
        page="team.html",
        team=load_staff(ROSTER),
        maintainer={"name": "Benjamin Yang", "email": "contact@example.org"},
        collection_name="Indo-Pacific Record Briefs",
        live_base="https://indopacificrecord.org",
        review_mode=False,
        run_status=None,
        desks=[],
        timelines=[],
    )
    values.update(kw)
    return values


def _template(name, **ctx):
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                      autoescape=select_autoescape(["html"]))
    env.filters["reader_date"] = lambda date: date
    return env.get_template(name).render(**ctx)


def test_public_roster_is_exact_and_domain_focused():
    people = load_staff(ROSTER)
    assert [(p["name"], p["role"]) for p in people] == [
        ("Benjamin Yang", "Founder & Editor-in-Chief"),
        ("Dylan Tanzi", "Lead Research Analyst"),
        ("Christin Sawyer", "Communications Editor"),
    ]
    for person in people:
        assert person["route"] == "authors/" + person["slug"] + ".html"
        assert not any(word in person["bio"].lower() for word in
                       ("manhasset", "aylus", "powerlifting", "oboe"))
    assert "Euna" not in ROSTER.read_text(encoding="utf-8")
    dylan = next(p for p in people if p["slug"] == "dylan-tanzi")
    assert dylan["links"]["LinkedIn"] == "https://www.linkedin.com/in/dylan-tanzi/"
    assert "Vietnam Research Desk" in dylan["bio"]
    founder = next(p for p in people if p["slug"] == "benjamin-yang")
    assert founder["links"]["LinkedIn"] == "https://www.linkedin.com/in/benjamin-w-yang/"
    assert "Strategic Materials Policy Tracker" in founder["bio"]
    assert "The Diplomat" in founder["bio"]
    christin = next(p for p in people if p["slug"] == "christin-sawyer")
    assert christin["links"]["LinkedIn"] == "https://www.linkedin.com/in/christin-sawyer-b4b499339/"
    assert "International Affairs" in christin["bio"]
    assert "International Business" not in christin["bio"]
    assert "Korean and English" in christin["bio"]


@pytest.mark.parametrize("bad", [
    [{"slug": "../escape", "name": "A", "role": "Editor", "bio": "Research", "links": {}}],
    [{"slug": "valid", "name": "A", "role": "Editor", "bio": "Research", "links": {"Website": "javascript:alert(1)"}}],
    [{"slug": "same", "name": "A", "role": "Editor", "bio": "Research", "links": {}},
     {"slug": "same", "name": "B", "role": "Editor", "bio": "Research", "links": {}}],
])
def test_invalid_roster_fails_closed(tmp_path, bad):
    source = tmp_path / "staff.json"
    source.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        load_staff(source)


def test_author_and_research_credits_are_not_conflated():
    briefs = [
        {"slug": "published", "author_names": ["Benjamin Yang"], "date": "2026-10-01", "title": "Published", "url": "briefs/published.html"},
        {"slug": "joint", "author_names": ["Benjamin Yang", "Dylan Tanzi"], "date": "2026-10-02", "title": "Joint", "url": "briefs/joint.html"},
        {"slug": "researched", "author_names": ["Benjamin Yang"], "date": "2026-10-03", "title": "Researched", "url": "briefs/researched.html"},
        {"slug": "draft", "author_names": ["Christin Sawyer"], "is_review": True, "url": "briefs/draft.html"},
        {"slug": "synthetic", "author_names": ["Christin Sawyer"], "synthetic": True, "url": "briefs/synthetic.html"},
    ]
    c = SimpleNamespace(briefs=briefs, sidecars={
        "researched": {"research_contributor": {"name": "Dylan Tanzi", "title": "Research analyst"}},
        "published": {"research_contributor": {"name": "Christin Sawyer", "title": "Communications"}},
    })
    b = credited_works(c, "Benjamin Yang")
    assert [p["slug"] for p in b["authored"]] == ["published", "joint", "researched"]
    d = credited_works(c, "Dylan Tanzi")
    assert [p["slug"] for p in d["authored"]] == ["joint"]
    assert [p["slug"] for p in d["contributed"]] == ["researched"]
    ch = credited_works(c, "Christin Sawyer")
    assert not ch["authored"]
    assert [p["slug"] for p in ch["contributed"]] == ["published"]


def test_templates_have_accessible_routes_without_assumed_credentials():
    people = load_staff(ROSTER)
    team = _template("team.html", **_ctx())
    for person in people:
        assert person["name"] in team and person["route"] in team
    assert team.count('href="authors/') == 6
    assert "Manhasset" not in team
    profile = _template("staff_profile.html", **_ctx(
        page="authors/christin-sawyer.html", member=people[2],
        works={"authored": (), "contributed": ()},
        staff_schema=None,
    ))
    assert "Christin Sawyer" in profile and "Communications Editor" in profile
    assert 'href="../team.html"' in profile
    assert 'href="../staff.css"' in profile
    assert "Authored Briefs" not in profile
    assert 'application/ld+json' not in profile


def test_person_schema_only_from_explicit_metadata():
    member = load_staff(ROSTER)[0]
    schema = {"@context": "https://schema.org", "@type": "Person", "name": member["name"]}
    page = _template("staff_profile.html", **_ctx(
        page=member["route"], member=member,
        works={"authored": (), "contributed": ()},
        staff_schema=schema,
    ))
    assert 'application/ld+json' in page
    assert '"name": "Benjamin Yang"' in page
    assert "LinkedIn" in page
