#!/usr/bin/env python3
"""Collect one bounded ministry family into its own external shadow state.

The dispatch-only ministry workflow may invoke this after owner activation.
This runner writes no remote; no source inherits another source's clock.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection.vietnam_sources import SOURCES
from core.shadow_schedule import SOURCE_EXPLICIT
from scraper.sources.vn_ministries import VNMinistryAdapter
from scripts.shadow_collect_vietnam import assert_isolated, assert_source_state, host_gate, run

MANIFEST = REPO_ROOT / "shadow/vietnam_ministries/manifest.json"


def load_source(slug):
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data["desk"]["desk_id"] != "vietnam" or data.get("_shadow") is not True:
        raise ValueError("not a Vietnam shadow manifest")
    matches = [s for s in data["sources"] if s["slug"] == slug]
    if slug not in SOURCES or len(matches) != 1:
        raise ValueError("unknown or ambiguous ministry source")
    return SimpleNamespace(**matches[0])


def collect(state_dir, slug, target, lookback=6, cap=40, run_id="local", commit="unknown",
            adapter=None, gate_dir=None, target_source=SOURCE_EXPLICIT):
    state_dir = Path(state_dir)
    assert_isolated(state_dir)
    source = load_source(slug)
    assert_source_state(state_dir, slug)
    if source.enabled is True and adapter is None:
        adapter = VNMinistryAdapter(source, max_requests=cap + 2,
                                    gate=host_gate(state_dir, gate_dir))
    if adapter is not None and adapter.slug != slug:
        raise ValueError("adapter belongs to another source")
    return run(state_dir, target, lookback, cap, run_id, commit, adapter=adapter,
               source=source, content_hash_rule=SOURCES[slug].hash_rule,
               target_source=target_source)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", choices=sorted(SOURCES), required=True)
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--target-date", type=date.fromisoformat, required=True)
    ap.add_argument("--lookback-days", type=int, default=6)
    ap.add_argument("--cap", type=int, default=40)
    ap.add_argument("--run-id", default="local")
    ap.add_argument("--commit", default="unknown")
    ap.add_argument("--gate-dir", default=None)
    args = ap.parse_args(argv)
    try:
        entry = collect(args.state_dir, args.source, args.target_date, args.lookback_days,
                        args.cap, args.run_id, args.commit, gate_dir=args.gate_dir)
    except (ValueError, OSError) as exc:
        print("collection refused: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(entry, ensure_ascii=False, indent=1, sort_keys=True))
    return 0 if entry["health"] in ("ok", "skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
