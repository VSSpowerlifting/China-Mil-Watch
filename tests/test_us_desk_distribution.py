"""Source-free delivery preflight tests, no live HTTP and no BIS promotion."""
import tempfile
import unittest
from pathlib import Path

from scripts.verify_us_desk_distribution import DistributionHold, verify


def page(*, uscc=10, treasury=10, pacom=9, bis=0):
    def rows(attr, n, host):
        return "".join(
            '<li '+attr+'="id'+str(i)+'"><a href="https://'+host+
            '/official/'+str(i)+'" target="_blank" rel="noopener noreferrer">'
            'Official '+str(i)+'</a></li>' for i in range(n))
    return ('<!DOCTYPE html><html><body><h1>U.S. Desk</h1>'+
            rows('data-uscc-official-link',uscc,'www.uscc.gov')+
            rows('data-us-treasury-official-link',treasury,'home.treasury.gov')+
            rows('data-us-pacom-link',pacom,'www.pacom.mil')+
            rows('data-us-bis-official-link',bis,'www.bis.gov')+
            '</body></html>').encode('utf-8')


class DistributionTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name)
        self.paths=[self.base/x for x in ("main.html","pages.html","http.html")]
        self.set_contents(page())

    def set_contents(self, value):
        for path in self.paths: path.write_bytes(value)

    def check(self):
        return verify(*self.paths)

    def test_existing_us_desk_parity_passes_without_bis(self):
        report=self.check()
        self.assertEqual(report["official_links"],{"uscc":10,"treasury":10,
                                                       "pacom":9,"bis":0})
        self.assertFalse(report["bis_schedule_attested"])

    def test_optional_bis_links_do_not_change_delivery_scope(self):
        self.set_contents(page(bis=2))
        self.assertEqual(self.check()["official_links"]["bis"],2)

    def test_stale_public_page_holds(self):
        self.paths[2].write_bytes(page(uscc=11))
        with self.assertRaisesRegex(DistributionHold,"public_domain_out_of_sync"):
            self.check()

    def test_stale_pages_git_holds(self):
        self.paths[1].write_bytes(page(treasury=11))
        with self.assertRaisesRegex(DistributionHold,"main_and_pages"):
            self.check()

    def test_missing_existing_source_holds(self):
        for family in ("uscc","treasury","pacom"):
            with self.subTest(family=family):
                self.set_contents(page(**{family:0}))
                with self.assertRaisesRegex(DistributionHold,"existing_us_official"):
                    self.check()

    def test_bad_official_anchor_holds(self):
        corrupted=page().replace(b'target="_blank"',b'target="_self"',1)
        self.set_contents(corrupted)
        with self.assertRaisesRegex(DistributionHold,"unsafe_or_non_official"):
            self.check()

    def test_empty_http_is_hold(self):
        self.paths[2].write_bytes(b"")
        with self.assertRaisesRegex(DistributionHold,"missing_or_unbounded"):
            self.check()


if __name__=="__main__":
    unittest.main()
