#!/usr/bin/env python3
"""
Versioned correction overlay for a shadow state branch.

Why an overlay rather than an UPDATE
------------------------------------
The state branch is hash-chained at two levels, and both forbid touching
`shadow.db`:

  * every ledger entry records `state_sha256_before` and `state_sha256_after`,
    the SHA-256 of the whole database file. Singapore's chain runs unbroken
    across all 32. Change one byte and the tip no longer matches the hash the
    last run published, the next run's `before` assertion fails, and the only
    way to reconcile is to rewrite ledgers that are append-only by design.

  * every ledger also records the `content_sha256` of each record it inserted.
    A rewritten body either leaves that hash describing text that no longer
    exists, or takes a value no ledger ever recorded.

So a correction is published *beside* the database, append-only and chained,
and a reader materialises corrected text on the way out. Stored values remain
the original evidence, permanently recoverable.

Why transformations rather than a refetch
-----------------------------------------
Live pages move. Of the 29 records carrying `&#x27;`, 26 are still
byte-identical to what was captured and 3 have drifted. Refetch-and-overwrite
would rewrite those 3 with newer text while claiming to fix an apostrophe.

The two defects, and the two very different transformations
-----------------------------------------------------------
1. **Entities.** `visible_text()` knew six entities and not `&#x27;`, so 84
   literal sequences survived into 29 bodies; `document_title()` decoded
   nothing at all, so 4 titles kept raw attribute text.

2. **Charset.** The ministry serves `text/html` with no charset, so `requests`
   decoded UTF-8 as ISO-8859-1. 544 mojibake sequences across 56 bodies and 11
   titles.

The second is *not* a global `latin-1 -> utf-8` round trip applied on faith,
and this file refuses to pretend otherwise. Bodies and titles were produced by
different code paths and need different rules:

  * a **body** went through `visible_text`, which collapsed whitespace *after*
    the mis-decode. Python's `\\s` matches U+0085 and U+00A0, so the second byte
    of every non-breaking space was eaten and only an orphan U+00C2 survived —
    all 176 of them followed by whitespace or end of string. The orphan must be
    removed before the round trip, and the collapse must run again afterwards,
    or the result carries a doubled space the correct extraction does not have.

  * a **title** came from the `og:title` attribute, which was never collapsed
    and never decoded. No stored title contains U+00C2 at all. It round-trips
    untouched and must *not* be re-collapsed.

The same collapse destroyed bytes inside two Mandarin passages, where a
continuation byte of a CJK character was itself U+00A0. Those bodies cannot be
repaired from stored text by any transformation, and `--emit` refuses them
rather than guessing a byte.

Evidence
--------
Every emitted record carries an evidence tier:

  * `live-confirmed` — re-extracting the live page with the fixed extractor
    produces exactly this corrected value.
  * `intrinsic` — the live page has drifted since capture, so an exact
    comparison is unavailable, but the stored substring contains a C1 control
    character (U+0080–U+009F), which cannot occur in legitimate extracted
    prose. The transformation is provably safe for that exact substring.

Nothing is emitted on no evidence at all.

This tool never opens the database for writing.
"""

from __future__ import annotations

import argparse
import codecs
import glob
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Optional

TOOL = "scripts/correct_shadow_bodies.py"
TOOL_VERSION = "2.0.0"
SCHEMA = "shadow-correction-overlay/2"

FIELDS = ("body", "title")
COLUMN = {"body": "text_original", "title": "title_original"}

#: The entity substitution. Not an unescape: the stored text has already been
#: through the old six-entity table, so unescaping again would double-decode.
HEX_APOSTROPHE = [["&#x27;", "'"]]

#: The construction where a literal substitution and a real re-extraction
#: disagree — `unescape` leaves it literal, the substitution would not.
AMBIGUOUS = "&amp;#x27;"

ENTITY_TOKEN = re.compile(r"&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")

MOJIBAKE_LEAD = chr(0xE2) + chr(0x80)
ORPHAN_NBSP = re.compile(chr(0xC2) + r"(?=\s|$)")
C1 = re.compile("[" + chr(0x80) + "-" + chr(0x9F) + "]")

APPROVED_KINDS = ("literal_replace_all", "html_unescape_once",
                  "mojibake_latin1_utf8")
EVIDENCE_TIERS = ("live-confirmed", "intrinsic")


# ── hashing and access ────────────────────────────────────────────────────────

def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_only(db: Path) -> sqlite3.Connection:
    """Immutable and read-only, so it cannot create -wal/-shm sidecars."""
    return sqlite3.connect("file:%s?mode=ro&immutable=1" % db.resolve(), uri=True)


