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

## After a separately approved successful listing observation

Independently establish visible first-party article issuer, posted date and stable document identity against the actual publisher. Then open a new proposal for a source-specific private shadow collector, prospective collection reliability, rights restrictions per content class, and a distinct metadata-only source adapter. **No direct DAPA original text, HWPX, PDF, photograph, translation or analysis may be published by this probe.**

Because the existing first-party and republisher sites are distinct domains, do not treat failure on either as justification to rotate IPs, change user agents or evade access controls. An official publisher-documented RSS/API is an alternative only if independently verified and separately approved.
