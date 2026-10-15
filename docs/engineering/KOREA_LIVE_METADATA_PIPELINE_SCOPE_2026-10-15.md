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

## Next production changes (not implemented by the schema PR)

1. Secure runner authenticates the actual immutable Korea shadow state and
   replays per-source collection proofs. Production access to original HWPX
   remains restricted to the processing runner; only validated metadata passes
   to the public repository.
2. Idempotent transaction imports newly verified MND references into this
   `held` table without silently replacing previously published source
   versions, asserting a fictional source-success day, or widening to DAPA.
3. **Standing owner policy decision still required:** may new future MND
   official URLs + issuer + dates (and, separately, original Korean titles)
   become `official_link_only` **automatically** after exact-source checks,
   without per-record human signatures? Existing 14-link signoff alone cannot
   justify automatically approving future source versions.
4. After owner-approved policy and tests, the publisher reads only
   `official_link_only` metadata and writes **only** Korea's page. No
   `./output` directory reupload, no rerender of China or Briefs. Check
   release checksum, observed IDs, lack of media/body, and rollback.
5. Demonstrate *one genuine new original* moving from new collection through
   capture replay, production database, and Pages. Verify record and GitHub
   Pages tip independently before changing Korea's public status/registry.
   Keep report of scheduling failures and collection gaps, rather than
   converting them into passing days.

Separate future releases are required for original document reproduction,
Korean title/license attribution scope, article analysis, model handling and
photography. The portal's observed KOGL Type 1 **text-only** badge on the
first fourteen releases is not automatic proof of rights on future pages or
embedded media.

## Exact user input needed

A single editorial policy decision approving automatic link/date/issuer-only
admission of **new, future** MND / Korea Policy Briefing references (or
requiring human review before public display). Also decide whether the
original Korean title is included when the *specific new page* retains a
matching copyright notice. The conservative default until approval is
private intake and HOLD, not auto publication.

No new paid infrastructure is required for this schema stage. Reuse GitHub
Actions and SQLite, with separate review of runner write credentials,
private-custody access, and atomic Pages publishing before live activation.
