# Desk manifest reference

One JSON file per desk: `desks/<desk_id>/manifest.json`, validated by
`core/manifests.py`. JSON rather than YAML because the CI runner is Python 3.9
and JSON needs no third-party parser — a new dependency on the daily collection
path is not worth comment syntax.

Validation is strict. A manifest with an unknown enum, a missing identifier, a
duplicate slug or a dangling institution reference **fails loudly**, naming the
file, the record index and the permitted values. It is never silently ignored,
defaulted or coerced: a silently-dropped source is configured, appears in no
error, and contributes nothing — which is exactly what Xinhua Military did for
the life of the project.

## Structure

```json
{
  "manifest_version": 1,
  "desk":         { ... },
  "institutions": [ { ... } ],
  "sources":      [ { ... } ]
}
```

Any key beginning `_` (such as `_comment`) is ignored, which is how these files
carry prose.

## `desk`

| Field | Required | Notes |
|---|---|---|
| `desk_id` | yes | Stable identifier, also the directory name. |
| `display_name` | yes | |
| `jurisdiction_code` | yes | ISO 3166-1 alpha-2, or `XX` for a reference desk. |
| `default_timezone` | yes | IANA name, e.g. `Asia/Shanghai`. |
| `default_calendar` | no | `gregorian` (default), `hijri`, `solar_hijri`. |
| `supported_language_tags` | yes | Non-empty list of BCP 47 tags. Every source's tag must appear here. |
| `public_status` | yes | `legacy`, `shadow`, `public`, `paused`. |
| `active` | no | Default `true`. |

`public_status` meanings: **legacy** — already published under its own brand
(China today); **shadow** — private collection, no public surface (where a pilot
starts); **public** — published as part of the parent platform; **paused** —
configuration retained, collection stopped.

## `institutions`

| Field | Required | Notes |
|---|---|---|
| `institution_id` | yes | Unique across all desks. |
| `display_name` | yes | |
| `institution_type` | yes | `head_of_state`, `defense_ministry`, `armed_forces`, `service_branch`, `security_council`, `state_news_agency`, `state_linked_media`, `other`. |
| `name_original` | no | Name in the source language. |
| `parent_institution_id` | no | Must resolve within the same manifest. |
| `active_from` / `active_to` | no | ISO dates. |

Sources belong to institutions, not directly to desks, so that two publications
of the same body can be counted as one institutional voice.

## `sources`

| Field | Required | Notes |
|---|---|---|
| `slug` | yes | **Must match `sources.slug` in the database.** Unique across all desks. |
| `institution_id` | yes | Must be declared above. |
| `display_name`, `base_url` | yes | |
| `language_tag` | yes | BCP 47, and must be in the desk's `supported_language_tags`. |
| `access_method` | yes | `html`, `rss`, `api`, `telegram`, `manual`. |
| `authority_tier` | yes | `A`–`D`, see below. |
| `source_type` | yes | Free text, e.g. `armed_forces_newspaper`. |
| `originality` | yes | `original`, `mirror`, `syndicated`, `unknown`. |
| `adapter` | yes in practice | `module.path:ClassName`. Configuration, not a core import. |
| `expected_cadence_days` | no | Positive number. |
| `silence_threshold_days` | no | Days of silence before the health report escalates. |
| `enabled` | no | Default `true`. |
| `timezone`, `calendar` | no | Default to the desk's. |
| `active_from`, `active_to`, `listing_endpoints`, `article_url_patterns`, `notes` | no | |

A slug collision between desks is rejected: it would merge two countries'
collection history into one row.

## Authority tiers

Proximity to an institution's **authorized public position**. Not a truth,
reliability, accuracy or moral score — a Tier A document is not more likely to
be true than a Tier D one, it is more likely to represent what the institution
has formally decided to say.

| Tier | Definition | China desk |
|---|---|---|
| A | National leader, central military command, ministry, formal directive, law, authoritative doctrine | `mod_china` |
| B | Official armed-force or service media, official spokesperson, institutional public-affairs channel | `pla_daily`, `china_mil_online` |
| C | Official state news agency | `xinhua_mil` |
| D | State-linked or semi-official outlet | `global_times_mil` |

## Cadence and silence thresholds

`silence_threshold_days` must be measured from the **source's own** publishing
rate, never from our collection — our collection is the thing under test. MOD
China sits at 21 days, measured 2026-08-09 from 28 distinct publish dates across
three months on its own listings. A flat 7-day rule would mark a source that
genuinely publishes twice a month as dead every other week, and an alarm that
cries wolf is worse than no alarm (DECISION_LOG 2026-08-09 §8).

## Taxonomy

`desks/<desk_id>/taxonomy.json` holds that desk's topical labels. These are
desk-scoped by design: "Taiwan" and "South China Sea" have no meaning on another
desk. The universal genre vocabulary lives in `core/domain.py` and desks do not
extend it.

## Adding a source

1. Add the entry, including `adapter`.
2. Run the tests — `tests/test_manifests.py` validates structure.
3. `python -m migrations.cli --apply` syncs it into the database.
4. It appears in `scripts/source_health_report.py` from that moment, including
   `not_implemented` if the adapter is a stub.

Sync writes only the desk-metadata columns on an existing row; it can never
rename a live source or re-point its `base_url`.

**Adding a desk in another language is supported** as of migration 0005, which
removed the finite `CHECK (language IN ('zh','en'))` from the legacy
`sources.language` column. A source with `language_tag: "ru"` now syncs through
the normal path; the legacy column records the primary subtag (`ru`). Tag
validation stays in this layer, where errors name the file and field. See the
language compatibility policy in docs/SCHEMA_AND_MIGRATIONS.md.

No Russia desk exists — this is a capability, not a deployment.
