# EDITORIAL_QA_CHECKLIST — Indo-Pacific Record Briefs

Run before publishing any brief (DECISION_LOG 2026-09-23). The existing issues
were published as *The PLA Watch* under the earlier form of this checklist; no
new issue is. Automated checks are enforced by `python3
scripts/validate_output.py` and, for a brief, `scripts/author_brief.py check`;
everything else is human judgment. Final analytical judgment and published
prose remain human-controlled.

## Automated (deploy gate — must pass)

- [ ] `validate_output.py` exits 0: sidecar/HTML pairing, filename = date =
      week_ending, week span 6 days (pilot exempt), issue number unique and
      chronological, n_significant ≤ n_articles, trail ≤ n_articles, trail
      entries carry title/url/source, body text present, index + archive
      link the edition, no unrendered Jinja.
- [ ] Review new **warnings**, not just errors: missing LinkedIn file,
      undated trail entries, trail dates outside the week, cadence gap,
      n_significant with no significant trail entry.
- [ ] `scripts/author_brief.py check <brief.json>` exits 0: collection
      recorded; two or more live desks, or an approved single-desk exception;
      every declared desk has trail entries, and every entry keeps its desk
      and `lang`; every cross-desk claim cites each desk it compares;
      coordination wording rests on a stated record; numbered only once
      approved.

## Source-to-claim (editorial-skeptic + mandarin-source-reviewer)

- [ ] Every named event, unit, rank, quotation, and date in the prose traces
      to a specific source-trail record. No claim rests on memory or vibes.
- [ ] Chinese terms, titles, and translations come from the source records —
      never composed at edit time. If the original wording is unavailable,
      say less, not more. The same holds in every source language.
- [ ] Novelty/escalation test: would this claim survive "show me the second
      source or the prior baseline"? Repetition alone is not novelty.
      Placement, seniority, terminology shift, or source hierarchy are the
      admissible arguments.
- [ ] No banned superlatives (unprecedented / historic / largest / first /
      turning point) unless the article data explicitly supports them.
- [ ] Intent language: official media shows *messaging*, not intent.
      "The framing suggests…" not "Beijing intends…".
- [ ] Thin week (<4 days observed): title and dek do not promise a full
      weekly readout; prose says "in the days observed".

## Cross-desk (editorial-skeptic)

- [ ] The brief opens on one concrete development, documented by the trail
      entries its `development` cites.
- [ ] Each institution is described from its own records and fairly; no
      desk is characterised through another desk's coverage of it.
- [ ] Similar timing or wording is reported as exactly that, never as
      coordination. Coordination is claimed only where a cited record
      states it.
- [ ] A desk with no record of the development is reported as silent in
      the collected record, not as silent in fact.
- [ ] A single-desk brief carries its approved exception, and its prose
      does not imply a comparison it cannot make.

## Edition mechanics (publishing-qa)

- [ ] Title never begins "The PLA Watch:" — that was the predecessor's
      format and stays only on the existing issues; dek 1–2 sentences.
- [ ] Signal line ≤ 28 words or intentionally omitted.
- [ ] edition_type (significant/routine) matches what the prose argues.
- [ ] Week-ending date is the Saturday. The issue number is assigned at
      approval — never in a draft, never reassigned, never read off the
      week, and not at all while No. 14 is unreconciled
      (`core/brief_contract.py`).
- [ ] Cover image credit present and marked "visual context only".
- [ ] LinkedIn .txt written, ends with the standing corrections invitation,
      and its source URLs match the edition's trail (no extras, no inventions).
- [ ] Local preview of post + index + archive at desktop and ~375px.

## After publish

- [ ] Update PROJECT_STATE.md (edition count, any new gap or irregularity —
      recorded, not explained away).
