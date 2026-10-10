# First-seen ordering for remaining China source adapters

A read-only audit after PLA Daily PR #312 found the same input-order loss in
three other live China sources: china_mil_online, global_times_mil and
mod_china. Each builds a set for URL membership then returns list(seen).
Identical HTML listing inputs can produce a different returned order under a
different Python hash seed.

Why this matters: the source adapter processes those URLs in order, and the
daily pipeline preserves first-seen order of independent articles while it
selects fresh records under DAILY_ANALYSIS_CAP. The title duplicate **winner**
is independently governed by a total canonical key; it is the scheduling of
otherwise unique records that can change by accident.

## Fix

Each source keeps its exact existing membership set and all original filters,
including the MOD 7-calendar-day lookback and Global Times YYYYMM URL check.
It additionally appends the URL on first acceptance into a list, returning
that list instead of reconstructing one from the set.

This preserves existing listing-section and HTML order; it does not introduce
a new cross-source source priority, sort by a fabricated chronology, expand
collection, alter the model cap or make any additional network/AI requests.
The shift from nondeterministic ordering may alter which fresh articles
reach the existing cap in the first run after deployment. That is an explicit
behavioral change to review, not a promised content parity proof.

Pure offline fixtures check date filtering, duplicate removal, all three
source-specific URL shapes, and cross-process stability for five hash seeds.
Existing MOD, Global Times and dedup suites are rerun and tracked SQLite /
public output hashes must remain unchanged. No retrospective data rewrite,
archive refetch, run scheduling change, paid API call or publication.
