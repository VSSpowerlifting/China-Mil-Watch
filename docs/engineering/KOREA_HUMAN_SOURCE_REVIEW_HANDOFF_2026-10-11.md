# Korea Desk — real human source-review handoff

**October 11, 2026** · Ready for a qualified external reviewer, not a completed signoff. See [Korea issue #221](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/221).

The ordinary Korea machine-fidelity audit and source workbench make metadata available, but cannot provide a qualified Korean reader with both the **exact archived HWPX files** and preserved original Korean text for side-by-side review. This stage supplies a secure **local-only** package from one **frozen, already preserved Git snapshot**.

## Reviewer execution (on their own trusted computer)

The reviewer needs Python 3.9+, Git, and local access to the IPR repo (including its `shadow/korea-policy-briefing` branch):

```sh
git fetch origin shadow/korea-policy-briefing
python -m scripts.prepare_korea_human_review \
  --state-repo /absolute/path/to/local/China-Mil-Watch \
  --state-commit dcb43b9c4edb471d6def5876701ec4a2e39d5264 \
  --out /absolute/secure/local/korea-original-review-20261011 \
  --acknowledge-private-originals
```

Output directory **must not exist**, be symlinked or be inside the repository. Folder permissions `0700`, files `0600`; no issuer requests, extra collectors, cloud export, deployment or database mutations. Contents:

- `originals/<newsId>.hwpx` — *actual exact original bytes*, SHA-256 verified from the existing five archived captures. May contain media not licensed for public reproduction; **DO NOT commit/upload/email publicly**.
- `originals/<newsId>.ko.txt` — original Korean text extracted and hashed, for line-by-line comparison to rendered HWPX.
- `reviews/<newsId>.md` — five **record-specific Korean-language review questions**, provenance, date and text-HWPX digests, separate KOGL/media rights checklist.
- `approvals_UNFILLED.json` — machine-readable **intentionally invalid/false/blank** per-original human/rights/owner decisions; never use this as an approved packet.
- `receipt.json` — strictly metadata-only hash and HOLD proof, no text body.
- `README_PRIVATE.md` — handling restrictions and workflow.

The updated private package also includes `reviews/<newsId>.line-hashes.json`: 1-based nonblank physical line numbers and SHA-256 digests from the exact archived `.ko.txt`, without reproducing original Korean bodies in that index. Source-use packets now use `ipr-korea-source-admission/2`: 1–8 unique anchored source lines, their line hashes, statement modality (`announcement`, `plan`, `reported_action`, `assessment`, or `discussion`), private English-claim linkage, and explicit Korean-reviewer confirmation. Old /1 packets fail closed. **The structural gate cannot authenticate those digests against the source or validate their semantic meaning**: the independent reviewer must compare the `.ko.txt`, rendered HWPX, and official page before owner approval.

The CLI checks all five candidate identities and pinned hashes against preserved SQLite and re-extracts the real HWPX; one mismatch blocks the entire package. The script cannot write into `output/`, repo worktrees or any existing review directory. The shadow/source records remain immutable. It uses `scripts.audit_korea_source_fidelity.source_compare`, not a second independent text extractor.

## Human gate (still OPEN)

For each record, an independent Korean-literate reviewer must visually read the original HWPX, compare extraction ordering/terminology/dates and document any discrepancies. A designated rights reviewer verifies the exact public notice and *intended text-only use*, plus whether non-text material is excluded. The IPR owner makes a final record-specific editorial decision. These are three roles, not Python checkboxes.

The `core.korea_reference_gate.approve` validator checks schema and date/hash consistency, **NOT the authenticity of reviewer identity/signature**. Protect completed reviewer notes and authenticated decisions outside public Actions/PR attachments. Source reuse conditions are not a substitute for source review; media are still held even with text-only Type 1 notice.

After genuine authenticated decisions, perform the private, site-matched five-or-fewer record preview introduced in merged PR #416, and only then a separate owner-approved public site release. Korea already has a live **five-link, metadata-only public bibliography**, but still has `status=shadow`, `manifest=null`, and `has_production_records=false`. Approved English descriptors require a separate publication decision; the public bibliography never constitutes original-language signoff or production admission.

## CI and evidentiary boundary

PR-only QA checks real archived five HWPX (not synthetic stubs alone), file-mode privacy, refusal of malformed candidates, BLANK per-source signoffs, and DB/output hash preservation. It **never uploads an Actions artifact**—the entire private source package is deleted after validation. Only a metadata-only count and SHA-free status are logged. Reviewers must generate their own local package using the command above.
