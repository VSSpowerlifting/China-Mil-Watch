# Korea archived KOGL Type 1: authenticated original-source replay

**Engineering boundary — October 15, 2026. No new publication authority.**

The standing-license fast lane in #703 requires independently authenticated source
and per-item KOGL Type 1 evidence. This change supplies **those two callbacks
only**, for the already preserved Korea Policy Briefing / Ministry of National
Defense HWPX collector family.

## Verification from actual preserved bytes

The verifier runs `scripts.stage_korea_production_candidates.build()` over a
clean, ancestry-checked checkout of `shadow/korea-policy-briefing`. That
existing stage proves preserved source Git identity, original SQLite and capture
hashes, exact publisher date/issuer/URL, and byte-for-byte HWPX re-extraction.

For each source, `core.korea_archived_kogl_replay` then reads the preserved
**actual publisher HTML**, checks its filename and SHA256 against the stage
record, and requires exactly one canonical source URL and exactly one
article-local `div.kogl_wrap .type` KOGL Type 1 **text-only** marker. The
expected Type 1 image badge and publisher warning about third-party non-text
photos and media must agree. All article checks are version-bound.

`verify_archive()` produces **counts and Git SHA only**. The two implemented
callbacks of `KoreaArchivedMarkAdapter`, `source_replay` and
`item_license_replay`, re-authenticate the frozen source every time they
are called; the private-only `read_original_text_private()` method returns
source bytes only to the in-process operator.

The GitHub Actions workflow runs synthetic negative tests and replays the
**actual** preserved Korea shadow Git branch using read-only permissions.
It never uploads original HWPX, Korean bodies, publisher HTML, source text,
translation drafts, or previews as Actions artifacts.

## What remains deliberately HELD

An authenticated historical article mark is **not** a proof of the publisher's
current standing terms or a judgment that all text is first-party. These
callbacks do not implement `policy_replay` or `exception_replay`; therefore
the published `stage_verified_original_text()` function cannot be invoked
successfully on the basis of these two callbacks alone.

The next engineering phase is a genuine fresh current-policy capture and
replay, an independently controlled per-item first-party/third-party exception
review, and a private end-to-end source-to-staging proof. Only then should a
separate production text schema, file-scoped page writer, guarded release and
live published-byte readback be considered.

**Current publication authorization remains URL/date/issuer metadata only.**
No Korean original text, HWPX binary, photograph, translation or machine notes
are authorized or published by this work. A particular preserved article with
an unresolved chronology issue remains under editorial hold despite its
Type 1 mark.
