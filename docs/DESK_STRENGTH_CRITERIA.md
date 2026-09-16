# Desk strength criteria

What it takes for a desk to be called operationally strong, and what each
weaker word is allowed to mean. Written because "the Japan desk works" and "the
Japan desk discovers documents it cannot read" had been said about the same
desk in the same week, and only one of them was true.

This document defines **testable** criteria. Where a criterion cannot be
settled by evidence already in the repository — a ledger, a manifest, a
database, a review packet — it says so and names what would settle it.

`desks/registry.json` remains authoritative for a desk's status and public
presentation, and each desk's manifest remains authoritative for its sources.
Nothing here changes either. This document governs the **vocabulary** those
files are allowed to use about themselves.

---

## 1. Seven stages, and no borrowing between them

A desk is not one capability. It is seven, in order, and each is measured on
its own evidence:

| # | Stage | The question it answers | Settled by |
|---|---|---|---|
| 1 | **Discovery** | Can we learn that a document exists? | listing/feed status in the ledger |
| 2 | **Retrieval** | Can we fetch that document's bytes? | `retrieved` / `challenged` / `fetch_failures` |
| 3 | **Extraction** | Can we turn those bytes into correct text? | `extraction_failures`, stored body lengths |
| 4 | **Storage** | Is the result stored identifiably and once? | corpus counts, duplicate rate, state hash chain |
| 5 | **Analysis** | Does the record survive the processing pipeline? | analysis completion, terminal-state counts |
| 6 | **Public rendering** | Does a reader see it, described honestly? | renderer output, validator |
| 7 | **Promotion readiness** | Should any of this become public coverage? | checkpoint reviews + owner sign-off |

**A verdict at one stage never implies the next.** The rule this encodes:

> A desk must not be called functional because discovery works.

Discovery working means stage 1 passes. It says nothing about stages 2–7, and a
desk whose stage 2 fails is **access-constrained**, not functional. The honest
phrases are fixed:

* *discovery works, retrieval does not* — say exactly that; never "partial
  coverage", never "working";
* *retrieval works for one document family only* — name the family and its
  share; a 6 % yield is not "collecting";
* *collecting* — stages 1–4 pass on the desk's declared scope;
* *functional* — stages 1–5 pass;
* *public* — stage 6, and only after stage 7.

---

## 2. The criteria

Each criterion is **PASS**, **FAIL** or **UNMEASURED**. `UNMEASURED` is a real
verdict and is never rounded to `PASS`.

### C1 — At least one reliable authoritative listing path
*Stage 1.* The desk has at least one official, openly accessible route that
enumerates documents: a feed, an index, a sitemap, or a documented API.

**Measured by:** `listing_status == "ok"` on every scheduled run in the
evaluation window, with no run recording `listing_failure`.
**Fails when:** the only enumerating route is an index the edge refuses, or
when document URLs would have to be guessed. **Guessing URLs is not a listing
path** — a namespace an institution has not published to us is not discovery,
it is enumeration, and this project does not do it.

### C2 — Compliant access under robots and published policy
*Stage 1–2.* `robots.txt` is readable and permits every path touched.

**Measured by:** `robots_status == "allowed"` on every run.
**Fails when:** `robots.txt` is unreadable, or disallows the paths needed.
**A 403 on `robots.txt` and a 404 on `robots.txt` are different facts.** A 404
means no file exists and no restriction is stated. A 403 means the host is
refusing to tell this client the rules, and collection then has **no permission
basis** — which is a blocker on its own, independent of whether some other
endpoint happens to answer. Recording the distinction is mandatory.

### C3 — Deterministic canonical URLs and dates
*Stage 1, 4.* Every record has one canonical URL derived by a pure function of
the discovered link, and one publication date derived by a stated rule.

**Measured by:** re-deriving both from stored inputs reproduces the stored
values, for every record.
**Fails when:** a date is the feed's generation time rather than the document's
publication date, or when the URL-encoded date and the feed date disagree
without a ruled precedence. Where they disagree, the rule must be written down
and the disagreement rate reported — not averaged away.

### C4 — Successful body or document retrieval
*Stage 2.* A stated, measured share of discovered documents yields bytes.

**Measured by:** `retrieved / selected` per run, and the same ratio per
document family.
**Fails when:** the overall yield is below the desk's declared threshold, or
when yield is concentrated in one document family that is not representative of
the desk's declared scope. **Concentration is a failure even when the ratio is
not** — a desk retrieving only one recurring administrative notice type has not
retrieved its scope.

### C5 — Extraction and encoding integrity
*Stage 3.* Retrieved bytes become correct text in the correct encoding.

