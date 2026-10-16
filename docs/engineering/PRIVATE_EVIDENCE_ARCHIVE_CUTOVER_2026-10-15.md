# IPR private-evidence archive — approved direction, precutover inventory and transfer safeguards

**15 October 2026. Status: owner approved the storage direction in [#332](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/332); provider, publication rights, historical cleanup, real-source transfer, and cutover remain unapproved.** This is the C4/C5 interface to the pre-existing [#342](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/342) implementation program, **not another synthetic custody engine**. Use its existing `core/evidence_snapshot.py`, `storage/evidence_custody.py`, snapshot restore/conditional write interfaces and rights-projection contract rather than replacing them.

## Owner decision and boundaries

The selected direction is **separate access-controlled, versioned original-source custody** with independently verified backups, immutable original digests and traceable access. Public Git and Pages should eventually hold **only fields independently approved for each action** (record metadata/link, short quotation, full body, photograph, external model use are *different* decisions). Nothing in this decision authenticates a reviewer, licenses a publisher page or permits rights-held MPS/MOIT/AFP/MINDEF media, model distribution or mass public archival mirrors.

**Provider undecided.** Recommend one versioned object-storage service with a repository-independent, encrypted backup and short-lived, least-privilege workload identity. AWS S3 with OIDC, encrypted versioned objects and independently managed backup is one candidate, not an already selected or deployed service. A private Git repository is another option but public Actions `GITHUB_TOKEN` cannot simply write cross-repository without separately provisioned, reviewed credentials; Git history growth, per-file limits, backups and provider risk must be addressed. **Do not generate or post credentials to GitHub PRs/issues, grant workflow secrets to pull-request contexts, create paid resources, move real originals or open public objects until the owner selects and configures one provider and access policy.**

## Verified current public-state reference inventory (UTC Oct 15, read-only)

These are immutable points *for a future reconciliation*, not proof that a later state head is identical. The archive planner must **re-fetch each moving source ref and list all history at the actual freeze**, plus failed-attempt Actions artifacts. Branches in the current **public** repository are public regardless of their `shadow/` prefix.

| Lane / Git ref | Observed exact commit | Main risk and migration requirement |
|---|---|---|
| `main` | `8e109f24c5714dc38c8faa3650f3c15e125872bd` | tracked `pla_watch.db` full source data; Daily success and failure-salvage `git add pla_watch.db` |
| `gh-pages` | `b9d14e7c37e319c1140b8a8ddde5e7b5ce5d1c86` | deployed record HTML and associated cached/exported data; separately review every release surface |
| `shadow/korea-policy-briefing` | `0595f0fd29b769cbab5dd57c2ef57af174237a67` | 14 preserved MND HWPX originals, linked capture bodies, failed Oct 12 attempt |
| `shadow/indonesia-kemhan` | `0595c6677be24f8f0f33aecb28eec0050e36e8f9` | retained government originals and raw captures; existing full-state artifact uploads |
| `shadow/ph-afp` | `4dd40b9655ec53fe4fae829eb12ba21032946b25` | AFP archived API bodies, noindex/no-follow observations, full-state artifact copies |
| `shadow/vietnam-mps-foreign-affairs` | `cb607582eda7bd8760663540c33de2f73da411ff` | 11 MPS archived originals, whole-state artifact duplicates |
| `shadow/vietnam-moit-energy` | `5d25d68ee5bd3d1e8e5c7759db880a30d172491a` | 2 originals; written-consent rights hold + robots MIME anomaly |
| `shadow/vietnam-moit-foundational-industry` | `75035550a2f9db4f7a1cac57925141961b390d60` | 1 original; distinct rights and robots gate |
| `shadow/jp-mod` | `0a19aa448b57ddec91dced8b08bee625a89172d5` | partial collection, unresolved publisher access challenges; preserving unsuccessful and partial ledgers |
| `shadow/japan-jcg` | `81558026117067cbcf54bd7a7859a2d9db168a0c` | one isolated manual Day-0, scheduled collector still gated |
| `shadow/singapore-mindef` | `7068d8f088b3a00206e4ab866611af41c693462c` | source-original evidence and historically incomplete days |

**Not exhaustive.** Before any transfer, enumerate other public shadow refs (including NSC, PCG and US if they contain preserved bodies), current production DB and site contents, unexpired Actions ZIP artifacts on every attempt, legacy output exports, historical public Git objects and known backups. Save the immutable source-list receipt **privately** and publish only permitted digests/counts.

## Operational dependency: failed collection and public artifact minimization

The currently active AFP, Vietnam and Indonesia collectors use `if: always()` on Actions artifact uploads. Successful state pushes are conditional, but failed jobs can retain original captures **only in their Actions ZIP**. Changing those globs to metadata-only (e.g. [AFP PR #606](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/606)) **before a verified private failed-attempt copy exists** risks irreversible evidence loss. First perform a per-run **two-source** inventory: successful shadow Git commit + full Actions artifact, and failed/cancelled attempt ZIP even when no Git commit exists. Hash all original objects and retain their run ID, attempt number, collector code SHA, logical date, actual UTC execution, issuer/source, rights disposition and source capture status.

Do not delete older artifacts (some have retention expiry), prune branches, edit Git history, force-push, move `shadow/db` to `main`, or mark missing dates successful to tidy the record. Publicly distributed historic copies may persist in forks and caches even after a private migration.

## C4 pre-cutover executable static inventory

```sh
python3 -m unittest tests.test_private_archive_cutover_preflight -v
python3 scripts/preflight_private_archive_cutover.py --repository .
```

The scanner checks *actual source-code files only*: Daily canonical DB push, Daily Pages publishing, source original display in the record template, presence of local `pla_watch.db`, and broad original-state Actions upload globs for Korea/Indonesia/AFP/Vietnam. It reports fixed **code+file labels** rather than publisher text, credentials or source-body samples. It never opens `pla_watch.db` or archived government documents. On current main it is **expected to return exit code 2** with unresolved exposure findings. Even on a hypothetical cleaned fictional tree, it returns nonzero and `cutover_ready=false`; structural code scanning does not authenticate remote custody or grant legal permission. Missing inspected files/symlinks fail closed. The normal CI exercises only synthetic path fixtures, not a pipeline migration.

This deliberately complements (not replaces) `scripts/audit_source_projection.py` and the existing independent public HTML/JSON leak checks. It is **not** a complete static analyzer of arbitrary YAML, Git history, `gh-pages` rendered bytes or binary assets.

## Concrete gated implementation and verification sequence

1. **Choose and bind one private destination** under named owner control. Require private-at-rest and in-transit access, versioning/immutable retention, least-privilege credentials, no public-read access, access/audit logs, bounded cost, two-person recovery test where feasible, independent backup with separate permissions and incident response. Never place provider credentials into an issue, PR, Actions artifact or public source.
2. **Freeze source inventory without stopping normal evidence preservation.** Capture exact Git SHAs/branch ancestry and all Actions attempts + artifacts before expiry, including failed attempts and execution-vs-logical dates. No historical continuity repair. Reconcile record/source/version IDs, article/binary SHA-256, database integrity/foreign keys, source metadata, reviewer annotations and artifact count. Explicitly preserve HWPX/PDF/images, external linked assets and publisher terms, not just extracted prose.
3. **Copy first, verify and independently restore.** Copy all original data into the selected private store, store an immutable manifest and at least one independent backup, perform byte-for-byte SHA-256 checks and restore exercises from both current and earlier generations. Verify outage/race/interrupted upload behavior with existing S2/fictional custody contracts and **authorized non-sensitive provider smoke tests**. No real-source transfer via public PR CI.
4. **Make failed attempts durable before stopping public full-state Actions artifacts.** A red collection must still retain its unique attempted captures, permission/robots observations and exact run logs privately. Only after the backup/readback gate passes should the metadata-only upload PRs be merged and live flows changed.
5. **Integrate Daily's two public write paths and public render projection** in separate bounded PRs, protecting last-success markers, `scripts/reconcile_db.py` merge behavior, derived corpus fingerprints, source links and all canonical `record/<id>.html` and old redirects. A private-store outage is a **hard hold**, not fallback to `git add pla_watch.db`, new unaudited public output or model dispatch.
6. **Rights and editorial gate by issuer/action** (#326): MOIT permission, MINDEF hyperlink/full-body/photo rules, KOGL text-vs-media, AFP API indexing/copy terms, independent photographer licenses, source retention and outside-model input. Unknown/revoked/missing approval must not self-authorize public pages or AI email; source-acquisition access and public display are distinct.
7. **Owner-controlled cutover and rollback** only after exact-head CI, full site's independent output scanner, retained citations/search/mobile/no-JS and Briefs/Timelines, private backup restore, source family audits and provider outage simulation pass. Freeze public branch refs with audit receipts; don't rewrite public history or claim historic erasure. Publish a specific rollback procedure and aftercare report before enabling scheduled writes into private storage.

## Current stop condition

The owner approved the **direction**, not a live provider transfer or deletion. No private destination was provisioned, no source originals were transferred, no rights granted, and no production page or workflow was changed here. The next owner action is selecting and connecting the **one** destination, with cost/access/backup policy; only then can the C5 adapter and real restricted-store restore test safely proceed. Current public corpus exposure remains an active design/custody issue, not a resolved incident.
