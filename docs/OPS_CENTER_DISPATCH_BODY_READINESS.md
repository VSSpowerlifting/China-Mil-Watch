# Private Operations Center: body-ready dispatch evidence

This extends the **existing opt-in stored analysis queue section** in the
local Operations Center with a second, separately pinned read-only
observation. It does not add a public site page, independent dashboard,
scheduled run, model request, publisher source or editorial deliverable.

## How an operator uses it

From a local clone of IPR, explicitly request both audits:

```sh
python scripts/operations_center_unified.py \
  --include-analysis-queue --include-dispatch-readiness \
  --db pla_watch.db \
  --json /private/tmp/ipr-ops-readiness.json \
  --html /private/tmp/ipr-ops-readiness.html
```

`--include-dispatch-readiness` requires the existing
`--include-analysis-queue` switch. Existing default reports and existing
queue-only reports do **not** scan text for body readiness, and their
outputs remain the same as before.

The optional section reports:
- Daily-eligible **stored** queue count: source-attributed records in
  the canonical eligible buckets, including records missing source text.
- **Model-input body-ready**: eligible records whose stored original
  body is a true string containing nonwhitespace text.
- **Body withheld for source review**: eligible records without usable
  stored original text, including Unicode-only whitespace and malformed
  stored values. They remain in the archive and are not marked terminal.
- The source/desk breakdown, reconciled against the canonical queue.

The evidence joins only if the **two audited SQLite file identities are
byte-identical**, its queue totals reconcile, and every triage source
identity maps to a source in the canonical report with consistent
counts. A source with only relevance-rejected or completed records may
be absent from the triage report and must have zero Daily-eligible
records. Duplicate, foreign or contradictory source claims refuse the
entire private report before any file is written.

Every response explicitly denies actual future-run workload certainty,
editorial authority, verified extraction or permission to spend. These
figures are historical stored-input observations, not promises that the
next Daily run will analyze exactly that number of records.

## Provenance and privacy

Both audits inspect **temporary, read-only SQLite copies** and reject
changed source hashes. Neither returns article bodies, titles or URLs in
this integration. Output files must be new, outside the repository,
and the existing owner-only private report writer makes the JSON/HTML
pair atomically or cleans up after a failed write. The HTML table
escapes source identifiers and contains no remote assets or JS.

No model calls, collector runs, source refetch, retry authorization,
source rights adjudication, pipeline cap adjustment, publication or
editor delivery occur.

## Dependency / merge gate

PR #301 (the canonical stored-body-readiness source audit) is
already **merged into `main`**. This Operations Center integration
is independently rebased onto `main` with only its five dedicated
files, not duplicate copies of the already-merged audit. Verify the
exact changed-file scope and run focused plus full repository/
Chromium/render/DB-preservation CI on the final exact head.
The branch does not change the source audit itself.

The dedicated focused CI runs current and new synthetic Operations Center
contracts, verifies the actual tracked SQLite pair and resulting private
HTML/JSON on the Actions temporary runner, and asserts database and
published-output preservation. This is diagnostic only.
