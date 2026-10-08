"""Read-only Git-object verifier for v2 topic evidence control candidates.

No network calls, database opens, topic attachment writes, or output generation.
The sample is only a set of provisional editorial examples, never gold labels.
Run from a checkout containing the pinned historical commit and Git blobs:
    python3 scripts/verify_topic_v2_evidence.py
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = ROOT / "research" / "topic_v2_evidence"
TOPICS = (
    "space_security",
    "east_china_sea",
    "export_controls_sanctions",
    "military_hadr",
)
STATUSES = {"positive", "negative", "borderline", "unassessable"}
ENTITY_PATTERN = re.compile(
    r"&(amp|lt|gt|quot|apos|nbsp|#39|#x[0-9a-f]+|#\d+);", flags=re.I
)
TEXT_PATTERN = re.compile(
    r'<div class="original-text"[^>]*>([\s\S]*?)</div>', flags=re.I
)
URL_PATTERN = re.compile(
    r'Original URL</th><td[^>]*><a href="([^"]+)"', flags=re.I
)


def _decode_entity(match: re.Match[str]) -> str:
    value = match.group(1).lower()
    if value.startswith("#x"):
        return chr(int(value[2:], 16))
    if value.startswith("#"):
        return chr(int(value[1:]))
    return {
        "amp": "&", "lt": "<", "gt": ">",
        "quot": '"', "apos": "'", "nbsp": " ",
    }[value]


def _html_decode(value: str) -> str:
    return ENTITY_PATTERN.sub(_decode_entity, value)


def _body_from_archived_html(raw: str) -> str:
    match = TEXT_PATTERN.search(raw)
    if match is None:
        return ""
    no_tags = re.sub(r"<[^>]+>", " ", match.group(1))
    return re.sub(r"\s+", " ", _html_decode(no_tags)).strip()


def _git(*args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        raise ValueError(
            f"git {' '.join(args)} failed: {completed.stderr.decode(errors='replace').strip()}"
        )
    return completed.stdout


def _utf16_units(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def validate() -> list[dict]:
    docs: list[dict] = []
    records: list[dict] = []
    for topic in TOPICS:
        path = EVIDENCE_DIR / f"{topic}.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc["topic"] != topic or doc["sample_version"] != 1:
            raise ValueError(f"{topic}: unexpected evidence version/topic")
        if doc["classification_status"] != "provisional_control_candidates_only":
            raise ValueError(f"{topic}: forbidden classification approval")
        if doc["source_index_path"] != "output/corpus-index.json":
            raise ValueError(f"{topic}: unsupported source index")
        docs.append(doc)
        records.extend(doc["records"])

    source_commits = {doc["source_commit"] for doc in docs}
    index_shas = {doc["source_index_blob_sha"] for doc in docs}
    if len(source_commits) != 1 or len(index_shas) != 1:
        raise ValueError("cross-topic source pins diverge")
    source_commit = next(iter(source_commits))
    index_sha = next(iter(index_shas))
    if _git("rev-parse", f"{source_commit}:output/corpus-index.json").decode().strip() != index_sha:
        raise ValueError("pinned index object does not belong to source commit")
    index = json.loads(_git("cat-file", "blob", index_sha).decode("utf-8"))
    if index.get("snapshot", {}).get("records") != len(index["records"]):
        raise ValueError("corpus index is inconsistent")
    by_id = {row[0]: row for row in index["records"]}
    if len(by_id) != len(index["records"]):
        raise ValueError("duplicate index record IDs")

    seen = set()
    for doc in docs:
        for item in doc["records"]:
            record_id = item["record_id"]
            if record_id in seen:
                raise ValueError(f"duplicate record {record_id}")
            seen.add(record_id)
            if item["review_state"] != "pending_human":
                raise ValueError(f"record {record_id}: no human review is authorized")
            if item["provisional_status"] not in STATUSES:
                raise ValueError(f"record {record_id}: invalid status")
            row = by_id.get(record_id)
            if row is None:
                raise ValueError(f"record {record_id}: absent from index")
            source = index["sources"][row[2]]
            for field, expected in (
                ("source_stated_date", row[1]),
                ("source_slug", source["code"]),
                ("desk_id", source["desk"]["code"]),
                ("title_original", row[5]),
                ("title_english", row[4] or None),
            ):
                if item[field] != expected:
                    raise ValueError(f"record {record_id}: index mismatch for {field}")

            path = f"output/record/{record_id}.html"
            if item["archive_path"] != path:
                raise ValueError(f"record {record_id}: unexpected archive path")
            actual_sha = _git("rev-parse", f"{source_commit}:{path}").decode().strip()
            if item["archive_blob_sha"] != actual_sha:
                raise ValueError(f"record {record_id}: archive blob differs from pinned commit")
            raw = _git("cat-file", "blob", actual_sha).decode("utf-8")
            url = URL_PATTERN.search(raw)
            if url is None or _html_decode(url.group(1)) != item["canonical_url"]:
                raise ValueError(f"record {record_id}: canonical source URL mismatch")
            if not item["canonical_url"].startswith(("https://", "http://")):
                raise ValueError(f"record {record_id}: invalid source URL")
            body = _body_from_archived_html(raw)
            if _utf16_units(body) != item["stored_text_chars"]:
                raise ValueError(f"record {record_id}: normalized text length mismatch")

            evidence = item["evidence"]
            if item["provisional_status"] == "unassessable":
                if evidence is not None or body:
                    raise ValueError(f"record {record_id}: missing-body entry has evidence/body")
            else:
                if not isinstance(evidence, dict) or not evidence.get("quote"):
                    raise ValueError(f"record {record_id}: absent exact source evidence")
                begin, end = evidence["offset_start"], evidence["offset_end"]
                b = body.encode("utf-16-le")
                if not (0 <= begin < end <= len(b) // 2):
                    raise ValueError(f"record {record_id}: invalid excerpt offsets")
                actual = b[begin * 2:end * 2].decode("utf-16-le")
                if actual != evidence["quote"]:
                    raise ValueError(f"record {record_id}: source excerpt mismatch")
            if not item["rationale"].strip():
                raise ValueError(f"record {record_id}: no rationale")

    if len(seen) != 15:
        raise ValueError(f"expected 15 candidate records, got {len(seen)}")
    for topic, doc in zip(TOPICS, docs):
        positives = sum(x["provisional_status"] == "positive" for x in doc["records"])
        if positives < 2:
            raise ValueError(f"{topic}: fewer than two proposed positive controls")
    return records


if __name__ == "__main__":
    rows = validate()
    counts = {label: sum(x["provisional_status"] == label for x in rows)
              for label in sorted(STATUSES)}
    print(f"Topic v2 evidence: {len(rows)} indexed records; "
          f"{counts}; pinned source, blob, identity and excerpt checks PASS")
