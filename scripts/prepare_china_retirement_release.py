"""Prepare a complete, read-only-to-production China retirement release.

All outputs and the physically reduced SQLite copy live under a NEW external
scratch directory. The canonical DB and tracked output/ are never written.
The manual cutover workflow may separately promote this exact verified build.
"""
import argparse
from datetime import date
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

from scripts.build_retired_archive_export import build as rebuild_export
from scripts.plan_china_active_retirement import (
    plan, publication_record_dependencies, scratch_retirement,
)
from scripts.verify_china_retirement_render import validate
from scripts.verify_china_retirement_crossdesk import (validate as crossdesk_validate, verify_us_public_link_parity)

ROOT = Path(__file__).resolve().parents[1]
SITE_RENDER = ROOT / "site" / "render.py"
BASE_DB = ROOT / "pla_watch.db"


def _render(db, output, origin):
    subprocess.run([sys.executable, str(SITE_RENDER), "--db", str(db),
                    "--out", str(output), "--site-origin", origin],
                   cwd=str(ROOT), check=True)


def _carried_published_assets(target):
    """Preserve already-published issues and admitted media, not old records."""
    spec = importlib.util.spec_from_file_location("ipr_render_release", SITE_RENDER)
    render = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render)
    old = ROOT / "output"
    for name in render.CARRIED_FORWARD:
        source, destination = old / name, target / name
        if not source.exists():
            continue
        if source.is_dir():
            for file in source.rglob("*"):
                if not file.is_file():
                    continue
                other = destination / file.relative_to(source)
                if not other.exists():
                    other.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file, other)
        elif not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    # The original tracked output may not contain this hosting marker because
    # the Pages action synthesizes it. Put it in the reviewed scratch tree so
    # the exact remote byte-readback can prove the published contract.
    (target / ".nojekyll").touch(exist_ok=True)
    # Existing export enumerates pre-cull rows. Recreate from scratch instead.
    (target / "data" / "articles.json").unlink(missing_ok=True)
    render.add_carried_pages_to_sitemap(target)


def prepare(scratch_root, *, expected_db_sha256, site_origin):
    scratch_root = Path(scratch_root)
    if (not scratch_root.is_absolute() or scratch_root.exists()
            or not scratch_root.parent.is_dir()
            or scratch_root.parent.is_symlink()):
        raise ValueError("release scratch must be a NEW absolute directory")
    scratch_root = scratch_root.resolve()
    if (scratch_root == ROOT or ROOT in scratch_root.parents
            or scratch_root in ROOT.parents):
        raise ValueError("release scratch cannot overlap the production repo")
    if not isinstance(expected_db_sha256, str) or len(expected_db_sha256) != 64:
        raise ValueError("exact release DB SHA-256 is required")
    before_digest = sha256(BASE_DB.read_bytes()).hexdigest()
    if before_digest != expected_db_sha256:
        raise ValueError("tracked corpus differs from reviewed recovery snapshot")

    scratch_root.mkdir(mode=0o700)
    before = scratch_root / "before-site"
    reduced = scratch_root / "reduced.db"
    after = scratch_root / "reduced-site"
    tombstones = scratch_root / "retired-url-hashes.json"
    plan_path = scratch_root / "plan.json"

    _render(BASE_DB, before, site_origin)
    dependencies, dependency_counts = publication_record_dependencies(ROOT)
    chosen = plan(json.loads((before / "corpus-index.json").read_text(encoding="utf-8")),
                  publication_ids=dependencies)
    summary = {key: value for key, value in chosen.items()
               if key not in ("retired_ids", "kept_ids")}
    summary["publication_reference_counts"] = dependency_counts
    if chosen["china_to_retire"] != 4400:
        raise ValueError("unexpected physical China retirement total")
    plan_path.write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n",
                         encoding="utf-8")

    result = scratch_retirement(BASE_DB, reduced, chosen,
                                tombstone_path=tombstones,
                                retired_at=date.today().isoformat())
    if not result["atomic_retirement"] or result["url_tombstone_count"] != 4400:
        raise ValueError("physical retirement not atomically tombstoned")

    # Physical China deletion must not touch independent official U.S. feed
    # rows, their historical collection receipts, or the source registry.
    crossdesk = crossdesk_validate(BASE_DB, reduced)

    _render(reduced, after, site_origin)
    _carried_published_assets(after)
    rebuild_export(reduced, after)
    us_public_links = verify_us_public_link_parity(before, after, crossdesk)

    proof = validate(before, after, reduced, plan_path)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_output.py"),
                    str(after)], cwd=str(ROOT), check=True)
    if sha256(BASE_DB.read_bytes()).hexdigest() != before_digest:
        raise ValueError("preflight changed production database")
    if (Path(str(BASE_DB)+"-wal").exists()
            or Path(str(BASE_DB)+"-shm").exists()):
        raise ValueError("preflight left a tracked SQLite sidecar")

    receipt = {
        "source_db_sha256": before_digest,
        "scratch_db_sha256": sha256(reduced.read_bytes()).hexdigest(),
        "retirement_id_sha256": proof["retirement_id_sha256"],
        "retired": proof["retired"],
        "retained": proof["retained"],
        "protected_trails": proof["protected_trails"],
        "legacy_export": proof["legacy_export"],
        "preserved_other_desk_sqlite": crossdesk,
        "preserved_us_public_link_counts": us_public_links,
        "site_path": str(after),
        "scratch_db_path": str(reduced),
        "no_production_mutation": True,
    }
    (scratch_root / "release-verification.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scratch-root", type=Path, required=True)
    p.add_argument("--expected-db-sha256", required=True)
    p.add_argument("--site-origin", required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.scratch_root,
                             expected_db_sha256=a.expected_db_sha256,
                             site_origin=a.site_origin),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
