# Philippines AFP: preserve collector attempt evidence without re-uploading original source bodies

**October 15, 2026. PR review only.** The currently deployed `.github/workflows/ph_afp_shadow.yml` uploads **the entire `state/` folder** to a publicly accessible GitHub Actions artifact on *every* attempt, successful or failed. This includes the isolated `state/shadow.db` with archived AFP text and `state/evidence/payloads/*.bin` HTTP response originals. Actual successful [October 14 run 38562843186](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38562843186) uploaded unexpired artifact `11893497374`, **2,415,959 compressed bytes**. The AFP API's archived response `X-Robots-Tag: noindex, nofollow` is an unresolved indexing/source-use consideration; it should not be characterized as either permission or a blanket copyright ruling.

## Narrow prospective change

The existing `if: always()` Actions upload remains 90-day retention, but the allowed path list now contains **only**:

- `state/ledger/*.json` — immutable run counters, failures, state digests;
- `state/evidence/*.json` — original-request metadata, response status, original HTTP capture SHA-256 and original URL, but not `payloads/*.bin`;
- `state/clock.json` — Day-0/continuity clock metadata;
- `ph-afp-run.log` — existing collector terminal progress/failure log.

No `state/shadow.db`, original `state/evidence/payloads/*.bin`, any capture/media, `output/`, database from main, or full `state/` folder is uploaded. The *actual existing* archived evidence can still be accessed via the pre-existing public isolated branch; this is not private archival custody. We do **not** change the source collector, its clock, target dates, robots/HTTP policies, sample limits, publisher credentials, success/failure handling, remote state commits or the manual/recovery rules.

**Historical reality:** prior full-state artifacts, existing Git commit objects and any external clones/caches continue to exist. Do not delete, rewrite or claim confidentiality retroactively. Preserve failed attempts and original hashes under the pending owner restricted-archive design [#332](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/332), and consider AFP [#226](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/226) source-specific rights terms. This new metadata-only path is a forward-looking minimization step, not a substitute for the required private-state migration and retention authorization.

## Verification and stop conditions

- No-network tests in `tests/test_ph_afp_actions_artifact_boundary.py` enforce **exact four-path allowlist**, `if: always()`, upload/retention semantics and no source-original state/payload paths.
- Require green exact-head full CI and independent diff review before any merge. On a later genuinely scheduled AFP run, compare the *actual* artifact file listing against the exact metadata allowlist and confirm the original's SHA and failed-attempt counters remain present while `shadow.db` and `payloads` are absent.
- This PR does **not** declare the 22 pending AFP source reviews signed, resolve `X-Robots-Tag`/source-body/photo rights, open public copies, grant external AI processing, start Sunday selection, promote Philippines, perform any manual dispatch or publish/deploy anything.
