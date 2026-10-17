"""Editorial team visibility and production-template contracts."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import tempfile
import unittest
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


class EditorialStaffTests(unittest.TestCase):

    def test_public_roster_is_exact_and_domain_focused(self):
        people = load_staff(ROSTER)
        self.assertEqual([(p["name"], p["role"]) for p in people], [
            ("Benjamin Yang", "Founder & Director of Research and Editorial"),
            ("Dylan Tanzi", "Lead Research Analyst"),
            ("Christin Sawyer", "Communications Editor"),
        ])
        for person in people:
            self.assertEqual(person["route"], "authors/" + person["slug"] + ".html")
            self.assertFalse(any(word in person["bio"].lower() for word in
                           ("manhasset", "aylus", "powerlifting", "oboe")))
        self.assertNotIn("Euna", ROSTER.read_text(encoding="utf-8"))
        dylan = next(p for p in people if p["slug"] == "dylan-tanzi")
        self.assertEqual(dylan["links"]["LinkedIn"], "https://www.linkedin.com/in/dylan-tanzi/")
        self.assertIn("Vietnam Research Desk", dylan["bio"])
        founder = next(p for p in people if p["slug"] == "benjamin-yang")
        self.assertEqual(founder["links"]["LinkedIn"], "https://www.linkedin.com/in/benjamin-w-yang/")
        self.assertIn("Indo-Pacific Record", founder["bio"])
        self.assertIn("primary-source evidence", founder["bio"])
        self.assertIn("Director of Research and Editorial", founder["bio"])
        self.assertNotIn("Editor-in-Chief", founder["bio"])
        self.assertNotIn("Strategic Materials Policy Tracker", founder["bio"])
        self.assertNotIn("The Diplomat", founder["bio"])
        self.assertNotIn("The Globe", founder["bio"])
        christin = next(p for p in people if p["slug"] == "christin-sawyer")
        self.assertEqual(christin["links"]["LinkedIn"], "https://www.linkedin.com/in/christin-sawyer-b4b499339/")
        self.assertIn("International Affairs", christin["bio"])
        self.assertNotIn("International Business", christin["bio"])
        self.assertIn("Korean and English", christin["bio"])

    def test_invalid_roster_fails_closed(self):
        cases = [
        [{"slug": "../escape", "name": "A", "role": "Editor", "bio": "Research", "links": {}}],
        [{"slug": "valid", "name": "A", "role": "Editor", "bio": "Research", "links": {"Website": "javascript:alert(1)"}}],
        [{"slug": "same", "name": "A", "role": "Editor", "bio": "Research", "links": {}},
         {"slug": "same", "name": "B", "role": "Editor", "bio": "Research", "links": {}}],
    ]
        for bad in cases:
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / "staff.json"
                source.write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_staff(source)

    def test_author_and_research_credits_are_not_conflated(self):
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
        self.assertEqual([p["slug"] for p in b["authored"]], ["published", "joint", "researched"])
        d = credited_works(c, "Dylan Tanzi")
        self.assertEqual([p["slug"] for p in d["authored"]], ["joint"])
        self.assertEqual([p["slug"] for p in d["contributed"]], ["researched"])
        ch = credited_works(c, "Christin Sawyer")
        self.assertFalse(ch["authored"])
        self.assertEqual([p["slug"] for p in ch["contributed"]], ["published"])

    def test_templates_have_accessible_routes_without_assumed_credentials(self):
        people = load_staff(ROSTER)
        team = _template("team.html", **_ctx())
        for person in people:
            self.assertTrue(person["name"] in team and person["route"] in team)
        self.assertEqual(team.count('href="authors/'), 6)
        self.assertNotIn("Manhasset", team)
        profile = _template("staff_profile.html", **_ctx(
            page="authors/christin-sawyer.html", member=people[2],
            works={"authored": (), "contributed": ()},
            staff_schema=None,
        ))
        self.assertTrue("Christin Sawyer" in profile and "Communications Editor" in profile)
        self.assertIn('href="../team.html"', profile)
        self.assertIn('href="../staff.css"', profile)
        self.assertNotIn("Authored Briefs", profile)
        self.assertNotIn('application/ld+json', profile)

    def test_person_schema_only_from_explicit_metadata(self):
        member = load_staff(ROSTER)[0]
        schema = {"@context": "https://schema.org", "@type": "Person", "name": member["name"]}
        page = _template("staff_profile.html", **_ctx(
            page=member["route"], member=member,
            works={"authored": (), "contributed": ()},
            staff_schema=schema,
        ))
        self.assertIn('application/ld+json', page)
        self.assertIn('"name": "Benjamin Yang"', page)
        self.assertIn("LinkedIn", page)


class StaffBuildTests(unittest.TestCase):
    """Use the production builder and real published credit registry."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'staff_build', ROOT / 'site/preview/generate_preview.py')
        cls.gp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.gp)
        cls.tmp = tempfile.TemporaryDirectory(prefix='ipr-staff-')
        cls.out = Path(cls.tmp.name) / 'site'
        cls.gp.build(cls.out, 'Indo-Pacific Record', ROOT / 'pla_watch.db',
                     snapshot=cls.gp.snapshot_from_corpus(ROOT / 'pla_watch.db'),
                     site_origin='https://indopacificrecord.org')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_public_profiles_metadata_and_exact_approved_roster(self):
        from bs4 import BeautifulSoup
        from xml.etree import ElementTree
        sitemap = ElementTree.parse(self.out / 'sitemap.xml')
        locations = {el.text for el in sitemap.findall('.//{*}loc')}
        for member in load_staff(ROSTER):
            with self.subTest(member=member['slug']):
                url = 'https://indopacificrecord.org/' + member['route']
                soup = BeautifulSoup((self.out / member['route']).read_text(), 'html.parser')
                self.assertEqual(soup.title.get_text(), member['name'] + ' — Indo-Pacific Record')
                self.assertEqual(len(soup.select('link[rel=canonical]')), 1)
                self.assertEqual(soup.select_one('link[rel=canonical]')['href'], url)
                self.assertIn(url, locations)
                self.assertEqual(soup.h1.get_text(), member['name'])
                self.assertEqual(soup.select_one('.staff-person-role').get_text(), member['role'])
                self.assertEqual(soup.select_one('.prose>p').get_text(), member['bio'])
                self.assertEqual(soup.html['data-surface'], 'utility')
                schema = json.loads(soup.select_one('script[type="application/ld+json"]').string)
                self.assertEqual(schema, {
                    '@context': 'https://schema.org', '@type': 'Person',
                    'name': member['name'], 'url': url, 'jobTitle': member['role'],
                    'worksFor': {'@type': 'Organization', 'name': 'Indo-Pacific Record',
                                 'url': 'https://indopacificrecord.org/'},
                    'sameAs': list(member['links'].values()),
                })
                for link in soup.select('a[href^="../"]'):
                    from urllib.parse import urlsplit, unquote
                    target = (self.out / 'authors' / unquote(urlsplit(link['href']).path)).resolve()
                    self.assertTrue(target.is_file(), link['href'])
        team = BeautifulSoup((self.out / 'team.html').read_text(), 'html.parser')
        self.assertEqual(team.title.get_text(), 'Editorial Team — Indo-Pacific Record')
        self.assertIn('https://indopacificrecord.org/team.html', locations)
        self.assertEqual(team.select_one('link[rel=canonical]')['href'],
                         'https://indopacificrecord.org/team.html')

    def test_real_publication_credits_and_reverse_links(self):
        from bs4 import BeautifulSoup
        collection = self.gp.load_collection(self.gp.load_editions(ROOT), self.gp.load_registry(), briefs_dir=ROOT / "briefs")
        for member in load_staff(ROSTER):
            with self.subTest(member=member['slug']):
                expected = credited_works(collection, member['name'])
                soup = BeautifulSoup((self.out / member['route']).read_text(), 'html.parser')
                for group, heading in [('authored', '#staff-authored'), ('contributed', '#staff-contributed')]:
                    section = soup.select_one(heading)
                    actual = [a['href'] for a in section.parent.select('.staff-work-list a')] if section else []
                    self.assertEqual(actual, ['../' + work['url'] for work in expected[group]])
                    for work in expected[group]:
                        self.assertFalse(work.get('synthetic') or work.get('is_review'))
                        self.assertTrue((self.out / work['url']).is_file())
        ben = (self.out / 'authors/benjamin-yang.html').read_text()
        dylan = (self.out / 'authors/dylan-tanzi.html').read_text()
        christin = (self.out / 'authors/christin-sawyer.html').read_text()
        self.assertIn('what-is-being-built-in-laos.html', ben)
        self.assertIn('what-is-being-built-in-laos.html', dylan)
        self.assertNotIn('class="staff-work-list"', christin)
        laos = BeautifulSoup((self.out / 'briefs/what-is-being-built-in-laos.html').read_text(), 'html.parser')
        self.assertEqual(laos.select_one('.brief-byline a')['href'], '../authors/benjamin-yang.html')
        contributor = laos.select('[aria-label="Co-author"]')[1]
        self.assertEqual(contributor.select_one('.brief-author-name a')['href'], '../authors/dylan-tanzi.html')
        self.assertIn('Lead Research Analyst', contributor.get_text())
        self.assertEqual(laos.select_one('.brief-byline').get_text(), 'By Benjamin Yang and Dylan Tanzi')
        self.assertEqual([a['href'] for a in laos.select('.brief-byline a')],
                         ['../authors/benjamin-yang.html', '../authors/dylan-tanzi.html'])

    def test_private_build_keeps_profiles_unindexed_and_excludes_person_schema(self):
        from bs4 import BeautifulSoup
        private = Path(self.tmp.name) / 'private'
        self.gp.build(private, 'Indo-Pacific Record', ROOT / 'pla_watch.db',
                     snapshot=self.gp.snapshot_from_corpus(ROOT / 'pla_watch.db'))
        self.assertFalse((private / 'sitemap.xml').exists())
        for route in ['team.html'] + [p['route'] for p in load_staff(ROSTER)]:
            soup = BeautifulSoup((private / route).read_text(), 'html.parser')
            self.assertEqual(soup.select_one('meta[name=robots]')['content'], 'noindex, nofollow')
            self.assertFalse(soup.select('link[rel=canonical]'))
            self.assertFalse(soup.select('script[type="application/ld+json"]'))
