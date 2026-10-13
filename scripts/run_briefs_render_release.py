"""Run the governed render for Phase 3C and No. 17 without publishing it.

The release renders historical PLA Watch pages from their existing sidecars,
then renders the current IPR tree. It never collects, changes canonical
sidecars, writes the database, or deploys. Publication is a separate, manual
workflow input after the strict output-scope check passes.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_ORIGIN = "https://indopacificrecord.org"
HISTORICAL_DATES = (
    "2026-05-09", "2026-05-16", "2026-05-23", "2026-05-30",
    "2026-06-06", "2026-06-13", "2026-06-20", "2026-06-27",
    "2026-07-04", "2026-07-11", "2026-07-18", "2026-08-01",
    "2026-08-08", "2026-08-15",
)


def _run(*args: str) -> None:
    print("$ " + " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_rendered_contract() -> None:
    out = ROOT / "output"
    analysis = (out / "analysis.html").read_text(encoding="utf-8")
    article_path = out / "briefs" / "trident-resolve-regional-scale-specific-chinese-tasks.html"
    article = article_path.read_text(encoding="utf-8")
    historical = (out / "the-pla-watch" / "posts" / "2026-08-15.html").read_text(
        encoding="utf-8")
    no12 = (out / "the-pla-watch" / "posts" / "2026-08-01.html").read_text(
        encoding="utf-8")

    assert "no-17-trident-resolve-basarnas-drone.jpg" in analysis, (
        "No. 17 catalogue card is missing its admitted photograph")
    assert "no-08-liaoning-j15-recovery.jpg" in analysis, (
        "No. 8's existing catalogue photograph disappeared")
    assert "no-09-scarborough-shoal-iss.jpg" in analysis, (
        "No. 9's existing catalogue photograph disappeared")
    for required in (
        "trident-resolve-basarnas-drone-800.webp",
        "9957254",
        "Sgt. 1st Class Timothy Hughes",
        "does not imply or constitute DoW endorsement",
    ):
        assert required in article, f"No. 17 article is missing {required!r}"
    assert "Adjacent historical issues" in historical, (
        "historical Brief navigation is absent from the rerendered article")
    assert "Downloaded from PLA Daily / 81.cn" not in no12, (
        "the prohibited No. 12 collector note has appeared")
    for rel in (
        "assets/editorial/trident-resolve-basarnas-drone.jpg",
        "assets/editorial/derivatives/trident-resolve-basarnas-drone-1600.jpg",
        "assets/editorial/derivatives/trident-resolve-basarnas-drone-800.webp",
        "assets/editorial/derivatives/trident-resolve-basarnas-drone-1600.webp",
        "assets/catalogue/media/no-17-trident-resolve-basarnas-drone.jpg",
    ):
        assert (out / rel).is_file(), f"required No. 17 asset is missing: {rel}"
    for date in HISTORICAL_DATES:
        assert (out / "the-pla-watch" / "posts" / f"{date}.html").is_file(), (
            f"historical Brief page missing after render: {date}")


def _check_db_and_worktree(db_hash: str) -> None:
    db = ROOT / "pla_watch.db"
    if _sha256(db) != db_hash:
        raise RuntimeError("pla_watch.db changed during render")
    for suffix in ("-wal", "-shm"):
        if (ROOT / ("pla_watch.db" + suffix)).exists():
            raise RuntimeError("database sidecar appeared: pla_watch.db" + suffix)
    subprocess.run(
        ["git", "diff", "--exit-code", "--", "pla_watch.db"],
        cwd=ROOT, check=True,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    outside_output = [
        line for line in status
        if line[3:].strip() and not line[3:].startswith("output/")
    ]
    if outside_output:
        raise RuntimeError(
            "render changed files outside output/; refusing release: "
            + "; ".join(outside_output[:20]))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope", choices=("report-only", "strict"), default="report-only",
        help="report-only produces a preview; strict refuses any unreviewed output path",
    )
    args = parser.parse_args(argv)
    db = ROOT / "pla_watch.db"
    if not db.is_file():
        raise SystemExit("BLOCKED: tracked pla_watch.db is missing")
    if any((ROOT / ("pla_watch.db" + suffix)).exists() for suffix in ("-wal", "-shm")):
        raise SystemExit("BLOCKED: pre-existing database sidecar; stop before rendering")
    initial_status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()
    if initial_status:
        raise SystemExit("BLOCKED: worktree must be clean before rendering")

    db_hash = _sha256(db)
    _run(sys.executable, "scripts/build_brief_cover.py", "--check")
    _run(sys.executable, "scripts/build_catalogue_media.py", "--check")
    _run(sys.executable, "scripts/rerender_pla_watch.py", "--no-covers")
    _run(sys.executable, "site/render.py", "--out", "output",
         "--site-origin", SITE_ORIGIN)
    _run(sys.executable, "scripts/validate_output.py")
    _assert_rendered_contract()
    _check_db_and_worktree(db_hash)

    from scripts.guard_briefs_render_scope import classify_output_changes
    changed, unexpected = classify_output_changes(ROOT)
    print(f"Briefs release output deltas: {len(changed)}")
    for path in sorted(changed):
        print(("BLOCKED: " if path in unexpected else "REVIEWED: ") + path)
    if unexpected:
        print("Unreviewed output drift:")
        for path in sorted(unexpected):
            print("  " + path)
        if args.scope == "strict":
            raise SystemExit(
                "BLOCKED: strict release scope failed; do not commit or deploy")
        print("PREVIEW ONLY: unexpected output paths are reported, not published.")
    elif not changed:
        print("No generated output changes.")
        if args.scope == "strict":
            raise SystemExit("BLOCKED: no changes to release")
    else:
        print("Output scope is within the explicit Briefs release allow-list.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
