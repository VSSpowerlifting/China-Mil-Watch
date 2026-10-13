"""
A paired Brief cover: one photograph on the catalogue card and the opened
article, or on neither (`core.brief_photography`), plus the source-notice
rule both gates share (`core.source_terms`).

The pair rules run against a scratch repository with a generic cover, so
admitting a later Brief needs no change here. The committed-record tests read
the real records.
"""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "site" / "preview"))

from core import brief_cover as bcv                              # noqa: E402
from core import catalogue_media as cm                           # noqa: E402
from core.brief_collection import load_collection                 # noqa: E402
from core.desk_registry import load_registry                      # noqa: E402
from core.brief_photography import article_cover, pair_problem    # noqa: E402
from core.source_terms import notice_problem, required_notice     # noqa: E402

DVIDS_NOTICE = required_notice({"source_label": "DVIDS"})
BRIEF = {"issue": 30, "date": "2026-11-07", "slug": "s-30"}
WEEK = (30, "2026-11-07")


class NoticeTests(unittest.TestCase):
    def test_dvids_is_recognised_by_host_or_label(self):
        for entry in ({"source_page": "https://www.dvidshub.net/image/1"},
                      {"source_page": "https://dvidshub.net/image/1"},
                      {"source_page": "https://example.org/x", "source_label": "dvids"}):
            with self.subTest(entry=entry):
                self.assertEqual(required_notice(entry), DVIDS_NOTICE)

    def test_a_lookalike_host_is_not_dvids(self):
        self.assertIsNone(required_notice({"source_page": "https://notdvidshub.net/image/1"}))

    def test_missing_and_altered_notices_fail(self):
        base = {"source_page": "https://www.dvidshub.net/image/1", "source_label": "DVIDS"}
        self.assertEqual(notice_problem(base), "required-notice-missing")
        self.assertEqual(notice_problem(dict(base, notice="")), "required-notice-missing")
        for altered in (DVIDS_NOTICE.rstrip("."), DVIDS_NOTICE.lower(),
                        DVIDS_NOTICE.replace("DoW", "DoD"), DVIDS_NOTICE + " "):
            with self.subTest(notice=altered):
                self.assertEqual(notice_problem(dict(base, notice=altered)),
                                 "required-notice-altered")
        self.assertIsNone(notice_problem(dict(base, notice=DVIDS_NOTICE)))

    def test_other_public_domain_photographs_need_no_notice(self):
        for entry in ({"source_page": "https://commons.wikimedia.org/wiki/File:X.jpg",
                       "source_label": "Wikimedia Commons", "license": "Public domain"},
                      {"source_page": "https://images.nasa.gov/details/x",
                       "source_label": "NASA", "license": "Public domain"}):
            with self.subTest(source=entry["source_label"]):
                self.assertIsNone(required_notice(entry))
                self.assertIsNone(notice_problem(entry))


