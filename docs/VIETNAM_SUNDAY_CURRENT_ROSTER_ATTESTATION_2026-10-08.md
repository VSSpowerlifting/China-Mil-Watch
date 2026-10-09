# Vietnam Sunday research-roster attestation — October 8, 2026

## What this closes

A fixed Japan/Vietnam JSON roster may have legitimate official-source research notes but fail to reflect the **latest** independently collected Vietnamese Ministry of Public Security source versions. The Sunday AI writer merged through #237 must not silently assume that its hard-coded October 10 source list is complete or unchanged.

`scripts/attest_vietnam_sunday_roster.py` re-derives its Vietnam portion from the **current exact MPS orphan-state Git commit** using the already-approved read-only review chain (`prepare_vietnam_mps_review_queue` and `build_vietnam_sunday_packet`). It then compares every advertised Vietnam identity, URL, language, issuer, date, title, content SHA-256, attributed synopsis, caveat, topic and no-approval flags with the freshly audited private packet.

Only the state commit pointer may be historically pinned: every static commit is separately proven to be a genuine ancestor of `shadow/vietnam-mps-foreign-affairs` and the source content MUST still match the latest independently verified archive.

The **attestation's current-source commit** (unlike each historically pinned static row) must match the trusted MPS orphan branch's actual HEAD exactly. A replay from a prior state may be useful for historical research, but it must not pass the current-state freshness gate. The original Japan rows are neither changed nor considered proof of Japanese source review.

A **strict optional gate** `--require-all-eligible` refuses this week's Sunday preview when the current archive has additional machine-eligible MPS publications that are missing source-specific private synopses. They cannot be silently omitted while the workflow claims a complete Vietnam research roster. This does **not** infer ministry silence; collection and limited publisher listing coverage are deliberately tracked separately.

## Real archive CI contract

The read-only `Vietnam Sunday Current MPS Roster Attestation` PR contract:

1. Runs synthetic no-network refusal tests on the proposed code.
2. Clones the real isolated MPS orphan state via unauthenticated read-only HTTPS, verifies its exact head and state-only tree.
3. Separately clones the authoritative `main` branch at its exact resolved commit and reads the October 10 private editorial roster merged from #237. This is a **read-only merged-production-code comparison**, not a push, approval, or change to the official roster.
4. Independently replays the actual MPS source-state/capture/SQLite/version chain and checks the packet against `editorial_notes_2026-10-10.json`.
5. Demands **every currently machine-eligible, in-window MPS row** have an exact source-version-matched short editorial synopsis (one to three, under the existing quota). The October 8 collection added a third, October 7 Vietnam–Australia item and the check correctly failed while the packet had only two; #245 prepares the third note. If additional source evidence arrives, the gate fails until independently source-specific research exists. It does not fabricate English claims or imply publisher silence.

The workflow does not call a language model, transfer source article bodies, send SMTP, upload public artifacts, schedule a collector, request write tokens, modify the archive or assert publisher/source-use rights. No actual Sunday email is sent by this milestone.

## Run locally after providing trusted exact Git clones

```bash
python -m scripts.attest_vietnam_sunday_roster \
  --state-repo /path/to/isolated/mps-shadow-clone \
  --state-commit <actual-exact-shadow-HEAD-SHA> \
  --week-ending 2026-10-10 \
  --notes research/vietnam_briefs_candidates/editorial_notes_2026-10-10.json \
  --offered-packet /path/to/exact-week-sunday-research.json \
  --require-all-eligible \
  --out /tmp/ipr-vietnam-2026-10-10-attestation.json
```

Never treat the output as human review, full publisher coverage, legal permission, a Vietnam production-desk qualification or a manuscript approval. It is a **source-version and completeness gate for private drafting only**.

## Follow-on coordination

Now that #237 has merged, the Sunday workstream can invoke this attestation on the actual private packet immediately before the model call, after this PR itself passes review and merges. This PR purposely does not modify #237's shared writer, scheduled workflow, model prompts or email controls. Longer-term weeks should generate the whole unified regional roster from source-version-audited country feeders, and use #235's explicit no-Vietnam fallback where Vietnam has no qualifying notes. The October 10 strict complete-Vietnam check must not accidentally become a hard dependency blocking unrelated regional Sundays.

The CI proof already uses `main`, not the retired #237 development branch, so deletion of that branch cannot disable this check. If the merged roster's schema or exact-week source file changes, fail closed until the verification is explicitly reviewed and adapted.
