# Desk source provenance matrix — eight desks (2026-10-13)

Status: Milestone A evidence for the Desks Source Atlas (parent issue #498).
Generated from `config/desk_source_provenance.json`, `desks/registry.json`,
`config/shadow_source_workflow_bindings.json`, the shadow manifests and the
gated reference loaders by:

```bash
.venv/bin/python scripts/desk_source_provenance.py --no-health --as-of 2026-10-13 --matrix -
```

The block between the markers is regenerated output; `tests/test_desk_source_provenance.py`
fails if it drifts. Run health is deliberately omitted (`--no-health`): it changes every
run and belongs only to the rendered page. Schema and rules:
[DESK_SOURCE_PROVENANCE_SCHEMA_2026-10-13.md](DESK_SOURCE_PROVENANCE_SCHEMA_2026-10-13.md).

## How to read it

- **production** — a source in a desk manifest validated under the full manifest contract,
  on a collecting desk. Only these may carry run health, and only by exact slug match.
- **shadow** — declared in a shadow manifest and workflow binding; not admitted to production.
  No health, no record count.
- **public_reference** — an approved official publisher index, bibliography or reviewed link
  lane. Links are counted as links; a bibliography is never a collection count.
- **access_blocked** — the registry records that the source refused or could not be reached.
- **insufficient_evidence** — nothing recorded supports a stronger class. Unknown stays unknown.

"unknown" in the Languages or Access column means the governing manifest does not declare it.
"declared" in Publisher URL means the registry carries a publisher URL for that family.

## Findings for owner review

These are recorded, not resolved. None changes a desk status, a source class or a public label.

1. **US Indo-Pacific limits vs. a disabled shadow manifest.** The registry limit says nothing
   has been configured for the desk, while `shadow/us_indopacom/manifest.json` declares
   `us_dvids_indopacom` (shadow disabled). The adapter shows no source on the US panel and lists
   DVIDS only under "not shown on any desk panel". Whether the limit text should acknowledge the
   disabled declaration is an editorial decision.
2. **Singapore shadow duplicate.** `shadow/singapore_mindef/manifest.json` still declares
   `sg_mindef_releases`, which is now a production slug. It is shown once, as production; the
   shadow copy is listed as undisplayed and never contributes health.
3. **Vietnam "Government portal".** Read once at the homepage, no publisher URL, no declaration
   and no approved reference: classified `insufficient_evidence`.
4. **Japan MOD access method.** `shadow/jp_mod/manifest.json` declares no `access_method`, so the
   two MOD feeds show access "unknown" rather than an inferred value.
5. **China desk limit filtering.** `public_desk_limits` in `site/preview/generate_preview.py`
   omits the China limit about an unimplemented source once every configured source has stored
   records. The adapter preserves all three limits verbatim; whether the Atlas panel applies the
   same rule is a Milestone B decision, not an adapter change.
6. **"Last successful collection" excludes `not_implemented`.** `scripts/source_health_report.py`
   treats any `is_failure = 0` row as success; the adapter counts only the four success statuses,
   so a `not_implemented` or `skipped_disabled` run never reads as a successful collection.

<!-- BEGIN GENERATED MATRIX -->
| Desk | Status | production | shadow | public_reference | access_blocked | insufficient_evidence | Reference links | Limits | Conflicts |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| China Desk | `live` | 5 | 0 | 0 | 0 | 0 | 0 | 3 | 0 |
| Singapore Desk | `live` | 1 | 0 | 0 | 0 | 0 | 0 | 4 | 0 |
| Japan Desk | `shadow` | 0 | 3 | 0 | 2 | 0 | 0 | 4 | 0 |
| South Korea Desk | `shadow` | 0 | 1 | 1 | 0 | 0 | 5 | 4 | 0 |
| Philippines Desk | `shadow` | 0 | 2 | 0 | 0 | 0 | 0 | 3 | 0 |
| Vietnam Desk | `shadow` | 0 | 5 | 0 | 3 | 1 | 0 | 5 | 0 |
| Indonesia Desk | `shadow` | 0 | 1 | 1 | 0 | 0 | 17 | 4 | 0 |
| US Indo-Pacific Reference Desk | `access_blocked` | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 |

### China Desk (`china`)

Status: Live — collecting.

| Source | Class | Slug | Languages | Access | Publisher URL |
|---|---|---|---|---|---|
| PLA Daily (解放军报) | `production` | `pla_daily` | zh-Hans | html | declared |
| MOD China (国防部) | `production` | `mod_china` | zh-Hans | html | declared |
| Xinhua Military (新华军事) | `production` | `xinhua_mil` | zh-Hans | html | declared |
| Global Times — Defense | `production` | `global_times_mil` | en | html | declared |
| China Military Online (EN) | `production` | `china_mil_online` | en | html | declared |

- Production run health applies to 5 source(s), matched by exact slug; values are omitted here because they change every run.
- Limits preserved verbatim: 3. Blockers preserved verbatim: 0.

### Singapore Desk (`singapore`)

Status: Live — collecting.

| Source | Class | Slug | Languages | Access | Publisher URL |
|---|---|---|---|---|---|
| MINDEF Singapore — official releases | `production` | `sg_mindef_releases` | en | html | declared |

- Production run health applies to 1 source(s), matched by exact slug; values are omitted here because they change every run.
- Limits preserved verbatim: 4. Blockers preserved verbatim: 0.

### Japan Desk (`japan`)

Status: Shadow evaluation — not in corpus.

| Source | Class | Slug | Languages | Access | Publisher URL |
|---|---|---|---|---|---|
| Ministry of Defense — news feed (Japanese) | `shadow` | `jp_mod_news_ja` | ja | unknown | declared |
| Ministry of Defense — site update feed (Japanese) | `shadow` | `jp_mod_siteupdate_ja` | ja | unknown | declared |
| Japan Coast Guard — English press releases | `shadow` | `jp_jcg_press_en` | en | html | declared |
| Joint Staff — press releases (English) | `access_blocked` | `jp_joint_staff_en` | en | unknown | none declared |
| Ministry of Defense — press releases (English) | `access_blocked` | `jp_mod_press_en` | en | unknown | none declared |

- Limits preserved verbatim: 4. Blockers preserved verbatim: 2.

### South Korea Desk (`korea`)

Status: Shadow evaluation — not in corpus.

| Source | Class | Slug | Languages | Access | Publisher URL |
|---|---|---|---|---|---|
| Ministry of National Defense — Policy Briefing republications (Korean) | `shadow` | `kr_policy_mnd_releases` | ko | html | declared |
| Defense Acquisition Program Administration (방위사업청) — Policy Briefing press index (Korean; research only) | `public_reference` | — | unknown | unknown | declared |

- Reference lane `korea_mnd_bibliography` (bibliography) for Ministry of National Defense — Policy Briefing republications (Korean): 5 outbound link(s); schema `ipr-korea-bibliography-only/1`.
- Limits preserved verbatim: 4. Blockers preserved verbatim: 3.

### Philippines Desk (`philippines`)

Status: Shadow evaluation — not in corpus.

| Source | Class | Slug | Languages | Access | Publisher URL |
|---|---|---|---|---|---|
| Armed Forces of the Philippines — first-party publications | `shadow` | `ph_afp_articles` | en | unknown | declared |
| Philippine National Security Council — official statements | `shadow` | `ph_nsc_official_statements` | en | unknown | declared |

- Limits preserved verbatim: 3. Blockers preserved verbatim: 3.

### Vietnam Desk (`vietnam`)

Status: Shadow evaluation — not in corpus.

| Source | Class | Slug | Languages | Access | Publisher URL |
|---|---|---|---|---|---|
| Viet Nam Government News — defense tag page (English) | `shadow` | `vn_vgp_defense_en` | en | unknown | declared |
| Ministry of National Defence — English portal | `access_blocked` | — | unknown | unknown | none declared |
| People's Army Newspaper — military news and international relations listings (English) | `access_blocked` | — | unknown | unknown | none declared |
| Government portal | `insufficient_evidence` | — | unknown | unknown | none declared |
| Ministry of Public Security — foreign affairs (Vietnamese) | `shadow` | `vn_mps_foreign_affairs_vi` | vi | unknown | declared |
| Ministry of Industry and Trade — energy (Vietnamese) | `shadow` | `vn_moit_energy_vi` | vi | unknown | declared |
| Ministry of Industry and Trade — foundational industry (Vietnamese) | `shadow` | `vn_moit_foundational_industry_vi` | vi | unknown | declared |
| National Defence Journal — English edition (military journal) | `shadow` | `vn_national_defence_journal_en` | en | html | none declared |
| Ministry of Finance | `access_blocked` | — | unknown | unknown | none declared |

- Limits preserved verbatim: 5. Blockers preserved verbatim: 5.

### Indonesia Desk (`indonesia`)

Status: Shadow evaluation — not in corpus.

| Source | Class | Slug | Languages | Access | Publisher URL |
|---|---|---|---|---|---|
| Indonesian Ministry of Defense — Berita (Indonesian) | `shadow` | `id_kemhan_news` | id | html | none declared |
| Indonesian Ministry of Defense — Siaran Pers (Indonesian) | `public_reference` | — | unknown | unknown | none declared |

- Reference lane `indonesia_berita_index` (official_index) for Indonesian Ministry of Defense — Berita (Indonesian): 15 outbound link(s); schema `ipr-indonesia-external-source-links/1`; editorial status `publisher_links_not_independently_human_reviewed`.
- Reference lane `indonesia_press_index` (official_index) for Indonesian Ministry of Defense — Siaran Pers (Indonesian): 2 outbound link(s); schema `ipr-indonesia-kemhan-press-links/1`; editorial status `official_pages_spotchecked_independent_human_review_pending`.
- Limits preserved verbatim: 4. Blockers preserved verbatim: 4.

### US Indo-Pacific Reference Desk (`us-indopacific`)

Status: Access blocked — not collecting.

No source is declared for this desk.

- Limits preserved verbatim: 4. Blockers preserved verbatim: 0.

### Shadow declarations not shown on any desk panel

- sg_mindef_releases (shadow/singapore_mindef/manifest.json, desk id singapore, shadow disabled)
- us_dvids_indopacom (shadow/us_indopacom/manifest.json, desk id us_indopacific, shadow disabled)
<!-- END GENERATED MATRIX -->
