---
description: Indo-Pacific Record Brief workflow — scaffold, contract check, editorial QA; stops before approval. Briefs have no renderer or route yet.
---

Run the Indo-Pacific Record Brief workflow. Follow
docs/ARCHITECTURE_AND_PUBLISHING.md §7 and docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md
§5b exactly. No new issue is authored or published as The PLA Watch
(DECISION_LOG 2026-09-23); `scripts/generate_pla_watch.py` refuses.

1. Confirm preconditions: the concrete development the brief begins with, its
   week, and the live desks it draws on — two or more, or one desk with an
   owner-approved exception (who, when, why). State them and stop for
   confirmation if the analyst has not specified them.
2. Scaffold: `.venv/bin/python scripts/author_brief.py scaffold --desks …
   --week-ending YYYY-MM-DD --out <path outside output/>`.
3. The analyst writes the brief: keeps the trail entries it cites, records
   `development` and each cross-desk claim with its citations, and writes the
   prose. Never compose prose, titles or translations on the analyst's behalf.
4. `.venv/bin/python scripts/author_brief.py check <path>` — must pass.
5. Run EDITORIAL_QA_CHECKLIST.md top to bottom. Delegate the source-to-claim
   and original-language checks to the `editorial-integrity-reviewer` agent
   and include its verdict.
6. **Stop.** Present the check and QA results. Do not assign an issue number,
   commit, push, or deploy — the analyst decides. Numbering is blocked while
   No. 14's publication status is unreconciled, and briefs have no renderer or
   route yet; rendering is the next phase.

Existing issues are re-rendered, never re-authored:
`.venv/bin/python scripts/rerender_pla_watch.py --no-covers`, then
`.venv/bin/python scripts/validate_output.py` (governed baseline in
PROJECT_STATE.md).