class PairRuleTests(unittest.TestCase):
    """A generic paired cover in a scratch repository."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="brief-photography-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.ed = self.tmp / bcv.EDITORIAL_ROOT
        (self.ed / "derivatives").mkdir(parents=True)
        (self.ed / "cv.jpg").write_bytes(b"retained source bytes")
        derivs = []
        for suffix in bcv._DERIVATIVES:
            rel = "derivatives/cv" + suffix
            (self.ed / rel).write_bytes(b"derivative " + suffix.encode())
            derivs.append({"file": rel, "width": 1600, "height": 1067,
                           "sha256": bcv.sha256_file(self.ed / rel)})
        credit = {
            "alt": "alt", "caption": "caption", "credit": "c · Public domain · via DVIDS",
            "creator": "c", "license": "Public domain",
            "license_url": "https://www.dvidshub.net/about/copyright",
            "source_page": "https://www.dvidshub.net/image/1", "source_label": "DVIDS",
            "date_note": "Date per source.", "notice": DVIDS_NOTICE,
            "cover_treatment": "gradient", "depicts": "event"}
        self.entry = dict(credit, **{
            "id": "cv", "file": "cv.jpg", "sha256": bcv.sha256_file(self.ed / "cv.jpg"),
            "derivative_builder": bcv.BUILDER, "derivatives": derivs,
            "surfaces": ["article", "catalogue"],
            "match": {"article_urls": [], "categories": [], "threads": [], "editions": [],
                      "routes": [], "briefs": [BRIEF["slug"]]}})
        self.served = self.tmp / "site/assets/catalogue/media/no-30-cv.jpg"
        self.served.parent.mkdir(parents=True)
        self.served.write_bytes(b"card crop bytes")
        self.record = dict(credit, **{
            "issue": WEEK[0], "week_ending": WEEK[1], "status": "admitted",
            "source_file": "site/assets/editorial/derivatives/cv-1600.jpg",
            "source_manifest_id": "cv", "focal": "50% 50%",
            "served": "assets/catalogue/media/no-30-cv.jpg",
            "change_note": bcv.TREATMENT_NOTES["gradient"],
            "source_sha256": bcv.sha256_file(self.ed / "derivatives/cv-1600.jpg"),
            "served_sha256": bcv.sha256_file(self.served), "width": 720, "height": 480})
        self.write(self.entry)

    def write(self, *entries):
        (self.tmp / bcv.MANIFEST_PATH).write_text(json.dumps(list(entries)), encoding="utf-8")

    def admissions(self, *records):
        records = records or (self.record,)
        return {(r["issue"], r["week_ending"]): r for r in records}

    def card(self, admissions=None, brief=BRIEF):
        return cm.resolve_catalogue_media({"kind": "brief", "entry": brief},
                                          admissions or self.admissions(), repo_root=self.tmp)

    def article(self, admissions=None, brief=BRIEF):
        return article_cover(brief, self.tmp, admissions=admissions or self.admissions())

    def assertNeither(self, reason=None, admissions=None):
        card = self.card(admissions)
        self.assertFalse(card.is_photograph)
        if reason:
            self.assertEqual(card.reason, reason)
        self.assertIsNone(self.article(admissions))

    def test_a_complete_pair_shows_one_photograph_on_both_surfaces(self):
        card = self.card()
        self.assertTrue(card.is_photograph, card.reason)
        self.assertEqual(card.photo["depicts"], "event")
        cover = self.article()
        self.assertEqual(cover["entry"]["id"], self.record["source_manifest_id"])

    def test_a_changed_file_takes_the_photograph_off_both_surfaces(self):
        cases = {
            "cv.jpg": "cover-failed:source-hash-mismatch",
            "derivatives/cv-1600.jpg": "source-hash-mismatch",
            "derivatives/cv-800.webp": "cover-failed:derivative-hash-mismatch:-800.webp",
            "derivatives/cv-1600.webp": "cover-failed:derivative-hash-mismatch:-1600.webp",
        }
        for rel, reason in cases.items():
            with self.subTest(file=rel):
                path = self.ed / rel
                original = path.read_bytes()
                path.write_bytes(b"swapped")
                try:
                    self.assertNeither(reason)
                finally:
                    path.write_bytes(original)
                self.assertTrue(self.card().is_photograph)

    def test_a_changed_card_crop_takes_the_photograph_off_both_surfaces(self):
        self.served.write_bytes(b"another crop")
        self.assertNeither("hash-mismatch")

    def test_a_removed_file_takes_the_photograph_off_both_surfaces(self):
        (self.ed / "derivatives/cv-800.webp").unlink()
        self.assertNeither("cover-failed:derivative-hash-mismatch:-800.webp")

    def test_mismatched_attribution_takes_the_photograph_off_both_surfaces(self):
        for key, value, reason in (
                ("credit", "someone else · Public domain · via DVIDS", "manifest-changed:credit"),
                ("creator", "someone else", "cover-record-differs:creator"),
                ("caption", "another caption", "cover-record-differs:caption"),
                ("source_page", "https://www.dvidshub.net/image/2", "manifest-changed:source_page"),
                ("license", "CC BY 4.0", "manifest-changed:license"),
                ("depicts", "context", "cover-record-differs:depicts")):
            with self.subTest(field=key):
                self.assertNeither(reason, self.admissions(dict(self.record, **{key: value})))

    def test_a_notice_missing_from_both_records_fails_both_gates(self):
        self.write(dict(self.entry, notice=""))
        self.assertNeither("required-notice-missing",
                           self.admissions(dict(self.record, notice="")))
        self.assertEqual(bcv.problem(dict(self.entry, notice=""), self.tmp),
                         "required-notice-missing")

    def test_an_altered_notice_on_both_records_fails_both_gates(self):
        altered = DVIDS_NOTICE.replace("does not imply", "need not imply")
        self.write(dict(self.entry, notice=altered))
        self.assertNeither("required-notice-altered",
                           self.admissions(dict(self.record, notice=altered)))

    def test_a_notice_missing_from_one_record_fails_both_surfaces(self):
        self.assertNeither("required-notice-missing",
                           self.admissions(dict(self.record, notice="")))
        self.write(dict(self.entry, notice=""))
        self.assertNeither("manifest-changed:notice")
        self.assertEqual(bcv.problem(dict(self.entry, notice=""), self.tmp),
                         "required-notice-missing")

    def test_a_held_card_takes_the_photograph_off_the_article(self):
        self.assertNeither("held", self.admissions(dict(self.record, status="held")))
        self.assertEqual(pair_problem(self.entry, BRIEF, self.tmp, {}),
                         "pair-card:no-admission-record")

    def test_a_card_cannot_show_a_cover_named_for_another_brief(self):
        other = dict(copy.deepcopy(self.entry), id="cv2")
        other["match"]["briefs"] = ["s-31"]
        for suffix in bcv._DERIVATIVES:
            shutil.copy(self.ed / ("derivatives/cv" + suffix), self.ed / ("derivatives/cv2" + suffix))
        other["derivatives"] = [dict(d, file=d["file"].replace("/cv-", "/cv2-"))
                                for d in other["derivatives"]]
        self.write(self.entry, other)
        record = dict(self.record, source_manifest_id="cv2",
                      source_file="site/assets/editorial/derivatives/cv2-1600.jpg")
        self.assertNeither("cover-names-another-brief", self.admissions(record))

    def test_two_records_claiming_one_cover_conflict(self):
        twin = dict(self.record, issue=31, week_ending="2026-11-14")
        self.assertNeither("cover-claimed-twice", self.admissions(self.record, twin))

    def test_two_covers_naming_one_brief_conflict(self):
        self.write(self.entry, dict(self.entry, id="cv2"))
        self.assertNeither("cover-conflict")

    def test_a_card_must_be_cut_from_the_cover_derivative(self):
        record = dict(self.record, source_file="site/assets/editorial/derivatives/cv-800.webp",
                      source_sha256=bcv.sha256_file(self.ed / "derivatives/cv-800.webp"))
        self.assertNeither("source-not-cover-derivative", self.admissions(record))

    def test_a_catalogue_only_approval_never_grants_the_article(self):
        self.write(dict(self.entry, surfaces=["catalogue"]))
        self.assertNeither("cover-failed:surfaces-invalid")
        # A card admitted from an ordinary manifest entry (as Nos. 8 and 9
        # are) is a photograph on the card and nothing on the article.
        plain = {k: v for k, v in self.entry.items()
                 if k not in ("derivative_builder", "match", "surfaces")}
        self.write(plain)
        self.assertTrue(self.card().is_photograph)
        self.assertIsNone(self.article())

    def test_an_article_only_cover_grants_no_card_and_keeps_its_article(self):
        self.write(dict(self.entry, surfaces=["article"]))
        self.assertEqual(self.card().reason, "cover-not-approved-for-catalogue")
        self.assertIsNotNone(self.article())
        self.assertIsNotNone(article_cover(BRIEF, self.tmp, admissions={}))

    def test_a_cover_must_classify_what_it_shows(self):
        for value in ("", "illustration", None):
            with self.subTest(depicts=value):
                self.write(dict(self.entry, depicts=value))
                self.assertIsNone(self.article(self.admissions(dict(self.record, depicts=value))))


class CommittedPairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = bcv.load_manifest(ROOT)
        cls.admissions = cm.load_admissions(repo_root=ROOT)
        import generate_preview as gp
        cls.collection = load_collection(gp.load_editions(ROOT), load_registry(),
                                         briefs_dir=ROOT / "briefs")

    def test_every_granted_cover_is_shown_on_both_of_its_surfaces(self):
        covers = [e for e in self.manifest if bcv.is_cover(e)]
        self.assertTrue(covers)
        briefs = {b["slug"]: b for b in self.collection.briefs}
        for entry in covers:
            for slug in entry["match"]["briefs"]:
                with self.subTest(cover=entry["id"], brief=slug):
                    self.assertIsNone(bcv.problem(entry, ROOT))
                    self.assertIsNone(pair_problem(entry, briefs[slug], ROOT, self.admissions))
                    self.assertIsNotNone(article_cover(briefs[slug], ROOT,
                                                       admissions=self.admissions))

    def test_catalogue_photographs_from_ordinary_entries_are_unaffected(self):
        rows = {r["entry"]["issue"]: r for r in self.collection.rows
                if isinstance(r["entry"].get("issue"), int)}
        for issue in (8, 9):
            with self.subTest(issue=issue):
                record = self.admissions[(issue, str(rows[issue]["entry"]["date"]))]
                curated = next(e for e in self.manifest
                               if e["id"] == record["source_manifest_id"])
                self.assertFalse(bcv.is_cover(curated))
                media = cm.resolve_catalogue_media(rows[issue], self.admissions, repo_root=ROOT)
                self.assertTrue(media.is_photograph, media.reason)

    def test_every_admitted_card_carries_any_required_notice(self):
        for record in self.admissions.values():
            if record.get("status") == "admitted":
                with self.subTest(issue=record["issue"]):
                    self.assertIsNone(notice_problem(record))


if __name__ == "__main__":
    unittest.main()
