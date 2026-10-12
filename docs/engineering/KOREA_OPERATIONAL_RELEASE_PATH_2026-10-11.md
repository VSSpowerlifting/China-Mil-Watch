# Korea Desk operational path — completed engineering stage / held release

**October 11, 2026.** This stage prepares a functional, **private** MND research and editorial review workflow plus a deny-by-default future publication gate. It **does not** publish a Korea Desk, broaden collection, complete a human review or grant source-use rights.

## Available now

- **Actual private researcher:** PR #410 merged to main, adding `--desk korea` and a bounded official Korean MND publication family to the existing SHA-pinned one-command country reader. Example, with an absolute path outside repo:
  `python -m scripts.launch_private_country_desks --desk korea --approve-github-shadow-fetch --format html --output /tmp/korea-private-reader.html`.
  It fetches existing GitHub shadow *Git refs only*; never fetches publisher pages. Search reads preserved Korean text in-memory and exports **titles, dates, publisher links and provenance only**.
- **Original-documents evidence:** exact SHA `dcb43b9c4edb471d6def5876701ec4a2e39d5264`, five source originals machine re-extracted with hash parity PASS (PR #411 real-source CI). Human reading and HWPX layout approval remains incomplete.
- **Source-specific Korean semantics and rights:** three documentation-only draft PR #412 files with five AI-assisted Korean analyses and rights observations; they explicitly **do not** impersonate a qualified human Korean reviewer or legal authority.
- **This PR:** Five **actual pinned source metadata records** stored in `research/korea_reference_candidates.json`. Titles/identities/public links, the archived Korean text SHA and preserved HWPX capture SHA; **no copied text bodies or binary originals**.
- **Workable private reviewer interface:** `python -m scripts.korea_reference_workbench --mode workbench --out /tmp/korea-review-workbench.html`. Displays five source links, chronology (Oct 4 distribution vs Oct 6 portal for missile statement), original-language titles and SHA identity with explicit HOLD. No reviewer signoff is fabricated.
- **Separate private static release-preview QA:** `--mode release-preview --approvals /private/completed-human-reviews.json --explicit-private-preview --out /tmp/korea-private-preview.html`. It will **refuse now**, because signed independent Korean-language, source-rights and owner approvals do not exist. It must not deploy or publish even if a structurally complete packet is supplied.

## Admission gate

Each *individual* row must bind to immutable `source_identity`, `content_sha256` and `document_capture_sha256`, and the exact shadow branch commit. A privately stored external reviewer packet (`ipr-korea-source-admission/1`) requires **three independent evidence categories**:

1. A named competent human Korean reviewer confirms *rendered original HWPX compared*, Korean semantic/technical terminology, names/dates, distribution-vs-posting chronology.
2. A named source-rights reviewer confirms the **specific official article page** KOGL Type 1 **text-only** attribution mark and that no unlicensed images/annexes/HWPX are included; permits only short human-edited English descriptions and official outbound links.
3. A named owner/editor explicitly approves the **specific record** for **reference-only use**, after both previous reviews; nothing else is authorized.

JSON validators enforce version/date/identities, explicit true values and strict field shape, block fifth-to-sixth expansion, aliases, fake DAPA issuer, hash drift, source-body leakage and output inside the public repo. **Caveat:** names and statements inside JSON are not cryptographic signatures. The actual reviewers and owner must independently authenticate the provenance of the approvals outside this tool. A structurally accepted *private* preview is not approval to change a public route.

## Required next engineering and editorial stages

- **R1:** Conduct qualified human Korean review and record source-specific rights/owner verdicts privately, including the October 4/6 chronology discrepancy. Exclude any failed rows.
- **R2:** After R1, a separate PR can integrate the strictly approved metadata projection into the site's existing `core/reviewed_source_links.py` / desk template. Require SHA-pinned receipts, **explicit manual feature enablement**, zero corpus/count changes, quality assurance and an accessible static preview. Unapproved rows cannot appear. No release from a draft PR.
- **R3:** Owner separately decides whether to deploy a tiny, accurately labeled Korea **reference pilot**: at most five MND republications, not direct MND source, no DAPA, no future scheduling, no whole-Korea coverage claim, no new production collector. Resolve 7/14/30 source qualification separately if promoting into full production collection.
- **R4:** Any operational source expansion (including DAPA) requires its own source rights/robots access, Korean original review and owner admission. This track authorizes none.

Safety boundaries: Existing `desks/registry.json` status stays `shadow`; production SQLite, public archive, briefs, collector configs, schedules, public HTML, email and deploy **unchanged**. All generated files are private, exclusive-created `0600` outside repo; HTML disallows scripts and search indexing.
