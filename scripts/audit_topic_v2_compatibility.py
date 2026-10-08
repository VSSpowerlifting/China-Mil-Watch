"""Audit versioned regional-topic metadata; never promote or write assignments.

Run: python3 scripts/audit_topic_v2_compatibility.py [--format json]
Read-only local JSON inputs, stdout-only output, no database or network.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V1_PATH = ROOT / "taxonomy" / "regional_topics.v1.json"
V2_PATH = ROOT / "taxonomy" / "regional_topics.v2.json"
V1_GIT_BLOB = "a068839cb0bd9227b3edcc92991e21865119c23a"
TAXONOMY_ID = "ipr_regional_topics"
TOPIC_FIELDS = ("display_name", "group", "description", "scope_note")
MODIFIED_LEGACY_FIELDS = {
    "force_posture_basing": ("scope_note",),
    "defense_diplomacy": ("scope_note",),
    "alliances_partnerships": ("scope_note",),
    "procurement_acquisition": ("scope_note",),
    "emerging_technology": ("scope_note",),
    "cyber_information": ("scope_note",),
    "space_security": ("scope_note",),
    "east_china_sea": ("scope_note",),
    "export_controls_sanctions": ("scope_note",),
    "critical_minerals_supply_chains": ("display_name", "description", "scope_note"),
    "doctrine_strategy": ("scope_note",),
}
NEW_SLUG = "military_hadr"
NO_PROMOTION = (
    "No automatic label promotion: matching slugs do not authorize moving "
    "record_topics rows from taxonomy_version=1 to taxonomy_version=2."
)


class CompatibilityError(ValueError):
    """V1/v2 compatibility contract differs from the reviewed proposal."""


def require(ok, message):
    if not ok:
        raise CompatibilityError(message)


def blob_sha(raw):
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).hexdigest()


def load_file(path):
    raw = Path(path).read_bytes()
    obj = json.loads(raw.decode("utf-8"))
    require(type(obj) is dict, "taxonomy must be a JSON object")
    return obj, {
        "git_blob_sha": blob_sha(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def index_topics(taxonomy, version):
    require(type(taxonomy) is dict, "taxonomy must be a JSON object")
    require(taxonomy.get("taxonomy_id") == TAXONOMY_ID,
            "taxonomy identity changed")
    require(type(taxonomy.get("taxonomy_version")) is int and
            taxonomy["taxonomy_version"] == version,
            "requested taxonomy version differs from file")
    require(type(taxonomy.get("groups")) is list and
            type(taxonomy.get("topics")) is list,
            "invalid group/topic arrays")
    groups = taxonomy["groups"]
    group_ids = []
    for group in groups:
        require(type(group) is dict and
                type(group.get("slug")) is str,
                "invalid group metadata")
        group_ids.append(group["slug"])
    require(len(group_ids) == len(set(group_ids)),
            "duplicate group identifiers")
    indexed = {}
    for row in taxonomy["topics"]:
        require(type(row) is dict and set(row) == (
            {"slug"} | set(TOPIC_FIELDS)), "unexpected topic fields")
        slug = row["slug"]
        require(type(slug) is str and slug and slug not in indexed,
                "invalid or duplicate topic slug")
        for field in TOPIC_FIELDS:
            require(type(row[field]) is str and row[field].strip(),
                    "blank or malformed topic definition")
        require(row["group"] in group_ids, "unknown topic group")
        indexed[slug] = row
    return indexed


def audit(v1, v2, *, v1_pin, v2_pin, v1_sha256="", v2_sha256=""):
    """Compare only vocabulary definitions; no per-record assignment access."""
    require(v1_pin == V1_GIT_BLOB,
            "v1 reference blob changed; preserve frozen v1")
    old = index_topics(v1, 1)
    new = index_topics(v2, 2)
    require(len(old) == 19 and len(new) == 20,
            "unexpected topic count")
    require(v1["groups"] == v2["groups"],
            "group metadata changed")
    require(set(old).issubset(new), "deleted or renamed legacy topic")
    require(set(new) - set(old) == {NEW_SLUG},
            "new v2 topics differ from reviewed HADR addition")
    require(new[NEW_SLUG]["group"] == "operations",
            "HADR group no longer operations")
    changed = {}
    for slug, prior in old.items():
        fields = tuple(
            f for f in TOPIC_FIELDS if prior[f] != new[slug][f]
        )
        if fields:
            changed[slug] = fields
    require(changed == MODIFIED_LEGACY_FIELDS,
            "unreviewed v2 definition changes; update review boundary first")

    rows = []
    for slug in sorted(old):
        fields = list(changed.get(slug, ()))
        rows.append({
            "slug": slug,
            "change": "definition_changed" if fields else "unchanged",
            "changed_fields": fields,
            "v1": {f: old[slug][f] for f in TOPIC_FIELDS},
            "v2": {f: new[slug][f] for f in TOPIC_FIELDS},
            "requires_scope_review": bool(fields),
            "automatic_record_promotion": False,
        })
    rows.append({
        "slug": NEW_SLUG,
        "change": "new_topic",
        "changed_fields": ["new_topic"],
        "v1": None,
        "v2": {f: new[NEW_SLUG][f] for f in TOPIC_FIELDS},
        "requires_scope_review": True,
        "automatic_record_promotion": False,
    })
    return {
        "report_version": 1,
        "taxonomy_id": TAXONOMY_ID,
        "versions": [1, 2],
        "pins": {
            "v1": {"git_blob_sha": v1_pin, "sha256": v1_sha256},
            "v2": {"git_blob_sha": v2_pin, "sha256": v2_sha256},
        },
        "summary": {
            "v1_topics": len(old),
            "v2_topics": len(new),
            "legacy_slugs_unchanged": len(old),
            "identical_legacy_definitions": len(old) - len(changed),
            "modified_legacy_definitions": len(changed),
            "new_topics": 1,
            "automatic_assignment_promotions": 0,
        },
        "safety": {
            "v1_default_preserved": True,
            "v2_explicit_version_required": True,
            "old_assignments_stay_on_v1": True,
            "no_human_approval_implied": True,
            "no_promotion_rule": NO_PROMOTION,
        },
        "changes": sorted(rows, key=lambda x: x["slug"]),
    }


def audit_files(v1_path=V1_PATH, v2_path=V2_PATH):
    old, pin1 = load_file(v1_path)
    new, pin2 = load_file(v2_path)
    return audit(
        old, new,
        v1_pin=pin1["git_blob_sha"],
        v2_pin=pin2["git_blob_sha"],
        v1_sha256=pin1["sha256"],
        v2_sha256=pin2["sha256"],
    )


def render_markdown(report):
    summary = report["summary"]
    lines = [
        "# Regional Topic v1 to v2: source-pinned, read-only compatibility",
        "",
        "Not a migration, classifier, record approval or production activation.",
        "",
        "V1 topics: %d; v2 topics: %d; modified old definitions: %d; "
        "identical old definitions: %d; new topics: %d."
        % (summary["v1_topics"], summary["v2_topics"],
           summary["modified_legacy_definitions"],
           summary["identical_legacy_definitions"], summary["new_topics"]),
        "",
        "V1 Git blob SHA: " + report["pins"]["v1"]["git_blob_sha"],
        "V2 Git blob SHA: " + report["pins"]["v2"]["git_blob_sha"],
        "",
        report["safety"]["no_promotion_rule"],
        "",
        "| Slug | Change | Changed fields | Scope review |",
        "|---|---|---|---|",
    ]
    for item in report["changes"]:
        lines.append("| %s | %s | %s | %s |" %
                     (item["slug"], item["change"],
                      ", ".join(item["changed_fields"]) or "none",
                      "required" if item["requires_scope_review"]
                      else "no definition change"))
    lines.extend([
        "",
        "Even unchanged definitions are not approval to carry record-level "
        "assignments forward. All v2 assignments require separately "
        "approved and source-specific editorial review.",
        "",
        "This audit reads local taxonomy JSON only; no DB, UI or records.",
        "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("markdown", "json"),
                        default="markdown")
    args = parser.parse_args()
    try:
        report = audit_files()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, "Taxonomy compatibility audit failed: %s\n" % exc)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
