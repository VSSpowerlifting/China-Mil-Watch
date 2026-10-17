"""Offline negative-control tests for B0 dossier *discovery*, not publication."""
import unittest

from scripts.audit_dossier_candidates import TOPICS, match_topic, iso_week


def lead(title, desk="singapore", categories=()):
    return {
        "title_original": title,
        "title_english": "",
        "desk_id": desk,
    }, set(categories)


class DossierCandidateAuditTests(unittest.TestCase):
    def test_iso_week_crosses_calendar_year(self):
        self.assertEqual(iso_week("2026-12-31"), (2026, 53))
        self.assertEqual(iso_week("2027-01-01"), (2026, 53))
        self.assertEqual(iso_week("2027-01-04"), (2027, 1))

    def test_invalid_publisher_date_rejected(self):
        with self.assertRaises(ValueError):
            iso_week("2026-02-30")

    def test_china_singapore_does_not_confuse_china_new_zealand(self):
        r, cats = lead("中新（西兰）两军举行第13次战略对话", "china")
        self.assertEqual(match_topic(r, cats, TOPICS["China–Singapore military contact"]), (False, False))

    def test_china_singapore_does_not_include_singapore_brunei(self):
        r, cats = lead("Singapore and Brunei Navies Strengthen Maritime Cooperation at Exercise Pelican")
        self.assertEqual(match_topic(r, cats, TOPICS["China–Singapore military contact"]), (False, False))

    def test_china_singapore_keeps_official_pla_navy_title(self):
        r, cats = lead("The Republic of Singapore Navy and People's Liberation Army (Navy) Commence Bilateral Maritime Exercise")
        self.assertEqual(match_topic(r, cats, TOPICS["China–Singapore military contact"]), (True, True))

    def test_china_singapore_keeps_named_maritime_cooperation(self):
        r, cats = lead("中新“海上合作-2026”联合演习开幕", "china")
        self.assertEqual(match_topic(r, cats, TOPICS["China–Singapore military contact"]), (True, True))

    def test_navals_exclude_malaysian_air_forces(self):
        r, cats = lead("Singapore and Malaysian Air Forces Successfully Concluded Annual Bilateral Search and Rescue Exercise")
        self.assertEqual(match_topic(r, cats, TOPICS["Singapore naval exercise diplomacy"]), (False, False))

    def test_navals_require_singapore_desk(self):
        r, cats = lead("Navy joins joint maritime exercise", "china")
        self.assertEqual(match_topic(r, cats, TOPICS["Singapore naval exercise diplomacy"]), (False, False))

    def test_navals_keep_rimpac(self):
        r, cats = lead("RSN Participates in Largest Edition of Multinational Naval Exercise RIMPAC 2026")
        self.assertEqual(match_topic(r, cats, TOPICS["Singapore naval exercise diplomacy"]), (True, True))

    def test_category_only_hints_not_title_corroboration(self):
        r, cats = lead("A commentary on politics and technology", "china", ["taiwan"])
        self.assertEqual(match_topic(r, cats, TOPICS["Taiwan Strait military messaging (contrast)"]), (True, False))

    def test_regional_filter_does_not_include_domestic_drill_by_default(self):
        r, cats = lead("部队开展海上演习", "china")
        self.assertEqual(match_topic(r, cats, TOPICS["Regional exercise diplomacy"]), (False, False))


if __name__ == "__main__":
    unittest.main()
