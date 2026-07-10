# EDITORIAL_QA_CHECKLIST — The PLA Watch weekly edition

Run before publishing any edition. Automated checks are enforced by
`python3 scripts/validate_output.py`; everything else is human judgment.
Final analytical judgment and published prose remain human-controlled.

## Automated (deploy gate — must pass)

- [ ] `validate_output.py` exits 0: sidecar/HTML pairing, filename = date =
      week_ending, week span 6 days (pilot exempt), issue number unique and
      chronological, n_significant ≤ n_articles, trail ≤ n_articles, trail
      entries carry title/url/source, body text present, index + archive
      link the edition, no unrendered Jinja.
- [ ] Review new **warnings**, not just errors: missing LinkedIn file,
      undated trail entries, trail dates outside the week, cadence gap,
      n_significant with no significant trail entry.

## Source-to-claim (editorial-skeptic + mandarin-source-reviewer)

- [ ] Every named event, unit, rank, quotation, and date in the prose traces
      to a specific source-trail record. No claim rests on memory or vibes.
- [ ] Chinese terms, titles, and translations come from the source records —
      never composed at edit time. If the original wording is unavailable,
      say less, not more.
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

## Edition mechanics (publishing-qa)

- [ ] Title format "The PLA Watch: [theme]"; dek 1–2 sentences.
- [ ] Signal line ≤ 28 words or intentionally omitted.
- [ ] edition_type (significant/routine) matches what the prose argues.
- [ ] Week-ending date is the Saturday; issue number = previous + 1.
- [ ] Cover image credit present and marked "visual context only".
- [ ] LinkedIn .txt written, ends with the standing corrections invitation,
      and its source URLs match the edition's trail (no extras, no inventions).
- [ ] Local preview of post + index + archive at desktop and ~375px.

## After publish

- [ ] Update PROJECT_STATE.md (edition count, any new gap or irregularity —
      recorded, not explained away).
