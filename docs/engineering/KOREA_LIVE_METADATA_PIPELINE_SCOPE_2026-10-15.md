# Korea Desk: typed live-source metadata before automatic publication

October 15, 2026. The owner wants newly collected official MND records in the
live database and automatically visible on the public Korea page. The current
shadow collector and fixed public 14-link directory do not do that.

## First engineering increment: migration 0008

Adds a **separate, empty** `korea_official_source_records` table to the existing
IPR SQLite migration framework. It is not a claim of live production activation:
no collector is switched, no source text is copied, no public page changes,
and no signed-review flag is auto-granted. Existing article IDs, original
Chinese corpus, source metadata, Brief trails and public Pages are untouched.

Only these data classes can enter this typed metadata store:
- fixed MND / Korea Policy Briefing `korea-policy:#########` identity;
- exact canonical HTTPS government outbound URL and portal-stated date;
- Git/source DB/candidate digest, original Korean title/text SHA, official
  publisher HTML and HWPX SHA;
- fixed Korean language, syndicated status, authority tier B;
- explicit `held` or `official_link_only` state, with timestamped admission
  and release evidence for the latter.

**No title/body or HWPX, document copy, photo, translation, summary, AI result,
reviewer identity, signing secret, or personal data is held in this table.**
Existing `articles` IDs remain separate, because a verified official URL does
not constitute an edited or machine-analyzed research article.

## Operational pipeline built on this branch (not deployed until CI and merge)

1. Workflow `.github/workflows/korea_verified_official_link_production.yml`
   clones the exact existing MND shadow Git branch after collection or on a
   daily retry, and `scripts/stage_korea_production_candidates.py` reconstructs
   its source ancestry and HWPX/HTML/text bytes and hashes. The runner holds
   originals only temporarily; only structured metadata enters production.
2. `core/korea_official_metadata_admission.py` admits eligible verified MND
   references into the new live SQLite metadata table under an explicit
   version-locked, owner-approved standing policy. Disputed source 156785161
   stays excluded, repeated records are idempotent, and changed versions are
   held rather than overwritten.
3. **Standing policy APPROVED by owner on October 15, 2026:** automatically
   publish new source-verified MND official URL, portal date, issuing ministry,
   republisher and neutral numerical ID. No per-record human signature is
   required for these factual link-only fields. The owner expressly excludes
   original Korean headlines, article bodies, imagery, translation, analysis,
   model and email use. The exact checked policy is recorded in
   `config/korea_official_link_automatic_admission.json`.
4. The renderer reads only `official_link_only` metadata and appends new
   verified references in a clearly differentiated page section. Existing
   frozen fourteen links remain, without duplicated entries. The workflow
   stages only `pla_watch.db` and `output/korea.html` on main, then updates
   only `korea.html` on Pages. A render may regenerate unrelated output
   locally, but the workflow neither stages nor uploads those assets.
5. **Still required before calling the desk genuinely live:** a green exact-
   head full test suite, merge into main, one real-source workflow run showing
   verified admission to the actual DB, successful Pages file-only update,
   and independent comparison of `main:pla_watch.db`, `main:output/korea.html`
   and `gh-pages:korea.html`. The workflow must fail safely on missing or
   stale shadow evidence, concurrent main changes and page overwrite races.

Separate future releases are required for original document reproduction,
Korean title/license attribution scope, article analysis, model handling and
photography. The portal's observed KOGL Type 1 **text-only** badge on the
first fourteen releases is not automatic proof of rights on future pages or
embedded media.

## User decision received

The owner expressly approved recurring publication of new government MND
URL/date/issuer metadata after exact-source checks, **without individual
human review**. Original Korean titles are excluded from the automatic path
regardless of future publisher copyright markings. The known chronology
exception and unverified original-source state are always held.

No new paid infrastructure is required for this schema stage. Reuse GitHub
Actions and SQLite, with separate review of runner write credentials,
private-custody access, and atomic Pages publishing before live activation.
