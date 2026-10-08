# Vietnam journal — byte-bound metadata observation seam

**Status:** pure offline integration candidate stacked on PR #163 (metadata
assembler). No publisher network access, article retention, authorized
metadata persistence, source activation, shadow Day 0 or production changes.

## Integrity gap addressed

The lower-level observation assembler in PR #163 accepts four already-parsed
journal listing observations and externally supplied page SHA-256 digests.
That contract is useful for independent researchers but allows an
*integration mistake*: a caller could swap digest A and parsed category B
while still producing an otherwise schema-valid metadata snapshot.

This separate module (scripts/vn_journal_byte_observation.py) accepts the
actual four previously obtained publisher category response bodies **in
memory**, parses each with the real merged English journal listing parser,
computes SHA-256 directly over the matching supplied bytes, and passes
the paired parser results/digests into PR #163's validated metadata
assembler. It never writes out the source HTML or changes the v1 snapshot
schema consumed by the merged PR #161 window comparator.

These are digests of **supplied HTTP entity body bytes**, not a signed
cryptographic attestation from the publisher or a guarantee that a network
transport was unmodified. The caller retains responsibility for recording
the legitimate response/source, following access policy, and verifying
rights to make a persistent bibliographic record.

## Required input

The public API, make_observation_from_bytes, takes:

- body_by_category: a dict with exactly the four keys news,
  theory-and-practice, events-and-comments, research-and-discussion.
  Each value must be an immutable bytes object, nonempty, valid UTF-8,
  and no longer than 256,000 bytes.
- captured_at_by_category: one actual UTC second-precision timestamp per
  category in the format YYYY-MM-DDTHH:MM:SSZ, as measured by the
  already-authorized external retrieval procedure. A missing, offset-form,
  malformed or non-UTC timestamp is rejected.
- observation_id: caller-supplied run identifier accepted by the merged
  strict journal snapshot schema.

All four timestamps must be contained in a **30-minute bounded acquisition
window**. This is an offline *coherence guard*, not a crawl-rate policy:
no request is made and a shorter duration is not proof of feed coverage.
The output's single observed_at is the last page's capture timestamp;
it is **not** presented as the identical observation time of all pages.

The module refuses an omitted/unknown section, mismatch between the two
canonical category URL registries, NUL bytes, malformed UTF-8, an oversized
response, or two distinct categories receiving identical response bytes
(which commonly indicates a fallback/error page). The existing journal
parser then refuses pages lacking valid canonical article links and
retains only ID, canonical permalink and unverified local date hints.
The existing v1 validation refuses unexpected fields, forged completeness
claims and cross-category identity contradictions.

A valid returned observation never contains source HTML, publisher
headlines, article text, image or author credits. It also never grants
permission to persist its metadata: the journal's separate source-use
review (Issue #155) remains open.

## Tests and boundaries

The synthetic end-to-end suite is at
tests/test_vn_journal_byte_observation.py. Unlike PR #163's synthetic
dataclass unit fixtures, these tests exercise the **actual** journal
HTML-to-ListingObservation parser and then the real metadata assembler,
including mutation of publisher-like paragraph bytes changing the digest
without changing the observed IDs. It includes negative cases for
identical responses, malformed encoding, wrong categories, missing/invalid
timestamps, a time span over 30 minutes, oversized payloads and
injected nonarticle HTML.

Focused offline run once PR #163 is merged:

~~~bash
python -m unittest tests.test_vn_journal_byte_observation -v
~~~

The module cannot authorize or perform an HTTP probe. It cannot verify
publisher rights, the chain of custody outside the function, the
correctness of user-provided timestamps, site-wide pagination, historical
completeness, first publication dates, zero missed articles, or future
collection reliability. None of those are established by matching
response digests.

**Merge choreography:** this PR is initially stacked on #163 only
because it needs the assembler module. Once #163 has independently
passed CI and merged to main, retarget this change to main; independently
verify its exact-head CI and diff (this module, synthetic integration
tests, documentation), and stop for separate owner review. The
future-window diagnostic #176 is independent.
