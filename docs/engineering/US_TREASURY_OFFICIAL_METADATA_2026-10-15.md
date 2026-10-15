# U.S. Treasury: official press listing metadata collection — October 15, 2026

The first genuine U.S. government access canary #685 proved that Treasury robots.txt allows a bounded first-party GET of `https://home.treasury.gov/news/press-releases`. Real GitHub-runner DOM inspection #687 found 10 individually dated `featured-stories content--2col` cards with publication dates in `time` elements and canonical `/news/press-releases/sbNNNN/` URLs.

This source is the **U.S. Department of the Treasury**, an executive department. It is distinct from the U.S.-China Economic and Security Review Commission, U.S. Pacific Command, the Navy, DVIDS, and IPR commentary.

The exact collector checks robots policy on every attempt, downloads only the first listing if permitted, validates card dates and canonical official release identifiers, refuses mixed-card dates and unfamiliar layouts, and records only source ID, canonical link, publisher date, official issuer/publisher, listing URL and source-listing SHA-256. No article body request, foreign redirect, reuse-rights assumption, media rehosting, translation or AI analysis.

The daily workflow runs at 12:10 UTC and appends genuine metadata receipts to Git `shadow/us-treasury-press`. A failed policy or parser check creates no observation. This is not historical publisher coverage; only directly observed listing cards are archived. The listed Treasury releases span multiple subjects, so a metadata directory must **not** falsely imply every item relates to the Indo-Pacific. Subsequent editorial research can separately select and describe relevant releases.

Next: exact immutable observed-day verification, idempotent isolated Treasury SQLite table admission, and U.S.-page-only publication under the already approved factual URL/date/issuer rule. Existing USCC metadata and nine static PACOM links must remain intact. Treasury public source URLs are not production source-body articles and cannot inflate the main IPR article count.
