"""Read-only inventory and ratchet for every GitHub Pages (gh-pages) writer.

Issue #346. This is an AUDIT, not a fix: it never fetches, pushes, renders or
edits anything. It parses workflow YAML text (standard library only, so it
runs on the CI runner's Python 3.9 without PyYAML) and, in the optional
``--git-evidence`` mode, reads local refs that the caller already fetched.

What it does
------------
* Finds every job that can write ``gh-pages``: peaceiris/actions-gh-pages,
  Pages artifact deployers, ``git push ...:gh-pages`` and write calls to the
  GitHub API, plus scripts that combine a push with ``gh-pages``.
* Records each writer's class (full-tree / overlay / file-only branch push),
  its concurrency groups (workflow and job level both apply), its checkout ref,
  and which freshness guards appear (main CAS, approved SHA, Pages CAS,
  staged-path scope, main-branch guard).
* Compares the observations with ``REGISTRY``. It fails (exit 1) only on:
  an unregistered writer, a push whose target cannot be resolved, a scope
  escalation (file-only -> overlay -> full-tree, force, orphan), a dropped
  concurrency lock or a dropped guard. Other differences are reported, not
  failed, so desk teams can keep editing their own workflows.
* Reports structural hazards (``HAZARDS``). Those are findings for the
  handoff. They are deliberately NOT failures: the race is not fixed, and
  this tool must not pretend otherwise.

Output never echoes workflow lines, so tokens such as
``x-access-token:${{ github.token }}`` cannot leak into logs.

Usage::

    python scripts/audit_pages_writers.py            # text report, CI ratchet
    python scripts/audit_pages_writers.py --json     # deterministic JSON
    python scripts/audit_pages_writers.py --git-evidence \\
        --pages-ref origin/gh-pages --main-ref origin/main   # local refs only
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED_LOCK = "daily-update"

# ── Registry of known writers ────────────────────────────────────────────────
# id = "<workflow file>::<job id>". ``locks`` are concurrency-group literals
# that must remain present (workflow- or job-level). ``guards`` must remain
# present. Adding a writer means adding an entry here in a reviewed PR.
_FC = ("main_cas", "pages_cas", "staged_scope")  # file-only compare-and-swap set
REGISTRY = {
    "briefs_render_only_release.yml::publish": {
        "class": "full-tree", "locks": (SHARED_LOCK,),
        "guards": ("approved_sha", "main_cas", "main_ref_guard", "staged_scope")},
    "china_focus_release.yml::release": {
        "class": "full-tree", "locks": (SHARED_LOCK,),
        "guards": ("approved_sha", "main_cas", "main_ref_guard", "staged_scope")},
    # Authorized re-publish of an approved SHA; never rechecks main at deploy.
    "china_retirement_pages_retry.yml::verify-and-redeploy": {
        "class": "full-tree", "locks": (SHARED_LOCK,),
        "guards": ("approved_sha", "main_ref_guard")},
    "china_retirement_release.yml::release": {
        "class": "full-tree", "locks": (SHARED_LOCK,),
        "guards": ("approved_sha", "main_cas", "main_ref_guard")},
    "country_research_render_only_release.yml::release": {
        "class": "full-tree", "locks": (SHARED_LOCK,),
        "guards": ("approved_sha", "main_cas", "main_ref_guard")},
    # Known hazard: no-commit branch deploys the job-start checkout.
    "daily_update.yml::update": {
        "class": "full-tree", "locks": (SHARED_LOCK,), "guards": ("staged_scope",)},
    # Known hazard: outside daily-update, trigger SHA, no branch guard.
    "deploy_output_only.yml::deploy": {
        "class": "full-tree", "locks": ("pages-deploy",), "guards": ()},
    "desks_p4a_render_only_release.yml::release": {
        "class": "overlay", "locks": (SHARED_LOCK, "pages-deploy"),
        "guards": ("approved_sha", "main_cas", "main_ref_guard")},
    "indonesia_official_links_release.yml::publish": {
        "class": "full-tree", "locks": (SHARED_LOCK,),
        "guards": ("main_cas", "main_ref_guard")},
    "indonesia_press_links_release.yml::publish": {
        "class": "full-tree", "locks": (SHARED_LOCK,),
        "guards": ("main_cas", "main_ref_guard")},
    "korea_original_text_pages_release.yml::release-only-this-korean-original": {
        "class": "file-only", "locks": ("korea-verified-official-link-production",),
        "guards": ("main_cas", "pages_cas", "main_ref_guard")},
    "korea_pages_file_only_release.yml::korea-pages-file-only-release": {
        "class": "file-only", "locks": (SHARED_LOCK,), "guards": _FC},
    "korea_public_bibliography_release.yml::release": {
        "class": "full-tree", "locks": (SHARED_LOCK,),
        "guards": ("main_cas", "staged_scope")},
    # Intentionally outside daily-update (tests/test_korea_release_concurrency).
    "korea_verified_official_link_production.yml::publish-korea-official-links": {
        "class": "file-only", "locks": ("korea-verified-official-link-production",),
        "guards": _FC + ("main_ref_guard",)},
    "treasury_verified_official_links_release.yml::production-metadata-page-only": {
        "class": "file-only", "locks": (SHARED_LOCK,), "guards": _FC + ("main_ref_guard",)},
    "us_bis_verified_official_links_release.yml::genuine-scheduled-source-only": {
        "class": "file-only", "locks": (SHARED_LOCK,), "guards": _FC},
    "us_pacom_pages_file_only_release.yml::us-pacom-pages-file-only-release": {
        "class": "file-only", "locks": (SHARED_LOCK,), "guards": _FC},
    "uscc_verified_official_links_release.yml::production-metadata-page-only": {
        "class": "file-only", "locks": (SHARED_LOCK,), "guards": _FC + ("main_ref_guard",)},
}
# Scripts allowed to combine a push with gh-pages. None today.
SCRIPT_REGISTRY: dict = {}

# Escalation order: a writer may move left (narrower) but never right.
_CLASS_RANK = {"file-only": 0, "overlay": 1, "full-tree": 2, "orphan": 3, "unknown": 4}

HAZARDS = {
    "FULL_TREE_REPLACE": "replaces the whole gh-pages tree with its own output/; "
                         "any page not in that tree is reverted or deleted",
    "NO_GENERATION_FENCE": "publishes without checking which source generation "
                           "gh-pages currently holds; parent CAS is not content CAS",
    "OUTSIDE_SHARED_LOCK": "not serialized with the daily-update writers",
    "NO_PREPUBLISH_FRESHNESS": "no main CAS or approved-SHA check before the "
                               "publish step; may deploy a job-start tree",
    "NO_MAIN_REF_GUARD": "dispatchable without a refs/heads/main guard and "
                         "without checking out main",
    "PROVENANCE_IS_TRIGGER_SHA": "peaceiris v3 records GITHUB_SHA (trigger), not "
                                 "the checked-out commit, in the gh-pages message",
}

_PAGES_ACTIONS = ("peaceiris/actions-gh-pages", "actions/deploy-pages",
                  "actions/upload-pages-artifact", "github-pages-deploy-action")
_PUSH_RE = re.compile(r"\bgit(?:\s+-C\s+\S+)?(?:\s+-c\s+\S+)*\s+push\b(.*)")
_API_WRITE_RE = re.compile(r"\bgh\s+api\b.*(?:-X|--method)\s*(?:PUT|POST|PATCH|DELETE)")
_GROUP_RE = re.compile(r"^\s*group:\s*(.+?)\s*$")
_LITERAL_BRANCH_RE = re.compile(r"\b(?:shadow|review)/[A-Za-z0-9_.-]+")


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _code(line):
    """Line text with a full-line comment removed (YAML or shell)."""
    stripped = line.strip()
    return "" if stripped.startswith("#") else line


def _scalar(value):
    value = value.split(" #", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    return value


def _concurrency(lines, start, end, key_indent):
    """Group string declared by a ``concurrency:`` key at ``key_indent``."""
    for i in range(start, end):
        line = _code(lines[i])
        if _indent(line) != key_indent or not line.strip().startswith("concurrency:"):
            continue
        inline = line.split(":", 1)[1].strip()
        if inline:
            return _scalar(inline)
        for j in range(i + 1, end):
            sub = _code(lines[j])
            if not sub.strip():
                continue
            if _indent(sub) <= key_indent:
                break
            match = _GROUP_RE.match(sub)
            if match:
                return _scalar(match.group(1))
    return None


def _top_keys(lines, block):
    """Child keys of a top-level block (``on``/``jobs``) with line spans."""
    start = next((i for i, l in enumerate(lines)
                  if re.match(r"^%s:\s*(#.*)?$" % block, l)), None)
    if start is None:
        inline = next((l for l in lines if l.startswith(block + ":")), "")
        return {k.strip(): (0, 0) for k in re.findall(r"[A-Za-z_]+", inline.split(":", 1)[-1])}
    keys, end = [], len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.strip() and not line.startswith(" ") and not line.startswith("#"):
            end = i
            break
        match = re.match(r"^  ([A-Za-z0-9_.-]+):", line)
        if match:
            keys.append((match.group(1), i))
    spans = {}
    for n, (key, i) in enumerate(keys):
        spans[key] = (i, keys[n + 1][1] if n + 1 < len(keys) else end)
    return spans


def _steps(lines, start, end):
    """Yield (first_line, last_line, {key: value}) for each step in a job."""
    marks = [i for i in range(start, end) if re.match(r"^\s*- ", _code(lines[i]) or "x")
             and _indent(lines[i]) == 6]
    for n, i in enumerate(marks):
        stop = marks[n + 1] if n + 1 < len(marks) else end
        fields = {}
        for j in range(i, stop):
            line = _code(lines[j]).replace("- ", "  ", 1) if j == i else _code(lines[j])
            match = re.match(r"^\s*([A-Za-z_-]+):\s*(.*)$", line)
            if match and match.group(2) and match.group(1) not in fields:
                fields[match.group(1)] = _scalar(match.group(2))
        yield i, stop, fields


def _push_target(rest):
    """(target branch or None for implicit, force?) from text after ``git push``."""
    rest = re.split(r";|&&|\|\||\)|\bthen\b", rest)[0]
    try:
        args = shlex.split(rest)
    except ValueError:
        return "$unparsed", False
    force = any(a in ("-f", "--force") or a.startswith("--force") for a in args)
    positional = [a for a in args if not a.startswith("-")]
    refspecs = positional[1:]
    if not refspecs:
        return None, force
    spec = refspecs[-1]
    force = force or spec.startswith("+")
    target = spec.split(":", 1)[-1].lstrip("+")
    if target.startswith("refs/heads/"):
        target = target[len("refs/heads/"):]
    return target, force


def _guards(text_lines):
    joined = "\n".join(text_lines)
    found = set()
    for line in text_lines:
        if "test" in line and "rev-parse origin/main" in line:
            found.add("main_cas")
        if "test" in line and "rev-parse origin/gh-pages" in line:
            found.add("pages_cas")
    if re.search(r"EXPECTED_SHA|approved_[a-z_]*sha", joined):
        found.add("approved_sha")
    if "diff --cached --name-only" in joined:
        found.add("staged_scope")
    if "refs/heads/main" in joined and "github.ref" in joined:
        found.add("main_ref_guard")
    return found


def audit_workflow(path):
    """Return (writers, problems) for one workflow file."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    name = path.name
    triggers = sorted(_top_keys(lines, "on"))
    wf_group = _concurrency(lines, 0, len(lines), 0)
    code_text = [_code(l) for l in lines]
    file_mentions_pages = any("gh-pages" in l for l in code_text)
    literal_branches = sorted(set(_LITERAL_BRANCH_RE.findall("\n".join(code_text))))
    writers, problems = [], []
    for job, (start, end) in sorted(_top_keys(lines, "jobs").items()):
        job_lines = [_code(l) for l in lines[start:end]]
        job_group = _concurrency(lines, start, end, 4)
        checkout_ref, publish_line, cls, details = None, None, None, {}
        signals = []
        for first, stop, step in _steps(lines, start, end):
            uses = step.get("uses", "")
            if uses.startswith("actions/checkout@") and "path" not in step:
                checkout_ref = checkout_ref or step.get("ref", "<trigger>")
            if any(a in uses for a in _PAGES_ACTIONS):
                signals.append("action:" + uses.split("@")[0])
                publish_line = publish_line or first
                if "peaceiris" in uses:
                    keep = step.get("keep_files", "false").lower() == "true"
                    orphan = step.get("force_orphan", "false").lower() == "true"
                    cls = "orphan" if orphan else ("overlay" if keep else "full-tree")
                    details.update(keep_files=keep, publish_dir=step.get("publish_dir", ""),
                                   publish_branch=step.get("publish_branch", "gh-pages"))
                else:
                    cls = "full-tree"
        for offset, line in enumerate(job_lines):
            lineno = start + offset + 1
            match = _PUSH_RE.search(line)
            if match:
                target, force = _push_target(match.group(1))
                if target is None:
                    target = checkout_ref or "<trigger>"
                if "$" in target:
                    if file_mentions_pages or not literal_branches:
                        problems.append({"kind": "UNRESOLVED_PUSH_TARGET",
                                         "where": "%s:%d" % (name, lineno), "job": job})
                    continue
                if target == "gh-pages":
                    signals.append("git-push:gh-pages")
                    publish_line = publish_line or (start + offset)
                    cls = cls or "file-only"
                    if force:
                        cls = "orphan"
                        details["force_push"] = True
            if _API_WRITE_RE.search(line) and re.search(r"gh-pages|/pages\b|git/refs", line):
                signals.append("gh-api-write")
                cls = cls or "unknown"
                publish_line = publish_line or (start + offset)
        if not signals:
            continue
        guards = _guards(job_lines)
        before = [l for l in lines[start:publish_line]] if publish_line else []
        fresh = bool(_guards([_code(l) for l in before]) & {"main_cas", "approved_sha"})
        writers.append({
            "id": "%s::%s" % (name, job),
            "class": cls,
            "signals": sorted(set(signals)),
            "triggers": triggers,
            "concurrency": sorted(g for g in (wf_group, job_group) if g),
            "checkout_ref": checkout_ref or "<none>",
            "guards": sorted(guards),
            "fresh_before_publish": fresh,
            "generation_fence": False,
            **details,
        })
    return writers, problems


