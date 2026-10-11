# Sunday reviewed-artifact replay — disabled offline integration rehearsal

**Issue:** #366. **Depends on:** PR #377, latest reviewed head to be pinned from live PR state. The original base for this feature branch was `cc5a6743bf01236494d437334a24cebafbf6c495`; the latest parent dedupe changes are copied in a separate synchronization commit. This is a stacked implementation, not independent main integration. **Branch is stacked on #377**, NOT on independent main. This change does not authorize merging either PR or using a live sender.

## Scope and real inherited contracts

A previously reviewed source-linked editor TXT is the only manuscript input. The existing `scripts/sunday_first_pilot_reviewed_replay.py::inspect_file` rejects malformed/partial packets, non-October-10 weeks, invalid article boundaries, absent source appendix and non-UTF-8 / normalized bytes. The existing `scripts.sunday_pilot_owner_review.require_owner_review` and `require_exact_reviewed_manuscript` require separate owner-week input and exact attachment SHA.

The new `core/sunday_delivery_replay_rehearsal.py` composes those guards with PR #377's private SQLite attempt journal, without touching the real `send_packet` function. Its entire transport is a **closed vocabulary of imaginary events**, not an SMTP client or injected callback. It contains no scheduler, CLI, credentials, dispatch flags, network import, live provider, or model call. The existing Sunday workflow, real replay and output do not import it.

## Input identity and caveats

**Cross-version fence:** the latest parent journal now enforces a database-level unique constraint on reporting Saturday and normalized recipient. A second reviewed manuscript with different bytes and a new owner digest cannot automatically reserve another attempt for the same week/recipient; this remains true in the fictional replay tests. Older journals missing that index fail closed. This is a conservative technical stop, not proof of owner authorization or a general email resend policy.

The synthetic caller explicitly supplies: real-file path in a disposable private test directory, journal object, reporting Saturday, **independent** owner-approved week, exact reviewed attachment SHA, separately pinned source-use receipt SHA, recipient and purported approval-evidence digest. The module verifies:
- The file's existing full-envelope and article syntax with `inspect_file`; it does not author new content.
- The owner-week and byte-SHA *format/equality* checks using established functions, without forging those guards' inputs.
- One contiguous, uniquely delimited original source-use subsection **inside** the source appendix; the SHA of those exact bytes must match the separately passed digest. This is a **model-produced triage report** and does not attest source truth, independent human review, source-use rights, or a signed owner decision.
- Metadata identity through the journal's immutable registration and atomic reservation.

A bare `owner_approval_sha256` remains an **unauthenticated placeholder identity**. This is deliberately insufficient for any actual delivery. There is no trusted approval database, cryptographic owner signature, genuine recipient authentication or storage selection in this PR.

## Fictional state scenarios

| Scenario | Stored state / effect | Can it send? |
| --- | --- | --- |
| `preflight_only` | No journal registration, no reservation | Never |
| `hold_before_contact` | `held`; cannot reserve later | Never |
| `crash_after_reservation` | Raises after persisting `attempt_reserved`; no auto reset | Never |
| `mock_timeout` | `outcome_unknown`; no retry | Never |
| `mock_acceptance_lost_ack` | `outcome_unknown`; simulated remote acceptance is **unprovable** | Never |
| `mock_acceptance` | `smtp_accepted` with a clearly **fictional** fingerprint; not an SMTP receipt | Never |

A second synthetic attempt against reserved, held, unknown or mock accepted state is refused. A real SMTP server and local SQLite journal cannot atomically commit; no exactly-once guarantee is claimed. **This harness must not write fake acceptance receipts into a future real journal.**

## Negative tests and scope preservation

The new `tests/test_sunday_delivery_replay_rehearsal.py` includes 16 offline scenarios: full no-model/no-SMTP preflight; fictional acceptance; duplicate; timeouts; lost acknowledgments; crash-after-reservation; pre-send hold; missing/wrong approved week; wrong approved TXT SHA; edited reviewed bytes; missing/wrong source receipt SHA; malformed receipt markers; invalid recipient or approval digest; invalid scenario; concurrent workers; revised same-week manuscript refusal; and a specific assertion that receipt equality is not human approval.

No new output, subscriber list, emails, external-source collection, SMTP invocation, paid model call, schedule, database migration or live export. No existing code is modified. The future real adapter must separately review the publisher use basis, authentic owner approvals, recipient privacy (raw hashed addresses are guessable), durable protected journal rollback detection, attachment/file atomicity, failed-ack reconciliation and one-send-per-week policy. **Do not treat a new SHA for the same week as consent for a second email.** PR #377 must be independently reviewed and integrated before any future rebase of this stacked PR.

## Validation

Run `python -m unittest tests.test_sunday_delivery_replay_rehearsal -v` under Python 3.9 with existing development dependencies. The ordinary full PR CI is separately required on this exact PR head. No real transport receipt, source-rights permission, editorial approval, actual mailbox send or production readiness is established by passing these fictional tests.
