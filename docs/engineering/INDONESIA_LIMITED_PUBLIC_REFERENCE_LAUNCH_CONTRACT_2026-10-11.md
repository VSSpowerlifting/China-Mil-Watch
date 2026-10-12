# Indonesia: minimum public-source reference launch contract — UNAPPROVED

Baseline 11 October 2026; draft PR #421. This specifies the **next owner-reviewed release**, not publication authorization or content rights clearance. Technical readiness is not source admission.

## Exact product

A non-live Indonesia Desk page, marked **shadow evaluation**, containing at most four independently approved Kemhan Berita first-party links with their original Indonesian titles, publisher attribution, and publication dates. The four candidates are ID-01 (Sudirman Dialogue 2027 **preparation**, not a held event), ID-02 (Singapore departing defence attaché courtesy call, not a new agreement), ID-03 (Sanggau Yonif TP 833) and ID-04 (Bengkayang Yonif TP 926). The source-pinned JSON and five original-language notes are in this PR. ID-05 (Yonif TP 880) remains **excluded** because the original publisher text contradicts itself about the location (North/West Kalimantan).

No production article, copied body/photo, quotation, translation, interpreted facts, shadow-count-as-coverage, model analysis, source institution count or archive-record route is eligible. One ministry institutional-news family is not comprehensive Indonesia defence coverage.

## Human and evidence prerequisites (all currently unresolved)

1. **Actual Day 7 after October 13, 2026 scheduled collection.** Pin new immutable Indonesia shadow SHA after its actual 17:17 UTC nominal slot completes; produce source-specific review_desk_shadow.py packet; independently enumerate all Indonesia and Korea shared-workflow attempts, artifacts, failures, skips, reruns and missing days. Distinguish late starts from missed logical slots. A manual attempt cannot silently replace a failed scheduled attempt. Store private full-original packets outside the public repo/artifacts. Named human records actual review completion time and source checks. October 11 success is only a pre-Day7 rehearsal.
2. **Named human Indonesian-language original review.** Read and compare the exact four archived originals and official publisher pages; independently check title, identity, publisher date versus event date, complete extraction, institutional voice, and nonclaims; hold the discrepant fifth case. AI semantic review in PR #421 is not human signoff.
3. **Individual rights-use decisions.** Kemhan Berita pages display a ministry copyright notice. An official-link and minimal title/date treatment may be acceptable but **has not been legally or editorially cleared**. Obtain a qualified named source-use assessment, record attribution and scope for each proposed reference, and keep full text, images, excerpts and translated republication on hold. Official publisher PPID address: ppid@kemhan.go.id; unsent Bahasa Indonesia inquiry available in the research/indonesia directory. No unanswered permission request implies licence.
4. **Owner review and acceptance of exact release diff.** Review four-source allowlist, publisher limitations, page wording, human signoffs, blocked cases, responsive design and immutable main SHA. A boolean in JSON is not an authenticated individual decision.

## Future separate public PR, only after prerequisites

- Add Indonesia to desks/registry.json with public true but status **shadow**, no production manifest and has_production_records false; describe exactly one Kemhan Berita family and limits. Do not admit source records through the registry.
- Extend core/reviewed_source_links.py by a **distinct Indonesia-reviewed source-link schema** validating only the exact official HTTPS www.kemhan.go.id dated path, date concordance, original language id, unique source identity, source-state SHA, independent human review and per-record publication permission. New research/indonesia_reviewed_links.json must contain only approved bibliographic metadata, not captures or source bodies. Do not inherit Vietnam MOIT, Korean KOGL or Philippine AFP rights decisions.
- Reuse the existing Philippines/Vietnam metadata-only reference component in site/preview/templates/desk.html and render a real Indonesia route only when the separately approved registry/source allowlist permits it. The current Indonesia preview flag is **private-only**.
- Update static routes, navigation, sitemap, validation, and the exact-scope country_research_render_only_release.yml workflow (currently explicitly scoped to Philippines/Vietnam). Test original-title escaping, 375/1280 px layouts, focus, no-JS links, empty or revoked approvals, protected public DB and output. Pin the exact owner-reviewed main SHA for render-only deployment; otherwise no public site change.
- Record the narrow owner-approved reference launch in DECISION_LOG.md separately from potential future corpus admission.

## Different, later production admission

After **30 actual consecutive evidenced collecting days** and all named Day 7/14/30 reviews, reassess publication-specific rights, collection completeness, language accuracy, provenance, source quality, exclusions and owner's separate approval. The disabled Siaran Pers candidate and any TNI or ministry expansion require independent clocks, original reviews and rights; do not infer them from Kemhan Berita.

**Current state:** Actual-template, noindex private preview built and CI-tested; four link candidates HELD. No independent human Day 7 review, final publisher use decision, Indonesia public route, owner publication acceptance or production corpus admission.
