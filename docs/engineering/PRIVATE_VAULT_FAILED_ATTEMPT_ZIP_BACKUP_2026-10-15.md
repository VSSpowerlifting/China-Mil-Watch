# IPR private vault — encrypted Actions ZIP evidence sidecars

**15 October 2026. Owner-controlled offline recovery tool, NOT a live collector change.**

The private GitHub vault exists but **real government originals are not yet transferred and an independently encrypted, restored copy has not been established**. [PR #617](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/617) covers referenced native Git history. That alone cannot preserve the **only remaining original bytes from a failed collection attempt**, which can exist in a GitHub Actions ZIP even if the source branch never pushed.

This complementary preparation builds one GPG-encrypted ZIP *sidecar* from the operator's existing, authenticated local Actions artifact downloads. The ZIPs are kept **opaque**: no government source text, images, HTML, filenames inside ZIPs, or permissions are extracted, interpreted, printed or uploaded. It preserves ZIP SHA-256 and compressed byte lengths, actual GitHub artifact IDs, the original run/attempt IDs, and the [#620](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/620) operator census file SHA-256. The *entire* sidecar manifest is encrypted alongside the bytes. No publisher or GitHub network calls, repo push, source-state mutation, model or email occurs.

## Two separate tools and custody requirements

1. **Discover retained runs and artifacts** with `scripts/inventory_ipr_actions_artifact_expiry.py` from #620, once approved/merged, using a restricted authenticated owner shell. Keep the original JSON receipt immutable and separately backed up. Query all relevant days and inspect **every historical attempt's job**; a successful top-level rerun must not conceal a prior failed attempt.
2. **Download actual artifact ZIPs** through an owner-authenticated GitHub workflow outside public PR CI, after source-original retention permission and destination controls are decided. This PR **does not provide a downloading tool**, and no actual ZIPs were fetched or uploaded in its CI. Keep one file per original GitHub artifact, named exactly `artifact-<numeric_artifact_id>.zip`, in a private local directory. Verify IDs via the GitHub Actions API in the same authorized session; the backup script cannot authenticate a local ZIP was actually supplied by GitHub. Keep receipts for ZIP fetch date/source, identity, HTTP status, and source rights. Do not trust downloaded files with names that claim official provenance without validating that chain.
3. **Encrypt all artifacts for exactly one run** with `scripts/private_vault_encrypt_actions_attempts.py`; no partial selection. The program refuses absent or extra staged files, wrong/unknown artifact IDs, unavailable/expired metadata, absent or malformed past-rerun jobs, missing artifacts for any reported attempt, modified files during export, wrong decryption key, and existing output targets. The supplied GPG public encryption-key fingerprint must already be trusted locally. The *private* decryption key stays offline, outside GitHub Actions, GitHub Issues and ChatGPT.
4. **Verify the ciphertext from an independent backup medium**, separately retain the exact input JSON receipt and its SHA-256, and run the sidecar restore/check in a private owner-controlled scratch directory. It decrypts only to automatically removed restricted temporary storage and rehashes every original **opaque ZIP** inside the encrypted TAR. A green restore verifies ZIP-byte preservation; it does **not** verify any original inside those ZIPs, source-retention permission, or producer provenance.
5. **Explicit separate custody gates** remain for all Git branch histories and source extraction, all source-specific media/copying permissions, Git LFS bytes, every missed/failed manual/scheduled attempt, independent encrypted backup location, and the owner-approved live collector cutover. Do not merge [draft AFP #606](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/606) simply because an encrypted sidecar tool passes synthetic tests.

## Operator commands — illustrative only, no real originals copied

```sh
# The authenticated owner first obtains the real inventory and exact downloaded
# ZIP files locally. Never run an original-transfer step in public PR CI.
python3 scripts/private_vault_encrypt_actions_attempts.py create \
  --inventory /restricted/inventory/actions-20261007.json \
  --run-id 37656171920 \
  --zip-dir /restricted/github-artifact-zips/37656171920 \
  --recipient-fingerprint REPLACE_WITH_TRUSTED_40_HEX_GPG_FINGERPRINT \
  --encrypted-output /offline-backup/run-37656171920.tar.gpg

# Record sha256 from the preceding ciphertext receipt, copy the encrypted
# file to independent durable media, then restore/test there. Compare the
# inventory SHA to the independently backed-up original census JSON.
python3 scripts/private_vault_encrypt_actions_attempts.py restore \
  --encrypted-input /offline-backup/run-37656171920.tar.gpg \
  --expected-cipher-sha256 REPLACE_WITH_64_HEX_CIPHERTEXT_SHA \
  --expected-inventory-sha256 REPLACE_WITH_64_HEX_JSON_INVENTORY_SHA \
  --run-id 37656171920 \
  --scratch-dir /secure/local-recovery-scratch
```

The **real example run 37656171920** represents the October 7 Vietnam bootstrap: attempt 1 failed, attempt 2 succeeded, both distinct artifacts remain currently retained. Those original government bytes have **not** been downloaded, copied or backed up by this work. The examples explain what a separately authorized operator would do after source-retention and secure backup decisions.

## What the synthetic QA proves

The narrow PR-only workflow creates a throwaway encryption key and **two fictional ZIP archives** representing failed attempt 1 and successful attempt 2, validates a mock #620 inventory and actual per-attempt job-result identities, encrypts the ZIP bytes without an intermediate plaintext TAR, and checks decryption + SHA-256/byte lengths. Missing a failed-attempt artifact, absent old-job proof, modified inventories, symlink staging, tampered ciphertext, unsafe output and missing files must refuse. GitHub network, sources and vault credentials are not present.

The resulting report **always** says `source_rights_approved=false`, `independent_backup_medium_verified=false` and `production_cutover_authorized=false`; those cannot be inferred from cryptographic roundtrips. Review the focused exact-head CI **and** full repository suite before merging preparatory code. Changes do not automatically schedule a backup, duplicate original publisher texts, delete any Actions artifact, rewrite branch history or qualify Vietnam/Korea/Philippines for publication.

The earliest currently observed retained shadow collector ledger in the bounded August sample expires **November 17, 2026**; the January 5 first wave of actual Vietnam/AFP/Korea/Indonesia original-source artifacts is a later, distinct urgency. The full retained history and rights/custody inventory must be completed separately; existing GitHub artifacts can expire before a pilot is ready.
