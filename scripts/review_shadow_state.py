#!/usr/bin/env python3
"""
Singapore shadow state review kit — read-only.

Produces the evidence package for a Day 7 / 14 / 30 checkpoint review from an
explicit copy of `shadow/singapore-mindef` state. It validates what a machine
can validate and then gets out of the way: the checkpoint is a *human* reading
of stored records against the ministry's own pages, and nothing here can stand
in for that.

Provenance, because a SHA is not a tree
--------------------------------------
A **formal** packet is derived from the Git object named by `--state-commit`:
the `state/` tree is exported from that commit with `git cat-file`, and those
exported bytes are the ones hashed, analysed and packaged. The commit must
exist in `--state-repo` and be reachable from `shadow/singapore-mindef` (or a
ref named explicitly with `--state-ref`), and the tree may hold only regular
files, so nothing can redirect a read outside it. The verified commit and tree
identities travel in the manifest.

A **rehearsal** packet reads `--state-dir`, an ordinary directory trusted
as-is. It exercises the tooling and is refused for publication. The two are
mutually exclusive: in formal mode a working-tree copy is refused rather than
quietly preferred over the committed bytes.

Safety, because the input is evidence
-------------------------------------
  * `--state-dir` (rehearsal) is refused if it is the repository, contains
    `pla_watch.db`, or contains a tracked `output/`
  * the shadow database is opened `mode=ro&immutable=1`, so no lock is taken
    and no -wal/-shm can appear beside it
  * every input file is hashed before and after; a changed input fails the run
  * `--out` is required and refuses a tracked repository destination unless the
    test-only `--allow-tracked-destination` override is passed
  * no network. The runtime imports are stdlib plus
    `core.collection.status`, which is a module of constants. The adapter is
    deliberately NOT imported: it pulls in `requests`, and `config` reads `.env`
    and names the production database. What this tool needs from the adapter —
    the canonical URL shape, the slug date, the slug kind — is re-derived here,
    and `tests/test_shadow_review_kit.py` imports both and asserts they agree,
    so drift is caught without giving this tool a network-capable import.

Determinism
-----------
Two runs of the same state commit with the same `--as-of` produce byte-identical
packet files — the manifest included. Wall-clock time and local paths go to
`generation_context.json`, which is neither part of the package nor preserved:
one package id names one set of bytes, or it names nothing in particular.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                       # noqa: E402

TOOL_VERSION = "1.1.0"
QUEUE_ALGORITHM = "shadow-review-queue/1"
SIGNOFF_SCHEMA = "shadow-review-signoff/1"

#: The one desk this kit reviews. Part of the binding: a packet that does not
#: name its desk could be filed against the wrong one.
DESK_IDENTITY = "singapore-mindef"

#: The state history a formal packet must be pinned to. A commit that exists is
#: not the same claim as a commit that belongs to this desk's state.
STATE_BRANCH = "shadow/singapore-mindef"

#: Where `state/` lives inside a state commit.
STATE_PREFIX = "state"

#: Git environment that would silently point a command at another repository.
#: Provenance read through an inherited GIT_DIR is provenance about some other
#: repository.
UNSAFE_GIT_ENV = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE",
    "GIT_CONFIG", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS", "GIT_SSH", "GIT_SSH_COMMAND",
    "GIT_EXTERNAL_DIFF", "GIT_PROXY_COMMAND", "GIT_ASKPASS",
)

#: Every path a state tree may contain. An unexpected file in the committed
#: tree is a refusal: a packet must not silently incorporate evidence nobody
#: expected, and must not silently omit evidence that was committed.
STATE_TREE_REQUIRED = ("clock.json", "shadow.db")
STATE_TREE_DIRS = ("ledger",)

#: Checkpoints the qualification defines. A formal packet is one of these.
CHECKPOINTS = {"day-07": 7, "day-14": 14, "day-30": 30}

#: Explicit answers only. "yes" in a free-text field is not an answer a program
#: can check, and a review nobody can check is not evidence.
CHECK_FIELDS = (
    "source_page_opened", "title_matches", "publication_date_matches",
    "canonical_url_matches", "body_appears_complete", "kind_is_reasonable",
    "no_denial_or_template_stored",
)
VERDICTS = ("pass", "pass_with_findings", "fail")

#: Exactly the columns `scripts/shadow_collect.py` creates. An unknown shape is
#: refused rather than guessed at.
EXPECTED_COLUMNS = (
    "url", "source_slug", "title_original", "text_original", "published_date",
    "language_tag", "publication_kind", "content_sha256", "capture_sha256",
    "retrieved_at", "first_seen_run",
)
REQUIRED_NON_NULL = (
    "url", "source_slug", "title_original", "text_original", "published_date",
    "language_tag", "publication_kind", "content_sha256",
)
EXPECTED_TABLES = {"shadow_records"}

#: The collector's own terminal-success set (`terminal_ok` in shadow_collect).
TERMINAL_OK = frozenset({st.OK, st.OK_NO_PUBLICATIONS, st.OK_ALL_DUPLICATES,
                         st.OK_ALL_FILTERED})

LEDGER_REQUIRED = (
    "run_id", "collector_commit", "started_utc", "finished_utc", "target_date",
    "lookback_days", "cap", "robots_status", "listing_status", "discovered",
    "selected", "retrieved", "inserted", "duplicates", "filtered",
    "fetch_failures", "extraction_failures", "access_failures",
    "state_sha256_before", "state_sha256_after", "result", "health",
    "shadow_day",
)

#: Mirrors scraper/sources/sg_mindef.py. Kept in step by an equivalence test.
RELEASE_RE = re.compile(
    r"^https://www\.mindef\.gov\.sg/news-and-events/latest-releases/[^/]+/$")
KINDS = {"nr": "news release", "speech": "speech", "fs": "fact sheet",
         "mq": "ministerial question", "pq": "parliamentary question"}
_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
           "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}

#: The collector refuses a body under this length, so anything shorter in the
#: database contradicts the collector that wrote it. This is the collector's
#: documented floor, not a threshold invented here.
COLLECTOR_MIN_BODY_CHARS = 200

#: Structures that mean "this is not the published document". Detected by the
#: text they contain, not by length: a short real reply and a long error page
#: are both possible, and length alone would misjudge each.
STUB_MARKERS = (
    "access denied", "403 forbidden", "404 not found", "page not found",
    "are you a robot", "enable javascript", "checking your browser",
    "request unsuccessful", "attention required", "cloudflare",
    "service unavailable", "temporarily unavailable",
)


class ReviewError(RuntimeError):
    """The state could not be reviewed. Fails closed; never a partial package."""


# ── provenance: bytes from the Git object database, not from a working tree ──

def _git_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in UNSAFE_GIT_ENV}
    # Verification reads objects that are already local. Nothing here may reach
    # out, and nothing here may stop to ask for a credential.
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git(args, cwd: Path, check: bool = True):
    proc = subprocess.run(["git"] + list(args), cwd=str(cwd), env=_git_env(),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True)
    if check and proc.returncode != 0:
        raise ReviewError("git %s failed in %s:\n%s"
                          % (" ".join(str(a) for a in args[:2]), cwd,
                             proc.stdout.strip()))
    return proc


def _git_bytes(args, cwd: Path) -> bytes:
    proc = subprocess.run(["git"] + list(args), cwd=str(cwd), env=_git_env(),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise ReviewError("git %s failed in %s:\n%s"
                          % (" ".join(str(a) for a in args[:2]), cwd,
                             proc.stderr.decode("utf-8", "replace").strip()))
    return proc.stdout


def assert_not_an_option(value: str, what: str) -> str:
    """Git reads a leading `-` as an option wherever it appears in an argv."""
    if str(value).startswith("-"):
        raise ReviewError(
            "%s may not begin with '-': %r would be read by git as an option."
            % (what, value))
    return str(value)


def resolve_state_repo(state_repo: Path) -> Path:
    """The repository that must contain the commit — a clone, not a worktree copy."""
    state_repo = Path(state_repo).resolve()
    if not state_repo.exists():
        raise ReviewError("no state repository at %s" % state_repo)
    proc = git(["rev-parse", "--git-dir"], state_repo, check=False)
    if proc.returncode != 0:
        raise ReviewError(
            "%s is not a Git repository. A formal packet is derived from the "
            "Git objects of the state clone, so `.git` must still be there.\n"
            "Clone the state branch and pass --state-repo; do not remove .git "
            "before generating the packet." % state_repo)
    return state_repo


def verify_state_commit(state_repo: Path, state_commit: str,
                        expected_ref: str) -> dict:
    """
    Establish that `state_commit` is a commit of this desk's state history.

    Three separate claims, each refused on its own terms: the object exists and
    is a commit; it is an ancestor of (or is) the expected state ref; and it
    carries a `state/` tree. A SHA that satisfies the first two but names no
    state tree is still not something this kit can review.
    """
    assert_not_an_option(state_commit, "--state-commit")
    if not re.fullmatch(r"[0-9a-f]{40}", state_commit):
        raise ReviewError(
            "--state-commit must be a full 40-character commit SHA; got %r"
            % state_commit)

    kind = git(["cat-file", "-t", state_commit], state_repo, check=False)
    if kind.returncode != 0 or kind.stdout.strip() != "commit":
        raise ReviewError(
            "commit %s does not exist in %s (or is not a commit).\n"
            "A formal packet is bound to a commit this repository can produce "
            "the bytes for — a syntactically valid SHA is not provenance."
            % (state_commit, state_repo))

    ref = assert_not_an_option(expected_ref, "--state-ref")
    tip = None
    for candidate in (ref, "refs/heads/%s" % ref, "refs/remotes/origin/%s" % ref):
        got = git(["rev-parse", "--verify", "--quiet", candidate + "^{commit}"],
                  state_repo, check=False)
        if got.returncode == 0:
            tip, ref = got.stdout.strip(), candidate
            break
    if tip is None:
        raise ReviewError(
            "%s names no ref in %s. A formal packet must be reachable from the "
            "state history it claims to review; clone that branch, or name the "
            "trusted ref explicitly with --state-ref." % (expected_ref, state_repo))

    reach = git(["merge-base", "--is-ancestor", state_commit, tip],
                state_repo, check=False)
    if reach.returncode != 0:
        raise ReviewError(
            "commit %s is not reachable from %s (%s).\n"
            "It may exist in this repository, but it is not part of the state "
            "history this desk's evidence comes from."
            % (state_commit, ref, tip[:12]))

    tree = git(["rev-parse", "--verify", "--quiet",
                "%s:%s" % (state_commit, STATE_PREFIX)], state_repo, check=False)
    if tree.returncode != 0:
        raise ReviewError("commit %s has no %s/ tree"
                          % (state_commit, STATE_PREFIX))
    return {"state_commit": state_commit, "state_tree": tree.stdout.strip(),
            "state_ref": ref, "state_ref_tip": tip,
            "state_repo_verified": True}


def export_state_tree(state_repo: Path, state_commit: str, dest: Path) -> Path:
    """
    Materialise `state/` from the commit's own tree.

    `git cat-file` gives the blob bytes Git has, so nothing a working tree
    happens to contain can substitute for them. Non-regular entries are refused
    rather than followed: a symlink committed into the tree would otherwise
    redirect a read outside it, and a gitlink names a tree this repository does
    not have.
    """
    dest.mkdir(parents=True, exist_ok=True)
    listing = _git_bytes(["ls-tree", "-r", "-z", "--full-tree", "--long",
                          "%s:%s" % (state_commit, STATE_PREFIX)], state_repo)
    written = []
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        meta, _, raw_name = entry.partition(b"\t")
        mode, kind, oid, _size = meta.decode("utf-8").split(None, 3)
        name = raw_name.decode("utf-8")
        if kind != "blob" or mode not in ("100644", "100755"):
            raise ReviewError(
                "%s/%s is a %s with mode %s — a state tree carries regular "
                "files only. Symlinks and submodules can redirect a read "
                "outside the committed tree, so they are refused rather than "
                "followed." % (STATE_PREFIX, name, kind, mode))
        if name.startswith("/") or ".." in Path(name).parts:
            raise ReviewError("refusing an escaping path in the state tree: %r"
                              % name)
        out = dest / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(_git_bytes(["cat-file", "blob", oid], state_repo))
        written.append(name)

    names = set(written)
    missing = [f for f in STATE_TREE_REQUIRED if f not in names]
    if missing:
        raise ReviewError(
            "the %s/ tree at this commit is missing %s — there is nothing to "
            "review" % (STATE_PREFIX, ", ".join(missing)))
    unexpected = sorted(
        n for n in names
        if n not in STATE_TREE_REQUIRED
        and n.split("/", 1)[0] not in STATE_TREE_DIRS)
    if unexpected:
        raise ReviewError(
            "the %s/ tree at this commit carries unexpected file(s): %s.\n"
            "A formal packet incorporates exactly the evidence the state branch "
            "committed, so an unrecognised file is a refusal rather than "
            "something to skip quietly." % (STATE_PREFIX, ", ".join(unexpected)))
    return dest


# ── derivations mirrored from the adapter ────────────────────────────────────

def slug_published_date(url: str):
    m = re.search(r"/latest-releases/(\d{1,2})([a-z]{3})(\d{2})[-_]", url)
    if not m:
        return None
    mon = _MONTHS.get(m.group(2))
    if not mon:
        return None
    try:
        return date(2000 + int(m.group(3)), mon, int(m.group(1))).isoformat()
    except ValueError:
        return None


def publication_kind(url: str) -> str:
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    token = re.sub(r"^\d{1,2}[a-z]{3}\d{2}[-_]", "", tail)
    token = re.sub(r"\d+$", "", token)
    return KINDS.get(token, "other")


# ── input safety ─────────────────────────────────────────────────────────────

def assert_safe_state_dir(state_dir: Path) -> None:
    state_dir = state_dir.resolve()
    if not state_dir.is_dir():
        raise ReviewError("state dir does not exist: %s" % state_dir)
    if state_dir == REPO_ROOT or REPO_ROOT in state_dir.parents:
        raise ReviewError(
            "refusing a state dir inside the repository: %s" % state_dir)
    for forbidden in ("pla_watch.db", "output"):
        if (state_dir / forbidden).exists():
            raise ReviewError(
                "refusing a state dir that contains %s — that is production, "
                "not shadow state: %s" % (forbidden, state_dir))
    if not (state_dir / "shadow.db").is_file():
        raise ReviewError("no shadow.db in %s" % state_dir)


def assert_safe_out_dir(out_dir: Path, allow_tracked: bool) -> None:
    out_dir = out_dir.resolve()
    if allow_tracked:
        return
    if out_dir == REPO_ROOT or REPO_ROOT in out_dir.parents:
        raise ReviewError(
            "refusing to write a review package inside the repository: %s\n"
            "Review evidence is not source. Pass --allow-tracked-destination "
            "only from a test." % out_dir)


def hash_inputs(state_dir: Path) -> dict:
    out = {}
    for p in sorted(state_dir.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(state_dir))] = hashlib.sha256(
                p.read_bytes()).hexdigest()
    return out


# ── loading ──────────────────────────────────────────────────────────────────

def open_readonly(db_path: Path) -> sqlite3.Connection:
    """Immutable: no lock, no journal, and no sidecar can appear."""
    return sqlite3.connect(
        "file://%s?mode=ro&immutable=1" % db_path.resolve(), uri=True)


def load_ledgers(state_dir: Path) -> list:
    entries = []
    for path in sorted((state_dir / "ledger").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ReviewError("ledger %s is not valid JSON: %s" % (path.name, exc))
        missing = [f for f in LEDGER_REQUIRED if f not in data]
        if missing:
            raise ReviewError(
                "ledger %s is missing required field(s): %s — refusing to "
                "review an unrecognised ledger format"
                % (path.name, ", ".join(missing)))
        data["_filename"] = path.name
        entries.append(data)
    if not entries:
        raise ReviewError("no ledgers in %s" % (state_dir / "ledger"))
    entries.sort(key=lambda e: (e["finished_utc"], str(e["run_id"])))
    return entries


def expected_ledger_filename(entry: dict) -> str:
    return "%s-%s.json" % (
        entry["finished_utc"].replace(":", "").replace("-", ""), entry["run_id"])


def expected_result(entry: dict):
    """
    The collector's own decision tree, re-evaluated.

    Only applies to runs that reached the storage loop — an early exit from
    discovery never sets `stored_total`, and its result is a property of
    discovery rather than of these counts.
    """
    if "stored_total" not in entry:
        return None
    if entry["access_failures"]:
        return st.AUTH_FAILURE
    if entry["fetch_failures"] and not entry["inserted"] and not entry["duplicates"]:
        return st.FETCH_FAILURE
    if entry["extraction_failures"] and not entry["inserted"] and not entry["duplicates"]:
        return st.EXTRACTION_FAILURE
    if entry["inserted"]:
        return st.OK
    if entry["duplicates"]:
        return st.OK_ALL_DUPLICATES
    return st.OK_NO_PUBLICATIONS


# ── validation ───────────────────────────────────────────────────────────────

def validate(state_dir: Path, ledgers: list, con: sqlite3.Connection,
             db_sha: str) -> tuple:
    """Returns (anomalies, facts). Anomalies are strings; facts feed the report."""
    a = []
    facts = {}

    # -- schema ---------------------------------------------------------------
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if not EXPECTED_TABLES <= tables:
        raise ReviewError("unknown schema: expected tables %s, found %s"
                          % (sorted(EXPECTED_TABLES), sorted(tables)))
    cols = tuple(r[1] for r in con.execute("PRAGMA table_info(shadow_records)"))
    if cols != EXPECTED_COLUMNS:
        raise ReviewError(
            "unknown shadow_records shape — refusing to review.\n  expected %s\n"
            "  found    %s" % (list(EXPECTED_COLUMNS), list(cols)))
    facts["integrity"] = con.execute("PRAGMA integrity_check").fetchone()[0]
    if facts["integrity"] != "ok":
        a.append("database integrity_check returned %r" % facts["integrity"])
    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    facts["foreign_keys"] = "clean" if not fk else "%d violation(s)" % len(fk)
    if fk:
        a.append("foreign key violations: %d" % len(fk))

    # -- clock ----------------------------------------------------------------
    clock_path = state_dir / "clock.json"
    if not clock_path.is_file():
        raise ReviewError("no clock.json — the shadow clock has not started")
    try:
        clock = json.loads(clock_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ReviewError("clock.json is not valid JSON: %s" % exc)
    for field in ("day_zero_utc", "day_zero_run_id"):
        if field not in clock:
            raise ReviewError("clock.json is missing %s" % field)
    facts["clock"] = clock
    try:
        day_zero = datetime.fromisoformat(clock["day_zero_utc"])
    except ValueError as exc:
        raise ReviewError("clock.json day_zero_utc is unparseable: %s" % exc)

    zero_runs = [e for e in ledgers if str(e["run_id"]) == str(clock["day_zero_run_id"])]
    if not zero_runs:
        a.append("clock names day-zero run %s, which has no ledger"
                 % clock["day_zero_run_id"])
    else:
        if zero_runs[0]["finished_utc"] != clock["day_zero_utc"]:
            a.append("day-zero timestamp mismatch: clock says %s, ledger %s says %s"
                     % (clock["day_zero_utc"], zero_runs[0]["run_id"],
                        zero_runs[0]["finished_utc"]))
        first_ok = next((e for e in ledgers if e["result"] in TERMINAL_OK), None)
        if first_ok and str(first_ok["run_id"]) != str(clock["day_zero_run_id"]):
            a.append("clock was not initialised by the first successful run: "
                     "first success is %s, clock names %s"
                     % (first_ok["run_id"], clock["day_zero_run_id"]))

    # -- ledgers --------------------------------------------------------------
    seen_ids = {}
    prev_finished = None
    for e in ledgers:
        rid, name = str(e["run_id"]), e["_filename"]
        if name != expected_ledger_filename(e):
            a.append("ledger filename %s does not match its contents "
                     "(expected %s)" % (name, expected_ledger_filename(e)))
        if rid in seen_ids:
            a.append("duplicate run id %s in %s and %s" % (rid, seen_ids[rid], name))
        seen_ids[rid] = name
        if e["result"] not in st.ALL_STATUSES:
            a.append("%s: unrecognised result %r" % (name, e["result"]))
        expected_health = "ok" if e["result"] in TERMINAL_OK else "fail"
        if e["health"] != expected_health:
            a.append("%s: health %r disagrees with result %r (expected %r)"
                     % (name, e["health"], e["result"], expected_health))
        want = expected_result(e)
        if want is not None and want != e["result"]:
            a.append("%s: counts imply %r but the ledger records %r"
                     % (name, want, e["result"]))
        try:
            finished = datetime.fromisoformat(e["finished_utc"])
        except ValueError:
            a.append("%s: unparseable finished_utc %r" % (name, e["finished_utc"]))
            continue
        if prev_finished and finished < prev_finished:
            a.append("%s: ledgers are not chronological" % name)
        prev_finished = finished
        # shadow_day recomputation
        if e["result"] in TERMINAL_OK:
            want_day = (finished - day_zero).days
            if e["shadow_day"] != want_day:
                a.append("%s: shadow_day is %r but %d complete 24-hour periods "
                         "have elapsed since day zero"
                         % (name, e["shadow_day"], want_day))
        elif e["shadow_day"] is not None:
            a.append("%s: failed run advanced the clock (shadow_day=%r)"
                     % (name, e["shadow_day"]))

    # -- state hash chain -----------------------------------------------------
    prev_after = None
    for i, e in enumerate(ledgers):
        before, after = e["state_sha256_before"], e["state_sha256_after"]
        if i == 0:
            if before is not None and before != prev_after:
                a.append("%s: first ledger declares a prior state hash %s"
                         % (e["_filename"], before[:12]))
        elif before != prev_after:
            a.append("%s: state chain broken — declares before=%s, previous "
                     "run ended at %s" % (e["_filename"],
                                          (before or "None")[:12],
                                          (prev_after or "None")[:12]))
        if e["result"] == st.OK_ALL_DUPLICATES and before != after:
            a.append("%s: a duplicate-only run changed the database "
                     "(%s -> %s)" % (e["_filename"], (before or "None")[:12],
                                     (after or "None")[:12]))
        prev_after = after
    facts["chain_final"] = prev_after
    if prev_after and prev_after != db_sha:
        a.append("the shadow database on disk (%s) does not match the last "
                 "ledger's after-hash (%s)" % (db_sha[:12], prev_after[:12]))

    # -- scheduled-day continuity --------------------------------------------
    days = sorted({datetime.fromisoformat(e["finished_utc"]).date()
                   for e in ledgers})
    gaps = []
    for x, y in zip(days, days[1:]):
        if (y - x).days > 1:
            gaps += [(x + timedelta(days=n)).isoformat()
                     for n in range(1, (y - x).days)]
    facts["observed_days"] = [d.isoformat() for d in days]
    facts["missing_days"] = gaps
    for g in gaps:
        a.append("no ledger for %s, inside the observed collection period" % g)
    return a, facts


def validate_records(con: sqlite3.Connection, ledgers: list) -> tuple:
    a = []
    rows = [dict(zip(EXPECTED_COLUMNS, r)) for r in con.execute(
        "SELECT %s FROM shadow_records ORDER BY url" % ", ".join(EXPECTED_COLUMNS))]
    by_url, by_title = {}, {}
    for r in rows:
        flags = []
        for field in REQUIRED_NON_NULL:
            if r[field] in (None, ""):
                flags.append("missing:%s" % field)
        if r["url"] in by_url:
            a.append("duplicate canonical URL in the database: %s" % r["url"])
        by_url[r["url"]] = r
        if not RELEASE_RE.match(r["url"] or ""):
            flags.append("url:not-canonical")
        want_date = slug_published_date(r["url"] or "")
        if want_date is None:
            flags.append("date:unparseable-slug")
        elif want_date != r["published_date"]:
            flags.append("date:slug-says-%s" % want_date)
        want_kind = publication_kind(r["url"] or "")
        if want_kind != r["publication_kind"]:
            flags.append("kind:slug-says-%s" % want_kind)
        body = r["text_original"] or ""
        if not body.strip():
            flags.append("body:empty")
        elif len(body) < COLLECTOR_MIN_BODY_CHARS:
            flags.append("body:below-collector-floor-%d" % len(body))
        lowered = body.lower()
        for marker in STUB_MARKERS:
            if marker in lowered:
                flags.append("body:stub-marker:%s" % marker.replace(" ", "-"))
                break
        recomputed = hashlib.sha256(body.encode("utf-8")).hexdigest()
        if recomputed != r["content_sha256"]:
            flags.append("hash:mismatch")
        if (r["source_slug"] or "") != "sg_mindef_releases":
            flags.append("source:foreign-%s" % r["source_slug"])
        r["_flags"] = flags
        by_title.setdefault((r["title_original"] or "").strip(), []).append(r["url"])
        for f in flags:
            a.append("%s: %s" % (r["url"], f))

    collisions = {t: u for t, u in by_title.items() if len(u) > 1}
    for title, urls in sorted(collisions.items()):
        if len(set(urls)) != len(urls):
            a.append("title %r maps to a repeated URL" % title[:60])
    return rows, collisions, a


# ── review queue ─────────────────────────────────────────────────────────────

def build_queue(rows: list, ledgers: list, review_all: bool,
                since_ledger: str = None) -> tuple:
    """
    Returns (selected_urls, reasons). Deterministic: every rule is a property
    of the data, and the remainder is chosen by content hash, not by chance.
    """
    reasons = {}

    def mark(url, why):
        reasons.setdefault(url, []).append(why)

    if review_all:
        for r in rows:
            mark(r["url"], "review-all")
        return sorted(reasons), reasons

    since_runs = None
    if since_ledger:
        names = [e["_filename"] for e in ledgers]
        if since_ledger not in names:
            raise ReviewError("--since-ledger %r is not a ledger in this state "
                              "(have: %s)" % (since_ledger, ", ".join(names)))
        idx = names.index(since_ledger)
        since_runs = {str(e["run_id"]) for e in ledgers[idx + 1:]}

    for r in rows:
        if since_runs is not None and str(r["first_seen_run"]) in since_runs:
            mark(r["url"], "new-since-%s" % since_ledger)
        if r["_flags"]:
            mark(r["url"], "anomaly:" + ",".join(r["_flags"]))

    by_title = {}
    for r in rows:
        by_title.setdefault((r["title_original"] or "").strip(), []).append(r)
    for title, group in by_title.items():
        if len(group) > 1:
            for r in group:
                mark(r["url"], "duplicate-title-group")

    by_kind = {}
    for r in rows:
        by_kind.setdefault(r["publication_kind"], []).append(r)
    for kind, group in sorted(by_kind.items()):
        pick = sorted(group, key=lambda x: x["url"])[0]
        mark(pick["url"], "kind-representative:%s" % kind)

    if rows:
        by_date = sorted(rows, key=lambda r: (r["published_date"], r["url"]))
        mark(by_date[0]["url"], "oldest")
        mark(by_date[-1]["url"], "newest")
        substantive = [r for r in rows
                       if len(r["text_original"] or "") >= COLLECTOR_MIN_BODY_CHARS]
        if substantive:
            by_len = sorted(substantive,
                            key=lambda r: (len(r["text_original"]), r["url"]))
            mark(by_len[0]["url"], "shortest-substantive-body")
            mark(by_len[-1]["url"], "longest-body")
        # Deterministic remainder: lowest content hashes not already queued.
        remainder = sorted((r for r in rows if r["url"] not in reasons),
                           key=lambda r: r["content_sha256"])
        for r in remainder[:max(0, min(5, len(remainder)))]:
            mark(r["url"], "hash-selected-remainder")
    return sorted(reasons), reasons


# ── package ──────────────────────────────────────────────────────────────────

def render_report(manifest: dict, ledgers: list, rows: list, collisions: dict,
                  anomalies: list, queue: list, reasons: dict,
                  checkpoint: str) -> str:
    L = []
    w = L.append
    w("# Singapore shadow review — %s" % checkpoint)
    w("")
    if manifest["formal"] and not manifest["publishable"]:
        w("> ## NOT PUBLISHABLE YET — the checkpoint has not arrived")
        w(">")
        w("> The state is pinned to its commit, but %s needs shadow_day >= %d"
          % (manifest["checkpoint"], CHECKPOINTS[manifest["checkpoint"]]))
        w("> and the latest ledger records shadow_day %s. Re-generate once a"
          % manifest["latest_shadow_day"])
        w("> run has recorded the day; the publisher refuses it until then.")
        w("")
    if not manifest["formal"]:
        w("> ## NOT PUBLISHABLE — rehearsal packet")
        w(">")
        w("> This package names no checkpoint and no shadow-state commit, so it")
        w("> identifies a corpus but not a point in the state branch's history.")
        w("> Its inputs were read from a working-tree copy that nothing")
        w("> verifies. It is a tooling rehearsal. Re-generate with")
        w("> `--state-repo`, `--state-commit` and `--checkpoint` to produce a")
        w("> packet whose bytes come from the committed tree itself.")
        w("")
    w("> **An unfilled report is not evidence of a completed review.** The")
    w("> automated checks below establish that the state is internally")
    w("> consistent. They do not establish that the stored records match what")
    w("> the ministry published. Only the reviewer sign-off section does that,")
    w("> and only once every field in it is filled in by a person.")
    w("")
    w("| | |")
    w("|---|---|")
    w("| Deterministic package id | `%s` |" % manifest["deterministic_sha256"])
    w("| Tool | `%s` v%s |" % (manifest["tool"], manifest["tool_version"]))
    if manifest["formal"]:
        w("| State commit (verified) | `%s` |" % manifest["state_commit"])
        w("| State tree | `%s` |" % manifest["state_tree"])
        w("| Reachable from | `%s` |" % manifest["state_ref"])
    w("| Provenance | %s |" % manifest["provenance"])
    w("| Collector commit (latest ledger) | `%s` |" % manifest["latest_collector_commit"])
    w("| Day zero | `%s` (run `%s`) |" % (manifest["day_zero_utc"],
                                          manifest["day_zero_run_id"]))
    w("| Latest ledger | `%s` |" % manifest["latest_ledger"])
    w("| Latest shadow_day | **%s** |" % manifest["latest_shadow_day"])
    w("| Ledgers | %d |" % manifest["ledger_count"])
    w("| Corpus | %d records, %s → %s |" % (
        manifest["corpus_count"], manifest["corpus_range"][0],
        manifest["corpus_range"][1]))
    w("| Database integrity | %s |" % manifest["database_integrity"])
    w("| Foreign keys | %s |" % manifest["foreign_keys"])
    w("| State-hash chain | %s |" % manifest["state_chain_verdict"])
    w("| Anomalies | %d |" % len(anomalies))
    w("")
    w("## Automated integrity")
    w("")
    if anomalies:
        w("**%d anomaly/anomalies. Each must be explained before this checkpoint "
          "can pass.**" % len(anomalies))
        w("")
        for x in anomalies:
            w("- %s" % x)
    else:
        w("No anomalies. Schema, clock, ledger identity, result taxonomy, "
          "state-hash chain, `shadow_day` arithmetic, record fields, canonical "
          "URL uniqueness and content hashes all reconcile.")
    w("")
    w("## Run chronology")
    w("")
    w("| Ledger | Run | Finished (UTC) | Day | Result | Health | Disc | Sel | Retr | Ins | Dup | Fetch✗ | Extr✗ | Acc✗ |")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for e in ledgers:
        w("| `%s` | %s | %s | %s | `%s` | %s | %d | %d | %d | %d | %d | %d | %d | %d |" % (
            e["_filename"], e["run_id"], e["finished_utc"][:19],
            "—" if e["shadow_day"] is None else e["shadow_day"],
            e["result"], e["health"], e["discovered"], e["selected"],
            e["retrieved"], e["inserted"], e["duplicates"], e["fetch_failures"],
            e["extraction_failures"], e["access_failures"]))
    w("")
    w("## Count reconciliation")
    w("")
    w("| Ledger | inserted | cumulative | stored_total | agrees |")
    w("|---|---|---|---|---|")
    cum = 0
    for e in ledgers:
        cum += e["inserted"]
        stored = e.get("stored_total")
        ok = "—" if stored is None else ("yes" if stored == cum else "**NO**")
        w("| `%s` | %d | %d | %s | %s |" % (e["_filename"], e["inserted"], cum,
                                            "—" if stored is None else stored, ok))
    w("")
    w("Corpus in database: **%d**. Sum of insertions: **%d**." %
      (len(rows), cum))
    w("")
    w("## Corpus overview")
    w("")
    w("| Publication kind | Records |")
    w("|---|---|")
    for kind, n in sorted(manifest["publication_kinds"].items(),
                          key=lambda kv: (-kv[1], kv[0])):
        w("| %s | %d |" % (kind, n))
    w("| **total** | **%d** |" % len(rows))
    w("")
    lens = sorted(len(r["text_original"] or "") for r in rows)
    if lens:
        def pct(p):
            return lens[min(len(lens) - 1, int(round(p * (len(lens) - 1))))]
        w("Body length (characters): min **%d**, p25 %d, median %d, p75 %d, "
          "max **%d**." % (lens[0], pct(.25), pct(.5), pct(.75), lens[-1]))
        w("")
        w("The collector refuses a body under %d characters, so a shorter body "
          "here would contradict the collector that wrote it. No length is "
          "treated as proof of completeness — that is a reviewer judgement."
          % COLLECTOR_MIN_BODY_CHARS)
    w("")
    w("## Title collisions")
    w("")
    if collisions:
        w("Distinct publications may share a title. These are kept separate by "
          "canonical URL and must be confirmed distinct by a reviewer.")
        w("")
        w("| Title | URLs |")
        w("|---|---|")
        for title, urls in sorted(collisions.items()):
            w("| %s | %s |" % (title[:70].replace("|", "\\|"),
                               "<br>".join("`%s`" % u for u in sorted(urls))))
    else:
        w("None. Every stored title is unique in this corpus.")
    w("")
    w("## Content-change history")
    w("")
    changed = [e for e in ledgers if e.get("inserted") and e["result"] == st.OK]
    w("Records are first-writer-wins on canonical URL, so the collector never "
      "rewrites a stored body. Insertions by run:")
    w("")
    for e in changed:
        w("- `%s` — %d inserted" % (e["_filename"], e["inserted"]))
    if not changed:
        w("- none")
    w("")
    w("## Human review queue — %d of %d records" % (len(queue), len(rows)))
    w("")
    w("Selection: `%s`. Every reason is a property of the data, so the same "
      "state always produces the same queue. This is a targeted queue, **not a "
      "statistically representative sample**, and no inference about "
      "unreviewed records follows from it." % QUEUE_ALGORITHM)
    w("")
    for url in queue:
        r = next(x for x in rows if x["url"] == url)
        w("### `%s`" % url)
        w("")
        w("- **Title:** %s" % (r["title_original"] or "").replace("|", "\\|"))
        w("- **Stored date:** %s · **kind:** %s · **body:** %d chars"
          % (r["published_date"], r["publication_kind"],
             len(r["text_original"] or "")))
        w("- **Content sha256:** `%s`" % r["content_sha256"])
        w("- **First seen in run:** %s" % (r["first_seen_run"] or "—"))
        w("- **Queued because:** %s" % "; ".join(reasons[url]))
        if r["_flags"]:
            w("- **Flags:** %s" % ", ".join(r["_flags"]))
        w("")
        w("| Check | Reviewer entry |")
        w("|---|---|")
        w("| Source page opened | |")
        w("| Title matches the page | |")
        w("| Publication date matches the page | |")
        w("| Stored body is the complete document | |")
        w("| Canonical URL is correct | |")
        w("| Publication kind is reasonable | |")
        w("| No access-denial or template text stored | |")
        w("| Notes | |")
        w("")
    w("## Reviewer sign-off")
    w("")
    w("This checkpoint is complete only when every row above is filled in and "
      "this block is signed. Until then the package is a request for a review, "
      "not a record of one.")
    w("")
    w("| Field | Entry |")
    w("|---|---|")
    w("| Checkpoint | %s |" % checkpoint)
    w("| Reviewer identity | |")
    w("| Review completion timestamp (UTC) | |")
    w("| Records reviewed against source | |")
    w("| Anomalies accepted, with reasons | |")
    w("| Verdict (continue / pause / stop) | |")
    w("")
    return "\n".join(L) + "\n"


def signoff_template(manifest: dict, rows: list, queue: list) -> dict:
    """
    The structured form a reviewer fills in. Deliberately separate from the
    automated evidence: the package says what was presented, this says what a
    person concluded, and keeping them apart is what lets each be checked
    against the other.
    """
    return {
        "signoff_schema": SIGNOFF_SCHEMA,
        "desk": manifest["desk"],
        "checkpoint": manifest["checkpoint"],
        "automated_package_id": manifest["deterministic_sha256"],
        "state_commit": manifest["state_commit"],
        "latest_ledger_run_id": manifest["latest_run_id"],
        "latest_shadow_day": manifest["latest_shadow_day"],
        "queue_algorithm": manifest["queue_algorithm"],
        "review_mode": manifest["review_mode"],
        "records_required": len(manifest["required_review_records"]),
        "reviewer": "",
        "review_started_utc": "",
        "review_completed_utc": "",
        "records": [
            {
                "identity": url,
                "source_page_opened": None,
                "title_matches": None,
                "publication_date_matches": None,
                "canonical_url_matches": None,
                "body_appears_complete": None,
                "kind_is_reasonable": None,
                "no_denial_or_template_stored": None,
                "note": "",
            } for url in manifest["required_review_records"]
        ],
        "anomalies": [
            {"anomaly": x, "disposition": ""} for x in manifest["anomalies"]
        ],
        "verdict": "",
        "notes": "",
        "attestation": "",
    }


def build(state_dir: Path, out_dir: Path, as_of: str, review_all: bool,
          since_ledger: str, allow_tracked: bool, state_commit: str = None,
          checkpoint: str = None, state_repo: Path = None,
          state_ref: str = STATE_BRANCH) -> dict:
    """
    Two modes, and the difference between them is the whole point.

    A **rehearsal** reads `--state-dir`: an ordinary directory, trusted as-is,
    useful for exercising the tooling. It is labelled NOT PUBLISHABLE.

    A **formal** packet reads `--state-repo`: the `state/` tree is exported
    from the Git object identified by `--state-commit`, and those exported
    bytes are the ones hashed, analysed and packaged. Nothing a working tree
    contains can substitute for them, so `--state-dir` is refused in this mode
    rather than quietly ignored.
    """
    if checkpoint is not None and checkpoint not in CHECKPOINTS:
        raise ReviewError("unknown checkpoint %r; expected one of %s"
                          % (checkpoint, ", ".join(sorted(CHECKPOINTS))))
    if state_commit is not None and checkpoint is None:
        raise ReviewError("--state-commit requires --checkpoint (%s)"
                          % ", ".join(sorted(CHECKPOINTS)))
    if checkpoint is not None and state_commit is None:
        raise ReviewError(
            "--checkpoint requires --state-commit: a formal packet must "
            "name the exact shadow-state commit it reviewed")

    formal = bool(state_commit and checkpoint)
    provenance = None
    export_root = None
    if formal:
        if state_repo is None:
            raise ReviewError(
                "a formal packet requires --state-repo: the state clone whose "
                "Git objects prove what --state-commit contains.\n"
                "Comparing a supplied SHA against another supplied field is "
                "not provenance. Do not remove .git before generating the "
                "packet.")
        if state_dir is not None:
            raise ReviewError(
                "--state-dir and --state-repo are mutually exclusive. A formal "
                "packet is derived from the committed tree, so a working-tree "
                "copy is refused rather than trusted.")
        repo = resolve_state_repo(state_repo)
        provenance = verify_state_commit(repo, state_commit, state_ref)
        export_root = Path(tempfile.mkdtemp(prefix="shadow-state-"))
        state_dir = export_state_tree(repo, state_commit,
                                      export_root / STATE_PREFIX)
    elif state_dir is None:
        raise ReviewError("--state-dir is required for a rehearsal packet")

    try:
        return _build(Path(state_dir), out_dir, as_of, review_all, since_ledger,
                      allow_tracked, state_commit, checkpoint, provenance,
                      skip_state_dir_check=formal)
    finally:
        if export_root is not None:
            shutil.rmtree(export_root, ignore_errors=True)


def _build(state_dir: Path, out_dir: Path, as_of: str, review_all: bool,
           since_ledger: str, allow_tracked: bool, state_commit: str,
           checkpoint: str, provenance: dict,
           skip_state_dir_check: bool) -> dict:
    if not skip_state_dir_check:
        assert_safe_state_dir(state_dir)
    assert_safe_out_dir(out_dir, allow_tracked)
    state_dir, out_dir = state_dir.resolve(), out_dir.resolve()

    before = hash_inputs(state_dir)
    db_path = state_dir / "shadow.db"
    db_sha = before["shadow.db"]

    ledgers = load_ledgers(state_dir)
    con = open_readonly(db_path)
    try:
        anomalies, facts = validate(state_dir, ledgers, con, db_sha)
        rows, collisions, record_anomalies = validate_records(con, ledgers)
    finally:
        con.close()
    anomalies = anomalies + record_anomalies

    queue, reasons = build_queue(rows, ledgers, review_all, since_ledger)

    latest = ledgers[-1]
    successes = [e for e in ledgers if e["result"] in TERMINAL_OK]
    kinds = {}
    for r in rows:
        kinds[r["publication_kind"]] = kinds.get(r["publication_kind"], 0) + 1
    dates = sorted(r["published_date"] for r in rows)

    ledger_hashes = {k: v for k, v in before.items() if k.startswith("ledger/")}
    ledger_set_sha256 = hashlib.sha256(json.dumps(
        ledger_hashes, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()

    manifest = {
        "tool": "scripts/review_shadow_state.py",
        "tool_version": TOOL_VERSION,
        "queue_algorithm": QUEUE_ALGORITHM,
        "signoff_schema": SIGNOFF_SCHEMA,
        "as_of": as_of,
        # ── formal binding ───────────────────────────────────────────────
        # What exactly was reviewed. A packet without a state commit names a
        # corpus but not a point in the state branch's history, so it can
        # describe evidence it cannot pin down. Such a packet is usable for a
        # rehearsal and is refused for publication.
        "desk": DESK_IDENTITY,
        "checkpoint": checkpoint,
        "state_commit": state_commit,
        # The tree the bytes actually came from, and the ref they are reachable
        # from. `state_commit` alone is a claim; these are what was verified.
        "state_tree": (provenance or {}).get("state_tree"),
        "state_ref": (provenance or {}).get("state_ref"),
        "provenance": ("git-verified-tree/1" if provenance
                       else "unverified-working-copy"),
        "formal": bool(state_commit and checkpoint),
        # Formal is about provenance; publishable is also about time. A day-2
        # corpus can be pinned to its commit perfectly well and still cannot be
        # filed as a Day 7 review, and the publisher refuses it. Saying
        # "publishable" here would send a reviewer through a checkpoint the
        # publisher was always going to turn away.
        "publishable": bool(
            state_commit and checkpoint
            and (successes[-1]["shadow_day"] if successes else None) is not None
            and successes[-1]["shadow_day"] >= CHECKPOINTS[checkpoint]),
        "review_mode": "complete-corpus" if review_all else "focused-queue",
        "state_dir_name": state_dir.name,
        "input_sha256": before,
        "ledger_set_sha256": ledger_set_sha256,
        "clock_sha256": before.get("clock.json"),
        "shadow_db_sha256": before.get("shadow.db"),
        "day_zero_utc": facts["clock"]["day_zero_utc"],
        "day_zero_run_id": facts["clock"]["day_zero_run_id"],
        "latest_ledger": latest["_filename"],
        "latest_run_id": latest["run_id"],
        "latest_collector_commit": latest["collector_commit"],
        "latest_shadow_day": (successes[-1]["shadow_day"] if successes else None),
        "ledger_count": len(ledgers),
        "corpus_count": len(rows),
        "corpus_range": [dates[0], dates[-1]] if dates else [None, None],
        "publication_kinds": kinds,
        "observed_days": facts["observed_days"],
        "missing_days": facts["missing_days"],
        "database_integrity": facts["integrity"],
        "foreign_keys": facts["foreign_keys"],
        "state_chain_final_sha256": facts["chain_final"],
        "state_chain_verdict": ("coherent" if not any(
            "state chain broken" in x or "does not match the last ledger" in x
            for x in anomalies) else "BROKEN"),
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "review_queue_size": len(queue),
        "review_queue": queue,
        # The exact identities a sign-off must answer for. Under --review-all
        # this is the whole corpus; under a focused queue it is the queue.
        "required_review_records": (sorted(r["url"] for r in rows)
                                    if review_all else queue),
        "automated_checks_are_not_the_human_review": (
            "These checks establish internal consistency only. The checkpoint "
            "is complete only when a person has compared queued records with "
            "the ministry's own pages and signed the report."),
    }

    checkpoint_label = "%s — shadow_day %s (as of %s)" % (
        checkpoint or "rehearsal (no checkpoint)",
        manifest["latest_shadow_day"], as_of)
    inventory = []
    for r in rows:
        inventory.append({
            "identity": r["url"],
            "canonical_url": r["url"],
            "title": r["title_original"],
            "published_date": r["published_date"],
            "publication_kind": r["publication_kind"],
            "body_chars": len(r["text_original"] or ""),
            "content_sha256": r["content_sha256"],
            "capture_sha256": r["capture_sha256"],
            "retrieved_at": r["retrieved_at"],
            "first_seen_run": r["first_seen_run"],
            "flags": r["_flags"],
            "selected_for_review": r["url"] in reasons,
            "selected_because": reasons.get(r["url"], []),
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    inv_text = "".join(json.dumps(x, sort_keys=True) + "\n" for x in inventory)
    (out_dir / "record_inventory.jsonl").write_text(inv_text, encoding="utf-8")

    # The deterministic identity covers content only: no wall clock, no paths.
    # It includes the desk, checkpoint and state commit, so two packets over the
    # same corpus at different checkpoints are not the same package.
    deterministic = dict(manifest)
    payload = json.dumps({"manifest": deterministic, "inventory": inventory},
                         sort_keys=True, separators=(",", ":"))
    manifest["deterministic_sha256"] = hashlib.sha256(
        payload.encode("utf-8")).hexdigest()

    template = signoff_template(manifest, rows, queue)
    template_text = json.dumps(template, indent=1, sort_keys=True) + "\n"
    (out_dir / "signoff_template.json").write_text(template_text,
                                                   encoding="utf-8")

    report = render_report(manifest, ledgers, rows, collisions, anomalies,
                           queue, reasons, checkpoint_label)
    (out_dir / "review_report.md").write_text(report, encoding="utf-8")

    manifest["artifact_sha256"] = {
        "record_inventory.jsonl": hashlib.sha256(
            inv_text.encode("utf-8")).hexdigest(),
        "review_report.md": hashlib.sha256(report.encode("utf-8")).hexdigest(),
        "signoff_template.json": hashlib.sha256(
            template_text.encode("utf-8")).hexdigest(),
    }
    (out_dir / "review_manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    # Wall clock and local paths, kept OUT of the packet.
    #
    # `generated` used to live in the manifest, excluded from the package id.
    # That made one package id name many byte sequences: two honest runs of the
    # same commit produced identical ids and different manifests, so an
    # independently regenerated packet was refused as conflicting content and a
    # completed-review id pointed at no particular bytes. It also wrote the
    # reviewer's absolute filesystem paths into permanently preserved evidence.
    # A formal package is content-addressed; when it was generated belongs in
    # the receipt and the commit that preserves it.
    (out_dir / "generation_context.json").write_text(
        json.dumps({
            "deterministic_sha256": manifest["deterministic_sha256"],
            "generated_utc": datetime.now(timezone.utc)
                             .isoformat(timespec="seconds"),
            "state_dir": str(state_dir),
            "out_dir": str(out_dir),
            "not_part_of_the_package": (
                "This file is not preserved and is not covered by the package "
                "id. The package is the manifest, the report and the "
                "inventory."),
        }, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    after = hash_inputs(state_dir)
    if after != before:
        changed = sorted(set(before) ^ set(after)) or [
            k for k in before if before[k] != after.get(k)]
        raise ReviewError(
            "input state changed during review — the package is void: %s"
            % ", ".join(changed))
    for sidecar in ("shadow.db-wal", "shadow.db-shm"):
        if (state_dir / sidecar).exists():
            raise ReviewError("a %s appeared beside the input database" % sidecar)
    return manifest


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument("--state-dir", default=None,
                   help="REHEARSAL ONLY: a copy of shadow/singapore-mindef "
                        "state/, trusted as-is. Never produces a publishable "
                        "packet.")
    p.add_argument("--state-repo", default=None,
                   help="the state clone (with its .git) whose objects prove "
                        "what --state-commit contains. Required for a formal "
                        "packet: state/ is exported from the commit itself.")
    p.add_argument("--state-ref", default=STATE_BRANCH,
                   help="the trusted state ref --state-commit must be "
                        "reachable from (default: %s)" % STATE_BRANCH)
    p.add_argument("--out", required=True, help="review package destination")
    p.add_argument("--as-of", default=None,
                   help="review date (YYYY-MM-DD); defaults to today UTC. "
                        "Pass it explicitly for reproducible packages.")
    p.add_argument("--review-all", action="store_true",
                   help="queue every record (appropriate while the corpus is small)")
    p.add_argument("--since-ledger", default=None,
                   help="incremental review: queue records first seen after "
                        "this ledger filename")
    p.add_argument("--checkpoint", default=None, choices=sorted(CHECKPOINTS),
                   help="formal checkpoint identity; required with --state-commit")
    p.add_argument("--state-commit", default=None,
                   help="full 40-character commit SHA of the shadow-state "
                        "branch being reviewed. Verified against --state-repo; "
                        "required for a publishable packet.")
    p.add_argument("--allow-tracked-destination", action="store_true",
                   help=argparse.SUPPRESS)
    args = p.parse_args(argv)

    as_of = args.as_of or datetime.now(timezone.utc).date().isoformat()
    if args.state_dir is None and args.state_repo is None:
        print("review refused: pass --state-repo (formal) or --state-dir "
              "(rehearsal)", file=sys.stderr)
        return 2
    try:
        m = build(Path(args.state_dir) if args.state_dir else None,
                  Path(args.out), as_of, args.review_all,
                  args.since_ledger, args.allow_tracked_destination,
                  args.state_commit, args.checkpoint,
                  Path(args.state_repo) if args.state_repo else None,
                  args.state_ref)
    except ReviewError as exc:
        print("review refused: %s" % exc, file=sys.stderr)
        return 2

    print("corpus         : %d records, %s → %s" % (
        m["corpus_count"], m["corpus_range"][0], m["corpus_range"][1]))
    print("ledgers        : %d, latest %s (shadow_day %s)" % (
        m["ledger_count"], m["latest_ledger"], m["latest_shadow_day"]))
    print("state chain    : %s" % m["state_chain_verdict"])
    print("anomalies      : %d" % m["anomaly_count"])
    print("review queue   : %d of %d" % (m["review_queue_size"], m["corpus_count"]))
    print("package id     : %s" % m["deterministic_sha256"])
    print("checkpoint     : %s" % (m["checkpoint"] or "— (rehearsal)"))
    print("state commit   : %s" % (m["state_commit"] or "— (rehearsal)"))
    print("state tree     : %s" % (m["state_tree"] or "— (unverified)"))
    print("provenance     : %s" % m["provenance"])
    print("publishable    : %s" % ("yes" if m["publishable"] else
                                   "NO — rehearsal packet"))
    print("written to     : %s" % args.out)
    if m["anomaly_count"]:
        print("\nAnomalies must be explained before the checkpoint can pass.")
    print("\nThe automated checks are not the review. Fill in review_report.md.")
    return 1 if m["anomaly_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
