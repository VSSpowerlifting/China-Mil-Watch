# Regional Topic Taxonomy v1

## Purpose

Indo-Pacific Record needs one subject layer that can describe records from
different country desks without pretending those desks publish the same kinds of
documents or use the same political vocabulary.

Version 1 establishes that layer. It does **not** classify the corpus.

The controlled vocabulary is
`taxonomy/regional_topics.v1.json`. The loader and assignment contract live in
`core/topics.py`.

## Three different classification axes

They must remain separate.

1. **Document genre** — country-neutral form such as
   `official_statement`, `exercise_operational_report`, or
   `procurement_industry`. Defined in `core/domain.py`.
2. **Desk-specific analytical labels** — a desk's inherited or local analytical
   vocabulary. The China Desk's 14 `article_categories` are the current
   example. They remain exactly what they already mean in the China pipeline.
3. **Regional topics** — the new cross-desk subject vocabulary. A Singapore
   release, Chinese ministry statement, Philippine military release, or Vietnam
   ministry record can carry the same regional topic when the underlying
   subject is genuinely the same.

Similarity between a legacy desk label and a regional topic does not create an
automatic mapping. For example, China `taiwan` and regional
`taiwan_strait` are deliberately different identifiers. A future migration or
classifier must earn that mapping record by record or through a separately
reviewed rule.

## Version 1 vocabulary

Six groups organize nineteen multi-label topics:

- **Operations & Posture:** Military Exercises; Force Posture & Basing;
  Maritime Security; Gray-Zone & Coast Guard.
- **Defense Diplomacy & Partnerships:** Defense Diplomacy; Alliances &
  Security Partnerships.
- **Capabilities & Defense Industry:** Procurement & Acquisition; Defense
  Industry; Emerging Technology; Nuclear Forces & Deterrence; Cyber &
  Information Operations; Space Security.
- **Regional Flashpoints:** Taiwan Strait; South China Sea; East China Sea.
- **Economic Security & Statecraft:** Economic Security; Export Controls &
  Sanctions; Critical Minerals & Supply Chains.
- **Doctrine & Strategy:** Doctrine & Strategy.

The JSON file is authoritative for slugs, display names, descriptions, and
scope notes. Code must load it rather than copy the vocabulary into prompts or
UI constants.

## Record identity

Topic attachment uses the stable triple:

`(desk_id, source_slug, canonical_url)`

rather than a production `articles.id`.

That is intentional. Production and shadow desks use different database
schemas, while source URL identity is already preserved across both. A topic
assignment therefore does not require moving a shadow record into production or
making shadow tables mimic the production corpus.

## Storage contract

Version 1 does **not** register a production database migration and does not
modify `pla_watch.db`. `core.topics.ensure_topic_store()` is the explicit,
storage-neutral opt-in path: it creates an empty `record_topics` table in a
writable SQLite store, or validates an existing compatible store and refuses a
partial schema.

The table has no foreign key to `articles` or a shadow record table. Its
integrity comes from the explicit record identity plus taxonomy validation.
This avoids coupling the regional layer to one desk's storage model.

When production adoption is authorized, it must be a separate schema phase:
add a numbered migration that installs this same contract, apply it to the
tracked production database in that same change, prove existing record rows are
preserved, and only then permit production assignments. Shadow stores follow
the same explicit opt-in boundary.

This foundation creates **no assignment rows** and changes no production or
shadow database. Existing articles, `article_categories`, analyses, shadow
state, and public output are unchanged.

## Assignment provenance

Every assignment records:

- taxonomy version;
- topic slug;
- stable record identity;
- assignment method: `human`, `rule`, or `model`;
- `assigned_by`, naming the human review, rule version, or model/classifier;
- UTC assignment time;
- optional evidence;
- optional confidence for rule/model assignments.

Human assignments cannot carry synthetic confidence scores.

The API is idempotent for an identical repeat. If the same record/topic key
already exists with different provenance, it raises instead of overwriting the
first evidence silently.

## What v1 explicitly does not do

- no bulk classification;
- no LLM prompt or classifier;
- no automatic mapping from China categories;
- no UI, topic page, browse filter, or public count;
- no production record rewrite;
- no shadow-state mutation;
- no entity or relationship graph;
- no event timeline or dossier generation.

Those are later phases after the storage and vocabulary contract has survived
review.

## Next phase

The next useful step after v1 lands is a **small reviewed classification
pilot**, not a corpus-wide model run.

Use a bounded set of records spanning at least two desks and several topic
families. Compare human labels against any proposed deterministic or model
classifier, record ambiguous cases, and revise the taxonomy before assigning at
scale. Only after that should the public renderer or search index consume
regional topics.
