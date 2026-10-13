"""Exact-scope Indonesia official-source navigation pilot, not archival admission."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from core.indonesia_official_index import (
    DEFAULT, PINNED, PublicIndexError, load, validate,
)
from scripts.preview_indonesia_reference_pilot import load as load_private_pilot


class IndonesiaOfficialSourceIndexTests(unittest.TestCase):
    def setUp(self):
        self.candidates = json.loads(DEFAULT.read_text(encoding="utf-8"))
        self.temp = tempfile.TemporaryDirectory(prefix="ipr-id-public-nav-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "index.json"

    def test_fifteen_first_party_links_keep_original_four_and_exclude_held_source(self):
        actual = load()
        pilot = load_private_pilot()
        self.assertEqual(len(actual), 15)
        self.assertEqual(self.candidates["pinned_shadow_commit"], PINNED)
        self.assertEqual(
            [(x["source_url"], x["title_original"], x["published_date"])
             for x in actual[:4]],
            [(x["source_url"], x["title_original"], x["published_date"])
             for x in pilot["candidates"]],
        )
        self.assertFalse(pilot["owner_release_approved"])
        self.assertFalse(pilot["independent_human_source_review_completed"])
        self.assertFalse(pilot["day7_review_completed"])
        self.assertEqual(actual[0]["id"], "id-01")
        self.assertEqual(
            [x["id"] for x in actual],
            ["id-01", "id-02", "id-03", "id-04",
             "id-06", "id-07", "id-08", "id-09",
             "id-10", "id-11", "id-12", "id-13", "id-14",
             "id-15", "id-16"],
        )
        self.assertFalse(any("yonif-tp-880-banuanta" in x["source_url"] for x in actual))
        self.assertEqual(
            [(x["id"], x["published_date"]) for x in actual[4:]],
            [("id-06", "2026-09-30"), ("id-07", "2026-10-03"),
             ("id-08", "2026-10-07"), ("id-09", "2026-10-09"),
             ("id-10", "2026-10-08"), ("id-11", "2026-10-08"),
             ("id-12", "2026-10-08"), ("id-13", "2026-10-09"),
             ("id-14", "2026-10-12"),
              ("id-15", "2026-10-03"), ("id-16", "2026-10-03")],
        )

    def test_public_registry_numbers_match_frozen_source_directories(self):
        """The reader-facing desk must not claim four links while showing fifteen."""
        from core.indonesia_press_index import load as load_press
        from core.desk_registry import load_registry

        news, press = load(), load_press()
        self.assertEqual((len(news), len(press)), (15, 2))
        desk = load_registry().get("indonesia")
        self.assertTrue(desk.public)
        self.assertEqual(desk.status, "shadow")
        self.assertFalse(desk.has_production_records)
        self.assertIsNone(desk.manifest_path)
        self.assertFalse(desk.is_collecting)
        # Validate the human-facing copy as well as the actual bibliography.
        registry = json.loads(
            (DEFAULT.parents[1] / "desks" / "registry.json").read_text(encoding="utf-8")
        )
        entry = next(row for row in registry["desks"] if row["slug"] == "indonesia")
        self.assertIn("Fifteen dated Berita links and two", entry["status_explanation"])
        self.assertIn(
            "seventeen first-party pages (fifteen Berita and two Siaran Pers)",
            entry["research"]["blockers"][1][1],
        )
        self.assertIn(
            "Fifteen Berita and two Siaran Pers first-party links",
            entry["limits"][0],
        )
        self.assertNotIn("four berita", json.dumps(entry).lower())
        self.assertIn("no admitted public corpus records", entry["limits"][0])

    def test_corrupt_forged_or_excessive_links_are_not_published(self):
        mutations = [
            lambda x: x["references"][0].update(url="https://www.kemhan.go.id.evil.test/2026/10/10/source.html"),
            lambda x: x["references"][0].update(url="http://www.kemhan.go.id/2026/10/10/source.html"),
            lambda x: x["references"][0].update(url="https://www.kemhan.go.id/category/berita"),
            lambda x: x["references"][0].update(url=x["references"][0]["url"] + "?redirect=1"),
            lambda x: x["references"][0].update(published_date="2026-10-09"),
            lambda x: x["references"][0].update(title_original="<script>bad</script>"),
            lambda x: x["references"][0].update(language="en"),
            lambda x: x["references"][0].update(text_original="private source body"),
            lambda x: x["references"].append(copy.deepcopy(x["references"][0])),
            lambda x: x["references"][4].update(title_original="Unreviewed inserted headline"),
            lambda x: x["references"][5].update(url="https://www.kemhan.go.id/2026/10/03/forged-source.html"),
            lambda x: x["references"][6].update(published_date="2026-10-08"),
            lambda x: x["references"][9].update(url="https://www.kemhan.go.id/2026/10/08/forged-source.html"),
            lambda x: x["references"][10].update(title_original="A new invented title"),
            lambda x: x["references"][11].update(published_date="2026-10-10"),
            lambda x: x["references"][13].update(title_original="Forged Yonif 921 headline"),
            lambda x: x["references"][14].update(url="https://www.kemhan.go.id/2026/10/03/forged-yonif-922.html"),
            lambda x: x["references"].insert(4, copy.deepcopy(x["references"][0])),
            lambda x: x.update(editorial_status="independently_reviewed"),
            lambda x: x.update(collection_status="production_admitted"),
            lambda x: x.update(pinned_shadow_commit="a"*40),
        ]
        for change in mutations:
            item = copy.deepcopy(self.candidates)
            change(item)
            with self.subTest(change=change), self.assertRaises(PublicIndexError):
                validate(item)

    def test_missing_file_bad_json_and_duplicate_keys_refused(self):
        with self.assertRaises(PublicIndexError):
            load(self.path)
        self.path.write_text('{"schema":"one","schema":"two"}', encoding="utf-8")
        with self.assertRaises(PublicIndexError):
            load(self.path)
        self.path.write_text(json.dumps(self.candidates, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(len(load(self.path)), 15)
        duplicate = self.path.parent / "symlink.json"
        duplicate.symlink_to(self.path)
        with self.assertRaises(PublicIndexError):
            load(duplicate)

    def test_real_site_has_fifteen_external_links_and_no_public_corpus(self):
        import sys
        from bs4 import BeautifulSoup
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "site" / "preview"))
        import generate_preview as gp

        db = root / "pla_watch.db"
        if not db.exists():
            self.skipTest("database fixture absent")
        output = Path(self.temp.name) / "render"
        gp.build(output, "Offline Indonesia Official Link Pilot", db,
                 snapshot=gp.snapshot_from_corpus(db))
        page = (output / "indonesia.html").read_text(encoding="utf-8")
        soup = BeautifulSoup(page, "html.parser")
        targets = soup.select("#indonesia-links-heading ~ ol a")
        if not targets:
            targets = soup.select('ol[aria-label="Fifteen external ministry news links"] a')
        self.assertEqual(len(targets), 15)
        self.assertEqual(
            {x["href"] for x in targets},
            {x["source_url"] for x in load()},
        )
        self.assertTrue(all(x.get("lang") == "id" for x in targets))
        self.assertIn("not independently", soup.get_text().lower().replace("\\n", " "))
        self.assertIn("No individual source references have completed", page)
        self.assertNotIn('data-reference-list', page)
        for forbidden in ("text_original", "body_original", "state/shadow.db",
                          "NOT APPROVED FOR PUBLICATION"):
            self.assertNotIn(forbidden, page)
        self.assertIn("Shadow evaluation — no public corpus records", page)
        self.assertIn("Fifteen dated Berita links and two historical Siaran Pers", page)
        notes = soup.select("div.desk-reference-reading-notes")
        self.assertEqual(len(notes), 1)
        self.assertEqual(len(notes[0].select("li")), 4)
        note_text = " ".join(notes[0].get_text(" ", strip=True).split())
        self.assertIn("not exclusively administrative fines", note_text)
        for part in ("Rp3.48 trillion", "Rp1.54 trillion", "Rp8.23 trillion",
                     "259,230.73-hectare", "mixed group", "does not prove its completion"):
            self.assertIn(part, note_text)
        self.assertIn("not independently certified IPR citations", note_text)
        self.assertIn("North Kalimantan border-battalion visits", note_text)
        self.assertIn("not independent verification", note_text)
        self.assertIn("Pangdam Wirabuana", note_text)
        self.assertIn("Kodam VI/Mulawarman", note_text)
        self.assertIn("unresolved", note_text)
        outgoing = {a["href"] for a in notes[0].select("a[href]")}
        self.assertEqual(outgoing, {
            "https://kejati-dkijakarta.kejaksaan.go.id/conference/news/14579/read",
            "https://www.kemhan.go.id/2026/10/09/mensos-dan-wamenhan-lepas-1-509-kadet-unhan-ri-untuk-mengabdi-di-181-sekolah-rakyat.html",
            "https://www.setneg.go.id/baca/index/pertemuan_presiden_prabowo_dan_presiden_el_sisi_hasilkan_empat_kesepakatan_kerja_sama",
        })
        self.assertTrue(all(a.get("rel") == ["noopener", "noreferrer"]
                            and a.get("target") == "_blank"
                            for a in notes[0].select("a[href]")))
        self.assertIn("<dt>Corpus records</dt><dd>Not admitted</dd>", page)
        self.assertNotIn("<dt>Records</dt><dd>None collected</dd>", page)
        self.assertNotIn("Four dated Berita links", page)
        self.assertNotIn(load()[0]["source_url"],
                         (output / "philippines.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
