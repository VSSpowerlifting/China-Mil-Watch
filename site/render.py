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
`DEFAULT_SITE_MODE` below is the switch. It is `INDO_PACIFIC_RECORD`: the
launch happened on 2026-08-27 and publishing was, mechanically, changing that
one constant. Rolling back is changing it back to `LEGACY`. Nothing else in
the tree selects a mode.

Fail-closed rules, all tested
-----------------------------
  * An unrecognised mode raises. There is no silent fallback to legacy, because
    a typo that quietly published the wrong site is the whole risk here.
  * Candidate mode REQUIRES an explicit destination. It will not inherit
    the production `output/` default, and `build()` refuses to write inside
    production output regardless — two independent guards, because one of them
    is the one that fails.
  * The scheduled workflow sets nothing, so it resolves to whatever
    `DEFAULT_SITE_MODE` is — today, Indo-Pacific Record. A contract test
    asserts the workflow does not set the variable, so the default stays the
    single place a mode is chosen.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import OUTPUT_DIR, DB_PATH, SITE_ORIGIN             # noqa: E402
from core.viewmodel import (                                    # noqa: E402
    InvalidDailyRunDate, daily_run_date_from_env, normalize_daily_run_date,
)

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
DEFAULT_SITE_MODE = INDO_PACIFIC_RECORD

#: Override for local builds and CI contract tests. Deliberately absent from
#: every workflow: `tests/test_site_mode_contract.py` asserts that.
SITE_MODE_ENV = "PLA_WATCH_SITE_MODE"

#: Where the published site will live. Read from the environment so the deploy
#: workflow supplies it once, in one place, rather than every caller
#: remembering a flag.
#:
#: This exists because an optional flag that production never passes is not a
#: safety feature. `generate_preview.build()` leaves a tree `noindex` and
#: writes no sitemap unless it is given an origin — correct for a candidate,
#: catastrophic for a launch — and `render_site()` did not pass one. Flipping
#: the mode alone would therefore have published a site that tells every
#: crawler to ignore it.
SITE_ORIGIN_ENV = "PLA_WATCH_SITE_ORIGIN"

#: What the published site keeps, and what it regenerates.
#:
#: `generate_preview` is forbidden from writing into the predecessor namespace
#: at all, and it does not render the editorial imagery, the predecessor marks
#: or the existing machine-readable export. Those are published pages and cited
#: evidence; a build that simply replaced `output/` with its own tree would
#: delete thirteen editions, their sidecar records, their covers, their media
#: and the feed every subscriber holds.
#:
#: So the publish is an exchange rather than an overwrite: these entries are
#: lifted out, the rest of `output/` is replaced wholesale by the new build —
#: which keeps the build deterministic and stops a withdrawn record leaving a
#: stale page behind — and then they are put back.
CARRIED_FORWARD = (
    "the-pla-watch",       # the weekly series as published, and its evidence
    "assets",              # editorial imagery referenced by published pages
    "data",                # the existing machine-readable export
    "favicon.svg",
    "logo-icon.png",
    "logo-wordmark.png",
    "og-image.png",
    "CNAME",               # the deployed domain
    ".nojekyll",
)

#: `/signals.html` moves to `/methodology.html`: "Signals & Methodology" has no
#: separate page in the regional model because its content is the methodology.
#: The renderer does not emit this stub — it emits no legacy route outside
#: `/article/` — so the publish writes it, and without it the predecessor's own
#: page would survive at a live address under the new masthead.
MOVED_LEGACY_PAGES = {"signals.html": "methodology.html"}

