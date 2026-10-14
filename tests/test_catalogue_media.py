"""
The Briefs catalogue's one media decision (Phase 3B).

`core/catalogue_media.py` decides, per card, between a credited photograph and
the original Editorial plate. These tests hold it to the Phase 0 rulings
(B2 no 81.cn, B3/B4 labels, B5 No. 12, B6 no share-alike) and to the Phase 3A
ledger: a plate is the default; Nos. 8 and 9 are the only photographs;
Nos. 1 and 10 are held; No. 12 is refused; an article cover never grants anything.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "site" / "preview"))

from core import catalogue_media as cm                       # noqa: E402
from core.brief_collection import load_collection             # noqa: E402
from core.desk_registry import load_registry                  # noqa: E402

ADMISSIONS = REPO_ROOT / "site/assets/catalogue/admissions.json"
MANIFEST = REPO_ROOT / "site/assets/editorial/manifest.json"
MEDIA = REPO_ROOT / "site/assets/catalogue/media"
PHOTO_ISSUES = {6, 7, 8, 9, 13, 14, 17, 18}
#: Where each admitted card's source page may be. No. 17 is the paired DVIDS
#: cover (treatment B, owner-selected 2026-10-12); the others are Commons files.
SOURCE_HOSTS = {6: "https://commons.wikimedia.org/", 7: "https://www.dvidshub.net/", 8: "https://commons.wikimedia.org/", 9: "https://commons.wikimedia.org/",
                13: "https://commons.wikimedia.org/",
                14: "https://commons.wikimedia.org/",
                17: "https://www.dvidshub.net/image/",
                18: "https://commons.wikimedia.org/"}
HELD_ISSUES = {1, 10}


def _row(issue, date, kind="issue", **entry):
    entry = dict(entry, issue=issue, date=date, slug="s-%s" % issue)
    return {"entry": entry, "kind": kind}


def _record(**over):
    base = {
        "issue": 8, "week_ending": "2026-06-27", "status": "admitted",
        "source_file": "site/assets/editorial/derivatives/x-duo-navy.jpg",
        "source_manifest_id": "x", "source_sha256": "",
        "served": "assets/catalogue/media/no-08-x.jpg", "focal": "50% 50%",
        "alt": "alt", "caption": "caption", "credit": "c · CC BY 4.0 · via Wikimedia Commons",
        "creator": "c", "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0",
        "source_page": "https://commons.wikimedia.org/wiki/File:X.jpg",
        "source_label": "Wikimedia Commons", "change_note": "Toned, cropped and resized by IPR.",
        "served_sha256": "", "width": 720, "height": 480}
    base.update(over)
    return base


class ResolverRuleTests(unittest.TestCase):
    """The resolver against a scratch repository, so no real record is touched."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="catalogue-media-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.served = self.tmp / "site/assets/catalogue/media/no-08-x.jpg"
        self.served.parent.mkdir(parents=True)
        self.served.write_bytes(b"placeholder derivative bytes")
        self.digest = cm.sha256_file(self.served)
        # The curated source this admission was reviewed against, and the
        # manifest entry that names it.
        self.source = self.tmp / "site/assets/editorial/derivatives/x-duo-navy.jpg"
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b"curated source derivative bytes")
        self.source_digest = cm.sha256_file(self.source)
        self.manifest = self.tmp / cm.MANIFEST_PATH
        self.write_manifest()

    def write_manifest(self, **over):
        entry = {"id": "x", "license": "CC BY 4.0",
                 "license_url": "https://creativecommons.org/licenses/by/4.0",
                 "source_page": "https://commons.wikimedia.org/wiki/File:X.jpg",
                 "credit": "c · CC BY 4.0 · via Wikimedia Commons"}
        entry.update(over)
        self.manifest.write_text(json.dumps([entry]), encoding="utf-8")

    def resolve(self, row, **over):
        fields = dict(served_sha256=self.digest, source_sha256=self.source_digest)
        fields.update(over)
        rec = _record(**fields)
        adm = {(rec["issue"], rec["week_ending"]): rec}
        return cm.resolve_catalogue_media(row, adm, repo_root=self.tmp)

    def test_an_admitted_record_that_passes_every_check_is_a_photograph(self):
        m = self.resolve(_row(8, "2026-06-27"))
        self.assertTrue(m.is_photograph)
        self.assertEqual(m.photo["served"], "assets/catalogue/media/no-08-x.jpg")

    def test_the_default_is_the_plate(self):
        m = cm.resolve_catalogue_media(_row(8, "2026-06-27"), {}, repo_root=self.tmp)
        self.assertEqual((m.kind, m.reason), (cm.KIND_PLATE, "no-admission-record"))

    def test_held_and_denied_statuses_fall_back_to_the_plate(self):
        for status in ("held", "denied", "pending", ""):
            with self.subTest(status=status):
                m = self.resolve(_row(8, "2026-06-27"), status=status)
                self.assertEqual(m.kind, cm.KIND_PLATE)

    def test_issue_twelve_is_refused_whatever_a_record_says(self):
        rec = _record(issue=12, week_ending="2026-08-01", served_sha256=self.digest,
                      source_sha256=self.source_digest)
        m = cm.resolve_catalogue_media(_row(12, "2026-08-01"), {(12, "2026-08-01"): rec},
                                       repo_root=self.tmp)
        self.assertEqual((m.kind, m.reason), (cm.KIND_PLATE, "denied"))

    def test_a_record_matches_its_week_not_just_its_number(self):
        m = self.resolve(_row(8, "2026-06-20"))
        self.assertEqual(m.reason, "no-admission-record")

    def test_a_missing_or_altered_file_falls_back(self):
        self.served.write_bytes(b"altered")
        self.assertEqual(self.resolve(_row(8, "2026-06-27")).reason, "hash-mismatch")
        self.served.unlink()
        self.assertEqual(self.resolve(_row(8, "2026-06-27")).reason, "file-missing")

    def test_a_swapped_or_removed_curated_source_falls_back(self):
        row = _row(8, "2026-06-27")
        self.assertTrue(self.resolve(row).is_photograph)
        self.source.write_bytes(b"a different curated derivative")
        m = self.resolve(row)
        self.assertEqual((m.kind, m.reason), (cm.KIND_PLATE, "source-hash-mismatch"))
        self.source.unlink()
        self.assertEqual(self.resolve(row).reason, "source-missing")

    def test_a_changed_or_missing_manifest_entry_falls_back(self):
        row = _row(8, "2026-06-27")
        for key, value in (("license", "CC BY-SA 4.0"),
                           ("license_url", "https://example.invalid/other"),
                           ("source_page", "https://commons.wikimedia.org/wiki/File:Y.jpg"),
                           ("credit", "someone else · CC BY 4.0 · via Wikimedia Commons")):
            with self.subTest(changed=key):
                self.write_manifest(**{key: value})
                m = self.resolve(row)
                self.assertEqual((m.kind, m.reason), (cm.KIND_PLATE, "manifest-changed:" + key))
        self.write_manifest(id="y")
        self.assertEqual(self.resolve(row).reason, "manifest-entry-missing")
        self.manifest.unlink()
        self.assertEqual(self.resolve(row).reason, "manifest-entry-missing")

    def test_a_card_notice_and_treatment_must_agree_with_the_manifest(self):
        row = _row(8, "2026-06-27")
        notice = "Non-endorsement notice."
        self.write_manifest(notice=notice, cover_treatment="gradient")
        note = "Cropped and resized by IPR; IPR gradient overlaid."
        self.assertTrue(self.resolve(row, notice=notice, cover_treatment="gradient",
                                     change_note=note).is_photograph)
        # A dropped notice or a different treatment is a different record.
        self.assertEqual(self.resolve(row, cover_treatment="gradient", change_note=note).reason,
                         "manifest-changed:notice")
        self.assertEqual(self.resolve(row, notice=notice, cover_treatment="photograph",
                                      change_note="Cropped and resized by IPR.").reason,
                         "manifest-changed:cover_treatment")

    def test_a_treated_card_must_say_what_was_done_to_it(self):
        row = _row(8, "2026-06-27")
        self.write_manifest(cover_treatment="gradient")
        m = self.resolve(row, cover_treatment="gradient",
                         change_note="Cropped and resized by IPR.")
        self.assertEqual((m.kind, m.reason), (cm.KIND_PLATE, "change-note-not-treatment"))
        m = self.resolve(row, cover_treatment="gradient",
                         change_note="Cropped and resized by IPR; IPR gradient overlaid.")
        self.assertTrue(m.is_photograph)
        self.assertEqual((m.photo["cover_treatment"], m.photo["notice"]), ("gradient", ""))

    def test_the_source_must_belong_to_the_manifest_entry_it_names(self):
        m = self.resolve(_row(8, "2026-06-27"), source_manifest_id="other")
        self.assertEqual(m.reason, "source-not-from-manifest-entry")

    def test_only_public_domain_and_cc_by_are_allowed(self):
        for lic in ("CC BY-SA 4.0", "CC BY-NC 4.0", "All rights reserved", "Unknown"):
            with self.subTest(licence=lic):
                self.assertEqual(self.resolve(_row(8, "2026-06-27"), license=lic).reason,
                                 "licence-not-allowed")
        self.write_manifest(license="Public domain", license_url="")
        pd = self.resolve(_row(8, "2026-06-27"), license="Public domain", license_url="")
        self.assertTrue(pd.is_photograph)

    def test_cc_by_without_a_licence_link_falls_back(self):
        m = self.resolve(_row(8, "2026-06-27"), license_url="")
        self.assertEqual(m.reason, "licence-link-missing")

    def test_veil_and_source_image_paths_are_never_admitted(self):
        for key, value in (
                ("source_file", "site/assets/editorial/derivatives/x-source-image.jpg"),
                ("source_file", "output/the-pla-watch/media/2026-07-18-veil.jpg"),
                ("served", "assets/catalogue/media/no-08-veil.jpg"),
                ("served", "assets/catalogue/media/no-08-source-image.jpg"),
                ("served", "assets/the-pla-watch/media/x.jpg")):
            with self.subTest(**{key: value}):
                self.assertNotEqual(self.resolve(_row(8, "2026-06-27"), **{key: value}).kind,
                                    cm.KIND_PHOTOGRAPH)

    def test_an_incomplete_credit_falls_back(self):
        for key in ("alt", "caption", "credit", "creator", "source_page", "change_note",
                    "source_manifest_id", "source_sha256"):
            with self.subTest(missing=key):
                m = self.resolve(_row(8, "2026-06-27"), **{key: ""})
                self.assertEqual(m.reason, "incomplete-record:" + key)

    def test_a_plain_http_source_page_falls_back(self):
        m = self.resolve(_row(8, "2026-06-27"), source_page="http://commons.wikimedia.org/x")
        self.assertEqual(m.reason, "source-page-not-https")

    def test_review_and_synthetic_rows_never_show_a_photograph(self):
        for flag in ("is_review", "synthetic"):
            with self.subTest(flag=flag):
                m = self.resolve(_row(8, "2026-06-27", kind="brief", **{flag: True}))
                self.assertEqual((m.kind, m.reason), (cm.KIND_PLATE, "not-a-published-brief"))

    def test_the_resolver_ignores_article_covers_and_photos(self):
        row = _row(9, "2026-07-04", cover={"route": "media/x.jpg"}, photo="x.jpg")
        self.assertEqual(cm.resolve_catalogue_media(row, {}, repo_root=self.tmp).kind,
                         cm.KIND_PLATE)

    def test_a_missing_record_file_is_an_empty_record(self):
        self.assertEqual(cm.load_admissions(self.tmp / "nope.json"), {})


