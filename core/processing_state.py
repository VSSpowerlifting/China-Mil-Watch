"""
When a record stops being retried, why, and how it comes back.

A record that can never be analyzed used to return to the queue on every run for
ever: article 2678 was retried on 28 separate runs. But "stop retrying" covers
two very different situations, and collapsing them is how a model outage turns
into a permanently lost document.

THREE STATES, AND THE LINE BETWEEN THEM
---------------------------------------
**retriable** — the failure may not recur. A model call that timed out, a rate
limit, a billing stop, an infrastructure error, a translation that came back
without a summary. These keep their place in the queue.

**paused** — the retry budget is spent. This is a *spend control*, not a
verdict about the document: it stops a record consuming a model call every day
while nobody is looking at it. A paused record is out of the automatic queue
and into manual review, and `resume()` puts it straight back. Nothing about the
document has been decided.

**terminal** — a deterministic condition in the content itself. Only two ways
in, and both are statements about what the document *is*:

  * `unsupported_media_only` — the adapter found its body container, found
    media in it, and found no prose. A photo set has no text to translate, and
    that will be true on every future run.
  * `no_usable_prose` — an explicit classification by a caller that has
    confirmed the same.

**Exhausting the retry budget can never produce a terminal state.** That was
the defect in the first version of this module: a fifth transient failure —
five bad days for the Anthropic API — permanently disposed of a perfectly good
document as though its content were at fault. An attempt counter measures this
project's luck, not the document's nature, and only the document's nature is
grounds for a permanent disposition.

WHY AN EMPTY BODY ALONE IS NOT DETERMINISTIC
--------------------------------------------
Records 3432, 3946 and 3948 held empty bodies because the Global Times
extractor had been left behind by a template change, not because the documents
were empty — their pages served 359, 3,969 and 2,113 characters. An empty body
can mean "there is nothing here" or "we can no longer read this", and from
inside the pipeline those are indistinguishable.

So an empty body on its own is retriable, and pauses at the budget. Only the
adapter can tell the two apart, because only the adapter saw the markup: it
reports `media_only` when it located the body container, so the template is
still understood, and that container held media and no prose. A missing
container is template drift and stays retriable, loudly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import NamedTuple, Optional

#: How many observed failures before a record is paused for manual review.
#: Five is a working week of daily runs. It bounds spend; it decides nothing
#: about the document.
RETRY_BUDGET = 5

RETRIABLE = "retriable"
PAUSED = "paused"
TERMINAL = "terminal"

#: States that keep a record out of the automatic analysis queue. `paused` is
#: here to control spend and is reversible; `terminal` is here because the
#: content cannot be analyzed and is not.
NOT_QUEUED = (PAUSED, TERMINAL)

#: Failure causes a caller may report. `transient` names the operational
#: family explicitly — API outage, rate limit, billing stop, timeout,
#: infrastructure error — so that the classifier can never mistake this
#: project's bad day for a property of the document.
TRANSIENT = "transient"
ANALYSIS_FAILED = "analysis_failed"
ANALYSIS_INCOMPLETE = "analysis_incomplete"
FAILURES = (TRANSIENT, ANALYSIS_FAILED, ANALYSIS_INCOMPLETE)

#: Deterministic content verdicts an adapter may report about a document.
#: Only these can produce a terminal state.
MEDIA_ONLY = "media_only"
NO_USABLE_PROSE = "no_usable_prose"
CONTENT_VERDICTS = (MEDIA_ONLY, NO_USABLE_PROSE)

#: Every reason this module can record, grouped by the state it belongs to.
#: A reason outside this set is a bug, not a new category — a free-text reason
#: is how a taxonomy quietly stops meaning anything.
TERMINAL_REASONS = ("unsupported_media_only", "no_usable_prose")
PAUSED_REASONS = ("retry_budget_exhausted",)
RETRIABLE_REASONS = ("transient_failure", "analysis_failed",
                     "analysis_incomplete", "empty_body_unconfirmed")
REASONS = TERMINAL_REASONS + PAUSED_REASONS + RETRIABLE_REASONS


class Disposition(NamedTuple):
    """What to record about a record that has just failed analysis."""

    state: str
    reason: str
    attempts: int

    @property
    def is_terminal(self) -> bool:
        return self.state == TERMINAL

    @property
    def is_paused(self) -> bool:
        return self.state == PAUSED

    @property
    def leaves_queue(self) -> bool:
        return self.state in NOT_QUEUED

    @property
    def is_permanent_content_disposition(self) -> bool:
        """True only for a statement about the document itself."""
        return self.state == TERMINAL and self.reason in TERMINAL_REASONS


def classify(*, attempts_before: Optional[int], has_body: bool,
             failure: str, content_verdict: Optional[str] = None
             ) -> Disposition:
    """
    Decide what this failure means, given how many came before it.

    `attempts_before` is the count already stored, or None for a record never
    observed failing. `failure` is one of FAILURES. `content_verdict` is the
    adapter's deterministic statement about the document, or None — and it is
    the **only** route to a terminal state.
    """
    if failure not in FAILURES:
        raise ValueError("unknown failure kind: %r" % (failure,))
    if content_verdict is not None and content_verdict not in CONTENT_VERDICTS:
        raise ValueError("unknown content verdict: %r" % (content_verdict,))

    attempts = (attempts_before or 0) + 1

    # The only route to terminal: a deterministic statement about the content.
    if content_verdict == MEDIA_ONLY:
        return Disposition(TERMINAL, "unsupported_media_only", attempts)
    if content_verdict == NO_USABLE_PROSE:
        return Disposition(TERMINAL, "no_usable_prose", attempts)

    # A transient failure never counts toward a permanent disposition, and it
    # never pauses a record either: an API outage is this project's problem,
    # and making the document wait for a human because our billing lapsed
    # would be charging the document for our fault. It stays queued.
    if failure == TRANSIENT:
        return Disposition(RETRIABLE, "transient_failure", attempts)

    if attempts >= RETRY_BUDGET:
        # Spend control, not a verdict. Reversible via resume().
        return Disposition(PAUSED, "retry_budget_exhausted", attempts)

    reason = "empty_body_unconfirmed" if not has_body else failure
    return Disposition(RETRIABLE, reason, attempts)


def resume(attempts_before: Optional[int] = None) -> Disposition:
    """
    Return a paused record to the automatic queue.

    The attempt count is reset, because the budget is what paused it and
    resuming without clearing it would pause the record again on its next
    failure. The stored reason and timestamps are the history; the caller
    preserves them (see `storage.db.resume_paused_article`).
    """
    del attempts_before
    return Disposition(RETRIABLE, "analysis_incomplete", 0)


def now_utc() -> str:
    """ISO-8601 UTC, seconds precision — the stamp both timestamps carry."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
