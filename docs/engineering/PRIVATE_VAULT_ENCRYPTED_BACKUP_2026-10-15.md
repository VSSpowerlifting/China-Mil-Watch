# IPR Private GitHub vault — offline encrypted backup and restore

**October 15, 2026. Pre-cutover supporting code only.** This is a separate small work package within [architecture #332](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/332), [program #342](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/342) and the verified [private vault](https://github.com/VSSpowerlifting/ipr-source-evidence-private). The owner selected a **separate private GitHub repo** as primary source-original custody. Its 15 October `main` contains policy only, and two `pilot/fictional-*` branches contain **fictional, harmless synthetic bytes**. The private vault is **NOT an independent backup of itself**.

The new `scripts/private_vault_encrypted_bundle.py` creates a **whole-native-Git-history** `git bundle` piped directly into **GnuPG encryption**. It never creates an intermediate plaintext `*.bundle` file on backup, never prints original names, body text or GPG error data and requires a **local, trusted, exact 40-hex-digit GPG encryption-key fingerprint**. Restore decrypts into a fresh restricted `0700` temporary folder, fetches **all pinned Git ref namespaces** (`refs/*`, including branches, tags, notes and custom archive refs), validates the expected pinned refs, runs `git fsck`, checks the expected reachable object count, and cleans the plaintext directory on exit. A plain `git clone --bare` was rejected for recovery because it drops notes/custom refs; the recovery fixture now tests these namespaces explicitly. The bare repository's symbolic `HEAD` target is not attested by this pinned-ref verification and must be configured separately by a recovery operator before relying on its default branch. A SHA-256 fingerprint of the ciphertext is retained as an integrity check **but is not a cryptographically signed owner attestation by itself**.

## Backing up — privileged operator shell only

First obtain a **complete, local, bare Git mirror** of the intended approved private repository, after owner review of access and original retention rights. Confirm all source and failed-only attempt copies have been imported and the vault ref inventory is frozen. Do **not** perform this on the public PR runner or supply secrets to any `pull_request` event.

Use an existing locally trusted GPG public encryption key, not a token or password typed into GitHub. In an owner-controlled terminal, generate/verify the exact encryption-key fingerprint (off GitHub), separately retain its **secret decryption key in secure offline custody**, and record a recovery contact. `gpg --list-keys --with-fingerprint` can show candidate fingerprints, but selecting the correct key is a human cryptographic identity decision; do not trust a key by a name alone. This script accepts only a 40-character hex fingerprint and verifies that the key actually exists in the local GPG keyring.

For example, *after* an actual approved private mirror and ref-freeze (illustrative placeholders, **not** a command to execute with real government data today):

```sh
python3 scripts/private_vault_encrypted_bundle.py backup \
  --bare-repo /secure/ipr-vault-mirror.git \
  --encrypted-output /secure/backup-device/ipr-vault-frozen.bundle.gpg \
  --recipient-fingerprint REPLACE_WITH_YOUR_40_HEX_FINGERPRINT \
  --expect-ref refs/heads/main=REPLACE_WITH_EXACT_40_HEX_COMMIT \
  --expect-ref refs/heads/pilot/fictional-custody-20261015=REPLACE_WITH_EXACT_40_HEX_COMMIT
```

**All named refs must be pinned**: the tool requires the exact entire local Git ref inventory to equal the owner-supplied `--expect-ref` set. Unexpected new branches, modified tips, tags or notes **fail closed**, rather than producing a superficially successful incomplete freeze. The bundle uses `--all` and includes only **reachable, referenced Git history**, not pruned/dangling objects, failed run ZIP-only evidence unless separately imported, or Git LFS file bytes (a Git bundle retains pointers without external LFS objects). Large Git histories may need a different provider/capacity plan. Never delete expired Actions artifacts before a reviewed independent private copy and recovery evidence.

Output is a ciphertext file written with restrictive `0600` permissions and an atomic no-clobber hard-link publish; it will not overwrite an existing snapshot. It also refuses output paths inside **any** Git worktree or bare Git repository—not merely inside the source mirror—so an operator cannot accidentally stage the custody ciphertext in the public IPR repository or another checkout. The script **checks the entire pinned ref map and native reachable-object count again after the encrypted Git stream finishes**, so a source branch modified during backup causes `HOLD` and deletion of the uncommitted temporary ciphertext instead of publishing a misleading snapshot. Ciphertext is flushed before publication. Treat a forced branch rewrite that briefly changes and restores identical refs as a separate incident to be addressed with protected writers and an external immutable checkpoint; static ref checks cannot prove writer trust. The returned JSON lists only exact ref SHA identifiers, ciphertext size and SHA-256 digest, and reachable object count. It always reports `independent_backup_medium_verified=false` and `independent_restore_passed=false`. **Creation alone does not qualify it as an independent encrypted backup.**

## Restoring on a different machine or medium

Transfer the ciphertext to **independent durable encrypted/offline media**, and check its SHA-256 at the destination. The owner-controlled recovery machine must independently possess the correct **private GPG decryption key** and have a protected, spacious scratch directory. Restore is deliberately **read-only** with respect to GitHub source and destination; it only creates and removes its own decrypted temporary files on the local trusted scratch disk.

```sh
python3 scripts/private_vault_encrypted_bundle.py restore \
  --encrypted-input /offline-backup/ipr-vault-frozen.bundle.gpg \
  --expected-sha256 REPLACE_WITH_BACKUP_CIPHERTEXT_SHA256 \
  --expected-object-count REPLACE_WITH_ORIGINAL_OBJECT_COUNT \
  --scratch-dir /secure/private-recovery-scratch \
  --expect-ref refs/heads/main=REPLACE_WITH_EXACT_40_HEX_COMMIT \
  --expect-ref refs/heads/pilot/fictional-custody-20261015=REPLACE_WITH_EXACT_40_HEX_COMMIT
```

Run a source-specific capture SHA-256 and SQLite `integrity_check`/foreign-key check **after** a real restore, plus full source/collector attempts and Git LFS parity where relevant. This script does not inspect publisher bodies or attest source-use rights; it cannot authenticate that the ciphertext is physically off-platform or that the private key is safe. Hardware-device/media restoration and key escrow have to be evidenced manually in a restricted handoff.

## Offline integration validation

```sh
python3 -m unittest tests.test_private_vault_encrypted_bundle -v
```

A GPG export timeout is a **HOLD**: both the Git producer and GPG child are reaped, any partial ciphertext is removed, and no backup is published. The failure-path test simulates a stalled GPG child using fictional Git data, with no original records or credentials.

The Python 3.9 test generates a **temporary throwaway fictional GPG encryption key**, creates a two-branch fictional bare Git repository containing a success capture and a separate failed-attempt-only binary, encrypts an actual streaming Git bundle, copies the ciphertext, decrypts and restores into an isolated bare Git repo, validates both branches, native objects and ciphertext SHA, and ensures missing keys, unexpected refs, changed source, tampering and overwrites **refuse safely**. The transient key is deleted after the test. No real source original, secret, private vault branch, external service, model or GitHub state is used. Focused CI has no public source download or upload path.

## Actual recovery and cutover holds

- Real independent encrypted media and independent machine restore: **NOT performed**.
- Recovery key identity, custody, expiry and backup: **NOT approved or configured**.
- Git LFS payload copy/rehash, failed-run original Actions ZIP inventory and source-specific authorization: **NOT cleared**.
- Private repo collaborator/personal-account forking rules, limited cross-repository GitHub App writer: **NOT cleared**.
- Public Daily `pla_watch.db` / record output still contains original data; website and collector workflows remain unchanged.
- **No real publisher sources have been moved** into the vault. Do not merge AFP #606's metadata-only attempt upload until failed-only originals are copied into a verified private destination and independent backup.

Neither owner provider choice nor a green fictional CI test is permission to transfer originals, switch production, rewrite public history, trim historic artifacts, publish/AI/email or claim copyright compliance.
