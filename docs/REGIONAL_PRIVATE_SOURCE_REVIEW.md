# Regional Intelligence Phase 3A — owner-reviewed evidence boundary

**Status:** experimental, offline and private; part of [#256](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/256). Stacked after [#254](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/254), which depends on [#253](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/253). Not wired to the existing Sunday writer, Friday task, Anthropic, SMTP, publication, or any official-source collector.

## Purpose and limits

The full-week regional inventory preserves metadata for all production-backed desks and
documents held/inaccessible country desks. It does **not** authorize source material
for a third-party model. Phase 3A introduces a *distinct* manual-review boundary
so an editor can verify a bounded set of production source pointers against
original publisher material, write concise analyst synopses, explicitly attest
the review, and prepare a private packet for a future thematic selector.

Signing a review says **only** that the owner has deliberately permitted
*manually authored, source-attributed private analyst synopses* to be considered
as private AI candidate evidence. It is NOT proof of publisher consent, a
perpetual copy license, perfect original-language accuracy, independent factual
corroboration, completeness of the weekly collection, any research-source
admission, or publication permission. Publisher versions are manually checked,
not attested by our archived SHA alone.

## Contract

`core/regional_reviewed_evidence.py` defines:

- `ipr-regional-source-review/1`: exact reporting week, full-week metadata
  digest, named reviewer, actual review date, private-model scope, and 1–20
  explicitly reviewed **numeric production** source decisions. Each decision
  pins ID, desk, HTTPS publisher URL, publication date and saved body SHA-256
  digest; includes human-attributed synopsis (65–650 chars) and the strongest
  accuracy limitation (30–350 chars).
- Each decision must positively record original-language, live publisher-version,
  and *not a quote/full-text* checks. An unscreened source may be chosen only
  after these **human** checks; records held by the inventory cannot enter.
- Sealing requires a separate, owner-controlled secret of at least 32 bytes,
  used with HMAC-SHA256 over stable canonical JSON. The secret is never put in
  the repository, source inventory, signature output or CLI stdout.
- `ipr-regional-private-model-candidates/1` is a **synopsis-only** packet.
  No raw article bodies, stored English translations or non-production Japan /
  Vietnam research synopses are included; no new issue number or provisional
  lead is selected. All public/delivery switches remain false.
- Verification requires a freshly generated read-only inventory with the
  complete reporting Saturday, Sunday success marker and zero preflight
  blockers; a stale digest, forged source ID, changed HMAC or partial week fails
  closed. Source metadata checksums prove only byte continuity in the stored
  corpus. The collector's *freshness marker* does not prove publisher silence.

The threat boundary is intentionally specific: **an owner-held secret +
manual source review** is an operator authorization, not a legal-rights or
external-content authenticity guarantee. It is inappropriate to give this key
to arbitrary CI jobs, LLMs, research packets or any publication tool.

## Operator sequence (local, never GitHub Actions)

1. Produce a fresh full-week inventory through
   `scripts/regional_weekly_inventory.py` (which writes its JSON outside the repo).
   Do not begin if its `production_preflight` is a hold.
2. Explicitly choose the reviewable production record IDs (not all records
   by default), then generate a **completely unsigned** private template.
   It fills in source IDs, dates, URLs and content pins but leaves all human
   review affirmations false and all analyst notes blank:

```bash
python scripts/regional_reviewed_evidence.py template \\
  --week-ending 2026-10-10 --as-of 2026-10-10 \\
  --review-local-day 2026-10-11 \\
  --ids 42,47 --reviewer "Human reviewer" \\
  --out /private/unsigned-source-review.json
```

   IDs `42,47` are **examples**, not a recommendation or assertion that they
   exist in the current week's eligible source inventory. Replace with actual
   numeric IDs from the fresh inventory; the template command refuses held,
   duplicate, nonproduction and unknown IDs.
3. Independently inspect each chosen original publisher article and the
   corresponding archived representation. Hand-write a source-attributed
   synopsis and limitations for each item. Only after conducting each review
   change its disposition to `privately_reviewed` and the three explicit
   human check booleans to `true`. Leave anything insufficiently verified
   unsigned and out of the review packet.
4. In a real interactive terminal, seal the completed template with the
   owner key:

```bash
python scripts/regional_reviewed_evidence.py seal \\
  --week-ending 2026-10-10 --as-of 2026-10-10 \\
  --review-local-day 2026-10-11 \\
  --review /private/completed-source-review.json \\
  --out /private/editor-signed-docket.json
```

5. Reinspect fresh SQLite data and verify a synopsis-only preview, using the
   **same** owner key without retaining it on disk:

```bash
python scripts/regional_reviewed_evidence.py preview \\
  --week-ending 2026-10-10 --as-of 2026-10-10 \\
  --review-local-day 2026-10-11 \\
  --review /private/editor-signed-docket.json \\
  --out /private/editor-synopsis-preview.json
```

Both operations refuse noninteractive execution and existing outputs. Their
files are created with mode 0600 outside the repository. `/private/` in these
examples represents an actual private directory that the operator supplies;
the scripts never create it or choose storage on behalf of the owner.

The October 11 example will **not** work until the actual October 11
same-day collection-success marker is present. That is deliberate: before then
this phase can only pass synthetic tests.

## What remains before automatic theme proposals

- Design a separately controlled no-send model candidate selector which
  consumes this exact review scope and must not ingest unreviewed source bodies.
- Allow Japan/Vietnam verified shadow candidates only through their **own**
  exact-source version and source-use gates (#200), not by forging numeric IDs.
- Compare 0–3 proposals and an explicit abstention, vet citations and source
  limitations, and keep all model text untrusted.
- Expose a private editorial preview for Ben and pass one approved thematic
  focus to the Sunday writer only in a future PR; preserve existing full-text,
  cross-desk exception, and human Brief publication conditions.

There is no public journal, timeline record, automated topic adjudication,
editor mail or source-rights assertion in this phase.
