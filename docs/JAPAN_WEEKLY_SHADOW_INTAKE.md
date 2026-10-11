# Japan MOD — recurring shadow evidence candidate intake

**Purpose:** provide a durable, version-pinned metadata inventory for the next phase of automated Sunday Brief research, not a parallel Japan production collector and not the editorial manuscript generator.

## Why this is needed

The first unified Sunday research packet is frozen to the October 10, 2026 reporting week. It includes verified-format short notes about Japan MOD and Vietnam MPS, but future Sundays cannot safely recycle those notes. The existing `shadow/jp-mod` repository does continue collecting the ministry's **Japanese RSS feed** and the accessible PDF subset; original HTML is often challenge-gated. Newly discovered information must be independently inventoried, source-verified, summarized for private model use where permitted, and later human reviewed before public dissemination. Simply copying an old country packet would fabricate source continuity.

## What the proposed weekly intake actually does

`scripts/japan_weekly_shadow_intake.py` reads a **specific immutable Git commit** from the isolated `shadow/jp-mod` branch. The read-only Actions workflow requires a full 40-character state SHA for manual runs and verifies branch ancestry before any inspection; the PR proof uses the currently present state head but reports the resolved exact SHA.

The script reads `state/shadow.db` through `git cat-file`, verifies the blob's exact SHA-1 Git object identity, opens an isolated temporary SQLite copy in immutable/read-only mode, and runs SQLite integrity checking. It selects only source records published within the named Sunday–Saturday week through the explicitly declared reporting-week cutoff.

It emits **metadata only** for at most 40 full-text Japan MOD records per reporting window: original headline, official source URL, publication date, issuing feed, publication class, language, first-seen collector run, text-character count, SHA-256 of stored original Japanese text, and observed source capture digest. Every extracted original's text digest is recalculated from the real archived text and checked against SQLite. The original Japanese body is **never exported**, fed to the model, logged or uploaded. Unexpected URLs, issuers, languages, dates, unrecognized sources, changed hashes, Git-object corruption or an over-cap week fail closed.

The companion `shadow_unretrieved` table is summarized **by gap reason**, including challenge-gated inaccessible originals. This prevents a quiet week with few retrievable PDFs being reported as publisher silence. The tool explicitly states that the Japan MOD English press estate and Joint Staff are **not collected**, that source use is not approved, and that original PDF bytes have not been retained for full-PDF comparison.

## This is a staging inbox, not a new source of model claims

Its candidate records always include:

- `eligible_for_automatic_model_drafting=false`
- `human_language_and_rights_review_complete=false`
- `production_eligible=false`
- `weekly_edition_approved=false`
- `known_publication_coverage_incomplete=true`

No automatic research synopsis or synthetic English quotation is created from source titles. Before a future source can reach the Sunday **one-theme AI writer**, a separately reviewed translation/source-use policy and private fact-capsule generator must be built. That stage should consume source bodies only where explicitly authorized, produce bounded attributed synopses with exact SHA/URL/date provenance, and preserve the independent human publication gate. The Sunday model can then synthesize one article while Dylan edits it, instead of demanding that he combine disconnected national supplements. This workflow does **not** pretend to complete that later stage.

## First operational use

The PR Actions check reports the week ending **2026-10-10** with an October 8 source cutoff from the current archived Japan state. That is an **interim, incomplete reporting-week view** and must not imply the October 10 source set has been fully collected. A future manual run accepts the exact `shadow/jp-mod` head SHA, Saturday ending date, and source cutoff within the reporting week, and produces a metadata-only review artifact. No cron means no unreviewed automatic model consumption.

The current single October 5 Japanese MOD agreement record remains identifiable by its URL and SHA-256, while `shadow_unretrieved` counts disclose access failures. [PR #242](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/242) separately pins the initial October 10 manuscript's three Japan source citations and their original version evidence; the two PRs do not mutate one another.

**Scope:** no new GitHub token writes, no state branch push, no PDF downloads, no publisher-access bypass, no production database or web renderer update, no Anthropic model call, and no email to Dylan.

### Explicitly incomplete interim proofs

The initial PR Actions run uses the actual **October 8** archived source-state snapshot against the week ending October 10. The report marks `full_reporting_week_elapsed_at_cutoff=false` and `source_snapshot_completeness_attested=false`. A later Saturday-cutoff report may set the first flag true but the second **remains false**: the ministry's challenged HTML and uncollected service pages never permit a claim of exhaustive publication coverage. The audit cannot infer a publishing silence from missing retrievable originals.
