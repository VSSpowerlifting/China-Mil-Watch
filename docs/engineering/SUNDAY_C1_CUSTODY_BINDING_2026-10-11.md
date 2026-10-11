# C1 execution: disabled private snapshot-to-journal custody binding

**Issue:** #366. **Status:** fictional, import-only, no sender. This is the first bounded implementation from planning PR #375's C0–C6 framework. It does not authenticate a real owner, prove source rights, operate a real send, or activate Sunday's scheduled workflow.

## Dependencies and branch arrangement

- #377 journal at `6ebdfabee05ebc564df7420c89a7a9e42d68f1f0`, successful CI #38114030442.
- #382 source-use and fictional replay at `a49a584a971cef5afdf271c5594272498026a598`, successful CI #38146369254; **this branch is based on #382**.
- #385 exact private TXT snapshot at `70e34c0c4655eda0e48e5aa77b4ba11b2ae86e4f`, an **independent main-based PR**. Its exact source/test/document blobs were copied unchanged into the C1 integration branch solely to test the combined code. The snapshot parent now includes its separate lexical+resolved public-Git symlink-ancestry guard and 15 focused tests; C1 includes 22 additional tests. #385's independent exact-head CI and owner acceptance remain separate requirements.
- C1 itself adds only `core/sunday_c1_custody_binding.py`, `tests/test_sunday_c1_custody_binding.py` and this document.

**Important diff accounting:** a C1 PR targeting #382 must show the 3 #385 dependency files *plus* these 3 new C1 files until the approved #385 changes are merged and this branch is safely rebuilt against them. A PR targeting main temporarily for offline CI shows #377+#382+#385+C1 together, which is for testing only and never a merge authorization.

## Functional contract

`bind_fictional_reviewed_snapshot(source, private_dir, journal, *, week, approved_week, reviewed_sha256, source_use_sha256, recipient, fictional_owner_approval_sha256)` performs:

1. Refuse anything but the October 10, 2026 pilot Saturday. Require a separately created `DeliveryJournal`; this function never initializes a missing database. Require absolute original source, journal and frozen destination paths outside public Git (both lexical and resolved locations) before any manuscript content read. Reject a reviewed original unless it is a caller-owned single-link regular file with no group/world permission bits; reject a symlinked original before opening it.
2. Validate canonical 64-character lowercase expected attachment/receipt/fictional owner reference digests. Permit only synthetic `@example.invalid` recipients, so real editor identities are never persisted even as guessable hashes.
3. Run the *existing* owner-week and exact-byte attachment guards against a preliminary original worksheet read, with a model-produced triage source-use subsection independently matched to the pinned receipt digest. These early checks reduce private-file side effects; **the preliminary mutable-file read is not treated as custody**.
4. Refuse any existing journal intent for the same reviewed digest, regardless of whether it was only registered or had already reserved an SMTP attempt. The parent SQLite unique index prevents a changed-digest second intent for the same week/recipient.
5. Call #385's single-descriptor, copy-once, fsynced, read-only snapshot helper in an existing private `0700` directory outside public Git. The canonical private copy is named after the exact digest, and no previous file can be overwritten.
6. Reinspect the **frozen** file, verify exact SHA, byte length, source-use receipt subsection and `0400` single-link regular-file metadata. **Then and only then**, register a fictional journal intent bound to week, recipient, actual frozen bytes, source receipt and fake owner evidence.
7. Return `FICTIONAL_REGISTERED_NO_SEND` with only a private path for a later *explicitly reviewed* phase; the operator must never print/log that path. C1 never invokes `reserve_attempt`, `send_packet`, an SMTP client, model composition, source fetch or any scheduler.

### Known limitations — stop gates

- The owner fields and independent source-use SHA are asserted test inputs, **not authenticated human approval** or independent publisher/rights verification. No real recipient can pass C1's fixture-only recipient gate.
- The frozen filename/mode is not cryptographic immutability. File replacement after final check, compromised parent directory, stale backup rollback, and hard process failure remain operational concerns for C2/C5. A later transport must use a pinned read-only descriptor or verified bytes at MIME-build time rather than trusting a returned path.
- If failure occurs **after a valid snapshot is created but before journal registration**, that private copy may remain. There is no send allowance and no automatic deletion/retry. Operators must reconcile before reusing or purging any private evidence.
- Journal registration does **not** reserve or authorize an SMTP attempt. A successful fake binding is not safe to hand to a sender. This helper has no CLI or live workflow import.
- Source-use matching proves only preservation of the model-supplied receipt text; all factual/source translation/use-rights decisions are external and remain open.
- Do not silently expand this first-week pilot to October 17 onward; future weekly protocol must be separately reviewed, including legitimate correction and resend policy.

## Offline negative matrix

The 24 synthetic `tests.test_sunday_c1_custody_binding` cases cover: successful byte-exact private snapshot with no SMTP/model; wrong week; missing owner week; altered/invalid SHA; changed input since review; missing/changed source receipt; real recipient/header injection; untrusted owner reference; malformed worksheet; repeated preflight; already reserved intent; revised manuscript in the same week; public Git-tree destination; corrupted snapshot between freeze and journal bind; concurrent competing workers; missing journal instance; public-repository source input; public-repository journal; relative source or destination paths; a checkout-local symlink to an external reviewed input; and a checkout-local symlinked parent that routes the private destination elsewhere.

Run focused suite with existing Python 3.9 dependencies:

`python -m unittest tests.test_sunday_c1_custody_binding -v`

Full PR CI must additionally report exact-head Python 3.9 tests including the new cases, preserved tracked database/output, no SQLite sidecar residue and governed validator warning status. A PR check that skipped due to targeting a feature branch is **not evidence**. All three parents require separate code and owner review before serial integration.

## Review sequence and scope

1. Hold this C1 PR unmerged as long as #377/#382/#385 are unapproved. Perform CI against the combined branch as *test-only* when safe; review diffs against exact parent refs.
2. Individually review and explicitly authorize #377, then #382, then #385 in a controlled main ancestry, refreshing final CI on the merged tree. Their existence and green CI do not imply automatic authorization.
3. Reconstruct a clean C1 delta against newly integrated approved parents; verify no duplicate parent files or lost guards.
4. Independently review/test C1. Stop with a **fictional, no-send** library; C2 authenticated owner/source-rights receipt and C3 pure MIME builder are separate PRs, not hidden extensions.
5. No public Pages, scheduled draft/sending toggle, Anthropic call, real SMTP, credentials, publisher materials, domain or archival corpus changed by this work.
