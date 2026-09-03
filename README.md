# Singapore shadow review evidence

Completed Day 7 / 14 / 30 checkpoint reviews for the `singapore-mindef` shadow
desk, preserved append-only.

This branch is orphan by design. It shares no history with `main` and none with
`shadow/singapore-mindef`, because the state branch is the artifact these
reviews assess — keeping the audit inside its own evidence would destroy the
distinction a later comparison depends on.

Each directory under `reviews/<checkpoint>/<completed-review-id>/` holds the
automated package that was presented, the reviewer's structured sign-off, and a
receipt binding the two. `index.jsonl` is append-only.

Identities:

* **automated package id** — what was presented for review
* **completed-review id** — the review answers and attestation, bound to that
  package
* **the Git commit** — when and by whom that completed review was preserved

None of these is a cryptographic signature, and none establishes a reviewer's
legal identity.

Nothing here is executable, and nothing here is published to the public site.
