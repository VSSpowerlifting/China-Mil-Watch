#!/usr/bin/env python3
"""
Pre-flight spend estimate for bulk backfill runs.

Why this exists (DECISION_LOG 2026-07-31): a translation backfill was launched
on an unverified "~$50, affordable" estimate, exhausted the account's monthly
API allowance mid-run, and blocked all API access for ~35 hours. The estimate
was never checked against anything before the spend was committed.

WHAT THIS DOES NOT DO — read this before trusting it:

    It cannot tell you how much headroom is left on your account. The Anthropic
    API exposes no remaining-balance or remaining-cap endpoint, so no code here
    can answer "can I afford this?". Only the Console can.

What it does do is narrow the gap that actually caused the incident:

  1. Estimates the run's cost from real token arithmetic and current published
     prices, instead of a number someone felt was about right.
  2. Confirms API access is live with one cheap call, before N workers are
     spawned against a dead account.
  3. Forces the estimate to be seen and acknowledged (--confirm-spend) rather
     than passing silently.

Treat the estimate as an order of magnitude, not a quote. Actual cost varies
with article length and how many pass relevance.
"""

import logging
import sys

logger = logging.getLogger("spend_guard")

# USD per million tokens, from the Anthropic pricing docs (checked 2026-07-31).
# Verify against platform.claude.com/docs/en/pricing before trusting a large
# estimate — an out-of-date table here reproduces the original failure.
PRICING_USD_PER_MTOK = {
    "claude-sonnet-4-6":          {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5":           {"input": 1.00, "output":  5.00},
    "claude-haiku-4-5-20251001":  {"input": 1.00, "output":  5.00},
}

# Chinese text tokenizes at roughly one token per character — far denser than
# English (~4 chars/token). Estimating Chinese input at 4 chars/token is the
# single biggest way to under-count a corpus like this one, so assume 1.0.
CHARS_PER_TOKEN_ZH = 1.0

# An English translation of a Chinese article runs longer in tokens than the
# source. 1.3 is deliberately pessimistic: over-estimating costs nothing, and
# under-estimating is what caused the outage.
OUTPUT_TOKEN_RATIO = 1.3

# Above this, the run must be explicitly acknowledged with --confirm-spend.
DEFAULT_CONFIRM_THRESHOLD_USD = 5.00


def _price(model: str) -> dict:
    if model not in PRICING_USD_PER_MTOK:
        raise KeyError(
            f"No price on file for {model!r}. Add it to PRICING_USD_PER_MTOK "
            "from platform.claude.com/docs/en/pricing — refusing to estimate "
            "a run whose cost is unknown."
        )
    return PRICING_USD_PER_MTOK[model]


def estimate_cost_usd(total_input_chars: int, model: str,
                      output_ratio: float = OUTPUT_TOKEN_RATIO) -> dict:
    """
    Estimate the cost of processing `total_input_chars` of Chinese text.

    Returns a dict with the token counts and dollar figures so the caller can
    show its work — an estimate you can't inspect is how you get a bad one.
    """
    price = _price(model)
    in_tok = total_input_chars / CHARS_PER_TOKEN_ZH
    out_tok = in_tok * output_ratio
    in_usd = in_tok / 1_000_000 * price["input"]
    out_usd = out_tok / 1_000_000 * price["output"]
    return {
        "model":            model,
        "input_tokens":     int(in_tok),
        "output_tokens":    int(out_tok),
        "input_usd":        in_usd,
        "output_usd":       out_usd,
        "total_usd":        in_usd + out_usd,
    }


def probe_api_access(model: str = "claude-haiku-4-5-20251001") -> tuple:
    """
    One minimal call to confirm the account can reach the API at all.

    Returns (ok, detail). Catches the case the incident actually hit: spawning
    a pool of workers against an account that is already blocked, turning one
    clear failure into N identical ones.
    """
    try:
        import anthropic
        from config import ANTHROPIC_API_KEY
    except Exception as exc:  # noqa: BLE001 — import/config problems are the caller's to see
        return False, f"could not load API client: {exc}"

    if not ANTHROPIC_API_KEY:
        return False, "ANTHROPIC_API_KEY is not set"

    try:
        anthropic.Anthropic(api_key=ANTHROPIC_API_KEY).messages.create(
            model=model,
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
        return True, "API reachable"
    except anthropic.APIStatusError as exc:
        return False, f"API status error ({exc.status_code}): {exc.message}"
    except Exception as exc:  # noqa: BLE001 — surface anything that blocks the run
        return False, f"{type(exc).__name__}: {exc}"


def preflight(stages: list, article_count: int, confirmed: bool,
              threshold_usd: float = DEFAULT_CONFIRM_THRESHOLD_USD,
              skip_probe: bool = False) -> bool:
    """
    Run the gate. Returns True if the caller may proceed.

    `stages` is a list of (label, input_chars, model, output_ratio) tuples, so
    a two-model pipeline is priced honestly rather than as a single blended
    guess. Screening, for example, pays cheap Haiku on every article but
    Sonnet only on the minority that pass relevance — collapsing that into one
    number is how an estimate ends up wrong by an order of magnitude.

    Order matters: estimate first (free), then probe (one cheap call), then
    require acknowledgement. No bulk work starts until all three pass.
    """
    estimates = [
        (label, estimate_cost_usd(chars, model, ratio))
        for label, chars, model, ratio in stages
    ]
    total_usd = sum(e["total_usd"] for _, e in estimates)

    logger.info("─" * 62)
    logger.info("SPEND PRE-FLIGHT")
    logger.info("  articles              : %d", article_count)
    for label, est in estimates:
        logger.info("  %-20s: %s in + %s out tok on %s → $%.2f",
                    label,
                    f"{est['input_tokens']:,}", f"{est['output_tokens']:,}",
                    est["model"], est["total_usd"])
    logger.info("  EST. TOTAL COST       : $%.2f", total_usd)
    logger.info("")
    logger.info("  This is an estimate of COST, not a check of your remaining")
    logger.info("  balance — the API cannot report headroom. Confirm in the")
    logger.info("  Console that the account can absorb this before proceeding.")
    logger.info("─" * 62)

    if not skip_probe:
        ok, detail = probe_api_access()
        if not ok:
            logger.error("API access probe FAILED: %s", detail)
            logger.error(
                "Aborting before any bulk work. Running anyway would produce "
                "one failed call per article against an account that is "
                "already blocked."
            )
            return False
        logger.info("API access probe: OK")

    if total_usd >= threshold_usd and not confirmed:
        logger.error(
            "Estimated cost $%.2f is at or above the $%.2f confirmation "
            "threshold. Re-run with --confirm-spend once you have checked "
            "the account's remaining headroom in the Console.",
            total_usd, threshold_usd,
        )
        logger.error(
            "To spend less, bound the run with --limit N (the estimate scales "
            "with it)."
        )
        return False

    if confirmed:
        logger.warning("Spend acknowledged via --confirm-spend — proceeding.")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) < 3:
        print(__doc__)
        print("Usage: spend_guard.py <total_input_chars> <model>")
        raise SystemExit(2)
    est = estimate_cost_usd(int(sys.argv[1]), sys.argv[2])
    print(f"Estimated cost: ${est['total_usd']:.2f}")