_SELF = "scripts/audit_pages_writers.py"  # mentions both patterns, writes nothing


def audit_scripts(root):
    problems, found = [], []
    for path in sorted(list((root / "scripts").rglob("*.py")) + list((root / "scripts").rglob("*.sh"))
                       + list((root / ".github").rglob("action.y*ml"))):
        code = [_code(l) for l in path.read_text(encoding="utf-8", errors="replace").splitlines()]
        joined = "\n".join(code)
        pushes = bool(re.search(r"\bgit\s+push\b|[\"']push[\"']", joined))
        if pushes and "gh-pages" in joined:
            rel = path.relative_to(root).as_posix()
            if rel == _SELF:
                continue
            found.append(rel)
            if rel not in SCRIPT_REGISTRY:
                problems.append({"kind": "UNREGISTERED_SCRIPT_WRITER", "where": rel})
    return found, problems


def hazards_for(writer):
    out = []
    groups = " ".join(writer["concurrency"])
    if writer["class"] in ("full-tree", "orphan"):
        out.append("FULL_TREE_REPLACE")
    if not writer["generation_fence"]:
        out.append("NO_GENERATION_FENCE")
    if SHARED_LOCK not in groups:
        out.append("OUTSIDE_SHARED_LOCK")
    if writer["class"] != "file-only" and not writer["fresh_before_publish"]:
        out.append("NO_PREPUBLISH_FRESHNESS")
    if ("workflow_dispatch" in writer["triggers"] and "main_ref_guard" not in writer["guards"]
            and writer["checkout_ref"] != "main"):
        out.append("NO_MAIN_REF_GUARD")
    if any("peaceiris" in s for s in writer["signals"]):
        out.append("PROVENANCE_IS_TRIGGER_SHA")
    return out


