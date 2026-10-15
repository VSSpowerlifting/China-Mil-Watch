# Korea encrypted backup and restoration — owner-only operator gate

**15 October 2026. This PR implements backup/restore verification, not an actual backup of Korea originals, nor authorization to copy them.** The existing private vault VSSpowerlifting/ipr-source-evidence-private holds only governance, metadata receipts and synthetic pilots, not real HWPX source evidence. Custody decision [#520](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/520) remains open.

## Functional new capability

The previously merged source-equivalence checker (#616) compares source and destination Git commits, bytes, database records, captures, historic Day 0 clock and failed October 12 collector slot; #610 supplies a **fictional, unencrypted** Git-object recovery test. This new operator utility uses GPG public-key encryption to turn a complete, pristine source-state Git history into a new, owner-only encrypted Git bundle, then **actually decrypts and clones it** into temporary restricted scratch and invokes that same per-source byte-equivalence validator. It never touches a publisher, emails anyone, activates a private collector, changes production or sends originals to GitHub Actions. It bundles ONLY the pinned HEAD commit and its reachable ancestry, not all refs or unrelated branches in the local source clone; synthetic CI explicitly checks this exclusion.

The utility produces only a receipt containing the real commit, encrypted bundle digest and length, source counts and deliberately false policy flags. It refuses missing or altered original bytes, changed state history, an existing destination, a wrong recipient fingerprint, permissions broader than owner-only, missing tools or failed restore. All errors are fixed hold codes, never source text, reviewer identities, local secret paths or command stderr.

## Conditions for an ACTUAL source-original run

Before an authorized operator executes this utility on real Korean materials:

1. Obtain **explicit, source-specific retention and backup permission for the complete HWPX files, embedded media and HTTP responses**. Historic KOGL Type 1 page-level text-only notices are **not** permission to redistribute or retain every embedded item. This software cannot make the rights decision.
2. Pin the exact clean Korea shadow Git checkout, retaining original state commit 0595f0fd29b769cbab5dd57c2ef57af174237a67, the October 6 founding clock and the failed October 12 scheduled slot. Never rewrite old Git history merely to perform a backup.
3. Provision a real, owner-approved public-key encryption recipient, verified 40-character hexadecimal GPG fingerprint and a GNUPGHOME directory restricted to 0700, with a separately controlled key-recovery plan. Never commit private encryption keys or credentials.
4. Choose a **new absolute encrypted output path**, in a 0700 owner-only directory outside any public/private repo checkout, and run only on a trusted **encrypted local machine**. A separate existing, owner-only 0700 directory on deliberately encrypted scratch storage is **required**; the utility no longer falls back to system /tmp.

Example command after all external approvals:

    python -m scripts.backup_korea_encrypted_custody --source-checkout /absolute/secured/korea-shadow --encrypted-out /absolute/owner-only/korea-state.bundle.gpg --recipient-fingerprint YOUR_VERIFIED_40_HEX_FINGERPRINT --gpg-home /absolute/owner-only/gnupg --scratch-parent /absolute/encrypted-owner-only/restore-scratch --owner-approved-restricted-retention

The operator acknowledgment switch does not authenticate a human or prove legal permissions. A genuinely independent owner must verify the permitted scope.

**Important temporary plaintext detail:** The initial backup is streamed directly into GPG encryption. The verification step briefly creates a decrypted Git bundle in a 0700 temporary folder. Its later deletion does not prove secure erasure of disk blocks, swap or snapshots. If the host cannot safely handle original bytes in encrypted scratch, do not execute this procedure.

A positive local encrypt/decrypt/restore report **does not prove a durable encrypted backup on a separate provider/machine**. Transfer of the encrypted result into an approved independent recoverable store, escrow and independent restoration are separate checkpoints. Do not conflate a second GitHub repo with disaster recovery.

## Verification and explicit non-activation

The PR's dedicated CI uses only **synthetic five-record Git states** and a disposable synthetic GPG encryption key. It exercises actual GPG encryption and decryption, Git bundle cloning and deep per-capture byte-equivalence, plus wrong-key, permissions, immutable-history and refusal paths. Real Korean originals are never fetched, backed up, uploaded, decrypted in Actions or published by CI.

No real archive move, owner signature, rights decision, long-term backup, credential provisioning, private writer, DAPA source access, Sunday model input, editor email, new corpus record or site deployment is performed.

**Disposition: reviewable engineering operator utility; source-original retention, independent durable encrypted restore and live cutover remain held.**
