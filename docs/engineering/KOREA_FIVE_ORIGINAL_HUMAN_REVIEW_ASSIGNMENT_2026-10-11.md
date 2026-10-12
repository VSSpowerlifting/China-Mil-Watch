# Korea Desk — five-real-original human review and source-specific decision docket

**Status, 2026-10-11:** source and technical preparation COMPLETE; independently authenticated Korean semantic/HWPX visual signoffs **0/5**; source-specific rights signoffs **0/5**; owner public-release approvals **0/5**. All five candidates remain on a PUBLICATION HOLD. This docket is an assignment record, not evidence that anyone has signed it.

## Smallest public product being considered

A **fixed and tightly labeled** list of no more than five individual Korean MND press releases **republished by** the Republic of Korea Policy Briefing portal. Each would contain its exact Korean title, first-party link, MND issuer and Policy Briefing publisher attribution, carefully edited short English description, explicit distinction between portal date and original-document release date, content SHA and review provenance. No article bodies, translated full text, HWPX, third-party media, automated Briefs, future IDs, DAPA or production source admission.

## What the independent reviewer receives

Merged [PR #419](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/419) prepares the REAL five HWPX bytes from state commit `dcb43b9c4edb471d6def5876701ec4a2e39d5264`, exact extracted Korean text, five tailored checklists (in Korean), and deliberately empty review/rights/owner fields. Each machine extraction and capture SHA was reverified against the archived source.

Locally, in a trusted checkout containing the unchanged Korea shadow Git ref, run:

```sh
python -m scripts.prepare_korea_human_review \
  --state-repo /absolute/path/to/China-Mil-Watch \
  --state-commit dcb43b9c4edb471d6def5876701ec4a2e39d5264 \
  --out /absolute/private/path/korea-human-original-review \
  --acknowledge-private-originals
```

The target must not exist, must be outside repo, and writes a 0700 directory and 0600 source files. **Never** commit or upload original HWPX, original Korean bodies, completed reviewer notes or personal signatures into public source control or public Actions artifacts. The original files remain in separately access-controlled review storage.

**Five exact identities:** `156783602` (remains-recovery exhibit announcement); `156783708` (naval readiness and Cheonghae **pre-deployment**); `156784196` (Camp Humphreys visit and reaffirmed existing posture); `156784297` (MND missile detection/interception **capability assessment**, original October **4** / portal October **6**); `156784652` (McCormick meeting, shipbuilding/defense industrial **discussion**, not a binding contract). Exact title and SHA for each live in `research/korea_reference_candidates.json` and `KOREA_FIVE_ORIGINAL_SEMANTIC_REVIEW_2026-10-11.md`.

## Strict division of roles and a reviewer's expected deliverable

1. **Independent qualified Korean-language document reviewer:** open each actual HWPX visually, compare line/paragraph/table order against `<id>.ko.txt` and live publisher article, verify title, issuer, names, event versus announced/proposed outcomes, factual modality and original-distribution-versus-portal date. Correct or reject the proposed English description. Sign only the source IDs and source/content/HWPX hashes personally inspected; record competence, date and supporting differences in private review storage.
2. **Designated source-rights reviewer:** independently open each *specific* official publisher page and applicable notice; decide that exact **text-only bibliography/English descriptor** is within the KOGL Type 1 attribution scope. Identify any photos, HWPX embedded graphics, diagrams, QR media, third-party content, images or seals that remain excluded; mark source use HOLD on uncertainty.
3. **IPR editorial owner:** review what the qualified human and rights reviewers signed, accept or reject *each* English descriptor, check author/publisher attribution and date conventions, and explicitly authorize only specific reference rows for a **private final QA**, not for general Korean source collection. Actual release still requires a separate public-site PR and deployment decision.

Keep all original review notes external and private. The structural schema `ipr-korea-source-admission/1` is in `core/korea_reference_gate.py`. **Typing reviewer names into JSON is not independent reviewer authentication.** Owner must verify identities and supporting evidence separately. A missing reviewer, hash discrepancy, title/date divergence, uncertain image rights, unauthorized sixth ID, or absent owner decision excludes that row. **Zero passed rows means zero public records.**

## Private website QA immediately after genuine review

```sh
python -m scripts.preview_korea_site \
  --out /absolute/private/path/korea-site-review \
  --structural-approval-packet /absolute/secure/path/actual-reviewer-packet.json \
  --acknowledge-no-identity-authentication
```

This generates a **real IPR-designed, unlinked, noindex** `korea.html` but is never a site deploy. Only valid SHA-bound rows receive an English descriptor; all others stay marked HOLD. [Merged PR #420](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/420) tested this with fake synthetic reviewer data for logic only ([website QA](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38191242859), [reference QA](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38191242849)). Current real approved rows: **0**.

## Publication handoff — blocked pending R1

After *authenticated* per-record decisions, a new isolated owner-reviewed PR must project only cleared metadata into the public site, test exact reviewed hashes, correct attribution, source links, accessibility and site navigation, confirm no HWPX/media or raw Korean body copied, keep source count/production SQLite unchanged and perform explicit authorized deployment. Korea may then be accurately labeled a **limited MND official-reference pilot**, not a live collecting or whole-country Korea Desk. The existing registry `public=false`, `status=shadow` and the site guard remain in place until that separately approved PR.

This is the **human review assignment**. More routine technical scaffolding is not a substitute for the actual reviewer.
