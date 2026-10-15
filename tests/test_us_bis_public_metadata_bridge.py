"""BIS U.S. Desk HTML bridge: typed scheduled metadata only, never corpus."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from bs4 import BeautifulSoup
from jinja2 import Environment, StrictUndefined
from core.us_bis_authenticated_metadata import admit_attested, load_public_links
from tests.test_us_bis_authenticated_metadata import packet, proof

ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=ROOT/"site/preview/templates/desk.html"
GENERATOR=ROOT/"site/preview/generate_preview.py"

def fragment():
    full=TEMPLATE.read_text(encoding="utf-8")
    start=full.index("{# Commerce/BIS links:")
    end=full.index("{# A permanent publication is IPR-authored analysis",start)
    return Environment(autoescape=True,undefined=StrictUndefined).from_string(
        full[start:end])

def render(rows, slug="us-indopacific"):
    return fragment().render(
        desk=SimpleNamespace(slug=slug), us_bis_authenticated_links=rows)

class BISDeskBridge(unittest.TestCase):
    def test_missing_table_returns_no_live_rows_and_empty_bis_section(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/"empty.sqlite"
            with sqlite3.connect(db) as con:
                con.execute("CREATE TABLE unrelated (k INTEGER)")
            links=load_public_links(db)
            self.assertEqual(links,[])
            self.assertEqual(render(links).strip(),"")

    def test_staged_attested_rows_are_rendered_in_neutral_link_only_section(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/"synthetic.sqlite"
            with sqlite3.connect(db) as con:
                admit_attested(con,packet(),proof())
            rows=load_public_links(db)
            soup=BeautifulSoup(render(rows),"html.parser")
            links=soup.select("li[data-us-bis-official-link] a[href]")
            self.assertEqual(len(rows),len(links))
            self.assertEqual(len(links),2)
            self.assertEqual([a.get("href") for a in links],
                             [r["source_url"] for r in rows])
            for anchor in links:
                self.assertTrue(anchor["href"].startswith(
                    "https://www.bis.gov/press-release/"))
                self.assertEqual(anchor.get("target"),"_blank")
                self.assertIn("noopener",anchor.get("rel",[]))
                self.assertIn("noreferrer",anchor.get("rel",[]))
                self.assertIn("official press reference",anchor.get_text())
            self.assertEqual(
                [x["datetime"] for x in soup.select("li[data-us-bis-official-link] time")],
                [r["published_date"] for r in rows])
            content=str(soup)
            self.assertIn("separately dated BIS homepage",content)
            self.assertIn("not the agency's full publication history",content)
            self.assertIn("does not add article records",content)
            self.assertIn("PACOM remains access-blocked",content)
            self.assertNotIn("title_original",content)
            self.assertNotIn("text_original",content)

    def test_no_bis_section_on_other_desks_or_when_rows_absent(self):
        rows=[{"source_identity":"us-bis-homepage-press:synthetic",
               "source_url":"https://www.bis.gov/press-release/synthetic",
               "neutral_label":"BIS official press reference · 2026-10-15",
               "published_date":"2026-10-15"}]
        self.assertEqual(render(rows,slug="china").strip(),"")
        self.assertEqual(render(rows,slug="singapore").strip(),"")
        self.assertEqual(render([],slug="us-indopacific").strip(),"")

    def test_generator_queries_typed_attested_table_only_for_us_desk(self):
        code=GENERATOR.read_text(encoding="utf-8")
        self.assertIn("from core.us_bis_authenticated_metadata import load_public_links as load_bis_live_links",code)
        self.assertIn("bis_links = (load_bis_live_links(db_path)",code)
        self.assertIn('if desk.slug == "us-indopacific" else [])',code)
        self.assertIn("us_bis_authenticated_links=bis_links",code)
        self.assertNotIn("load_staged_links(db_path)",code)
        self.assertNotIn("shadow/us-bis-homepage",code)

    def test_existing_us_sources_and_context_survive_conditionally(self):
        source=TEMPLATE.read_text(encoding="utf-8")
        for key in ("data-us-pacom-link=","data-uscc-official-link=",
                    "data-us-treasury-official-link=",
                    "data-us-bis-official-link="):
            self.assertIn(key,source)
        self.assertIn("Official USCC, Treasury and BIS link metadata feeds live",source)
        self.assertIn("Direct PACOM collection remains access-blocked",source)
        self.assertIn("DVIDS paused",source)
        self.assertIn("No U.S. production",source)
        self.assertNotIn("BIS original article bodies live",source)

    def test_template_escapes_untrusted_fields_even_when_called_directly(self):
        rows=[{"source_identity":'evil"><img src=x onerror=alert(1)>',
               "source_url":'https://www.bis.gov/press-release/foo',
               "neutral_label":'<script>hello</script>',
               "published_date":"2026-10-15"}]
        output=render(rows)
        self.assertNotIn("<script>hello</script>",output)
        self.assertNotIn('data-us-bis-official-link="evil"><img',output)
        self.assertIn("&lt;script&gt;hello&lt;/script&gt;",output)

if __name__=="__main__":
    unittest.main()
