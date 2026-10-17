# Archive release preparation — PR #776

This completes the existing release preparation; no publication is authorized.
The original 966-item receipts remain historical evidence. Full local candidate
manifests, captures and the detailed owner report are preserved untracked under
`docs/evidence/archive-release-2026-10-17/` and
`docs/ARCHIVE_RELEASE_CANDIDATE_2026-10-17.md`. This concise receipt is the PR record:
[scoped release evidence](evidence/archive-release-pr776.json).

## Reconciliation and reused verification

Initial reconciliation with base `ca4424cb15204ef366323f997c28119c2bf6d3ad`
resolved `PROJECT_STATE.md` and the Archive/staff and Archive/Korea renderer
sections. That pushed revision `faef90f15a2939de68cc9916eca4264c0bce3353`
passed Linux CI run 39057066513: 7,275 tests, two explained corpus-dependent
skips, all 56 GPG-backed cases, seven Archive browser cases, 60 source rows and
60 independent review excerpts. Tested synthetic merge:
`106a3fda5e8827948c83fe88b415a64c19ad773f`.

During that run main advanced to **`348ff1c8f1de66f668d46fd2406696aa46db2a83`**
with AFP/Kemhan tooling and conditional regional desk rendering. The one new
conflict is resolved by retaining both the admitted-regional loader and the
reviewed Archive projection block. The current DB has zero admitted rows in
either new regional lane; this reconciliation grants no admission or approval.
The absent-count Archive label fix remains unchanged.

Both current isolated production renders were refreshed through `site/render.py`.
They pass with zero errors and ten governed warnings. Their entire candidate
change since reviewed tree `9d5e5d19fd93257a02633fee7fa1f500f4883abc`'s output
is one added blank line in each of the eight desk HTML pages. Every other output
file, including Archive HTML/CSS/JS, both indexes and all shared dependencies,
is byte-identical. This exact comparison preserves the browser, publication-
boundary, route and budget evidence; repeating those unchanged browser inputs
is unnecessary. The fresh full CI still executes its seven Archive contracts.
Sixty focused regional wiring/render/readback and Archive contracts passed.

Both indexes remain bound to the HTML. Candidate output manifest SHA-256:
`8bce55968f1df8a586753c053fe200d54477a8a2808f3fc4c0a61156141e1e02`.
Research-index SHA-256:
`9624fa77e93b132d9b3dbf6b3d67cfcb2fccbdc21480fed2acabd8a8a7342d20`.
Raw JS remains 9,879/10,000 bytes; HTML/CSS is 156,997/300,000.

## Snapshot reconciliation

The original PR receipts used main `e376bcb6bfc9c2926d21c180a944535917990172`:
2026-10-15, 873 archive records, 966 eligible items. The interim `d53ee0ed...`
render used the same corpus/index payload. Current main has 912 records and
1,006 eligible items, dated 2026-10-17, logical SHA-256
`6dc8594a72c2b8fd435a95c59f5a4af4e4eda98ae474610b9ad463b0df704930`.

The increase is exactly 39 archive records (24 PLA Daily, ten MOD China, three
Xinhua Military, one China Military Online EN and one Global Times Defense),
plus Treasury reference `sb0662`. No old item disappeared. All 873 retained
archive citations advance their snapshot; records 5276 and 5277 also carry main's
existing transition from awaiting screening to not selected for analysis. No
other retained field changes. Human analyses/originals/reviewed artifacts retain
their prior counts and permissions.

The four-path receipt compares equivalent clean-main and candidate renders,
not candidate output against stale tracked output. That scope is unchanged:
`archive.html`, `archive.css`, `browse.js`, added `archive-research-index.json`.
Current clean-main has 1,893 files; candidate 1,894; 1,890 are identical, none deleted.

At pinned ca4424, main's own render differed from tracked output at 980 paths:
971 HTML pages change only shared Team navigation/colophon or author-credit links;
three individually reviewed HTML pages change about/team presentation, the
maintainer citation title, and Desks' measured MND count (15) and unadmitted
country/DAPA boundaries. The sitemap adds Team and three author URLs. Five new
files are Team, staff CSS and three author profiles. These groups account for
all 975 changed plus five added paths; no unexplained path remains. Candidate
versus tracked ca4424 main was 983 paths (977 changed, six added), with overlap
between Archive and inherited shell changes. On current 348ff1 main, the new
conditional template adds a blank line to Korea too: inherited drift is **981
paths (976 changed, five added)**; candidate versus tracked main is **984 paths
(978 changed, six added)**. The prior 980 groups remain accounted for, and the
sole new inherited path is whitespace-only `korea.html`. The U.S. page update
on main already includes its blank line. No unexplained path remains. None of
this establishes release approval.

## Final Linux CI

The unchanged full offline suite, validator and preservation gate run on the
PR synthetic merge. CI now verifies GPG availability, logs the actual head/base/
merge SHA, fetches the eight exact ledger commits without credentials or branch
updates, verifies their blob IDs, and replays all 60 source rows plus 60 independent
review excerpts. Missing objects or GPG fail rather than reducing coverage.
Workflow permission, trigger and preservation safeguards remain enforced.
The 116 scoped workflow/Archive/pilot/review checks passed locally.

The earlier Linux run 39034183101 and local 7,228-test run are historical;
neither substitutes for this final revision. Final exact-head CI results are
recorded in PR #776 and the local completion receipt after the push. GPG-backed
classes and applicable historical replays must execute. The two corpus-dependent
cases may skip: absent quoted vocabulary and the immutable August launch default.
The current explicit corpus pin and wrong-content rejection remain validated.

## Concrete output-release proposal

1. Review the exact corpus/output pin and separately approve main's 981 inherited
   changes. Publish main's Team routes before or together with their new links;
   a four-path Archive-only publication onto current tracked output is incomplete.
2. At an authorized window, recheck current main, renderer competitors and all
   queued/running Pages writers. Repin/recheck affected evidence if inputs change.
   Separate inherited-main output from Archive output in review/commits.
3. Require passing actual-final-head/current-base Linux CI and owner authorization
   for automatic feature activation before merging. Source-only merge can enable
   Archive on the next eligible daily render; daily-update/pages-deploy have
   different concurrency groups. The optional #739 guard is not assumed active.
4. Publish HTML and both bound indexes from the same accepted production build,
   using the existing authorized output-only path if selected; then verify real
   public bytes/bindings, legacy routes and desktop/mobile/no-JS behavior.

No generated production output, DB, canonical editorial/permission records or
private artifacts are authored into this PR. Inherited main files enter only
through reconciliation. PR #766 and db53 are untouched. Merge, inherited-output
approval, publication and live readback remain outside this authorization.
