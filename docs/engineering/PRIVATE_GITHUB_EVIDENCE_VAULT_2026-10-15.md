# Private GitHub source vault — provider choice and safe activation

**Owner choice: October 15, 2026 — a separate PRIVATE GitHub repository.** This specifies the provider for the previously approved independent original-evidence archive (#332/#342). It does **not** create that repository, transfer originals, resolve publisher permissions, or enable production. Avoid repurposing unrelated existing private repositories.

## Create the empty destination

Proposed name: **`VSSpowerlifting/ipr-source-evidence-private`**. The owner can create it using the GitHub New repository UI, choosing:
- Owner `VSSpowerlifting`, name `ipr-source-evidence-private`, **Private**.
- **Do not initialize** with a README, license, .gitignore or template. Do not import/fork the public IPR repo: public-history copies are not erased by a new fork.
- No Pages, no public access, no collaborators by default; review owner/admin and recovery contact; enable strong account MFA. Keep code, original media, full-text payloads and reviewer packets OUT of public repositories.
- Do not enable an automatic public-source GitHub Actions transfer. No secrets in PR contexts. Treat linked assets and HWPX/PDF embedded media as rights-held pending source-specific reviews.

[Create a private repository on GitHub](https://github.com/new?owner=VSSpowerlifting&name=ipr-source-evidence-private&visibility=private). This is a UI setup link; it does not create anything automatically. After creation, verify the authenticated repository API reports `visibility=private`, `private=true`, nonfork, nonarchived, correct owner and empty branches. If a different private repository is chosen later, re-run all checks for that exact name.

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
| Owner creates `ipr-source-evidence-private` from GitHub UI | Owner action | Verify **private**, correct owner, empty, no unwanted collaborators |
| Cross-repository App/short-lived token, branch protections, budget, backup permissions | Separately reviewed setup | No credentials or source copies in public PR jobs |
| One historical source family, plus one genuinely failed-attempt ZIP, copy/rehash/restore pilot | Later, explicit live pilot approval | Source-original rights retention scope reviewed; independent backup complete |
| All desk archives + production DB/historic artifacts | Later migration approval | Every original/attempt/tree/corpus hash reconciles |
| Stop public full-state writes/artifacts, public projection + release | Later C6 approval | Verified fail-closed private persistence, human rights approvals, full tests, rollback |

**Non-goals of the current PR:** no new repository created, no source transfer or provider access attempted, no secret/provisioning mutation, no publisher requests, no model/email/publication, no Git history rewrite, no website/collector modification. Full offline CI required before merging any supporting code. Provider selection does not change the legal/retention status of a single ministry original.


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
