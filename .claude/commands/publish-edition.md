---
description: Indo-Pacific Record Brief workflow — readiness, editorial review, private preview, authorized approval, render and release verification.
---

Use `docs/ARCHITECTURE_AND_PUBLISHING.md` §7 and the full
`EDITORIAL_QA_CHECKLIST.md`. Existing issues retain their historical sources,
addresses and attribution; no new issue is authored as The PLA Watch.

1. Recover existing work and recorded human instructions first. Scaffold only
   if needed with `scripts/author_brief.py scaffold`, choosing the development,
   reporting window ending Saturday, and contributing live desks from the brief.
2. Finish the prose and source trail. `check` validates schema; `ready` also
   requires finished prose, resolvable citations and exact stored source state.
   Neither is editorial approval.
3. Delegate source-to-claim and original-language review to the read-only
   `editorial-integrity-reviewer`. Apply the full checklist and inspect the
   actual article and Analysis pages at 1280 and 375 pixels.
4. Render an unapproved candidate with `site/render.py --review-brief
   briefs/<slug>.json --out <private scratch directory>`. This uses production
   templates with a visible review notice, no number/approval, `noindex`, and
   no native feed or sitemap. Ordinary rendering continues to withhold drafts.
5. Follow authorization already given by the human. If approval is genuinely
   missing, finish the exact review candidate before asking once. Never infer
   approval of one artifact from approval of a different draft or fabricate it.
6. With explicit approval, run `author_brief.py approve` with approving human,
   actual date and approval reference. It assigns the next number from the
   whole collection; repeat execution with identical evidence is unchanged.
7. Run the production renderer and deploy validator. Separate source/docs/output
   commits, prepare the PR and follow recorded merge/deploy authorization.
   Existing deploy workflows publish committed output from main; no new
   collection, API call or scheduled authoring flow is required.
8. After deployment, fetch the actual article, Analysis, home, native feed and
   sitemap. Check title, number, citations and version; only then report it as
   published. Update `PROJECT_STATE.md` with actual status and remaining work.
