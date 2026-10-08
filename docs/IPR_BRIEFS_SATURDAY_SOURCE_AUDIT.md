# Saturday source reconciliation for IPR Briefs

A Friday draft sent to Dylan is **provisional** through Friday. It does not
include Saturday's developments and does not become a complete-week Brief
merely because its generation and email delivery succeeded.

The new Saturday audit is a manual-only read-only check that identifies
Saturday-dated records the current repository has stored and detects changes
in the *currently offered* Sunday-Friday source-candidate set against the
original Friday attachment.

## Fast, secretless GitHub Actions audit

On Sunday or later, open **Actions → IPR Briefs Saturday Source Audit (No
Model, No Send)**. Select Run workflow on main and enter the edition's
week-ending **Saturday** in YYYY-MM-DD format, such as 2026-10-10.
The workflow refuses Saturdays that have not ended in New York.

The output is aggregate-only: stored Saturday records by live desk,
Saturday candidates not screened out, and Friday source-candidate counts.
It does not print unpublished manuscript prose, record bodies, source URLs,
or titles. It does not authorize publication.

## Stronger comparison against the Friday packet

Keep the original Friday attachment from the message sent to Dylan in a
private local directory; it is not placed in public Actions artifacts.
After Saturday has elapsed and the corpus has been updated, run from repo root:

    python -m scripts.weekly_briefs_saturday_audit \
      --saturday 2026-10-10 \
      --friday-packet /private/IPR-Briefs-Provisional-2026-10-10.txt

The original source appendix must be a Friday provisional packet with a
matching Saturday edition identity. The report counts:

- newly offered Sunday-Friday candidate IDs not present in the sent Friday
  packet (which may reflect late collection or changes in screening state);
- IDs originally offered that are no longer offered by the current corpus;
- changed desk assignments for original source IDs;
- stored Saturday records, and Saturday candidates by desk.

The comparator **does not silently add sources** to the article, authorize
new citations, decide which records matter, or change Dylan's document. A
count difference requires human reconciliation. Current candidate membership
is not a snapshot of what the website served on Friday; a screening decision
may change after the packet was sent.

## Hard editorial boundaries

The report cannot prove a source did *not* publish anything on Saturday;
missing sources, late captures, backdated publications, edited PDFs, source
rights, model hallucinations and entity/taxonomy errors still require manual
review. Candidate records and model-selected evidence are not the same.
The tool reads the *current* tracked database; running before Saturday
collection is complete can underestimate Saturday records even on Sunday.

The full process remains:

1. Dylan revises Friday's provisional manuscript.
2. Ben reviews Saturday's stored developments and rechecks Friday source drift.
3. Ben reconciles the *complete-week* source corpus, checks language and
   attribution, and requests corrections if the article's angle or citations
   need to change.
4. Only afterward may Ben authorize a separate unnumbered editorial sidecar,
   readiness/approval workflow, numbering, and eventual publication.

This CLI and workflow perform none of those owner-only operations, do not
send Gmail messages, do not call Claude and never write database state.
Keep IPR_EDITOR_DELIVERY_ENABLED aligned with the separately verified
Friday workflow gates; this audit has no effect on that variable.
