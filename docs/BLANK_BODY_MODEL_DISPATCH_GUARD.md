# Blank original text: hold before paid analysis dispatch

## Measured failure pattern, October 9

Tracked SQLite and the original October 6 and 8 Daily Actions logs
establish that articles **1856, 1857 and 1944** repeatedly produced
failed/empty translation results on both days, **and all three rows have
blank stored original bodies**. The review used the existing source-
attributed SQLite audit on a scratch copy; article IDs and flags only,
without article text or site mutation.

The tracked October 8 snapshot held ten Daily-eligible blank-body
records: eight from Global Times Military and two from PLA Daily. Every
one of the eight Global Times blanks was scraped before the documented
September 16 flow-template extractor repair. **This does not establish
that any publisher really issued a blank report, that pages are currently
retrievable, or the reason a model produced a particular response.**

## New dispatch policy

`pipeline.hold_blank_original_bodies` separates records with actual
original source prose from records with **missing, non-text or
whitespace-only** original body fields, before the model queue is
capped or a model client is constructed.

It guards all three input lanes:

- New articles discovered/stored today.
- Prior records that passed relevance but have unfinished analysis.
- Previously stored, never-scored live and archive records.

Only candidates with a genuine nonblank stored source text consume
the 55-slot Daily model cap or its backlog reserve. The contents and
original order of valid candidates are unchanged. A warning reports
aggregate withheld counts by lane. The **original article records,
scrape provenance, original text, source identity, retry histories and
processing states are unchanged**. Blank-body records remain eligible
in the *stored* backlog inventory for human review; they are simply not
dispatched to paid model tasks until their source text is recovered.
Thus `stored_daily_queue_eligible` and `model_dispatch_eligible` are
different counts. Existing history/recovery audits can still see them.

No empty body is declared `terminal` or `no_usable_prose`; a failed
extractor is never proof of publisher silence. The change does **not**
automatically refetch, write recovered prose, resume paused articles,
change the cap, change the model or send anything to an editor.

## Cost / outcomes

This prevents **future paid relevance and translation attempts** for
records whose original bodies are blank *at queue construction time*.
It does not reverse historical token expense or prove that all of
October 2–8's 20 translation failures came from blank inputs.

The three recurring records above are directly confirmed as blank in
the tracked snapshot. This explains why they are **predictably poor
candidates for full-text translation** using the stored input, rather
than attributing the original provider response to an unsupported cause.

## Verification and release gate

Synthetic no-network tests cover all three lanes, non-string and
whitespace values, retained content, repeated IDs, cap/reserve selection
accounting, and the placement of the guard after storage and before the
model queue is capped. The dedicated CI runs the existing source queue
audit against actual tracked SQLite and logs aggregate blank-body
counts; it proves original database/output bytes were unchanged.

The full repository offline/Chromium/render checks and the dedicated
exact-head checks must both pass before owner merge. The changed
production behavior is a **model dispatch safety guard only**, not a
content verdict or authorization for any new calls. No production run
was executed in the PR.
