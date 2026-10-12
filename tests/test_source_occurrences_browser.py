"""Mandatory real Chromium verification of a fictional metadata-only local reader."""
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.source_occurrences import build_batch
from scripts.source_occurrences_view import make_server
from storage.source_occurrences import commit_batch, initialize, private_path
from tests.test_source_occurrences import BODY, EXTRA, SUMMARY, TITLE, document, native_row


class PrivateReaderBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='ipr-occurrence-browser-')
        cls.root=Path(cls.tmp.name).resolve()
        cls.ledger=cls.root/'ledger.db'; initialize(cls.ledger)
        docs=[document(),document(url='https://example.test/b',text='Fictional different body',date='2026-10-11'),
              document(url='https://example.test/c',title='',text=None,date=None)]
        rows=[native_row(i+1,d) for i,d in enumerate(docs)]
        for mode in ['archive_inventory','observed_replay']:
            batch=build_batch(mode,'fictional-browser-'+mode,'a'*64,rows,[],docs)
            commit_batch(cls.ledger,batch)
        cls.server=make_server(cls.ledger)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()
        cls.url='http://127.0.0.1:%d/'%cls.server.server_port
        cls.pw=sync_playwright().start()
        # A missing/failing browser is a failed required gate, not SkipTest.
        cls.browser=cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(5); cls.tmp.cleanup()

    def test_viewports_nojs_reduced_motion_network_console_keyboard_and_filters(self):
        receipts=[]
        for width in [375,1280]:
            for nojs in [False,True]:
                for reduced in [False,True]:
                    with self.subTest(width=width,nojs=nojs,reduced=reduced):
                        context=self.browser.new_context(viewport={'width':width,'height':900},
                            java_script_enabled=not nojs,reduced_motion='reduce' if reduced else 'no-preference')
                        page=context.new_page(); requests=[]; errors=[]
                        page.on('request',lambda r:requests.append(r.url))
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
                        response=page.goto(self.url,wait_until='networkidle')
                        self.assertEqual(response.status,200)
                        self.assertIn("default-src 'none'",response.headers['content-security-policy'])
                        self.assertEqual(page.locator('h1').inner_text(),'Deduplication provenance workbench')
                        self.assertEqual(page.locator('script, iframe, img').count(),0)
                        text=page.locator('body').inner_text()
                        for secret in [TITLE,BODY,SUMMARY,EXTRA]: self.assertNotIn(secret,text)
                        self.assertIn('Archive inventory',text); self.assertIn('Observed replay',text)
                        self.assertIn('Differing publication dates',text)
                        self.assertIn('Differing extracted versions; unresolved',text)
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
                        page.keyboard.press('Tab')
                        self.assertEqual(page.locator(':focus').inner_text(),'Skip to results')
                        self.assertNotEqual(page.locator(':focus').evaluate('(e)=>getComputedStyle(e).outlineStyle'),'none')
                        page.keyboard.press('Enter')
                        self.assertEqual(page.locator(':focus').get_attribute('id'),'results')
                        details=page.locator('details').first
                        details.locator('summary').focus(); page.keyboard.press('Enter')
                        self.assertTrue(details.evaluate('(e)=>e.open'))
                        page.keyboard.press('Enter'); self.assertFalse(details.evaluate('(e)=>e.open'))
                        # Native HTML GET filtering works with JavaScript disabled.
                        page.locator('#mode').select_option('observed_replay')
                        page.locator('#source').select_option('unknown')
                        page.locator('#from').fill('2026-10-11'); page.locator('#to').fill('2026-10-11')
                        page.get_by_role('button',name='Apply filters').click()
                        page.wait_for_load_state('networkidle')
                        self.assertNotIn('Archive inventory · existing_archive_row',page.locator('body').inner_text())
                        self.assertEqual(page.locator('article[id^="observation-"]').count(),1)
                        page.get_by_role('link',name='Reset filters').click(); page.wait_for_load_state('networkidle')
                        self.assertEqual(page.locator('#from').input_value(),'')
                        self.assertEqual(page.locator('#mode').input_value(),'')
                        group=page.get_by_role('link',name='Title group',exact=False).first
                        stable=group.get_attribute('href'); group.click(); page.wait_for_load_state('networkidle')
                        self.assertEqual(page.locator('.group').count(),1)
                        self.assertEqual(page.locator('.group a').get_attribute('href'),stable)
                        page.locator('article h3 a').first.click()
                        page.wait_for_load_state('networkidle')
                        self.assertEqual(page.locator('article[id^="observation-"]').count(),1)
                        page.get_by_role('link',name='Record 1',exact=True).first.click()
                        page.wait_for_load_state('networkidle')
                        self.assertEqual(page.locator('#native-1').count(),1)
                        page.get_by_role('link',name='Reset filters').click()
                        page.locator('#mode').select_option('archive_inventory')
                        page.locator('#source').select_option('unknown')
                        page.locator('#from').fill('2026-10-11')
                        page.locator('#to').fill('2026-10-11')
                        page.get_by_role('button',name='Apply filters').click()
                        page.get_by_role('link',name='Show all observations',exact=True).click()
                        page.wait_for_load_state('networkidle')
                        self.assertEqual(page.locator('article[id^="observation-"]').count(),1)
                        self.assertEqual(page.locator('#source').input_value(),'unknown')
                        self.assertEqual(page.locator('#from').input_value(),'2026-10-11')
                        page.locator('#from').fill('2026-10-10')
                        page.get_by_role('button',name='Apply filters').click()
                        page.wait_for_load_state('networkidle')
                        self.assertEqual(page.locator('article[id^="observation-"]').count(),2)
                        self.assertEqual(page.locator('input[name="show"]').get_attribute('value'),'all')
                        self.assertTrue(all(u.startswith(self.url) for u in requests),requests)
                        self.assertEqual(errors,[])
                        receipts.append(dict(width=width,no_js=nojs,reduced_motion=reduced,
                                             console_errors=0,unexpected_requests=0))
                        if nojs and reduced:
                            directory=os.environ.get('IPR_SYNTHETIC_BROWSER_EVIDENCE')
                            if directory:
                                target=private_path(Path(directory)/('synthetic-%d.png'%width))
                                fd=os.open(str(target),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                                with os.fdopen(fd,'wb') as f: f.write(page.screenshot(full_page=True))
                        context.close()
        print('IPR synthetic browser receipt: '+json.dumps(receipts,sort_keys=True))
