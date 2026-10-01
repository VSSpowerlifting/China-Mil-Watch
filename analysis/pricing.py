"""
The one pinned model price table.

Two things read it: `scripts/spend_guard.py` (pre-flight estimate for bulk
backfills) and `analysis/usage.py` (run-level cost telemetry). Before this
module existed the table lived only in spend_guard; it moved here so the
telemetry did not become a second copy that drifts from the first.

These are ESTIMATES against a table pinned in the repository. Nothing here is
fetched at run time and nothing here reads an invoice: a price change at the
provider is invisible until someone updates this file. Verify against
https://platform.claude.com/docs/en/about-claude/pricing before trusting a
large figure.

Rates verified 2026-10-01 against that page:

    claude-sonnet-4-6   $3 / $15 per MTok (input / output)
    claude-haiku-4-5    $1 / $5  per MTok
    5-minute cache write = 1.25 x base input; cache read = 0.10 x base input.
"""

from __future__ import annotations

from typing import Optional

#: Date the rates below were last checked against the provider's page.
PRICING_CHECKED = "2026-10-01"

# USD per million tokens.
PRICING_USD_PER_MTOK = {
    "claude-sonnet-4-6":          {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5":           {"input": 1.00, "output":  5.00},
    "claude-haiku-4-5-20251001":  {"input": 1.00, "output":  5.00},
}

#: Multipliers on the base input rate. The pipeline marks its system prompt
#: `{"type": "ephemeral"}`, which is the 5-minute TTL, so that is the write
#: rate that applies.
CACHE_WRITE_5M_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10


def estimate_usage_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
) -> Optional[float]:
    """
    Estimated USD for one model's token counts, or None if the model has no
    price on file.

    `input_tokens` is the uncached input the API reports; cache writes and
    reads are reported separately by the API and are priced here from their own
    multipliers, so the four terms never overlap.
    """
    price = PRICING_USD_PER_MTOK.get(model)
    if price is None:
        return None
    rate_in, rate_out = price["input"], price["output"]
    return (
        input_tokens * rate_in
        + output_tokens * rate_out
        + cache_creation_input_tokens * rate_in * CACHE_WRITE_5M_MULTIPLIER
        + cache_read_input_tokens * rate_in * CACHE_READ_MULTIPLIER
    ) / 1_000_000
