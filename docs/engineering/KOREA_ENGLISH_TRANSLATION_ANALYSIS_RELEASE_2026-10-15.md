# Korea English translations and source-grounded analysis

## What is delivered

Three completely separate tracks are intentionally preserved:

1. **Verified Korean originals**: live and automatically admitted under the owner's standing KOGL Type 1 text-only approval. This does not allow attachments or media.
2. **Private machine translation and analytical drafting**: after a published Korean original arrives, a bounded model run can draft one English translation segment for each preserved Korean source segment and propose substantive analytical observations with precise Korean source excerpts and source-paragraph indices. The draft is **unreviewed**, never an IPR editorial decision, and cannot appear on the public website.
3. **Editor-approved public translations and analysis**: after checking the bilingual translation and separate analytical assertions, the owner may release two interconnected public pages through an authenticated manual workflow. This uses an exact reviewed-packet digest and source SHA, not a self-asserted `approved: true` model output.

## Automation / private editorial inbox

`.github/workflows/korea_english_owner_draft_handoff.yml` runs after successful standing Korea original-text release and once daily. It selects up to **two not-yet-reviewed, not-yet-delivered** publicly released Korean originals. It uses already available repository Secrets `ANTHROPIC_API_KEY`, `IPR_SMTP_USER`, `IPR_SMTP_APP_PASSWORD`, `IPR_PREVIEW_TO`, and `IPR_EDITOR_TO` when configured.

If any credential is missing, the workflow **holds without a model call or send**. Otherwise, each valid, unreviewed JSON draft is sent only to the owner, never automatically to Dylan or public Pages. Successful delivery commits **only** the exact source/draft hash, model identity and timestamp to `research/korea_english_draft_handoff_receipts.json`; model output and original bodies never enter source-control commits or workflow artifacts. Failed sends do not count as successful handoffs. The receipt avoids daily duplicate sends.

The default model is `claude-sonnet-4-6` (the repository's existing model family). Maximum input per article: 16,000 UTF-8 bytes and 50 source segments; larger originals HOLD rather than silently receive truncated English. Calls are capped at two per candidate; at most two candidate documents per run. No broad-model scraping or unsupervised political opinion generation.

## Actual inaugural document

The first public source is `korea-policy:156784297` (22 extracted original-text segments, 969 UTF-8 bytes, source SHA `ef066346d991369fe99a1ad8db5dae85979c05c484d0f77462c25b30684b0284`). A separately prepared `machine_unreviewed` first English translation and three-claim source-grounded analysis draft was produced for owner review. **It was not supplied as an editor-approved packet in this engineering PR**, and the public English registry remains intentionally empty.

For the source, the original Korean document records a distribution timestamp of October 4, 2026. The Korean official portal's publication date is October 6, 2026. An English article must preserve that distinction.

## Approve and release one English package

1. Verify and correct the privately delivered JSON's **every** translation against the original Korean text, including publication dates, personnel names, technical language, and qualifiers. Compare the exact Korean quotations and source indices for each substantive analytical claim. Distinguish the issuing ministry's assertions from independently confirmed facts and review the `limitations_en` text. Structural tests **do not** replace bilingual fact-checking.
2. Only after genuine editorial review, set the JSON's `review` object to:
   `{"status":"editor_approved","reviewer":"VSSpowerlifting","reviewed_at_utc":"<current ISO UTC timestamp>","translation_semantics_checked":true,"analysis_fact_checked":true,"attribution_checked":true,"source_limitations_checked":true}`.
3. Commit only the reviewed JSON file to `research/korea_english_reviewed/<newsId>.json` on `main` via a human-reviewed pull request. The code will not consider the mere existence of this file as public approval.
4. Compute the **canonical, Unicode-preserving JSON SHA** (hash JSON, not its formatted file bytes) using:
   `python -c 'import hashlib,json,sys; print(hashlib.sha256(json.dumps(json.load(open(sys.argv[1],encoding="utf-8")),ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest())' research/korea_english_reviewed/<newsId>.json`
5. On the repository GitHub Actions tab, run **Korea — Owner-reviewed English translation and analysis release** on `main`. Enter `korea-policy:<newsId>`, the exact canonical reviewed-packet SHA, and affirmatively select **approve editorial translation and analysis**. The authenticated owner-only workflow re-verifies the entire review against the already-published immutable Korean source. It updates only `research/korea_english_publications.json`, `output/korea.html`, the respective translation and analysis HTML pages, and their matching three Pages paths. No production SQLite or other country pages are published.

The resulting public routes will be `/korea-translations/<newsId>.html` and `/korea-analysis/<newsId>.html`, cross-linked to the exact original. Analysis is identified as **IPR editor-reviewed source-grounded interpretation**, not as independent verification of every government assertion. No photographs, whole HWPX, video, PDF or other embedded third-party material is rehosted.

## Release integrity and known limits

Public original text registration, reviewed English registration, model-generated drafts, human semantic validation, source rights, and public Pages release are deliberately distinct. Passing a model schema, an exact Korean quote, or an SHA proves provenance and traceability—not that every English sentence conveys the Korean correctly or that a geopolitical claim is true.

Successful workflow merge and green offline CI **do not equal** a reviewed/approved published English page. The first live, editor-reviewed end-to-end publication must pass the owner dispatch and public deployed-byte readback. The Korean Desk may be fully operational for original texts while editorial publication still awaits a real reviewed packet.
