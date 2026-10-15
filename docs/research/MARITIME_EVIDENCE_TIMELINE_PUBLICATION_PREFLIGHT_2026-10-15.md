# Maritime Cooperation 2026 — first Evidence Timeline publication preflight

**Prepared:** 2026-10-15  
**Status:** Engineering/editorial handoff only. **HOLD PUBLICATION.**  
**Canonical draft:** `timelines/maritime-cooperation-2026.json` (still `editorial_status: draft`)  
**Existing engine:** `core/timelines.py`, `scripts/validate_timelines.py`, `site/preview/templates/timeline.html`, `site/preview/templates/timelines.html`.  
**Existing governed editorial work:** Brief No. 15, `briefs/maritime-cooperation-2026.json`, separately approved.  
**Related:** #158 / PR #181 (initial feature, integrated by merged #279), research program #318, MINDEF source-use #326, China retirement #657/#663/#665/#675.

## Decision: do not create a second Timeline engine

The frontend and strict v1 sidecar contract already exist on `main`. Regular public builds withhold the private pilot. The launch task is an **independent editorial/source-use approval of this specific six-entry timeline**, followed by a read-only current-corpus check, deterministic approved-only build and a governed site release. An approval of Brief No. 15, source preservation, automated metadata-only desk publication, or a green CI run does **not** approve this Timeline.

## What readers will get if approved

The document distinguishes events from *reports about events* and from their publication dates. Its bounded question: how the Singapore and Chinese authorities dated Exercise Maritime Cooperation 2026, and where their published dates diverge. Do not claim an independently verified operational history, independently assessed combat capability, comprehensive regional coverage or definitive reconciliation of the starting date.

| Reported event period | Source-attributed reading to verify | Stored records / source publication |
| --- | --- | --- |
| Sep 3–9 | Chinese ministry's broader period, with the earlier boundary unexplained | 4164, China MOD, Sep 14 |
| Sep 4 | PLA Daily's preparatory meetings and planning, **not** necessarily the formal exercise beginning | 3924, PLA Daily, Sep 6 |
| Sep 5 | Opening described by MINDEF and PLA Daily | 4466, MINDEF, Sep 5; 3924, PLA Daily, Sep 6 |
| Sep 5–9 | Singapore MINDEF's exercise interval; **do not reconcile away** Sep 3–9 | 4466, Sep 5; 4472, Sep 9 |
| Sep 8–9 | MINDEF's prospective sea-phase schedule and later separate PLA Daily report | 4466, Sep 5; 4102, PLA Daily, Sep 12 |
| Sep 9 | Contemporaneous closing and subsequent retrospective | 4472, Sep 9; 4102, Sep 12 |

These rows are a **review index of the current draft**, not a new assertion that source wording, Chinese-to-English interpretation or source-use permissions are approved. The exact original-language excerpts must be inspected by a qualified human reviewer in the privately preserved evidence, without copying them into this memo.

## Four independent go/no-go gates

1. **Source identity, provenance and archive survival (mechanical).** Verify all five exact numeric article IDs (3924, 4102, 4164, 4466, 4472), original publisher URLs, publication dates, desk/source/institution identities and exact preserved excerpt bytes using `scripts/validate_timelines.py`. They are source-trail IDs in the separately approved Brief No. 15. The China retirement planner is specified to preserve all approved Brief citations; verify these *exact three* China IDs and both Singapore IDs in the proposed reduced database and newly generated routes before any 4,400-row physical retirement. A successful prior rehearsal does not substitute for the exact release database.
2. **Independent human editorial approval.** Read the actual archived originals and compare **all six** chronological entries, attributed date bases, translated/paraphrased claims, disputed date comparisons, captions and qualifications against them. Resolve corrections in the **canonical** draft. Name the actual reviewer/editor; do not retain the current `Pending owner review` credit if approved. Human authorization must identify the **exact final editorial content version**, after revisions, for `approval.content_sha256 = core.timelines.content_digest(sidecar)` and `approved_on >= updated_on`. Do not hand-author an approval merely because a digest validates. The October 5 approval of Brief No. 15 cannot be inherited.
3. **Source-use/rights review.** #326 still documents an unresolved Singapore MINDEF permissions and public full-body/excerpt question, including hyperlinking, quoted excerpts and copying preserved original text. A timeline has both outward publisher links and rendered excerpts. Obtain source-specific human rights decisions for those exact uses, including Chinese sources, or redesign the public citation presentation under a separately reviewed rights policy. This memo gives **no copyright/fair-use conclusion**, no permission, and no authority to publish full originals. A user's standing approval for automatic URLs/dates/issuer metadata at desk level does not authorize a human-authored Timeline or source-text excerpts.
4. **Release verification and explicit owner authorization.** Regenerate the private candidate outside the repo with `site/render.py --review-timeline ...`; compare at 375/1280 widths, keyboard/focus, no-JS/reduced motion, print, canonical/privacy tags and publisher/record links. Run exact-head offline CI and the approved-only site renderer plus `scripts/validate_output.py`, confirming draft/stale approval refusal, byte-determinism, page budgets, no broken preserved IDs and public sitemap/backlinks only for the approved artifact. Record the owner's express authorization of this exact approved content and exact release route. Publish through a governed site release rather than assuming that merging a source PR has deployed a page. Independently verify live `/timelines.html`, `/timeline/maritime-cooperation-2026.html` and related approved Brief/record backlinks, with the other desks unaffected.

## Private review commands

```sh
.venv/bin/python scripts/validate_timelines.py
.venv/bin/python site/render.py \
  --review-timeline timelines/maritime-cooperation-2026.json \
  --out /tmp/ipr-maritime-timeline-review
python3 -m http.server 8782 --bind 127.0.0.1 \
  --directory /tmp/ipr-maritime-timeline-review
```

Open `http://127.0.0.1:8782/timelines.html` and the private `/timeline/maritime-cooperation-2026.html` route. The review tree is expected to be **noindex/nofollow** and must be rejected by the production deploy validator. The private preview is not itself the published page.

## Decision record requested from the owner/editor

- [ ] Exact original-source reading and all six event/claim/date interpretations accepted **or** corrections enumerated.
- [ ] Individual MINDEF and Chinese publisher use/link/excerpt policies cleared for the exact *public* presentation, with permission/reference receipts retained appropriately.
- [ ] Correct author/editor name, update/review dates and separately verified digest-bound approval recorded.
- [ ] China retirement survival and actual released record links checked.
- [ ] Exact site build, browser and production-readback receipts green; owner authorizes this **Timeline** publication.

**Stop condition:** a documented GO with exact reviewed artifact and deployment receipt, or a precise HOLD reason. Until then, leave `editorial_status: draft`, the public Timelines library absent, and production artifacts unchanged. Do not broaden this review to Dossiers, new source collection or other Timeline subjects.