def compare(writers, registry):
    problems, notes = [], []
    seen = {w["id"]: w for w in writers}
    for wid, writer in sorted(seen.items()):
        entry = registry.get(wid)
        if entry is None:
            problems.append({"kind": "UNREGISTERED_WRITER", "where": wid, "class": writer["class"]})
            continue
        if _CLASS_RANK[writer["class"]] > _CLASS_RANK[entry["class"]]:
            problems.append({"kind": "SCOPE_ESCALATION", "where": wid,
                             "registered": entry["class"], "observed": writer["class"]})
        elif writer["class"] != entry["class"]:
            notes.append({"kind": "SCOPE_NARROWED", "where": wid, "observed": writer["class"]})
        groups = " ".join(writer["concurrency"])
        for lock in entry["locks"]:
            if lock not in groups:
                problems.append({"kind": "LOCK_DROPPED", "where": wid, "lock": lock})
        for guard in entry["guards"]:
            if guard not in writer["guards"]:
                problems.append({"kind": "GUARD_DROPPED", "where": wid, "guard": guard})
    for wid in sorted(set(registry) - set(seen)):
        notes.append({"kind": "REGISTERED_WRITER_NOT_FOUND", "where": wid})
    return problems, notes


def run_audit(root=ROOT, registry=None):
    registry = REGISTRY if registry is None else registry
    writers, problems = [], []
    for path in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        found, issues = audit_workflow(path)
        writers.extend(found)
        problems.extend(issues)
    scripts, script_problems = audit_scripts(root)
    problems.extend(script_problems)
    cmp_problems, notes = compare(writers, registry)
    problems.extend(cmp_problems)
    for writer in writers:
        writer["hazards"] = hazards_for(writer)
    writers.sort(key=lambda w: w["id"])
    problems.sort(key=lambda p: (p["kind"], p["where"]))
    return {
        "writers": writers,
        "script_writers": scripts,
        "violations": problems,
        "notes": notes,
        "hazard_legend": HAZARDS,
        "summary": {
            "writers": len(writers),
            "by_class": {c: sum(w["class"] == c for w in writers)
                         for c in sorted({w["class"] for w in writers})},
            "outside_shared_lock": sorted(w["id"] for w in writers
                                          if "OUTSIDE_SHARED_LOCK" in w["hazards"]),
            "with_generation_fence": sum(w["generation_fence"] for w in writers),
            "violations": len(problems),
        },
    }


