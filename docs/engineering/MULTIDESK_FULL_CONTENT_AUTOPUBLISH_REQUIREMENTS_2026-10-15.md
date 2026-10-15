# Multi-desk full-content auto-release — rights, translation and analysis

**October 15, 2026 · executable fail-closed foundation, NOT production authorization.**

The owner requests a path to automatically publish ORIGINAL OFFICIAL DOCUMENTS,
independent English TRANSLATIONS, and SUBSTANTIVE IPR ANALYSIS across the
Indo-Pacific Record country desks. Source capture, editorial model access,
publisher-asset rights, translation accuracy and editorial sign-off are
**separate gates**. The owner's earlier permanent activation approval covered
verified **metadata-only URLs/dates/issuer** for AFP and Kemhan, NOT automatically
rehosting government text/PDF/photos or releasing unreviewed AI analysis.

A growing link index is a valuable archive but is not a mirrored primary
document archive. The correct technical approach is ONE reusable multi-desk
source/rights/editorial release ledger and one automated publisher for
**already qualified exact-content versions**, not a universal bypass.

## Publisher realities: prioritize licenses, not country popularity

These are **research anchors and candidates**. A family-wide license statement
is not enough to assume every PDF, attachment, photo, source or later page is
within it. Verify the actual item, the applicable version of the policy and any
named exceptions before each publication.

