# Private GitHub source vault — provider choice and safe activation

> **Current-state correction, October 15, 2026.** The empty/policy-only
> repository snapshots and “no originals transferred” claims below document
> an **earlier onboarding state**, not the current vault. Nine native source
> Git histories now reside on distinct private `archive/*` refs, with matching
> original Git commits and independent private readback. The first nine-job
> [daily fast-forward sync run](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/38786044913)
> succeeded. The original public refs remain; failed-attempt/ZIP-only evidence
> is not comprehensively preserved, off-GitHub recovery is not claimed, and
> collector/publishing cutover and source-use rights are separate. The current
> private README and dated frozen-source inventory govern the archive baseline
> (visible only to authorized private-repository members). The onboarding
> preflight described below is **not a current validator of a populated vault**.


**Owner choice: October 15, 2026 — a separate PRIVATE GitHub repository.** The owner has now **created** `VSSpowerlifting/ipr-source-evidence-private` and the connected GitHub API has independently confirmed `visibility=private`, owner-admin permissions and a clean empty branch list at first observation. I subsequently initialized its `main` with a **policy README only** at exact commit `2d53f25a2a4c31b3d1b2a84b569a7f203fdad593` and blob `b1a7c174d224f0d9e9245ab400a31bb19c6eab86`. A follow-up authenticated API read reverified private visibility and exactly one `README.md` Git tree entry, no archive refs or government bodies. **No originals have been transferred**, no independent backup or source-use permission is established, and production is untouched.

## Current authenticated preflight baseline — metadata-only (October 15 update)

The private vault now contains the original policy README, two **metadata-only** Korea manifests, and the two strictly fictional pilot/restore branches. The genuine Korea 14-original source bytes, HWPX, source database and failed Actions ZIP **have not been migrated**. The saved manifests contain source-capture inventory hashes/IDs and a verified cross-check of the genuine October 12 failed ZIP (32 capture payload hashes matched the frozen 58-object source inventory, zero additional capture identities). The failed scheduled slot is still failed; the unique attempt log is not backed up here.

The authenticated preflight now explicitly accepts a **second exact pinned snapshot** of the private vault: current `main` at `43a9ad7efec2731133f0e2e2fb9fee4747091c51`, with README Git blob `0fc7181cb1941c8f1893c30b99caca18a3f87b14`, the exactly pinned `manifests/` tree and the two expected JSON blobs. Only the two original fictional pilot branches are accepted alongside that main commit. Any unexpected blob/ref, public visibility, Pages use or missing administrator access remains a HARD HOLD; the tool does not claim the vault has protected branches, restricted collaborators, independent encrypted backup, rights signoffs or real transfer.

This current snapshot is a **read-only onboarding checkpoint**. Adding another vetted metadata receipt requires explicitly updating the authenticated pin and tests. Do not broaden it to `manifests/**` or accept arbitrary files, and never treat merely being in a private Git repository as permission to store originals.

## Destination created and initialized — initial onboarding record

Actual destination: **`VSSpowerlifting/ipr-source-evidence-private`**. The owner already created it through GitHub. These original setup requirements have been met for the private visibility/name and initial empty state:
- Owner `VSSpowerlifting`, name `ipr-source-evidence-private`, **Private**.
- **Do not initialize** with a README, license, .gitignore or template. Do not import/fork the public IPR repo: public-history copies are not erased by a new fork.
- No Pages, no public access, no collaborators by default; review owner/admin and recovery contact; enable strong account MFA. Keep code, original media, full-text payloads and reviewer packets OUT of public repositories.
- Do not enable an automatic public-source GitHub Actions transfer. No secrets in PR contexts. Treat linked assets and HWPX/PDF embedded media as rights-held pending source-specific reviews.

