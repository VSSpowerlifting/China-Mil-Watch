# One thematic Sunday Brief from verified-format production and research evidence

## Desired editor-facing experience

Dylan receives **one substantive draft with one editorial focus**, source-cited
paragraphs, a conventional **production record appendix**, and a second
explicitly labeled **external official-source research appendix**. He should
edit and verify the argument, not stitch together Japan and Vietnam
supplements. The drafting model may inspect and cite Japan/Vietnam material
alongside eligible China/Singapore/etc. production records, but it is instructed
to *omit unrelated inputs*. An October 5 meeting in Hanoi does not automatically
fit an October 5 exercise notice in Japan.

A unified draft is provisional. An attributed model-generated sentence is
**not** a confirmed translation or a publisher-endorsed fact. Dylan and Ben
must actually examine the exact original sources before publication. New
source access, full-text republication and desk activation still require their
own approvals.

## Evidence boundary

1. Production evidence is queried READ-ONLY from the regular SQLite archive,
   paired against the exact source trail and restricted to stored bodies of at
   least 250 characters. Ten total source bodies maximum; selection takes one
   per live desk first, then a second per desk as space allows.
2. Separate short, original, source-attributed editorial synopses come from
   `research/briefs_editorial_evidence/<Saturday>.json`, with hard exact-week,
   date, issuer/domain, source identity, hash, metadata, and size checks.
   The packet is *only* a private drafting input. It copies no article body.
3. This week's file contains five actual official-source candidates:
   - Japan October 6 Kunisaki disaster-relief publication, official HTML
   - Japan October 6 U.S. ambassador defense-minister meeting, official HTML
   - Japan October 5 Tsuiki airfield agreement, pinned shadow PDF extraction
   - Vietnam October 5 Turkish security-industry contacts, pinned MPS extraction
   - Vietnam October 5 Concordia security-technology research contacts, pinned
     MPS extraction
   Japan body/hash and Vietnam source metadata are independently cross-compared
   with the existing country review packets in offline tests. The actual source
   review approvals are still pending.
4. The model schema still permits **only real numeric production IDs** in
   `citations`. Research input can appear **only** under typed IDs such as
   `JP-W41-06` and `VN-MPS-1791199100` in a separate
   `supplemental_citations` map. Every factual section requires at least one
   actual supplied ID of either type. Cross-desk comparison requires cited
   sources from two distinct issuing desks, not a fabricated collaboration.
5. The `editorial_focus` field explicitly anchors a single narrow theme.
   Its presence is mechanically validated; **semantic cohesion still needs
   editorial review**. Nothing forces any research source to be cited if it
   doesn't support the chosen development.
6. The editor's .txt has no separate Vietnam/Japan supplements when the
   synthesis lane is active. The immutable external bibliography lists URLs,
   original headlines, provenance classes, actual state hash when one exists,
   and source-specific cautions. The returned-file validator permits Dylan to
   adjust citations within the original reference universe but rejects
   fabricated external or numeric production IDs.
7. All publisher and shadow data is **untrusted input**; short summaries may
   not be treated as verbatim source quotations or independent confirmation.
   No automated Brief approval, numbering, public source archiving, topic
   classification, source collector activation, or publication is introduced.

## Sunday activation and contingency

The replacement Sunday schedule is **19:17 UTC each Sunday**, only after a
same-Sunday production success marker (for current-week runs). Monday 8 p.m.
Eastern remains Dylan's return target. The Sunday workflow offers a full
Saturday-ending week to the model, loads the narrow research packet using
`--full-week --include-research`, and sends one editorial email only when the
separate repository variable `IPR_SUNDAY_EDITOR_DELIVERY_ENABLED=true`.

The old Friday schedule is left untouched and needs
`IPR_EDITOR_DELIVERY_ENABLED=false` before Sunday's service will send.
**Both variables must never be enabled concurrently**. The workflow and
script have default no-send behavior for manual preview, and the scheduled job
skips entirely while Sunday delivery is disabled. A malformed research packet
fails closed **before** the model call or SMTP. If no weekly packet exists, the
ordinary production-only Sunday draft remains possible; it must not imply that
Japan/Vietnam were reviewed or that no publications occurred.

The new PR supersedes the *implementation* proposed in pending PR #187 (Sunday
migration) and #201 (Friday shadow packet carry-over). Merge one integrated
Sunday workflow rather than applying both overlapping edits to the writer.
Keep the previously merged #197 Friday candidate lane as a fallback only while
the Friday service remains operational.

## Recurring-source limitation and next collector bridge

**The current 2026-10-10 research file is an initial, source-audited weekly
candidate roster, not automatic future Japan/Vietnam discovery.** Future weeks
will not inherit these sources. The next stage (Issue #200) is to read an exact
immutable, audited Japan and Vietnam shadow state at Sunday cutoff, apply
source-use gates, and generate *new, bounded* candidate briefs dynamically.
No automatic import of publisher article bodies into model prompts should be
activated before rights and exact-version/fidelity review. Empty results or
shadow outages should be disclosed to editors, never called institutional
silence.

## Review & deployment gate

Run:

```sh
python -m unittest tests.test_briefs_editorial_evidence tests.test_weekly_briefs_auto_writer tests.test_weekly_editorial_handoff tests.test_editorial_return_validation tests.test_weekly_briefs_sunday_window
```

Then run full repository offline CI, database/output preservation, rendered
output validation and one Sunday manual no-email preview with a complete
production scaffold and working Anthropic credential. Check the actual
generated text and evidence trail privately; no source content should appear
in public Actions logs or artifacts. **Only after owner signoff** should
Friday delivery be disabled and Sunday delivery enabled. Sending a draft
is not authorization to publish the eventual edited Brief.
