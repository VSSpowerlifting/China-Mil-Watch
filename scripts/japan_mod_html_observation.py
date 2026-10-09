#!/usr/bin/env python3
"""EXPLICIT manual fetch of two exact MOD HTML pages, hash-only private output.

Makes two HTTPS GETs ONLY if --fetch-live is provided. The raw response is
processed in memory and never stored. No model, site publication, email,
rights or archival-original certification.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.brief_editorial_evidence import load_editorial_evidence  # noqa: E402
from core.japan_mod_html_observation import (  # noqa: E402
    MAX_BYTES, MODObservationError, TARGETS, summarize,
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def read_official_html(ident):
    """Network access is manually opt-in; hosts and paths are FIXED."""
    if ident not in TARGETS:
        raise MODObservationError("untrusted MOD HTML identity")
    url = TARGETS[ident][0]
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Indo-Pacific-Record/1.0 (manual source review)",
                 "Accept": "text/html",
                 "Accept-Encoding": "identity",
                 "Cache-Control": "no-cache"},
        method="GET")
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=18) as response:
            if response.status != 200:
                raise MODObservationError("official publisher returned non-200")
            final_url = response.geturl()
            if final_url != url:
                raise MODObservationError("official publisher URL redirected")
            encoding = response.headers.get("Content-Encoding", "identity")
            if encoding.lower() != "identity":
                raise MODObservationError("compressed/encoded HTML not accepted")
            content_type = response.headers.get("Content-Type", "")
            payload = response.read(MAX_BYTES + 1)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise MODObservationError("official publisher fetch failed or redirected") from exc
    if len(payload) > MAX_BYTES:
        raise MODObservationError("MOD page exceeds bounded source-observation budget")
    return {"payload": payload, "fetched_url": final_url,
            "content_type": content_type}


def write_private(path, result):
    dest = Path(path).expanduser()
    root = ROOT.resolve()
    absolute = dest.resolve()
    if (dest.exists() or dest.is_symlink() or
            absolute == root or root in absolute.parents or
            not absolute.parent.is_dir() or dest.parent.is_symlink()):
        raise ValueError("private metadata receipt must be new and outside repository")
    flags = os.O_CREAT | os.O_WRONLY | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(absolute), flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(result, output, ensure_ascii=False, sort_keys=True,
                      indent=2, allow_nan=False)
            output.write("\n")
    except BaseException:
        absolute.unlink(missing_ok=True)
        raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fetch-live", action="store_true", required=True,
                   help="EXPLICITLY authorize two official MOD webpage GETs")
    p.add_argument("--research-directory", type=Path,
                   default=ROOT / "research/briefs_editorial_evidence")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        sources = load_editorial_evidence(
            "2026-10-10", "2026-10-10", directory=args.research_directory)
        # Scope validated before any URL fetch; never fetch arbitrary packet links.
        from core.japan_mod_html_observation import attest_packet_scope
        attest_packet_scope(sources)
        received = {ident: read_official_html(ident) for ident in sorted(TARGETS)}
        report = summarize(sources, received)
        write_private(args.out, report)
    except (OSError, ValueError, UnicodeError) as exc:
        p.error(str(exc))
    print("Two bounded MOD official HTML observations, no bodies retained.")
    print("Visible title/date signals: %d of 2." %
          report["expected_visible_title_and_date_count"])
    print("Historical original body proof FALSE; AI/email/publication rights FALSE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