# ── Optional local-ref evidence (never in the CI path; refs move) ────────────
def _git(root, *args, stdin=None):
    return subprocess.run(["git", *args], cwd=root, input=stdin, check=True,
                          capture_output=True, text=True).stdout


def _tree(root, ref):
    out = {}
    for line in _git(root, "ls-tree", "-r", "-z", ref).split("\0"):
        if line:
            meta, path = line.split("\t", 1)
            out[path] = meta.split()[2]
    return out


def git_evidence(root, pages_ref, main_ref, limit):
    ignore = {".nojekyll", "CNAME"}
    pages, main = _tree(root, pages_ref), _tree(root, main_ref + ":output")
    drift = {
        "pages_only": sorted(p for p in pages if p not in main and p not in ignore),
        "main_only": sorted(p for p in main if p not in pages and p not in ignore),
        "differs": sorted(p for p in pages if p in main and pages[p] != main[p]),
    }
    log = _git(root, "log", "--first-parent", "-n", str(limit),
               "--format=%H%x1f%cn%x1f%ct", pages_ref).splitlines()
    commits = [l.split("\x1f") for l in reversed(log)]
    authors = {"actions_bot": 0, "out_of_band": 0}
    out_of_band = []
    history, recent, candidates = {}, [], []
    zero = "0" * 40
    for sha, committer, ctime in commits:
        bot = committer == "github-actions[bot]"
        authors["actions_bot" if bot else "out_of_band"] += 1
        if not bot:
            out_of_band.append(sha[:10])
        parents = _git(root, "rev-list", "--parents", "-n", "1", sha).split()
        if len(parents) < 2:
            continue
        diff = _git(root, "diff-tree", "-r", "--no-renames", "-z", parents[1], sha).split("\0")
        changed = {}
        for i in range(0, len(diff) - 1, 2):
            if diff[i].startswith(":"):
                meta = diff[i].split()
                changed[diff[i + 1]] = (meta[2], meta[3])
        recent_paths = set().union(*[r for r in recent[-10:]]) if recent else set()
        for path, (old, new) in changed.items():
            prior = history.setdefault(path, [])
            if new != zero and new in prior[:-1]:
                candidates.append((sha, ctime, path, new, "blob_reuse"))
            elif new == zero and path in recent_paths and path not in ignore:
                candidates.append((sha, ctime, path, new, "delete_after_recent_write"))
            prior.append(new)
        recent.append(set(changed))
    resolved = []
    for sha, ctime, path, new, kind in candidates:
        mains = _git(root, "rev-list", "-1", "--first-parent", "--before=" + ctime, main_ref).strip()
        blob = ""
        if mains:
            check = _git(root, "cat-file", "--batch-check",
                         stdin="%s:output/%s\n" % (mains, path)).split()
            blob = "" if "missing" in check else check[0]
        backed = (new == zero and not blob) or new == blob
        resolved.append({"commit": sha[:10], "path": path, "kind": kind, "main_backed": backed})
    unexplained = [r for r in resolved if not r["main_backed"]]
    return {
        "pages_ref": pages_ref, "main_ref": main_ref, "commits_scanned": len(commits),
        "drift_counts": {k: len(v) for k, v in drift.items()},
        "drift_sample": {k: v[:50] for k, v in drift.items()},
        "committer_classes": authors, "out_of_band_commits": out_of_band,
        "reversion_candidates": len(resolved),
        "unexplained_reversions": unexplained[:200],
        "main_backed_reversions": len(resolved) - len(unexplained),
        "limits": "main parity is approximated by the first-parent main commit before "
                  "each deploy's committer time; deletions are only tracked within "
                  "ten commits of the last write",
    }


