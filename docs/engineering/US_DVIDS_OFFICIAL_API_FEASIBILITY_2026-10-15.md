# DVIDS official USINDOPACOM news API — credential-gated source feasibility

Status: **source-free code only; no authorized live DVIDS API collection, archive
admission or public publishing yet**.

DVIDS is the U.S. Department of Defense's distribution service for media,
including some news releases. It is **not** the same publisher as United States
Indo-Pacific Command and cannot replace PACOM's blocked first-party statements.

Official API:
- https://api.dvidshub.net/docs/search_api
- https://api.dvidshub.net/docs/tos
- https://api.dvidshub.net/docs
- https://api.dvidshub.net/ (DVIDS app/API key registration)

The API requires a **DVIDS-issued key for this IPR integration**. Its
documented parameters permit USINDOPACOM combatant-command tagging,
type=news, twenty bounded first-page results and descending publisher
publication dates. The collection date is NOT the producer's shoot date.
Never bypass API key requirements, blocklists, origin restrictions, quotas,
geographical restrictions, DVIDS branding or content removals; no HTML scrape
or proxy substitution is implemented.

Only an official canonical news URL, normalized publication date,
fixed source identity and neutral issuer/publisher attribution are eligible
for private scratch staging. The prototype rejects any image/video/audio
item, off-host URL, identity mismatch, missing or implausible date, unbounded
response or changed API schema. It **discards** publisher title, description,
media URL, caption, body, image, video, translation and analysis. DVIDS items
are never reclassified as direct PACOM command statements. The output is a new
0600 JSON scratch file outside the tracked repository, not SQLite, Git
source evidence or GitHub Pages. The private file is never uploaded.

Do NOT run the manual API check with a guessed key or another client's key.

## Owner credential activation (after source-free review)

1. Register an application on the [official DVIDS API site](https://api.dvidshub.net/),
   using IPR's real identity and domain. Agree to source terms only if acceptable.
2. Obtain the DVIDS-issued **search API** key, ensuring DVIDS has authorized
   use from GitHub Actions/server-to-server or the IPR application domain.
3. In GitHub repository Settings > Secrets and variables > Actions, create
   **repository secret DVIDS_API_KEY**. Never paste it into chat, an issue or a PR.
4. After the exact-head tests and source permissions are reviewed and this PR
   is merged, manually dispatch "DVIDS — Authorized USINDOPACOM News API Metadata
   Rehearsal", checking the explicit one-time authorization input.
5. Confirm legitimate API access and the exact normalized neutral metadata
   fields. A 403 is a valid HOLD and must not be bypassed. An empty/changed
   source is a HOLD, not an invented record.

## Future qualification — separate PR required

The DVIDS terms require API result cache updating/removal when publisher
metadata is changed or an asset is withdrawn. Therefore a live collector must
handle removals, verified update reconciliation, idempotency, lawful use,
publisher attribution, source/run immutability, rate limits and human review.
Only then may a separate authorized metadata-only production importer and
U.S. Desk conditional renderer be considered. No scheduled trigger, evidence
streak, live source or original-media rights are created by this feasibility PR.

The existing USCC/Treasury live feeds and nine static PACOM references are
untouched; direct PACOM remains access-blocked.
