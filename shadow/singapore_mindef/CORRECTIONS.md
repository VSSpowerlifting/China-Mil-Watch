# Correcting history on a shadow state branch

Status: **designed, built and rehearsed. Not applied.** Nothing here has run
against `shadow/singapore-mindef`. The remote branch is untouched.

## The two defects

Both are fixed prospectively in the extractor. Neither fix touches a record
already captured.

| Defect | Scale in the 59-record corpus |
|---|---|
| `visible_text()` knew six entities and not `&#x27;` | **84 occurrences in 29 bodies** |
| `document_title()` decoded nothing on its `og:title` branch | **5 occurrences in 4 titles** |
| `text/html` with no charset, so UTF-8 was decoded as ISO-8859-1 | **1125 damaged code points in 56 bodies; 26 in 11 titles** |

## Why the database is not updated

The state branch is hash-chained twice over, and both chains forbid it — checked
against the real branch, not assumed:

1. **The state chain.** Every ledger records `state_sha256_before` and
   `state_sha256_after`, the SHA-256 of the whole `shadow.db`. Singapore's chain
   runs unbroken across all 32. An in-place substitution touches 29 rows and
   moves the hash from `ef2d1e4f…` to `6de1f2f4…`, which matches no ledger; the
   next run's `before` assertion then fails and the only repair is rewriting
   append-only ledgers.

2. **The per-record hashes.** Every ledger records the `content_sha256` of each
   record it inserted. A rewritten body either leaves that hash describing text
   that no longer exists, or takes a value no ledger ever recorded.

So `shadow.db` is never opened for writing.

## Why not a refetch

Live pages move. Of the 29 records carrying `&#x27;`, **26 are still
byte-identical to capture and 3 have drifted** — `25jul26-nr`, `29aug26-nr`,
`9sep26-nr`, all in image captions and photo credits. Refetch-and-overwrite
would have rewritten those three with newer text while claiming to fix an
apostrophe.

## Where the overlay lives, and why not in `state/`

`state/corrections/` would have been the obvious place and is the wrong one.
The review kit's state-tree allowlist is `clock.json`, `shadow.db` and
`ledger/`, and an unrecognised file there is a refusal by design — the kit
rejects it outright. Forcing that allowlist open to admit our own file would
weaken the rule that protects the evidence.

The overlay therefore sits **beside** `state/`, as a sibling `corrections/`
directory. The state tree hash is unchanged, the existing Day-30 packet still
reproduces byte for byte (`4ad9a838…`, tree `ad97f27d…`, still `publishable:
yes`), and the allowlist is untouched.

## The transformations, and why each is justified

A global `latin-1 -> utf-8` round trip applied on faith would be wrong, and the
tool does not offer one. Bodies and titles came from different code paths and
need different rules.

**Bodies — entities.** Literal `&#x27;` → `'`. Not an unescape: the text has
already been through the old table, so unescaping again would double-decode.
For all 29 records, re-extracting the live page with the fixed extractor gives
exactly what this substitution gives. No page contains `&amp;#x27;`, the one
construction where the two would disagree, and `--emit` refuses outright if it
ever finds one.

**Titles — entities.** One `html.unescape`. The `og:title` branch decoded
nothing, so the stored value is the raw attribute verbatim and one pass is
exactly what the fixed extractor produces. Verified equal to re-extraction for
all 4. `--emit` refuses if a second pass would change anything.

**Bodies — charset.** Strip the orphan U+00C2, round-trip Latin-1 → UTF-8, then
re-collapse whitespace. The orphan needs explaining: a body went through
`visible_text`, which collapsed whitespace *after* the mis-decode, and Python's
`\s` matches U+0085 and U+00A0. So the second byte of every non-breaking space
was eaten and only a lone U+00C2 survived — **all 176 of them followed by
whitespace or end of string.** Removing it without re-collapsing leaves a
doubled space the correct extraction does not have.

**Titles — charset.** Round-trip only. Titles were never collapsed, no stored
title contains U+00C2 at all, and all 11 round-trip cleanly. They must *not* be
re-collapsed: `document_title` does not collapse, and doing so would destroy a
genuine double space that the live page also has.

