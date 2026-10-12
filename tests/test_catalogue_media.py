"""
The Briefs catalogue's one media decision (Phase 3B).

`core/catalogue_media.py` decides, per card, between a credited photograph and
the original Editorial plate. These tests hold it to the Phase 0 rulings
(B2 no 81.cn, B3/B4 labels, B5 No. 12, B6 no share-alike) and to the Phase 3A
ledger: a plate is the default; Nos. 8, 9 and 10 are the only photographs;
No. 1 is held; No. 12 is refused; an article cover never grants anything.
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
PHOTO_ISSUES = {8, 9, 10}


def _row(issue, date, kind="issue", **entry):
    entry = dict(entry, issue=issue, date=date, slug="s-%s" % issue)
    return {"entry": entry, "kind": kind}


def _record(**over):
    base = {
        "issue": 8, "week_ending": "2026-06-27", "status": "admitted",
        "source_file": "site/assets/editorial/derivatives/x-duo-navy.jpg",
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

    def resolve(self, row, **over):
        rec = _record(served_sha256=self.digest, **over)
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
        rec = _record(issue=12, week_ending="2026-08-01", served_sha256=self.digest)
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

    def test_only_public_domain_and_cc_by_are_allowed(self):
        for lic in ("CC BY-SA 4.0", "CC BY-NC 4.0", "All rights reserved", "Unknown"):
            with self.subTest(licence=lic):
                self.assertEqual(self.resolve(_row(8, "2026-06-27"), license=lic).reason,
                                 "licence-not-allowed")
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
        for key in ("alt", "caption", "credit", "creator", "source_page", "change_note"):
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

    def test_seventeen_cards_three_photographs_fourteen_plates(self):
        self.assertEqual(len(self.audit), 17)
        photos = {a["issue"] for a in self.audit if a["kind"] == cm.KIND_PHOTOGRAPH}
        self.assertEqual(photos, PHOTO_ISSUES)
        self.assertEqual(sum(a["kind"] == cm.KIND_PLATE for a in self.audit), 14)

    def test_number_one_is_held_and_number_twelve_is_denied(self):
        by_issue = {a["issue"]: a for a in self.audit}
        self.assertEqual((by_issue[1]["kind"], by_issue[1]["reason"]), ("plate", "held"))
        self.assertEqual((by_issue[12]["kind"], by_issue[12]["reason"]), ("plate", "denied"))

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

    def test_admissions_are_exactly_the_three_reviewed_photographs(self):
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
                self.assertTrue(e["source_page"].startswith("https://commons.wikimedia.org/"))
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
        for e in self.record["entries"]:
            if e["status"] != "admitted":
                continue
            blob = bcm.derive(REPO_ROOT / e["source_file"], e["focal"])
            self.assertEqual(blob, bcm.derive(REPO_ROOT / e["source_file"], e["focal"]))
            self.assertEqual(blob, (REPO_ROOT / "site" / e["served"]).read_bytes())

    def test_resolver_module_reads_no_article_image_surface(self):
        src = (REPO_ROOT / "core/catalogue_media.py").read_text(encoding="utf-8")
        code = re.sub(r'""".*?"""', "", src, flags=re.S)
        for needle in ("brief_veil", "source_veil_for_edition", "pw_env", '["cover"]',
                       ".get(\"cover\")", '["photo"]', "output/"):
            self.assertNotIn(needle, code)


if __name__ == "__main__":
    unittest.main()
