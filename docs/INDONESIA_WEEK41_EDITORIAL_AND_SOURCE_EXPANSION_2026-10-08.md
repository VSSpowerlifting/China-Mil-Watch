# Indonesia Desk — week-41 editorial bridge and source expansion (October 8, 2026)

## Decision and scope

**Proposed, not approved for publication or production promotion.** This change prepares a read-only, exact-week provisional Indonesia source for the Friday October 9 writer and sets up a **disabled** research gate for expanding the Kemhan source family. It does not collect additional data, touch \`pla_watch.db\`, mark an editor's human review complete, enable a public desk, or publish/send a Brief.

The existing Indonesia shadow collector operates solely on the Ministry of Defense's **Berita** category and preserves originals under the isolated \`shadow/indonesia-kemhan\` branch. On October 7, the scheduled collector run \`37693074726-1\` passed with 15/15 article fetches and extractions, 2 inserts, 13 duplicates, zero failures, and 16 total stored articles. The state is pinned at \`dc6a76193d17f3513c32ec1de02902ed01421437\`, not in production.

## This week's source selection

\`research/indonesia/friday_2026-10-09/official_source_candidates.json\` provides **one** narrowly checked publisher account:

- **Publisher:** Kementerian Pertahanan Republik Indonesia / Kemhan Berita.
- **Article date:** October 6, 2026; **meeting date:** October 5, 2026.
- **Subject:** Minister Sjafrie Sjamsoeddin's courtesy call with outgoing Singapore defense attaché ME7 Gan Chee Weng Melvin, plus related courtesy meetings, as *Kemhan* describes them.
- **Original:** https://www.kemhan.go.id/2026/10/06/menhan-sjafrie-terima-courtesy-call-athan-singapura-apresiasi-dedikasi-selama-bertugas.html
- **GitHub Actions capture evidence:** October 7 source run's exact URL, HTTP 200, \`capture_sha256 = 62e3d7d48601d2395adb1d2a3fc88d20c6b67d572a247bd9e8408fa25ae8af0b\`, linked to the shadow branch commit and immutable ledger file path recorded in the JSON.
- **Research identity:** \`ID-W41-01\`, never a numeric IPR production record ID.

The candidate is based on a public official-language page checked on October 8 and previously fetched into the shadow archive. The AI input is **two explicit analyst paraphrases**, *not* the original archived body, a translation, an independent Singapore statement, or proof of new defense policy. An assistant's source review is **not** independent human editorial sign-off. No full snapshot/copyright reuse clearance is represented by this packet.

### Sunday/Friday editorial integration

The existing Friday Claude draft still reads only full-text, eligible live-desk records for its **production** citation vocabulary. The previously merged Japan research lane remains exact-week and nonproduction. This change optionally attaches \`ID-W41-01\` from a second exact-week packet to the **same** AI call via \`--use-indonesia-research\`, which the scheduled Friday workflow now supplies alongside \`--use-japan-research\`.

- Production IDs remain **integers**; additional Japan/Indonesia source IDs remain separate **strings**. Two distinct **production** desks must still support the source-bounded cross-desk comparison.
- Every manuscript section lists its normal integer sources. A separate supplemental citation field identifies each unapproved Japan/Indonesia claim. The appendix keeps the original URLs and status visible to Dylan.
- One extra **AI-synthesized regional editorial concept** can propose a coherent framing **only when the events truly relate**. The Indonesia–Singapore attaché courtesy call, Japan's concluded Indonesia firefighting deployment, and any Singapore sources are **not** automatically one event or evidence of coordination.
- The Friday window is Sunday October 4–Friday October 9; Saturday October 10 requires a separate later-source audit. The schedule's guard continues to refuse late Saturday runs.
- For every other week, the bounded Indonesia/Japan packets return empty and the ordinary production-only writer continues.
- **Nothing** here updates the production database, the public desk registry, the newsletter, editorial approvals, numbering, or SMTP recipient. Any enabled scheduled email remains controlled by existing workflow secrets and configuration.

### Test contract and merge checks

\`tests/test_indonesia_weekly_writer_sources.py\` covers date gates, missing and altered packets, wrong original/source/hash/date, fabricated human approval and production IDs, separate citation schemas, two-production-desk source gating, one model call for three supplemental source IDs, the combined private .txt, and a no-email CLI preview. It also checks the disabled source-family gate. Existing Japan tests must continue to pass.

**Before merge:** run exact-head PR CI (full offline suite, browser/render checks, and tracked DB/output preservation); inspect the final diff; verify the scheduled writer does not include this material in other weeks; perform an original-language comparison of \`ID-W41-01\` before editorial use. No live model call or editor email is made during this PR.

## Long-term Indonesia expansion: Siaran Pers

The separate [Siaran Pers](https://www.kemhan.go.id/category/siaran-pers) listing visibly presents press-release entries and pagination. It is **not** the Berita feed. On the October 8 public inspection, its newest visible listed item was dated **August 23, 2026**, followed by March 23, 2026, and 2025 entries. Therefore a daily current-week source assumption would misleadingly report repeated silence. This source may add **historically valuable primary statements** but is **not yet proven a high-volume daily source**.

The disabled research gate at \`research/indonesia/source_expansion/siaran_pers_candidate.json\` is not imported by any collector/registry/manifest. The next **separate engineering phase** should:

1. Use the existing clearly identified native client to recheck robots permission for this exact listing and source articles, source dates, pagination and full-body extraction; avoid new network identities and any access workaround.
2. Capture real immutable fixtures for a historical Siaran Pers article, an overlap with Berita if discovered, pagination and a true empty current-date window; distinguish no recent releases from a broken listing.
3. Create a separate \`id_kemhan_siaran_pers\` adapter/source entry with independent liveness/health thresholds and article type metadata. Keep disabled until bounded first collection and review.
4. If initial evidence shows only a handful of sporadic releases, prioritize authoritative policy texts and statements over chasing record volume.
5. Evaluate TNI and service portals as **separate** sources only when native policy and listing access can be established; existing TNI robots timeout provides no permission basis.

## Graduation criteria and ownership

Day zero is October 6, 2026, not the PR date. This desk must retain 30 consecutive collecting days, correct gap/anomaly disposition, source-specific reliability thresholds, independent Day 7/14/30 full-original review, rights treatment, coherent provenance, and an explicit owner decision recorded in \`DECISION_LOG.md\` before production activation. No model draft or successful daily collector run substitutes for those gates.

**Next action after this PR:** independently read the full Indonesia original and Japanese source, conduct Friday/Saturday window checking, and review the CI results. If the independent factual reading and CI pass, consider merging this *week-specific editorial bridge* before the guarded Friday handoff. In parallel, start a separate fresh Codex phase for the disabled Siaran Pers adapter after approving its native access test plan.
