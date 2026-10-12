"""
Deduplication filter.

Two articles are considered duplicates if they share:
  (a) an identical URL — exact match, or
  (b) an identical content hash — catches reposts at different URLs.

Both checks are run against the database so the filter is cumulative
across scrape runs, not just within a single day.
"""

import logging
from typing import Optional

from storage import db
from processing.dedup import DedupDecision, DedupResult

logger = logging.getLogger(__name__)


def deduplicate(articles: list[dict]) -> list[dict]:
    """Compatibility wrapper; retains the default database lookup behavior."""
    return deduplicate_detailed(articles).articles


def deduplicate_detailed(articles: list[dict], *, url_lookup=None,
                         hash_lookup=None) -> DedupResult:
    """
    Filter a list of normalized article dicts to those not yet in the DB.
    Runs two passes:
      1. URL check (fast index lookup)
      2. Content-hash check (catches cross-source reposts)

    Returns only genuinely new articles.
    """
    new_articles: list[dict] = []
    url_seen: set[str]  = set()  # Within-batch dedup for the same run
    hash_seen: set[str] = set()
    url_first = {}
    hash_first = {}
    positions = []
    decisions = []
    url_lookup = (lambda url: db.url_exists(url)) if url_lookup is None else url_lookup
    hash_lookup = (lambda sha: db.hash_exists(sha)) if hash_lookup is None else hash_lookup

    for position, article in enumerate(articles):
        url  = article["url"]
        chash = article["content_hash"]

        # Within-batch dedup
        if url in url_seen:
            decisions.append(DedupDecision(position, "batch_url_match", url_first[url]))
            logger.debug("Skipping batch duplicate URL: %s", url)
            continue
        if chash in hash_seen:
            decisions.append(DedupDecision(position, "batch_legacy_hash_match", hash_first[chash]))
            logger.debug("Skipping batch duplicate hash: %s", url)
            continue

        # DB checks
        if url_lookup(url):
            decisions.append(DedupDecision(position, "stored_url_match"))
            logger.debug("Skipping DB duplicate URL: %s", url)
            url_seen.add(url)
            url_first[url] = position
            continue
        if hash_lookup(chash):
            decisions.append(DedupDecision(position, "stored_legacy_hash_match"))
            logger.debug("Skipping DB duplicate content: %s", url)
            hash_seen.add(chash)
            hash_first[chash] = position
            continue

        url_seen.add(url)
        hash_seen.add(chash)
        url_first[url] = position
        hash_first[chash] = position
        decisions.append(DedupDecision(position, "prospective_survivor"))
        positions.append(position)
        new_articles.append(article)

    logger.info(
        "Dedup: %d in → %d new (%d duplicates removed)",
        len(articles),
        len(new_articles),
        len(articles) - len(new_articles),
    )
    return DedupResult(new_articles, positions, decisions)
