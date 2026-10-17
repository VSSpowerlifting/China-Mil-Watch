#!/usr/bin/env python3
"""Rebuild the committed vanilla Archive bundle (development only).

Uses pinned Terser 5.44.0; no Node toolchain or package is needed by the site
renderer. Readable query/export and controller sources remain authoritative.
`--check` verifies exact output and the raw per-page JS budget including shell.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'site/preview'


def bundle():
    engine = (SOURCE / 'archive-search.js').read_text()
    body = engine[engine.index("  const SCHEMA"):engine.index('  const api =')]
    controller = (SOURCE / 'browse.source.js').read_text()
    controller = controller[controller.index(' const $'):controller.rindex('})();')]
    controller = controller.replace('error = $("research-error"), E = ArchiveSearch,', 'error = $("research-error"),')
    # Fuse the pure helpers and controller in one lexical scope: unused CLI
    # helpers disappear, without changing readable source or runtime behavior.
    body = body.replace('function selected(', 'function exportRecords(').replace('selected(records, ids)', 'exportRecords(records, ids)')
    for name in ('prepare', 'search', 'csv', 'SCHEMA'):
        controller = controller.replace('E.' + name, name)
    controller = controller.replace('E.selected', 'exportRecords')
    script = '(function(){"use strict";' + body + controller + '})();'
    with tempfile.TemporaryDirectory(prefix='ipr-archive-js-') as directory:
        path = Path(directory) / 'source.js'
        path.write_text(script)
        return subprocess.check_output(['npx', '--yes', 'terser@5.44.0', str(path),
            '--compress', 'passes=3', '--mangle'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = bundle()
    target = SOURCE / 'browse.js'
    if args.check:
        if result != target.read_bytes():
            raise SystemExit('browse.js differs; run scripts/build_archive_js.py')
    else:
        target.write_bytes(result)
    total = len(result) + (SOURCE / 'shell.js').stat().st_size
    print('Archive JS: %d raw bytes, including shell.js (10,000-byte ceiling)' % total)
    if total > 10000 or len(result) > 9500:
        raise SystemExit('Archive JavaScript budget exceeded')


if __name__ == '__main__':
    main()
