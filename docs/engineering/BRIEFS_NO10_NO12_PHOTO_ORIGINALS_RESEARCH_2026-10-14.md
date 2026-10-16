# IPR Briefs Nos. 10 and 12 — stronger original-photograph research

**Research date:** 14 October 2026 · **Parent:** [#544](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/544) · **Disposition:** research and owner image-selection review only, no photo admission.

## Keep the 16-cover release intact

The approved 16/18 photographic catalogue was published at `gh-pages` commit `cb6f8f70f7dbf2d2eb0d0f1e5e801cd8deea6866` ([successful Pages deployment](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38576174202)); release `analysis.html` and all 16 served catalogue JPEGs match `main` output at exact Git blob identities (independent check recorded [here](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/544#issuecomment-6170343004)). **Do not modify or republish those 16 images to pursue a numerical 18/18 goal.**

No. 10 **HELD**, No. 12 **DENIED** in `site/assets/catalogue/admissions.json`. The denial on No. 12 belongs to the earlier, disqualified B5/81.cn source; the decision is not automatically lifted by finding a different photo. A new, separately selected and legally checked source may justify an explicitly scoped governance decision. No article-hero or public Page changes in this research branch.

## Read the actual articles before selecting images

| Brief | Published emphasis | What a photo must not imply |
|---|---|---|
| **No. 10**, [*Beijing's Public SLBM Test and What It Was Designed to Do*](https://indopacificrecord.org/the-pla-watch/posts/2026-07-11.html), week ending 11 July 2026 | Why China's 6 July report of a strategic submarine-launched ballistic missile training test, described in unusually precise public terms, was itself a strategic signal. The public record does **not** identify the missile type or specific submarine. | No unsourced assertion that a pictured Type 094, JL-2/JL-3 launch, or launch plume belongs to the July 2026 test. A generic U.S. Trident launch would imply the wrong navy. |
| **No. 12**, [*Army Day, Scarborough Shoal, and a Week of Deliberate Disclosure*](https://indopacificrecord.org/the-pla-watch/posts/2026-08-01.html), week ending 1 August 2026 | Southern Theater Command joint naval-air exercise at Scarborough Shoal, simultaneous CCG drills, and Army Day platform disclosures (Type 076 *Sichuan*, YJ-20, H-6K); the article analyzes strategic messaging rather than claiming independent observation. | No implication that a **2024 or 2025** archival photograph depicts the **1 August 2026** exercise or a Type 076 test. Do not pass off a video frame or Chinese-ministry photograph as a freely reusable photographer-origin still. |

## No. 12 — leading NEW candidate for separate review

**PCG photograph: CCG cutter 3105 near Scarborough Shoal, 2 February 2024.**

![Research-only original PCG photograph of China Coast Guard 3105 near Scarborough Shoal. NOT a published IPR card.](https://upload.wikimedia.org/wikipedia/commons/0/0c/China_Coast_Guard_CCG_3105_near_Scarborough_Shoal_02.02.24.jpg)

| Evidence dimension | Verified finding and limitation |
|---|---|
| Image source | [Commons file and history](https://commons.wikimedia.org/wiki/File:China_Coast_Guard_CCG_3105_near_Scarborough_Shoal_02.02.24.jpg); the *source file*, not a search-engine thumbnail. Original 1,980 × 1,200 JPEG, approx. 587 KB; Commons SHA-1 `c6350ca5285def6e585ffe693cd3b53fd312123a`. Uploaded 9 April 2024 by a third party, credited to **Philippine Coast Guard**. |
| **First-party publication** | [Philippine Information Agency government archive, 13 February 2024](https://mirror.pia.gov.ph/news/2024/02/13/roadshow-kontra-patalang-nga-impormasyon-bahin-sa-west-philippine-ginlunsar). The page contains an image explicitly captioned (Hiligaynon) as a *Chinese Coast Guard vessel monitored by the Philippine Coast Guard near Bajo de Masinloc*, with **photo credited to the PCG**. The Commons entry points to this same PIA item. The original PIA article is a roadshow article using archival vessel imagery, **not** eyewitness reporting of the August 2026 exercise. |
| Rights evidence | Commons marks the particular file **PD-PhilippinesGov**, citing Philippine copyright-law provisions on official-duty government works; the PIA government archive footer separately says its content is public domain unless otherwise stated. This is materially stronger custody evidence than the earlier B5 image. **Still required:** independent check that the exact pictured file carries no third-party exception or additional reuse restrictions and that republication on a U.S.-hosted IPR site is permissible; avoid treating a jurisdictional Commons tag alone as worldwide permission. |
| Image honesty | Visually identifiable **China Coast Guard 3105**, dark water and a 2024 timestamp/PCG watermark on the original. The 2024 date is explicit. It depicts an enforcement-capable vessel in the *same Scarborough Shoal geography*; not the named 2026 joint exercise, not the PLA Navy and not Type 076. Do **not remove or conceal the embedded official watermark/date** for aesthetic reasons. |
| Crop/quality | 1,980×1,200 is sufficient for 720×480 catalogue display. A 3:2 crop needs careful review because the long hull spans most of the frame and the bottom right has embedded photo marks. Consider keeping the intact photograph within a 3:2 card rather than cropping off hull or the source/date marks. **No crop, derivative, card SHA or render has been made in this research PR.** |
| Editorial suitability | **Strong topical/geographic match**, but a Coast Guard ship is only one strand of this mixed Army Day/PLA analysis and the existing catalogue already uses CCG vessels for Nos. 5 and 7. This repetition is an editorial drawback, not a license defect. |

**Suggested review-only wording**, *if* later approved: 

> Philippine Coast Guard photograph of China Coast Guard cutter 3105 near Scarborough Shoal (Bajo de Masinloc), 2 February 2024. Historical maritime context; this image does **not** show the 1 August 2026 PLA joint exercise or related equipment disclosures. Photo: Philippine Coast Guard, via Philippine Information Agency / Wikimedia Commons. Preserve embedded date/watermark; specify any resizing/cropping.

**Proposed alt:** `Chinese Coast Guard patrol vessel 3105 on open water near Scarborough Shoal in a Philippine Coast Guard photograph dated February 2024.`

**Review gates before *any* new admission:** (1) compare the actual Commons file against the PIA-hosted photograph rather than inferring identity from a matching caption; (2) inspect rights in the originating government context, including U.S. redistribution; (3) review the genuine 720×480 treatment with intact attribution and timestamp; (4) obtain owner selection on the specific image; (5) make the smallest *new-source-specific* change to the old No. 12 `DENIED_ISSUES` rule while retaining a denial for the B5 original, with negative tests demonstrating the disqualified 81.cn media is still refused; (6) pass exact-head full CI and a separately scoped output-only Pages release.

### No. 12 considered but not selected

- [PCG photographs of Chinese cutter Nanyu 3104 on 11 August 2025](https://commons.wikimedia.org/wiki/File:China_Coast_Guard_Cutter_Nanyu_(3104)_20250811.jpg) and [destroyer Guilin 164](https://commons.wikimedia.org/wiki/File:People%27s_Liberation_Army_Navy_Destroyer_Guilin_(164)_20250811.jpg), each labeled PD-PhilippinesGov on Commons, have photo-size originals (1,199×1,167 and 1,647×828). However, their publicly linked publication trail runs through social-media reposting of a *different, dramatic 2025 collision*. Risk of implying that event occurred in 2026 outweighs the advantage of a less watermarked photo. The [2,428×1,382 collision image](https://commons.wikimedia.org/wiki/File:People%27s_Liberation_Army_Navy_Destroyer_Guilin_(164)_and_China_Coast_Guard_Cutter_Nanyu_(3104)_collision_20250811.jpg) comes from video material, not an independently originated still.
- [Kremlin.ru PLA personnel at a September 2025 parade](https://commons.wikimedia.org/wiki/File:PLA_personnel_before_the_2025_China_Victory_Day_Parade.jpg), marked CC BY 4.0, is much less directly relevant to Scarborough operations and the new platform disclosures.
- Chinese Type 076 *Sichuan* stills sourced as frame captures from China News Service videos have unresolved underlying video-specific reuse/creator chain; legitimate newsworthiness is not a republication license.
- A second NASA Scarborough satellite image could repeat the already-admitted near-identical No. 9 / No. 13 orbital imagery without helping the PLA/CCG story.

## No. 10 — continue hold, no worthy replacement found

[Commons's **Type 09IV / Jin-class media category**](https://commons.wikimedia.org/wiki/Category:Type_09IV_submarines) contains **five files**: one illustrated SVG diagram (not photography; CC BY-SA), a research PDF, the existing CRS photograph, the 587×397 self-published candidate, and its smaller crop. It does not expose a second, high-resolution, unambiguously photographer-attributed Type 094 original.

- [Existing CRS-origin 1,000×600 image](https://commons.wikimedia.org/wiki/File:Jin_(Type_094)_Class_Ballistic_Missile_Submarine.JPG): the CRS cited the Navy Office of Legislative Affairs as the **provider**; the originating photographer, camera operator and copyright basis remain unproven. Do not declare this a U.S. government-owned photo on that evidence.
- [`SSBN-0-lover` image](https://commons.wikimedia.org/wiki/File:Type_094_SSBN.JPG): uploader claimed `Own work` and `PD-self`, with a July/October 2008 date inconsistency across file metadata and revisions. Original is only **587×397**, 27 KB (its separate crop is 292×189). Original photographer/capture and higher-resolution provenance were not independently established; the source's *own claim* is better than missing attribution but not enough to clear for the new IPR surface.
- Modern Chinese-media Type 094 photos and widely republished submarine imagery found through general searches did **not** carry a verified individual photographer/public license. Reproduced news-site photos, gallery snippets, maps, SVGs and model submarines are not equivalent to cleared photographs of the actual 2026 test.

**Follow-on target:** one source-identified original of a real Chinese SSBN (e.g., independent photographer-owned image whose provenance can be validated), or an independently verified photographer-origin Chinese submarine/missile-system photograph directly relevant to the July disclosure, with the caption marking year/system distinctions. Do not substitute U.S. missile tests or falsely identify a photographed hull as involved in July 2026. If source integrity cannot be established, retain No. 10's editorial plate.

## Publication and engineering boundary

This research packet does **not** propose an automatic 18/18 promotion. No change to `site/assets/catalogue/admissions.json`, `site/assets/editorial/manifest.json`, `core/catalogue_media.py`, `site/render.py`, `output/`, `gh-pages`, collectors, databases, Brief manuscripts, captions already published, or active release workflows. No external images were downloaded into the repository. A separate photo-selection decision and governed implementation PR would be needed for No. 12; No. 10 still lacks a suitable source.