| Desk / source family | Full official text | PDFs / embedded media | Translations | IPR substantive analysis |
|---|---|---|---|---|
| **Japan MOD** (`jp_mod_news_ja`) | Strong first pilot: MOD site terms generally permit reuse with attribution and editing notice (confirm this exact page's scope and exceptions) | Hold until all embedded asset rights and separate terms verified | Potential under the terms, **requires bilingual source-vs-English review** | Publish separately approved IPR-authored, sourced interpretation |
| **Korea Policy Briefing MND** (`kr_policy_mnd_releases`) | Affected articles are reported as KOGL Type 1 **text-only**; verify the exact mark for each article | **HOLD** generic HWPX/PDF or photos under text-only notice | May be supported by Type 1 for the underlying text, subject to accuracy and attribution review | Independently reviewed IPR analysis only |
| **Singapore MINDEF** (`sg_mindef_releases`) | **HOLD**: current official terms require prior written permission for public rehosting | **HOLD** | **HOLD** for derivative source-expression translation absent permission or other assessed lawful basis | Original IPR-authored analysis with brief/source links can proceed under editorial checks without copying publisher expression |
| **Philippines AFP / NSC** | No automatically verified publisher-specific blanket reuse grant in this project | HOLD until asset/document use assessed | HOLD derivative text until assessed; factual summaries distinguishable from translations | Editorial, cited IPR writing separately |
| **Indonesia Kemhan Berita** | Ministry copyright noted; no confirmed blanket republication license | HOLD; Yonif 880 geography exception remains unresolved | HOLD until original-language accuracy plus rights are cleared | IPR analysis only, with semantic discrepancy caveats |
| **Vietnam MPS/MOIT/government** | Family-specific Vietnamese reuse provisions not signed off | HOLD | HOLD for translation of original wording, accuracy requires bilingual review | IPR analysis after source and claim-check sign-off |
| **Japan Coast Guard** | Separate ministry/agency source terms need review (MOD terms must not be inherited) | HOLD until assessed | Separate review | Separate review |
| **China PLA/other official** | Do not infer redistribution rights from public discoverability | HOLD | HOLD derivative-source translation absent vetted basis | Original source-attributed analysis only after independent verification |
| **U.S. USCC/Treasury/PACOM** | Different U.S. government and publisher/contractor rights regimes; do not infer anything from metadata feed | HOLD until exact item assessment | Independent review | Independently reviewed IPR analysis with official citations |

Primary publisher evidence:
- Japan MOD site terms: https://www.mod.go.jp/en/notice.html
  (attribution, modification acknowledgment, third-party rights)
- Japan MOD Japanese public data terms: https://www.mod.go.jp/j/info/contents.html
- Korea Policy Briefing copyright: https://www.korea.kr/guide/copyRight.do
  (verify KOGL text mark; assets and direct-link policy separately)
- Singapore MINDEF Terms of Use: https://www.mindef.gov.sg/term-of-use
  (written permission generally required for public content use)

**These initial default HOLDs are not definitive legal opinions or blanket
prohibitions:** item-specific licensed documents or verified written permissions
can qualify through the same validation engine; restrictions can change.

## Implemented in this PR

`core/multidesk_full_content_release.py` gives all eight desks the same
object-level release contract, including official allowlisted source families
that are mapped to their exact host and country.

1. **Source identity and collection custody:** family, exact publisher HTTPS
   URL, immutable source Git commit, SHA256 of its preserved original, issuer,
   original language and publisher date. A **separately wired trusted source
   verifier** must replay that actual origin/version. An unsigned self-claim
   of source verification is always HOLD.
2. **Rights per use, not one checkbox:** each planned
   `original_text`/`original_pdf`/`translation_en`/`analysis_en` has its
   OWN exact bytes SHA, applicable reference and SHA of rights evidence,
   scoped use, attribution, and third-party asset disposition.
   `original_pdf` cannot use text-only rights or a mere attribution notice to
   rehost embedded media. **An independently wired trusted rights verifier**
   must re-examine the actual item license/evidence, and its scope.
3. **Content QA per work, signed to the exact digest:** rights reviewer +
   source-fidelity reviewer for original text, rights + complete-document
   reviewer for PDF, rights + independent bilingual and publishing editor
   for an English translation, rights + independent factual checker and editor
   for IPR analysis. Reviewer-role HMAC keys must be independently provisioned
   and NEVER committed to GitHub or passed into model prompts. Role keys
   must be distinct, and each signature's reviewer identity must match an
   independently provisioned allowed-reviewer roster for that role. Source
   originality, translation fidelity and article truth cannot be established
   merely by possession of signing keys.
4. **Automatic release staging after all gates:** once and only once the
   independent verifiers and exact version-bound signatures check out,
   `stage_approved_bundle` can copy a narrowly allowlisted set of exact
   approved text/PDF bytes into a NEW, external, disposable `noindex`
   publishing staging directory. It escapes third-party text in its HTML
   preview, makes attribution and unofficial translations explicit, and
   refuses accidental direct writes to the repository. This is a real staged
   output mechanism, not a live Pages release.
5. **No source can authorize another source:** a Singapore original cannot
   inherit the Japan MOD text grant, and a Korea document/photo cannot inherit
   a KOGL text-only notice.

Unit tests use ONLY invented articles/keys/dates. They check missing source
validators, rights holds, forged signatures, changed original/publish version,
human bilingual/fact checker, corrupt PDFs, no media exceptions, path traversal,
missing/excess artifacts and isolated staging. Neither a passing CI status nor
owner metadata consent creates an actual published original.

## Real next build and operational prerequisites

1. **Enumerate each source family's actual rights policy and exception ledger**
   (policy URL, access timestamp, exact asset grant, edition, SHA, issuer).
   First: Japan MOD **text**, then Korea KOGL-marked **text**. Treat images,
   PDFs/HWPX and translations as independent scopes.
2. **Attach independently authenticated source-version evidence** from the
   existing private preserved capture branches. An Actions-green schedule,
   unsigned AI summary, or Git file name is not a human-authenticated original.
   Store originals only in controlled private custody until public reuse clears.
3. **Build a role-separated reviewer queue:** assign qualified native-language
   readers to compare every proposed translated sentence to the exact source,
   and editors/fact checkers to evaluate all substantive claims, citations,
   uncertainties, corrections, and independence from publisher wording.
   Generate signed, version-bound review receipts outside GitHub (separate
   secrets). General previous human source review must not be re-labeled
   **translation or analysis review** if those works did not exist yet.
4. **Wire real source and rights replay validators** to the exact original
   capture bytes and live/recorded publisher license/permission version.
   Deny on a changed source, ambiguous media ownership, missing rights evidence,
   contrary terms, or an unsigned human decision.
5. **Serialize and migrate production content index** after Korea/China's
   competing `0008` migration number is resolved. Reuse the existing
   guarded region metadata index and release serialization, not a new writer
   that races with the daily importer. Keep originals, translations, analysis
   under their own content-scope columns and table(s).
6. **Publish previously reviewed immutable artifacts automatically** to
   the public document/translation/analysis routes. Include original citation,
   license version and conditions, translation's unofficial notice, author
   byline, claim sources, correction history, and withdrawal/takedown links.
   Public PDF/assets only if EVERY included component clears rights.
7. **Run independent readback:** staging SHA = approved SHA = committed
   `main` content index = deployed `gh-pages` content bytes. Observe a
   genuine newly approved item flow end-to-end; automatic collector dates or
   synthetic tests do not establish live full-content publishing.

A fully unattended feed of freshly generated geopolitical analysis, or new
unverified machine translations, cannot be equated with finished editorial
research. Automate source observation, drafts, queue generation, deterministic
reviews and **post-approval publishing**. Changing that quality policy needs
a separately documented owner/editor decision and independent correctness
controls, not a checkbox in the metadata pipeline.

## Scope of approval recorded

The owner is asking us to ENGINEER expanded full-content automation. The
previous owner approval for automatic AFP/Kemhan metadata remains in force.
No publisher has granted broader rights merely because this module exists.
No source review receipt previously concerning the **metadata-only source**
is promoted to a signed approval of a later translation, PDF or commentary.
