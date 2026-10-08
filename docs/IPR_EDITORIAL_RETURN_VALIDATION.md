# Dylan's edited text file — safe IPR Briefs editorial intake

This phase begins **only after** a successful owner-authorized SMTP delivery.
The outgoing Friday attachment is a *provisional, unnumbered* source-backed
machine draft, not a completed Saturday-ending Brief.

## Human handoff and custody

1. Ben retains the original attachment from the message in **Gmail Sent**.
   Do not rely on a GitHub Actions artifact: the workflow intentionally stores
   no unpublished draft in a public artifact or repository.
2. Dylan edits only the text under **EDITABLE MANUSCRIPT**, preserving the
   packet header and entire **SOURCE APPENDIX — DO NOT EDIT**.
   He retains the supplied section headings and SOURCE RECORD IDS lines,
   revising cited IDs only among the listed original records.
   He should flag translation questions and any claims whose supporting
   source does not clearly establish the fact.
3. Dylan replies to the original message with his edited UTF-8 text file
   attached. Ben saves **both** the sent original and reply attachment
   outside the public repository, on a private local directory.
4. Ben runs the offline checker from repository root:

       python -m scripts.validate_editorial_return \
         --original /private/IPR-original.txt \
         --edited /private/IPR-Dylan-edited.txt

5. A passing check confirms the packet header, cutoff, desk metadata,
   approval status and source appendix match exactly (apart from line-ending
   differences); section headings remain in order, and source-reference
   lists contain IDs that occur in the preserved appendix. It reports how many
   sections changed but never prints private draft prose to terminal logs.
6. Ben or an editorial reviewer then checks the *actual* prose and sources,
   including citation meaning, original languages, attribution, possible
   Saturday developments, chronology and completeness.
7. Only after the complete Saturday-ending corpus is reconciled may a separate
   unnumbered draft sidecar be prepared under the existing Brief contract.
   That is a future human-authorized action. The validator never writes or
   imports briefs, assigns issue numbers, generates a website, publishes
   records, triggers Claude, or emails anyone.

## Failure handling

The checker refuses missing/extra section headings, changed packet metadata,
modified source appendix or appended record URLs, missing/unknown/duplicate
IDs in source-reference lines, empty sections, completely unchanged replies,
invalid UTF-8, oversized files, and malformed packet markers.

If it refuses, **do not auto-fix or accept the draft**. Ask Dylan to send a
corrected file, or reconcile changes manually against the original attachment.
Newly discovered sources belong in the refreshed *full-week* corpus, not as
silent edits to the immutable source appendix.

The check is purely structural. It does not certify Dylan authored the edits,
verify the email sender, establish independent source authenticity or legal
redistribution rights, or guarantee factual or analytical accuracy.
Passing status is always **STRUCTURAL REVIEW ONLY — UNAPPROVED**.

## No automatic imports from Gmail

No mailbox crawler, automatic source mutation, scheduled import, write
permission or publication path is added in this phase. The attachment will be
handled explicitly by Ben when Dylan replies. Keep publication authorization
separate from editorial intake.
