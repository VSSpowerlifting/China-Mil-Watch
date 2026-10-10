# Living Dossiers B1.3 — private validation and editor handoff

**Status:** nonpublishing engineering prototype, stacked on B1.2 [PR #329](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/329), which itself depends on B1.1 [PR #328](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/328). No live Dossier has been created or approved.

## What this slice implements

\`scripts/validate_dossiers.py\` offers a **private** CLI that reads canonical Dossier sidecars, uses B1.1 to validate their shape, uses B1.2 to compare source references against a scratch-copy **read-only** SQLite database and the declared public collecting-source registry, and returns a metadata-only review packet. It intentionally cannot approve or publish anything.

The CLI runs in Python 3.9+ without extra dependencies beyond those of the existing repository, and requires three arguments for an explicit review:

~~~sh
python scripts/validate_dossiers.py \
  --source-dir dossiers \
  --db pla_watch.db \
  --report /tmp/ipr-dossier-review-PRIVATE.json
~~~

**Do not actually populate \`dossiers/\` with a live pilot until [#319](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/319) human scope approval and [#326](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/326) source-use review.** Without such files, the CLI reports \`no_dossiers\` and does not authorize a public library. This is an API demonstration, not a request to process production records now.

A private review file must be **new, absolute, JSON-suffixed, outside the repository**, in an existing non-symlinked directory; the command refuses overwriting it. It is created exclusively with POSIX mode \`0600\` so it is not a committed/site-accessible artifact. Do not upload the report to public CI artifacts, attach it to GitHub issue comments, place it in \`output/\`, or include private permission correspondence in any field.

## Example result: fictional sources only

~~~json
{
  "schema": "ipr-dossier-private-review/1",
  "status": "review_hold",
  "eligible_for_publication": false,
  "dossier_count": 1,
  "mechanically_valid_count": 1,
  "error_count": 0,
  "hold_count": 7,
  "errors": [],
  "dossiers": [
    {
      "input": "sidecar",
      "slug": "fictional-exercise-reporting",
      "status": "review_hold",
      "structure_valid": true,
      "archive_reconciled": true,
      "eligible_for_publication": false,
      "content_sha256": "<calculated 64-hex digest>",
      "selected_record_ids": [900001, 900002],
      "errors": [],
      "holds": [
        {"code": "screening-pending-human-review"},
        {"code": "independent-source-admission-required"},
        {"code": "independent-source-use-decision-required"},
        {"code": "independent-source-admission-required"},
        {"code": "independent-source-use-decision-required"},
        {"code": "human-claim-and-inference-review-required"},
        {"code": "independently-authenticated-editorial-approval-required"},
        {"code": "publication-renderer-not-authorized"}
      ]
    }
  ]
}
~~~

**Note:** This is an illustrative excerpt of the report **structure**, not a captured run artifact; the list contains eight holds, so a real emitted result would say \`hold_count: 8\`, not 7. The test suite asserts the actual counts from code, and users should rely on the actual report rather than this diagram.

### Return and exit semantics

- \`exit 0\`: no mechanical errors, possibly **multiple human review holds**; must NEVER be interpreted as source approval or readiness to publish. Empty input also exits 0, with \`status: no_dossiers\`.
- \`exit 1\`: malformed Dossier or mismatched source integrity/eligibility. All selected inputs are reported individually; invalid input does not become approved because another input was valid.
- \`exit 2\`: unsafe or unavailable private report destination; refuse writes and send a generic, non-source-revealing message to stderr.

A report exposes only safe fixed error/hold codes, validated slugs, numeric record IDs, counts, reconciliation state and SHA digest; **no publisher text, source excerpts, machine reasoning, private research notes or contact correspondence** is copied into the output. This is a diagnostic convention, not a claim that the actual Dossier has been human-reviewed.

## Security and lifecycle posture

- One repo-owned B1.1 contract parses JSON and rejects duplicate object keys, invalid fields, symlinks and path traversal.
- One repo-owned B1.2 reconciler compares records and SHA-256 over archived original text from \`read_only()\` scratch SQLite; it does not update production SQLite or source models.
- This CLI uses both and **hard-sets \`eligible_for_publication: false\`** regardless of apparently approved JSON, screening output, or fabricated permission references.
- Because stored publisher-text errors could contain sensitive or copyrighted material, malformed files emit **generic diagnostic codes** rather than reflecting their content or arbitrary exception strings.
- The CLI has **no** \`--approve\`, \`--publish\`, \`--force\`, SMTP, model, collector, cron, renderer hook or automatic source reclassification. It never replaces old published Briefs, Timelines or public archive HTML.
- Rights permission to link, quote, reproduce full text or use a third-party image can only come from an independently reviewed external source-use decision. B1.3 neither claims such a decision exists nor verifies a permit.
- An internally consistent approval digest is **not** authentication of Benjamin Yang's decision or any other human. Separate owner authority is required before B2.

## Synthetic verification and merge sequence

\`tests/test_validate_dossiers.py\` tests the CLI with invented \`example.org\` records, synthetic SQLite and a fake registry, including invalid JSON, forged approval and permission references, known screening rejection, archived-body drift, mixed valid/invalid input, \`0600\` permissions, path/symlink/refuse-overwrite boundaries, no publisher-body leakage and unchanged original SQLite bytes.

Run the three synthetic suites (no production DB or network access):

~~~sh
python -m unittest tests.test_dossier_contract tests.test_dossier_sources tests.test_validate_dossiers -v
~~~

This is the **third, deliberately stacked** engineering slice. Correct merge order:

1. #328 — pure source/claim/editorial-version JSON contract.
2. #329 — synthetic SQLite and manifest source-parity checker (retarget to main after #328).
3. B1.3 CLI PR — retarget to main only after #329; rerun exact-head full CI after each dependency changes.

**Stop:** private review reporting complete. No real Singapore Dossier sidecar, no production source admission, no public Analysis route, no rights workaround, no frontend integration or automatic merge/deploy. Any B2 publication attempt is a fresh, separately approved project.
