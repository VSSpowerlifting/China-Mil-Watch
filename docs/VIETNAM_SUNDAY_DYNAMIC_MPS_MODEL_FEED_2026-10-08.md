# Vietnam: recurring current-shadow input for ONE Sunday AI Brief

Status: proposed production workflow integration; source collection / publication rights remain separately gated.

## Actual gap this closes

PR #237 merged a one-theme Sunday writer, but its initial workflow read a committed, exact-week regional research file. A committed file can drift from the current independent Vietnam MPS archive, and a fixed October 10 file will not provide Vietnam research next Sunday without additional editorial notes.

This milestone uses the **existing** provenance-bound, read-only Vietnam composite action from the merged private MPS feeder, rather than rebuilding source scraping or writing a second AI Brief. It does not add a new scheduled publisher crawl or modify Japan's research and Friday authoring code.

## Runtime sequence

The existing Sunday workflow still verifies that its Saturday reporting week has finished and the daily production update succeeded before it can run the model.

1. Validate the optional committed regional research file for exactly that Saturday (Japan notes are preserved and remain unapproved private drafting inputs).
2. Select an optional version-pinned Vietnam MPS editorial-notes catalog for the same reporting Saturday; reject symlinks and malformed files.
3. Run the composite action to clone ONLY the isolated MPS state branch read-only at its **current head**, independently check the raw-capture / SQLite / source-version chain, and join the current machine-eligible publication metadata to matching source-version synopses.
4. Replace only the static Vietnam section in an **ephemeral** research JSON in the runner's temporary directory, leaving Japan and other non-Vietnam research untouched.
5. Validate the merged exact-week schema and Vietnam count, then pass the verified private JSON to the **same** Sunday model through its pre-existing --research-packet argument. No independent country articles/supplements are generated for Dylan.

### October 10 pilot

The initial October 10 packet is special: **Vietnam is required** to enter the owner preview. If the current archive shows a source revision without a matching synopsis, or the two expected current source notes disappear, the job refuses **before** any AI or email step. Do not silently claim Vietnam contributed when no authenticated source-version-matched research exists.

### Later weeks

When no Vietnam note catalog exists, the policy explicitly permits zero private Vietnam model inputs **after** independently checking the real current MPS shadow archive. The composite action records that absence separately from observed publications. This prevents a permanent production-wide model outage merely because Vietnam has no reviewed notes yet.

A **present but invalid, version-stale, or symlinked** research file always fails closed, even for later weeks. A source article found only in shadow state is **not** automatically eligible for third-party AI use or published Briefs; the action consumes only separately authored, source-version-matched short research synopses. No article bodies go to the Sunday model.

## Coordination and follow-ons

- #225: human-verifiable citation bridge for final published Briefs. Nothing here substitutes for editor signoff, source-use verification, or final issue approval.
- #228: independent Sunday missing/stale synopsis dashboard. It can surface why a future weekend has zero Vietnam research without implying government silence.
- #241: explicit live-shadow roster attestation. Its standalone real-state proof is useful as an additional check but this change does **not** import that PR's unmerged code; it uses the already-merged read-only verified packet builder instead.
- Japan and other desks must qualify their own shadow sources and research notes independently. This Vietnam change **does not** create equivalent source permissions for them.

No new GitHub secret, recipient, SMTP permission, publishing/production database write, public artifact or unsupervised model-generated article is introduced. The existing, owner-controlled Sunday delivery variable and no-send preview workflow remain unchanged. **The integration PR must pass CI and be merged before Sunday can use the new input path.**
