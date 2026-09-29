# Third-Party Notices

This prototype is built on **Halftone**, an MIT-licensed Astro theme by ondelva
(https://github.com/ondelva/astro-theme-halftone, commit `d389a3d`). The theme's licence is kept
in `LICENSE` and applies to the theme code carried here.

| Asset          | Type  | Source                                           | License | Notice / attribution                   |
| -------------- | ----- | ------------------------------------------------ | ------- | -------------------------------------- |
| Source Serif 4 | Font  | https://fonts.google.com/specimen/Source+Serif+4 | OFL 1.1 | Copyright Adobe                        |
| Inter          | Font  | https://fonts.google.com/specimen/Inter          | OFL 1.1 | Copyright The Inter Project Authors    |
| IBM Plex Mono  | Font  | https://fonts.google.com/specimen/IBM+Plex+Mono  | OFL 1.1 | Copyright IBM Corp.                    |
| Lucide         | Icons | https://lucide.dev                               | ISC     | Copyright (c) Lucide Contributors      |

The fonts are fetched by the Astro fontsource provider at build time (`fonts:` in
`astro.config.mjs`), latin subset. Nothing is fetched from a CDN at runtime.

## Plates

The theme's sample photographs have been removed. The plates in `src/assets/plates/` are abstract
graphics drawn by `scripts/make-ipr-plates.mjs`. They depict nothing and are credited on every
page as generated graphics, not photographs.
