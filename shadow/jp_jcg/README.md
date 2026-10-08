# Japan Coast Guard official English releases — disabled shadow candidate

**Status: adapter under fidelity review, source disabled, no state branch or
scheduled collection authorized by this folder. No production record exists.**

The Japan Coast Guard is a maritime law-enforcement authority, **not** the
Japanese Ministry of Defense or Joint Staff. Its English official press-release
index `https://www.kaiho.mlit.go.jp/e/topics_archive/index.html` is a distinct
source family from Japan MOD RSS. It supports maritime safety, law enforcement,
capacity building, and cooperation with foreign coast guards. It cannot stand
in for comprehensive Japanese defense-government coverage.

## Source access and policy

The named GitHub Actions client obtained actual original HTML articles and a
PDF from the host in the bounded October 8 access probe
[run #37816874786](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37816874786).
Robots.txt returned 404, meaning no rules file was published, not a 403
denial. There were no identity switches, cookies, proxies, retries, redirects,
challenge solvers, guessed URLs or third-party text mirrors.

The JCG's publisher content-use notice states ordinary government-created
website content is generally under Japan's Public Data License 1.0, subject to
attribution, edited-content disclosure and exclusions. This does not confer
rights over third-party photographs, logos or attachments. Formal source-use
review is still required before any permanent archival publication.

## Initial scope

Only the English original HTML press-release family, with source-stated dates
on or after **2026-09-01**, is within the initial pilot. Historical index rows
before September remain *counted as pre-scope rows*, not secretly presented as
collected. The parser demands paired index dates and first-party article URLs.

The adapter extracts only the HTML article body inside the publisher's
`section.topics.topics-article` / `div.topics-article__main.tich-text`.
Linked PDF text, images, and external resources are **not** included or
claimed to be archived. A publisher release available only as PDF or whose
HTML is merely a links page fails text-quality review rather than becoming
a fake full-text record. Subsequent optional PDF integration requires
separate extraction, content-boundary and reuse gates.

Every eligible captured record must include the original English title,
original body, official URL and publisher's article date, plus capture and
content SHA-256 digests. The schema never uses a repeating headline as identity.
The source is not a translation of Japanese MOD publications.

## Proofs and next steps

- Offline source tests: `python -m unittest tests.test_japan_jcg_shadow_adapter`.
- Live read-only tests: `python -m scripts.probe_japan_jcg_adapter_live`.
  Fixed October 8 source window; no database, no original HTML/PDF persistence,
  no owner approval, no clock and no email.
- `enabled: false` in this candidate manifest. The ordinary production
  manifest loader reads only `desks/*/manifest.json`; this remains under
  `shadow/`.

**Before a live shadow run:** pass actual index+article extraction proof and
independent source-use check; review a dedicated isolated runner entry and
state-branch policy; obtain owner authorization to activate manually.
**Before production:** measure source-specific retrieval and extraction
continuity; complete the Day 7, 14 and 30 human reviews; fix date, charset,
attachment and omission issues; rehearse correction/promotion on a disposable
production database; obtain explicit owner signoff. The automated weekly AI
writer remains restricted to eligible production records.