**Measured by:** fixture tests over real captured responses, asserting body
text, character encoding, and that navigation chrome is not mistaken for a
body.
**Fails when:** a stored body is empty for a document that is live and has
text, or when a stored body is the page's navigation rather than its article.
An empty body for a live document is an **extraction defect**, never a source
silence, and must never be reported as one.

### C6 — Deduplication
*Stage 4.* Identity is by canonical URL and by content hash of extracted text.
Never by title.

**Measured by:** duplicate rate per run, and a test asserting that a recurring
official title produces as many records as there were publications.
**Fails when:** dedup is title-derived, or when the duplicate rate is
indistinguishable from a stalled listing.

### C7 — Honest result taxonomy
*Stages 2–5.* Every run ends in one of the repository's existing results
(`ok`, `ok_no_publications`, `ok_all_duplicates`, `ok_all_filtered`,
`listing_failure`, `extraction_failure`, `fetch_failure`, `auth_failure`), and
failures are split into **fetch**, **extraction** and **access**.

**Measured by:** the ledger.
**Fails when:** a policy refusal is filed as an outage, or an outage as a
policy refusal. An access challenge is `access_challenged`; it is not a
`fetch_failure`, and a reader comparing two desks must not be led to conclude
one ministry publishes less than it does.

### C8 — Isolated shadow storage
*Stage 4.* A shadow desk writes only to its own database, on its own branch,
and the runner cannot name the production database or `output/`.

**Measured by:** the four barriers in `docs/SHADOW_COLLECTION.md` §Isolation,
each already covered by a test.
**Fails when:** any barrier is removed, including "temporarily".

### C9 — Append-only, hash-chained state
*Stage 4.* Each run appends one ledger entry carrying `state_sha256_before` and
`state_sha256_after`, and the chain is continuous.

**Measured by:** `scripts/review_shadow_state.py`, which reports
`state chain: coherent` or names the break.
**Fails when:** the chain breaks, a ledger is rewritten, or a push is forced.

### C10 — Scheduled-run continuity
*Stage 1–4.* Every scheduled day has a recorded terminal result, and expected
empty days are distinguishable from failures.

**Measured by:** one ledger per nominal target date, with
`target_date_source` recording which rule applied.
**Fails when:** a nominal day has no ledger. A missing day is an **anomaly
requiring disposition**, not a gap to be smoothed. Historical anomalies are
never rewritten to make a later count look tidy.

### C11 — Health and freshness reporting
*Stages 2–5.* Every run publishes a health verdict, and the desk's freshness is
readable without opening the database.

**Measured by:** `health` in the ledger; `scripts/source_health_report.py` for
production.
**Fails when:** a source that has never produced a record is left silently
enabled. A source with no working collector is reported as
`not_implemented` — or reclassified — and is never hidden.

### C12 — Checkpoint-review tooling
*Stage 7.* The desk has its **own** review path that produces a provenance-
verified, deterministic evidence packet from a named state commit.

**Measured by:** the tool refuses to produce a publishable packet before the
checkpoint has arrived, and two runs of the same state commit are byte-
identical.
**Fails when:** a desk is reviewed with another desk's tooling. Review tooling
encodes a desk's URL shapes, date rules and document kinds; pointing Singapore's
reviewer at Japan would silently validate Japanese records against Singaporean
assumptions.

### C13 — No promotion on elapsed days alone
*Stage 7.* Thirty collecting days is **necessary and never sufficient**.

**Measured by:** promotion requires, together: 30 consecutive collecting days;
every scheduled day with a terminal result; every anomaly dispositioned; the
Day 7, Day 14 and Day 30 human checkpoint reviews completed; C1–C12 all `PASS`;
and an owner sign-off recorded in `DECISION_LOG.md`.
**Fails when:** a day count is quoted as progress toward public status. Elapsed
days live in the ledger and are deliberately not restated in documentation or
on any page — a number copied out of a ledger goes stale the next day and reads
as a promise.

---

## 3. Applying this to a blocked desk

A desk that fails C1 or C2 has no compliant path and cannot be repaired by
effort. The permitted responses are, in order:

1. **Find another openly accessible official route.** A different official
   index, an official feed, directly linked official PDFs, or another official
   publication system of the same institution.
2. **Retain as declared-only.** The desk keeps its declared scope and an honest
   status (`access_blocked`, or `shadow` with its constraint stated), collects
   nothing it cannot collect compliantly, and claims nothing.
3. **Replace the desk**, on evidence, through the comparison in
   `docs/DESK_RELIABILITY_REVIEW_2026-09-16.md` §7.

The responses that are **not** permitted, at any coverage cost: solving or
bypassing an access challenge, impersonating a browser, rotating identities,
using residential proxies, ignoring `robots.txt`, or enumerating a URL
namespace the institution has not published. Defeating a challenge destroys the
capability the rule protects — an institution must be able to recognise this
collector and refuse it.
