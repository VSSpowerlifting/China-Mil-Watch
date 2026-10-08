# AFP source review docket — keep the 18-record human gate manageable

The existing collector already preserved **13 full-text AFP originals on October 7** and **five more on October 8**. Scripts for regenerating each complete immutable original-capture review packet were merged in #178 and #185, but those packets contain long AFP body text and full JSON. This docket creates a separate **metadata-only scheduling view** to see what must be reviewed without duplicating full source material in public artifacts or pretending a model completed a source review.

## Read-only operator command

Fetch the public isolated `shadow/ph-afp` Git history deliberately into a **local authorized checkout** before running this script. It does not fetch websites or follow mutable branches on its own. Each batch must identify the actual historical Git commit at which the run's state became final, not the newest state snapshot.

```sh
python3 -m scripts.prepare_ph_afp_review_docket \
  --state-repo /path/to/local/repository-containing-historical-shadow-state \
  --batch 492001f34ba6176169b6acc96a237f05592a3395:37631681338-1 \
  --batch c668790ce3be88b08b3300b945bad58589b3a5b1:37788547061-1 \
  --format markdown > /secure/afp-unsigned-review-docket.md

```

This should list 18 first-seen records if both actual preserved historical commits are available and validated. It is a **deterministic expected result**, not a claim of a live replay on this development branch. JSON is available with `--format json`. Output excludes article bodies and original API JSON; it includes the original *article titles*, publication dates, official URLs and hashed evidence identities. Do not publish source-sensitive review annotations or the private originals alongside this index.

The docket deliberately does not choose topics, produce executive summaries, rank sources by strategic significance, count independent events, add taxonomy labels, certify reuse rights, identify the reviewer or mark records verified. Every source remains **Pending**. Three AFP reports describing the Sanlakas exercise are still evidence for one provisional exercise, not three independently corroborated exercises.

## How to complete actual human review

For each batch, generate the separate full source packet using the existing merged script:

```sh
python3 scripts/prepare_ph_afp_run_review.py packet \
  --state-repo /path/to/local/repository-containing-historical-shadow-state \
  --state-commit 492001f34ba6176169b6acc96a237f05592a3395 \
  --run-id 37631681338-1 > /secure/afp-2026-10-07-private-originals.json

```

An actual reviewer must independently compare the full archived API response and extracted text for **every** source, then record the six source-fidelity decisions in that private original packet. Repeat for the October 8 batch using its own historical commit and run ID. Do not infer approval from the fact that AFP published the text, from automated hashes alone, or from the docket's compact table. Use the merged `prepare_ph_afp_run_review.py validate` command to test the completed review file against the exact frozen originals.

Keep the full packets under access control. The original API's observed `X-Robots-Tag: noindex, nofollow` and source-use rights remain unresolved separately from an editor checking completeness. This is not a production promotion or a source-text publication tool.

## Engineering guardrails

- Per-run original packets must be regenerated from literal Git commits. The docket rejects unexpected protocol/state flags, any non-pending or fabricated reviewer status, missing full-text records, wrong AFP URL hosts/paths, inconsistent hashes, duplicate source IDs and malformed run references.
- Neither the docket nor its output contains raw source bodies, original API responses, model text, editorial judgment or a source approval.
- No modification to `desks/`, AFP/NSC collector schedules, production SQLite, Briefs or the Sunday workflow. Do not use this document to place shadow records into the AI writer.
- The review validator, reliability audit and independent Actions provenance audit remain separate stages of the eventual owner-controlled production admission.

Tests: `python3 -m unittest tests.test_ph_afp_review_docket -v`. The new synthetic tests do not supply any real source text or claim that a human reviewed it. Full exact-head CI, rendered-output verification and unchanged production DB/output remain required.
