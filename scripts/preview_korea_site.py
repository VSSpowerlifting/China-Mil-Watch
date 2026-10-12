"""Build the private, site-matched Korea Desk layout without enabling it.

Renders a COMPLETE regular IPR preview for design QA plus an unlinked Korea
candidate page. No site origin, registry mutation, public source admission,
production output writes, captured body, or release is possible from this CLI.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "site" / "preview"))
import generate_preview as site  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True,
                        help="new absolute output directory outside repository")
    args = parser.parse_args(argv)
    try:
        result = site.build(
            args.out, "Indo-Pacific Record", REPO_ROOT / "pla_watch.db",
            snapshot=site.snapshot_from_corpus(REPO_ROOT / "pla_watch.db"),
            review_korea=True)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    target = Path(result["out_dir"])
    korea_page = target / "korea.html"
    if not korea_page.is_file() or (target / "sitemap.xml").exists():
        parser.error("Korea private noindex preview integrity failure")
    print(json.dumps({
        "preview_file": str(korea_page),
        "public_korea_route_activated": False,
        "registry_changed": False,
        "source_collection_changed": False,
        "production_output_changed": False,
        "site_origin": None,
        "candidate_count": 5,
        "approved_reference_count": 0,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
