"""Offline eight-desk Git parity contract tests, without network or Git writes."""
import hashlib
import unittest
from unittest.mock import patch

from scripts import verify_eight_desk_pages_parity as parity

MAIN = "a" * 40
PAGES = "b" * 40


def html(route):
    return ('<!DOCTYPE html>\n<html data-route="%s"><head><title>Desk</title>'
            '</head><body><main><p>%s</p></main></body></html>\n' %
            (route, "official" * 20)).encode()


class ParityContracts(unittest.TestCase):
    def setUp(self):
        self.pages = {route: html(route) for route in parity.ROUTES}

    def fake_git(self, repo, *args):
        if args[:2] == ("cat-file", "-t"):
            return b"commit\n"
        if args[0] == "ls-tree":
            path = args[-1]
            route = path.rsplit("/", 1)[-1]
            if route not in self.pages:
                return b""
            blob = hashlib.sha1(route.encode()).hexdigest()
            return ("100644 blob %s\t%s\n" % (blob, path)).encode()
        if args[:2] == ("cat-file", "-s"):
            return str(len(self.blob(args[2]))).encode()
        if args[:2] == ("cat-file", "blob"):
            return self.blob(args[2])
        raise AssertionError(args)

    def blob(self, blob_sha):
        for route, data in self.pages.items():
            if hashlib.sha1(route.encode()).hexdigest() == blob_sha:
                return data
        raise AssertionError(blob_sha)

    def test_all_eight_pages_match(self):
        with patch.object(parity, "git", self.fake_git):
            result = parity.verify(".", MAIN, PAGES)
        self.assertEqual(result["desk_pages_verified"], 8)
        self.assertFalse(result["public_https_verified"])
        self.assertFalse(result["collector_history_verified"])

    def test_missing_route_fails_closed(self):
        self.pages.pop("japan.html")
        with patch.object(parity, "git", self.fake_git):
            with self.assertRaisesRegex(parity.ParityHold, "missing_or_nonregular_page"):
                parity.verify(".", MAIN, PAGES)

    def test_truncated_html_fails_closed(self):
        self.pages["korea.html"] = b"<html>broken</html>"
        with patch.object(parity, "git", self.fake_git):
            with self.assertRaisesRegex(parity.ParityHold, "unbounded_page"):
                parity.verify(".", MAIN, PAGES)

    def test_wrong_route_identity_fails_closed(self):
        self.pages["china.html"] = html("indonesia.html")
        with patch.object(parity, "git", self.fake_git):
            with self.assertRaisesRegex(parity.ParityHold, "unrecognized_desk_html"):
                parity.verify(".", MAIN, PAGES)

    def test_untrusted_commit_fails_closed(self):
        with self.assertRaisesRegex(parity.ParityHold, "invalid_commit_sha"):
            parity.verify(".", "main", PAGES)


if __name__ == "__main__":
    unittest.main()
