# Operations Center local report file security

The three existing local Operations Center CLIs emit internal operator reports:

- `scripts/operations_center.py` (production and shadow configuration)
- `scripts/operations_center_shadow_overlay.py` (optional candidate overlay)
- `scripts/operations_center_unified.py` (combined source, shadow, optional Actions and queue evidence)

All three share `scripts.operations_center.write_private_reports`, which creates
**new files only** with owner-only POSIX file permissions (`0600`, subject to a
more restrictive caller umask). It refuses to replace existing files and, if
any output fails, deletes only newly created outputs with their original
inode/device identities; an external actor's replacement is not removed.
A pair of reports is *not* an atomic transaction against concurrent readers.

Before writing, callers still use `safe_destination` to prevent report output
inside the repository, including the public `output/` tree. Every report
remains strictly a local, human-review tool: no source promotion, publication,
collector execution, model authorization, editor delivery, or proof of live
pipeline success is conferred by the output file. The unified command stays
network-free unless `--fetch-daily-utc-day` is explicitly selected.

The regression suite `tests.test_operations_center_private_reports` covers
owner-only permissions, existing-file and symlink refusal, rollback on second
file failure and encoding failure, and identity preservation on replacement.
