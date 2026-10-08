# Philippines Coast Guard source admission: PCG bylines hosted on PIA

**Current state: research candidates only. Collector disabled. No source was captured, admitted, classified or published by this research packet.**

## Finding

The Philippine Information Agency (PIA) maintains an official government publication platform that includes multiple first-person reports credited **“By PCG”**. That provides a plausible, more accessible source surface for the Philippine Coast Guard (PCG), which the Philippines Desk currently lacks as an independent collected issuer alongside AFP and NSC.

**Institutional precision matters:** These pages are **hosted by PIA**; the displayed author credit is **PCG**. The credit is evidence of claimed issuer, not independent authentication. Neither host identity nor presence of an official government domain alone proves original authorship. A PIA reporter writing *about* PCG or PNP is different from PCG-submitted copy redistributed by PIA. In the eventual event/relationship model, store all three separately: `host_institution`, `attributed_issuer`, and `issuer_verified_by` (initially empty), with both PIA URL and any separately discovered original PCG URL.

## Five verified web discovery leads

These are **public URLs whose title, visible byline and publication date were inspected** on October 8, 2026. They are *not captured into IPR*. Each is registered as a **disabled research lead** in `source_candidates.json`.

| ID | PIA date | Issuer byline | Topic / why the Philippines Desk needs it |
|---|---|---|---|
| PCG-PIA-01 | Oct 7, 2026 | PCG | Establishment of a PCG auxiliary district in the Kalayaan Island Group; maritime presence and civil security |
| PCG-PIA-02 | Sep 28, 2026 | PCG | Coast Guard/PLA Navy encounter around Cabra Island; attributed observations and allegation provenance |
| PCG-PIA-03 | Sep 18, 2026 | PCG | PCG maritime-domain awareness in support of BFAR at Bajo de Masinloc |
| PCG-PIA-04 | Sep 10, 2026 | PCG | PCG account of PLA flares near the Kalayaan Island Group; competing narratives remain unverified |
| PCG-PIA-05 | Jul 21, 2026 | PCG | PCG-reported medical evacuation near Ayungin Shoal; maritime HADR and rescue capability |

The PIA website identifies itself as the information arm of the Philippine government. Its footer states, **“All content is in the public domain unless otherwise stated.”** That conditional language is *not* a blanket assurance about underlying PCG-origin press release text, photographs, third-party material, indexing or wholesale mirrors. A reviewer must check rights and publishing terms for each source, and should presume **no reusable full-text publication rights** until then.

## Negative controls: what we must NOT call a PCG release

- A September 18 PIA-NCR story about PNP international relations is written by **PIA staff reporter Jimmyley Guzman**. It cannot be silently attributed to PNP just because it quotes PNP leadership.
- October 1 coverage on **Radyo Pilipinas** of AFP/PNP/PCG exercise Sanlakas is journalist-authored reporting. A public state broadcaster does not become the original Coast Guard issuer.
- A September 1 **Presidential Communications Office** release discussing newly promoted PCG leaders is originally issued by **PCO**, not PCG.

These three identified URLs are deliberately included as **excluded/separately classified leads** to guard against an eventual collector discovering page subjects instead of checking explicit issuer metadata.

## Admission checklist for a separate authorized phase

1. Confirm the site's robots and access/traffic limits, and whether a bounded manual fetch is authorized. Do not challenge-solve, bypass rate limits or try alternate user identities.
2. Independently verify the PCG byline: primary source credit, posted agency metadata, provenance links and whether PIA republishes a PCG-authored release or merely summarizes it.
3. Review the site-wide conditional copyright/public-domain notice *and each article's source-specific caveats*, including photographs, third-party text and republication restrictions. Access permission is not the same as public-display permission.
4. Preserve original page date separately from any PCG-stated action date and any later PIA updates. Do not infer exact publication timestamps from calendar-only dates.
5. Investigate duplicates with other PCG channels. A PCG statement mirrored by PIA is **one originating institutional assertion on two hosts**, not independent PIA corroboration.
6. If authorized, perform a **one-off rights-aware bounded capture** with original bytes, URL, response headers, retrieved-at UTC, SHA-256 and explicitly identified source/host/body; inspect a human sample.
7. Only after source access, rights and human source-integrity checks should an owner consider a **new isolated disabled-by-default shadow collector PR**. The AFP and NSC collectors, production registry, topic attachments and UI must remain unchanged until then.

## Versioned reproducibility

    python3 scripts/validate_ph_pcg_pia_sources.py
    python3 -m unittest tests.test_ph_pcg_pia_sources -v

These are purely offline structural checks. They do not contact PIA, authenticate PCG, validate publication times, or verify body rights. The five URLs are exact allowlisted leads, seven admission review gates are all pending, and test regressions refuse unsupported URLs, publication-time inventions, misclassified PNP newsroom writing or forged archived object IDs.

**Editorial opportunity:** These primary-attributed releases may materially broaden a future Philippines Desk from AFP-only defense statements to persistent coast-guard maritime/security and HADR coverage. They must not be counted as five IPR archived records or independently confirmed events until admission review is completed.
