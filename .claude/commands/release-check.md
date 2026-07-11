---
description: Full pre-deploy validation and rendered QA sweep (validator, responsive, a11y, budgets) with a go/no-go verdict.
---

Run the release gate: launch the `release-qa` agent on the current
`output/` and report its go/no-go verdict with findings.

If it reports blockers, do not proceed toward deploy; map each blocker to
its owning source file (templates/scripts, never output/) and propose the
fix as a bounded ticket for `frontend-implementer`. If it reports go,
summarize the evidence (validation status, routes checked, page weights)
and remind the analyst that deploying requires committing output to main
and running the deploy workflow — which only happens on their explicit
request.
