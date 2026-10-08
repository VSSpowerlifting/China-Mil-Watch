# Japan Coast Guard official full-text source — live access gate (Oct 8, 2026)

**Status: independent institutional candidate; not in shadow collection or production.**

## Why JCG rather than forcing access to MOD

The existing Japanese MOD RSS feeds give reliable discovery but mostly challenged HTML; the sampled news feed had 8 PDFs and 134 HTML pages. A new MOD parser cannot solve an HTTP challenge.

Japan Coast Guard (JCG) is an independent maritime law-enforcement/public-safety institution. Its English [press-release archive](https://www.kaiho.mlit.go.jp/e/topics_archive/index.html) publishes individually dated pages with substantive bodies and linked original PDFs. On 2026-10-06 it published distinct Philippine Coast Guard training reports:
- https://www.kaiho.mlit.go.jp/e/topics_archive/article9455.html — maritime/environmental forensic and oil-spill investigative skills
- https://www.kaiho.mlit.go.jp/e/topics_archive/article9453.html — arrest-techniques instructor training

On 2026-09-29 it published:
- https://www.kaiho.mlit.go.jp/e/topics_archive/article9436.html — Indonesia BAKAMLA maritime law enforcement capacity building

This evidence is directly relevant to cross-desk maritime law enforcement, Philippines-Japan cooperation and capacity building. **Do not attribute any JCG statements to Japan MOD or its Joint Staff.**

**Source use:** the [official JCG terms](https://www.kaiho.mlit.go.jp/questions/post-1.html) state that ordinary government-owned website content is generally subject to Japan's Public Data License 1.0 (with source attribution and disclosure of edited work), while logos, particular excluded works and third-party rights are treated separately. Image/logo ingestion is excluded from this pilot. The separate publishing/rights review remains necessary before permanent archive admission.

## Actual GitHub egress test

The self-contained probe is deliberately not a collector. It reads robots.txt once from the exact official hostname, then requests at most these 5 declared official URLs *if and only if* the policy can be read and permits them: the archive index, the two Philippine original HTML articles, the Indonesia article, and one linked SAPPHIRE26 official PDF.

One GET per URL, no redirects or retry, single clearly identified client, bounded body sizes, no cookie/session reuse or challenge solving. Raw original bytes and extracted visible text are used in memory only for signature and headline checks. They are never written, logged, uploaded or committed. The run preserves only status/mime/size/SHA-256 counts in a metadata artifact.

Success requires a compliant policy response, full HTML bodies with expected title markers, and PDF magic/response type for the test document. **Success is just accessibility; not editorial validation, institutional scope verification, complete PDF extraction, or a license to add a manifest.** If policy is unavailable (as MOFA and METI were in run 37815162333) the script makes zero document requests.

## If it passes

1. Use a separate PR to implement an English-language JCG adapter to the *existing* SourceAdapter interface; no alternate ingest path.
2. Persist publisher URL, exact date and title, original English body, capture hashes, capture timestamp and issuer. Test actual document fixtures and zero-navigation extraction. Do not infer date from page number.
3. Qualify an isolated Japan Coast Guard shadow source using a dedicated, declared scope, independently of the challenged MOD sources. Verify source cadence and coverage over repeated runs.
4. Run the existing Day 7/14/30 review/owner-promotion process; rehearse a multi-source Japan promoter on a disposable production database with immutable capture binding.
5. Only then admit JCG as a production source under Japan Desk and allow its native source records to reach the weekly AI writer. Describe coverage as *Japan Coast Guard*, not full Japanese defense policymaking.

PR #202's dated, externally labeled AI-source path is temporary and remains independent.
