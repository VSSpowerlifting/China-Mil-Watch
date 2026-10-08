# Regional Topic Taxonomy v1 classification pilot

This is a frozen, source-grounded review sample, not approved classification.
`ledger.json` is the canonical pilot artifact. `LEDGER.md` is its reproducible
human review rendering. Findings are in
[`docs/REGIONAL_TOPIC_PILOT.md`](../../docs/REGIONAL_TOPIC_PILOT.md).

## Method

Selection is purposive, not random or proportional: 60 records, comprising
24 China and 12 Singapore production records plus 5 Japan, 6 Vietnam,
7 Philippines, 3 Indonesia and 3 Korea shadow records. It tests subject families,
likely overlaps, and abstention boundaries. It cannot estimate corpus prevalence
or classifier accuracy. China Military Online and Global Times are not represented
in the selected records; source-level generalization is therefore limited. The production candidate window was source-stated dates
from 2026-09-01 onward at main `4efa9c086f70ae3fe4d24720754f323c8e393ebf`.
China selections span three production sources (19 PLA Daily, four MOD China
and one Xinhua), include local-label
counterexamples, and include a China-source report about Russia as a regional
scope control. Singapore includes acquisition, diplomacy, exercises, a broad
strategic speech, personnel/social material and one empty-body infographic.

Japan includes **all five stored body-bearing records** at its pin, four of
which concern facility agreements and one disaster-relief expenditure. These
are PDF-derived texts, not a proxy for Japan's inaccessible HTML estate.
Vietnam includes **all six stored current ministry versions** across MPS foreign
affairs and the two MOIT families. The body/title are joined from `shadow_versions`
using `current_content_sha256`, preserving the versioned storage model. Vietnam's
Government News route is excluded. Other desks supply positive and negative
controls from available body-bearing records. Philippine NSC has zero stored
records at `feb118268faa7504ef4aa694636f34b51f6bae87`; AFP supplies the Philippine
sample. The US Indo-Pacific/DVIDS desk is excluded by the owner's scope.

The exact selected identities, source commit, database Git blob, row locator,
original title, source-stated date, original-body SHA-256, stored content hash,
existing desk-local categories and exact text offsets are frozen in the ledger.
The selection manifest is the ordered record list itself: replay selects these
identities, never whatever happens to be newest on a branch. Full source text is
retained in the pinned stores; only short relevant excerpts are copied here.
Offsets count Unicode characters in the preserved `text_original`, not bytes or
PDF page coordinates. Markdown display trims line-end whitespace; the canonical
JSON excerpts preserve it exactly for replay. No translation is stored as authoritative source text.
English rationales are Codex interpretations requiring original-language review.

Codex proposed labels through one-time reading of the selected records. There is
no classifier, model API, keyword assignment rule, or China-category crosswalk.
Vocabulary scope notes govern proposals: subject must be substantive; affiliations,
source sections, incidental geography, or local categories alone are insufficient.
Multi-label topics are supported. An empty proposal list is an explicit abstention
with a reason, including one body-unavailable record. Source assertions are evidence
of what the source published, not independent confirmation of the described event
or contested sovereignty claims.

Every record remains `status: provisional`, `review_state: pending`, with named
Codex provenance. These objects deliberately are **not** `TopicAssignment` rows:
no invented human approval or attachment method is supplied. Source locators and
excerpts accompany every proposed topic, and scope/overlap review questions are
kept separate from the topic proposals. Repeated reports of the same event remain
separate records: P02/P15, P27/P28, and P51/P52 are correlated examples. Distribution
counts records, not unique incidents or independent observations.

## Reproduce and verify

From the repository root (Python 3.9+; stdlib plus repository code):

```sh
python3 scripts/topic_pilot.py
python3 scripts/topic_pilot.py --report > /tmp/ipr-topic-ledger.md
python3 -m unittest tests.test_topic_pilot tests.test_regional_topics -v
```

The default checks never access a database or network. They validate taxonomy
version/hash, record identities, uniqueness, layer separation, provisional state,
known/nonduplicate topics, abstention consistency and excerpt locators. The tests
also verify exact Markdown regeneration, tamper refusal and byte preservation.

Full replay needs the pinned Git objects. Fetch the branches named by `origins`
from the existing repository, without checking out or writing their state:

```sh
git fetch origin main shadow/jp-mod shadow/vietnam-mps-foreign-affairs \
  shadow/vietnam-moit-energy shadow/vietnam-moit-foundational-industry \
  shadow/ph-afp shadow/indonesia-kemhan shadow/korea-policy-briefing
python3 scripts/topic_pilot.py --verify-sources
```

Advancing branch tips does not alter ledger pins. If old commits are absent,
fetch each exact `origins.*.commit` explicitly from origin. Replay refuses missing
objects; it never substitutes a new snapshot or fetches on its own. It reads each
pinned database Git blob into a temporary immutable SQLite copy, verifies metadata,
versioned bodies, hashes, all excerpt slices, and production desk categories, then
checks the input bytes and absence of WAL/SHM sidecars. No canonical database is
opened by SQLite. No topic store is created or attachment API called.

Production replay tests use the exact pinned blob from the checkout or Git object
store. A future shallow checkout lacking that historical blob explicitly skips
those source-replay tests; portable integrity/report tests still execute. The
all-desk CLI replay is required evidence for this pilot and future ledger edits.
No skipped historical replay is proof of source parity.

## Human review and next boundary

Review the original excerpt and pinned full text for each proposal. Record accept,
reject or revise decisions and the actual reviewer/date in a separately reviewed
ledger revision; do not convert `pending` into approval without that review.
Resolve scope flags before treating proposals as a gold set. Reviewers should also
check omitted labels, especially broad speeches, and preserve abstentions rather
than forcing a topic on every record. Independent second review and disagreements
are needed to measure agreement; this pilot alone supplies no such metric.

Any vocabulary change requires evidence-linked review and an explicit version/
compatibility decision. No identifiers are silently renamed here. Any eventual
production migration or assignment application is a separate authorized phase;
this ledger is not an import queue. Neither human review nor this pilot promotes
shadow records, changes desk status, or authorizes production classification.
