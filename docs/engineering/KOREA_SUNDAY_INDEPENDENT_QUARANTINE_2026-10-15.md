# Korea Sunday quarantine — independent pre-model and pre-email gate

October 15, 2026. The three Korea Week-42 HWPX-pinned, authored synopses remain held for local no-send drafting. Korea is still a shadow desk with zero production records. The Korea no-send manuscript rehearsal in PR #625 and the independent backup operator capability in PR #628 confer no model, email or publication permission.

## Operational boundary

The existing Sunday editor workflow already refuses Korea in the shared, strict source validator. This proposal adds an **independent explicit denial** at three points in the real scheduled and manual Sunday workflow: before refreshing source evidence, immediately after Vietnam's current-source packet is created, and after the final editor-safe packet is selected but before the Anthropic writer/email handoff.

The new offline gate script at scripts/sunday_korea_quarantine_gate.py rejects any record with desk=korea, a KR- or korea-policy: identity, or the korea.kr official source hostname, even if somebody later widens the general editorial source-family validator. It also runs the current existing validator; this is additional denial, not a substitute for strict source identities, permissions, source hashes or dates.

## Functional limits

The real October 17 research packet contains Japan and Indonesia source IDs only; it remains accepted unchanged. Japan, Vietnam, Indonesia and Philippines research continue through their own current checks. For initial unrefreshed evidence only, a missing week-specific file is a safe empty result; missing refreshed or final packets are held. Tampered packets, wrong dates, unknown desks, copied bodies, changed permission flags, malformed or symlinked files, and unapproved Korea source substitution are refused.

This guard can NEVER authorize admission by a configuration flag. Actual Korea participation would require a separate owner-reviewed code change, authenticated source-version Korean reading, original and derivative rights for the requested use, independently recoverable private custody, prospective collection qualification, and separate approval for model/SMTP/publication.

## Verification

A PR-only workflow tests source injection into a copy of the real October 17 Japan/Indonesia packet, including forged Korea IDs, canonical Korea publisher hostname, unknown desks, edited copy_scope and widened general loader. Structural tests require all three workflow quarantine call sites to precede the model writer. They never access the Korean original HWPX, publisher website, private vault, production database, AI API, SMTP, real Sunday dispatch or site deployment.

Require current-head focused and repository-wide offline CI plus owner review of the live workflow before merge. Passing CI means Korea is safely *excluded*, not qualified for production. Outstanding release gates are tracked in Korea issues #221 and #520.
