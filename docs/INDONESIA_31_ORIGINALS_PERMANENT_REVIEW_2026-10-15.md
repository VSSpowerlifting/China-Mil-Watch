# Indonesia Kemhan — exact 31-original permanent-admission review handoff

**Date:** October 15, 2026. **Scope:** genuine original-language editorial and source-rights review preparation for one official Ministry of Defense Berita source family. No beta, no automatic public source admission, no generated source summaries, and no collector/publisher fetch.

### Frozen original state

- Source branch: `shadow/indonesia-kemhan`.
- Exact archive commit: `0595c6677be24f8f0f33aecb28eec0050e36e8f9` (actual Oct 14 scheduled source commit).
- Exactly **31 existing first-party originals**; Day-7 machine checkpoint had already passed in [run 38542531580](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38542531580).
- Existing public external-link directory: **15** official Berita publisher links with original title/date, *not* authenticated published IPR source claims.
- Exactly **one** held Yonif TP 880 publisher-geography contradiction, [issue #452](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/452).
- Other **15** unpublished original identities are candidates requiring separate per-record human review. This arithmetic describes queue dispositions, not 30 release-approved documents.

### Source-original review entrypoint

After reviewed integration, manually run the pre-existing [Indonesia Desk — pinned official-link review queue](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/workflows/indonesia_pinned_reference_review_queue.yml) with its explicit existing-state-only authorization. This PR strengthens it so the actual queue uses the **above immutable 31-record commit** and refuses an unavailable/not-ancestor state, rather than silently changing roster every time the daily shadow branch advances.

Review its 14-day metadata-only artifact containing original Indonesian headline/date, canonical URL, source identity, first-seen run, and unapproved disposition. No original article body, images, source HTML or source-derived translation is uploaded by the queue.

### Review work that remains genuinely human

For each of the 30 non-held originals, a named reviewer must inspect the exact preserved Indonesian original and record: original text extraction and title/date parity, issuer, whether a reported meeting or proposed cooperation actually happened versus was merely planned, repeated-event overlap, source-page revisions, rights for *specific output types*, and correction/hold decisions. The existing 15 publisher links are **not** a substitute for this review.

Do **not** automatically infer independent corroboration from three Kemhan articles about the same Russia MTC meeting; Oct 14 source-specific research documents why. Keep the Yonif 880 geographic contradiction held unless genuine source-version evidence resolves it. Reuse requirements for original-body text, translated text, media, links and machine-model analysis are **distinct**.

The [public-information attribution language](https://ppid.kemhan.go.id/assets/attachments/ef004855a10302e9ef5f336454daf931.pdf) in a ministry PPID document is relevant to public-information use, but is **not**, by itself, a blanket license to rehost all Kemhan Berita article bodies or photographs. Verify site- and original-specific terms separately.

### Permanent release decision

This queue does not turn Indonesia live. The owner-authorized shorter collection-observation exception being reviewed in #648 cannot waive original review, rights, truthful source coverage, authenticated proof or an exact-source owner/public release PR. The final permitted corpus subset may be smaller than 31. Do not modify `desks/registry.json`, the tracked DB, site render, Sunday writer or deployment from this queue.

**Pass condition of this PR only:** immutable source-head ancestry, 31 metadata entries, 15 external-link entries, 1 held original, 15 new source-review candidates, zero automatically approved rows and unchanged public database/site, with exact-head focused and repository-wide checks green.
