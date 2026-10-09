"""Contract for local-only Operations Center report writers."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import operations_center as ops
from scripts import operations_center_unified as unified


class PrivateReportWriterTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="ipr-private-reports-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.json = self.root / "private.json"
        self.html = self.root / "private.html"

    def test_single_and_pair_output_owner_only(self):
        ops.write_private_reports(((self.json, '{"mode":"private"}'),))
        self.assertEqual(self.json.read_text(), '{"mode":"private"}')
        if os.name != "nt":
            self.assertEqual(self.json.stat().st_mode & 0o077, 0)
        self.json.unlink()
        unified.write_report_pair(self.json, '{}', self.html, '<h1>Owner</h1>')
        self.assertEqual(self.html.read_text(), '<h1>Owner</h1>')
        if os.name != "nt":
            for path in (self.json, self.html):
                self.assertEqual(path.stat().st_mode & 0o077, 0)

    def test_existing_report_is_never_overwritten(self):
        self.html.write_text('existing', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            ops.write_private_reports(((self.json, '{}'), (self.html, 'new')))
        self.assertFalse(self.json.exists())
        self.assertEqual(self.html.read_text(), 'existing')

    def test_broken_second_report_rolls_back_first(self):
        original_open = os.open
        def fail_second(path, *args, **kwargs):
            if Path(path) == self.html:
                raise OSError('synthetic failure')
            return original_open(path, *args, **kwargs)
        with patch.object(ops.os, 'open', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, 'synthetic failure'):
                ops.write_private_reports(((self.json, '{}'), (self.html, 'html')))
        self.assertFalse(self.json.exists())
        self.assertFalse(self.html.exists())

    def test_fdopen_failure_rolls_back_just_created_file(self):
        with patch.object(ops.os, 'fdopen', side_effect=OSError('wrap refused')):
            with self.assertRaisesRegex(OSError, 'wrap refused'):
                ops.write_private_reports(((self.json, '{}'),))
        self.assertFalse(self.json.exists())

    def test_unicode_encoding_failure_cleans_pair(self):
        with self.assertRaises(UnicodeEncodeError):
            ops.write_private_reports(((self.json, '{}'),
                                      (self.html, 'bad surrogate \ud800')))
        self.assertFalse(self.json.exists())
        self.assertFalse(self.html.exists())

    def test_replaced_own_file_is_not_removed_by_rollback(self):
        replacement = self.root / 'replacement'
        replacement.write_text('do not delete', encoding='utf-8')
        original_open = os.open
        def swap_then_fail(path, *args, **kwargs):
            if Path(path) == self.html:
                self.json.unlink()
                os.link(replacement, self.json)
                raise OSError('after replacement')
            return original_open(path, *args, **kwargs)
        with patch.object(ops.os, 'open', side_effect=swap_then_fail):
            with self.assertRaisesRegex(OSError, 'after replacement'):
                ops.write_private_reports(((self.json, '{}'), (self.html, 'html')))
        self.assertEqual(self.json.read_text(), 'do not delete')
        self.assertTrue(replacement.exists())

    def test_symlink_target_is_never_overwritten(self):
        original = self.root / 'original'
        original.write_text('preserved', encoding='utf-8')
        self.json.symlink_to(original)
        with self.assertRaises(FileExistsError):
            ops.write_private_reports(((self.json, '{}'),))
        self.assertEqual(original.read_text(), 'preserved')
        self.assertTrue(self.json.is_symlink())


if __name__ == '__main__':
    unittest.main()
