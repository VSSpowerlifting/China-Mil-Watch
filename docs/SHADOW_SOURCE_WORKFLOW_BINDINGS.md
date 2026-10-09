# Shadow source-family → workflow/state branch declarations

**Status:** Internal declaration-only contract; **not** live run evidence, source authorization, production qualification, or an Operations Center health feed.

## Why it exists

Eleven isolated `shadow/*/manifest.json` files currently declare **16 source slugs**. Their `desk_id` values are not unique to an isolated collector: Philippines AFP and NSC share the Philippines identity, Vietnam has three ministry families under one desk, and the Japan MOD manifest includes multiple source slugs. The `enabled` boolean in a shadow manifest does **not** mean production is enabled.

The explicit mappings in `config/shadow_source_workflow_bindings.json` bind each declared source slug and manifest to its exact state branch, workflow and *declared* UTC cron, where one exists. These mapping decisions are subject to human review. A new source family or changed schedule must update the mapping in the same PR, rather than being silently counted as one of its country's existing collectors.

## Verify

```sh
python scripts/audit_shadow_workflow_bindings.py
python -m unittest tests.test_shadow_workflow_bindings -v
```

The audit reads only the checked-out manifest and workflow files. It does not contact GitHub Actions, read or fetch shadow branch state, call live publishers, write to `pla_watch.db` or `output/`, or advance any collection schedule.

It fails if a manifest/source is missing or added without a mapping, a source is duplicated, a manifest stops being an isolated nonproduction declaration, a mapped workflow is missing, an expected cron becomes commented out, a manual-only workflow gains a schedule, or a mapped state branch disappears from workflow code. Indonesia/Korea's shared workflow has an **additional** country-to-branch-and-cron case-arm check; the Vietnam ministry shared workflow has a **source-to-branch** case-arm check. This prevents a green result from merely seeing both possible branch names in the same YAML.

`vietnam_journal` is currently classified `research_only` with **no declared collector workflow or state branch**. `us_indopacom` and the original `vietnam` pilot are `manual_only`, even if comments discuss a hypothetical future cron. Singapore's isolated shadow workflow is historical/configuration evidence and must never double-count the separate production Singapore desk.

### Limitations

This is intentionally an offline conservative *static contract*, not a YAML parser or runtime control-flow proof. Presence of an active-looking YAML cron and a code-level branch token still cannot establish that a particular scheduled job executed, selected the intended input, succeeded, published its immutable ledger, or complied with source-use rights. The audit does not authenticate GitHub workflow configuration against an independently pinned upstream SHA. The general Operations Center must label these results `declaration_only` until additional Actions, state-branch, source-specific receipt, clock, review and license checks complete. In particular, do not interpret `cron_and_branch_literals_found_not_run_verified` as a health verdict.

Existing publication, editorial and source admission restrictions are unchanged. No changes to tracked source records or automated Brief generation are authorized by this map.

## Later

After this declaration baseline, Phase 2 [issue #250](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/250) can consume the map as *input* for per-family scheduled-slot audits. Those future monitors must authenticate Actions run event/attempt/status, inspect immutable state hashes, distinguish manual recovery, verify rights, and fail closed on missing or conflicting evidence. The existing Indonesia pilot [PR #255](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/255) demonstrates the next stage without modifying these mappings.
