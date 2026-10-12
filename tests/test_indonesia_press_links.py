"""Official Kemhan press-release public metadata without press collector/admission."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from core.indonesia_official_index import PublicIndexError, load as load_news
from core.indonesia_press_index import DEFAULT, RELEASES, load, validate


class IndonesiaPressLinks(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(DEFAULT.read_text(encoding="utf-8"))
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-id-press-metadata-")
        self.addCleanup(self.tmp.cleanup)

    def test_exact_two_real_first_party_press_releases(self):
        links = load()
        self.assertEqual(len(links), 2)
        self.assertEqual(self.raw["source_family"], "id_kemhan_press")
        self.assertEqual(self.raw["collection_status"], "press_parser_unregistered_no_shadow_state")
        self.assertEqual(
            [(row["id"], row["source_url"], row["title_original"],
              row["published_date"], row["press_number"]) for row in links],
            list(RELEASES),
        )
        self.assertTrue(all(row["language"] == "id" for row in links))
        self.assertEqual([r["published_date"] for r in links],
                         ["2026-08-23", "2026-03-23"])
        self.assertEqual([r["press_number"] for r in links],
                         ["SP/17/VIII/2026/ROINFOHAN", "SP/10/III/2026/ROINFOHAN"])

    def test_index_is_frozen_fail_closed_on_other_links_and_body_fields(self):
        muts = [
            lambda x: x["references"][0].update(url="https://www.kemhan.go.id.evil.test/2026/08/23/forged.html"),
            lambda x: x["references"][0].update(url="http://www.kemhan.go.id/2026/08/23/forged.html"),
            lambda x: x["references"][0].update(url="https://www.kemhan.go.id/category/siaran-pers"),
            lambda x: x["references"][0].update(url=x["references"][0]["url"]+"?preview=1"),
            lambda x: x["references"][0].update(published_date="2026-08-22"),
            lambda x: x["references"][0].update(press_number="SP/999/II/2026/ROINFOHAN"),
            lambda x: x["references"][0].update(title_original="<script>body</script>"),
            lambda x: x["references"][0].update(text_original="unlicensed copied press body"),
            lambda x: x["references"][0].update(language="en"),
            lambda x: x["references"].append(copy.deepcopy(x["references"][0])),
            lambda x: x.update(collection_status="production_admitted"),
            lambda x: x.update(editorial_status="human_reviewed"),
            lambda x: x.update(category_url="https://fake.example"),
            lambda x: x.update(hidden_public_release_approved=True),
        ]
        for mutate in muts:
            item = copy.deepcopy(self.raw)
            mutate(item)
            with self.subTest(mutate=mutate), self.assertRaises(PublicIndexError):
                validate(item)

    def test_duplicate_json_keys_and_symlink_rejected(self):
        p = Path(self.tmp.name) / "candidate.json"
        p.write_text('{"schema":"first","schema":"duplicate"}', encoding="utf-8")
        with self.assertRaises(PublicIndexError):
            load(p)
        p.write_text(json.dumps(self.raw, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(len(load(p)), 2)
        link = Path(self.tmp.name) / "alias.json"
        link.symlink_to(p)
        with self.assertRaises(PublicIndexError):
            load(link)

    def test_full_actual_site_render_has_press_and_news_distinct(self):
        import sys
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "site" / "preview"))
        import generate_preview as gp
        database = root / "pla_watch.db"
        if not database.exists():
            self.skipTest("repository test database fixture absent")
        out = Path(self.tmp.name) / "site"
        gp.build(out, "Offline Indonesia Press Links Pilot", database,
                 snapshot=gp.snapshot_from_corpus(database))
        page = (out / "indonesia.html").read_text(encoding="utf-8")
        doc = BeautifulSoup(page, "html.parser")
        press = doc.select('ol[aria-label="Two external ministry press release links"] a')
        news = doc.select('ol[aria-label="Four external ministry news links"] a')
        self.assertEqual([a["href"] for a in press],
                         [r["source_url"] for r in load()])
        self.assertEqual([a["href"] for a in news],
                         [r["source_url"] for r in load_news()])
        self.assertTrue(all(a.get("lang") == "id" for a in press))
        self.assertEqual(len(set(a["href"] for a in press+news)), 6)
        self.assertIn("SP/17/VIII/2026/ROINFOHAN", page)
        self.assertIn("SP/10/III/2026/ROINFOHAN", page)
        self.assertIn("press parser is disabled", page)
        self.assertIn("No individual source references have completed", page)
        self.assertIn("Shadow evaluation — no public corpus records", page)
        self.assertNotIn('data-reference-list', page)
        for forbidden in ("state/shadow.db", "text_original", "body_original",
                          "NOT APPROVED FOR PUBLICATION"):
            self.assertNotIn(forbidden, page)
        self.assertNotIn(load()[0]["source_url"],
                         (out / "philippines.html").read_text(encoding="utf-8"))

    def test_second_family_remains_unregistered_with_no_press_shadow(self):
        from scripts.shadow_collect_desk import DESKS
        from core.manifests import load_all_desks
        self.assertNotIn("id_kemhan_press", DESKS)
        self.assertNotIn("indonesia", load_all_desks())


if __name__ == "__main__":
    unittest.main()
