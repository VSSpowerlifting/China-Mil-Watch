"""
When a record stops being retried, and what it is allowed to say about itself.

A record that passed relevance on its title and holds no body can never produce
a translation. Retrying it is not perseverance, it is a loop: article 2678 was
retried on 28 separate runs before this existed. But "stop retrying" and "drop
quietly" are different things, and only the first is acceptable — so every
decision here is recorded with a reason and a history.

The distinction this module exists to draw
------------------------------------------
**Retriable** — the failure might not recur. A model call that timed out, a
translation that came back without a summary, an account-level interruption.
These keep their place in the queue.

**Terminal** — the failure will recur, every time, for ever. Two ways in:

  * `unsupported_document` — the adapter said so. A photo set, a video shell, a
    redirect stub: the document genuinely has no prose to analyze. This is
    terminal on the first observation, because nothing about it will change.
  * retry budget exhausted — the failure has recurred RETRY_BUDGET times. This
    is the honest catch-all: it does not claim to know *why* the record cannot
    be analyzed, only that this project has now tried often enough that
    continuing to try is a choice rather than an accident.

WHY AN EMPTY BODY IS NOT TERMINAL ON SIGHT
------------------------------------------
It is tempting to make "no body" terminal immediately. It was also, until
2026-09-16, wrong: records 3432, 3946 and 3948 held empty bodies because the
Global Times extractor had been left behind by a template change, not because
the documents were empty — their pages served 359, 3,969 and 2,113 characters.
An immediate terminal state would have made an extraction regression
permanent and invisible, converting a repairable defect into a silent one.

So an empty body spends the retry budget first. If the extractor is broken, the
record keeps reappearing in health reporting where somebody can see it; if the
document really has no prose, it goes terminal after RETRY_BUDGET runs instead
of after 28.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import NamedTuple, Optional

#: How many observed failures before a record stops being retried. Five is a
#: working week of daily runs: long enough that a transient model or network
#: problem cannot exhaust it, short enough that nothing spends a month in the
#: queue. It is deliberately not 1 — see the module docstring.
RETRY_BUDGET = 5

RETRIABLE = "retriable"
TERMINAL = "terminal"

#: Every reason this module can record. A reason outside this set is a bug, not
#: a new category: `tests/test_processing_state.py` asserts the vocabulary is
#: closed, because a free-text reason is how a taxonomy quietly stops meaning
#: anything.
REASONS = (
    "unsupported_document",             # adapter: no prose to analyze, ever
    "no_prose_body_budget_exhausted",   # empty body, retried RETRY_BUDGET times
    "analysis_failed_budget_exhausted", # analysis failed RETRY_BUDGET times
    "analysis_incomplete",              # retriable: no translation or no summary
    "analysis_failed",                  # retriable: the call produced nothing
    "no_prose_body",                    # retriable: empty body, budget remains
)


class Disposition(NamedTuple):
    """What to record about a record that has just failed analysis."""

    state: str
    reason: str
    attempts: int

    @property
    def is_terminal(self) -> bool:
        return self.state == TERMINAL


def classify(*, attempts_before: Optional[int], has_body: bool,
             failure: str, unsupported: bool = False) -> Disposition:
    """
    Decide what this failure means, given how many came before it.

    `attempts_before` is the count already stored, or None for a record that
    has never been observed failing. `failure` is why this attempt failed:
    "analysis_failed" when the call produced nothing at all,
    "analysis_incomplete" when it produced a partial result. `unsupported` is
    the adapter's own statement that the document has no prose.
    """
    if failure not in ("analysis_failed", "analysis_incomplete"):
        raise ValueError("unknown failure kind: %r" % (failure,))

    attempts = (attempts_before or 0) + 1

    if unsupported:
        return Disposition(TERMINAL, "unsupported_document", attempts)

    if attempts >= RETRY_BUDGET:
        reason = ("no_prose_body_budget_exhausted" if not has_body
                  else "analysis_failed_budget_exhausted")
        return Disposition(TERMINAL, reason, attempts)

    reason = "no_prose_body" if not has_body else failure
    return Disposition(RETRIABLE, reason, attempts)


def now_utc() -> str:
    """ISO-8601 UTC, seconds precision — the stamp both timestamps carry."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