[View the now-created private repository](https://github.com/VSSpowerlifting/ipr-source-evidence-private). The authenticated preflight accepts an empty new repo, the exact historical policy-README-only bootstrap, or tightly pinned metadata-only + fictional-pilot snapshots described above. It never accepts arbitrary populated archives. Any changed README blob, extra file or source-archive ref is a fail-closed preflight discrepancy; once genuine archival refs are added, use the separate full object-parity and retention tools, not this onboarding check. The `main` branch was reported **not protected** on first inspection, so repository rulesets and actor access remain a **separate owner review gate**.

**Authenticated preflight from an operator-controlled shell with `gh` installed and already authenticated:**

```sh
python3 -m scripts.verify_private_github_vault \
  --source VSSpowerlifting/China-Mil-Watch \
  --vault VSSpowerlifting/ipr-source-evidence-private
```

The CLI uses only **GET** requests via `gh api`, does not open source captures, and reports only destination identity/metadata and explicit negative transfer/rights flags. It refuses public/unknown visibility, wrong owner, forks, archived/disabled repos, unavailable authenticated API, nonempty destination and missing operator admin rights. It intentionally **never reports `ready_to_transfer=true`**, even for a successfully created vault: provider access and an empty repo are necessary, not sufficient, evidence.

## GitHub-specific security and continuity design

1. **Separate authenticated workload identity.** The public repository's ordinary `GITHUB_TOKEN` cannot access the separate vault. Use a dedicated GitHub App (preferred), installed on **only** the source and private vault with minimal per-repo permissions; issue short-lived installation tokens for **manually approved protected** runner jobs, not PRs. Permissions: public source metadata/captures **read**, vault contents **write**, vault state verification **read**, plus no admin/issues/workflows privilege. GitHub App installation-token scope and branch settings need independent operator review before any real operations. Where a GitHub App is unavailable, a fine-grained token with equivalent scope is an explicitly reviewed alternative, not something to paste into chat or code.
2. **Versioned state layout.** Preserve the original source's isolated Git history under deterministic vault refs, e.g. `refs/heads/archive/korea-policy-briefing`, `archive/indonesia-kemhan`, `archive/ph-afp`, and one source branch per Vietnam family. Never merge unrelated orphan source histories; never graft Git histories, drop Git blobs, rewrite existing origin branches, rename source identities, or mistake a private branch in a **public** repo for a private vault. The initial copy of each source Git ref must verify its immutable original tip, tree shape, parent ancestry, complete blob object reachability and on-vault readback of matching commit IDs, plus review permissions; no `--force` push.
3. **Failed-attempt state is mandatory.** For runs where the scheduled collector failed and never committed source state, the Actions ZIP may be the **only** archived raw publisher response. Save it under an independently tracked vault failure-intake ID based on `run_id` and `attempt`, with its original bytes and manifest SHA-256 in the private vault, and public metadata-only hashes if permitted. Include cancellations/reruns, actor/time, true execution date vs logical date, failed processing stage and earlier attempt provenance. Old Actions artifacts can expire: do not delete or shorten retention before verified transfer.
4. **Repository and binary limits.** GitHub's enforced **100 MiB per Git object** limit and recommended much smaller objects must be checked against every capture/snapshot; Git Large File Storage is necessary for oversized binaries but comes with bandwidth/storage/account and backup considerations. A `git bundle` **does not automatically include LFS bytes**. The repository's expanding version history (frequently rewritten SQLite files and many captures) requires size forecasting and periodic re-evaluation; exceeding viable Git/LFS capacity is a reason to halt, not a reason to discard originals or weaken checks. Nothing here claims GitHub is automatically an appropriate infinite-retention object store.
5. **Independent restoreable backup.** Private GitHub is the live *primary vault*, not the sole durable backup. Produce a separate access-restricted, encrypted backup on independently owned storage (e.g. offline encrypted local drive under owner control), with Git refs, Git objects, failed-run intake copies, and any LFS objects. Rehearse restoration into a **different empty private or offline bare repository**, rehash all blobs, validate SQLite `integrity_check` and `foreign_key_check`, and match original dated manifests. Keep one previous generation recoverable. All backups and local cache copies require their own access and retention policy.
6. **Private origin and public projection gates.** An unseen vault ref does not authorize copying an MND HWPX or MOIT article into public `main`, `gh-pages`, source URLs, searchable JSON, screenshots, AI prompts or Sunday emails. Publisher terms, human review, rights and separate textual vs visual scope determine public fields. `scripts/audit_source_projection.py`, `core/source_publication_contract.py` and the #609 static preflight are existing pre-cutover safeguards, not self-authenticating rights grants.
7. **Two-phase cutover, no unsafe fallback.** In test/staging, verify private-copy + readback + separate backup **before** narrowing public Actions artifact uploads or removing public Git original writes. Then separately owner-authorize the live Daily/AFP/Vietnam/Indonesia/Korea collector workflow changes, source reviewer handoff, public projection, rollback and staged deploy. Failure to authenticate, persist, compare, restore or link a failed attempt means **STOP** and retain historic evidence without inventing successful collection days. Neither this PR nor owner provider choice authorizes such a cutover.
8. **Historic public exposure is permanent historical fact.** Moving records privately does not make prior Git forks, old Actions artifacts or cached page text inaccessible retroactively. No branch deletion, history rewriting, bulk privacy promise or old artifact deletion without a separately approved, evidence-preserving risk/legal/incident plan.

## Phases and acceptance

| Phase | Can proceed now? | Exact stop condition |
|---|---|---|
| Private GitHub provider design, authenticated **read-only** destination checker, fictional unit tests | **Yes** | No source bytes, secrets, network in PR CI |
| Owner creates `ipr-source-evidence-private` from GitHub UI | **Complete** — verified private + owner; policy README only | Still review collaborators, branch restrictions, backup and credential scope |
| Cross-repository App/short-lived token, branch protections, budget, backup permissions | Separately reviewed setup | No credentials or source copies in public PR jobs |
| One historical source family, plus one genuinely failed-attempt ZIP, copy/rehash/restore pilot | Later, explicit live pilot approval | Source-original rights retention scope reviewed; independent backup complete |
| All desk archives + production DB/historic artifacts | Later migration approval | Every original/attempt/tree/corpus hash reconciles |
| Stop public full-state writes/artifacts, public projection + release | Later C6 approval | Verified fail-closed private persistence, human rights approvals, full tests, rollback |

**Non-goals of the current PR:** The new repository and policy-only initial README now exist (created by owner and initialized through the connected GitHub tool). No source-original transfer, privileged cross-repository credential, independent backup, publisher request, model/email/publication, Git history rewrite, website/collector change or source-rights grant occurred. Full offline CI remains required before merging supporting code. Provider selection does not change legal/retention status of any ministry original.


## After an approved restricted transfer: independent read-only Git object parity

A genuine archive migration is **not** in scope for this PR. After separately approved owner-controlled copy and backup, inspect source and vault clones locally with the new read-only tool. For example, the frozen October 14 Korea source branch currently has commit `0595f0fd29b769cbab5dd57c2ef57af174237a67`. Only after confirming it is still the intended freeze point:

```sh
python3 -m scripts.verify_private_github_ref_parity \
  --source-repo /secure/original-source-checkout \
  --vault-repo /secure/private-vault-checkout \
  --source-ref shadow/korea-policy-briefing \
  --vault-ref archive/korea-policy-briefing \
  --source-commit 0595f0fd29b769cbab5dd57c2ef57af174237a67
```

The tool invokes `git rev-parse`, `git fsck --connectivity-only` and full reachable Git object-ID set equality on the specified **local** repositories. It has **no** `git fetch`, `clone`, `push`, GitHub API or network path, cannot reconcile a moving source ref by itself, and outputs only fixed failure codes, commit IDs and object counts. A successful result proves matching reachable native Git objects for one frozen ref. It **does not** prove Git LFS original binary bytes (Git stores a pointer), independent backup restoration, a failed attempt preserved only in an Actions ZIP, GitHub API visibility of a remote, another source/ref, retention rights or permission to publish. These are separately required before any cutover. A synthetic/fixture Git parity check in PR CI is not evidence that the private remote has been created or populated.
