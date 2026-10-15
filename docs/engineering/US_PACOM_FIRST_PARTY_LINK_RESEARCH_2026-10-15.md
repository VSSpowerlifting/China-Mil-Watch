# U.S. Pacific Command: first-party official URL research docket
**Date:** October 15, 2026. **Status:** research-only, unapproved for public IPR publication or automatic collector use.

## What changed and why

The U.S. Indo-Pacific Reference Desk's published `access_blocked` status remains accurate for its originally proposed first-party command collection. PACOM's `robots.txt` returned HTTP 403 to the project in earlier September probes. The separate DVIDS `USINDOPACOM` unit-tag stream is a Defense Media Activity (Tier B) media service, *not* a complete set of U.S. Pacific Command statements. Its scheduled collector was paused on October 7 after eighteen consecutive 502/504 failures retrieving its own robots policy. Those conditions are **not fixed by the presence of an indexed PACOM webpage**, and this PR does not relaunch any collection or represent the DVIDS state as PACOM-authored records.

Publicly indexed pages from the first-party `www.pacom.mil` site do, however, establish concrete **source leads** useful for human-source research. The command announced restoration of the **U.S. Pacific Command** designation on June 16, 2026. The official site distinguishes `Press Releases and Readouts` from `News Articles`; a story on its news feed must not silently be reclassified as a command-authored press statement. The country desk keeps the geographical label "U.S. Indo-Pacific Reference Desk."

This pilot adds nine fixed **official URL, publisher-displayed date, identity and section** tuples under `research/us_pacom_official_link_review_2026-10-15.json`. Each was located in an indexed page on the official PACOM host; during this research, direct open of the command's releases index still returned HTTP 403. Consequently this is an **indexed first-party link docket**, *not* a live HTTP/robots verification or source-body fidelity audit. Original headlines, documents, quotes, photographs, summaries and translations were **not** copied into the project.

| Official PACOM page ID | Portal-displayed date | Website section | Reference subject |
|---|---|---|---|
| [4519249](https://www.pacom.mil/Media/Press-Releases-and-Readouts/Press-Releases-and-Readout-view/Article/4519249/department-of-war-restores-us-pacific-command-designation/) | 2026-06-16 | Press releases/readouts | Command name restoration |
| [4522099](https://www.pacom.mil/Media/Press-Releases-and-Readouts/Article/4522099/us-and-philippines-deepen-defense-cooperation-at-execom-summit/) | 2026-06-25 | Press releases/readouts | U.S.–Philippines EXCOM |
| [4566845](https://www.pacom.mil/Media/Press-Releases-and-Readouts/Press-Releases-and-Readout-view/Article/4566845/philippines-us-mark-75th-anniversary-of-the-mutual-defense-treaty-reaffirm-alli/) | 2026-08-08 | Press releases/readouts | U.S.–Philippines defense board |
| [4586166](https://www.pacom.mil/Media/Press-Releases-and-Readouts/Press-Releases-and-Readout-view/Article/4586166/mutual-defense-treaty-75th-anniversary/) | 2026-08-30 | Press releases/readouts | Treaty anniversary |
| [4589860](https://www.pacom.mil/Media/News/News-Articles/Article/4589860/28th-indo-pacific-chiefs-of-defense-conference-focuses-on-strengthening-regiona/) | 2026-09-02 | News articles | Chiefs of defense conference |
| [4591082](https://www.pacom.mil/Media/News/News-Articles/Article/4591082/readout-of-adm-samuel-j-paparos-meetings-on-the-sidelines-of-the-indo-pacific-c/) | 2026-09-03 | News articles | Commander's conference meetings |
| [4591776](https://www.pacom.mil/Media/News/News-Articles/Article/4591776/freedom-edge-2026-opening-ceremony-marks-start-of-trilateral-exercise/) | 2026-09-07 | News articles | Trilateral exercise opening |
| [4596632](https://www.pacom.mil/Media/Press-Releases-and-Readouts/Press-Releases-and-Readout-view/Article/4596632/freedom-edge-26-concludes-advancing-trilateral-readiness-across-the-indo-pacific/) | 2026-09-11 | Press releases/readouts | Trilateral exercise closing |
| [4599539](https://www.pacom.mil/Media/News/News-Articles/Article/4599539/us-pacific-command-statement-on-dprk-missile-launch/) | 2026-09-11 | News articles | PACOM DPRK missile statement |

*Dates are those shown on indexed original-site pages, not dates of a new IPR collection. None is independently verified as a source-body version, rights decision, or complete official command press archive.*

## Offline isolation

`scripts/review_us_pacom_official_link_docket.py` performs an exact, no-network check of the nine pinned identities, date strings, HTTPS URL patterns and categorized website sections. This snapshot is strictly frozen; adding one reference or changing its displayed date requires an explicit new review and code change. `tests/test_us_pacom_official_link_docket.py` tests counterfeit hosts, query insertion, invented IDs/dates, unknown media/title/body fields, false publication grants, DVIDS scope confusion, and read-only checks. The narrow CI workflow performs no source fetch, production DB writes, webpage rendering or GitHub push.

Crucially, these nine tuples do **not** enter the public website or searchable IPR collection, and the status stays `access_blocked`. This avoids confusing an easily discoverable **outbound URL** with authorized **automated crawling**, or mistaking a command-hosted `News Article` for a directly command-issued statement.

## Next operational decision and admission path

1. Obtain an officially documented **permitted** PACOM feed, readable `robots.txt`, or authorization from the command's public-affairs office for machine retrieval. Do **not** use indexed search as a hidden bulk collection route, evade a 403, or use proxies/alternate hosts to bypass the documented blocker.
2. Independently confirm each official URL and displayed publication date through a permitted first-party route. Verify whether it is an authored press statement, a readout, or an externally authored article merely hosted or syndicated there.
3. If reliable source discovery becomes permitted, build a separately versioned, shadow-only **first-party command-source adapter** with source IDs, date/issuer provenance, bounded collection and attempt/health logs, and review its actual gaps; it must not inherit DVIDS's clock or recast existing DVIDS records as command releases.
4. A **bounded official-link-only public directory** is a separate editorial release choice, not automatic approval conferred by this research. Keep original source bodies, photos, derivative analysis and full citations on their own approval tracks. Update the registry only after the public reference/reliability claims are actually true.
5. Keep the future U.S. Desk a complementary **institutional perspective**, not evidence that an institution's self-reports independently verify contested events. Do not treat military activities throughout the region as equivalent to all U.S. policy or Pacific Command orders.

**No owner action or credential is required for this research-only PR.** The owner may separately authorize a finite, reviewed, outbound-link directory if useful before machine collection becomes possible.
