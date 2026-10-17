# Editorial team integration — 17 October 2026

PR: https://github.com/VSSpowerlifting/IndoPacificRecord/pull/770
Integrated main: `d53ee0ed043380a05fafa053cdd622a15bcfbed9`.
Original feature head: `977b6c02934eab2629695f07e534a1b6aae2eb5f`.
Merge base before integration: `6a3861b035846e49d9d99b1934e39229253becad`.
Main was merged without conflicts; its Korea/U.S. changes are retained.

## Source and publication boundaries

The validated `site/preview/staff.json` roster supplies `/team.html` and three
`/authors/<slug>.html` routes. Approved biographies, titles and LinkedIn URLs
remain verbatim. Profiles project exact credits from the published Brief
collection; roster membership grants no credit. Dylan's Laos credit is a
recorded **co-author** credit, not a research-only credit. Christin currently
has no credited Briefs. Joint bylines link each recorded person separately.
Historical catalogue bylines read the edition identity, avoiding today's
maintainer title being projected onto an earlier edition.

The ordinary builder supplies `team` to the current shell. Standalone historical
and Korean-original renderers do not supply it, preserving their navigation and
footer bytes. Historical articles still use the current IPR shell under the
October 9 ruling; this compatibility boundary preserves their published bytes,
not a predecessor masthead. No parity assertion or Korea guard was weakened.

No database, source archive, research approval, workflow, sidecar or tracked
`output/` change is included relative to integrated main. Production rendering,
publication and deployment remain separate owner actions.

## Visual review

The directory uses a name/role column beside the approved biography, stacking
below 700 px. Profiles keep the shared utility page header and a readable prose
column. Existing Instrument Serif, Source Serif 4, Inter, jade roles, chart-paper
and chart-shelf assets provide the material treatment; no new image, font,
script or dependency is added. Page descriptions are concise and route specific.

Chromium captures compare production Home, About, Methodology, Desks and Analysis
at 1440, 768 and 390 px with the candidate Team, all three profiles, About,
Methodology and Analysis at 1440, 768, 390 and 320 px. The 43 screen captures
have no overflow, HTTP errors or page errors. Print and forced-colors captures,
mobile menu/profile/back navigation and visible keyboard focus are also checked.
Representative full-page pixels were reviewed for all three staff identities,
directory wrapping, native chrome and visible textures. Reduced motion was enabled.

Local screenshots, visual receipts, reproduction scripts and logs are retained
outside tracked output at `/tmp/ipr-editorial-team-228e/`; the image index is
`visual-review.html`. Large generated images are intentionally uncommitted.
The final PR report records the tested head and authoritative CI links.

## Verification

Focused acceptance:

```sh
python -m unittest tests.test_indo_pacific_identity.TestTheMastheadIsTheNewIdentity tests.test_editorial_staff tests.test_preview_prototype.TestTrancheOneIdentityAndStructure tests.test_historical_brief_shell
```

98 tests passed. The staff module alone passes eight tests under `unittest`;
no pytest dependency remains. Added contracts check production metadata,
canonical uniqueness, sitemap routes, approved rendered roster values, internal
profile links, real published credits and private noindex/schema exclusions.
Historical tests compare all published issue HTML byte for byte.

`python scripts/validate_output.py` passes with the ten governed warnings.
A disposable assembly using `site.render.render_site(output_dir=...)` and
`site.render.publish` against copied carried-forward files also validates
(seven warnings; checks restricted to the repository output are not run there).
Every carried historical file is byte-identical. The three Korean-original
renders equal both current-main templates and their actual published bytes;
the previously failing original-text guard is no longer reproduced.

Full verification uses `python -m unittest discover -s tests -t . -v` and the
existing PR workflows. Local Python's missing, already-required `python-docx`
was supplied through a temporary package directory, without modifying the
shared virtual environment or requirements. Final full-suite outcome and merge
readiness are recorded in the PR report, not inferred from focused results.
