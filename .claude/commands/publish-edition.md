---
description: Weekly PLA Watch publish workflow — draft, editorial QA, validate, preview; stops before commit for analyst approval.
---

Run the weekly edition publish workflow for The PLA Watch. Follow
docs/ARCHITECTURE_AND_PUBLISHING.md §7 exactly.

1. Confirm preconditions: week-ending Saturday date; issue number =
   1 + count of existing sidecars; API key available. State them and stop
   for confirmation if the analyst has not already specified the week.
2. Generate the draft: `.venv/bin/python scripts/generate_pla_watch.py`
   (or note the artifact from `generate_pla_watch_draft.yml` if provided).
3. Run EDITORIAL_QA_CHECKLIST.md top to bottom. Delegate the source-to-claim
   and Chinese-text checks to the `editorial-integrity-reviewer` agent and
   include its verdict.
4. `.venv/bin/python scripts/validate_output.py` — must pass; explain any
   warning beyond the 9 historical ones.
5. Re-render dependents: `.venv/bin/python scripts/rerender_pla_watch.py
   --no-covers` (predecessor's "next" link, index, archive, terms, feed).
6. Preview post + index + archive at desktop and 375px; provide screenshots.
7. **Stop.** Present: QA results, validator output, LinkedIn text, preview
   evidence. Do not commit, push, or deploy — the analyst decides. After an
   approved publish lands, update PROJECT_STATE.md (edition count, any new
   recorded gap).
