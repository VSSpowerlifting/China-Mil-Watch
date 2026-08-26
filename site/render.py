#!/usr/bin/env python3
"""
Site mode selection — the one place that decides which frontend gets built.

Why this module exists
----------------------
There are two renderers and there will be two for a while:

  * `site/generator.py`  — the live China Mil Watch site. Committed to
    `output/` and deployed by the daily workflow every day.
  * `site/preview/generate_preview.py` — the Indo-Pacific Record candidate:
    the multi-desk architecture, the regional identity, and the record
    surfaces. Tested, complete, and not public.

Merging them into one renderer today would mean rewriting the daily publishing
path days after it came back from an outage, against a corpus that ships to
production every morning. That trade is not worth taking, so the two renderers
stay separate and this module is the single seam between them. What it prevents
is the failure mode that actually matters: a mode selected implicitly, in more
than one place, by a value nobody can find.

The launch switch
-----------------
`DEFAULT_SITE_MODE` below is the switch. It is `LEGACY` today. Publishing
Indo-Pacific Record is, mechanically, changing that one constant — after the
evidence and branding gates pass, which is an owner decision and not this
module's business. Rolling back is changing it back. Nothing else in the tree
selects a mode.

Fail-closed rules, all tested
-----------------------------
  * An unrecognised mode raises. There is no silent fallback to legacy, because
    a typo that quietly published the wrong site is the whole risk here.
  * Candidate mode REQUIRES an explicit destination. It will not inherit
    the production `output/` default, and `build()` refuses to write inside
    production output regardless — two independent guards, because one of them
    is the one that fails.
  * The scheduled workflow sets nothing, so it resolves to legacy. A contract
    test asserts the workflow does not set the variable.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import OUTPUT_DIR, DB_PATH                          # noqa: E402

#: The live site. Default, and the only mode that may write to `output/`.
LEGACY = "legacy"

#: The Indo-Pacific Record candidate: the multi-desk architecture and the
#: regional identity. Not public. Renders to a disposable destination.
#:
#: Renamed from `declared-record` on 2026-08-25. "The Declared Record" was a
#: prototype codename, never adopted and never published, and keeping it as a
#: mode string would have left the retired working name in the one place a
#: build says what it is. Nothing published ever carried the old value: legacy
#: is the only mode that has ever written to `output/`.
INDO_PACIFIC_RECORD = "indo-pacific-record"

SITE_MODES = (LEGACY, INDO_PACIFIC_RECORD)

#: ── THE LAUNCH SWITCH ────────────────────────────────────────────────────
#: Change this one constant to publish Indo-Pacific Record. Change it back to
#: roll the launch back. Do not add a second way to select a mode.
DEFAULT_SITE_MODE = LEGACY

#: Override for local builds and CI contract tests. Deliberately absent from
#: every workflow: `tests/test_site_mode_contract.py` asserts that.
SITE_MODE_ENV = "PLA_WATCH_SITE_MODE"

#: Public name carried by the candidate build. Owner-directed 2026-08-25 and
#: recorded in docs/INDO_PACIFIC_RECORD_EVOLUTION.md §1. Trademark screening,
#: domain and handles are owner actions and none has been performed — none of
#: which this constant asserts, and none of which a local build requires.
INDO_PACIFIC_RECORD_TITLE = "Indo-Pacific Record"


class UnsupportedSiteMode(ValueError):
    """Raised for a mode this build does not implement. Never falls back."""


def resolve_site_mode(explicit: str = None, environ=None) -> str:
    """
    explicit argument > environment > DEFAULT_SITE_MODE.

    An unrecognised value raises rather than degrading to the default: a run
    that asked for a mode it did not get must stop, not publish something else.
    """
    environ = os.environ if environ is None else environ
    mode = explicit or environ.get(SITE_MODE_ENV) or DEFAULT_SITE_MODE
    mode = str(mode).strip().lower()
    if mode not in SITE_MODES:
        raise UnsupportedSiteMode(
            "unsupported site mode %r; supported modes are %s"
            % (mode, ", ".join(SITE_MODES)))
    return mode


def render_site(mode: str = None, output_dir=None, db_path=None,
                environ=None, snapshot=None) -> dict:
    """
    Build the site for `mode`. Returns a small report.

    Legacy renders to `output/` by default — the current behaviour, unchanged.
    The candidate has no default destination on purpose.
    """
    resolved = resolve_site_mode(mode, environ)

    if resolved == LEGACY:
        target = Path(output_dir) if output_dir else OUTPUT_DIR
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "site_generator", Path(__file__).resolve().parent / "generator.py")
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        gen.generate_site(target)
        return {"mode": LEGACY, "output_dir": str(target)}

    # Indo-Pacific Record candidate.
    if output_dir is None:
        raise UnsupportedSiteMode(
            "%s mode requires an explicit destination; it must not inherit the "
            "production output directory" % INDO_PACIFIC_RECORD)
    target = Path(output_dir).resolve()
    if target == OUTPUT_DIR.resolve() or OUTPUT_DIR.resolve() in target.parents:
        raise UnsupportedSiteMode(
            "refusing to render %s inside production output/: %s"
            % (INDO_PACIFIC_RECORD, target))

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "generate_preview",
        Path(__file__).resolve().parent / "preview" / "generate_preview.py")
    gp = importlib.util.module_from_spec(spec)
    sys.modules["generate_preview"] = gp
    spec.loader.exec_module(gp)
    result = gp.build(target, INDO_PACIFIC_RECORD_TITLE,
                      Path(db_path) if db_path else DB_PATH,
                      snapshot=snapshot or gp.DECLARED_SNAPSHOT,
                      legacy_routes=True)
    report = {"mode": INDO_PACIFIC_RECORD, "output_dir": str(target)}
    if isinstance(result, dict):
        report.update(result)
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument("--mode", choices=SITE_MODES, default=None,
                   help="site mode (default: %s)" % DEFAULT_SITE_MODE)
    p.add_argument("--out", default=None,
                   help="destination directory; required for %s"
                        % INDO_PACIFIC_RECORD)
    p.add_argument("--db", default=None, help="database to read (read-only)")
    args = p.parse_args(argv)
    try:
        report = render_site(args.mode, args.out, args.db)
    except UnsupportedSiteMode as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print("mode   : %s" % report["mode"])
    print("output : %s" % report["output_dir"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
