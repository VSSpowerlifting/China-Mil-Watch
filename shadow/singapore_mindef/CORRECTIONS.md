# Correcting history on a shadow state branch

Status: **designed and rehearsed, not applied.** Nothing in this document has
been run against `shadow/singapore-mindef`. The remote branch is untouched.

## The problem this exists for

`visible_text()` decoded a hand-written table of six HTML entities. The
ministry's CMS emits `&#x27;`, the hexadecimal spelling of the apostrophe, which
that table did not know. 84 literal `&#x27;` sequences survived into the bodies
of 29 of the 59 captured records. Separately, `document_title()` decoded
nothing at all on its `og:title` branch, so 4 stored titles kept `&#x27;`,
`&quot;` and `&amp;` verbatim.

Both are fixed prospectively in the extractor. Neither fix touches a record
already captured.

## Why the database is not updated

The obvious repair is `UPDATE shadow_records SET text_original = replace(...)`.
It is not available here, for two independent reasons — both checked against
the real branch rather than assumed:

1. **The state chain.** Every ledger entry records `state_sha256_before` and
   `state_sha256_after`: the SHA-256 of the entire `shadow.db` file. Singapore's
   chain runs unbroken across all 32 ledgers, and the tip matches the file
   exactly. Change one byte and the tip disagrees with the hash the last run
   published, the next run's `before` assertion fails, and the only way to make
   the chain agree again is to rewrite ledger entries that are append-only by
   design.

2. **The per-record hashes.** Every ledger also records the `content_sha256` of
   each record it inserted. A rewritten body either leaves that hash describing
   text that no longer exists, or takes a value no ledger ever recorded.

Measured: an in-place substitution touches 29 rows and moves the database hash
from `ef2d1e4f…` to `6de1f2f4…`, which matches no ledger.

So the rule is not weakened and no exception is carved out. `shadow.db` is
never opened for writing.

## Why not simply refetch

Because live pages move. Of the 29 affected pages, **26 are still
byte-identical** to what was captured and **3 have drifted** — `25jul26-nr`,
`29aug26-nr` and `9sep26-nr`, all in image captions and photo credits.
Refetch-and-overwrite would have rewritten those three with newer text under
cover of fixing an apostrophe.

## The design: a versioned correction sidecar

Corrections live in `state/corrections/NNNN-<field>-<timestamp>.json`, beside
`state/ledger/`. Each file is append-only and chained by content hash to the
correction before it, and anchored to the database hash it applies to. A reader
materialises corrected text on the way out; the stored values remain the
original evidence, permanently recoverable.

Each file carries the full audit trail:

| Field | Meaning |
|---|---|
| `schema`, `sequence` | format, and position in the chain |
| `field` | `body` or `title` — which column this repairs |
| `transformation` | declarative; a reader can apply it without running the tool |
| `anchor.state_sha256` | the database this correction describes |
| `anchor.ledger_tip_file`, `ledger_tip_run_id` | the evidence it follows |
| `anchor.prev_correction_sha256` | the chain link |
| `tool`, `tool_version`, `collector_commit` | what produced it |
| `reason`, `created_utc` | why, and when |
| `affected_record_count`, `total_occurrences` | the totals |
| `records[].url` | article identity |
| `records[].value_sha256_before` / `_after` | original and corrected hashes |
| `records[].occurrences`, `chars_before`, `chars_after` | the size of the change |
| `records[].unchanged` | title (or body), date, URL and identity hashes, so a verifier can prove they did not move |

### The transformations, and why each is provably sufficient

**Bodies — literal `&#x27;` → `'`.** Not an unescape: the stored text has
already been through the old table, so unescaping it again would double-decode.
Sufficiency is evidence, not assumption — for all 29 records, re-extracting the
live page with the fixed extractor produces exactly the string that this
substitution produces from the old extractor's output. The one construction
where a substitution and a real re-extraction disagree is `&amp;#x27;`; no page
in the corpus contains it, and `--emit` refuses outright if it ever finds one.

**Titles — one `html.unescape`.** The `og:title` branch decoded nothing, so the
stored value is the raw attribute verbatim and one pass is exactly what the
fixed extractor now does. Verified equal to re-extraction for all 4. `--emit`
refuses if a second pass would change anything, which would mean the value was
not raw after all.

## Rehearsal result

Against a clone of `shadow/singapore-mindef` at `be52cc125`:

| Claim | Result |
|---|---|
| exactly the evidenced records change | 29 bodies (the evidenced set), 4 titles |
| exactly 84 `&#x27;` occurrences corrected | 84 → 0 |
| no other body content changes | every change is the declared substitution; other 30 bodies and 55 titles byte-identical |
| all 59 records remain distinct | 59 records, 59 distinct bodies |
| zero empty bodies | shortest body 258 chars |
| state and correction ledgers reconcile | `VERIFIED`; 32 ledgers, 0 chain breaks |
| repeat execution is idempotent | second materialisation identical; re-emit deterministic |
| the original evidence remains recoverable | all 59 stored values still the originals; the 84 sequences still on disk |
| the Day-30 packet remains deterministic | same invocation twice → package id `4ad9a838…`, state tree `ad97f27d…` |
| `shadow.db` untouched | `ef2d1e4f…` before and after everything |

## What still blocks applying this

The review kit's state-tree allowlist is `clock.json`, `shadow.db` and
`ledger/`. A committed tree containing `corrections/` is **refused**:

```
review refused: the state/ tree at this commit carries unexpected file(s):
corrections/0001-body-....json
```

That refusal is correct and is deliberately left in place. Teaching
`review_shadow_state.py` to admit `corrections/` and to materialise corrected
text is a separate, owner-approved change, because it alters what a published
packet means. Until then the sidecar can be rehearsed but not committed to the
state branch.
