#!/usr/bin/env python3
"""
A corrected-view packet: the same evidence, read through a verified overlay.

This does **not** touch `review_shadow_state.py` and does not alter the Day-30
packet. That packet is derived from the committed `state/` tree, whose allowlist
is `clock.json`, `shadow.db` and `ledger/`, and an unrecognised file there is a
refusal by design. The overlay therefore lives *beside* `state/`, the state tree
hash is unchanged, and the existing Day-30 packet still reproduces byte for byte
and stays exactly as valid as it was. Nothing is weakened; a second, separately
named packet is added.

The packet carries two views, always both, never one silently substituted:

  * **ORIGINAL CAPTURE VIEW** — the bytes as collected. The evidence of record.
  * **VERIFIED CORRECTED VIEW** — the same records read through the overlay,
    named by its digest so a reader can tell which correction produced it.

It fails closed. If the overlay does not verify against this exact database,
ledger tip, state commit and state tree, no packet is written at all — because
a packet that quietly drops a correction it could not check would look complete
while being wrong.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.correct_shadow_bodies as cc                     # noqa: E402

PACKET_KIND = "singapore-corrected-view/3"


def load_disposition(path: Optional[Path]) -> Optional[dict]:
    """The owner's decision, recorded as data.

    Recorded, never inferred, and deliberately separate from the checkpoint
    sign-off: a disposition says what the owner decided about these records, a
    sign-off says a human opened every page and checked it. This packet can
    carry the first. Only a person can produce the second, and the packet says
    so rather than filling it in.
    """
    if not path:
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    for key in ("decided_by", "decided_utc", "decisions"):
        if not doc.get(key):
            raise SystemExit("owner disposition is missing %r" % key)
    return doc


def build(state: Path, state_repo: Path, out: Path, as_of: str,
          disposition: Optional[Path] = None) -> dict:
    # Fail closed: verify before reading anything into a packet.
    if cc.verify(state, state_repo) != 0:
        raise SystemExit(
            "refusing to build: the overlay does not verify against this "
            "state. A packet that drops a correction it could not check "
            "would look complete while being wrong.")

    digest = cc.overlay_digest(state)
    if digest is None:
        raise SystemExit("refusing to build: there is no overlay to apply. "
                         "The Day-30 packet already covers the original view.")

    bind = cc.binding(state, state_repo)
    original = cc.original_view(state)
    corrected = cc.corrected_view(state, state_repo)

    files = []
    for f in cc.existing_corrections(state):
        doc = json.loads(f.read_text(encoding="utf-8"))
        files.append({
            "file": f.name,
            "sha256": cc.sha256_file(f),
            "field": doc["field"],
            "transformation": doc["transformation"]["kind"],
            "records": doc["affected_record_count"],
            "occurrences": doc["total_occurrences"],
            "refused": len(doc.get("refused", [])),
            "reason": doc["reason"],
        })

    # Holds are read through the same binding the corrections are, so a holds
    # file describing another database refuses here rather than quietly
    # promoting a record someone withheld.
    holds = cc.load_holds(state, state_repo)
    recaptured = {}
    for f in cc.existing_corrections(state):
        doc = json.loads(f.read_text(encoding="utf-8"))
        if doc["transformation"]["kind"] != cc.RECAPTURE:
            continue
        for r in doc["records"]:
            recaptured[r["url"]] = {
                "field": doc["field"],
                "retrieved_at": r["recapture"]["retrieved_at"],
                "raw_sha256": r["recapture"]["raw_sha256"],
                "http_status": r["recapture"]["http_status"],
                "declared_encoding": r["recapture"]["declared_encoding"],
                "encoding_source": r["recapture"]["encoding_source"],
                "equivalence_note": r["recapture"].get("equivalence_note"),
                "warning": r["warning"],
            }

    changed = sorted(u for u in original if original[u] != corrected[u])
    refused = [r for f in cc.existing_corrections(state)
               for r in json.loads(f.read_text(encoding="utf-8")).get("refused", [])]

    packet = {
        "packet_kind": PACKET_KIND,
        "desk": "singapore-mindef",
        "as_of": as_of,
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "publishable": False,
        "not_a_replacement_for": (
            "the Day-30 packet, which is derived from the committed state tree "
            "and is unchanged by this overlay"),
        "binding": bind,
        "overlay_digest": digest,
        "overlay_files": files,
        "record_count": len(original),
        "records_changed": len(changed),
        "records_refused": len(refused),
        "refusals": refused,
        "views": {
            "ORIGINAL CAPTURE VIEW": {
                "description": "the bytes as collected; the evidence of record",
                "records": {u: {"title": original[u]["title"],
                                "body_sha256": cc.sha256_text(original[u]["body"]),
                                "body_chars": len(original[u]["body"])}
                            for u in sorted(original)},
            },
            "VERIFIED CORRECTED VIEW": {
                "description": "the same records read through overlay %s" % digest[:12],
                "records": {u: {"title": corrected[u]["title"],
                                "body_sha256": cc.sha256_text(corrected[u]["body"]),
                                "body_chars": len(corrected[u]["body"])}
                            for u in sorted(corrected)},
            },
        },
        "changed_records": changed,
        "owner_disposition": load_disposition(disposition),
        "promotion": {
            "holds_digest": cc.holds_digest(state),
            "held": {u: {"reason": h["reason"], "evidence": h["evidence"]}
                     for u, h in sorted(holds.items())},
            "held_count": len(holds),
            "promotable_count": len(corrected) - len(holds),
            "recaptured": recaptured,
            "recaptured_count": len(recaptured),
            "warning": (cc.RECAPTURE_WARNING if recaptured else None),
            "owner_decision_required": [
                "approve, or decline, promotion of the %d promotable records "
                "into the production corpus" % (len(corrected) - len(holds)),
                "approve, or decline, the %d recaptured value(s) — text fetched "
                "from the live page after capture, not the captured bytes"
                % len(recaptured),
                "confirm the %d held record(s) stay out of promotion"
                % len(holds),
                "confirm the %d record(s) accepted as originally captured, "
                "whose live pages have since drifted" % 2,
                "re-emit the overlay against the state commit current at the "
                "moment of approval: the overlay binds to a ledger tip, and a "
                "scheduled shadow run advances it",
            ],
        },
    }

    out.mkdir(parents=True, exist_ok=True)
    (out / "corrected_view_packet.json").write_text(
        json.dumps(packet, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    (out / "corrected_bodies.json").write_text(
        json.dumps({u: corrected[u] for u in sorted(corrected)},
                   indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    return packet


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--state-dir", required=True, type=Path)
    ap.add_argument("--state-repo", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--as-of", default=datetime.now(timezone.utc).date().isoformat())
    ap.add_argument("--owner-disposition", type=Path, default=None)
    a = ap.parse_args(argv)
    p = build(a.state_dir, a.state_repo, a.out, a.as_of, a.owner_disposition)
    print("\ncorrected-view packet")
    print("  overlay digest : %s" % p["overlay_digest"])
    print("  state commit   : %s" % p["binding"]["state_commit"])
    print("  state tree     : %s" % p["binding"]["state_tree"])
    print("  database       : %s" % p["binding"]["database_sha256"])
    print("  records        : %d (%d changed, %d refused)"
          % (p["record_count"], p["records_changed"], p["records_refused"]))
    print("  publishable    : no — this is an overlay view, not the Day-30 packet")
    print("  written to     : %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
