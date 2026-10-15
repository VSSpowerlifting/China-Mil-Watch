"""Chronology-only navigation; no production database, sidecar or output writes."""
import unittest
from core.brief_collection import Collection, continuity_items


def collection():
    rows = (
        {"kind": "brief", "entry": {"slug": "new-brief", "date": "2026-10-10",
         "issue": 17, "title": "New brief", "label": "Routine"}},
        {"kind": "brief", "entry": {"slug": "draft-brief", "date": "2026-10-09",
         "issue": None, "title": "Preview only", "is_review": True}},
        {"kind": "brief", "entry": {"slug": "synthetic", "date": "2026-10-08",
         "issue": None, "title": "Synthetic only", "synthetic": True}},
        {"kind": "issue", "entry": {"slug": "2026-09-20", "date": "2026-09-20",
         "issue": 14, "title": "The PLA Watch: Earlier brief", "label": "Significant",
         "rendered_locally": True}},
        {"kind": "issue", "entry": {"slug": "2026-09-13", "date": "2026-09-13",
         "issue": 13, "title": "Oldest available", "label": "",
         "rendered_locally": False, "url":
         "https://indopacificrecord.org/the-pla-watch/posts/2026-09-13.html"}},
    )
    return Collection(rows=rows, briefs=(), withheld=(), sidecars={})


class BriefContinuityTests(unittest.TestCase):
    def test_oldest_first_and_never_show_review_or_synthetic(self):
        items = continuity_items(collection(), "analysis.html")
        self.assertEqual([x["number"] for x in items], [13, 14, 17])
        self.assertFalse(any(x["slug"] in ("draft-brief", "synthetic") for x in items))
        self.assertEqual(items[1]["title"], "Earlier brief")
        self.assertEqual([x["kind"] for x in items],
                         ["unclassified", "significant", "routine"])

    def test_links_are_resolved_from_each_page_type(self):
        landing = continuity_items(collection(), "analysis.html")
        native = continuity_items(collection(), "briefs/new-brief.html", "new-brief")
        earlier = continuity_items(
            collection(), "the-pla-watch/posts/2026-09-20.html", "2026-09-20")
        self.assertEqual(landing[-1]["href"], "briefs/new-brief.html")
        self.assertEqual(native[-1]["href"], "new-brief.html")
        self.assertEqual(native[1]["href"], "../the-pla-watch/posts/2026-09-20.html")
        self.assertEqual(earlier[-1]["href"], "../../briefs/new-brief.html")
        self.assertEqual(landing[0]["href"],
                         "https://indopacificrecord.org/the-pla-watch/posts/2026-09-13.html")
        self.assertEqual([x["current"] for x in landing], [False, False, False])
        self.assertEqual([x["current"] for x in earlier], [False, True, False])
        self.assertEqual([x["current"] for x in native], [False, False, True])

    def test_no_new_classification_or_automatic_history(self):
        items = continuity_items(collection(), "analysis.html")
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["date"], "2026-09-13")
        self.assertNotIn("recurring_threads", items[0])
        self.assertNotIn("event_date", items[0])

    def test_unknown_collection_row_fails_closed(self):
        c = Collection(rows=({"kind": "other", "entry": {"slug": "bad"}},),
                       briefs=(), withheld=(), sidecars={})
        with self.assertRaisesRegex(ValueError, "unknown Brief"):
            continuity_items(c, "analysis.html")


if __name__ == "__main__":
    unittest.main()
