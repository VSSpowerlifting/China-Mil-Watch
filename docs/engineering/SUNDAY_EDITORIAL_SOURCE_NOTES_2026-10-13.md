# Sunday IPR Briefs — ordinary source-linked contributions

**Engineering scope:** Expand the *existing* private Sunday source-note intake. This is an editorial research path, not a country desk launch, source reuse license, or approval to send email. No extra public badges, statuses, or experimental article category are added.

## What changed

`core/brief_editorial_evidence.py` now accepts the already-supported Japan MOD / Vietnam MPS notes plus strict original-publisher link identities for:

| Desk | `source_name` | Allowed first-party URL shape | Typed citation |
| --- | --- | --- | --- |
| Japan | `Japan Coast Guard` | `https://www.kaiho.mlit.go.jp/e/topics_archive/articleNNN.html` | `JP-W42-01` |
| Philippines | `Armed Forces of the Philippines` | `https://www.afp.mil.ph/news/original-article-slug` | `PH-AFP-W42-01` |
| Indonesia | `Indonesia Ministry of Defense` | `https://www.kemhan.go.id/YYYY/MM/DD/original-article-slug.html` | `ID-KEMHAN-W42-01` |

The table shows URI *shapes*, **not real claimed articles**, and does not make listed URLs sufficient evidence. Existing Japan MOD and Vietnam MPS IDs retain their historical rules. New Philippines and Indonesia IDs embed the reporting Saturday's ISO week; they never become numeric production IDs.

A source can be considered **without** waiting for its entire collector to pass Day 7/14/30, be admitted to the archive, or preserve complete publisher article bodies. Use `source_kind=official-publisher-page-reviewed-for-research` with null `state_commit`, `source_content_sha256`, and `hash_rule` when there is no qualified immutable collector original. **Do not invent a captured original or source hash.**

## Smallest responsible operator procedure

1. Identify a development with a genuine first-party publisher article dated within the Sunday–Saturday reporting week. Open the **specific** source, verify date, title, issuing organization, original language, and what actually occurred versus what was only planned. Record the material limitations and independently write a concise attributed synopsis. If the source cannot be independently inspected, omit it; do not mark it verified.
2. Confirm the particular intended use is permitted: linking/citation, independent synopsis for human editorial review, and—**separately**—transmission of that synopsis to an external model. Publisher terms, third-party material and translation rights differ. Do not assume source rights from the host suffix or the existence of a shadow capture. Respect the separate Vietnamese MOIT written-consent hold.
3. Prepare a **private** exact-Saturday JSON in the existing `ipr-private-drafting-evidence/1` schema (see the older source packet under `research/briefs_editorial_evidence/` for field names and limits). Use exact source URL, original title, date, one short analyst synopsis, 1–4 explicit caveats and 1–3 existing topic tags. `status` stays `unapproved-source-linked-editorial-candidate`; `copy_scope` stays `private-model-drafting-only-no-source-body` as a boundary, **not** a substitute for an actual use-rights decision. No copied bodies, attachments, maps, images, or source text are packaged.
4. Load with `load_editorial_evidence(saturday, saturday, directory=private_packet_directory)`. Reject a wrong-week, duplicate, malformed, unsupported or out-of-scope source. Put the JSON outside public site output and Actions artifacts.
5. Use the existing **manual no-send** handoff only after satisfying the normal live-source production scaffold prerequisites. With a ready scratch scaffold and explicitly authorized model call:
   ```sh
   python -m scripts.sunday_editorial_handoff \
     --sidecar /private/ipr-sunday-scaffold.json \
     --out /private/ipr-editorial-preview.txt \
     --write-automatic --full-week --include-research \
     --research-packet /private/2026-10-17.json --as-of 2026-10-17
   ```
   No `--send` or `--preview-to-owner`. This is deliberately **not** wired into the scheduled Sunday job in this PR. The schedule retains its independently audited Vietnam refresh and Japan offer controls.
6. The model may select a genuine regional theme or omit all research notes. Dylan/Ben check each actually cited original and factual claim before publication. Keep internal capture/pending distinctions out of public prose; ordinary official-source attribution is sufficient. No desk production status, archive count, article ID or publisher approval is inferred.

## Explicitly unchanged

- No new production collectors, shadow schedules, source-admission or 7/14/30 changes.
- No changes to `desks/registry.json`, SQLite, site templates, tracked `output/`, Pages, Brief numbering or public status labels.
- No scheduled Sunday SMTP change, automatic model dispatch, owner-signature substitution or public publication.
- No blanket copyright exception, model-use authorization, or fact-review waiver.
- Existing Sunday production desk minimum and one-manuscript editorial standards remain intact.

## Verification

```sh
python -m unittest tests.test_briefs_editorial_evidence tests.test_briefs_editorial_multidesk -q
```

Follow with exact-head full offline CI. Additional desk material can join the scheduled path only after a separate, specifically reviewed no-send runner rehearsal confirms the source-use and custody boundaries and existing at-most-one-send protection. The goal is to **reuse** the normal Brief, not build a separate regional product.

Refs: #200, #251, #271, #373.
