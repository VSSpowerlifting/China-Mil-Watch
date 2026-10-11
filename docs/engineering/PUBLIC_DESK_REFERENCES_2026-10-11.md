# Philippines and Vietnam: reviewed public-source reference index (P2)

Status: **code candidate, no approvals or record promotion**. The public desk pages show a dedicated, empty publication-specific reference section until a named human approves exact links. This is not an Article corpus route, shadow release, archived text, or Briefs source trail.

## Manual input and admission

- Philippines: `research/philippines_reviewed_links.json` with exact schema `philippines-reviewed-source-links/1`, one article per reviewed AFP or Philippine NSC first-party source. Vietnam: retain existing `research/vietnam_reviewed_links.json` and its version-1 checks. The public renderer accepts Vietnam MPS only and explicitly refuses MOIT under rights hold #196, even if old JSON contains positive source-link review fields.
- Each source-link entry must use its exact original-language title, official HTTPS issuing-host URL, publication date, language, pinned Git source-state SHA, human reviewer, review date, and all five human checks with positive `link_publication_approved`. Duplicate official URLs, arbitrary extra keys including source bodies, fake language, wrong host, future approval, missing reviewer, and disabled families fail the build.
- Positive flags and a syntactically valid receipt **do not independently prove permission or human review**. New nonempty public-reference lists require a separate source-specific human review and owner-accepted PR, documenting the approval and any publisher restrictions. This phase creates **no affirmative receipts** or new publisher requests.
- The generated desk page reads *only* curated static JSON—not the Git shadow state, raw captures, full text, model outputs or the external publisher. The list is rendered at build time; a tiny no-network script permits title/institution searching and filtering by issuer, language and publication month. With scripts off, every already-approved link stays visible. With an empty register, the site truthfully displays that no article references have been cleared.
- No research link becomes an IPR archive `record/<id>.html`, `archive.html` item, institutional source count, model-analyzed article, Day 7/14/30 review, published Brief citation, or a production manifest entry.

## Test and release conditions

Exact-head Python 3.9 test modules: `tests.test_public_desk_references`, `tests.test_vietnam_reviewed_links`, `tests.test_desk_rollout_contract`, `tests.test_desk_map`, plus full offline CI and production output/SQLite preservation. Check 375/1280 widths, keyboard focus, no-JS approved-link fallback, query clearing, and stale/held publication field leakage.

The current P2 branch is stacked on P1 #388; merging into `main` before P1 and full individual checks would be improper. Human source-use and owner launch decisions remain upstream gates for nonempty source references and for any later live archive admission.
