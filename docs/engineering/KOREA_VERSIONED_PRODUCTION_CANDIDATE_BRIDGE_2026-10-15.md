# Korea — versioned shadow-to-production candidate bridge

**Engineering scope, October 15, 2026:** a real read-only normalization step connecting the existing Korea collector's actual `shadow_records` schema to per-source, versioned **pending** production-candidate envelopes. This is not an admission or a publisher release. Unlike the static 14-source official link workbench, the bridge can read **new** Korean records as they arrive in a compatible, immutable, verified shadow Git checkout.

## Actual pipeline

1. The scheduled `KoreaPolicyAdapter` currently collects source documents on the separate `shadow/korea-policy-briefing` state branch. Each preserved row contains `source_identity`, canonical official URL, portal date, original Korean title/text, immutable original-text digest, issuer/publisher metadata and both HTML and HWPX capture identities.
2. This bridge first invokes the existing strong `verify_korea_private_custody_equivalence.inventory()` audit against an owner-provided local Git checkout. That checks clean Git state, the immutable fourteen-original ancestor `0595f0fd29b769cbab5dd57c2ef57af174237a67`, the founding clock, the historic October 12 failure, all SHA-addressed captured bytes, ledger content and database identity. The checkout **may contain new later records**, but must retain the old evidence. It does not call any government publisher.
3. A read-only immutable SQLite connection checks each stored Korean record's canonical government URL, MND issuer versus Korea Policy Briefing publisher, `ko` source language, date, source slug, `syndicated_press_release` kind, `published_hwpx_text` scope, original text SHA, HWPX and captured HTML SHA, and first-seen run identity. **Every actual preserved HWPX is also re-extracted offline** with the existing bounded Korean HWPX parser; any difference from the stored complete Korean text blocks candidate staging, including when the database text and its SHA have been changed together.
4. Each row becomes a normalized **production candidate**, carrying only structured identities, official source URL, portal date, SHA pins, source kind/authority, first-seen run and a deterministic version digest. A new version of one government source produces a distinct candidate version, rather than silently rewriting a previously reviewed item. The contradictory 2025/2026 excavation-year release `156785161` retains an explicit hold.
5. The bridge audits the original Git/capture state **again** before writing a new owner-only 0600 JSON packet to an explicitly chosen absolute path outside the public repo, with a 0700 owner-only parent. Its CLI prints only a count/digest metadata receipt and never prints Korean original text, title, path or reviewer identity.

## What this solves

It supplies the missing **collection-to-normalization** interface for a full Korea desk. Future source-review systems can bind a human's approved exact-version decision to `source_identity` + `candidate_version_sha256` + capture hashes before allowing the record into a separately reviewed production import. New records do **not** need to be added manually to the five- or fourteen-link public directories to become eligible for private normalization.

The normalized schema is country-specific and source-bound. It distinguishes the issuing **MND** from the republishing **Policy Briefing** institution, so Korea is not misrepresented as direct MND-website ingestion or an independently corroborated military event.

## Explicit remaining production boundary

Every exported candidate has `disposition=held_pending_exact_version_human_and_rights_review` and **false** flags for text/title/media inclusion, production ingestion, model use, editor email and public publication. It has no ability to import into `pla_watch.db`, register Korea as a live desk, call Claude, email Dylan, deploy to Pages or extend DAPA source coverage. A fake self-attestation or a metadata-only script cannot authenticate a reviewer or confer rights.

A separate future **human/rights-bound admission and disposable production-database rehearsal** must verify (a) authenticated exact-version Korean review, (b) scope-specific permitted original text handling and attribution, (c) independent private archive backup and recovery, (d) genuine scheduled collection reliability, (e) production DB schema and source-specific normalization, (f) no contradictory claims, and (g) owner release authorization. For a public text/analysis release, a separate content-use decision is required. The existing general shadow promoter is *not* blindly reused for Korea: it expects verified correction overlays and has different storage semantics.

## Operator-only local rehearsal

Only after legitimate authority to handle the restricted original files on an encrypted local computer, provide a clean owner-controlled checkout of the Korea shadow evidence and a fresh output directory with 0700 permissions:

```bash
python -m scripts.stage_korea_production_candidates \
  --source-checkout /absolute/secured/korea-shadow-checkout \
  --private-output /absolute/owner-only/staging/korea-held-candidates.json \
  --explicit-no-send-or-promotion
```

**No real-source run has been performed as part of this PR.** Its focused PR-only workflow uses five fabricated HWPX ZIP/XML originals and SQLite fixtures, then adds a sixth newly collected fictional release. Tests verify full Korean-text re-extraction, hash-consistent forged source text denial, issuer/date/source mutation rejection, corrupted captures, founding-clock forgery, safe output, and owner-only file permissions. No real publisher request is made. The full exact-head repository test suite remains a separate merge requirement.

The ongoing fourteen-link public release #644, authenticated seven-day census #634, original source custody #520 and Korea editorial gate #221 are independent. None is automatically lifted by a successfully generated candidate packet. 