def _known(encoding: str) -> bool:
    try:
        codecs.lookup(encoding)
        return True
    except LookupError:
        return False


# ── transformations ───────────────────────────────────────────────────────────

def apply_pairs(text: str, pairs) -> str:
    for find, repl in pairs:
        text = text.replace(find, repl)
    return text


def demojibake(text: str, field: str) -> Optional[str]:
    """Undo an ISO-8859-1 mis-decode. `None` if stored text cannot carry it."""
    if field == "body":
        stripped = ORPHAN_NBSP.sub("", text)
        try:
            fixed = stripped.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            return None
        return re.sub(r"\s+", " ", fixed).strip()
    try:
        return text.encode("latin-1").decode("utf-8").strip()
    except (UnicodeDecodeError, UnicodeEncodeError):
        return None


def apply_transformation(text: str, tr: dict, field: str) -> Optional[str]:
    kind = tr["kind"]
    if kind not in APPROVED_KINDS:
        raise SystemExit("unapproved transformation kind: %r" % kind)
    if kind == "literal_replace_all":
        return apply_pairs(text, tr["pairs"])
    if kind == "html_unescape_once":
        return unescape(text)
    return demojibake(text, field)


def has_mojibake(text: str) -> bool:
    return MOJIBAKE_LEAD in text or chr(0xC2) in text


# ── state helpers ─────────────────────────────────────────────────────────────

def ledger_entries(state: Path):
    return [Path(p) for p in sorted(glob.glob(str(state / "ledger" / "*.json")))]


def ledger_tip(state: Path):
    files = ledger_entries(state)
    if not files:
        raise SystemExit("no ledger entries under %s" % (state / "ledger"))
    return files[-1], json.loads(files[-1].read_text(encoding="utf-8"))


def corrections_dir(state: Path) -> Path:
    """Beside `state/`, never inside it.

    The review kit's state-tree allowlist is `clock.json`, `shadow.db` and
    `ledger/`, and an unrecognised file in that tree is a refusal by design.
    Putting the overlay inside `state/` would either break every formal packet
    or force that allowlist open. Keeping it as a sibling leaves the state tree
    hash untouched, so the existing Day-30 packet still reproduces byte for
    byte and stays exactly as valid as it was.
    """
    return state.parent / "corrections"


def existing_corrections(state: Path):
    d = corrections_dir(state)
    if not d.is_dir():
        return []
    return [Path(p) for p in sorted(glob.glob(str(d / "*.json")))]


