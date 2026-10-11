# Japan Coast Guard — guarded schedule, Actions jobs, and state evidence

**Prepared October 11, 2026.** Status: read-only observability tool; **NOT** a verified daily collection schedule, source license, human review, or Japan desk promotion.

## Existing source facts, and the operational uncertainty

The public Japan Desk is currently `shadow`. Its JCG original-source lane uses isolated branch `shadow/japan-jcg`. The pinned state at `81558026117067cbcf54bd7a7859a2d9db168a0c` has one October 8 manually authorized **Day 0** ledger (`37828199188-1`), with explicit target October 8 and `health=ok`. This is an original collection observation, **not seven collecting days**.

The existing `.github/workflows/jcg_guarded_daily_shadow.yml` declares `13 19 * * *` UTC and checks `vars.JCG_SHADOW_DAILY_ENABLED == 'true'` on its shadow job. A cron entry does **not** establish that this variable was enabled or that the job ran. The remote state branch having only the Day 0 ledger does **not** prove the publisher went silent, that jobs were missed, or that a collector failed.

## Implemented read-only separation

`scripts/audit_jcg_daily_gate.py` inspects **GitHub metadata only**, from a trusted local checkout after an operator explicitly approves API reads. It verifies:

1. Current exact repository variable `JCG_SHADOW_DAILY_ENABLED` as `true` or `false`, **without claiming to know its historical value**. An absent or unreadable variable is **blocked**, not assumed false.
2. Pre-existing `shadow/japan-jcg` branch head, source-specific `state/clock.json`, Day 0 linkage and each pinned `state/ledger/*.json`, with Git blob SHA validation. A branch that moves during the read is refused.
3. A bounded official GitHub Actions run index for **this exact** JCG guarded daily workflow, and job results for each numbered attempt. The tool does not interpret a GitHub workflow conclusion as proof that its gated `shadow` job executed.
4. Only when a specific scheduled job reports **success** and a corresponding pinned, source-family-specific schedule-slot ledger exists for the same run attempt and logical day is it counted as a correlated **observed collecting day**. A skipped, cancelled, incomplete or failed job is not such a day. A success without a matching ledger is **held for review**.
5. A declared source anomaly, unknown job state, wrong source clock, malformed query, lost ledger, wrong run-to-date match or historically unobservable variable remains an explicit review limitation.

Every report keeps `complete_scheduled_attempt_history_proven=false`, `historic_gate_values_known=false`, `human_day_7_review_approved=false`, `source_licence_or_publication_authorized=false`, `production_desk_promotion_authorized=false`. Even one genuinely matching success is **not** continuity qualification. A current `false` variable does not mean it was false when older jobs ran; a current `true` variable does not prove it was enabled when a job was skipped.

## Operator-only audit, not a workflow

Use a local read-authorized GitHub token with repository Variables, Actions, and Contents **read** permission. Do **not** turn on or change the variable. From a trusted checkout:

```sh
python -m scripts.audit_jcg_daily_gate --as-of 2026-10-11 --approve-github-read
```

The script makes only bounded GETs under `api.github.com/repos/VSSpowerlifting/China-Mil-Watch`; it does **not** visit Japan Coast Guard sites, download captures/SQLite data, retrieve publisher text, run a model, send email, deploy, or write to state. Reports expose GitHub run identifiers, dates, source anomalies and state commit only.

The first version supports at most **30 indexed scheduled workflow runs**, **five attempts per run**, **30 jobs per attempt** and **60 pinned state ledgers**. When those bounds are exceeded, it **refuses** to imply exhaustive coverage; a separately bounded/paginated archival reviewer can be designed. It may require a GitHub token authorization scope not currently available to the ChatGPT GitHub connector. This is a distinct operational dependency, not a reason to make up a gate setting.

## GitHub-native self-service observation (without a separate Variables API token)

A new **manual-only** workflow, `.github/workflows/jcg_gate_readonly_observation.yml`, provides a simpler route for the owner. After review/merge to main, navigate to GitHub Actions → **JCG Source Gate Observation — Read Only** → Run workflow and explicitly check `acknowledge_read_only_review`. **This is not the JCG guarded collector workflow.** It has no schedule, no publisher access, no upload artifacts, and `contents: read` / `actions: read` permissions only.

