# First editorial article review — seven exact sources, two unsigned dockets

**15 October 2026 · reviewer handoff only · not public approval or production source admission**

This packet makes the first two proposed permanent *editorial* country-desk publications easier to verify. It does not replace the full 22-original Philippines AFP or 31-original Indonesia Kemhan reviewer dockets. Both full cohorts remain necessary to evaluate any eventual broader production-source admission.

## Inputs: the owner's actual manual workflow artifacts

From the completed **main-branch** GitHub Actions dispatches, download and safely unpack:

1. **AFP first 22 originals — unsigned consolidated human review docket:** its single `ph-afp-all22-unsigned.json` artifact, backed by three exact scheduled historical commits (13 + 5 + 4 original records). An Actions run ID, attempt, head SHA and successful conclusion should be recorded in the human reviewer handoff.
2. **Indonesia Desk — pinned official-link review queue:** its `review_queue.json` metadata-only artifact, backed by exact Oct 14 shadow source commit `0595c6677be24f8f0f33aecb28eec0050e36e8f9` (31 originals, 15 existing publisher links, 1 geographic hold, 15 other candidates). Its successful run/attempt/head should likewise be recorded.

The inputs are deliberately **not government-original bodies**. Do not copy original API JSON, Indonesian ministry HTML, images or translated source text into this packet or a GitHub comment.

After checking artifact authenticity and run identity in the GitHub Actions interface, run locally in a source checkout containing the frozen `research/philippines/sanlakas_2026/source_event_candidates.json`:

```bash
python -m scripts.select_first_desk_editorial_review \
  --afp-docket /path/to/ph-afp-all22-unsigned.json \
  --indonesia-queue /path/to/indonesia-review-queue/review_queue.json \
  > /tmp/ipr-seven-unsigned-review.json

python -m unittest tests.test_select_first_desk_editorial_review -v
```

**No network, publisher access or repository mutation occurs.** This selector aborts if either original batch's immutable source revision, count, citation URL, date/identity, existing AFP full-body/capture digest, unsigned status, or required disposition mismatches its prior packet. For the Indonesia links, the reviewer docket contains **no per-original byte hash**; the selector intentionally emits `capture_sha256_reference: null`. Actual capture-byte parity must still be verified against the pinned shadow original, not presumed.

## First editorial priorities

| Desk and draft | Prioritize exactly | Central issue for named original-language reviewer |
| --- | --- | --- |
| Philippines [draft #661](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/661) | `afp:1391`, `afp:1393`, `afp:1394` | **One** Sanlakas 2026 exercise with opening, field stage, and closing on separate event dates; AFP publishing dates differ. Venue ambiguous, don't geocode. |
| Philippines [draft #661](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/661) | `afp:1390` | Separate Sept 29 JPSCC meeting and alleged Cyber Plan signing; the PCG commandant's published `Gavan`/`Galvan` spelling conflicts. |
| Indonesia [draft #652](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/652) | Oct 14 Kemhan **MTC opening, closing/protocol, ministerial FSMTC audience** | Ministry reported Oct 13–15 event span **versus** Oct 14 official close; reported signed protocol **not** an inspected contract or independently proven industrial transfer; same ministry is one issuing institution. |

For every selected source, the real reviewer must separately record the preserved source bytes and extraction comparison, original publisher URL/title/date and actual event chronology, exact quotations or uncertainties, source independence, allowable **links versus snippets versus body versus photographs**, reviewer identity and timestamp, discrepancies, and a held/approved-for-precisely-described-use verdict. No checkbox is prefilled, no approval inferred from the successful workflow, and a negative verdict keeps the affected citation or manuscript held.

## What constitutes progress

- **Machine-ready:** successful genuine Actions docket runs and this selector returning all four + three references with no mismatch. This shows **identity/provenance agreement in metadata**, not reviewed original-language facts.
- **Editorial-ready:** named, version-bound human source review on the precise **seven** originals, documented copyright/access scope for the proposed link-first use, final manuscript editorial/owner approval, and governed IPR Brief conversion with exact source trail.
- **Published:** separate permanent-release PR, exact-head CI and rendered-site validation, guarded owner-authorized deployment. The country's **collector stays `shadow`** unless a distinct source-ingestion PR qualifies and ships.

No document/photo rehosting, production database writes, public desk promotion, model/SMTP use, or automatic website release occurs through the selector. It does not claim the whole 22+31 original corpus is reviewed.
