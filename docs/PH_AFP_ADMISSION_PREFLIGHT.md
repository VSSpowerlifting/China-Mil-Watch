# Philippine AFP admission preflight — provenance first, no automatic promotion

This is the next step after the October 7–8 AFP shadow collection successes and merged review/reliability infrastructure (#178, #183, #185). It joins the separate **seven-successive-schedule-day evidence** and **original API response human-review** contracts into one **read-only operator report**. It is not a new collector, weekly AI-writer feeder, unpublished-source export or desk activation mechanism.

## Current evidence and calendar

- AFP scheduled shadow day zero: **2026-10-07**, run `37631681338-1`; 13 archived original English text records, all 13 queued unsigned for inspection.
- AFP day one: **2026-10-08**, run `37788547061-1`; 5 additional full-text records, 13 correctly recognized duplicates, 0 observed collector failures. Five new originals are queued unsigned.
- The earliest seventh scheduled *logical* date is **2026-10-13**, assuming seven distinct successful scheduled slots. That is after the **2026-10-11** Sunday editorial draft. No script should backdate success by counting multiple reruns, manual rehearsals, elapsed days, or NSC quiet runs.
- **Production graduation is a different, later milestone.** `docs/DESK_STRENGTH_CRITERIA.md` C13 requires **30 consecutive collecting days**, independent **Day-7, Day-14 and Day-30 human checkpoint reviews**, all C1–C12 checks passing, and owner approval in the decision log. The earliest possible 30th scheduled date, if every Oct 7–Nov 5 logical date succeeds, is **2026-11-05**. This is an earliest date, not an activation forecast.
- National Security Council remains an independent shadow source (`shadow/ph-nsc`), not an AFP source or surrogate verification.

## Run an evidence-only preflight

Explicitly fetch the isolated `shadow/ph-afp` branch in an authorized checkout first. The script itself neither fetches the network nor follows moving refs. Supply its **literal 40-character current historical commit** and the desired UTC reporting date:

```shell
python3 -m scripts.assess_ph_afp_activation \
  --state-repo /path/to/checkout-containing-shadow-state \
  --state-commit LITERAL_40_CHARACTER_GIT_COMMIT \
  --as-of 2026-10-08 > /tmp/ph-afp-admission-readiness.json

```

The report identifies each of seven dates as successful-evidence, future, missing, ambiguous or invalid, and separately marks the original-source reviews that remain missing. A pending report exits successfully because absence of evidence is an ordinary status, **not a fabricated collector failure or permission to activate**. Corrupt/inconsistent source evidence fails with a nonzero exit.

## Human review decisions, when genuinely completed

The merged Day-0 review queue (`scripts/prepare_ph_afp_day0_review.py`) is an orientation packet, but **this preflight accepts only the newer per-run packet schema**. Generate both the October 7 and subsequent insertion-batch decisions using `scripts/prepare_ph_afp_run_review.py packet` against the corresponding exact historical commit, and validate them with that same script before admission preflight. Each independently reviewed original must have genuine source-specific fidelity checks, attribution, timestamp, complete-body comparison and capture provenance; the `verified`/`hold` distinction is retained. An operator's typed reviewer name is **not** independently authenticated by software. Never invent a human attestation.

Use a local, access-controlled manifest (not committed into `main`, `shadow/`, or `output/`) to bind a submitted review file to its own **historical state commit**, not the later latest commit. Example syntax **only**, with no claim that these files or decisions exist:

```json
{
  "protocol": "ipr_ph_afp_activation_review_manifest_v1",
  "reviews": [
    {"run_id": "37631681338-1", "state_commit": "492001f34ba6176169b6acc96a237f05592a3395", "file": "oct07-reviewed.json"},
    {"run_id": "37788547061-1", "state_commit": "c668790ce3be88b08b3300b945bad58589b3a5b1", "file": "oct08-reviewed.json"}
  ]
}

```

Only supply this manifest once the exact review packets have actually been read and completed. Then run:

```shell
python3 -m scripts.assess_ph_afp_activation \
  --state-repo /path/to/checkout-containing-both-historical-commits \
  --state-commit LITERAL_LATEST_HISTORICAL_COMMIT \
  --as-of 2026-10-13 \
  --manifest /secure/ph-afp-manifest.json \
  --review-dir /secure/ph-afp-review-packets

```

Any review with `hold` does not pass the review gate. Altered API bytes, missing records, wrong source/run/commit, incomplete checks, duplicate files, attempts to inject a review for a failed/unscheduled run, or unreadable original captures fail closed. The JSON report deliberately contains neither raw AFP body text nor reviewer private notes.

## What must happen after the preflight

Even if all seven scheduled slots and the run-specific source-review documents check out, **that is only a Day-7 machine-evidence checkpoint**, not a production admission assessment. The preflight does not assess 30-day continuity or claim that any Day-7/14/30 human checkpoint has occurred; it **always sets `production_eligible=false` and `weekly_AI_model_eligible=false`**. Independent checks still need to establish GitHub Actions provenance (including failed-attempt artifacts), actual human reviewer identity and original-source inspection, permitted reuse/indexing of original AFP text (including the observed API `X-Robots-Tag: noindex, nofollow`), source attribution and event corroboration, then the owner's explicit desk/AI-writer authorization. No automatic approval can be produced from an operator-written JSON file.

The Sunday writer remains production-only except for separately governed nonproduction research lanes being developed elsewhere. Do **not** slip AFP shadow IDs into production `source_trail`, substitute AFP for PCG/NSC corroboration, make public Timeline entries, or silently add source text to the AI prompt. Once these gates pass, a separate well-scoped implementation phase can wire approved AFP evidence into weekly synthesis and later move to production.

Offline tests: `python3 -m unittest tests.test_ph_afp_activation -v`. CI, output preservation and review of the exact branch head are required before merge.
