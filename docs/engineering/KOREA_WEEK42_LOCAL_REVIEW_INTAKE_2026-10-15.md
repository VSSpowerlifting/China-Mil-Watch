# Korea Week-42 human review intake — private, version-bound, no-send

**October 15, 2026 — stage-only operator tool. No actual reviewer has signed a record.** The three source-pinned Week-42 research notes were merged by [#602](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/602); page-specific KOGL Type 1, text-only attribution evidence was merged by [#607](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/607). The public [three-source reviewer checklist](KOREA_WEEK42_THREE_SOURCE_REVIEW_HANDOFF_2026-10-15.md) is proposed in [#611](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/611).

A Korean original being read by a person is important, but the owner-reported reading of 14 documents does not by itself record a **named reviewer, date, rendered-HWPX comparison, specific reuse scope and owner/editor decision** tied to the exact three current source versions. A code checker cannot authenticate reviewer identity or legally adjudicate rights.

## What is pinned — and what is not copied

The tool reads the pre-existing research/korea/private_research_candidates/2026-10-17.json through its fail-closed validator. It creates exactly three reviewer entries with source ID, canonical URL, portal and original distribution dates, extracted Korean text SHA-256, actual HWPX response SHA-256 and archived publisher HTML SHA-256. All tie to frozen source state 0595f0fd29b769cbab5dd57c2ef57af174237a67.

It does not fetch government pages or HWPX binaries, copy original Korean text, collect new records, update the DB/site, call a model or email anyone. The **October 12 missed scheduled collection remains failed**. Conflicted excavation-year original 156785161 stays excluded.

## Local operator steps

Run from a trusted repository checkout on a reviewer-authorized machine. Provide a **new absolute path outside the public repository**.

**Create a private blank form:**

    python -m scripts.korea_week42_private_review --create /absolute/secure/local/korea-week42-human-review.json --explicit-local-only

The tool creates a new owner-only mode-0600 JSON file, refuses an existing destination, symlinks, relative paths and any path in this public repo, and prints only metadata with false authority flags.

A qualified Korean-language reviewer should compare the exact preserved rendered HWPX with the extracted original and inspect the issuer, dates, tables, reading order, names and claim modalities. A rights reviewer separately considers the actual historical KOGL text-only mark, attribution obligations and the exclusion of all media, **only for restricted local synopsis review**. The owner may acknowledge a **local, no-send rehearsal only** after those separate reviews. The roles must reflect actual people and times; do not invent signatures or fill blank approval fields merely because machine parity was green.

After authenticating each human decision *outside* this tool, the custodian may **check the private file locally**:

    python -m scripts.korea_week42_private_review --check /absolute/secure/local/korea-week42-human-review.json --explicit-local-only

The structural checker rejects missing/extra sources, source URL/hash/date drift, changed use scope, true external-model/email/publication flags, malformed JSON, reviewer-order inversions, future or noncanonical timestamps, nonbool review flags, and forged state transitions. A pending section has a blank name/time and all flags false. Stdout contains only aggregate counts and explicit non-authority flags — **never names, concerns, original Korean bodies, paths or files**.

## Strict separation from permission and Sunday

Even if three completed-looking rows pass *structural* validation, the output states:
- reviewer_identity_authenticated = false (JSON names/timestamps are **not signed identities**);
- source_line_evidence_independently_checked = false (no HWPX/line evidence replay);
- legal_rights_adjudicated_by_software = false; source_rights_automatically_approved = false;
- model_use_authorized = false; sunday_admission_authorized = false; publication_authorized = false.

Actual signed review and source-specific rights decisions belong in appropriately restricted storage with a designated custodian. A future **separate owner-approved integration** must prove a genuinely fail-closed path into a private no-send manuscript/citation rehearsal; never let this structural form silently authorize an AI call, SMTP, public site or production database.

The source-custody decision remains held in [#520](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/520); [draft #608](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/608) proposes private Git evidence custody but does not perform a migration. Rights and issue-specific claim holds remain governed by [#221](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/221) and [#601](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/601). DAPA is an independent issuer still requiring its own source-access authorization.

## PR-only verification

The new offline workflow runs the genuine merged three-source packet plus adversarial tests, writes/checks/deletes a **blank** local test file under RUNNER_TEMP and checks protected production data remain unchanged. It uploads no artifact, sends no mail, calls no model and has no publisher access. **Never commit/upload a filled review file or personal reviewer identity to a public PR, Actions artifact or public issue.**

**Disposition:** structural intake prepared; real reviewer signatures and scoped permissions still pending; Korea not production-admitted.