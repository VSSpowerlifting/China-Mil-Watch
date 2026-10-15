# Cross-desk Actions original-artifact expiry inventory (October 15, 2026)

The owner created a separate [private IPR government-original vault](https://github.com/VSSpowerlifting/ipr-source-evidence-private). Its two private pilot refs contain **fictional** captures and readback proofs, not real publisher documents. The public repo's collector workflows remain unchanged. [Custody #332](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/332), [implementation #342](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/342) and [private vault issue #1](https://github.com/VSSpowerlifting/ipr-source-evidence-private/issues/1) govern the future evidence transfer, written-consent/source-retention rights, restricted account access and independent backup.

## Why this additional audit

The existing desk-specific evidence audits already validate Indonesia/Korea attempts and source states, Vietnam logical dates and packet fidelity, and AFP seven-slot collection. **Do not replace them.** This PR supplies the missing *cross-desk expiring-artifact triage* layer: enumerate every **retained** GitHub Actions collector run in a bounded **creation-date** window, inventory every returned Actions artifact under that run, identify earliest expiration timestamps, and flag both rerun attempts and unassigned/unlabeled attempt receipts. No archive ZIP is downloaded, no source-body or publisher endpoint is opened, no rights grant is inferred, no collector is dispatched and no record is promoted.

Actual [Vietnam bootstrap run 37656171920](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37656171920) has **two separate retained artifacts**: failed attempt 1 ID `11498114543` expires **January 5, 2027 at 17:04:25 UTC**, and successful attempt 2 ID `11499686512` expires **January 5 at 17:15:50 UTC**. They must remain separate in the custody inventory; a green rerun does not erase evidence from the failed attempt. [AFP Oct 7 artifact 11487280883](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37631681338) expires January 5 at 13:50:12 UTC; Korea and Indonesia also have January 5 original-source artifacts. Check the live provider expiration value at each future audit, not a hardcoded fixed deadline.

## Operator-only authenticated, metadata-only census

Run in an **already authenticated** owner-controlled shell with the GitHub CLI installed. Output is intended for restricted local review and is not automatically published or uploaded. Do not paste CLI tokens, publisher bodies or private ZIPs into PRs or comments.

```sh
# Example at a later owner-audited run: replace timestamp with actual UTC now
python3 scripts/inventory_ipr_actions_artifact_expiry.py \
  --from-date 2026-10-07 \
  --through-date 2026-10-15 \
  --as-of-utc YYYY-MM-DDTHH:MM:SSZ \
  --out /restricted/evidence-inventory/collector-actions-20261015.json
```

`--as-of-utc` must be a **real UTC timestamp at or before the operator's collection time**. The implementation fixes repo scope to `VSSpowerlifting/China-Mil-Watch` and requires 1–35 contiguous calendar days from October 1 onward, not a selector the caller can use to query another account or endpoint. It invokes `gh api --method GET` for each day's `schedule`/`workflow_dispatch` collection runs (under each day’s **complete repo Actions run listing**, not fragile top-5 workflow search) and checks stable GitHub `total_count`, every pagination page, unique run IDs and `created_at` date. It then paginates every retained in-scope run's artifacts, validates scope and expiry, and records names/IDs/byte counts/attempt labels. Each artifact’s `name_attempt` is inferred **only** if its filename ends in the proven `-<run_id>-<attempt>` pattern; ledger-only/no-suffix names remain ambiguous.

**Retained-run coverage** includes active Indonesia/Korea shared workflow, AFP and NSC, Vietnam ministry and legacy Vietnam shadow, Singapore MINDEF, Japan MOD, Japan JCG guarded and JCG manual. An event/path outside this declared list is ignored; review workflow name additions before claiming family exhaustivity. Multiple jobs in a shared Indonesia/Korea run do not automatically establish which original-source family was selected; desk-specific audits must reconcile source identity. This tool currently provides **no per-attempt historical job log fetch**, so it cannot authenticate all unsuccessful job attempts for a rerun from retained `run_attempt` alone. Missing individual attempt-labeled artifacts generate a hold.

**Explicit output limits:** only the *retained* repository API catalog at audit time, not deleted runs, expired artifact contents, actual source-original bytes, provenance of captured bytes inside the ZIP, rights, or backup. An artifact reported `expired=false` may still later vanish; capture the live provider metadata receipt and preserve its exact evidence before expiry under source-specific lawful retention. A zero-result day is not a green desk-qualification result; compare to the governing schedule and source-specific expected ledger dates separately. Retention report `production_cutover_authorized=false` is unconditional.

The worktree-output guard prevents overwriting an existing evidence-inventory JSON. No artifact-download endpoint, GitHub App writer, API secret in PR contexts, scheduled monitoring, source-state mutation, shadow-state promotion, permission flag, website deploy or private-vault data write is present.

## Release and verification

- `python3 -m unittest tests.test_ipr_actions_artifact_retention_inventory -v` — pure fake API; tests two distinct Vietnamese bootstrap attempt artifacts, pagination coverage and duplicate/stale-page rejection, failed/no artifacts, expired artifacts, mislabeled source/run, out-of-window/refused account, and no secret-bearing CLI errors.
- Require exact-head *focused* PR contract workflow and the repository-wide offline suite to pass before merging. If either fails, correct only the audit logic/tests, not historical source ledgers.
- After an authorized merge, run the tool once in an **owner-controlled authenticated environment** and check its full retained inventory against existing desk-specific source receipts; compare all run attempts with job histories where needed. A complete inventory does not create an independent encrypted backup or legal permission to retain the data.
- Before shrinking the full-state AFP Actions artifact upload under [draft #606](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/606), independently copy and restore-verify every retained original unique to unsuccessful attempts. Do **not** remove/delete/force-push any historic evidence on the strength of this metadata report.

**No original has been transferred by this PR.** The owner-approved private-vault direction and independent encrypted backup work remain distinct. No production, public website, model, editor email, source-rights decision or permanent migration is authorized.
