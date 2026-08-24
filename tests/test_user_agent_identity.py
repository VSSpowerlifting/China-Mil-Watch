"""
The collector's public identity.

Every request this project makes carries a `User-Agent` naming the project and
where to find it. That string is the whole basis of a promise the project makes
in public: an institution that wants to refuse this collector must be able to
recognise it and say so in `robots.txt`, rather than having to guess which
anonymous client to block.

A promise like that fails in three specific ways, and all three were live in
`scraper/base.py` until 2026-08-24:

  * an unreplaced placeholder (`[username]`), so the advertised source URL does
    not resolve — an identity that cannot be looked up is not an identity;
  * an example or documentation host (`example.com`, `localhost`), same fault
    in a different costume;
  * "OSINT", which contradicts the project's own description of itself
    (CLAUDE.md: never "OSINT tool or intelligence cosplay") and which a defense
    ministry may reasonably read as intelligence collection.

These tests refuse all three, for every user agent the project declares — not
only the one that was broken, so a new collector cannot reintroduce the fault
somewhere else.
"""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def declared_user_agents() -> dict:
    """Every user agent the project sends, read from its own module."""
    from scraper.base import _USER_AGENT
    from scraper.sources.sg_mindef import USER_AGENT as SG
    agents = {"scraper/base.py": _USER_AGENT,
              "scraper/sources/sg_mindef.py": SG}
    # The media fetchers import optional dependencies at module scope, so read
    # their constants by parsing the source rather than importing the modules.
    # Parsed, not regexed: these strings contain parentheses of their own, and
    # a regex that stops at the first ")" silently truncates the URL out of the
    # value it is supposed to be checking.
    for rel in ("scripts/fetch_article_image.py",
                "scripts/fetch_pla_watch_media.py"):
        tree = ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8"))
        for node in tree.body:
            if (isinstance(node, ast.Assign)
                    and any(getattr(t, "id", None) == "USER_AGENT"
                            for t in node.targets)):
                agents[rel] = ast.literal_eval(node.value)
    return agents


#: Tokens that mean "nobody filled this in".
PLACEHOLDERS = ("[username]", "<username>", "{username}", "YOUR_", "TODO",
                "FIXME", "xxx", "changeme")

#: Hosts reserved for documentation and testing. A user agent pointing at one
#: of these advertises an address that cannot be reached.
NON_RESOLVING = ("example.com", "example.org", "example.net", "example.invalid",
                 "localhost", "127.0.0.1", "yourdomain", "yoursite")


class TestEveryDeclaredUserAgentIsHonest(unittest.TestCase):

    def setUp(self):
        self.agents = declared_user_agents()
        self.assertTrue(self.agents, "no user agent was found to check")

    def test_no_placeholder_survives_into_a_request(self):
        for where, agent in self.agents.items():
            for token in PLACEHOLDERS:
                with self.subTest(where=where, token=token):
                    self.assertNotIn(token.lower(), agent.lower())

    def test_no_unresolvable_or_example_source_is_advertised(self):
        for where, agent in self.agents.items():
            for host in NON_RESOLVING:
                with self.subTest(where=where, host=host):
                    self.assertNotIn(host, agent.lower())

    def test_no_osint_language(self):
        """CLAUDE.md: never "OSINT tool" or intelligence cosplay. That rule
        governs what the project calls itself to a ministry, not only what it
        prints on a page."""
        for where, agent in self.agents.items():
            with self.subTest(where=where):
                self.assertNotIn("osint", agent.lower())

    def test_each_agent_names_a_reachable_project_url(self):
        for where, agent in self.agents.items():
            with self.subTest(where=where):
                urls = re.findall(r'https?://[^\s;)]+', agent)
                self.assertTrue(urls, "no URL to identify the project by")
                for url in urls:
                    self.assertRegex(url, r'^https://',
                                     "identity URL must be https")

    def test_each_agent_names_the_project_and_a_version(self):
        for where, agent in self.agents.items():
            with self.subTest(where=where):
                self.assertRegex(agent, r'^[A-Za-z][A-Za-z0-9-]*/\d+\.\d+ ')

    def test_no_personal_email_is_exposed(self):
        for where, agent in self.agents.items():
            with self.subTest(where=where):
                self.assertNotRegex(agent, r'[\w.+-]+@[\w-]+\.[\w.]+')


class TestTheCollectorAgentIsTheAgreedString(unittest.TestCase):
    """
    The default collector agent is quoted verbatim in correspondence asking
    institutions for access, so it is pinned rather than merely constrained. If
    it changes, the change should be deliberate and the correspondence updated
    with it.
    """

    AGREED = ("ChinaMilWatch/1.0 (non-commercial research; "
              "project: https://github.com/VSSpowerlifting/"
              "China-Mil-Watch)")

    def test_the_default_agent_matches_the_agreed_identity(self):
        from scraper.base import _USER_AGENT
        self.assertEqual(_USER_AGENT, self.AGREED)

    def test_it_does_not_advertise_a_contact_route(self):
        """
        The URL identifies the project; it is not a reply address. Labelling it
        `contact:` would promise a mechanism the project does not operate, which
        is the same class of fault as the placeholder that preceded it — an
        identity making a claim that does not hold up when someone acts on it.
        Correspondence carries a real reply address separately.
        """
        from scraper.base import _USER_AGENT
        self.assertIn("project:", _USER_AGENT)
        self.assertNotIn("contact", _USER_AGENT.lower())

    def test_it_is_what_the_session_actually_sends(self):
        """Pinning the constant is worth nothing if the header is built from
        something else."""
        import scraper.base as base
        source = Path(base.__file__).read_text(encoding="utf-8")
        self.assertIn('"User-Agent": _USER_AGENT', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
