#!/usr/bin/env python3
"""S1 synthetic public-artifact leak rehearsal, NOT a deploy approval tool.

The audit inspects a test tree outside the repository and redacts all evidence
from diagnostics. No production DB/output, credentials or publisher text.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.source_publication_contract import ProjectionContractError  # noqa: E402

TEXT_EXTENSIONS = frozenset({".html", ".htm", ".json", ".xml", ".txt", ".js",
                             ".css", ".svg", ".md", ".webmanifest"})
BINARY_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".ico", ".woff2", ".pdf"})
FORBIDDEN_JSON_KEYS = frozenset({"text_original", "source_url", "original_url",
                                "title_original", "machine_summary", "raw_body",
                                "publisher_body"})


def _contains_forbidden_keys(value):
    if isinstance(value, dict):
        return any(key in FORBIDDEN_JSON_KEYS or _contains_forbidden_keys(subvalue)
                   for key, subvalue in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_keys(child) for child in value)
    return False


def _forms(token):
    return frozenset({
        token,
        html.escape(token, quote=True),
        json.dumps(token, ensure_ascii=True)[1:-1],
        quote(token, safe=""),
        base64.b64encode(token.encode("utf-8")).decode("ascii"),
    })


def audit_synthetic_tree(tree: Path, forbidden_tokens) -> dict:
    """Return counts and fixed error codes only; NEVER report copied source bytes.

    Binary files are explicitly NOT scanned. Success is not publication safety.
    """
    tree = Path(tree)
    if tree.is_symlink() or not tree.is_dir():
        raise ProjectionContractError("invalid_test_tree")
    root = tree.resolve()
    if root == ROOT.resolve() or ROOT.resolve() in root.parents:
        raise ProjectionContractError("repository_tree_forbidden")
    if type(forbidden_tokens) not in (list, tuple) or not forbidden_tokens:
        raise ProjectionContractError("missing_synthetic_tokens")
    variants = set()
    for token in forbidden_tokens:
        if type(token) is not str or len(token) < 12 or len(token) > 50000 or not token.strip():
            raise ProjectionContractError("invalid_synthetic_token")
        variants.update(_forms(token))
    counts = {"text_files": 0, "binary_unscanned": 0, "violations": 0,
              "unrecognized_files": 0}
    codes = set()
    for path in sorted(tree.rglob("*")):
        if path.is_symlink():
            codes.add("symlink")
            counts["violations"] += 1
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            codes.add("unsupported_entry")
            counts["violations"] += 1
            continue
        if path.suffix.lower() in BINARY_EXTENSIONS:
            counts["binary_unscanned"] += 1
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            counts["unrecognized_files"] += 1
            counts["violations"] += 1
            codes.add("unknown_artifact_type")
            continue
        counts["text_files"] += 1
        if path.stat().st_size > 8 * 1024 * 1024:
            counts["violations"] += 1
            codes.add("text_file_oversize")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            counts["violations"] += 1
            codes.add("unreadable_text")
            continue
        if any(value in content for value in variants):
            counts["violations"] += 1
            codes.add("synthetic_token_exposed")
        if path.suffix.lower() == ".json":
            try:
                doc = json.loads(content, object_pairs_hook=_unique_pairs)
                if _contains_forbidden_keys(doc):
                    counts["violations"] += 1
                    codes.add("private_field_in_json")
            except (ValueError, TypeError):
                counts["violations"] += 1
                codes.add("invalid_json")
    return {
        "schema": "ipr-synthetic-artifact-audit/1",
        "surface": "synthetic_test_tree_only",
        "eligible_for_publication": False,
        "legal_conclusion": None,
        "counts": counts,
        "finding_codes": sorted(codes),
    }


def _unique_pairs(pairs):
    obj = {}
    for key, val in pairs:
        if key in obj:
            raise ValueError("duplicate_json_key")
        obj[key] = val
    return obj


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-only", action="store_true", required=True)
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--synthetic-tokens-file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        token_path = args.synthetic_tokens_file
        if token_path.is_symlink() or ROOT.resolve() == token_path.resolve() or \
                ROOT.resolve() in token_path.resolve().parents:
            raise ProjectionContractError("repository_tokens_forbidden")
        tokens = token_path.read_text(encoding="utf-8").splitlines()
        report = audit_synthetic_tree(args.tree, tokens)
    except (ProjectionContractError, UnicodeError, OSError):
        print(json.dumps({"schema": "ipr-synthetic-artifact-audit/1",
                          "error": "audit_input_rejected", "eligible_for_publication": False}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 1 if report["counts"]["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
