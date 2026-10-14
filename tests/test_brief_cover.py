"""
A native Brief's cover photograph: the gate in `core.brief_cover`.

The rule tests run against a scratch repository, so no real record is touched.
The committed-record tests read the real manifest and derivatives. Rendered
pages are covered in `tests/test_article_media.py`, which already builds the
site once.
"""
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import brief_cover as bcv                              # noqa: E402
from core.source_terms import required_notice                   # noqa: E402

SLUG = "trident-resolve-regional-scale-specific-chinese-tasks"
ENTRY_ID = "trident-resolve-basarnas-drone"


class GateRuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="brief-cover-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        ed = self.tmp / bcv.EDITORIAL_ROOT
        (ed / "derivatives").mkdir(parents=True)
        (ed / "x.jpg").write_bytes(b"retained source bytes")
        derivs = []
        for suffix in bcv._DERIVATIVES:
            rel = "derivatives/x" + suffix
            (ed / rel).write_bytes(b"derivative " + suffix.encode())
            derivs.append({"file": rel, "width": 1600, "height": 1067,
                           "sha256": bcv.sha256_file(ed / rel)})
        self.entry = {
            "id": "x", "file": "x.jpg", "sha256": bcv.sha256_file(ed / "x.jpg"),
            "alt": "alt", "caption": "caption", "credit": "c · Public domain · via DVIDS",
            "creator": "c", "license": "Public domain",
            "source_page": "https://www.dvidshub.net/image/1", "source_label": "DVIDS",
            "cover_treatment": "gradient", "derivative_builder": bcv.BUILDER,
            "surfaces": ["article"], "depicts": "event",
            "notice": required_notice({"source_label": "DVIDS"}),
            "derivatives": derivs,
            "match": {"article_urls": [], "categories": [], "threads": [], "editions": [],
                      "routes": [], "briefs": ["s"]}}

    def grant(self, *entries):
        return bcv.brief_cover("s", self.tmp, manifest=list(entries) or [self.entry])

    def changed(self, **over):
        e = copy.deepcopy(self.entry)
        e.update(over)
        return e

    def test_a_complete_entry_is_granted_with_its_three_files(self):
        cover = self.grant()
        self.assertEqual([f["route"] for f in cover["files"]],
                         ["assets/editorial/derivatives/x" + s for s in bcv._DERIVATIVES])
        self.assertTrue(cover["src"]["route"].endswith("-1600.jpg"))
        self.assertEqual(len(cover["webp"]), 2)

    def test_only_the_named_brief_is_granted(self):
        self.assertIsNone(bcv.brief_cover("other", self.tmp, manifest=[self.entry]))

    def test_two_entries_naming_one_brief_are_a_conflict(self):
        self.assertIsNone(self.grant(self.entry, self.changed(id="y")))

    def test_only_public_domain_and_cc_by_are_allowed(self):
        for licence in ("CC BY-SA 4.0", "All rights reserved", ""):
            with self.subTest(licence=licence):
                self.assertIsNone(self.grant(self.changed(license=licence)))
        self.assertEqual(bcv.problem(self.changed(license="CC BY 4.0"), self.tmp),
                         "licence-link-missing")

    def test_a_changed_source_or_derivative_grants_nothing(self):
        ed = self.tmp / bcv.EDITORIAL_ROOT
        (ed / "derivatives/x-800.webp").write_bytes(b"swapped")
        self.assertEqual(bcv.problem(self.entry, self.tmp), "derivative-hash-mismatch:-800.webp")
        (ed / "x.jpg").write_bytes(b"swapped")
        self.assertEqual(bcv.problem(self.entry, self.tmp), "source-hash-mismatch")
        self.assertIsNone(self.grant())

    def test_an_unrecorded_derivative_grants_nothing(self):
        e = self.changed(derivatives=self.entry["derivatives"][:2])
        self.assertEqual(bcv.problem(e, self.tmp), "derivative-unrecorded:-1600.webp")

    def test_a_cover_never_serves_another_surface(self):
        for key in bcv._EXCLUSIVE:
            with self.subTest(match=key):
                e = copy.deepcopy(self.entry)
                e["match"][key] = ["anything"]
                self.assertEqual(bcv.problem(e, self.tmp), "matches-another-surface")
        self.assertEqual(bcv.problem(self.changed(placement="home"), self.tmp),
                         "matches-another-surface")

    def test_a_cover_names_exactly_one_well_formed_brief_slug(self):
        for briefs in (["s", "t"], ["s", "s"], [], [""], ["S"], ["s t"], ["s/../t"],
                       ["-s"], ["s-"], [1], "s", None):
            with self.subTest(briefs=briefs):
                e = copy.deepcopy(self.entry)
                e["match"]["briefs"] = briefs
                self.assertEqual(bcv.problem(e, self.tmp), "brief-slug-invalid")
        e = copy.deepcopy(self.entry)
        e["match"]["briefs"] = ["s", "t"]
        for slug in ("s", "t"):
            with self.subTest(granted_to=slug):
                self.assertIsNone(bcv.brief_cover(slug, self.tmp, manifest=[e]))
        self.assertEqual(bcv.problem(self.changed(match={"briefs": ["s-30"]}), self.tmp), None)

    def test_unknown_treatment_other_builder_and_http_source_grant_nothing(self):
        self.assertEqual(bcv.problem(self.changed(cover_treatment="duotone"), self.tmp),
                         "unknown-treatment")
        self.assertEqual(bcv.problem(self.changed(derivative_builder="scripts/x.py"), self.tmp),
                         "not-a-cover-build")
        self.assertEqual(bcv.problem(self.changed(source_page="http://x.invalid/1"), self.tmp),
                         "source-page-not-https")

    def test_an_incomplete_credit_grants_nothing(self):
        for key in ("alt", "caption", "credit", "creator", "source_page", "source_label"):
            with self.subTest(missing=key):
                self.assertEqual(bcv.problem(self.changed(**{key: ""}), self.tmp),
                                 "incomplete-record:" + key)

    def test_every_treatment_has_a_change_note(self):
        self.assertEqual(set(bcv.TREATMENT_NOTES), {"photograph", "gradient"})
        for note in bcv.TREATMENT_NOTES.values():
            self.assertTrue(note.startswith("Cropped and resized by IPR"))


class CommittedCoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = bcv.load_manifest(ROOT)
        cls.entry = next(e for e in cls.manifest if e["id"] == ENTRY_ID)

    def test_reviewed_seventeen_and_eighteen_covers_are_granted(self):
        named = [e["id"] for e in self.manifest if (e.get("match") or {}).get("briefs")]
        self.assertEqual(set(named), {ENTRY_ID, 'laos-vientiane-museum-plane'})
        self.assertIsNotNone(bcv.brief_cover('what-is-being-built-in-laos', ROOT))
        self.assertIsNotNone(bcv.brief_cover(SLUG, ROOT))

    def test_the_record_carries_its_rights_and_restrictions(self):
        e = self.entry
        self.assertEqual(e["license"], "Public domain")
        self.assertEqual(e["source_page"], "https://www.dvidshub.net/image/9957254")
        self.assertEqual(e["dod_id"], "260921-A-XH946-9505")
        self.assertIn("does not imply or constitute DoW endorsement", e["notice"])
        self.assertIn("G3", e["license_basis"])
        self.assertIn("No Chinese or Singaporean personnel are shown or implied", e["note"])

    def test_g3_covers_editorial_use_and_the_date_conflict_stays_open(self):
        e = self.entry
        # G3 (DECISION_LOG 2026-10-12): editorial and news publication only,
        # without claiming every commercial use is prohibited.
        self.assertIn("editorial and news publication", e["license_basis"])
        self.assertIn("promote IPR is a different use", e["license_basis"])
        self.assertNotIn("not cleared", e["license_basis"])
        # DVIDS gives two dates; both are stated and neither is asserted.
        self.assertIn("21 September 2026 (caption)", e["date_note"])
        self.assertIn("20 September 2026 (date-taken field)", e["date_note"])
        self.assertNotIn("Photographed", e["date_note"])

    def test_the_card_admission_agrees_with_the_cover(self):
        record = json.loads((ROOT / "site/assets/catalogue/admissions.json").read_text())
        card = [r for r in record["entries"] if r.get("source_manifest_id") == ENTRY_ID]
        self.assertEqual(len(card), 1)
        card = card[0]
        for key in ("alt", "caption", "credit", "creator", "license", "license_url",
                    "source_page", "source_label", "date_note", "notice", "cover_treatment"):
            with self.subTest(field=key):
                self.assertEqual(card[key], self.entry[key])
        self.assertEqual(card["change_note"], bcv.TREATMENT_NOTES[self.entry["cover_treatment"]])
        self.assertEqual(card["source_file"],
                         "site/assets/editorial/derivatives/%s-1600.jpg" % ENTRY_ID)

    def test_the_derivatives_match_their_record(self):
        out = subprocess.run([sys.executable, str(ROOT / "scripts/build_brief_cover.py"),
                              "--check"], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(out.stdout.count("ok  "), 6)


if __name__ == "__main__":
    unittest.main()
