# PLA Daily first-seen discovery order

The PLA Daily scraper has enumerated article URLs into a Python set and
returned list(seen). A set is valid as a membership guard, but its iteration
order can vary with PYTHONHASHSEED and process history. The adapter wrapper
passes that list directly into source fetching, and the pipeline preserves
input order through title deduplication, storage, and its fresh-article
model-dispatch cap.

That means identical listing pages could acquire different article IDs,
have different source ordering under the daily 55-article total cap,
and send different fresh records for paid analysis. Canonical duplicate
**selection** is already deterministic; the ordering of independent
nonduplicate articles was not.

## Narrow fix

- Keep seen as a set for membership checks and duplicates.
- Append the canonical URL at its first discovery to an ordered list.
- Return that ordered list. The predefined _SECTIONS traversal order and
  the original listing DOM order now determine the same result each time.
- Do NOT sort by lexicographic URL, invent publication-time chronology,
  alter authority tiers, modify extraction/parsing or refetch anything.
- The one-time change from ungoverned set order to observed first-seen
  listing order may affect which fresh records are dispatched at the
  existing cap. This is an explicit, reviewed prioritization impact,
  not an increase in the model budget or a data rewrite.
- Existing source date filter, URL pattern, scope and dedup count stay intact.

Offline synthetic listing tests assert section order, in-page order, same
URL seen in multiple sections, old-date/index exclusion, stable results
under five independent PYTHONHASHSEED processes, and pipeline dedup order.

CI must pass the focused no-network suite, existing PLA body/date tests,
dedup authority tests, then full repository offline/Chromium/render tests.
Tracked SQLite and public output must remain unchanged. No production
collect, paid analysis, workflow schedule change, or historical DB reorder.
