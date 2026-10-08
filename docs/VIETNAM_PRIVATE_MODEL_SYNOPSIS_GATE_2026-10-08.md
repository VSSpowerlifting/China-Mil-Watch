# Vietnam: version-bound private synopsis automation after a source-use decision

## What this makes possible

The Indo-Pacific Record weekly Briefs writer should choose **one thematic
argument** from a common source pool. PR #203 establishes that shared writer
and initial Japan/Vietnam research citations. PR #211 contributes independently
audited Vietnam MPS shadow data to that model in a private packet.

The remaining recurring friction is **writing a new source-specific English
research synopsis every week**, after Vietnam's collector discovers new
official publications.

`scripts/draft_vietnam_private_synopses.py` prepares that synopsis catalog
automatically **only after an explicit, per-record human decision permitting
a strictly bounded original-language excerpt to be sent to an external
drafting model**.

This is a source-use gate, not a source-credibility ruling, publication
authorization, desk promotion or signed license. The code cannot determine
whether a particular Ministry of Public Security publication permits the
proposed external processing. A human owner must establish and record that
basis independently. There are **zero default authorizations** and this
proposal does **not** ship any pre-approved real source-use grants.

## Before any model invocation

1. A separately operated shadow collector has produced an isolated,
   immutable `shadow/vietnam-mps-foreign-affairs` Git state commit.
2. The operator selects the exact full 40-hex SHA and reporting Saturday.
3. An **external, private** human source-use authorization file identifies
   individual `mps-vi:` source IDs, their current content-version SHA-256,
   canonical official URL, reviewer, approval timestamp, narrow external
   model-processing scope and reason for the source-use decision.
4. The script verifies the same Git commit's ancestry on the correct orphan
   branch, exports the exact historical state, replays the full MPS capture,
   SQLite, content-hash and ledger validator, and checks every authorized
   source is the **current** source version published in the given week.
5. Only then may Anthropic see up to **1400 characters per expressly
   authorized Vietnamese article**. A different digest, changed URL,
   unresolved state integrity, missing permission, out-of-week date or
   oversized excerpt stops the process before any model API call.

The actual source-use decision file is **not** added to this repo. A synthetic
shape for understanding the interface, deliberately **not approved for use**:

```json
{
  "schema": "vietnam-private-model-source-use/1",
  "source_slug": "vn_mps_foreign_affairs_vi",
  "state_commit": "<exact-verified-shadow-sha>",
  "reporting_saturday": "2026-10-10",
  "reviewer": "<reviewer's name>",
  "approved_at_utc": "<ISO UTC instant>",
  "scope": "private-third-party-model-bounded-excerpt",
  "records": [
    {
      "source_identity": "mps-vi:<source-id>",
      "canonical_url": "https://bocongan.gov.vn/bai-viet/<canonical-slug>",
      "content_sha256": "<current-MPS-content-version-sha256>",
      "decision": "allow-private-model-bounded-excerpt",
      "source_use_basis": "<specific independently checked permission and narrow scope>",
      "max_excerpt_chars": 600
    }
  ]
}
```

No placeholders above are valid records or grant permission. A named reviewer
or basis string is recorded as an auditable declaration; code does not
establish the legal truth of a self-declared basis. Repository administrators
must ensure only genuine authorized source-use decisions are supplied.

## Explicit invocation

After reviewer approval, with the exact cloned state branch available
read-only and a correctly configured Anthropic API key:

```sh
python -m scripts.draft_vietnam_private_synopses \
  --state-repo /tmp/mps-shadow \
  --state-commit <exact-shadow-commit> \
  --week-ending 2026-10-10 \
  --source-use-authorization /private/owner-reviewed-source-use.json \
  --out /private/editorial_notes_2026-10-10.json
```

The output is `vietnam-editorial-notes/1`, matching PR #211's Vietnam
queue-to-packet join. It includes only: source identity, official URL,
publication date, current version hash, one **unapproved** English
source-attributed paraphrase, cautions and bounded topical cues. No original
text or capture is in the output file.

Next run PR #211's `build_vietnam_sunday_packet` with that notes file,
a newly verified queue and optional existing Japan research packet; pass
its ephemeral JSON through #203's `--research-packet` to compose **one
cohesive provisional regional Brief**. The model is free to omit unrelated
Vietnam or Japan sources. Dylan edits the *already written* draft. Ben
retains original-language verification and final publication approval.

## Explicitly outside scope

- No automatic legal/publisher-use permission and no unsigned implicit grant
- No publisher-site network fetch or new collection family
- No complete article body or raw PDF sent to an external model
- No automatically approved source quotation or translation
- No silent refresh of changed article versions
- No change to `pla_watch.db`, production desk status, public Brief contracts,
  Friday/Sunday send flags, SMTP, issue numbering or publication
- No source digest represented as a production record ID
- No scheduled execution: an independent, version-checked authorization
  process must exist *before* enabling autonomous model-synopsis generation

## Merge plan

Independent PR. It should merge **after full isolated CI**, but it has no
dependency on #203's conflicting writer files or Japan's shadow PR. It can
land before #211 because it only generates an input format consumed later.
It should never be wired automatically to Sunday's cron until an owner has
approved the actual source-use process.

Test:

```sh
python -m unittest tests.test_vietnam_private_synopses -v
```

Mocked no-network tests verify missing/forged scope, changed SHA, wrong
reporting week, future approval timestamp, bounded excerpts, untrusted
prompts, model schema validation and no model call when source evidence or
the authorization gate fails. These are structural checks, not human
translation or legal-review substitutes.