class CommittedRecordTests(unittest.TestCase):
    """The committed admission record and the real collection."""

    @classmethod
    def setUpClass(cls):
        import generate_preview as gp
        cls.record = json.loads(ADMISSIONS.read_text(encoding="utf-8"))
        cls.admissions = cm.load_admissions(repo_root=REPO_ROOT)
        cls.rows = load_collection(gp.load_editions(REPO_ROOT), load_registry(),
                                   briefs_dir=REPO_ROOT / "briefs").rows
        cls.audit = cm.audit_rows(cls.rows, cls.admissions, repo_root=REPO_ROOT)
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.manifest = {m["id"]: m for m in manifest}

    def test_every_row_is_a_card_and_only_the_admitted_issues_are_photographs(self):
        # Row-count agnostic: publishing No. 18 must not turn this red.
        self.assertEqual(len(self.audit), len(self.rows))
        self.assertGreaterEqual(len(self.audit), 17)
        photos = {a["issue"] for a in self.audit if a["kind"] == cm.KIND_PHOTOGRAPH}
        self.assertEqual(photos, PHOTO_ISSUES)
        plates = sum(a["kind"] == cm.KIND_PLATE for a in self.audit)
        self.assertEqual(plates, len(self.rows) - len(PHOTO_ISSUES))

    def test_numbers_one_and_ten_are_held_and_number_twelve_is_denied(self):
        by_issue = {a["issue"]: a for a in self.audit}
        for issue in HELD_ISSUES:
            with self.subTest(issue=issue):
                self.assertEqual((by_issue[issue]["kind"], by_issue[issue]["reason"]),
                                 ("plate", "held"))
        self.assertEqual((by_issue[12]["kind"], by_issue[12]["reason"]), ("plate", "denied"))

    def test_number_ten_is_held_for_authorship_and_serves_nothing(self):
        record = next(e for e in self.record["entries"] if e["issue"] == 10)
        self.assertEqual(record["status"], "held")
        self.assertIn("original government authorship", record["reason"])
        self.assertIn("provided to CRS", record["reason"])
        # No drafted alt, caption or served derivative may survive the hold.
        for key in ("alt", "caption", "served", "served_sha256"):
            self.assertNotIn(key, record)
        self.assertFalse(list(MEDIA.glob("no-10-*")))

    def test_wave2_photographs_are_explicitly_historical_and_source_distinct(self):
        by_issue = {e["issue"]: e for e in self.record["entries"]}
        six, fourteen = by_issue[6], by_issue[14]
        self.assertNotEqual(six["source_page"], fourteen["source_page"])
        eight = by_issue[8]
        self.assertNotEqual(six["source_page"], eight["source_page"])
        self.assertNotEqual(self.manifest[six["source_manifest_id"]]["sha256"], self.manifest[eight["source_manifest_id"]].get("sha256"))
        self.assertIn("2022", six["caption"])
        self.assertIn("2026", six["caption"])
        self.assertIn("2016", fourteen["caption"])
        self.assertIn("2026", fourteen["caption"])
        self.assertIn("not", fourteen["caption"].lower())
        self.assertIn("not", six["caption"].lower())
        from core.source_terms import required_notice
        self.assertEqual(fourteen["notice"], required_notice({"source_label": "DVIDS"}))
        self.assertEqual(self.audit[[a["issue"] for a in self.audit].index(6)]["kind"], "photograph")
        self.assertEqual(self.audit[[a["issue"] for a in self.audit].index(14)]["kind"], "photograph")

    def test_wave3_2015_nasa_and_2019_uscg_are_explicit_historical_context(self):
        by_issue = {e["issue"]: e for e in self.record["entries"]}
        ccg, shoal, previous = by_issue[7], by_issue[13], by_issue[9]
        self.assertNotEqual(shoal["source_page"], previous["source_page"])
        self.assertNotEqual(self.manifest[shoal["source_manifest_id"]]["sha256"],
                            self.manifest[previous["source_manifest_id"]].get("sha256"))
        self.assertIn("2015", shoal["caption"])
        self.assertIn("2026", shoal["caption"])
        self.assertIn("2019", ccg["caption"])
        self.assertIn("2026", ccg["caption"])
        self.assertIn("South China Sea", ccg["caption"])
        self.assertIn("east of Taiwan", ccg["caption"])
        from core.source_terms import required_notice
        self.assertEqual(ccg["notice"], required_notice(ccg))
        self.assertEqual(shoal.get("notice", ""), "")
        by_audit = {a["issue"]: a for a in self.audit}
        self.assertTrue(all(by_audit[i]["kind"] == "photograph" for i in (7, 13)))

    def test_every_plate_names_its_reason(self):
        for a in self.audit:
            if a["kind"] == cm.KIND_PLATE:
                self.assertTrue(a["reason"], a)
                self.assertIsNone(a["served"])

    def test_no_card_can_resolve_to_a_veil_or_an_81cn_image(self):
        for a in self.audit:
            if a["served"]:
                self.assertTrue(a["served"].startswith(cm.MEDIA_ROUTE_PREFIX))
                self.assertNotRegex(a["served"], r"veil|source-image|81")
        for entry in self.record["entries"]:
            for key in ("source_file", "served"):
                self.assertNotRegex(str(entry.get(key, "")), r"veil|source-image|81\.cn|81cn")

    def test_admissions_are_exactly_the_admitted_photographs(self):
        admitted = {e["issue"] for e in self.record["entries"] if e["status"] == "admitted"}
        self.assertEqual(admitted, PHOTO_ISSUES)
        self.assertEqual(sorted(p.name for p in MEDIA.iterdir()),
                         sorted(Path(e["served"]).name for e in self.record["entries"]
                                if e["status"] == "admitted"))

    def test_every_admitted_card_carries_credit_licence_and_link(self):
        for e in self.record["entries"]:
            if e["status"] != "admitted":
                continue
            with self.subTest(issue=e["issue"]):
                self.assertIn(e["license"], cm.ALLOWED_LICENCES)
                if e["license"] in cm.LICENCE_NEEDS_LINK:
                    self.assertTrue(e["license_url"].startswith("https://"))
                self.assertTrue(e["source_page"].startswith(SOURCE_HOSTS[e["issue"]]))
                self.assertEqual((e["width"], e["height"]), (720, 480))
                self.assertTrue(e["alt"] and e["caption"] and e["change_note"])

    def test_the_visible_credit_is_the_manifest_credit_reconstructed(self):
        for e in self.record["entries"]:
            if e["status"] != "admitted":
                continue
            with self.subTest(issue=e["issue"]):
                m = self.manifest[e["source_manifest_id"]]
                self.assertEqual(e["alt"], m["alt"])
                self.assertEqual(e["caption"], m["caption"])
                self.assertEqual(e["credit"], m["credit"])
                self.assertEqual(e["license"], m["license"])
                self.assertEqual(e["license_url"], m.get("license_url", ""))
                self.assertEqual(e["source_page"], m["source_page"])
                native = " (%s)" % e["creator_native"] if e["creator_native"] else ""
                rebuilt = "%s%s · %s · via %s" % (e["creator"], native, e["license"], e["source_label"])
                self.assertEqual(rebuilt, e["credit"])

    def test_served_files_match_their_recorded_hashes_and_size(self):
        from PIL import Image
        for e in self.record["entries"]:
            if e["status"] != "admitted":
                continue
            path = REPO_ROOT / "site" / e["served"]
            self.assertEqual(cm.sha256_file(path), e["served_sha256"])
            self.assertEqual(cm.sha256_file(REPO_ROOT / e["source_file"]), e["source_sha256"])
            with Image.open(path) as im:
                self.assertEqual(im.size, (e["width"], e["height"]))
                self.assertFalse(im.info.get("exif"))

    def test_the_receipt_the_record_cites_exists(self):
        receipt = REPO_ROOT / self.record["receipt"]
        self.assertTrue(receipt.is_file())
        self.assertTrue(json.loads(receipt.read_text(encoding="utf-8")))

    def test_the_builder_is_deterministic(self):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import build_catalogue_media as bcm
        from PIL import Image
        same_encoder = bcm.PILLOW_VERSION == self.record.get("built_with", {}).get("pillow")
        for e in self.record["entries"]:
            if e["status"] != "admitted":
                continue
            with self.subTest(issue=e["issue"]):
                blob = bcm.derive(REPO_ROOT / e["source_file"], e["focal"])
                self.assertEqual(blob, bcm.derive(REPO_ROOT / e["source_file"], e["focal"]))
                with Image.open(__import__("io").BytesIO(blob)) as im:
                    self.assertEqual(im.size, (e["width"], e["height"]))
                # Byte equality holds only for the encoder that wrote the file.
                # Other Pillow/libjpeg builds may differ; production is protected
                # by the resolver's hash check on the committed file instead.
                if same_encoder:
                    self.assertEqual(blob, (REPO_ROOT / "site" / e["served"]).read_bytes())

    def test_resolver_module_reads_no_article_image_surface(self):
        src = (REPO_ROOT / "core/catalogue_media.py").read_text(encoding="utf-8")
        code = re.sub(r'""".*?"""', "", src, flags=re.S)
        for needle in ("brief_veil", "source_veil_for_edition", "pw_env", '["cover"]',
                       ".get(\"cover\")", '["photo"]', "output/"):
            self.assertNotIn(needle, code)


