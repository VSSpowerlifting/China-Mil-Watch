# Joint offline recovery of Git-history and Actions ZIP evidence

**Operator-only supporting procedure. No publisher originals, credentials, private
repository, or Actions artifact is downloaded by this tool.**

The merged [Git bundle backup #617](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/617)
and [per-run Actions sidecar #624](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/624)
serve **distinct** obligations. A successfully restored native Git ref does not
preserve original bytes that existed only in failed-run Actions artifacts.
A verified encrypted Actions ZIP is not proof that Git history was preserved.

Use `python -m scripts.private_vault_recovery_pair` on an **owner-controlled,
offline terminal** to actually decrypt/restore *both* an encrypted Git bundle and
one pinned Actions ZIP sidecar with an independently retained original census.
The supplied JSON creation receipts must have owner-recorded SHA-256 values from
**outside the copy being tested**. Store immutable receipts and original census
separately; receipt digests are integrity comparisons, not signatures or
authorization by themselves.

```bash
python -m scripts.private_vault_recovery_pair \
  --git-encrypted /independent-medium/git-history.bundle.gpg \
  --git-receipt /trusted-owner-receipts/git-backup.json \
  --git-receipt-sha256 '<owner-recorded-sha256-of-git-json>' \
  --zip-encrypted /independent-medium/attempt-37656171920.gpg \
  --zip-receipt /trusted-owner-receipts/attempt-37656171920.json \
  --zip-receipt-sha256 '<owner-recorded-sha256-of-sidecar-json>' \
  --inventory /trusted-owner-receipts/actions-census.json \
  --run-id 37656171920 \
  --scratch-dir /restricted/tmp-0700 \
  --gpg-home /restricted/keys
```

**Never paste a private key/passphrase, captured body, raw ZIP or token into
GitHub, ChatGPT, a public PR, or runner logs.** Pass ciphertext paths from the
operator's verified separate storage device; the tool cannot identify whether
the device is physically independent or controlled by a separate principal.
Use a fresh directory with mode `0700`, outside any Git checkout. Successful
Git recovery uses an automatically deleted plaintext temporary bundle.
Actions sidecar recovery *streams* decrypted ZIPs through checksums without
extracting them.

On success it emits `OFFLINE_BYTE_PARITY_PASS`, counts and policy flags:
**independent storage, authenticated HTTP download, publisher rights and
production cutover all remain false**. This is a joint cryptographic-integrity
rehearsal, NOT a certification of offsite media, live corpus completeness or
permission to delete/shorten Actions retention. A backup may require multiple
sidecars: **run this for every scoped run, including every earlier failed
attempt** and reconcile a separate exhaustive census; a successful pair for
one run does not imply full desk coverage. Preserve any ZIP-only failed original,
provider identity/redirect evidence and all preexisting public historical refs.

For review, `python -m unittest tests.test_private_vault_recovery_pair -v`
uses deliberately fictional Git and ZIP data and a throwaway GPG key. It
performs both real local decrypt/restore paths, verifies wrong key, receipt
tampering, original census drift, shared ciphertext path and unsafe scratch
directory behavior. No external GitHub or publisher calls occur.
