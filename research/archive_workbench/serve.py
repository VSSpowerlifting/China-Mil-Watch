"""Loopback-only private preview with noindex, restrictive CSP and no cache."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
from urllib.parse import unquote, urlsplit

from .build import DEFAULT

CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; "
       "connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


class PrivateHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('X-Robots-Tag', 'noindex, nofollow, noarchive')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', CSP)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        super().end_headers()

    def send_head(self):
        host = self.headers.get('Host', '').split(':')[0]
        if host not in ('localhost', '127.0.0.1'):
            self.send_error(403)
            return None
        parts = Path(unquote(urlsplit(self.path).path)).parts
        requested = Path(self.translate_path(self.path))
        if (any(p.startswith('.') for p in parts) or requested.is_symlink()
                or Path(self.directory).resolve() not in requested.resolve().parents
                and requested.resolve() != Path(self.directory).resolve()):
            self.send_error(403)
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(403)
        return None


def server(path=DEFAULT, port=8876):
    path = Path(path).resolve()
    if not (path / '.ipr-private-preview').is_file():
        raise ValueError('not_an_archive_workbench_private_preview')
    return ThreadingHTTPServer(('127.0.0.1', port), partial(PrivateHandler, directory=str(path)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dir', type=Path, default=DEFAULT)
    parser.add_argument('--port', type=int, default=8876)
    args = parser.parse_args()
    with server(args.dir, args.port) as httpd:
        print('Private preview: http://127.0.0.1:%d' % httpd.server_port, flush=True)
        httpd.serve_forever()
