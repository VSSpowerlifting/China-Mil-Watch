#!/usr/bin/env python3
"""Render the selected identity's 1200x630 share card with local assets only.

Requires Playwright/Chromium. Source artwork and licensed faces remain unchanged.
"""
import hashlib
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'site/assets'


def build():
    serif = (ASSETS / 'fonts/instrument-serif-1.woff2').as_uri()
    sans = (ASSETS / 'fonts/inter-0.woff2').as_uri()
    logo = (ASSETS / 'identity/selected-ipr/ipr-navy-640.png').as_uri()
    source = '''<!doctype html><html><head><style>
@font-face{font-family:Display;src:url('%s')}@font-face{font-family:UI;src:url('%s')}
*{box-sizing:border-box}body{margin:0;width:1200px;height:630px;background:#F3F2EC;color:#1D2D31;padding:80px;font-family:UI}
main{display:flex;align-items:center;gap:65px;margin-top:70px}img{width:220px;height:auto}h1{font:400 90px/1 Display;margin:0;letter-spacing:-1px}
p{font:24px/1.5 UI;margin:45px 0 0;border-top:1px solid #CDD5CF;padding-top:25px;max-width:900px}
</style></head><body><main><img src="%s" alt=""><h1>Indo-Pacific<br>Record</h1></main><p>Official defense and security texts, preserved as published<br>and analyzed in context.</p></body></html>''' % (serif, sans, logo)
    # A file origin permits local assets; no external font/image request.
    temporary = ASSETS / 'frontend/social-card-source.html'
    temporary.write_text(source)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={'width':1200, 'height':630}, device_scale_factor=1)
            page.goto(temporary.as_uri());page.evaluate('document.fonts.ready')
            page.screenshot(path=str(ASSETS / 'frontend/ipr-social-card-1200x630.png'))
            browser.close()
        receipt_path = ASSETS / 'frontend/SOCIAL_CARD.json'
        target = ASSETS / 'frontend/ipr-social-card-1200x630.png'
        receipt_path.write_text(json.dumps({'builder': 'scripts/build_frontend_social_card.py',
            'file': target.name, 'width': 1200, 'height': 630,
            'bytes': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'logo_sha256': hashlib.sha256((ASSETS / 'identity/selected-ipr/ipr-navy-640.png').read_bytes()).hexdigest()}, indent=2) + '\n')
    finally:
        temporary.unlink()


if __name__ == '__main__': build()
