# Korea DAPA first-party government press source — bounded access investigation

**Status:** Research-only. The first-party `www.dapa.go.kr` website is a distinct potential source from the `www.korea.kr` DAPA republisher listing. No first-party live network authorization, collection, capture, reuse permission, source identity or Pages publication is granted here.

## Triggering verified failure

Owner-dispatched [korea.kr DAPA listing probe #38971932979](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/38971932979) on **October 16, 2026** returned:

`{"state":"blocked","reason":"publisher unavailable","requests_attempted":1,"robots_checked":false,"listing_checked":false,"collector_enabled":false}`

The very first `www.korea.kr/robots.txt` GET did not complete during the bounded 15-second request. There was **no DAPA-filtered listing GET**, publisher original, bypass, attachment, production or licensing observation. This is an unknown availability/egress issue, not proof DAPA blocked or permitted robots access.

## Separate direct-site lead (not verified live by Actions)

Public search indexing identifies the **agency-operated** official site `www.dapa.go.kr`, with a dedicated press list:

`https://www.dapa.go.kr/dapa/doc/selectDocList.do?bbsSeq=326&menuSeq=3069`

Indexed results show dated press releases from October 2026. A known detail URL shape is `/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=...&menuSeq=3069`. **Neither the search index nor synthetic tests establish Actions-runner accessibility, source/date/issuer authentication, a stable API contract, copyright rights or owner authorization.** This route is not an automatic replacement for the `korea.kr` listing.

## Explicit one-time probe on a distinct hostname

Workflow: `.github/workflows/korea_dapa_native_access_canary.yml`. The user must separately dispatch from `main` as repo owner and check `approve_one_time_direct_dapa_access`. Pull requests only execute offline synthetic tests.

1. One strict, unredirected `GET https://www.dapa.go.kr/robots.txt` (15s, <=32 KiB, plain text). Fail closed if unreachable, challenged, unusable, unexpected or disallowed by robots.
2. Only after robots explicitly permits the press-list route, pause two seconds, then ONE unredirected `GET` to the exact DAPA-owned listing (15s, <=350 KiB HTML). No cookies, retries, alternative clients/hosts or hidden endpoints.
3. Inspect HTML **only in memory** for strict, same-host links to `/dapa/doc/selectDoc.do`, exact `bbsSeq=326`, unique numeric `docSeq`, optional exact menuSeq. Output only counts and up to six provisional numeric identifiers. Never persist titles, source article bodies, press HTML or attachments. Zero qualifying links is **unknown listing structure**, not proof of zero articles.
4. Output is at most `listing_shape_observed_unverified`, NOT source eligibility, verified DAPA attribution, automatic source permission, rights clearance or production admission. Any failure returns a fixed HOLD code.

## Actual first-party live observation — 2026-10-16

Owner manually dispatched the separately authorized [native-source canary run 38974484820](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/38974484820); its exact run produced:

- `robots_checked=true`, `listing_checked=true`, `requests_attempted=2` (one `robots.txt`, one exact DAPA-owned listing GET); workflow **passed**
- `observed_anchor_count=325`, `provisional_docseq_count=0`, `sample_unverified_docseq=[]`
- `zero_matching_links_is_not_zero_publications=true`; no valid same-host static `selectDoc.do?bbsSeq=326&docSeq=...` link was recognized by the **existing strict parser**
- No article or attachment request, zero publisher-original content saved, and no changes to the production site or DB

**Interpretation:** the press page is reachable in the GitHub Actions network, but its actual list-to-item navigation format remains unverified. A zero numeric ID count cannot prove an empty release list. It may use JavaScript handlers, form submissions or other DOM patterns; these are hypotheses, not observed facts.

This follow-on engineering change records only aggregate counts of anchor/form/link *shapes*, including the number with JavaScript hrefs, onclick handlers, direct-detail paths without qualified IDs, forms and hidden inputs. It does not emit publisher HTML, unverified URLs, full titles, JavaScript code or guessed IDs, and it does not modify the one-time request budget or scope. A **new** separately owner-approved manual run after merge will be required to observe these diagnostics from the publisher.

Do not convert tentative JavaScript/form-derived numeric strings into official source IDs until a real issuer/date/article pair has been independently established through a separately approved source-specific workflow.

## Second structural observation — 2026-10-16

Owner-authorized [run 38977064941](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/38977064941), current as of the merged [#764](https://github.com/VSSpowerlifting/IndoPacificRecord/pull/764), completed successfully. It read exactly two first-party requests, with 325 anchors, 45 fragment hrefs, 17 JavaScript hrefs, 10 onclick anchors, one GET form and seven hidden inputs. There were **zero** qualified canonical article hrefs, zero recognized `data-docseq` attributes, zero inputs named `docSeq`, and zero requests for an article. These counts do NOT identify which anchors are press-release rows.

Separate publicly indexed official first-party pages establish that the publisher presents a release listing with article numbers/titles/dates in a table, and that genuine DAPA article detail URLs include `bbsSeq=326` and a numeric `docSeq`. Search observations cannot establish how the exact live list's HTML connects individual rows to detail IDs, nor certify completeness of that list on an Actions runner. A listed press release may originate from an affiliated institute rather than DAPA itself, so issuer attribution must remain item-local.

**Follow-up change:** Count only the number of HTML table rows, table cells, rows bearing a date-shaped token, and whether such rows have an anchor/JavaScript navigation or a qualified static document link. This diagnostic intentionally returns no row number, date, title, URL, JavaScript code, hidden field value, candidate original, or inferred source ID. No new request routes, no click simulation, no collector, and no rights or editorial authority are added. Further human owner authorization is required for another manual network run after merge.

## Latest bounded row-navigation diagnostic: actionable vs. ambiguous JS shape

Verified [owner-run 39031062944](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39031062944) saw ten date-bearing table rows, all with interactive anchors, but zero static canonical `docSeq` URLs. One cannot conclude the actual row-to-ID mapping from this count.

The next **offline-first, PR-tested** phase classifies whether dated rows carry a simple single-integer function call, a more complex numeric call, a nonnumeric call, or no recognizable call. Crucially it returns **counts only**: neither JavaScript code/function names nor argument values, document IDs, dates, Korean release titles, row ordinals or raw publisher HTML appear in the receipt. A simple numeric argument might be an ordinal or tracking reference; it is **not assumed to equal the immutable DAPA `docSeq`**.

This adds no request endpoints or retries. On PRs the test uses fictional HTML only. A later real observation is a new explicitly approved owner dispatch of the existing robots-first DAPA listing canary; previous approvals are not automatically reused. Even a successful run cannot enable collection, source reproduction, per-item DAPA attribution, English translation or analysis publication. Link arguments must be separately corroborated against genuinely served same-origin article identities before admission.

## After a separately approved successful listing observation

Independently establish visible first-party article issuer, posted date and stable document identity against the actual publisher. Then open a new proposal for a source-specific private shadow collector, prospective collection reliability, rights restrictions per content class, and a distinct metadata-only source adapter. **No direct DAPA original text, HWPX, PDF, photograph, translation or analysis may be published by this probe.**

Because the existing first-party and republisher sites are distinct domains, do not treat failure on either as justification to rotate IPs, change user agents or evade access controls. An official publisher-documented RSS/API is an alternative only if independently verified and separately approved.

## October 17 — owner browser-click witness as an optional listing-only comparison

The owner clicked the apparent newest entry on the live DAPA first-party press list, page 1 with 10 rows, and reported the resulting browser URL:

`https://www.dapa.go.kr/dapa/doc/selectDoc.do?docSeq=59312&menuSeq=3069&bbsSeq=326&currentPageNo=1&recordCountPerPage=10`

This is an **owner-supplied browser observation** from a real click, not an independently captured versioned source record or proof of the government article's text, date, issuer or rights. The strict canonical route for this one example is `https://www.dapa.go.kr/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=59312&menuSeq=3069`. The two navigation parameters are pagination state, not source identity; list row number 1 is not itself the `docSeq`.

The previously authorized first-party listing canary [run 39042532768](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39042532768) saw ten dated rows, each with one simple numeric JavaScript link argument, but **zero static article URLs**. The clicked URL lets the owner compare the apparent first row's exact numeric argument against one browser outcome on the **next separately approved listing request**; it does not establish what the navigation handler does for all rows.

The existing `korea_dapa_native_access_canary.yml` now accepts an **optional** `witness_article_url` on owner-approved manual dispatch only. It enforces the original fixed maximum of **one robots GET plus one listing GET**—no article, JS resource, HWPX, PDF, or media GET. It strictly checks the owner-provided full same-host URL/board/section and navigation parameters *before* any request, then uses the existing offline private row parser to ask whether **exactly one** unambiguous dated row matches the URL's numeric value **and it is the first dated row**. The only additional emitted data are a fixed match verdict, row count, a claimed list date when matched, and the SHA-256 of the listing HTML response. No raw HTML, original headline, JavaScript function code or article text leaves runner memory. A mismatch has a distinct nonzero HOLD result and does not silently qualify collection.

**Still separately unverified even if this comparison turns green:** authenticated visual click/handler semantics, article date and issuer from this specific current item, exact-source preservation and private custody, dynamic listing pagination/completeness, per-article/attachment license, scheduled reliability and production admission. The previously qualified article `docSeq=59180` and the owner-clicked current `docSeq=59312` are different items. The owner must separately authorize any live listing request; the earlier one-time consent is not reused. Do not re-run probes merely for a green checkmark or mark full Korea source coverage as live from one row.