class HeroPhotographTests(unittest.TestCase):
    """The hero photograph path, which no real native lead reaches today.

    `analysis.html` renders `.briefs-lead-photo` only when the lead resolves to
    an admitted photograph, and its caption must carry the same credit as a
    card: caption, creator with native name, licence link, source link and
    change note. The synthetic lead below is a non-synthetic copy of the
    fixture Brief; the resolver is patched to admit it with No. 8's record.
    """

    @classmethod
    def setUpClass(cls):
        import copy
        import functools
        from tests import brief_fixtures
        import generate_preview as gp
        cls.gp = gp
        cls.slug = brief_fixtures.FIXTURE_SLUG
        cls.root = Path(tempfile.mkdtemp(prefix="catalogue-hero-"))
        side = json.loads((brief_fixtures.FIXTURE_DIR / (cls.slug + ".json"))
                          .read_text(encoding="utf-8"))
        side = copy.deepcopy(side)
        side.pop("synthetic", None)
        side.pop("fixture_note", None)
        briefs = cls.root / "briefs-src"
        shutil.copytree(brief_fixtures.FIXTURE_DIR, briefs)
        (briefs / (cls.slug + ".json")).write_text(json.dumps(side), encoding="utf-8")
        brief_fixtures.write_synthetic_veil(briefs / "media" / (cls.slug + "-veil.jpg"))
        # A real admitted record, resolved by the real resolver.
        adm = cm.load_admissions(repo_root=REPO_ROOT)
        real = cm.resolve_catalogue_media(_row(8, "2026-06-27"), adm, repo_root=REPO_ROOT)
        assert real.is_photograph, real.reason
        cls.photo = real.photo
        original_resolve = gp.resolve_catalogue_media
        original_collection = gp.load_collection

        def admit_the_lead(row, admissions, **kw):
            if row["entry"].get("slug") == cls.slug:
                return cm.CatalogueMedia(cm.KIND_PHOTOGRAPH, "admitted", 8, (), real.photo)
            return original_resolve(row, admissions, **kw)

        db = REPO_ROOT / "pla_watch.db"
        snap = gp.snapshot_from_corpus(db)
        gp.load_collection = functools.partial(original_collection, unreconciled=frozenset())
        try:
            gp.build(cls.root / "default", gp.PUBLIC_TITLE, db, snapshot=snap, briefs_dir=briefs,
                     site_origin="https://briefs-review.test", allow_test_origin=True)
            gp.resolve_catalogue_media = admit_the_lead
            gp.build(cls.root / "admitted", gp.PUBLIC_TITLE, db, snapshot=snap, briefs_dir=briefs,
                     site_origin="https://briefs-review.test", allow_test_origin=True)
        finally:
            gp.resolve_catalogue_media = original_resolve
            gp.load_collection = original_collection

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def hero(self, name):
        html = (self.root / name / "analysis.html").read_text(encoding="utf-8")
        m = re.search(r'<figure class="briefs-lead-photo">.*?</figure>', html, re.S)
        return html, (m.group(0) if m else None)

    def test_a_lead_without_an_admission_has_no_hero_photograph(self):
        html, fig = self.hero("default")
        self.assertIsNone(fig)
        self.assertIn('class="briefs-lead"', html)

    def test_an_admitted_cc_by_lead_is_credited_like_a_card(self):
        html, fig = self.hero("admitted")
        self.assertIsNotNone(fig)
        p = self.photo
        self.assertIn('src="%s"' % p["served"], fig)
        self.assertIn('alt="%s"' % p["alt"], fig)
        cap = fig[fig.index("<figcaption>"):]
        self.assertIn(p["caption"], cap)
        self.assertIn(p["date_note"], cap)
        self.assertIn(p["creator"], cap)
        self.assertIn('<span lang="%s">%s</span>' % (p["creator_native_lang"], p["creator_native"]), cap)
        self.assertIn('<a href="%s" rel="noopener">%s</a>' % (p["license_url"], p["license"]), cap)
        self.assertIn('<a href="%s" rel="noopener">%s</a>' % (p["source_page"], p["source_label"]), cap)
        self.assertIn(p["change_note"], cap)
        self.assertIn("Visual context, not evidence.", cap)

    def test_the_hero_credit_is_the_card_credit(self):
        # One macro renders both; the hero caption is not a second credit format.
        html = (self.root / "admitted" / "analysis.html").read_text(encoding="utf-8")
        tpl = (REPO_ROOT / "site/preview/templates/analysis.html").read_text(encoding="utf-8")
        self.assertEqual(tpl.count("photo_credit("), 2)
        self.assertNotIn("lp.credit", tpl)
        self.assertIn("Photo: ", html)


if __name__ == "__main__":
    unittest.main()
