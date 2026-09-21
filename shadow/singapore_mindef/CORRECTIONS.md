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
Re-capture is the only route.

### Both were re-fetched, and they did not get the same answer (2026-09-20)

Both pages were fetched compliantly and compared with the stored capture on
their **ASCII skeleton** — every character a mis-decode can neither invent nor
destroy — using `difflib` with `autojunk=False`.

| record | skeleton similarity | what the differences are | disposition |
|---|---|---|---|
| `15aug26-speech` | 0.998773 over 17125 vs 17095 chars | all six differing spans are `&#x27;`, the known entity defect, and nothing else | **recaptured** |
| `16sep26-speech` | 0.999161 over 10725 vs 10733 chars | one span, and it is prose: stored `makes us feel less insecure`, live `makes us feel insecure all the more` | **held** |

The second is the same document, and MINDEF has since revised a sentence in it
— correcting a line that contradicted itself. Recapturing it would substitute
text published after we captured, under a record whose `retrieved_at` says
2026-09-16. The stored text cannot be repaired and the live text is not what
was captured, so the record is held rather than guessed at or quietly dropped.

### `recaptured_current_source`

Schema `shadow-correction-overlay/3` adds one transformation kind. It is the
only one whose corrected value is **not** a function of the stored bytes, so it
is the only one that can disagree with the capture about what the document
said. It is constrained accordingly:

- the replacement travels inside the record and is checked against
  `value_sha256_after`, so a tampered replacement fails exactly as a tampered
  transformation would;
- it must carry `request_url`, `retrieved_at`, `http_status`,
  `response_bytes`, `raw_sha256`, `declared_encoding` and `encoding_source`,
  and `--emit` refuses a recapture missing any of them or returning anything
  but 200;
- `equivalent_to` is explicitly `null`. Every other kind states what a correct
  re-extraction would have produced. This one cannot, and must not pretend to;
- it uses the evidence tier `recaptured`, and the verifier requires that tier
  and that kind to imply each other in both directions — a derived correction
  may not launder itself as a fetch, and a fetch may not present itself as
  live-confirmed;
- the warning that this is a later recapture and not the original byte stream
  is stored verbatim on the file, on the transformation and on every record,
  and verification fails if any copy is altered.

## Holds: a record can be perfectly corrected and still unfit

A hold is not a correction and does not live among them. Corrections say what a
captured value should have been; a hold says the record must not leave the
shadow desk at all. Keeping them apart means the corrected view stays a
statement about text, and promotion stays a separate decision with its own
evidence.

`promotion_holds.json` sits beside `corrections/`, binds to the same database
hash, ledger tip and state commit, and is refused if it describes anything
else. Holding a record the database does not have is refused; a `hold_count`
that disagrees with the list is refused.

## Promotion, rehearsed

`scripts/promote_shadow_records.py` materialises **only the corrected view**
into a disposable production database. It refuses to run against the tracked
one. Every promoted row is accompanied by a `shadow_promotions` row naming the
capture it came from, the state commit and tree, the database hash, the overlay
digest and the holds digest, so a promoted record can always be traced back to
the byte stream it was built on and to the corrections applied to it. A record
with no capture provenance is refused rather than promoted with a null.

Rehearsed against the current tip: 59 records, 1 held, **58 promoted**. A second
run inserts 0 and reports 58 already present. Two fresh promotions produce
byte-identical rows. The shadow database is not written and grows no sidecars.

Refusals proven: no overlay at all; a tampered recapture replacement; an
overlay bound to another state commit; a correction file removed from the
chain; a holds file bound to another database; the tracked database as a
target; and a record without capture provenance. In every case the target
database is left with zero promoted rows.

### The overlay binds to a moving state, on purpose

The scheduled shadow run of 2026-09-20 (`35543956283`, shadow day 32,
`ok_all_duplicates`) appended a ledger entry and changed no records —
`shadow.db` is byte-identical — but it advanced the state commit, the state
tree, the ledger tip and the entry count. The overlay emitted against the
previous commit then fails **twenty** binding checks and promotion refuses.
That is correct: an overlay is a statement about one exact state, not about a
branch. The operational consequence is that the overlay must be re-emitted
against whatever commit is current at the moment of approval. Re-emitting is
mechanical and reproduces the same record and occurrence counts.

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

Owner approval, and nothing else technical. The overlay is built, verified and
rehearsed end to end through promotion; it has not been written to the state
branch, and the prospective extractor fix is what stops new records being
corrupted in the meantime.

The decision has five parts, and the corrected-view packet states them:

1. approve or decline promotion of the 58 promotable records;
2. approve or decline the 1 recaptured value — text fetched from the live page
   after capture, not the captured bytes;
3. confirm the 1 held record stays out;
4. confirm the 2 records accepted as originally captured, whose live pages have
   since drifted;
5. re-emit the overlay against the state commit current at the moment of
   approval.
