# South Korea — private Sunday regional-evidence bridge (October 8, 2026)

## What this does

Extend the pending **one-theme Sunday AI drafting** lane in PR #210 with the **actual current** isolated Korean Policy Briefing shadow state. The existing Japan/Vietnam research packet remains intact; Korea is added to that **same** private model evidence pool, never to a second supplement or separate email. The Korea feeder is stacked on PR #210, not on `main`; do not merge the stack out of order.

Source: `shadow/korea-policy-briefing`, the government portal's `A00005 / 국방부`-filtered republications. This is a **Tier B government-republished source**, not first-party MND-site collection, a complete Korean military-release wire, or evidence from the Joint Chiefs or services. The ministry site's robots restrictions remain untouched. The original extracted text and HWPX response captures remain on the shadow state branch.

## Trust model

* The existing formal review helper replays a **literal current Git state commit** and checks every tracked capture hash, HWPX-derived original-text hash, issuer, URL, schema, file topology, daily attempt status and state preservation. Any missing logical day or unhealthy attempt blocks the Korea step when it is enabled.
* The model sees only a constrained **publication metadata card**: original Korean headline, publisher-hosted link, portal date, Korean language, source class, source hashes and immutable canned caution. This is a source-discovery lead, **not permission for the writer to assert an event based on its headline**.
* All Korean evidence receives typed IDs `KR-PB-<newsId>`; it can never impersonate production integer IDs or Japanese/Vietnamese namespaces. Strict source URL/ID/issuer checks reject spoofed external links, and altered summaries fail the schema.
* There is **no auto-translation, machine-created original-source synopsis or implicit human source approval**. An independently reviewed Korean-language article may eventually qualify for a *separately reviewed* source-specific synopsis, but that is out of scope here.
* At most three Korean cards and eight regional candidates total. Historical dates outside the exact Saturday-ending reporting week are excluded. The model may omit every Korean card if none fits the one defensible theme.

## Activation and workflow

The Sunday workflow now has a repository variable `IPR_SUNDAY_KOREA_RESEARCH_ENABLED` (default **off**). With the variable unset/false, it copies the existing Japan/Vietnam private packet unchanged to the combined packet: Sunday delivery behavior is preserved. With the variable **true**, it clones `shadow/korea-policy-briefing` read-only, rejects stale or incomplete state, produces a combined packet outside the checkout and passes that packet into the existing **one** Claude draft call. A bad enabled Korean state intentionally fails the handoff rather than misattributing evidence.

The previous Sunday SMTP and approval gates are unchanged. **No email is sent merely by merging this PR.** The owner should first merge and validate #210, retarget this PR to main, require exact-head CI and successful no-send Sunday preview, then decide whether to enable the Korea research variable. If the Oct 11 scheduled Korean collector has not succeeded before the Sunday writer, leave the variable off. The first Sunday merged draft still requires Dylan to inspect the original Korean document (or omit its source) and Ben's approval before any public Brief.

This bridge is **not production activation**. Korea's full seven/fourteen/thirty-day reliability checkpoints, original HWPX visual/source comparison, source reuse assessment, institution expansion and explicit owner promotion are unchanged.

## Operator proof (no-send)

With #210's Sunday workflow merged, run its `workflow_dispatch` preview for October 10 with `send_email=false` and Korea variable off first. For Korea-on dry runs, require an on-time successful scheduled ledger for the day and a clean tip on `shadow/korea-policy-briefing`; then set the research variable, run the same no-send preview and inspect the single article's provenance, focus and separate supplemental citations. Verify there is **zero** claim that Korea is an active desk.

This PR includes synthetic tests for metadata-only claims, URL/issuer spoofing, capacity, window checks, preserving Vietnam/Japan cards, stale-state failure and no-overwrite. Synthetic tests are not a substitute for real remote Git/state replay, model quality review or CI.