## What cannot be corrected, and is refused rather than guessed

The same whitespace collapse ate a continuation byte *inside* CJK characters in
two Mandarin passages — `15aug26-speech` and `16sep26-speech` — where the
continuation byte was itself U+00A0. The original character is not recoverable
from stored text by any transformation. `--emit` refuses both and records why.
Re-capture is the only route, and that is an owner decision.

## Evidence

Every emitted record carries a tier:

- **`live-confirmed`** (93 records) — re-extracting the live page with the fixed
  extractor produces exactly this corrected value.
- **`intrinsic`** (7 records) — the live page has drifted, but the stored
  substring contains a C1 control (U+0080–U+009F), an orphaned lead byte before
  whitespace, or an undecoded entity reference. None of those can occur in
  legitimate reader-visible text, so the transformation is provably safe for
  that exact substring whatever the page says today.

Nothing is emitted on no evidence at all.

## What each correction file binds to

State commit · state-tree hash · database SHA-256 · ledger tip file, run id and
entry count · previous correction's hash · schema version · tool and version ·
collector commit · reason · timestamp. Per record: URL, field, occurrence count,
evidence tier, original field hash, corrected field hash, and the hashes of
every field the correction must be proven *not* to have touched.

Corrections compose: a second transformation on the same field is described
against the text the first one produces, not against raw storage.

## The corrected-view packet

`scripts/build_corrected_view_packet.py` produces a **separately named** packet
carrying both views, never one silently substituted:

- **ORIGINAL CAPTURE VIEW** — the bytes as collected; the evidence of record.
- **VERIFIED CORRECTED VIEW** — the same records read through the overlay,
  named by its digest.

It is marked `publishable: false` and states that it does not replace the
Day-30 packet. It fails closed: an unknown schema, an unapproved transformation
kind, a wrong database hash, a wrong state commit or tree, a mismatched original
field hash, a duplicate correction, a correction of a record this database does
not have, an incomplete manifest, unreadable JSON, a broken chain link or an
unknown evidence tier each stop the build. No partial packet is written.

## Rehearsal result

Against a clone of `shadow/singapore-mindef` at `be52cc125`:

| Claim | Result |
|---|---|
| original database byte-identical | `ef2d1e4f…` throughout; no WAL/SHM sidecars |
| state chain intact | `VERIFIED`; 32 ledgers, 0 breaks, `clock.json` unchanged |
| exact totals | 29/84 · 4/5 · 56/1125 · 11/26, with exactly 2 refusals |
| no unrelated content changes | changed bodies are exactly the union of the two body corrections; 57 bodies, 13 titles; every other record byte-identical |
| no residue | 0 `&#x27;` anywhere; charset damage only in the 2 refused bodies |
| idempotence | second materialisation identical; re-emitting finds nothing left |
| original evidence recoverable | all 59 stored values still the originals; the 84 entity sequences and every C1 byte still on disk |
| corrected view deterministic | two builds identical; overlay digest stable |
| all records distinct | 59 records, 59 distinct bodies |
| zero empty bodies | none |
| Day-30 packet unchanged | `4ad9a838…`, tree `ad97f27d…`, still `publishable: yes` |
| repeat packet builds | byte-identical apart from the declared build timestamp |

## 59-record review through the corrected view

**PASS 55 · AMBIGUOUS 4 · MISMATCH 0 · INACCESSIBLE 0.** Zero residual
entities. Every title, slug date, publication kind and identity matches.

The four exceptions, precisely:

- `15aug26-speech`, `16sep26-speech` — the two records whose CJK bytes the
  whitespace collapse destroyed. Core identity and prose match; the Mandarin
  passages remain damaged and are the reason these stay AMBIGUOUS.
- `29aug26-nr`, `9sep26-nr` — live-page drift in image captions and photo
  credits. Core identity and prose match; the stored body is not wrong, the
  page moved.

## What still blocks applying this

Owner approval. The overlay is built and rehearsed; it has not been written to
the state branch, and the prospective extractor fix is what stops new records
being corrupted in the meantime.
