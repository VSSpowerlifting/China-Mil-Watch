# Vietnam MOD — one-time robots and English Defence Relations listing access canary

**Date prepared:** 2026-10-10. **Status:** engineering proposal + offline synthetic proof ONLY. This note does **not** record a successful live publisher access check, a rights ruling, a current-week article, or a working MOD collector.

## Why this is necessary

The existing [offline URL identity validator](VIETNAM_MOD_PORTAL_CANARY_2026-10-08.md) and \`scripts/review_vietnam_mod_portal_links.py\` accept only exact stable \`https://mod.gov.vn/en/detail?current=true&urile=<wcm...>\` English Defence Relations content keys. That is a useful **hypothesis** but is not a source-access attestation. The ministry's WebSphere \`/!ut/p/\` widget and navigation URLs can carry session/layout tokens that should not be used as article IDs. Indexed headlines from July/May 2026 are historical examples, **not October 2026 evidence or proof of a continuously accessible source**.

This phase answers only whether a normal **GitHub Actions runner** can access the first-party robots policy and an explicitly allowlisted English Defence Relations listing without bypasses. The script is not an unattended network collector and has no effect on Vietnam's MPS/MOIT source clocks.

## Hardcoded access boundary

A live run is impossible by default. The only supported operator route is a **separately approved manual workflow dispatch**, \`.github/workflows/vietnam_mod_listing_access_canary.yml\`, with its explicit Boolean acknowledgment. PR tests run **offline** with injected fake responses and cannot make a network request.

The manual probe makes at most two GETs, in this order:

1. \`https://mod.gov.vn/robots.txt\` — requires HTTP 200, same URL without redirect, \`text/plain\` and at most 64 KiB. An unreadable, missing, HTML/challenge or disallowing robots policy ends the probe **without a listing request**.
2. Only after robots explicitly permits the disclosed project client, \`https://mod.gov.vn/en/news/sa-en-news/sa-en-news-rela\` — HTTP 200, no redirect, \`text/html\`, at most 384 KiB, at least 2 seconds after robots. Refuses obvious challenge/denial and non-listing responses.

Both calls use the **existing public project research user-agent**, 15-second timeout, one attempt, no cookies, no offsite host, no proxy/challenge solving, and no retry. Only bounded **link identities** are counted via the existing URL identity validator. No article URLs are fetched. A live result prints \`blocked\` with a machine-readable reason, or \`metadata-access-observed-not-source-approved\` with a link count and at most eight provisional WCM IDs. **Zero identified IDs is not evidence that MOD published nothing**: the listing may use widget links. No source HTML, article text, titles, PDF, media, tokens or screenshot are stored or attached.

Source rights and site terms remain **unreviewed** even if robots permits listing; robots is a technical crawler access condition, not a copyright license. Access success does not prove article-body reachability, content attribution, date fidelity, or permission to preserve/reproduce source text.

## After owner-authorized, actual-run evidence

For a result to count in the decision log, preserve the **Actions run ID and attempt, commit SHA, request statuses, refusal reason, effective logical date and precise source family**. Do not copy publisher bodies into GitHub issues. If blocked, **stop** and seek an authorized access route rather than trying mirrors, rotating identities, widgets or a stealth browser.

Only after permission and actual access checks may a later independent PR consider:
- Verifying representative publisher-served article pages against displayed issuer/byline, time and title, including zero-body and inconsistent-date fixtures;
- Demonstrating stable WCM identity across reloads **without deleting identity-bearing query fields**, as well as pagination and late-arrival behavior;
- An isolated MOD shadow state with its own clock and complete attempt journal;
- Day 7, 14 and 30 source- and version-bound human reviews, source-use scope and owner signoff;
- A verified typed **private** Vietnam MOD research synopsis for the **one** Sunday Brief, not production promotion.

Do not switch on the disabled National Defence Journal source, silently add this host to another collector, change \`desks/registry.json\`, or interpret the October 11 Brief's MPS sources as MOD coverage.

**Intended outcome this phase:** a repeatable *answer about access*, even if that answer is **blocked**. No desk-status promotion, model call, production database write, article collection, schedule, email or deployment is included.
