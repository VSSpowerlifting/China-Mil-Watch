# Korea Desk — private site rehearsal using record-specific reviewer decisions

**2026-10-11**. This stage joins the exact source/rights/owner structural checks from `core/korea_reference_gate.py` with the real, IPR-branded Korea page rendered by `site/preview/generate_preview.py`.

The previous Korea site mock-up only showed five HOLD candidates. After a genuine Korean HWPX reviewer, rights reviewer, and editorial owner produce an **externally verified** packet, this tool can check that the *shape* and source hashes match and render the resulting short English source descriptions on the actual site layout **without publishing them**.

## Commands

Default, still all five HOLD:

```sh
python -m scripts.preview_korea_site --out /tmp/korea-preview-unsigned
```

Future structural private rehearsal, **ONLY** after a separately authenticated human decision packet exists:

```sh
python -m scripts.preview_korea_site \
  --out /tmp/korea-reviewed-site-rehearsal \
  --structural-approval-packet /absolute/secure/offline/completed-decisions.json \
  --acknowledge-no-identity-authentication
```

The packet must live outside the repository and is never copied to public site output. The reviewer names, rights reviewer names, private checkboxes and timestamps do NOT render in the HTML. The displayed projection contains only official issuer/publisher identities, source link, original Korean title, separate portal/distribution dates, human-edited English descriptor and bounded original SHA provenance.

## Exact bounds

- A record renders a proposed English reference description only if the **same individual record** has the expected exact content SHA and HWPX capture SHA, source URL/issuer, complete independent Korean review fields, page-specific text-only rights fields, and owner reference-only approval fields. The schema checks date sequencing and only the five frozen source identities.
- Other candidates stay separately marked `HOLD`. The output clearly labels all structurally passed rows as **PRIVATE QA only / human identities not authenticated by code**.
- **Critical limitation:** JSON names and `true` values are not a signed human attestation. The qualified reviewers and owner must authenticate outside this program. Synthetic test packets are for regression tests only and are not source approvals.
- Refuse source SHA drift, HWPX mismatch, swapped or extra IDs, bad rights flags, packet files under repository, any public `site_origin`, indexability, ordinary site builds receiving approval packets, production collection, source-body import or automatic Briefs.
- Render the exact same desk template as IPR. Keep Korea `status=shadow` and `public=false`. The preview is an unlinked, noindex local `korea.html` and never enters sitemap, navigation, or public output.
- A *separate* public-release PR must implement approval authentication/owner review and an explicit, narrowly scoped public metadata allowlist; this private rehearsal does not flip the public registry guard.
- Before a public launch, a human reviews desktop/mobile preview, source attribution, approved English text, correction/takedown policy and exact Git head and then gives an explicit deployment decision.

A private original-HWPX reviewer handoff script is available from merged [PR #419](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/419), with source-local review files and all decisions initially blank. This site QA stage never handles raw HWPX.
