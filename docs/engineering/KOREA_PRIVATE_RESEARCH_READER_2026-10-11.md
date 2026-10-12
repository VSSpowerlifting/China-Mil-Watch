# Korea Desk — private, SHA-pinned research reader

**October 11, 2026. Proposed review PR, not deployed or approved for public release.**

## Purpose and exact existing evidence

Korea's existing MND-labeled government Policy Briefing collector writes a separate immutable Git history at `shadow/korea-policy-briefing`. The publisher is **Republic of Korea Policy Briefing** (`www.korea.kr`); the represented issuer is **Ministry of National Defense, 국방부**. This is a republication stream, not direct collection from `mnd.go.kr`. The separately investigated DAPA (`방위사업청`, code `B00008`) is **not** in this reader or the MND shadow branch.

This adds `kr_policy_mnd_releases` to the *existing* local, private metadata-only country reader, not to production, the public website, a source license allowlist, or the daily collector. The one-command launcher recognizes `--desk korea`, while legacy `--desk both` remains Philippines + Vietnam and `--desk all` means all three country research readers. The launcher retrieves only an already-existing GitHub **shadow Git ref** after `--approve-github-shadow-fetch` and pins its 40-character commit; it makes no publisher requests.

## Use (local terminal, after review and merge)

```bash
python -m scripts.launch_private_country_desks \
  --desk korea --approve-github-shadow-fetch \
  --query "국방부" --format html \
  --output /absolute/private/path/kr-mnd-research.html
```

A manually pinned snapshot can also be read offline without even requesting GitHub: `python -m scripts.private_country_desk_reader --source kr_policy_mnd_releases,/absolute/local/state-repo,EXACT_40CHAR_SHA --country korea --format json`.

The output contains original-language titles, official publisher links, dates, institution/source family, source identity, Git state SHA and **PUBLIC REVIEW PENDING**. Full Korean source text may be used **only for in-memory private term matching**. No original paragraph, copied document, attachments, captured bytes, translation, excerpt, LLM input, summary or third-party asset is emitted in HTML/JSON. A title is discoverability metadata, not substantiation of an event claim.

## Fail-closed identity contract

For Korea, this reader additionally checks:

1. Git *commit* object, Day 0 clock provenance and desk=`korea`; SQLite `shadow_meta.desk=korea`. The actual October 11 Korea state was inspected at `dcb43b9c4edb471d6def5876701ec4a2e39d5264`: Day 0 is the literal `local-native-20261006-korea`, not a numeric Actions run. The reader permits **that one exact legacy Korea bootstrap ID only** alongside normal numeric run IDs; other desks do not inherit an exception.
2. Source slug `kr_policy_mnd_releases` and **exact** canonical `https://www.korea.kr/briefing/pressReleaseView.do?newsId=<id>` matching `korea-policy:<id>` (no extra query, DAPA substitution or alternate host).
3. Korean `ko` original-language label; MND original issuer `국방부` but government Policy Briefing publisher `대한민국 정책브리핑`; explicit HWPX-text republication metadata, canonical HWPX document URL, capture-hash reference shapes.
4. The archived original Korean text's SHA-256 parity with its stored `content_sha256`; no title/body export. **This alone does not reproduce the original HWPX extraction** and does not certify rights or editorial fidelity.

No MND source permission is inferred from portal robots access, KOGL general categories, or a single page marker. The separately developed `scripts/audit_korea_source_fidelity.py` must re-extract original preserved HWPX documents and compare source bytes. Original Korean human review of text, ordering, issuer, publication dates and rights still must be completed and tied to exact source SHA-256 before an analytical synopsis, citation or public promotion can be considered.

## Verification and boundaries

```bash
python -m unittest tests.test_private_country_desk_reader tests.test_launch_private_country_desks -v
```

Offline tests construct real local Git commits plus both Korea and preexisting country SQLite schemas; verify in-memory body filtering, no body disclosure, wrong issuer, wrong canonical identity/host/language, corrupt Korean text SHA, wrong desk DB/clock, and backwards-compatible launcher selection. PR-only Actions jobs run those tests without publisher access. This work never touches `pla_watch.db`, `output/`, `desks/registry.json`, live source manifests, S3/deployment, email, scheduling, model calls or publisher websites.

**Next source-admission gate:** run latest SHA-pinned Korea fidelity review, reconcile actual Actions attempts against nominal ledger dates, secure Korean-language human reviewer signoff and exact per-page/attachment reuse decisions. Only then propose a separately reviewed, source-specific, editorially bounded public Korea desk admission.
