# Private Sunday manuscript snapshot — disabled operator helper

**Issue:** #366. **Branch:** independent three-file PR on main. **Status:** inert library/test only; no workflow, SMTP, model, owner approval, legal clearance or deployment.

## Missing seam

The existing manual first-Sunday replay accepts an on-disk owner-reviewed TXT and validates its digest. A later live sender can reopen the same path, creating a change-between-check-and-use risk if a downloaded or working copy is edited after review. The reviewed manuscript also has no code-defined durable private copy; keeping an attachment temporarily in email is not the same as controlled preservation.

This module provides the narrow, preparatory **copy-once snapshot primitive**: `core/sunday_private_reviewed_snapshot.freeze_exact_reviewed_attachment(source, private_dir, expected_sha256=...)`. It targets **only October 10, 2026**, and uses the existing source-bound first-pilot `inspect_file` to reject an incomplete or invalid article. No original-language content is scraped, generated, published, logged or sent.

## Storage and byte identity

- Require an explicit absolute input path, a caller-owned regular file with **one hardlink**, and one bounded descriptor read using `O_NOFOLLOW` where supported; reject changing size/timestamps/inode during that read.
- Demand a separately supplied **exact lowercase SHA-256** of the owner-reviewed attachment before copying. Equality alone **does not authenticate** who approved that hash or prove source reuse rights.
- Require an existing caller-owned **0700 private directory**, not symlinked at its final path and **not inside the public repository worktree**, including under `output/` or a private subfolder. The helper enforces this refusal using **both the lexical absolute directory path and the resolved target**; symlinked parent directories under public Git cannot redirect snapshot writes into otherwise private external storage. The operator must arrange that directory and approve its retention/backups; this code does not provision a cloud store.
- Create one named file based on (pilot Saturday, approved digest) with `O_CREAT|O_EXCL`: never overwrite, follow a malicious preexisting symlink, or silently reuse a prior copy. Write exact original bytes, flush/fsync file, restrict it to **0400**, validate its actual on-disk bytes and existing full packet structure, then fsync the directory.
- On handled failures remove the candidate created by this invocation. A hard kill/power failure can leave a **partial private snapshot**; the next attempt safely refuses the existing filename rather than rewriting it. Recovery and comparison against actual owner evidence are human decisions.
- Return only a private path, source digest, Saturday and byte count. Keep the returned path out of CI artifacts and any public issue description, and do not log private article/source content.

**Threat boundary:** file mode 0400 is a deterrent to accidental writes, **not cryptographic immutability**. The directory owner/root can modify, rename, delete or restore stale snapshots. A separate protected, rollback-detecting custody receipt and authentic human approval are still required before relying on this for real SMTP. OS and trusted parent-directory semantics are assumed; networked filesystems are not certified.

## 15 synthetic regression tests

`python -m unittest tests.test_sunday_private_reviewed_snapshot -v`

Tests cover exact SHA/unchanged copy, read-only mode, post-freeze input rewrite, duplicate refusal, wrong digest, malformed digest, wrong week, source symlink/hardlink, permissive, symlinked, repository-contained or checkout-symlink-routed private directory, incomplete editorial TXT clean-up, preexisting symlink trap, and competing file-freeze workers. Checks that no mock SMTP or model composition is invoked. No use of actual owner manuscript; fixture comes from the existing Sunday synthetic worksheet builder.

The library has no command-line entry point, network API, scheduled workflow, real mail or model dependencies beyond importing the existing inspector. It does not modify the actual replay function. Separate integration into an authenticated approval-and-replay adapter must be reviewed and authorized on its own branch, and must avoid rereading mutable source input after freezing. Do not enable Sunday's scheduled model or delivery flags from this PR.
