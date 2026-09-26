---
name: ipr-design-references
description: Research outside design sites and tools for Indo-Pacific Record frontend work, then translate useful patterns into the existing editorial design system. Use when asked for design inspiration, Refero, institutional research-site comparisons, or outside-platform design input.
---

# Outside design references for IPR

Read `CLAUDE.md`, `docs/DESIGN_SYSTEM.md`, `docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md`, and the specific route before browsing. Define the reader task and a bounded question (for example, finding an official record, comparing desk status, or tracing a cited source).

Use **Refero for visual and interaction inspiration**, and compare relevant patterns from **ChinaPower** (research/data discovery), **Bellingcat** (source and method transparency), and **Impresso** (corpus and provenance). For disclosure and accessibility patterns, consult GOV.UK or USWDS. These are reference leads, not design specifications: inspect current pages, link the exact examples, record what was observed, and do not claim a reference has a feature without seeing it. If a site is gated or inaccessible, say so and move on.

For each useful pattern, record: reference URL and observed component; the reader problem it solves; the equivalent IPR route/component; the data needed and whether that data exists; accessibility and small-screen behavior; and an implementation sketch using this repo's Python/Jinja2 static output and vanilla JS. Keep the shortlist small and choose one bounded experiment. Do not copy a whole page, wording, imagery, logo, or CSS from another publisher.

Respect the accepted constraints: the existing design system governs visual taste; Refero is inspiration only; do not add React, Next.js, Tailwind, shadcn, Bklit, 21st.dev, GSAP, or a chart library by default. Retain the 10 KB/page vanilla JS budget and existing reveal/fallback patterns. Impeccable and browser/Playwright review can refine and verify rendered output **if available**; do not pretend a tool is installed. Avoid the retired SkillUI token extraction as an authority. Do not upload repo data to outside design services or create/publish an external project without an explicit task for that destination.

Return a compact reference-to-implementation table and a concrete local prototype or ticket, with screenshots and keyboard/mobile checks when implementation is authorized. Keep live desk status and provenance grounded in the registry and generated data, never in a design mockup.
