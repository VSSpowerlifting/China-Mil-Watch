# Korea Desk — internal registration (NOT public launch)

Korea had a working isolated government-publisher shadow collector, a SHA-pinned private reader, and an actual five-record HWPX integrity/semantic review program, but as of October 11 was **not in the authoritative desk registry**. That meant the real operational research desk could not be accounted for with other declared desks.

This PR declares **South Korea Desk** as:
- `status=shadow`, **`public=false`**, `manifest=null`, `has_production_records=false`.
- Single bounded private source family: MND (`국방부`) releases **republished by** Policy Briefing (`대한민국 정책브리핑`). DAPA is excluded.
- Clear review and rights holds and no claimed 30-day production qualification.
- A real private on-demand reader and review workbench, operating only against existing source-state Git refs, are available in main after PRs #410, #413 and #414.

**The public site must not gain a Korea page** from this change. The public site generator uses `core.desk_registry.DeskRegistry.public_entries`; `public=false` excludes this private entry even from desk navigation. No production manifest is created; `core.manifests.load_all_desks` still discovers only China and Singapore. No output or database is touched.

A subsequent *separate* reviewed release PR may propose `public=true` for a bounded, metadata-only Korea reference pilot **only after** independent Korean source review, per-page rights determinations, content-SHA-bound signoffs, explicit owner approval and static render/citation QA. Even then status remains `shadow`; a full collecting desk requires a distinct 30-day program and production manifest admission decision. This PR grants neither step.
