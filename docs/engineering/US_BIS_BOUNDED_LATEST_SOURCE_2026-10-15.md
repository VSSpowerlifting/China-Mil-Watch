# Bureau of Industry and Security — bounded alternate source access

The BIS news-updates page returned an `oversize_response` error at the original 160 KiB read cap, not an HTTP 403 and not a usable metadata collection. BIS is an executive agency within Commerce with substantive export controls and enforcement reporting. Its official homepage and Enforcement landing page both preview recent news with dated links according to the publisher's own public pages. <https://www.bis.gov/> and <https://www.bis.gov/enforcement>.

This canary requests the verified BIS official `robots.txt` before **at most two fixed official listing routes** (homepage `/`, `/enforcement`), each strictly limited to 650,000 bytes with no redirects, proxy use, retries, article-body requests, pagination or external links. It prints only structural DOM properties and official relative path samples, not release headlines, body excerpts, analysis or original files. No observed source state is persisted, no collection day is claimed, and no source material is published.

If one route supports strict self-contained date-link association, build a narrow first-family metadata-only parser and tests, rather than silently increasing request limits without evidence. Keep BIS export controls separate from Treasury press, congressional USCC, PACOM commands and DVIDS media.
