#!/usr/bin/env python3
"""
Versioned body corrections for a shadow state branch, as a sidecar.

Why a sidecar rather than an UPDATE
-----------------------------------
The shadow state branch is hash-chained at two levels, and both of them
forbid touching `shadow.db`:

  * every ledger entry records `state_sha256_before` and `state_sha256_after`,
    the SHA-256 of the whole database file. The Singapore chain runs unbroken
    across all 32 ledgers. Change one byte of the database and the tip no
    longer matches the hash the last run published, the next run's `before`
    assertion fails, and the only way to make the chain agree again is to
    rewrite ledger entries that are append-only by design.

  * every ledger also records the `content_sha256` of each record it inserted.
    Rewriting a body leaves that hash describing text that no longer exists,
    or updates it to a value no ledger ever recorded. Either way the database
    stops agreeing with the evidence that produced it.

So a correction is never applied to the database. It is published beside it as
an append-only, hash-chained file that says exactly what transformation a
reader should apply, to which records, and what the result must hash to. The
stored bodies remain the original evidence, permanently recoverable, and any
reader can reproduce the corrected text or reject the correction outright.

Why a transformation rather than a refetch
------------------------------------------
Refetching would silently import whatever the live page says today. Measured
on the 29 affected Singapore records: 26 pages are still byte-identical to
what was captured, but 3 have drifted. Refetch-and-overwrite would have
rewritten those 3 with newer text under the guise of fixing an apostrophe.

The transformation is justified by evidence rather than assumption. For all 29
records, re-extracting the live page with the fixed extractor produces exactly
the same string as applying the literal substitution to the old extractor's
output — and no source page anywhere in the corpus contains `&amp;#x27;`, the
one construction under which the substitution and a real re-extraction would
disagree. `--emit` re-checks that no record contains a double-escaped form
before it will write a correction.

This tool never opens the database for writing.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sqlite3
import sys
from html import unescape
from datetime import datetime, timezone
from pathlib import Path

TOOL = "scripts/correct_shadow_bodies.py"
TOOL_VERSION = "1.0.0"
SCHEMA = "shadow-body-correction/1"

#: Correctable fields, and the transformation each one takes. Kept declarative
#: so a reader can apply them without running this code.
#:
#: `text_original` is corrected by literal substitution rather than by
#: unescaping, because it has *already* been through the old six-entity table:
#: unescaping it again would decode entities the table had legitimately left
#: alone and would double-decode the ones it had already handled.
#:
#: `title_original` is the opposite case. The `og:title` branch decoded nothing
#: at all, so what is stored is the raw attribute value verbatim and a single
#: `html.unescape` is exactly what the fixed extractor now does to it.
FIELDS = ("body", "title")
COLUMN = {"body": "text_original", "title": "title_original"}
HEX_APOSTROPHE = [["&#x27;", "'"]]

#: The construction under which a literal substitution and a genuine
#: re-extraction would disagree: `unescape` turns it into the literal text
#: `&#x27;`, while the substitution would turn it into an apostrophe.
AMBIGUOUS = "&amp;#x27;"

#: Any HTML entity reference, named or numeric.
ENTITY_TOKEN = re.compile(r"&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_only(db: Path) -> sqlite3.Connection:
    """Immutable, read-only, and takes no lock — so it cannot create -wal/-shm."""
    return sqlite3.connect("file:%s?mode=ro&immutable=1" % db.resolve(), uri=True)


def apply_pairs(text: str, pairs) -> str:
    for find, repl in pairs:
        text = text.replace(find, repl)
    return text


def apply_transformation(text: str, tr: dict) -> str:
    if tr["kind"] == "literal_replace_all":
        return apply_pairs(text, tr["pairs"])
    if tr["kind"] == "html_unescape_once":
        return unescape(text)
    raise SystemExit("unknown transformation kind: %r" % tr["kind"])


def ledger_tip(state: Path):
    files = sorted(glob.glob(str(state / "ledger" / "*.json")))
    if not files:
        raise SystemExit("no ledger entries in %s" % (state / "ledger"))
    return Path(files[-1]), json.loads(Path(files[-1]).read_text(encoding="utf-8"))


def corrections_dir(state: Path) -> Path:
    return state / "corrections"


def existing_corrections(state: Path):
    d = corrections_dir(state)
    if not d.is_dir():
        return []
    return [Path(p) for p in sorted(glob.glob(str(d / "*.json")))]


# ── emit ──────────────────────────────────────────────────────────────────────

def emit(state: Path, reason: str, collector_commit: str,
         field: str = "body", out: Path = None) -> dict:
    if field not in FIELDS:
        raise SystemExit("unknown field %r" % field)
    db = state / "shadow.db"
    tip_path, tip = ledger_tip(state)
    state_hash = sha256_file(db)
    if state_hash != tip["state_sha256_after"]:
        raise SystemExit(
            "refusing to emit: the database does not hash to what the last "
            "ledger published.\n  ledger %s\n  actual %s"
            % (tip["state_sha256_after"], state_hash))

    if field == "body":
        tr = {"kind": "literal_replace_all", "pairs": HEX_APOSTROPHE,
              "equivalent_to": ("re-extraction of the captured page with the "
                                "fixed sg_mindef.visible_text")}
    else:
        tr = {"kind": "html_unescape_once",
              "equivalent_to": ("re-extraction of the captured page with the "
                                "fixed sg_mindef.document_title")}
    tr["applies_to"] = "shadow_records." + COLUMN[field]

    con = read_only(db)
    rows = con.execute(
        "select url, title_original, text_original, published_date, "
        "       content_sha256, capture_sha256 "
        "from shadow_records order by url").fetchall()
    con.close()

    records, occurrences = [], 0
    for url, title, body, pub, content_sha, capture_sha in rows:
        title, body = title or "", body or ""
        value = body if field == "body" else title
        if field == "body":
            if AMBIGUOUS in value:
                raise SystemExit(
                    "refusing to emit: %s contains %s, where a literal "
                    "substitution and a real re-extraction disagree. This "
                    "correction is not provably equivalent to re-extraction "
                    "for that record." % (url, AMBIGUOUS))
            n = sum(value.count(find) for find, _ in HEX_APOSTROPHE)
        else:
            # A second pass must change nothing, or the stored value was not
            # the raw attribute this transformation assumes.
            if unescape(unescape(value)) != unescape(value):
                raise SystemExit(
                    "refusing to emit: unescaping %s twice is not the same as "
                    "unescaping it once, so one pass is not provably the "
                    "extractor's own output." % url)
            n = len(ENTITY_TOKEN.findall(value))
        if not n:
            continue
        after = apply_transformation(value, tr)
        occurrences += n
        rec = {
            "url": url,
            "occurrences": n,
            "value_sha256_before": sha256_text(value),
            "value_sha256_after": sha256_text(after),
            "chars_before": len(value),
            "chars_after": len(after),
        }
        # Everything this correction must be proven NOT to touch. A verifier
        # recomputes these from the untouched database and compares.
        untouched = {
            "url": url,
            "published_date": pub,
            "content_sha256": content_sha,
            "capture_sha256": capture_sha,
            "title_sha256": sha256_text(title),
            "body_sha256": sha256_text(body),
        }
        # The field being corrected is, of course, not among the untouched.
        untouched.pop("title_sha256" if field == "title" else "body_sha256")
        rec["unchanged"] = untouched
        records.append(rec)

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
        "anchor": {
            "state_sha256": state_hash,
            "ledger_tip_file": tip_path.name,
            "ledger_tip_run_id": tip.get("run_id"),
            "prev_correction_sha256": (sha256_file(prev[-1]) if prev else None),
        },
        "affected_record_count": len(records),
        "total_occurrences": occurrences,
        "records": records,
    }
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    return doc


# ── verify ────────────────────────────────────────────────────────────────────

def verify(state: Path) -> int:
    db = state / "shadow.db"
    tip_path, tip = ledger_tip(state)
    failures = []

    def check(ok, label):
        print("  %-4s %s" % ("PASS" if ok else "FAIL", label))
        if not ok:
            failures.append(label)

    print("state chain")
    state_hash = sha256_file(db)
    check(state_hash == tip["state_sha256_after"],
          "shadow.db still hashes to the last ledger's state_sha256_after")

    chain_prev, breaks = None, 0
    for f in sorted(glob.glob(str(state / "ledger" / "*.json"))):
        e = json.loads(Path(f).read_text(encoding="utf-8"))
        if chain_prev is not None and e["state_sha256_before"] != chain_prev:
            breaks += 1
        chain_prev = e["state_sha256_after"]
    check(breaks == 0, "ledger chain unbroken (%d break(s))" % breaks)

    con = read_only(db)
    rows = {u: (t or "", b or "", p, c, k) for u, t, b, p, c, k in con.execute(
        "select url, title_original, text_original, published_date, "
        "content_sha256, capture_sha256 from shadow_records")}
    con.close()

    files = existing_corrections(state)
    print("corrections: %d file(s)" % len(files))
    prev_hash, expect_seq = None, 1
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        field = doc.get("field", "body")
        print("  %s  (field: %s)" % (f.name, field))
        check(doc.get("schema") == SCHEMA, "    schema is %s" % SCHEMA)
        check(field in FIELDS, "    field is one this tool knows")
        check(doc.get("sequence") == expect_seq, "    sequence is %d" % expect_seq)
        check(doc["anchor"]["prev_correction_sha256"] == prev_hash,
              "    chains to the previous correction")
        check(doc["anchor"]["state_sha256"] == state_hash,
              "    anchored to the current database")
        check(len(doc["records"]) == doc["affected_record_count"],
              "    affected_record_count matches the record list")
        check(sum(r["occurrences"] for r in doc["records"]) == doc["total_occurrences"],
              "    total_occurrences matches the record list")
        seen, bad_before, bad_after, bad_untouched = set(), 0, 0, 0
        for r in doc["records"]:
            seen.add(r["url"])
            if r["url"] not in rows:
                bad_before += 1
                continue
            title, body, pub, content_sha, capture_sha = rows[r["url"]]
            value = body if field == "body" else title
            if sha256_text(value) != r["value_sha256_before"]:
                bad_before += 1
            if sha256_text(apply_transformation(value, doc["transformation"])) \
                    != r["value_sha256_after"]:
                bad_after += 1
            u = r["unchanged"]
            actual = {"url": r["url"], "published_date": pub,
                      "content_sha256": content_sha, "capture_sha256": capture_sha,
                      "title_sha256": sha256_text(title),
                      "body_sha256": sha256_text(body)}
            if any(actual[k] != v for k, v in u.items()):
                bad_untouched += 1
        check(len(seen) == len(doc["records"]), "    every record named once")
        check(bad_before == 0, "    every before-hash matches the stored value")
        check(bad_after == 0, "    every after-hash reproduces from the stored value")
        check(bad_untouched == 0,
              "    the other fields — title or body, date, URL, identity — unchanged")
        prev_hash, expect_seq = sha256_file(f), expect_seq + 1

    print("\n%s" % ("VERIFIED" if not failures else
                    "FAILED — %d check(s)" % len(failures)))
    return 0 if not failures else 1


# ── materialize ───────────────────────────────────────────────────────────────

def corrected_records(state: Path) -> dict:
    """{url: {"title": ..., "body": ...}} for readers, with every correction
    applied in sequence. The database is never modified.

    A value that already hashes to `value_sha256_after` is left alone, so
    applying this twice is the same as applying it once.
    """
    con = read_only(state / "shadow.db")
    rows = {u: {"title": t or "", "body": b or ""} for u, t, b in con.execute(
        "select url, title_original, text_original from shadow_records")}
    con.close()
    for f in existing_corrections(state):
        doc = json.loads(f.read_text(encoding="utf-8"))
        field = doc.get("field", "body")
        for r in doc["records"]:
            rec = rows.get(r["url"])
            if rec is None:
                continue
            h = sha256_text(rec[field])
            if h == r["value_sha256_after"]:
                continue                      # already correct — idempotent
            if h != r["value_sha256_before"]:
                raise SystemExit(
                    "record %s matches neither the before nor the after hash; "
                    "the correction does not describe this database" % r["url"])
            rec[field] = apply_transformation(rec[field], doc["transformation"])
    return rows


def corrected_bodies(state: Path) -> dict:
    return {u: v["body"] for u, v in corrected_records(state).items()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--state-dir", required=True, type=Path)
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--reason", default="")
    ap.add_argument("--collector-commit", default="")
    ap.add_argument("--field", choices=FIELDS, default="body",
                    help="which stored column this correction repairs")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)

    state = a.state_dir
    if not (state / "shadow.db").is_file():
        raise SystemExit("no shadow.db under %s" % state)

    if a.emit:
        if not a.reason:
            raise SystemExit("--emit requires --reason")
        n = len(existing_corrections(state)) + 1
        out = a.out or (corrections_dir(state) /
                        ("%04d-%s-%s.json" % (n, a.field, datetime.now(timezone.utc)
                                              .strftime("%Y%m%dT%H%M%SZ"))))
        doc = emit(state, a.reason, a.collector_commit, a.field, out)
        print("wrote %s — %d record(s), %d occurrence(s)"
              % (out, doc["affected_record_count"], doc["total_occurrences"]))
        return 0
    if a.verify:
        return verify(state)
    ap.error("choose --emit or --verify")


if __name__ == "__main__":
    sys.exit(main())