#: The stub written for a moved legacy page. Deliberately not the record-page
#: redirect from `generate_preview`: that one says "this record has moved to
#: its record page", which is true of `/article/<id>.html` and false of a
#: section page. A redirect that misdescribes what it is redirecting is a small
#: lie in the one place a reader is already confused.
MOVED_PAGE_STUB = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Moved</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="%(target)s">
<meta http-equiv="refresh" content="0; url=%(target)s">
</head>
<body>
<p>This page has moved to <a href="%(target)s">%(target)s</a>.</p>
</body>
</html>
"""

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


class MissingSiteOrigin(RuntimeError):
    """A publishable mode was asked for without saying where it publishes."""


def render_site(mode: str = None, output_dir=None, db_path=None,
                environ=None, snapshot=None, site_origin=None,
                allow_test_origin=False, daily_run_date=None) -> dict:
    """
    Build the site for `mode`. Returns a small report.

    Legacy renders to `output/` by default — the current behaviour, unchanged.
    The candidate has no default destination on purpose.

    `daily_run_date` is the logical date of a daily-workflow run. This module
    is the ONE seam that turns the workflow's environment into that value: an
    explicit argument wins, otherwise `PLA_WATCH_DAILY_RUN_DATE` is read,
    otherwise there is no run context and the render keeps reading the
    persisted marker. See `core.viewmodel.daily_run_date_from_env` for why an
    unusable value stops the build instead of falling back.
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

    # Indo-Pacific Record — the published site since 2026-08-27.
    #
    # Until the launch this mode had no default destination and refused
    # `output/` outright, because a dormant candidate that could reach the
    # published tree is one typo away from replacing it. That is now the tree
    # it is supposed to write, so the destination defaults like legacy's does
    # and the refusal is gone from here. It is *not* gone from
    # `generate_preview.build()`: that guard still stands, and the publish
    # below satisfies it by building into a scratch tree and exchanging it in.
    target = Path(output_dir).resolve() if output_dir else OUTPUT_DIR.resolve()

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "generate_preview",
        Path(__file__).resolve().parent / "preview" / "generate_preview.py")
    gp = importlib.util.module_from_spec(spec)
    sys.modules["generate_preview"] = gp
    spec.loader.exec_module(gp)
    # Fail closed. In this mode the tree is publishable, so the origin is
    # required rather than optional: without one every page ships `noindex` and
    # no sitemap is written, and that failure is silent — the build succeeds and
    # the damage only appears once crawlers obey it.
    env = os.environ if environ is None else environ

    # The daily run's logical date, resolved once, here, and handed down as an
    # argument. Resolved BEFORE the corpus is read and the tree is built, so a
    # broken wire fails before any output exists rather than after.
    if daily_run_date is None:
        run_date = daily_run_date_from_env(env)
    else:
        run_date = normalize_daily_run_date(daily_run_date, "daily_run_date")

    origin = site_origin or env.get(SITE_ORIGIN_ENV) or SITE_ORIGIN
    if not origin.strip():
        raise MissingSiteOrigin(
            "%s mode needs the site origin it will be published under. Set %s "
            "(e.g. https://example-domain.org) or pass site_origin=. Without "
            "it the build would emit a site that is entirely noindex and has "
            "no sitemap." % (INDO_PACIFIC_RECORD, SITE_ORIGIN_ENV))

    # ── Which corpus, and which corpus identity ──────────────────────────
    #
    # The database is selected first, because the snapshot has to describe the
    # corpus that is actually about to be rendered — not a different one that
    # happens to be the default.
    #
    # Then the two callers are separated, and the distinction is the whole
    # point of this block:
    #
    #   snapshot omitted   the daily run. Derive the identity from the corpus
    #                      in hand and render it truthfully. Collection adds
    #                      records every morning; a daily build that refused
    #                      to describe them would stop publishing the moment
    #                      the corpus moved, which is exactly what happened
    #                      after the launch.
    #   snapshot supplied  a release build. Render exactly that declared
    #                      corpus or fail. The count, the date and the
    #                      fingerprint are checked in `build()` and none of
    #                      them is relaxed here.
    #
    # `DECLARED_SNAPSHOT` is neither of those. It is the accepted release
    # metadata for the launch — immutable, and not the daily corpus identity.
    # Defaulting to it is what made every daily render after 2026-08-27 abort
    # with `SnapshotMismatch`, and because the scheduled workflow runs the
    # offline suite before it collects, that stopped collection too.
    #
    # `is not None`, not truthiness: an empty dict is a caller saying "this
    # snapshot", and answering it with the launch pin would silently render a
    # different corpus identity than the one asked for.
    selected_db = Path(db_path) if db_path else DB_PATH
    if snapshot is not None:
        effective_snapshot = snapshot
        snapshot_source = "declared"
    else:
        # Derived once, here, and handed to the builder explicitly. `build()`
        # re-reads the database and asserts the corpus against what it is
        # given, so a corpus that changes between this line and that read is
        # caught there rather than producing a page set that describes neither
        # state.
        effective_snapshot = gp.snapshot_from_corpus(selected_db)
        snapshot_source = "derived"

    def _render(destination):
        return gp.build(destination, INDO_PACIFIC_RECORD_TITLE,
                        selected_db,
                        snapshot=effective_snapshot,
                        legacy_routes=True,
                        site_origin=origin,
                        allow_test_origin=allow_test_origin,
                        daily_run_date=run_date)

    if target == OUTPUT_DIR.resolve():
        with tempfile.TemporaryDirectory(prefix="ipr-publish-") as scratch:
            staged = Path(scratch) / "site"
            result = _render(staged)
            carried, moved, listed = publish(staged, target, gp)
        report = {"mode": INDO_PACIFIC_RECORD, "output_dir": str(target),
                  "snapshot_source": snapshot_source,
                  "daily_run_date": run_date,
                  "carried_forward": carried, "moved_legacy_pages": moved,
                  "carried_pages_listed_in_sitemap": listed}
    else:
        result = _render(target)
        report = {"mode": INDO_PACIFIC_RECORD, "output_dir": str(target),
                  "snapshot_source": snapshot_source,
                  "daily_run_date": run_date}

    if isinstance(result, dict):
        report.update(result)
    return report