def git(repo: Path, *args) -> str:
    out = subprocess.run(["git", "-C", str(repo)] + list(args),
                         capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else ""


def binding(state: Path, state_repo: Optional[Path]) -> dict:
    """Everything the overlay is pinned to."""
    db = state / "shadow.db"
    tip_path, tip = ledger_tip(state)
    b = {
        "database_sha256": sha256_file(db),
        "ledger_tip_file": tip_path.name,
        "ledger_tip_run_id": tip.get("run_id"),
        "ledger_entry_count": len(ledger_entries(state)),
        "state_commit": None,
        "state_tree": None,
    }
    if state_repo:
        b["state_commit"] = git(state_repo, "rev-parse", "HEAD") or None
        b["state_tree"] = git(state_repo, "rev-parse", "HEAD:state") or None
    return b


# ── emit ──────────────────────────────────────────────────────────────────────

def load_evidence(path: Optional[Path]) -> dict:
    if not path:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {r["url"]: r for r in raw}


def emit(state: Path, field: str, kind: str, reason: str, collector_commit: str,
         evidence_path: Optional[Path] = None, state_repo: Optional[Path] = None,
         out: Optional[Path] = None) -> dict:
    if field not in FIELDS:
        raise SystemExit("unknown field %r" % field)
    if kind not in APPROVED_KINDS:
        raise SystemExit("unapproved transformation kind: %r" % kind)

    db = state / "shadow.db"
    bind = binding(state, state_repo)
    _, tip = ledger_tip(state)
    if bind["database_sha256"] != tip["state_sha256_after"]:
        raise SystemExit(
            "refusing to emit: the database does not hash to what the last "
            "ledger published.\n  ledger %s\n  actual %s"
            % (tip["state_sha256_after"], bind["database_sha256"]))

    evidence = load_evidence(evidence_path)
    tr = {"kind": kind, "applies_to": "shadow_records." + COLUMN[field]}
    if kind == "literal_replace_all":
        tr["pairs"] = HEX_APOSTROPHE
        tr["equivalent_to"] = "re-extraction with the fixed visible_text"
    elif kind == "html_unescape_once":
        tr["equivalent_to"] = "re-extraction with the fixed document_title"
    else:
        tr["equivalent_to"] = "re-extraction from correctly decoded bytes"
        tr["steps"] = (["strip orphan U+00C2 before whitespace or end",
                        "encode latin-1", "decode utf-8",
                        "collapse whitespace", "strip"] if field == "body"
                       else ["encode latin-1", "decode utf-8", "strip"])

    con = read_only(db)
    meta = {u: (p, c, k) for u, p, c, k in con.execute(
        "select url, published_date, content_sha256, capture_sha256 "
        "from shadow_records")}
    con.close()

    # Corrections compose. A second transformation on the same field must be
    # described against the text the first one produces, not against raw
    # storage, or a reader applying them in sequence finds a value matching
    # neither hash. So emit reads the view as of this point in the chain.
    view = corrected_view(state, state_repo)

    records, occurrences, refused = [], 0, []
    ev_key = "%s_matches_live" % field
    for url in sorted(view):
        title, body = view[url]["title"], view[url]["body"]
        pub, content_sha, capture_sha = meta[url]
        value = body if field == "body" else title

        if kind == "literal_replace_all":
            if AMBIGUOUS in value:
                raise SystemExit(
                    "refusing to emit: %s contains %s, where a literal "
                    "substitution and a real re-extraction disagree." % (url, AMBIGUOUS))
            n = sum(value.count(f) for f, _ in HEX_APOSTROPHE)
        elif kind == "html_unescape_once":
            if unescape(unescape(value)) != unescape(value):
                raise SystemExit(
                    "refusing to emit: unescaping %s twice differs from once, "
                    "so one pass is not provably the extractor's output." % url)
            n = len(ENTITY_TOKEN.findall(value))
        else:
            if not has_mojibake(value):
                continue
            # Count the damaged code points, not the runs. C1 controls are the
            # bulk of it, but an orphan U+00C2 is damage too and is NOT in the
            # C1 range — count it, or a body whose only defect is one stray
            # orphan scores zero and is silently skipped.
            n = len(C1.findall(value)) + len(ORPHAN_NBSP.findall(value))

        if not n:
            continue

        after = apply_transformation(value, tr, field)
        if after is None:
            refused.append({
                "url": url, "field": field,
                "why": ("the whitespace collapse ate a continuation byte, so "
                        "the original character is not recoverable from stored "
                        "text; re-capture is the only route and is an owner "
                        "decision"),
            })
            continue
        if after == value:
            continue

        ev = evidence.get(url, {})
        if ev.get(ev_key) is True:
            tier = "live-confirmed"
        elif (C1.search(value) or ORPHAN_NBSP.search(value)
              or ENTITY_TOKEN.search(value)):
            # Intrinsic evidence: the stored substring cannot be what a correct
            # extraction produces, whatever the live page says today.
            #
            #   * a C1 control (U+0080-U+009F), or an orphaned lead byte before
            #     whitespace, cannot occur in legitimate extracted prose;
            #   * an undecoded entity reference cannot either — `visible_text`
            #     and `document_title` exist to produce reader-visible text, so
            #     a surviving `&#x27;` is by definition a decoding failure.
            #
            # The constructions where a transformation and a real re-extraction
            # could disagree are refused earlier and by name.
            tier = "intrinsic"
        else:
            refused.append({"url": url, "field": field,
                            "why": "no live confirmation and no intrinsic "
                                   "evidence for this substring"})
            continue

        occurrences += n
        untouched = {
            "url": url,
            "published_date": pub,
            "content_sha256": content_sha,
            "capture_sha256": capture_sha,
            "title_sha256": sha256_text(title),
            "body_sha256": sha256_text(body),
        }
        untouched.pop("title_sha256" if field == "title" else "body_sha256")
        records.append({
            "url": url,
            "field": field,
            "occurrences": n,
            "evidence": tier,
            "value_sha256_before": sha256_text(value),
            "value_sha256_after": sha256_text(after),
            "chars_before": len(value),
            "chars_after": len(after),
            "unchanged": untouched,
        })

    prev = existing_corrections(state)
    doc = {
        "schema": SCHEMA,
        "sequence": len(prev) + 1,
        "desk": "singapore-mindef",
        "field": field,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "collector_commit": collector_commit,
        "reason": reason,
        "transformation": tr,
        "binding": dict(bind,
                        prev_correction_sha256=(sha256_file(prev[-1]) if prev else None)),
        "affected_record_count": len(records),
        "total_occurrences": occurrences,
        "refused": refused,
        "records": records,
    }
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    return doc


# ── verify ────────────────────────────────────────────────────────────────────

def verify(state: Path, state_repo: Optional[Path] = None) -> int:
    db = state / "shadow.db"
    _, tip = ledger_tip(state)
    failures = []

    def check(ok, label):
        print("  %-4s %s" % ("PASS" if ok else "FAIL", label))
        if not ok:
            failures.append(label)

    print("state chain")
    bind = binding(state, state_repo)
    check(bind["database_sha256"] == tip["state_sha256_after"],
          "shadow.db still hashes to the last ledger's state_sha256_after")
    prev, breaks = None, 0
    for f in ledger_entries(state):
        e = json.loads(f.read_text(encoding="utf-8"))
        if prev is not None and e["state_sha256_before"] != prev:
            breaks += 1
        prev = e["state_sha256_after"]
    check(breaks == 0, "ledger chain unbroken (%d break(s))" % breaks)

    con = read_only(db)
    meta = {u: (p, c, k) for u, p, c, k in con.execute(
        "select url, published_date, content_sha256, capture_sha256 "
        "from shadow_records")}
    con.close()
    # Replayed in sequence, exactly as a reader would apply them.
    view = original_view(state)

    files = existing_corrections(state)
    print("corrections: %d file(s)" % len(files))
    prev_hash, expect_seq, seen_pairs = None, 1, set()
    for f in files:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            check(False, "  %s is not readable JSON (%s)" % (f.name, type(exc).__name__))
            continue
        field = doc.get("field")
        print("  %s  (field: %s)" % (f.name, field))
        # fail closed on anything unrecognised
        check(doc.get("schema") == SCHEMA, "    schema is %s" % SCHEMA)
        check(field in FIELDS, "    field is one this tool knows")
        kind_ok = doc.get("transformation", {}).get("kind") in APPROVED_KINDS
        check(kind_ok, "    transformation kind is approved")
        schema_ok = doc.get("schema") == SCHEMA and field in FIELDS
        check(doc.get("sequence") == expect_seq, "    sequence is %d" % expect_seq)
        b = doc.get("binding", {})
        check(b.get("prev_correction_sha256") == prev_hash,
              "    chains to the previous correction")
        check(b.get("database_sha256") == bind["database_sha256"],
              "    bound to this database's hash")
        check(b.get("ledger_tip_file") == bind["ledger_tip_file"],
              "    bound to this ledger tip")
        check(b.get("ledger_entry_count") == bind["ledger_entry_count"],
              "    bound to this ledger entry count")
        if state_repo:
            check(b.get("state_commit") == bind["state_commit"],
                  "    bound to this state commit")
            check(b.get("state_tree") == bind["state_tree"],
                  "    bound to this state tree")
        check(len(doc.get("records", [])) == doc.get("affected_record_count"),
              "    affected_record_count matches the record list")
        check(sum(r["occurrences"] for r in doc["records"]) == doc["total_occurrences"],
              "    total_occurrences matches the record list")

        if not (kind_ok and schema_ok):
            # Already reported. Replaying records through an unknown
            # transformation would raise, and a verifier that dies cannot
            # report — so stop reading this file and keep going.
            prev_hash, expect_seq = sha256_file(f), expect_seq + 1
            continue

        dupes = bad_before = bad_after = bad_untouched = unknown = bad_tier = 0
        local = set()
        for r in doc["records"]:
            key = (r["url"], field, doc["transformation"]["kind"])
            if key in seen_pairs or key in local:
                dupes += 1
            local.add(key)
            if r.get("evidence") not in EVIDENCE_TIERS:
                bad_tier += 1
            if r["url"] not in view:
                unknown += 1
                continue
            title, body = view[r["url"]]["title"], view[r["url"]]["body"]
            pub, content_sha, capture_sha = meta[r["url"]]
            value = body if field == "body" else title
            if sha256_text(value) != r["value_sha256_before"]:
                bad_before += 1
            got = apply_transformation(value, doc["transformation"], field)
            if got is None or sha256_text(got) != r["value_sha256_after"]:
                bad_after += 1
            actual = {"url": r["url"], "published_date": pub,
                      "content_sha256": content_sha, "capture_sha256": capture_sha,
                      "title_sha256": sha256_text(title),
                      "body_sha256": sha256_text(body)}
            if any(actual[k] != v for k, v in r["unchanged"].items()):
                bad_untouched += 1
            if got is not None:
                view[r["url"]][field] = got        # advance for the next file
        seen_pairs |= local
        check(unknown == 0, "    every record exists in this database")
        check(dupes == 0, "    no record corrected twice by the same transformation")
        check(bad_tier == 0, "    every record carries a known evidence tier")
        check(bad_before == 0, "    every before-hash matches the stored value")
        check(bad_after == 0, "    every after-hash reproduces from the stored value")
        check(bad_untouched == 0,
              "    the other fields — title or body, date, URL, identity — unchanged")
        prev_hash, expect_seq = sha256_file(f), expect_seq + 1

    print("\n%s" % ("VERIFIED" if not failures else
                    "FAILED — %d check(s)" % len(failures)))
    return 0 if not failures else 1


# ── materialize ───────────────────────────────────────────────────────────────

def original_view(state: Path) -> dict:
    """{url: {"title":…, "body":…}} exactly as captured."""
    con = read_only(state / "shadow.db")
    rows = {u: {"title": t or "", "body": b or ""} for u, t, b in con.execute(
        "select url, title_original, text_original from shadow_records")}
    con.close()
    return rows


def corrected_view(state: Path, state_repo: Optional[Path] = None) -> dict:
    """The original view with every verified correction applied, in sequence.

    Refuses rather than guessing: a value matching neither the before nor the
    after hash means the overlay does not describe this database.
    """
    rows = original_view(state)
    bind = binding(state, state_repo)
    for f in existing_corrections(state):
        doc = json.loads(f.read_text(encoding="utf-8"))
        if doc.get("schema") != SCHEMA:
            raise SystemExit("%s: unknown correction schema %r"
                             % (f.name, doc.get("schema")))
        if doc.get("transformation", {}).get("kind") not in APPROVED_KINDS:
            raise SystemExit("%s: unapproved transformation" % f.name)
        b = doc.get("binding", {})
        if b.get("database_sha256") != bind["database_sha256"]:
            raise SystemExit("%s: bound to a different database" % f.name)
        if state_repo and b.get("state_commit") != bind["state_commit"]:
            raise SystemExit("%s: bound to a different state commit" % f.name)
        field = doc["field"]
        for r in doc["records"]:
            rec = rows.get(r["url"])
            if rec is None:
                raise SystemExit("%s: corrects a record this database does not "
                                 "have: %s" % (f.name, r["url"]))
            h = sha256_text(rec[field])
            if h == r["value_sha256_after"]:
                continue                       # already applied — idempotent
            if h != r["value_sha256_before"]:
                raise SystemExit(
                    "%s: %s matches neither the before nor the after hash"
                    % (f.name, r["url"]))
            got = apply_transformation(rec[field], doc["transformation"], field)
            if got is None or sha256_text(got) != r["value_sha256_after"]:
                raise SystemExit("%s: %s does not reproduce its after-hash"
                                 % (f.name, r["url"]))
            rec[field] = got
    return rows


def overlay_digest(state: Path) -> Optional[str]:
    """One hash naming the whole overlay, for a packet to quote."""
    files = existing_corrections(state)
    if not files:
        return None
    h = hashlib.sha256()
    for f in files:
        h.update(f.name.encode("utf-8"))
        h.update(f.read_bytes())
    return h.hexdigest()


# ── cli ───────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Shadow correction overlay.")
    ap.add_argument("--state-dir", required=True, type=Path)
    ap.add_argument("--state-repo", type=Path, default=None)
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--digest", action="store_true")
    ap.add_argument("--field", choices=FIELDS, default="body")
    ap.add_argument("--kind", choices=APPROVED_KINDS, default="literal_replace_all")
    ap.add_argument("--evidence", type=Path, default=None)
    ap.add_argument("--reason", default="")
    ap.add_argument("--collector-commit", default="")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)

    state = a.state_dir
    if not (state / "shadow.db").is_file():
        raise SystemExit("no shadow.db under %s" % state)

    if a.digest:
        print(overlay_digest(state) or "(no corrections)")
        return 0
    if a.emit:
        if not a.reason:
            raise SystemExit("--emit requires --reason")
        n = len(existing_corrections(state)) + 1
        out = a.out or (corrections_dir(state) /
                        ("%04d-%s-%s.json" % (n, a.field, a.kind)))
        doc = emit(state, a.field, a.kind, a.reason, a.collector_commit,
                   a.evidence, a.state_repo, out)
        print("wrote %s — %d record(s), %d occurrence(s), %d refused"
              % (out, doc["affected_record_count"], doc["total_occurrences"],
                 len(doc["refused"])))
        return 0
    if a.verify:
        return verify(state, a.state_repo)
    ap.error("choose --emit, --verify or --digest")


if __name__ == "__main__":
    sys.exit(main())
