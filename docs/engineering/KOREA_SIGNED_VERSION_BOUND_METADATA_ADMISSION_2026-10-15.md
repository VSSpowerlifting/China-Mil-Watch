# Korea exact-version human + owner admission for metadata-only import rehearsals

**October 15, 2026.** This is the next operational stage after [#656](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/656) (Korea shadow original-to-versioned candidate normalization). It accepts a previously verified private, source-pinned candidate packet, provides a blank per-record review form, and checks separate reviewer and owner HMAC attestations for a narrowly bounded **metadata-only disposable database rehearsal**. It cannot promote into the real production database, modify the public Korea desk, use a model, email the editor or publish articles. All HWPX, Korean bodies and media are excluded.

## Concrete intake sequence

1. A secured local Korea shadow checkout is verified and normalized by `scripts/stage_korea_production_candidates.py`. Its versioned packet is generated from the real preserved source Git tree and matched HWPX/HTML/text captures, not arbitrary unpinned data.
2. `core.korea_versioned_review_admission.blank(packet, source_identity)` creates one **held** unsigned review sheet. All five verification questions are false and rights references are unreviewed.
3. A qualified independent Korean-language reviewer checks the exact HWPX rendering and extracted text; source, portal date and issuer; claim modalities; link and attribution terms; and nontext media exclusion. They record those checks and the exact candidate SHA/version, plus the source-specific rights reference. A locally provisioned *trusted reviewer HMAC key* signs the canonical document. A reviewer name alone is **not authentication**.
4. After seeing the exact signed review, the owner records a separate, later decision and signs the complete reviewer seal with a **different** trusted owner HMAC key. Both secrets must be provisioned outside GitHub and the code; they must never appear in source, PRs, CI, artifacts or logs. Without the verified keys, all review claims remain untrusted.
5. `verify(packet, seal, reviewer_key, owner_key, as_of_utc)` independently checks strict packet/row schemas, candidate version digest, source Git commit, database SHA, original Korean HWPX/text/HTML SHA pins, signer separation, date order, permissions and exact reviewed rights scope. It emits a redacted receipt indicating whether that specific metadata-only candidate is eligible for an **isolated disposable database rehearsal**. No original text or reviewer name is emitted.

The deliberate **exception:** Article `156785161` remains blocked because its excavation-year dating is contradictory; a formally signed reviewer assertion cannot bypass unresolved original-source ambiguity.

## What an apparently positive receipt does NOT mean

It proves the supplied review record matches the supplied source-version metadata and bears signatures from two keys *provided to the verifier*. Without independently trusted keys, correct reviewer identity, valid source evidence and a human evaluation of publisher rights, these receipts prove neither the reviewer's real-world identity nor legal permission. Both signing keys, their custody, rotation, allowed reviewers and trusted operator are separate prerequisites.

A positive receipt is limited to `reviewed_official_link_metadata_only` and **does not permit live production import, website publication, copying Korean titles/bodies, translations, embedded-media reuse, sending source text to any AI model, Sunday delivery, or external email**. All such flags remain false even for approved metadata rehearsals. Every actual public or production use requires another separately reviewed owner/publisher scope.

The existing public directory's 5+9 owner approval under #644 applies to those selected URLs only; it is NOT a blanket right for new, future Korean records. New source identities can be normalized automatically in #656, but cannot become admitted on their own.

## Real next step

Build the isolated import simulator that takes only the independently verified signed metadata-rehearsal receipt plus source-pinned candidate, loads them into a **scratch schema** without originals, and reports normalized metadata, idempotency, source version drift, deletion/rollback and display snapshot. Then integrate secure owner-approved actual production record ingestion via explicit rights/custody and Korea-enabled schema migrations. The current China production schema does not automatically imply it can accept Korean BCP-47/authority metadata.

## Verification and release hold

The PR-only CI has no Korean originals or real signing secrets; it uses entirely fabricated candidates and two nonsecret synthetic keys to confirm correct version-matched dual signature, stale source/commit, tampering, missing review check, wrong issuer/title/media rights, wrong key, premature owner signature, divergent reviewer/owner identity and the disputed excavation-year hold. The full repository offline suite must pass at the exact head. This PR is intentionally **stacked on #656**; do not merge it independently while the public Korea link-only release #644 is pending or without rebasing/retargeting once #656 is merged.