def publish(staged: Path, target: Path, gp) -> tuple:
    """
    Exchange a freshly built tree into `output/`, keeping what is cited.

    The order matters and is the whole point. The carried-forward entries are
    moved aside *first*, so that if anything below fails they are still on
    disk rather than half-copied. Only then is the old tree removed and the new
    one moved into place — a replacement rather than a merge, so a record that
    has left the corpus cannot leave a stale page behind. Finally the carried
    entries go back, and the pages that moved get their redirect.

    Returns what was carried and what was redirected, so the caller can report
    it and a test can assert on it rather than on a directory listing.
    """
    staged, target = Path(staged), Path(target)
    holding = target.parent / (target.name + ".carried")
    if holding.exists():
        shutil.rmtree(holding)
    holding.mkdir(parents=True)

    carried = []
    for name in CARRIED_FORWARD:
        source = target / name
        if not source.exists():
            continue
        shutil.move(str(source), str(holding / name))
        carried.append(name)

    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(staged), str(target))

    for name in carried:
        shutil.move(str(holding / name), str(target / name))
    shutil.rmtree(holding)

    moved = []
    for page, destination in sorted(MOVED_LEGACY_PAGES.items()):
        (target / page).write_text(
            MOVED_PAGE_STUB % {"target": destination}, encoding="utf-8")
        moved.append("%s -> %s" % (page, destination))

    listed = add_carried_pages_to_sitemap(target)

    return carried, moved, listed


#: A page's own declaration of where it lives. The carried pages already carry
#: one, written by the weekly renderer against the same origin, so the sitemap
#: can be built from what the pages say rather than from a second list that
#: would have to be kept in step with them.
_CANONICAL = re.compile(r'<link rel="canonical" href="([^"]+)"')
_NOINDEX = re.compile(r'content="noindex')
_LOC = re.compile(r"<loc>([^<]+)</loc>")


def add_carried_pages_to_sitemap(target: Path) -> int:
    """
    Put the carried-forward series back into the sitemap.

    The renderer cannot do this itself: it is forbidden from the predecessor
    namespace, so it has never seen these pages and writes a sitemap without
    them. Left alone, the launch would quietly drop sixteen indexable pages —
    the weekly index, its archive, its glossary and the thirteen editions —
    from the map every crawler reads. They would still resolve, and nothing
    would report that they had stopped being advertised.

    Derived from the pages themselves: any carried page that declares a
    canonical and is not `noindex` belongs in the map, at the address it
    declares. Sorted, so a rebuild is byte-identical.
    """
    sitemap = target / "sitemap.xml"
    if not sitemap.exists():
        return 0

    existing = _LOC.findall(sitemap.read_text(encoding="utf-8"))
    found = set(existing)
    added = 0
    for page in sorted((target / "the-pla-watch").rglob("*.html")):
        html = page.read_text(encoding="utf-8", errors="replace")
        if _NOINDEX.search(html):
            continue
        match = _CANONICAL.search(html)
        if not match:
            continue
        url = match.group(1)
        if not url.startswith("http") or url in found:
            continue
        found.add(url)
        added += 1

    body = "".join("  <url>\n    <loc>%s</loc>\n  </url>\n" % url
                   for url in sorted(found))
    sitemap.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + body + "</urlset>\n", encoding="utf-8")
    return added


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument("--mode", choices=SITE_MODES, default=None,
                   help="site mode (default: %s)" % DEFAULT_SITE_MODE)
    p.add_argument("--out", default=None,
                   help="destination directory; required for %s"
                        % INDO_PACIFIC_RECORD)
    p.add_argument("--db", default=None, help="database to read (read-only)")
    p.add_argument("--site-origin", default=None,
                   help="absolute origin the site will be published under. "
                        "Required for %s; may also come from %s."
                        % (INDO_PACIFIC_RECORD, SITE_ORIGIN_ENV))
    p.add_argument("--allow-test-origin", action="store_true",
                   help="permit a reserved or placeholder origin. Test builds "
                        "only; a real publication must name a real domain.")
    args = p.parse_args(argv)
    try:
        report = render_site(args.mode, args.out, args.db,
                             site_origin=args.site_origin,
                             allow_test_origin=args.allow_test_origin)
    except (UnsupportedSiteMode, MissingSiteOrigin, InvalidDailyRunDate) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print("mode   : %s" % report["mode"])
    print("output : %s" % report["output_dir"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
