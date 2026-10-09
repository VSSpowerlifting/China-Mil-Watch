# Targeted CI repair for PR #314 (not a public-site redesign)

Context: PR #314's full offline suite [run #37991208830] found two
regressions in test assumptions, rather than a proven content mismatch.

## Self-hosted font fallback

The site's owned font delivery introduced local WOFF2 assets under
`/assets/fonts/`, but `BrowserCase.measure(block_webfonts=True)` still
blocked only Google Fonts domains. The test checking that the fallback
condition was exercised failed because no Google font was requested.
The new intercept blocks WOFF2 resources **and** the historic remote
font addresses. It preserves a genuine requested-font count and
warm-versus-fallback monospace text-width assertion. It does not block
all same-origin CSS/JS/images or remove the source-domain wrap checks.

## Navy paper pixel reproducibility

The PNG builder preserves the verified indexed 256x256 paper pixels,
replaces its fixed palette, then optimizes PNG compression using
Pillow. Compressed IDAT byte output can vary with Pillow/zlib builds,
so byte-identical **rebuilt compressed files** are not a portable
artwork regression assertion. Existing tests still check the shipped
asset's exact sha256 against its shipped receipt, original paper and
master source-chain sha256, palette topology, color extents, seamless
edges and size budgets.

The new builder test checks regenerated **decoded** palette, indexed
pixel bytes and RGBA representation against the delivered PNG, and
full regenerated metadata/source receipt fields against the stored
approved metadata. It separately validates the generated file's own
sha256 and delivery cap. No stored binary or published page changed.

## Scope and release

This is a child PR based on the existing frontend #314 branch;
merge it into that branch only if its targeted CI passes.
Afterwards, the **parent #314** must rerun full repository offline/
Chromium/render/public output tests on its new head. No change to
visual design, existing public markup or navigation is included.