The manual workflow passes the **current** `${{ vars.JCG_SHADOW_DAILY_ENABLED }}` into an in-process observer from its own GitHub Actions context. The same exact variable reference controls the scheduled JCG collection job. To avoid trusting an arbitrary user-supplied environment variable, the auditor's `--gate-from-actions-context` option fails closed unless the runtime reports this repository, this exact workflow file, main branch, GitHub workflow_dispatch event, full commit SHA, and a literal `true` or `false` current gate. It does **not** call the repository Variables REST endpoint in this mode. Other GitHub REST requests still check the actual existing workflow jobs and immutable state branches using the ephemeral read-only `github.token` token.

An unset variable, denied Actions metadata, incomplete historical run listing, invalid state or moving branch is **BLOCKED**; the observer must not reinterpret it as `false` or claim a missing publication. A readable current gate does **not** establish what the variable was last Friday. A completed manual run can report **review HOLD** while its workflow status is green; a green observation workflow certifies only that the metadata check completed, not that Japan JCG is source-qualified. Read the JSON printed in the run log, not the workflow color alone.

This mode is deliberately not invoked by pull requests, and merge/presence of the workflow does not trigger it. It changes neither the JCG variable nor the guarded source collector. `--approve-github-read` remains necessary inside the explicitly authorized manual Actions job. A separate owner's permission is still needed to activate actual Japan Coast Guard collection.

## Official JCG publication terms: specific rights review still required

The Japan Coast Guard's **current central-website copyright page** is published at https://www.kaiho.mlit.go.jp/questions/post-1.html and states that content generally falls under **Public Data License 1.0 (PDL1.0)** unless another applicable license or exemption is specified. Its instructions call for source attribution (publisher and URL), explicit identification of edits/adaptations, and caution against representing altered material as an unmodified Japanese government publication. It excludes JCG logos/mascot artwork and materials with separately stated use conditions.

This is **material source-policy evidence**, but not yet a verified licence determination for each Oct 8 English `/e/topics_archive/` release or its linked PDFs. Other JCG departmental/subdomain notices may differ; individual images, third-party works, hydrographic materials and explicitly excepted documents can have other rules. Before any public reuse, a human must map the central policy and any local exceptions to the **specific originating document version and use type**, distinguishing a source-linked factual synopsis from retaining publisher text and reusing media/PDF. The owner cannot authorize unreviewed source retention based solely on one general policy page.

## Decision tree and next engineering milestone

- Variable definitely **false now**: label **held by current gate**; inspect the actual owner's original-source Day 0 and permission decisions. Do not change the variable by automation or count missing scheduled days against the source.
- Variable definitely **true now**, but only skipped jobs: label **needs review**; GitHub variable *history* is not proven. Check source policy and dated owner approval separately before running collection.
- Shadow job **success**, matching exact state ledger, logical date and clock: record a **bounded observation**, not successful source qualification.
- Job **failure**, no state ledger, mismatched state/clock, challenge or denied original document: hold as failure/missing evidence, with the correct source family; do not turn into `ok_no_publications`.
- No authorized daily collection yet: continue the existing original-language, permissions and PDF-completeness review, then seek owner signoff *for that JCG family only*. Japan MOD RSS/PDF/HTML is a separate lane and remains independently constrained.

**Next step:** the owner or permitted operator runs the metadata observation, records its current gate value and exact Actions attempts in issue #205, and checks the **actual Oct 8 first-party publisher/source-rights review**. Any later authorization to activate JCG daily shadow is a distinct action, after owner review; any 7/14/30-day qualification is based on actual collecting days and named human source checks, never calendar elapsed time.

## Offline proof and files

```sh
python -m unittest tests.test_jcg_daily_gate_audit -v
```

The PR changes only this document, the read-only auditor, its synthetic no-network tests and a PR-only CI workflow. No collector, source manifest, `desks/registry.json`, existing JCG scheduling workflow, source branch, database, publisher data, runtime configuration, SMTP, publication or deployment is changed.
