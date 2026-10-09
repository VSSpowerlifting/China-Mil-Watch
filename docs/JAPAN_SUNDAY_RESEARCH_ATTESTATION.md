# Japan source version assurance for the October 10 Sunday Brief

**Machine evidence, never independent approval.** The first unified Sunday editorial writer is live on main following PR #237. For the Saturday-ending week of October 10 it has three deliberately separate, unapproved Japan MOD research candidates. Two are publisher HTML pointers, while the third is a precisely pinned extracted text record from a Japanese MOD PDF on isolated `shadow/jp-mod` state.

## What the new evidence check does

`scripts/attest_japan_sunday_research.py` calls the existing strict parser for `research/briefs_editorial_evidence/2026-10-10.json` and refuses changes to the three Japan identifiers, exact URLs, publication dates or source classes:

- `JP-W41-01`: 2026-10-06 Japan MOD English HTML release on JS Kunisaki's departure after Indonesian disaster relief — **official HTML pointer only**, no archived full body;
- `JP-W41-02`: 2026-10-06 English MOD account of Koizumi's meeting with U.S. Ambassador George Glass — **official HTML pointer only**, no archived full body;
- `JP-W41-06`: 2026-10-05 Japanese MOD Tsuiki airfield agreement PDF — pinned **extracted text** stored on orphan state branch `shadow/jp-mod`.

For the PDF-derived source it invokes the existing, independent `scripts/audit_japan_oct05_brief_source.py` verifier against **commit `d57f0a94b2134a68b9f13fb35a0a0b8c8a4ffe13`** and original Git blob **`60f126db5a36369ade81f44f12c3a838cddbfb59`**. It checks the exact published original-language content digest `d8ec17263a4465f75f79e03d2096ce82b9094da649d2ee0d7f198778d0cd0eb8` against the actual immutable SQLite object. The source audit also checks issuer, original headline, publication date, first-seen run, Japanese phrases, collection scope and archive record count. It never reconstructs or retains publisher PDF bytes.

## Verification limits

The receipt says **original PDF bytes NOT verified; full-PDF human fidelity review NOT completed**. Text extraction fidelity against the full PDF remains an explicit source hold. The other two HTML sources have verified issuer URL/date/format identity in this bounded packet but **do not** have archived full HTML originals or machine content digest attestation. Site access can be publisher-challenged. No HTML source body fidelity is claimed.

The source-linked paraphrases remain editorial notes, not signed agreements, operational exercise confirmation or publisher-certified quotations. Machine matching of a hash does not attest English translation, broader publication coverage, publisher content-use rights or whether any source belongs in a coherent Sunday thesis.

## Workflow

`.github/workflows/japan_sunday_source_attestation.yml` runs on PR and later manually on main (no schedule). It checks out production files with read-only GitHub access and independently clones the isolated `shadow/jp-mod` branch, verifies the exact artifact is an ancestor of that branch, then runs a **pinned immutable Git-object audit**. Only a metadata JSON report is uploaded. No original Japanese bodies, PDF bytes, database files, or unpublished manuscript are uploaded or logged. No Anthropic call, source collection, email, production-desks mutation or public Brief update.

The source audit provides objective evidence to Dylan and the editor, but it does **not** block a normal production-only Sunday draft for other weeks. It explicitly reports no Japan packet for later reporting Saturdays and cannot reuse the October 10 roster indefinitely.

**Next recurring-work milestone:** supply a new exact-week Japan source roster with independently pinned version evidence and short attributed synopses from newly available official materials. The automated producer remains a separate source-use and human-review design gate under [Issue #200](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/200). This PR intentionally does not change the Sunday model's source selection or enable Japan production admission.
