"""Synthetic negatives for real frozen-HWPX/HTML evidence adapter."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import korea_archived_kogl_replay as replay


URL = "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784297"
IDENTITY = "korea-policy:156784297"
COMMIT = "1" * 40
HTML_MARKUP = (
    '<!doctype html><html><head><link rel="canonical" href="' + URL
    + '"></head><body><div class="kogl_wrap"><div class="kogl">'
    + '<div class="guide"><div class="type"><a href="https://www.kogl.or.kr/info/license.do">'
    + '<img src="/images/v5/common/open_type_01.png" '
    + 'alt="공공누리 공공저작물 자유이용허락 1유형 출처표시"></a>'
    + '<span>이 자료는 <strong>텍스트에 한하여 공공누리 제1유형(출처표시)의 조건'
    + '</strong>에 따라 이용할 수 있습니다.</span></div>'
    + '<div class="info"><p>단, 텍스트를 제외한 사진·이미지·일러스트·동영상 등 자료는 '
    + '이용 전 해당 저작권자의 허락을 반드시 받으셔야 합니다.</p></div>'
    + '</div></div></div></body></html>'
)


def sha(value):
    return hashlib.sha256(value).hexdigest()


class KoreaArchivedMarkTests(unittest.TestCase):
    def test_exact_article_specific_type1_text_only_mark(self):
        result = replay.inspect_captured_mark(HTML_MARKUP.encode(), URL)
        self.assertEqual(result["mark"], "KOGL_TYPE_1_TEXT")
        self.assertEqual(result["scope"], "original_text_only")
        self.assertFalse(result["whole_hwpx_licensed"])
        self.assertFalse(result["media_licensed"])

    def test_wrong_publisher_page_cannot_transfer_its_license(self):
        with self.assertRaisesRegex(replay.MarkHold, "captured_publisher_article_identity_mismatch"):
            replay.inspect_captured_mark(HTML_MARKUP.encode(), URL + "9")

    def test_missing_exact_text_scope_fails(self):
        changed = HTML_MARKUP.replace("텍스트에 한하여 공공누리 제1유형", "공공누리 제2유형")
        with self.assertRaisesRegex(replay.MarkHold, "article_not_marked_kogl_type1_text_only"):
            replay.inspect_captured_mark(changed.encode(), URL)

    def test_marker_elsewhere_outside_article_scope_fails(self):
        changed = HTML_MARKUP.replace("텍스트에 한하여 공공누리 제1유형", "외부고지")
        changed += "<p>텍스트에 한하여 공공누리 제1유형</p>"
        with self.assertRaisesRegex(replay.MarkHold, "article_not_marked_kogl_type1_text_only"):
            replay.inspect_captured_mark(changed.encode(), URL)

    def test_missing_media_exception_notice_fails(self):
        changed = HTML_MARKUP.replace("사진·이미지·일러스트·동영상", "사진")
        with self.assertRaisesRegex(replay.MarkHold, "nontext_third_party_exception_notice_missing"):
            replay.inspect_captured_mark(changed.encode(), URL)

    def test_badge_type_conflict_fails(self):
        changed = HTML_MARKUP.replace("open_type_01.png", "open_type_02.png")
        with self.assertRaisesRegex(replay.MarkHold, "article_license_badge_conflicts_with_text"):
            replay.inspect_captured_mark(changed.encode(), URL)

    def test_duplicate_article_license_blocks(self):
        changed = HTML_MARKUP.replace("</body>", '<div class="kogl_wrap"></div></body>')
        with self.assertRaisesRegex(replay.MarkHold, "article_specific_license_wrapper_missing"):
            replay.inspect_captured_mark(changed.encode(), URL)

    def test_invalid_encoding_fails_closed(self):
        with self.assertRaisesRegex(replay.MarkHold, "publisher_html_not_utf8"):
            replay.inspect_captured_mark(b"\xff" + HTML_MARKUP.encode(), URL)

    def test_oversize_html_fails_closed(self):
        with self.assertRaisesRegex(replay.MarkHold, "publisher_html_capture_missing_or_oversize"):
            replay.inspect_captured_mark(b"x" * (replay.MAX_HTML + 1), URL)


class KoreaAuthenticatedSourceCallbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        (self.folder / "state" / "captures").mkdir(parents=True)
        self.html_bytes = HTML_MARKUP.encode()
        self.html_sha = sha(self.html_bytes)
        self.capture_file = (self.folder / "state" / "captures"
                             / (self.html_sha + ".bin"))
        self.capture_file.write_bytes(self.html_bytes)
        self.body = "국방부 자료: 훈련 예정. " * 12
        self.title = "국방부 공식 발표"
        self.row = {
            "source_identity": IDENTITY,
            "canonical_source_url": URL,
            "publisher_html_sha256": self.html_sha,
            "original_text_sha256": sha(self.body.encode()),
            "original_title_sha256": sha(self.title.encode()),
            "candidate_version_sha256": "a" * 64,
            "publisher_posted_date": "2026-10-15",
            "editorial_exception": None,
        }
        self.original = {
            "source_identity": IDENTITY, "text_original": self.body,
            "title_original": self.title, "capture_sha256": self.html_sha,
        }
        self.packet = {
            "source_git_commit": COMMIT,
            "records": [self.row],
        }
        self.stage_build = patch.object(replay.stage, "build",
                                        side_effect=lambda checkout: self.packet)
        self.stage_rows = patch.object(replay.stage, "_rows",
                                       side_effect=lambda checkout: [self.original])
        self.stage_build.start()
        self.stage_rows.start()
        self.addCleanup(self.stage_build.stop)
        self.addCleanup(self.stage_rows.stop)

    def test_trusted_source_and_license_callbacks_agree_on_exact_source(self):
        adapter = replay.KoreaArchivedMarkAdapter(self.folder, IDENTITY)
        source = adapter.source
        self.assertEqual(source["source_git_commit"], COMMIT)
        proof = adapter.source_replay(source)
        self.assertEqual(proof["entire_clean_original_text_sha256"],
                         sha(self.body.encode()))
        self.assertTrue(adapter.item_license_replay(source, "KOGL_TYPE_1_TEXT"))
        self.assertEqual(adapter.read_original_text_private(), self.body.encode())
        self.assertNotIn("text_original", source)
        self.assertNotIn("publisher_html", source)
        self.assertFalse(hasattr(adapter, "policy_replay"))
        self.assertFalse(hasattr(adapter, "exception_replay"))

    def test_source_identity_mutation_refuses_callback(self):
        adapter = replay.KoreaArchivedMarkAdapter(self.folder, IDENTITY)
        changed = dict(adapter.source, source_git_commit="2" * 40)
        with self.assertRaisesRegex(replay.MarkHold, "source_callback_identity_mismatch"):
            adapter.source_replay(changed)

    def test_capture_tampering_refuses_fresh_replay(self):
        adapter = replay.KoreaArchivedMarkAdapter(self.folder, IDENTITY)
        self.capture_file.write_bytes(b"tampered")
        with self.assertRaisesRegex(replay.MarkHold, "publisher_html_capture_hash_mismatch"):
            adapter.source_replay(adapter.source)

    def test_moving_source_git_refuses_fresh_replay(self):
        adapter = replay.KoreaArchivedMarkAdapter(self.folder, IDENTITY)
        self.packet["source_git_commit"] = "2" * 40
        with self.assertRaisesRegex(replay.MarkHold, "original_git_capture_changed"):
            adapter.source_replay(adapter.source)

    def test_editorial_exception_cannot_be_auto_qualified(self):
        self.row["editorial_exception"] = "unresolved_factual_conflict"
        with self.assertRaisesRegex(replay.MarkHold, "source_has_unresolved_editorial_exception"):
            replay.KoreaArchivedMarkAdapter(self.folder, IDENTITY)

    def test_read_only_archive_receipt_hides_original_bytes(self):
        result = replay.verify_archive(self.folder)
        self.assertEqual(result["source_original_count"], 1)
        self.assertEqual(result["text_only_type1_marks_verified"], 1)
        self.assertEqual(result["public_files_written"], 0)
        self.assertEqual(result["production_records_written"], 0)
        self.assertNotIn(self.body, repr(result))


if __name__ == "__main__":
    unittest.main()
