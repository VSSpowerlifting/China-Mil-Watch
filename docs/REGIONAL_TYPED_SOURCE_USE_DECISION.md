# Typed research: owner-signed private-synopsis source-use decisions

Follow-up to Issue #271. This is the offline decision contract, not regional
model integration, a Sunday schedule change, Dylan delivery or publication.

## Why the lanes remain separate

The older scheduled Sunday provisional owner-preview can already offer strictly
bounded, unapproved Japan/Vietnam research synopses under its explicit research
roster rules; this branch does not alter that lane.

The newer HMAC-governed regional thematic selector instead accepts only reviewed
numeric production synopses. The typed Japan/Vietnam research sources must stay
excluded there until a separate source admission/selector integration is reviewed.

Historical Git/SQLite continuity verifies archive consistency, not current
publisher source versions or rights. A live HTML observation digest is not
evidence that the HTML bytes were identical on the publication date. Filling
the existing unsigned human-review worksheet never grants any authorization.

## Manual process

The pure make_unsigned_decision function creates an exact six-source all-HOLD
decision form from the fresh full-Saturday inventory and validated research
notes. All source publisher URL hashes, historical content/commit pins, roster
SHA and unsigned worksheet SHA are immutable.

Only an explicit human owner review may change individual decisions to
private_analyst_synopsis_reviewed. Each positive decision requires:

1. Human review of the current official publisher source, original-language
   factual context and a canonical UTC observed version timestamp, raw-version
   SHA-256 and private issuer/capture reference. This DOES NOT establish
   historical publication-day byte equality.
2. Original analyst synopsis and concrete limitations, including translation,
   issuer attribution, chronology, and lack of third-party corroboration.
3. An explicit legal rights basis: qualifying official published reuse terms or
   written rights-owner permission, documented by reference. An attribution-only
   footer is not sufficient. The operator must explicitly affirm private
   synopsis scope. The tool never copies publisher bodies or clears images.
4. An owner decision made after the completed Saturday reporting week and
   not later than the review execution day. No partial-week signing.

An owner separately invokes sign_owner_decision with an independent secret
of at least 32 bytes in a secure OFFLINE operator environment. The HMAC is
domain-separated from production source reviews; it seals every human entry,
purpose, source pin, date and permission restriction. Do not put secrets,
signed dockets or private source evidence in Git or CI logs/artifacts.

Reverification via verify_owner_decision recomputes exact current source
identities and the HMAC. The result contains only typed approved/held source
IDs and explicit remaining restrictions, not original publisher text, URLs,
human notes, rights documents or secrets.

## Non-authority boundary

An owner HMAC authenticates what the owner attested; it does not magically
prove rights or facts. Even a positive signed private-synopsis decision yields
model_input_authorized=false, dylan_editor_email_authorized=false,
publication_authorized=false and japan_vietnam_production_activated=false.

This module implements NO HTTP, model invocation, SMTP, CLI, report writer,
source promotion, scheduling, database/site mutation or publication.
Focused CI uses fabricated fixtures and a test-only owner key.

The next separate engineering phase may consume these signed decisions only
with independent refreshed publisher/rights/version checks, explicit per-run
owner model authorization, vetted synopsis-only admission, and the established
exact-attachment handoff/publication boundaries. None is implied by this PR.
