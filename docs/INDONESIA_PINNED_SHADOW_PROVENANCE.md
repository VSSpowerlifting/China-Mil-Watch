# Indonesia Kemhan pinned shadow provenance — narrow research verifier

This is a **read-only, offline Phase 2 precursor** for [Operations Center issue #250](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/250). It inspects **one** explicit source family, `id_kemhan_news`. It does not import or require the Phase 1 dashboard in PR #249.

## Inputs and execution

Provide a local clone containing the `refs/heads/shadow/indonesia-kemhan` branch, a **literal immutable commit SHA** within that branch's ancestry, and a complete exported GitHub Actions workflow-runs JSON response (single page or `gh api --paginate --slurp` array). The command itself makes **no network calls**:

```bash
python scripts/audit_indonesia_shadow_provenance.py \
  --state-repo /path/to/state-clone \
  --state-commit <40-character-state-commit> \
  --actions-export /path/to/workflow-runs-export.json
```

This is not a collector, state-mutating operation, scheduled checker, human review, rights review, desk-promotion decision, Sunday Brief eligibility gate, or approval of editor email delivery. Do **not** add the state branch to the production manifest to run it.

The source and workflow identities are explicit and intentionally singular:
`shadow/indonesia-kemhan`, `Indonesia and South Korea Shadow Collection`, workflow ID `376840713`. Korea runs from that *shared* workflow are not Indonesia evidence. The source's original `local-native-...` Day 0 run is local research, not a GitHub Actions schedule. A `workflow_dispatch` continuation is manual, even when it has the same date as a scheduled run.

## What is actually verified

- A pinned state Git commit exists on the declared state-branch history. Git reads the specified tree **without changing the working directory** and requires `state/clock.json`, `state/shadow.db`, and bounded ledger files.
- The initial ledger agrees with the Day-0 clock; subsequent ledgers have monotonic run intervals and match their predecessor's `state_sha256_after` via `state_sha256_before`.
- The SHA-256 computed from **actual pinned SQLite bytes** equals the latest ledger's `state_sha256_after` (stronger than comparing ledger text to ledger text).
- Every non-local ledger matches an Actions export entry on workflow ID/name, run ID, attempt, main-branch collector commit, event and successful conclusion; scheduled dates must agree with the ledger's logical date.
- The entire supplied Actions pagination must be complete *as declared by the export*. Rejection on missing/duplicate runs, malformed hashes, source failures, changed dates or mismatched manual/scheduled identities.

## What it does **not** verify

The supplied Actions export is **not independently authenticated** by this script. Its query coverage, GitHub API origin, missing failed attempts, and jobs/artifacts are not proven. The script also does not rehash individual source captures, validate the licensing of publisher material, certify all expected future/past schedule slots, infer coverage completeness, or authorize production/Briefs.

A successful output must always say `pinned_state_and_supplied_actions_consistent_not_qualified`, with all rights, review, production and editor-delivery flags **false**. It is a historical positive research receipt, not a live health badge.

## Testing

```bash
python -m unittest tests.test_indonesia_shadow_provenance -v
```

Fixtures construct temporary local Git repositories and synthetic ledger/Actions histories. They test byte-hash alteration, missing/unreachable commits, branch identity, Actions mismatches, incomplete pagination, manual/scheduled separation, and no working-tree mutation. Run the regular full PR offline CI before merge.

**Next phase:** a separately authorized, read-only Actions API fetch and immutable export receipt with signed/reproducible query scope, jobs/step evidence, schedule-slot gap accounting and publisher-rights/owner-review joins. Keep this out of production.