def _text(report):
    out = ["Pages writer audit (issue #346) — %d writers, %d violations"
           % (report["summary"]["writers"], report["summary"]["violations"])]
    for w in report["writers"]:
        out.append("  %-72s %-9s locks=%s ref=%s guards=%s" % (
            w["id"], w["class"], ",".join(w["concurrency"]) or "-",
            w["checkout_ref"], ",".join(w["guards"]) or "-"))
        out.append("      hazards: " + (", ".join(w["hazards"]) or "-"))
    for p in report["violations"]:
        out.append("VIOLATION %s %s" % (p["kind"], json.dumps(
            {k: v for k, v in p.items() if k != "kind"}, sort_keys=True)))
    for n in report["notes"]:
        out.append("note %s %s" % (n["kind"], n["where"]))
    out.append("Writers with a generation fence: %d. Passing this audit does NOT mean "
               "the stale-deploy race is fixed." % report["summary"]["with_generation_fence"])
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--git-evidence", action="store_true",
                        help="also compare local refs (read-only; not for CI gating)")
    parser.add_argument("--pages-ref", default="origin/gh-pages")
    parser.add_argument("--main-ref", default="origin/main")
    parser.add_argument("--limit", type=int, default=300)
    args = parser.parse_args(argv)
    report = run_audit(args.root)
    if args.git_evidence:
        report["git_evidence"] = git_evidence(args.root, args.pages_ref, args.main_ref, args.limit)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else _text(report))
    if args.git_evidence and not args.json:
        print(json.dumps(report["git_evidence"], indent=2, sort_keys=True))
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
