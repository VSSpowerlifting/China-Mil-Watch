"""No LLM credits spent on absent original prose. Offline; no real DB or API."""
from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import pipeline


def item(i, body="Document text"):
    return (i, "Publisher title", body, "https://example.org/%d" % i)


class NoBlankBodyDispatchTests(unittest.TestCase):
    def test_valid_original_body_is_kept_byte_for_byte(self):
        originals = [item(1, " 中文 \n English "), item(2, "P"),
                     item(3, "\nGovernment statement\n\nDetails\n")]
        with patch("pipeline.db", autospec=False) as db:
            ready, withheld = pipeline.hold_blank_original_bodies(originals)
            db.assert_not_called() if callable(db) else None
        self.assertEqual(ready, originals)
        self.assertEqual(withheld, 0)
        self.assertIsNot(ready, originals)
        self.assertIs(ready[0], originals[0])
        self.assertIs(ready[1], originals[1])

    def test_blank_string_and_unicode_space_are_withheld(self):
        original = [item(1, ""), item(2, " \t\n\r"), item(3, " \u3000 "),
                    item(4, "actual prose")]
        ready, withheld = pipeline.hold_blank_original_bodies(original)
        self.assertEqual([x[0] for x in ready], [4])
        self.assertEqual(withheld, 3)
        self.assertEqual(len(original), 4, "input candidate list was mutated")

    def test_missing_or_nonstring_body_refused_without_coercion(self):
        originals = [item(1, None), item(2, 123), item(3, False),
                     item(4, ["not actually stored as prose"]),
                     item(5, {"text": "not string"}), item(6, b"raw bytes"),
                     item(7, "Actual text")]
        ready, withheld = pipeline.hold_blank_original_bodies(originals)
        self.assertEqual(withheld, 6)
        self.assertEqual([a[0] for a in ready], [7])

    def test_all_invalid_inputs_leave_an_empty_dispatch(self):
        new, count = pipeline.hold_blank_original_bodies(
            [item(1, ""), item(2, None)])
        self.assertEqual(new, [])
        self.assertEqual(count, 2)

    def test_no_reassignment_or_fake_analysis_status(self):
        original = [item(1, ""), item(2, "Body"), item(3, " ")]
        after, withheld = pipeline.hold_blank_original_bodies(original)
        self.assertEqual(withheld, 2)
        self.assertEqual(after, [original[1]])
        # Only a new candidate list is produced. No row status, content
        # verdict, retry budget, database query or record update is touched.
        self.assertEqual(original[0][2], "")
        self.assertEqual(original[2][2], " ")
        self.assertEqual(len(original), 3)

    def test_pure_filter_never_instantiates_analyzer(self):
        with patch("analysis.analyzer.Analyzer", side_effect=AssertionError(
                "no model may be instantiated")):
            ready, held = pipeline.hold_blank_original_bodies(
                [item(1, ""), item(2, "Real body")])
        self.assertEqual(held, 1)
        self.assertEqual(len(ready), 1)

    def test_new_pending_and_unscored_sources_all_filtered_before_cap(self):
        new = [item(1, ""), item(2, "Fresh prose"), item(3, "")]
        pending = [item(4, None), item(5, "Prior relevance pass")]
        unscored = [item(6, "  "), item(7, "Older article")]
        ready_new, hn = pipeline.hold_blank_original_bodies(new)
        ready_pending, hp = pipeline.hold_blank_original_bodies(pending)
        ready_unscored, hu = pipeline.hold_blank_original_bodies(unscored)
        self.assertEqual((hn, hp, hu), (2, 1, 1))
        self.assertEqual([x[0] for x in ready_new], [2])
        self.assertEqual([x[0] for x in ready_pending], [5])
        self.assertEqual([x[0] for x in ready_unscored], [7])
        self.assertEqual(len(ready_new + ready_pending + ready_unscored), 3)

    def test_no_blank_consumes_reserve_slots(self):
        new = [item(i, "" if i in (1, 2) else "new prose")
               for i in range(1, 43)]
        back = [item(i, "" if i in (100, 101, 102) else "backlog prose")
                for i in range(100, 142)]
        ready_new, held_new = pipeline.hold_blank_original_bodies(new)
        ready_back, held_back = pipeline.hold_blank_original_bodies(back)
        self.assertEqual((held_new, held_back), (2, 3))
        cap, reserve = 55, 0.3
        backlog_slots = min(len(ready_back), max(1, round(cap * reserve)))
        new_take = ready_new[:cap-backlog_slots]
        backlog_take = ready_back[:cap-len(new_take)]
        selected = new_take + backlog_take
        self.assertEqual(len(selected), 55)
        self.assertEqual(len(new_take), 39)
        self.assertEqual(len(backlog_take), 16)
        self.assertTrue(all(a[2].strip() for a in selected))

    def test_all_three_lanes_are_guarded_before_cost_selection(self):
        source = inspect.getsource(pipeline.run)
        selection = source.index("backlog_slots = 0")
        self.assertLess(
            source.index("new_queue, blank_new = hold_blank_original_bodies(new_queue)"),
            selection)
        self.assertLess(
            source.index("pending, blank_pending = hold_blank_original_bodies(pending)"),
            selection)
        self.assertLess(
            source.index("unscored, blank_unscored = hold_blank_original_bodies(unscored)"),
            selection)
        self.assertIn("Rows and processing states were not changed", source)

    def test_new_source_documents_remain_in_database_insert_path(self):
        source = inspect.getsource(pipeline.run)
        self.assertLess(
            source.index("db.insert_article(article, run_id)"),
            source.index("hold_blank_original_bodies(new_queue)"))
        self.assertIn("inserted_ids = {aid for aid, _ in inserted}", source)
        self.assertIn("if r[\"id\"] not in queued_ids", source)

    def test_no_new_terminal_content_verdict_or_retry_reset(self):
        source = inspect.getsource(pipeline.hold_blank_original_bodies)
        self.assertNotIn("record_processing_failure", source)
        self.assertNotIn("resume_paused_article", source)
        self.assertNotIn("processing_state.classify(", source)
        self.assertNotIn("update_analysis", source)
        self.assertNotIn("update_relevance", source)


if __name__ == "__main__":
    unittest.main()
