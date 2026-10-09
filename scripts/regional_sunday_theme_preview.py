#!/usr/bin/env python3
"""Manual, owner-only private themed Sunday manuscript rehearsal.

No scheduled workflow, SMTP, numbering, publication, public source artifact,
or unapproved research promotion. Even a valid theme selection never contacts
Dylan: production editor delivery is explicitly out of scope.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH  # noqa: E402
from core.brief_contract import eligible_desks  # noqa: E402
from core.desk_registry import load_registry  # noqa: E402
from core.regional_theme_handoff import sign_choice, verify_choice, digest  # noqa: E402
from core.regional_reviewed_evidence import private_model_packet  # noqa: E402
from core.regional_weekly_inventory import inspect  # noqa: E402
from scripts.author_brief import build_draft  # noqa: E402
from scripts.reconcile_db import read_only  # noqa: E402
from scripts.regional_reviewed_evidence import _json, _out  # noqa: E402
from scripts.sunday_briefs_auto_writer import choose_evidence, compose  # noqa: E402
from scripts.sunday_editorial_handoff import render_packet  # noqa: E402
from storage.db import get_articles_for_desks  # noqa: E402

CONFIRM_SELECTION = "I APPROVE THIS THEME FOR PRIVATE SUNDAY REHEARSAL"
CONFIRM_MODEL = "I AUTHORIZE ONE PRIVATE THEMATIC MANUSCRIPT MODEL CALL"


def _out_text(path, content):
    target = Path(path).expanduser()
    if target.is_symlink() or target.exists():
        raise ValueError("private manuscript output must be a new file")
    target = target.resolve()
    if target == ROOT.resolve() or ROOT.resolve() in target.parents:
        raise ValueError("private manuscript cannot be written in the repository")
    if not target.parent.is_dir():
        raise ValueError("private output directory must already exist")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(target), flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def prepare_scaffold(*, inventory, database=DB_PATH, registry=None):
    """Rebuild exact-week production source trail from a read-only SQLite copy."""
    registry = registry if registry is not None else load_registry()
    desks = eligible_desks(registry)
    if len(desks) < 2:
        raise ValueError("Sunday still requires two production-backed desks")
    with read_only(Path(database)) as conn:
        rows = get_articles_for_desks(
            inventory["week_start"], inventory["week_ending"], desks, conn=conn)
    return build_draft(rows, desks=desks, week_start=inventory["week_start"],
                       week_ending=inventory["week_ending"])


def preflight_theme(*, inventory, signed_review, proposal, choice,
                    secret, db=DB_PATH, registry=None):
    """Independent no-LLM rehearsal gate; receipt expires with the corpus.

    The audit is advisory and has NO persistence/transport authority. A later
    paid manuscript call must re-run every source gate on a fresh SQLite copy.
    """
    approved = verify_choice(inventory, signed_review, secret, proposal, choice)
    chosen = approved["selected_source_ids"]
    by_id = {entry["id"]: entry for entry in inventory["production_evidence"]}
    pins = {
        ident: {field: by_id[ident][field] for field in (
            "desk", "source_url", "published_date", "stored_text_sha256",
            "source_name", "title_original", "language")}
        for ident in chosen
    }
    approved = dict(approved, reviewed_source_pins=pins)
    sidecar = prepare_scaffold(inventory=inventory, database=db, registry=registry)
    trail_ids = {row["record_id"] for row in sidecar["source_trail"]}
    if not set(chosen).issubset(trail_ids):
        raise ValueError("owner-selected thematic sources not present in current Sunday trail")
    packet = private_model_packet(inventory, signed_review, secret)
    notes = {
        entry["id"]: {
            "analyst_synopsis": entry["analyst_synopsis"],
            "accuracy_limitations": entry["accuracy_limitations"],
        }
        for entry in packet["production_sources"]
        if entry["id"] in chosen
    }
    if set(notes) != set(chosen):
        raise ValueError("approved thematic sources lack current reviewed synopses")
    # The ordinary Sunday writer's own source-trail gate and the owner-signed
    # archive body/issuer pins are independently verified before any model
    # token is spent. This audit never returns raw publisher text.
    checked = choose_evidence(
        sidecar, as_of=inventory["week_ending"], db=db,
        selected_ids=chosen, selected_pins=pins)
    actual_ids = [row["id"] for row, _body in checked]
    if actual_ids != chosen:
        raise ValueError("preflight did not recover exact signed source selection")
    receipt = {
        "schema": "ipr-regional-private-sunday-rehearsal-preflight/1",
        "week_ending": inventory["week_ending"],
        "source_metadata_digest_sha256": inventory["source_metadata_digest_sha256"],
        "reviewed_source_pins_sha256": digest(pins),
        "owner_choice_sha256": digest(choice),
        "selected_source_ids": chosen,
        "represented_desks": approved["represented_desks"],
        "selected_source_count": len(chosen),
        "publisher_body_text_in_receipt": False,
        "model_called": False,
        "source_audit_only_not_a_reusable_model_authorization": True,
        "publication_authorized": False,
        "editor_email_authorized": False,
    }
    return receipt, approved, sidecar, notes


def build_private_manuscript(*, inventory, signed_review, proposal, choice,
                             secret, db=DB_PATH, registry=None, client=None):
    """Recheck fresh source pins and owner seals BEFORE model invocation."""
    _receipt, approved, sidecar, notes = preflight_theme(
        inventory=inventory, signed_review=signed_review, proposal=proposal,
        choice=choice, secret=secret, db=db, registry=registry)
    chosen = approved["selected_source_ids"]
    # The writer independently verifies record-level source trail equality
    # and text availability, but the actual LLM sees synopsis-only material.
    manuscript = compose(
        sidecar, inventory["week_ending"], db=db, client=client,
        selected_theme=approved, reviewed_synopses=notes)
    if manuscript.get("_private_owner_selected_production_ids") != sorted(chosen):
        raise ValueError("writer did not offer precisely the owner-selected source IDs")
    text = render_packet(sidecar, manuscript=manuscript,
                         as_of=inventory["week_ending"])
    prefix = (
        "IPR PRIVATE OWNER-SELECTED THEMATIC REHEARSAL — NO EDITOR DELIVERY\n"
        "Selected focus: " + approved["approved_focus"].replace("\n", " ") + "\n"
        "Selected evidence IDs: " + ", ".join(map(str, chosen)) + "\n"
        "Approval scope: private no-send trial only; source claims remain unverified.\n"
        "No single-desk exception, issue number, publication, or Dylan delivery.\n\n"
    )
    return prefix + text


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("approve", "audit", "rehearse"))
    parser.add_argument("--week-ending", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--review-local-day", required=True)
    parser.add_argument("--signed-review", type=Path, required=True)
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--choice", type=Path, help="Required for audit or rehearsal")
    parser.add_argument("--theme-slug", help="Required for approve")
    parser.add_argument("--approved-by", help="Required for approve")
    parser.add_argument("--db", type=Path, default=ROOT / "pla_watch.db")
    parser.add_argument("--marker", type=Path,
                        default=ROOT / ".github/state/last_daily_run_date.txt")
    parser.add_argument("--allow-private-paid-writer", action="store_true",
                        help="Required ONLY for rehearse; separate interactive approval also required")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if not sys.stdin.isatty():
        parser.error("owner-approved thematic handoff cannot run noninteractively")
    if args.mode == "approve":
        if (not args.theme_slug or not args.approved_by or args.choice
                or args.allow_private_paid_writer):
            parser.error("approve requires theme slug and owner name; no writer authorization")
    elif args.mode == "audit":
        if (not args.choice or args.theme_slug or args.approved_by
                or args.allow_private_paid_writer):
            parser.error("audit requires signed choice and must not authorize a paid model")
    elif (not args.choice or args.theme_slug or args.approved_by
          or not args.allow_private_paid_writer):
        parser.error("rehearse requires signed choice and explicit private paid writer flag")
    try:
        inventory = inspect(
            week_ending=args.week_ending, as_of=args.as_of,
            review_day=args.review_local_day, database=args.db,
            marker_path=args.marker)
        signed_review = _json(args.signed_review)
        proposal = _json(args.proposals)
        key = getpass.getpass("Owner source-review signing key: ").encode("utf-8")
        if args.mode == "approve":
            if input("Type thematic choice approval phrase: ").strip() != CONFIRM_SELECTION:
                raise ValueError("owner did not authorize the selected theme")
            result = sign_choice(
                inventory, signed_review, key, proposal,
                slug=args.theme_slug, owner=args.approved_by,
                approved_on=args.review_local_day)
            _out(args.out, result)
        else:
            choice = _json(args.choice)
            # The audit is local/no-call; model rehearsal rechecks everything
            # after authorization. Neither path can reuse a stale audit receipt.
            if args.mode == "audit":
                receipt, _approved, _sidecar, _notes = preflight_theme(
                    inventory=inventory, signed_review=signed_review,
                    proposal=proposal, choice=choice, secret=key,
                    db=args.db)
                _out(args.out, receipt)
            else:
                verify_choice(inventory, signed_review, key, proposal, choice)
                if input("Exact one-call manuscript authorization phrase: ").strip() != CONFIRM_MODEL:
                    raise ValueError("private manuscript AI call not authorized")
                if not os.environ.get("ANTHROPIC_API_KEY"):
                    raise ValueError("no Anthropic API key configured")
                text = build_private_manuscript(
                    inventory=inventory, signed_review=signed_review,
                    proposal=proposal, choice=choice, secret=key,
                    db=args.db)
                _out_text(args.out, text)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print("Private %s completed; NO Dylan email, site publication or PR." % args.mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
