# Sunday Briefs: immutable source-use receipt inside Dylan's manuscript

**Goal:** preserve the difference between official research *offered* to the AI writer and official research **actually cited** in the single synthesized article. Neither implies human verification or approval.

## Why

The model may correctly reject unrelated Japan/Vietnam candidates when choosing a coherent regional theme, but the source appendix contains **all** candidates. Without separate attribution, a reviewer could falsely assume each offered source contributed to the article, or pressure the writer into inventing a cross-country thematic relationship.

For the October 10 first-week packet, the model receives production source text from eligible desks and up to eight typed source-linked research candidates (Japan MOD and Vietnam MPS). Each candidate is labeled unapproved. The private receipt transparently answers: was Japan actually cited? Was Vietnam actually cited? Which exact research IDs and *manuscript sections* were affected? Which sources were offered but unused?

## Implementation

- `core/brief_editorial_source_use.py` accepts only the model's section-level numeric production citations, typed external research citations, and the existing source trail/evidence roster. The composer independently attaches its exact bounded production model-input IDs after manuscript validation. The receipt distinguishes this subset from the larger production appendix, and explicitly reports **UNATTESTED** when the composer-owned selection roster is absent. It independently refuses duplicate identities, citations to absent sources, numeric pseudo-external IDs, malformed sections, a section without any citation, or any external candidate whose status claims human approval.
- Counts are by distinct **manuscript section**, NOT independent verified factual claims. Sources are grouped by production desk and the named research-only Japan/Vietnam desks. The production portion separately shows records **listed in the editor appendix**, production records **actually supplied to the model**, and production records **cited by the model**. Research inputs are reported as **offered** or **cited**, and offered but unused research IDs are listed.
- The `scripts/sunday_editorial_handoff.py` private `.txt` gains one short `MANUSCRIPT SOURCE USE — EDITORIAL TRIAGE ONLY` section **inside** the `SOURCE APPENDIX — DO NOT EDIT` boundary. Dylan edits the prose, not the model's original source-use receipt. The existing editorial return verifier must detect tampering.
- Zero citations to research-only Japan or Vietnam is allowed when the sources truly do not support the chosen theme. The receipt explicitly says **NOT INCORPORATED** instead of asserting those countries were covered or manufacturing an institutional relationship.
- No source original bodies, complete paraphrases, private model response, user email address, URLs or unapproved drafting text are printed by the receipt module. It only uses official IDs, desk identities, offered/cited counts and section names inside the private manuscript.

## Example, a hypothetical model result only

Suppose five external sources were offered (three Japan, two Vietnam) and the model cited exactly one from each. The private receipt says:

```text
NON-PRODUCTION JAPAN/VIETNAM RESEARCH USE:
- japan: 3 offered; 1 cited in manuscript.
  Uncited research IDs: JP-W41-02, JP-W41-06
- vietnam: 2 offered; 1 cited in manuscript.
  Uncited research IDs: VN-MPS-1791199677
ACTUAL NON-PRODUCTION RESEARCH CITATIONS:
- JP-W41-01 (japan): cross_desk_comparison
- VN-MPS-1791199100 (vietnam): why_it_matters
```

Those are **synthetic test citations**, not observed model output and not evidence of source or editorial approval.

## Future Sunday/long-term source feeder

The receipt is registry-neutral on production sources and uses the existing typed-source vocabulary for external evidence. It does not require a static October 10 research roster: when the Vietnam agent's current-shadow-state feeder or Japan's future governed intake becomes eligible for the private model, the receipt will continue to describe only what that **particular manuscript** actually cites. It does not promote JCG, Japan MOD, Vietnam MPS or any shadow branch into the production archive.

This PR touches the Sunday manuscript renderer, the Sunday composer (post-validation internal input roster only), a new pure reporting module, tests and its focused workflow. It does not edit the Sunday workflow, fixed research packet, any country source collector, model prompt, SMTP logic, approval variables, Friday legacy workflow, production DB, public output or publisher rights. It therefore does not conflict with Vietnam dynamic-integration PR #243 or the Japan intake PR #244.

All existing editorial gates remain: the actual private draft must be inspected by the owner, translated/official source claims verified independently, Dylan's work reviewed, and publication specifically approved.
