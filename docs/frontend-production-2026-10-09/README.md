# Candidate review evidence

These screenshots show the regenerated production candidate and a separate,
noindex private timeline candidate. The private timeline screenshot is review
material; it does not authorize its editorial publication.

| Route | Desktop (1440px) | Mobile (375px) |
|---|---|---|
| home | [opening](home-desktop-opening.png) | [opening](home-mobile-opening.png) |
| archive | [opening](archive-desktop-opening.png) | [opening](archive-mobile-opening.png) |
| record | [opening](record-desktop-opening.png) | [opening](record-mobile-opening.png) |
| brief | [opening](brief-desktop-opening.png) | [opening](brief-mobile-opening.png) |
| timeline | [opening](timeline-desktop-opening.png) | [opening](timeline-mobile-opening.png) |

Full-page screenshots remain in the ignored local
`preview/frontend-verification/` directory. Opening screenshots are committed
here to keep the PR review assets bounded.

[Browser receipt](BROWSER_QA.json): 75 responsive/fallback cases, 13 reader flows,
actual cold/cached loopback delivery and navigation timings. Chromium version
is recorded in the receipt. These measurements establish local rendering and
delivery, not deployed network speed or cache behavior.

[Integrity receipt](INTEGRITY.json): all 4,980 record contents and provenance,
exact six-field index rows, 10 approved native Brief relations, compatibility
routes, private/public boundary and complete CSS/JS dependency budgets.

| Route | Complete HTML + CSS bytes | Script bytes |
|---|---:|---:|
| index.html | 58492 | 11940 |
| archive.html | 126583 | 9847 |
| record/3924.html | 57260 | 5322 |
| briefs/maritime-cooperation-2026.html | 69167 | 5322 |
| timelines.html | 57318 | 3118 |
| timeline/maritime-cooperation-2026.html | 83346 | 3118 |

[Generated diff audit](DIFF_AUDIT.json): 5,166 generated files, grouped by route/asset family; canonical inputs, historical issues and source assets stay unchanged. The only archive index change is its approved native trail membership.

[All-route delivery budget receipt](ALL_ROUTE_BUDGETS.json): all 5,122 changed HTML routes fit their complete local CSS/JS budgets. The largest record is 110,284 bytes; the archive and Desks directory fit the 300,000-byte index allowance. Only the home retains its existing 12,000-byte intro script allowance.

[Validator receipt](VALIDATOR.txt): passes with the existing 10 governed historical warnings.

[Complete offline suite receipt](TESTS.json): 4,874 tests in 849.487 seconds; OK with one existing stale prototype snapshot readiness skip. Production verification uses the current explicit governed snapshot. No browser classes were skipped.
