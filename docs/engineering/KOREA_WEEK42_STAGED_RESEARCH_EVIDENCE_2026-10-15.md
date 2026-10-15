# Korea Week-42 private research evidence — unsigned, source-specific staging

**As of:** October 15, 2026. **Reporting week:** Sunday October 11–Saturday October 17, 2026. **Default status:** stage-only / **not Sunday-drafting, model, email, site or public-source enabled**.

## What is independently established

The genuine [October 15 post-fix Korea HWPX review run 38685903922](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38685903922) replayed the frozen Korea branch at `0595f0fd29b769cbab5dd57c2ef57af174237a67` and checked **14/14** archived HWPX original-byte/text extraction pairs: `machine_hwp_original_parity=PASS`, `scheduled_continuity=FAIL`, `human_source_review=UNMEASURED`, `production_promotion_authorized=false`. The owner reports a separate reviewer examined **all 14 originals**; the independent IPR editorial text check similarly read all 14 retained Korean bodies and documented a targeted chronological problem in [#601](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/601). Source-specific signed version-bound review, copyright/reuse and public-storage custody are still outstanding.

Original preservation and editorial publication are distinct. **October 12** was a genuine scheduled collector timeout; it remains a failed Day-7 slot regardless of source-parity or subsequent source coverage.

## Three actual Week-42 source-specific editorial notes

The current proposed notes are preserved only in `research/korea/private_research_candidates/2026-10-17.json` and checked by `core/korea_private_research_candidates.py`. They are authored short original-language-informed synopses, **not translated or mirrored article bodies**, and include topic-specific cautions:

| Typed internal ID | Canonical MND-republished source | Original HWPX distribution | Editor's intended bounded statement |
|---|---|---|---|
| `KR-MND-W42-01` | [156784873](https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784873) (portal Oct 12) | Oct 12 | The Pangyo **first** defense AI hub opened; the other four listed hubs and advanced military AI applications are future plans, **not already operating**. |
| `KR-MND-W42-02` | [156784787](https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784787) (portal Oct 12) | **Oct 9** | Korean vice-minister visited Japan **Oct 8–9**; MND reported talks about North Korea and **proposed future** AI/unmanned defense cooperation, without a signed agreement. Source document Oct9, portal posting Oct12 must remain distinct. |
| `KR-MND-W42-03` | [156785162](https://www.korea.kr/briefing/pressReleaseView.do?newsId=156785162) (portal Oct 14) | Oct 14 | Minister visited Gwangju-based Air Force 1st Fighter Wing for readiness and site inspection. **Proposed** strategic industrial-site use/base relocation is not an accomplished transfer. |

Each item fixes `source_content_sha256` of the **archived Unicode Korean original** and `hwpx_capture_sha256` of the publisher's actual HWPX response bytes, exact source URL/title, portal publication date and original-distribution date. The immutable current 14-original state commit is also exact; a source/version change or publisher route spoof fails closed. Both Korea MND and Korea Policy Briefing are clearly identified to prevent counting government republications as independent institutional corroboration.

**Deliberate exclusion:** [156785161](https://www.korea.kr/briefing/pressReleaseView.do?newsId=156785161), the Oct14 Korean War repatriation article, is blocked by the candidate source-ID allowlist due to unresolved publisher-internal **2025 versus 2026 Inje excavation date** ([#601](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/601)). Other individual claims from that article are not globally declared false.

## Strict output/control separation

The stage-only packet is **not located in** `research/briefs_editorial_evidence/`; the scheduled Sunday integration reads only that separate governed directory and is not changed by this work. No Korea source has been added to the Sunday writer. No source body, photo, HWPX attachment or translation is copied into this research packet.

All packet status fields explicitly say: `publication_authorized=false`, `model_use_authorized=false`, `source_rights_approved=false`; the candidate item status is `held-not-sunday-or-model-eligible`. A short authored synopsis does not grant automatic license to use these notes in a paid model. The owner-reported human coverage is a separate string that **cannot** be silently promoted into signed human source approval.

`python -m scripts.check_korea_private_research_candidates --week-ending 2026-10-17 --as-of 2026-10-17` emits only a bounded set of typed source IDs, a count and explicit false flags—**never publisher bodies or synopsis text**. The focused GitHub Actions workflow is pull-request/manual only; it uses no model, SMTP, publisher requests, auth secrets, collection state pushes, artifacts or production output.

The offline tests challenge original HWPX/text hashes, source dates, fake user rights, extra body fields, duped IDs, source substitution, malformed JSON, source version mismatches and false Sunday/model flags.

## Remaining promotion gates before any actual private Sunday research use

1. Receive a limited written/recorded, version-bound reviewer attestation for the actual 14 originals or targeted three (date/reviewer scope and source pin; no public posting of a reviewer's private personal details).
2. Document exact government publisher text/republication reuse rights and distinguish copies, translation, images/embedded files and external paid-model input. Human source review does **not** grant copyright rights.
3. Verify separately authenticated collection continuity from the prospectively new seven scheduled slots, without rewriting the October 12 failure.
4. If/when the owner approves the desired **source-specific private drafting scope**, design a separate gated integration PR that refuses Korea evidence **before any model or editor email** absent exact source-version and week approval. This staging PR grants no such approval.
5. Use a private **no-send** writer/manuscript and citation QA trial before any explicit weekly editor email or publication permission. Preserve the source-specific [#601](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/601) hold and private archive custody problem [#520](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/520).

**No production release requested.** This document is a review/drafting design record, not source approval or a deployment instruction.
