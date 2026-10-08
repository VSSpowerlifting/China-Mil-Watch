# Japan Desk — October 9, 2026 Friday Briefs source supplement

**Status: provisional, unnumbered, not part of the automated corpus, not emailed, not an approved Brief.** This source packet was assembled using official Japanese Ministry of Defense public HTML pages inspected October 8. It provides a practical **manual editorial supplement** to Dylan for the normal October 9 Friday draft if the owner and editor elect to use it. It does not pretend that the Japan shadow Desk has reached production readiness.

## Why Japan does not already enter the Friday draft

The existing `weekly_briefs_editorial_handoff.yml` reads `live_editorial_desks()`, which calls `core.brief_contract.eligible_desks(load_registry())`. It then selects date-scoped **production SQLite** record IDs and requests a single source-constrained writer draft. The scaffold and Claude writer refuse fewer than two eligible, full-text-bearing production desks. These are deliberate governance checks: **Japan has no production `desks/japan/` manifest and cannot be injected as an unnumbered shadow or web-search source without violating the author's citation contract.**

The most recent observed Japan shadow state commit is `d57f0a94b2134a68b9f13fb35a0a0b8c8a4ffe13` on `shadow/jp-mod`, scheduled logical October 7 (completed October 8 UTC). Its ledger `20261008T021529+0000-37716894616-1.json` reported `health: partial`, `inserted: 0`, `stored_total: 5`, `unretrieved_total: 155`, `listing_failures: 0`, `fetch_failures: 1`, and `extraction_failures: 2`. The two exposed MOD Japanese RSS feeds yield substantial link coverage but access to most HTML article bodies remains challenged from GitHub Actions. **A public HTML page visible to a separate browser does not magically become an IPR archived original.**

This patch does **not** modify that collector, add source credentials, bypass an access challenge, add an archived Japan record, or loosen production eligibility.

## Four current-week first-party leads, researched through October 8

All four lie inside the official IPR Friday source window **Sunday October 4 – Friday October 9** in New York. However **Friday is not over**, and the Thursday research snapshot cannot substitute for the final Friday/Saturday delta review.

### Highest-value lead — Japanese international disaster-relief operations in Indonesia

**October 6:** The Japan MOD press release [JS Kunisaki Departs Indonesia after Completing International Disaster Relief Activities](https://www.mod.go.jp/en/article/2026/10/5fc631a5d1b2f36a9b697a611082a85af444ea54.html) says that the vessel departed Indonesia's **Kijing Port** bound for Japan with three JGSDF **CH-47** helicopters after the firefighting mission. The MOD reports **56** helicopter firefighting missions and **approximately 280 tons of water** released. A matching dated [original-language Japanese MOD release](https://www.mod.go.jp/j/press/news/2026/10/06a.html) independently supports those numbers as the *same institutional release in another language*, **not** an independent second institutional confirmation.

This is a promising, specific regional humanitarian assistance/disaster-relief item. An editor could compare this Japanese account to *separately verified* Indonesia source evidence if available; the mere presence of Japanese and Indonesian references in the archive does not establish joint operational coordination, and the Philippine Sanlakas exercise is a **different occurrence**. Do not describe the CH-47 missions as all taking place on October 6: that date is the MOD release and ship departure date.

### Secondary lead — Japan–U.S. alliance contacts, with an Okinawa protest

MOD separately reports:

- [October 6 meeting with Ambassador George Glass](https://www.mod.go.jp/en/article/2026/10/92045078e2a66f0957658c577e65cb0832261b17.html): minister Koizumi reiterated Tokyo's protest about a reported robbery-murder incident in Naha, requested U.S. cooperation with the investigation and stronger discipline and prevention measures, and expressed a commitment to continued work together.
- [October 6 courtesy call with Senator David McCormick](https://www.mod.go.jp/en/article/2026/10/310c36ee3042840e8ea24c951cacaa1766cba0a0.html): official account emphasizes the Japan–U.S. alliance and repeats the protest.
- [October 5 courtesy call with Senator Michael Bennet's delegation](https://www.mod.go.jp/en/article/2026/10/1aaec60496e51175d95622df5ffc904a24af6c9c.html): official account thanks the delegation for its alliance support and repeats the protest.

These are **three distinct meetings but one MOD issuing institution**. Their similar wording is not three independent confirmations of a crime, not three new incidents, and not automatically evidence of an alliance-policy change. Source date does not prove a meeting's diplomatic outcome.

## How to produce a practical text supplement now

From the repository root:

    python3 scripts/render_japan_friday_supplement.py validate

    python3 scripts/render_japan_friday_supplement.py render \
      > /tmp/japan-friday-2026-10-09-provisional-editor-supplement.txt

The read-only renderer uses `official_source_candidates.json`. It prints the full **short editorial cue and exact official source URLs**, distinguishes issuer and source dates, and keeps the caveats and Friday recheck prominently visible. It does **not** write to production SQLite, ingest web pages, ask Claude to manufacture a citation ID, send Dylan email, or turn these into approved source records.

For manual use, provide Dylan the separately labeled supplement **only after an editor reopens and reads the full official sources**. Cite them with their original URLs, **not fabricated numeric IPR archive IDs**. An approved editorial decision to include Japan-sourced context in a brief is separate from automatically marking the Japan Desk active.

## Rights and scope

[Japan MOD terms of use](https://www.mod.go.jp/en/notice.html) provide broad reuse permission for ministry content, subject to **proper attribution, clear labels for edited material, exceptions, and third-party rights**. This is a source policy, not proof that every photograph or external contribution can be republished. This research packet uses only metadata, source URLs and original analytical paraphrases, not full reproduced ministry texts or images. The official English Kunisaki release is paired to its Japanese original; editorial reviewers should keep translation provenance visible.

No article body has been newly captured to IPR or replayed under the Japan shadow admission protocol. The underlying archive rights/access process remains distinct from this time-limited editorial supplement.

## Tomorrow's decision gate

1. Complete Friday's automated production-backed Draft-to-Dylan handoff independently. Do not alter its eligible desk list or source appendix.
2. Recheck the official MOD English and Japanese releases after the Friday window and determine whether better/more consequential Japan documents appeared October 8–9. Source discovery as of October 8 is **not** a final-week completeness assertion.
3. Independently review the exact source claims and decide whether the **Kunisaki/Indonesia item** improves the Brief. This is the strongest Japan contribution candidate; do not force it into an unrelated story just to increase desk diversity.
4. If the owner accepts a Japan paragraph, give Dylan this *distinct, non-archive* appendix and source URLs, with a clear note about its status and provenance; the final Brief's real source-trail/signoff still requires the normal editorial gate and any exception documented by the owner.
5. Longer term, pursue a lawful Japanese source-body capture/rights strategy and production readiness separately; do not graduate the Japan desk simply because a web tool accessed four articles.

### Tests

    python3 -m unittest tests.test_japan_friday_supplement -v

The 18 synthetic contracts check date scope, source URL/date identity, the primary Japanese/English pair, preservation of exact source grouping, citation-ID non-fabrication, production isolation, disabled mail/publish toggles and read-only rendering.

**This PR does not change the Friday email workflow.** It gives a ready-to-review, independent written supplement to use if and only if the human editorial team wants it.
